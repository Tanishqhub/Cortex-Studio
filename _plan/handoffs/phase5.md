# Phase 5 Hand-off — Artifact Marketplace + Polish

## What was built

- **`Artifact` model** (`backend/app/models.py`) + migration
  `5735222756dd_create_artifacts_table`: `id, build_id (FK, unique), filename,
  size_bytes, download_ref, created_at`. Thin by design — joins through
  `Build` (`self.build`) for log/duration/timestamps/workspace/user rather
  than duplicating them. `to_dict(include_log=False)` assembles the full
  required-metadata shape in one call.
- **`LocalStorage.read_bytes`** (`backend/app/storage.py`) — the one method
  the interface was missing to serve binary downloads.
- **Artifact creation wired into the build pipeline**
  (`backend/app/builds.py::_run_build_job`): right after a successful
  build's raw binary (`bin_bytes`) is written to storage, one `Artifact`
  row is created pointing at it. A failed/errored build never gets an
  `Artifact` (verified by test).
- **Marketplace API** (`backend/app/marketplace.py`, new blueprint):
  - `GET /api/marketplace` — list all artifacts (all-public visibility, see
    below), newest first.
  - `GET /api/artifacts/<id>` — full detail incl. full build log.
  - `GET /api/artifacts/<id>/download` — raw binary,
    `application/octet-stream`, `Content-Disposition: attachment`.
  - All three `@login_required`, none ownership-checked (by design).
- **Visibility model: all-public-to-logged-in-users.** Chosen as the
  literal reading of "a shared, browsable catalogue" from the phase goal.
  Full reasoning + two rejected alternatives (owner-only, public-browse/
  owner-download) in `docs/DECISIONS.md` Phase 5.
- **Frontend**: `frontend/src/pages/Marketplace.jsx` (table: filename,
  workspace, user, built-at, duration, size, links to detail) and
  `ArtifactDetail.jsx` (metadata + full log + Download button). Wired into
  `App.jsx` as `/marketplace` and `/marketplace/:id` (both behind
  `RequireAuth`), reachable via a link on the landing page and a
  "Marketplace" link in the workspace list header. `api.js` gained
  `listMarketplace`, `getArtifact`, `artifactDownloadUrl`. `npm run build`
  verified clean.
- **`backend/seed.py`**: idempotent script creating >=2 test accounts
  (`SEED_USER{1,2}_EMAIL`/`_PASSWORD` env vars, or a generated random
  password printed once). Safe to re-run — skips existing accounts.
