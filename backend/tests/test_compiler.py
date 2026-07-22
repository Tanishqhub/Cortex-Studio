"""Tests for the sandboxed build runner (backend/app/compiler.py).

These are real integration tests -- they invoke actual `podman run` against
the `c-sandbox:latest` image (see backend/sandbox/), same as production.
There is no mocked-compiler unit-test path: the whole point of this phase is
that the sandbox behaviour itself is what's under test (see
_plan/phase4.txt task 6 and docs/SECURITY.md). Requires Podman to be
installed and the `c-sandbox:latest` image built (`podman build -t
c-sandbox:latest -f backend/sandbox/Containerfile backend/sandbox`) -- if
either is missing these tests fail with a clear podman/image error, not a
silent skip, per the "fail loudly" ground rule.
"""

import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

os.environ.setdefault("SECRET_KEY", "test-secret-key")
os.environ["DATABASE_URL"] = "sqlite://"
os.environ["ENV"] = "testing"

from app.compiler import run_build  # noqa: E402


def test_syntax_error_yields_error_status_with_real_gcc_log():
    bad_source = "int main(void) { int x = ; return 0 }\n"
    result = run_build(bad_source, [])

    assert result["status"] == "error"
    assert result["exit_code"] == 1
    assert result["log_text"].strip() != ""
    assert "error" in result["log_text"].lower()
    assert result["elf_bytes"] is None


def test_good_program_compiles_to_a_real_arm_elf():
    good_source = "int main(void) { volatile int x = 1 + 1; (void)x; return 0; }\n"
    result = run_build(good_source, [])

    assert result["status"] == "success"
    assert result["exit_code"] == 0
    assert result["elf_bytes"] is not None
    # ARM ELF magic + machine type: \x7fELF, class 1 (32-bit), machine 0x28 (EM_ARM) little-endian
    assert result["elf_bytes"][:4] == b"\x7fELF"
    assert result["elf_bytes"][18:20] == b"\x28\x00"
    assert result["bin_bytes"] is not None


def test_timeout_path_marks_status_error_and_kills_the_container(monkeypatch):
    # Per phase brief: "can mock/short-timeout". We force a timeout far
    # shorter than any real compile can finish in, against an otherwise
    # perfectly ordinary program -- see docs/SECURITY.md T1 for why a
    # literal `while(1){}` source does not itself hang the compiler.
    monkeypatch.setattr("app.compiler.SANDBOX_TIMEOUT_SECONDS", 0.01)

    source = "int main(void) { return 0; }\n"
    result = run_build(source, [])

    assert result["status"] == "error"
    assert result["exit_code"] is None
    assert "wall-clock limit" in result["log_text"]
    assert result["elf_bytes"] is None
