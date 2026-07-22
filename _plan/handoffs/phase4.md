# Phase 4 Hand-off — Compilation + Sandbox

## What was built

- **Sandbox image** (`backend/sandbox/Containerfile`, `backend/sandbox/build.sh`):
  Debian bookworm-slim + `gcc-arm-none-eabi`/`libnewlib-arm-none-eabi` (apt
  packages), non-root `builder` (uid 10001) user, `WORKDIR /build`. The
  `ENTRYPOINT` is `build.sh`, baked into the image, which always runs the
  same two fixed commands regardless of any argv it's given — the user's C
  source is data, never part of the command line (see `docs/SECURITY.md`
  T7). Built and verified locally: `podman build -t c-sandbox:latest -f
  Containerfile .` succeeds; `arm-none-eabi-gcc --version` inside the image
  reports `arm-none-eabi-gcc (15:12.2.rel1-1) 12.2.1 20221205`.
- **Fixed build contract** (`build/startup.c`, `build/link.ld`, checked into
  the repo root, never regenerated): minimal Cortex-M4 vector table +
  `Reset_Handler` (`.data` copy, `.bss` zero, call `main()`), generic-but-fixed
  linker script (512K FLASH @ 0x08000000, 128K RAM @ 0x20000000).
- **`signals_def.c` generation** (`backend/app/header_gen.py`): refactored
  `generate_header`'s name-resolution logic into a shared `_resolve_signals`
  helper, added `generate_definitions(measurements)` which emits one
  zero-initialised tentative definition per declared signal — gives
  `signals.h`'s `extern`s something to link against. All existing
  `test_header_gen.py` tests still pass unmodified (pure refactor of the
  internals, same external behaviour).
- **Build runner** (`backend/app/compiler.py::run_build`): writes an
  isolated temp workdir (`user.c`, generated `signals.h`/`signals_def.c`,
  copies of the fixed `startup.c`/`link.ld`), runs one `podman run` with
  every flag from the phase spec (`--network none`, `--memory`/
  `--memory-swap`/`--pids-limit`/`--cpus` caps, `--read-only` + a single
  `-v <workdir>:/build:rw` bind mount, `--cap-drop=ALL`,
  `--security-opt no-new-privileges`, `--user 10001:10001`), wrapped in a
  Python-side `subprocess.run(..., timeout=...)`. On timeout, explicitly
  runs `podman kill <container-name>` — necessary because `podman machine`
  on this dev host is a remote VM reached over SSH, so killing the local
  client process does not stop the container by itself (verified — see
  below). Captures stdout+stderr+exit code+duration, caps log length
  (64 KB) and artifact size (2 MB) before returning.
- **`Build` model** (`backend/app/models.py`) + migration
  `d9df6d1df611_create_builds_table`: `id, workspace_id, user_id, status
  [queued|running|success|error], created_at, duration_ms, exit_code,
  log_text, artifact_ref, bin_artifact_ref`. Two artifact refs (ELF + raw
  `objcopy` binary) instead of the spec's single field — see
  `docs/DECISIONS.md` for why.
- **Build API + worker pool** (`backend/app/builds.py`):
  - `POST /api/workspaces/<id>/builds` — owner-only, 404 on someone else's
    workspace (same convention as phase 2/3), 400 if no source saved, 429
    if the caller already has a build queued/running. Creates the `Build`
    row synchronously (`status=queued`) and submits the actual compile to a
    module-level `ThreadPoolExecutor(max_workers=BUILD_WORKER_COUNT)`
    (default 2).
  - `GET /api/builds/<id>` — poll status + full log, owner-only.
  - `GET /api/workspaces/<id>/builds` — recent builds for a workspace.
  - Chose polling over SSE (phase brief explicitly allows this fallback) —
    `run_build` is a single blocking call with no partial output to stream,
    and real compiles finish in ~1-2s at this scope. See
    `docs/DECISIONS.md`.
- **Frontend** (`frontend/src/pages/Workspace.jsx`, `api.js`, `App.css`): a
  Compile button next to Save (saves current source first, then triggers a
  build and starts polling `GET /api/builds/<id>` every 800ms) and a log
  console panel showing live status/duration/exit-code and the full
  compiler stdout+stderr. `npm run build` verified clean.
- **`docs/SECURITY.md`** (new, required deliverable): full threat model
  table (T1-T8) with mitigation + residual risk per item, the exact
  `podman run` flags used, and an "Observed evidence" section. Includes one
  correction to the phase brief's own T1 example, verified by testing: a
  bare `while(1){}` does not hang `arm-none-eabi-gcc` (compilation never
  executes the loop, and this project never runs the produced binary) — the
  timeout was instead verified via a forced short-timeout kill test, and a
  real compile-time DoS attempt (an exponential macro expansion, ~2^23
  repetitions) was caught by the memory cap in ~3-4 seconds before the
  timeout would matter.