- **Tests**: `backend/tests/test_marketplace_api.py` (6 tests, real podman
  sandbox — same policy as Phase 4's tests): successful build → artifact
  with correct metadata; visible to a *different* logged-in user, not just
  the owner; download returns real binary bytes matching the reported size;
  marketplace/detail/download all require login; unknown artifact 404s;
  failed build produces no artifact. **35/35 tests pass overall** (29 from
  phases 1-4 + 6 new).
- **`docs/DECISIONS.md`** and **`README.md`**: Phase 5 sections added —
  visibility model + alternatives, Artifact-joins-through-Build rationale,
  inline-creation-not-a-publish-step rationale, generated-filename
  rationale, why `.bin` not `.elf` is served, `read_bytes`-only (no R2
  client) rationale, seed-script-not-CLI rationale, plain-table-UI
  rationale. README also finalized per task 6: architecture diagram
  (mermaid), key decisions summary, security posture pointer, known
  limitations (consolidated from all phases), time-spent note, and
  attribution (arm-none-eabi-gcc, Monaco, Flask/SQLAlchemy stack, React/Vite
  stack — nothing else copied in).

## What was cut / deferred (per ground rules)

- **No pagination on `GET /api/marketplace`** — fine at this project's test
  scale; would need it before real volume. Noted in README known
  limitations.
- **No delete/unpublish from the marketplace** — out of scope (ground rules
  explicitly exclude rating/moderation-style features); every successful
  build is permanent.
- **No R2/S3 storage backend implementation** — only `LocalStorage` was
  extended (`read_bytes`). Consistent with every earlier phase's pattern:
  build the interface + local implementation, leave the cloud backend to
  the DevOps phase per `00_agent_ground_rules.txt`.
- **ELF (debug) artifact not exposed for download** — only the raw `.bin`
  is served; the ELF stays on `Build.artifact_ref` if a future "download
  debug symbols" feature is wanted.
- **Walkthrough recording**: not produced as a video/screenshot set by this
  agent — no browser-automation or screen-capture tool is available in
  this environment (same limitation every prior phase hit). Instead, the
  full flow was verified end-to-end via a real running Flask dev server +
  curl (see below); this document + the exact commands below constitute
  the walkthrough evidence. **Tanishq should record the actual 5-10 min
  screen capture** following the "End-to-end smoke test" steps in
  `README.md`, since a human clicking through a browser is needed for the
  literal deliverable.

## Real command output

### Migration applied

```
$ flask db migrate -m "create artifacts table"
INFO  [alembic.autogenerate.compare.tables] Detected added table 'artifacts'
Generating F:\Task\backend\migrations\versions\5735222756dd_create_artifacts_table.py ...  done

$ flask db upgrade
INFO  [alembic.runtime.migration] Running upgrade d9df6d1df611 -> 5735222756dd, create artifacts table
```

### Backend tests (full suite)

```
$ python -m pytest tests/ -v
tests/test_auth.py::test_signup_success PASSED
tests/test_auth.py::test_signup_duplicate_email_rejected PASSED
tests/test_auth.py::test_login_wrong_password_401 PASSED
tests/test_auth.py::test_me_requires_session PASSED
tests/test_builds_api.py::test_trigger_build_runs_end_to_end_via_real_sandbox PASSED
tests/test_builds_api.py::test_build_requires_owner PASSED
tests/test_builds_api.py::test_rate_limit_rejects_second_build_while_one_outstanding PASSED
tests/test_compiler.py::test_syntax_error_yields_error_status_with_real_gcc_log PASSED
tests/test_compiler.py::test_good_program_compiles_to_a_real_arm_elf PASSED
tests/test_compiler.py::test_timeout_path_marks_status_error_and_kills_the_container PASSED
tests/test_header_gen.py:: (9 tests) PASSED
tests/test_marketplace_api.py::test_successful_build_appears_in_marketplace_with_required_metadata PASSED
tests/test_marketplace_api.py::test_marketplace_visible_to_any_logged_in_user_not_just_owner PASSED
tests/test_marketplace_api.py::test_download_returns_real_binary_bytes PASSED
tests/test_marketplace_api.py::test_marketplace_and_download_require_login PASSED
tests/test_marketplace_api.py::test_unknown_artifact_404s PASSED
tests/test_marketplace_api.py::test_failed_build_does_not_create_an_artifact PASSED
tests/test_parser.py:: (6 tests) PASSED
tests/test_signals_api.py:: (4 tests) PASSED
============================= 35 passed in 10.62s ==============================
```

### Seed script

```
$ python seed.py
created tester1@example.com / IwimAkOUrtOgKpur (generated -- copy this into the private submission note now)
created tester2@example.com / lB399wQ4OdVdFT3b (generated -- copy this into the private submission note now)

$ python seed.py   # idempotency check
skip tester1@example.com (already exists)
skip tester2@example.com (already exists)
```

### Full live-server end-to-end flow (real Flask dev server, real HTTP, real podman)

```
--- login as tester1 ---
{"email": "tester1@example.com", "id": 9}

--- create workspace ---
{"id": 6, "name": "smoke-ws", "owner_id": 9, "has_a2l_file": false}

--- upload real A2L sample ---
{'measurement_count': 173, 'characteristic_count': 0,
 'datatypes_seen': ['A_UINT64', 'FLOAT32_IEEE', 'SBYTE', 'SLONG', 'SWORD', 'UBYTE', 'ULONG', 'UWORD'],
 'skipped': []}

--- pick a real signal and write C using it ---
SIGNAL=Acc_Pedal_Pos
code: #include "signals.h"

int main(void) {
    int x = (int)Acc_Pedal_Pos;
    return x;
}

--- trigger build, poll ---
poll 1: success
{"duration_ms": 1108, "exit_code": 0, "has_artifact": true, "status": "success", "id": 2, "workspace_id": 6}

--- marketplace listing ---
[{"id": 1, "build_id": 2, "filename": "workspace_6_build_2.bin", "workspace_name": "smoke-ws",
  "user_email": "tester1@example.com", "size_bytes": 192, "duration_ms": 1108, ...}]

--- artifact detail (includes full log) ---
{"id": 1, "log_text": "", ...}   # clean compile, no warnings -> empty log, as expected

--- download ---
$ curl -D headers.txt -o downloaded.bin .../api/artifacts/1/download
HTTP/1.1 200 OK
Content-Disposition: attachment; filename="workspace_6_build_2.bin"
Content-Type: application/octet-stream
Content-Length: 192

$ file downloaded.bin
downloaded.bin: ARM Cortex-M firmware, initial SP at 0x20020000, reset at 0x08000040, ...
```

This is the exact chain task 4 (DoD) asks for: log in -> create workspace
-> upload the sample .a2l -> see the 173 signals -> write C using a signal
-> compile -> watch the log -> find the resulting artifact in the
marketplace -> download it. **Confirmed working end-to-end via a real
server, no manual DB fiddling** — the only step not literally exercised in
a browser is the click path itself (see "Honesty note" below).

### Frontend build

```
$ npm run build
vite v5.4.21 building for production...
✓ 54 modules transformed.
dist/index.html                 0.46 kB │ gzip:  0.29 kB
dist/assets/index-t8_dMDh1.css  5.37 kB │ gzip:  1.72 kB
dist/assets/index-A4G2mG2S.js 191.83 kB │ gzip: 61.58 kB
✓ built in 621ms
```

## Honesty note on browser verification

Same caveat as every prior phase: no browser-automation tool is available
in this environment, so the Marketplace/ArtifactDetail pages were **not**
click-tested in an actual browser. What *was* verified for real: the
production build compiles cleanly (above), and the exact API responses
the new pages consume (`GET /marketplace`, `GET /artifacts/<id>`,
`GET /artifacts/<id>/download`) were exercised against a real running
Flask server with a real podman-compiled binary, producing the response
shapes `Marketplace.jsx`/`ArtifactDetail.jsx` expect. **Tanishq (or the
next agent, if a browser tool becomes available) should click through the
golden path** in `README.md`'s "End-to-end smoke test" section and record
the walkthrough deliverable (task 7) from that session, since this agent
cannot produce a screen recording.

## Notes for whoever deploys (06_devops)

- `docs/SECURITY.md` T3/T5 residual risk (rootless podman not
  code-enforced) still applies — flagged again here since it's directly
  relevant to the deploy-host checklist in `_plan/06_devops_instructions.txt`.
- Storage is still `LocalStorage` only; if deploying with R2 per the devops
  instructions, a new storage class implementing
  `write_bytes`/`read_text`/`read_bytes`/`delete` needs to be written and
  swapped in behind the same interface — `marketplace.py` and `builds.py`
  only ever call those four methods, never touch the filesystem directly.
- Remember to run `python seed.py` (or set `SEED_USER{1,2}_EMAIL/PASSWORD`
  before running it) against the deployed DB, and put the real credentials
  in the private submission note — not in the repo.
- The walkthrough recording (task 7) and the actual public-URL deployment
  (06_devops) are the two remaining items outside this agent's reach in
  this environment.
