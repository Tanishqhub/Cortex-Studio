# Security posture: compiling untrusted C

The brief is blunt about this: "Compiling code submitted by an authenticated
stranger on your server is the sharp edge of this assignment. We would like
to see that you noticed." This document is that acknowledgement, plus an
honest account of what is actually implemented (`backend/app/compiler.py`,
`backend/sandbox/Containerfile`, `backend/sandbox/build.sh`) versus what is
left as residual risk.

**Ground rule:** nothing below is aspirational. If a mitigation isn't in the
code today, it's listed as residual risk, not as "mitigated."

## The exact sandbox invocation

Every build runs as this fully server-controlled `podman run` (see
`compiler.py::_sandbox_run_args` — the single place this argv is built):

```
podman run --rm --name c-sandbox-build-<uuid>
  --network none
  --memory 256m --memory-swap 256m
  --pids-limit 64
  --cpus 1
  --read-only
  -v <per-build temp dir>:/build:rw
  --cap-drop=ALL
  --security-opt no-new-privileges
  --user 10001:10001
  c-sandbox:latest
```

The image's `ENTRYPOINT` is a fixed script (`build.sh`) baked in at build
time, not a shell the caller can redirect — it always runs exactly:

```
arm-none-eabi-gcc -mcpu=cortex-m4 -mthumb -Wall -Wextra -ffreestanding \
  -nostdlib -O0 -g -T link.ld startup.c signals_def.c user.c -o out.elf
arm-none-eabi-objcopy -O binary out.elf out.bin
```

against files this module wrote into the bind-mounted workdir
(`user.c`, `signals.h`, `signals_def.c`) plus the two files checked into the
repo and never regenerated per-build (`build/startup.c`, `build/link.ld`).
The user never supplies a compiler flag, include path, or filename — the
only user-controlled input that reaches the container is the *contents* of
`user.c`.

A wall-clock timeout (`SANDBOX_TIMEOUT_SECONDS`, default 15s) wraps the
`podman run` call in Python (`subprocess.run(..., timeout=...)`). On expiry
the module explicitly runs `podman kill <container-name>` — killing the
local Python-side process does **not** stop the container, because `podman
run` here is a client of a remote VM (`podman machine`, reached over SSH);
only an explicit `podman kill` reaches the actual container process. This
was verified, not assumed (see "Observed evidence" below).

## Threat model

