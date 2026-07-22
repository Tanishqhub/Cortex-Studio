"""Runs a workspace's C source through arm-none-eabi-gcc inside a locked-down
Podman sandbox container. See docs/SECURITY.md for the full threat model
this module implements mitigations for.

NEVER run user code / gcc on the host process directly -- always inside the
sandbox container, via a fully server-controlled `podman run` argv. The user
never supplies compiler flags, include paths, or filenames (see
_plan/phase4.txt guardrails).
"""

import os
import shutil
import subprocess
import tempfile
import time
import uuid

from .header_gen import generate_definitions, generate_header

_APP_DIR = os.path.dirname(os.path.abspath(__file__))
BUILD_FIXED_DIR = os.path.abspath(os.path.join(_APP_DIR, "..", "..", "build"))

SANDBOX_IMAGE = os.environ.get("SANDBOX_IMAGE", "c-sandbox:latest")
SANDBOX_TIMEOUT_SECONDS = float(os.environ.get("SANDBOX_TIMEOUT_SECONDS", 15))
SANDBOX_MEMORY = os.environ.get("SANDBOX_MEMORY", "256m")
SANDBOX_PIDS_LIMIT = os.environ.get("SANDBOX_PIDS_LIMIT", "64")
SANDBOX_CPUS = os.environ.get("SANDBOX_CPUS", "1")
SANDBOX_UID = os.environ.get("SANDBOX_UID", "10001")

MAX_LOG_BYTES = 64 * 1024
MAX_ARTIFACT_BYTES = 2 * 1024 * 1024


def _sandbox_run_args(workdir_host_path):
    """The exact, fully server-controlled `podman run` argv. Every flag here
    corresponds to one line of the docs/SECURITY.md threat model; see that
    file for the mitigation <-> flag mapping. Nothing here is derived from
    user input except the bind-mounted workdir path, which contains only
    files this module itself wrote (or copied from the fixed build/ dir)."""
    container_name = f"c-sandbox-build-{uuid.uuid4().hex}"
    return container_name, [
        "podman",
        "run",
        "--rm",
        "--name",
        container_name,
        "--network",
        "none",  # T4: no network exfiltration/callbacks
        "--memory",
        SANDBOX_MEMORY,  # T2: memory exhaustion cap
        "--memory-swap",
        SANDBOX_MEMORY,  # no swap headroom beyond the memory cap
        "--pids-limit",
        SANDBOX_PIDS_LIMIT,  # T2: fork-bomb cap
        "--cpus",
        SANDBOX_CPUS,  # T1: CPU share cap (backstop; timeout is primary)
        "--read-only",  # T3/T6: rootfs read-only; only /build is writable
        "-v",
        f"{workdir_host_path}:/build:rw",  # T3: single per-build bind mount, nothing else from the host
        "--cap-drop=ALL",  # T5: drop all Linux capabilities
        "--security-opt",
        "no-new-privileges",  # T5: block setuid/setgid privilege escalation
        "--user",
        f"{SANDBOX_UID}:{SANDBOX_UID}",  # T5: non-root inside the container too
        SANDBOX_IMAGE,
    ]


def run_build(source_code, measurements):
    """Compile `source_code` (the workspace's saved main.c-equivalent)
    against `measurements` (the workspace's parsed A2L signals, for
    signals.h / signals_def.c generation). Returns a dict:
        status: "success" | "error"
        exit_code: int | None (None only if the container was killed)
        log_text: str (compiler stdout+stderr, capped at MAX_LOG_BYTES)
        duration_ms: int
        elf_bytes: bytes | None
        bin_bytes: bytes | None
    Never raises for ordinary build failures (bad source, timeout) -- those
    are reported via the returned dict, not exceptions.
    """
    workdir = tempfile.mkdtemp(prefix="c-sandbox-build-")
    try:
        with open(os.path.join(workdir, "user.c"), "w", encoding="utf-8", newline="\n") as f:
            f.write(source_code)
        with open(os.path.join(workdir, "signals.h"), "w", encoding="utf-8", newline="\n") as f:
            f.write(generate_header(measurements))
        with open(os.path.join(workdir, "signals_def.c"), "w", encoding="utf-8", newline="\n") as f:
            f.write(generate_definitions(measurements))
        shutil.copy(os.path.join(BUILD_FIXED_DIR, "startup.c"), workdir)
        shutil.copy(os.path.join(BUILD_FIXED_DIR, "link.ld"), workdir)

        container_name, cmd = _sandbox_run_args(workdir)

        start = time.monotonic()
        timed_out = False
        try:
            proc = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=SANDBOX_TIMEOUT_SECONDS,
            )
            exit_code = proc.returncode
            log_text = proc.stdout + proc.stderr
        except subprocess.TimeoutExpired as exc:
            timed_out = True
            exit_code = None
            log_text = (exc.stdout or "") + (exc.stderr or "")
            # subprocess.run() already killed the local `podman run` client
            # process, but that does NOT stop the remote container (podman
            # machine is a separate VM reached over SSH) -- it must be
            # killed explicitly. Best-effort: the container has --rm, so a
            # successful kill also removes it.
            subprocess.run(
                ["podman", "kill", container_name],
                capture_output=True,
                text=True,
                timeout=10,
            )

        duration_ms = int((time.monotonic() - start) * 1000)

        if timed_out:
            log_text += f"\n[build killed: exceeded {SANDBOX_TIMEOUT_SECONDS:.0f}s wall-clock limit]\n"

        if len(log_text) > MAX_LOG_BYTES:
            log_text = log_text[:MAX_LOG_BYTES] + "\n[log truncated at size cap]\n"

        elf_bytes = None
        bin_bytes = None

        if not timed_out and exit_code == 0:
            elf_path = os.path.join(workdir, "out.elf")
            bin_path = os.path.join(workdir, "out.bin")
            if os.path.isfile(elf_path) and os.path.isfile(bin_path):
                elf_size = os.path.getsize(elf_path)
                bin_size = os.path.getsize(bin_path)
                if elf_size <= MAX_ARTIFACT_BYTES and bin_size <= MAX_ARTIFACT_BYTES:
                    with open(elf_path, "rb") as f:
                        elf_bytes = f.read()
                    with open(bin_path, "rb") as f:
                        bin_bytes = f.read()
                else:
                    log_text += "\n[artifact exceeded size cap; discarded, build marked as failed]\n"
                    exit_code = 1
            else:
                log_text += "\n[compiler reported success but no artifact was found; build marked as failed]\n"
                exit_code = 1

        status = "success" if elf_bytes is not None else "error"

        return {
            "status": status,
            "exit_code": exit_code,
            "log_text": log_text,
            "duration_ms": duration_ms,
            "elf_bytes": elf_bytes,
            "bin_bytes": bin_bytes,
        }
    finally:
        shutil.rmtree(workdir, ignore_errors=True)