- **Tests**: `backend/tests/test_compiler.py` (3 tests, real podman:
  good-code → real ELF, syntax error → real gcc error text, forced-short-
  timeout → killed with no orphaned container) and
  `backend/tests/test_builds_api.py` (3 tests: end-to-end trigger-and-poll
  via the real sandbox, cross-user 404, rate-limit 429 using a mocked slow
  compile to make the race deterministic). 29/29 tests pass overall.
- **`docs/DECISIONS.md`** and **`README.md`**: phase 4 sections added —
  `signals_def.c` rationale, fixed startup/linker rationale, fixed-entrypoint
  script rationale, toolchain-via-apt-package rationale, polling rationale,
  worker-pool/rate-limit rationale, dual-artifact-ref rationale, pointer to
  `docs/SECURITY.md`.

## What was cut / deferred (per ground rules)

- **SSE/streaming build output** — polling fallback used instead
  (explicitly allowed by the phase brief). See `docs/DECISIONS.md`.
- **Custom seccomp profile** — relies on Podman's default profile; not
  hand-tightened for time. Documented as residual risk in
  `docs/SECURITY.md` (T5).
- **Rootless-podman enforcement in code** — `compiler.py` issues the same
  `podman run` regardless of whether the CLI it's talking to is a rootless
  or rootful connection; nothing fails closed if a deploy accidentally
  points at a rootful daemon. This dev environment's `podman machine`
  defaulted to a **rootful** connection out of the box
  (`podman-machine-default-root`) — I explicitly ran `podman system
  connection default podman-machine-default` to switch to the rootless one
  before building/testing, and verified `podman info` reports `rootless:
  true`. Documented as a deploy-host checklist item, not code-enforced —
  see `docs/SECURITY.md` T3.
- **Filesystem quota on the per-build workdir** — it's a plain host temp
  directory, not a size-bounded tmpfs; bounded in practice by the memory
  cap + timeout, not a hard quota. See `docs/SECURITY.md` T6.
- **Sliding-window / token-bucket rate limiting** — "one outstanding build
  per user" was judged sufficient for this scope; does not cap sequential
  builds/hour for a well-behaved single client. See `docs/DECISIONS.md`.
- **Load-testing the resource caps** (256m memory, 64 pids, 1 cpu) against
  a wider range of real programs — untuned guesses appropriate to this
  scope, not production-tuned values. Noted in `docs/SECURITY.md` T2.

## Real command output

### Podman machine setup (environment note for the next agent)

This dev host is Windows; `podman machine` was already installed
(v5.7.1) but not running, and its WSL VM crashed and had to be reinitialized
once mid-session (unrelated environment flakiness, not a code issue) via
`podman machine rm` + `podman machine init --memory 4096 --cpus 4
--disk-size 30` + `podman machine start`. After reinit the default
connection was rootless by default; no further action was needed for
subsequent commands in this session.

### Sandbox image build + toolchain verification

```
$ podman build -t c-sandbox:latest -f Containerfile .
...
Successfully tagged localhost/c-sandbox:latest

$ podman run --rm --entrypoint arm-none-eabi-gcc c-sandbox:latest --version
arm-none-eabi-gcc (15:12.2.rel1-1) 12.2.1 20221205
Copyright (C) 2022 Free Software Foundation, Inc.
```

### The three required observations (via `backend/app/compiler.py::run_build`, real podman)

**1. Good code -> real ARM ELF:**
```
OK success 0 890
$ file test_out.elf
test_out.elf: ELF 32-bit LSB executable, ARM, EABI5 version 1 (SYSV), statically linked, with debug_info, not stripped
```

**2. Syntax error -> real gcc error text:**
```
STATUS error EXIT 1
user.c: In function 'main':
user.c:1:26: error: expected expression before ';' token
    1 | int main(void) { int x = ; return 0 }
      |                          ^
user.c:1:36: error: expected ';' before '}' token
...
```