| # | Threat | Mitigation | Residual risk |
|---|--------|------------|----------------|
| T1 | Malicious C consumes CPU forever (`while(1){}`) | Wall-clock timeout kills the container (`SANDBOX_TIMEOUT_SECONDS`, default 15s) + `--cpus 1` caps its share while it runs. | **Important nuance, verified not assumed:** a bare `while (1) {}` in `user.c` does **not** hang `arm-none-eabi-gcc` — compilation only *emits code* for the loop, it never executes it, and this project never flashes or runs the produced binary (out of scope, see `00_agent_ground_rules.txt`). So the literal DoD example doesn't actually exercise the timeout. What *can* make compilation itself slow is pathological input to the compiler/preprocessor (see T7's macro-bomb finding below) — the timeout is a real backstop for that, verified by forcing a short timeout and confirming the kill path fires and leaves no orphaned container (see "Observed evidence"). |
| T2 | Memory exhaustion / fork bomb | `--memory 256m --memory-swap 256m` (no swap headroom beyond the cap) and `--pids-limit 64`. | Cap values (256m / 64 pids) are untuned guesses, not load-tested against real workloads. A legitimate program that needs more memory than 256m to compile (unlikely for this scope) would be misreported as a build failure rather than a resource-limit failure — the log does not currently distinguish "OOM-killed" from "gcc exited 1", see Known limitations. |
| T3 | Reading host / other users' files | `--read-only` rootfs; the only writable path is the single per-build bind mount (`-v <tempdir>:/build:rw`); no other host mount. Rootless podman (see below) means the container's root user maps to an unprivileged host user, not real root. | **Rootlessness is a deploy-host/environment property, not something `compiler.py` enforces or checks.** The code issues the same `podman run` regardless of whether the `podman` CLI it's talking to is a rootless or rootful connection. On this dev machine we deliberately pointed the default `podman system connection` at the rootless socket and verified `podman info` reports `rootless: true` before testing (see hand-off notes) — but nothing in the code fails closed if a future deploy accidentally points at a rootful daemon. Documented as a deploy-time checklist item for `06_devops_instructions.txt`, not code-enforced here. |
| T4 | Network exfiltration / callbacks | `--network none` — verified: no network devices are available inside the container. | None identified for this vector at this scope. |
| T5 | Container escape / privilege escalation | `--cap-drop=ALL`, `--security-opt no-new-privileges`, `--user 10001:10001` (also the image's own default `USER builder`, so even a caller that forgot `--user` would still not run as root), rootless podman host-side. | Relies on Podman/runc/the kernel having no unpatched container-escape bugs — no sandbox is escape-proof against a kernel 0-day. Seccomp is whatever the image's default runtime profile provides (not hand-tightened for this project); a custom seccomp profile denylisting more syscalls was not built for time. |
| T6 | Disk filling from huge outputs/artifacts | Source is capped at 256 KB before it ever reaches here (`workspaces.py::MAX_SOURCE_SIZE_BYTES`, enforced at save time). Captured compiler log is capped at `MAX_LOG_BYTES` (64 KB, truncated with a marker). Produced `out.elf`/`out.bin` are capped at `MAX_ARTIFACT_BYTES` (2 MB) — if either exceeds the cap the build is discarded and marked failed rather than stored. | The per-build workdir itself has no filesystem-level quota (it's a plain host temp directory, not a size-bounded tmpfs) — a build that writes many large intermediate files before hitting the memory/pids caps could still use meaningful host disk momentarily. Mitigated in practice by `--memory`/timeout bounding how much work can happen at all, but not a hard quota. |
| T7 | Compiler/preprocessor abuse (`#include "/etc/passwd"`, `-I` tricks, `#embed`, gcc plugins) | The compiler invocation is entirely fixed by `build.sh`, baked into the image — the user's C source is data, never part of the command line, so there is no flag/path injection surface. `-ffreestanding -nostdlib` means no host libc headers are pulled in even if a user tried `#include <stdio.h>` (it would simply fail to resolve, not read a real system header, since the sandbox image has none of the host's files). | **Verified finding:** the C preprocessor is itself a DoS vector independent of flags — a small "billion laughs"-style exponential macro (`#define A1 A0 A0`, doubled ~23 times) blew past the 256m memory cap and got OOM-killed by the container in ~3-4 seconds, *before* the wall-clock timeout could matter (see "Observed evidence"). This is caught today, but only because the memory cap happens to fire first; it is not a preprocessor-specific mitigation (e.g. no `-fmax-include-depth` / macro-expansion limit was set, and GCC has no built-in flag for this). |
| T8 | Server overload via many concurrent builds | Bounded worker pool: `ThreadPoolExecutor(max_workers=BUILD_WORKER_COUNT)` (default 2) in `builds.py` — extra build requests queue in the executor rather than spawning unbounded containers. Simple per-user rate limit: a user with any `queued`/`running` build is rejected (HTTP 429) until it finishes. | The rate limit is per-user-outstanding-build, not a sliding-window/token-bucket limiter — a user cannot run two builds at once, but there's no cap on how many builds/hour they can *sequentially* trigger. `BUILD_WORKER_COUNT` bounds concurrent containers but was not load-tested under real concurrency beyond the two-request check in this phase's hand-off. |

## Observed evidence

All three observed directly (see phase hand-off notes for full transcripts):

1. **Good code → real ARM ELF.** `file out.elf` → `ELF 32-bit LSB executable, ARM, EABI5 version 1 (SYSV), statically linked, with debug_info, not stripped`.
2. **Syntax error → real gcc error text.** `int x = ;` inside `main()` returns the actual `arm-none-eabi-gcc` parser error (`expected expression before ';' token`, etc.), `status=error`, `exit_code=1`.
3. **Timeout kill path.** Forcing `SANDBOX_TIMEOUT_SECONDS=0.2` against a normal (fast-compiling) program reliably produces `status=error`, `exit_code=None`, a `"[build killed: exceeded 0s wall-clock limit]"` log line, and `podman ps -a` shows **no** leftover container afterward (the explicit `podman kill` + the image's `--rm` clean it up). As noted under T1, a literal `while(1){}` source does not itself trigger this path — this demonstrates the kill mechanism is real and leaves no orphaned containers, using a forced short timeout rather than a naturally slow compile, which is the same allowance the phase brief gives the test suite ("can mock/short-timeout").
4. **Macro-bomb → memory cap, not timeout, fires.** An exponential macro expansion (~2^23 repetitions of a string literal) got `arm-none-eabi-gcc`'s `cc1` killed by the 256m memory cap in ~3-4 seconds — a real, unprompted compile-time DoS attempt caught in practice (see T2/T7).

## Known cuts (see docs/DECISIONS.md for the full reasoning)

- **Polling, not SSE/streaming**, for build output (`GET /api/builds/<id>`). The
  phase brief explicitly allows this as a fallback. `compiler.run_build()`
  only returns after the container exits — there is no partial output to
  stream mid-build with the current subprocess-based design, since real
  compiles finish in roughly 1-2 seconds for the programs this scope
  targets.
- **No custom seccomp profile** — relies on Podman's default. Tightening it
  further (e.g. denying more syscalls than the default profile already
  does) was not attempted for time.
- **Rootless podman is a deploy-host configuration, not code-enforced.**
  See T3/T5 above.