**3. Timeout kills the container (forced short timeout, see docs/SECURITY.md T1 for why a
literal `while(1){}` source doesn't itself hang the compiler):**
```
$ SANDBOX_TIMEOUT_SECONDS=0.2 python -c "... run_build('while(1){}...', [])"
STATUS error EXIT None DURATION_MS 1015
[build killed: exceeded 0s wall-clock limit]

$ podman ps -a --filter name=c-sandbox-build
CONTAINER ID  IMAGE       COMMAND     CREATED     STATUS      PORTS       NAMES
(empty -- no orphaned container)
```

### Bounded worker pool observation (task 3 DoD)

```
BUILD_WORKER_COUNT = 2
peak concurrent compiles observed = 2
```
(5 concurrent build requests fired across 5 different users, instrumented
fake compile sleeps 1s each; peak simultaneous in-flight compiles never
exceeded the pool size.)

### Full live-server end-to-end flow (real Flask dev server, real HTTP, real podman)

```
--- signup ---
{"email": "livetest@example.com", "id": 8}
--- create workspace, save source ---
WS_ID=5
{"ok": true}
--- trigger build ---
{"id": 1, "status": "queued", "workspace_id": 5, "user_id": 8, ...}
--- poll ---
poll 1: "status": "running"
poll 2: "status": "success"
{"duration_ms": 907, "exit_code": 0, "has_artifact": true, "status": "success", ...}

$ file instance/uploads/workspace_5/builds/1/out.elf
...: ELF 32-bit LSB executable, ARM, EABI5 version 1 (SYSV), statically linked, with debug_info, not stripped
```

### Backend tests

```
$ python -m pytest tests/ -v
tests/test_auth.py::test_signup_success PASSED                           [  3%]
tests/test_auth.py::test_signup_duplicate_email_rejected PASSED          [  6%]
tests/test_auth.py::test_login_wrong_password_401 PASSED                 [ 10%]
tests/test_auth.py::test_me_requires_session PASSED                      [ 13%]
tests/test_builds_api.py::test_trigger_build_runs_end_to_end_via_real_sandbox PASSED [ 17%]
tests/test_builds_api.py::test_build_requires_owner PASSED               [ 20%]
tests/test_builds_api.py::test_rate_limit_rejects_second_build_while_one_outstanding PASSED [ 24%]
tests/test_compiler.py::test_syntax_error_yields_error_status_with_real_gcc_log PASSED [ 27%]
tests/test_compiler.py::test_good_program_compiles_to_a_real_arm_elf PASSED [ 31%]
tests/test_compiler.py::test_timeout_path_marks_status_error_and_kills_the_container PASSED [ 34%]
tests/test_header_gen.py::... (9 tests) PASSED
tests/test_parser.py::... (6 tests) PASSED
tests/test_signals_api.py::... (4 tests) PASSED
============================= 29 passed in 6.31s ==============================
```

### Migration applied

```
$ flask db migrate -m "create builds table"
INFO  [alembic.autogenerate.compare.tables] Detected added table 'builds'
Generating F:\Task\backend\migrations\versions\d9df6d1df611_create_builds_table.py ...  done

$ flask db upgrade
INFO  [alembic.runtime.migration] Running upgrade d1bbb003f98f -> d9df6d1df611, create builds table
```

### Frontend build

```
$ npm run build
vite v5.4.21 building for production...
✓ 52 modules transformed.
dist/index.html                 0.46 kB │ gzip:  0.30 kB
dist/assets/index-BNM_fAjW.css  4.41 kB │ gzip:  1.52 kB
dist/assets/index-CNZzkA6T.js 188.47 kB │ gzip: 60.85 kB
✓ built in 605ms
```

## Honesty note on browser verification

Same caveat as phase 3: no browser-automation tool is available in this
environment, so the Compile button / log console panel were **not**
click-tested in an actual browser. What *was* verified for real: the
production build compiles cleanly (above), and the full API surface the
frontend calls (`POST /builds`, `GET /builds/<id>` polling) was exercised
against a real running Flask dev server with real podman compiles, producing
the exact response shapes `Workspace.jsx` consumes (`status`, `duration_ms`,
`exit_code`, `log_text`, `has_artifact`). If the next agent can run a
browser: log in -> open a workspace -> Compile -> confirm the console panel
shows "running" then real gcc output and a final success/duration.

## Notes for the next agent (phase 5)

- `Build.artifact_ref` / `Build.bin_artifact_ref` are storage-relative paths
  (via the existing `LocalStorage` interface) to the linked ELF and raw
  `objcopy` binary respectively, at
  `workspace_<id>/builds/<build_id>/out.{elf,bin}`. Phase 5's `Artifact`
  model/marketplace should read the binary from `bin_artifact_ref` (that's
  the "downloadable binary" the brief wants) and can surface `artifact_ref`
  (the ELF) as a secondary/debug download if useful.
- `Build` already carries everything phase 5's required per-artifact
  metadata needs except a human filename: `log_text` (full log),
  `created_at`, `duration_ms`, `workspace_id`, `user_id`. Phase 5 should
  join through `Build` rather than duplicating any of this onto a new
  table.
- `docs/SECURITY.md` T3/T5 residual risk (rootless podman is a deploy-host
  config, not code-enforced) is directly relevant to `06_devops_instructions.txt`
  — worth flagging to Tanishq for the actual deploy host checklist.
- `BUILD_WORKER_COUNT`, `SANDBOX_TIMEOUT_SECONDS`, `SANDBOX_MEMORY`,
  `SANDBOX_PIDS_LIMIT`, `SANDBOX_CPUS`, `SANDBOX_UID`, `SANDBOX_IMAGE` are
  all environment-overridable (`backend/app/compiler.py` /
  `backend/app/builds.py`) — no cloud-provider assumptions baked in, per
  ground rules.
