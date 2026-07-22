# Phase 2 Hand-off — Workspaces + A2L Upload + Parser + Signals API

## What was built

- `backend/app/models.py`: `Workspace` (id, name, owner_id -> User,
  created_at) and `A2LFile` (one per workspace, unique `workspace_id` FK;
  stores `filename`, `stored_path`, `uploaded_at`, and cached
  `signals_json`/`summary_json` so `/signals` doesn't re-parse per
  request). Migration `3fdd17621eb0_create_workspaces_and_a2l_files_tables`
  applied.
- `backend/app/storage.py`: `LocalStorage` — a small interface
  (`write_bytes`/`read_text`/`delete`) so the upload route never touches
  the filesystem directly; swappable for R2 later per ground rules.
- `backend/app/a2l_parser.py`: line-scanner for `/begin MEASUREMENT ...
  /end MEASUREMENT` and `/begin CHARACTERISTIC ... /end CHARACTERISTIC`
  blocks. Extracts name, datatype, compu_method (null if
  `NO_COMPU_METHOD`), ECU_ADDRESS, limits (lower/upper), MATRIX_DIM.
  Handles dotted/bracketed names (`ctx[0].state`), missing ECU_ADDRESS
  (-> null, no crash), and raises `ParseError` on an unterminated block or
  input with no `/begin` blocks at all (route turns this into 422).
  CHARACTERISTIC blocks are captured by name/kind only (see
  `docs/DECISIONS.md` for why — zero in the sample to validate field
  layout against) and reported in the `skipped` list.
- `backend/app/workspaces.py`: blueprint at `/api/workspaces`, all routes
  `login_required` + ownership-checked (404, not 403, on someone else's
  workspace):
  - `POST /api/workspaces` `{name}` -> create
  - `GET /api/workspaces` -> list caller's workspaces
  - `GET /api/workspaces/<id>` -> details (owner only)
  - `DELETE /api/workspaces/<id>` -> delete (owner only)
  - `POST /api/workspaces/<id>/a2l` -> multipart upload (`file` field),
    `.a2l` extension enforced, 5 MB cap, stores raw file + parses +
    persists signals/summary
  - `GET /api/workspaces/<id>/signals` -> parsed measurements +
    characteristics + summary
- `backend/tests/test_parser.py` (6 tests): simple MEASUREMENT field
  extraction, dotted/bracketed name + MATRIX_DIM, missing ECU_ADDRESS,
  truncated block -> ParseError, non-A2L input -> ParseError, real sample
  ground truth (173/0 + current_gear fields).
- `backend/tests/test_signals_api.py` (4 tests): create/list workspace,
  upload sample + GET signals (173 measurements, current_gear fields),
  reject non-`.a2l` upload, cross-user access on GET/POST/DELETE all 404.
- `docs/DECISIONS.md`: phase 2 entries — direction convention, why a
  line-scanner not a grammar, why CHARACTERISTIC fields aren't extracted,
  why 404 not 403, storage interface, one-file-per-workspace, 5 MB cap.
- `README.md`: phase 2 status + architecture section describing the
  models, storage interface, parser scope, and API surface.

## What was cut / deferred (per ground rules)

- CHARACTERISTIC field extraction (datatype/address/limits) — not
  implemented, documented above and in DECISIONS.md. Only name/kind
  captured; every CHARACTERISTIC block is reported in `skipped`.
- Optional COMPU_VTAB enum lookup (task 4 called this out as optional) —
  skipped for time; `compu_method` is returned as the raw conversion-table
  name (e.g. `gear_state_t`) rather than resolved to its enum values.
- Workspace `DELETE` was marked optional in the brief — implemented
  anyway since it was trivial given the ownership-check helper already
  existed, and it's needed to clean up storage in tests/dev.
- No pagination on `GET /api/workspaces` — out of scope at this size.

## Real command output

### Migration applied

```
$ flask db migrate -m "create workspaces and a2l_files tables"
INFO  [alembic.autogenerate.compare.tables] Detected added table 'workspaces'
INFO  [alembic.autogenerate.compare.constraints] Detected added index 'ix_workspaces_owner_id' on '('owner_id',)'
INFO  [alembic.autogenerate.compare.tables] Detected added table 'a2l_files'
INFO  [alembic.autogenerate.compare.constraints] Detected added index 'ix_a2l_files_workspace_id' on '('workspace_id',)'
Generating F:\Task\backend\migrations\versions\3fdd17621eb0_create_workspaces_and_a2l_files_tables.py ...  done

$ flask db upgrade
INFO  [alembic.runtime.migration] Running upgrade 234b5b908c95 -> 3fdd17621eb0, create workspaces and a2l_files tables

$ python -c "import sqlite3; print(sqlite3.connect('instance/app.db').execute(\"select name from sqlite_master where type='table'\").fetchall())"
[('alembic_version',), ('users',), ('workspaces',), ('a2l_files',)]
```

### Parser against the real sample (ground truth check)

```
measurements: 173
characteristics: 0
summary: {'measurement_count': 173, 'characteristic_count': 0,
  'datatypes_seen': ['A_UINT64', 'FLOAT32_IEEE', 'SBYTE', 'SLONG', 'SWORD', 'UBYTE', 'ULONG', 'UWORD']}
skipped count: 0
current_gear: {'name': 'current_gear', 'kind': 'MEASUREMENT', 'direction': 'input',
  'datatype': 'UBYTE', 'address': '0x280058C0', 'limits': {'lower': 0, 'upper': 2},
  'compu_method': 'gear_state_t', 'matrix_dim': None}
dotted examples: [{'name': 'AppStatusListFrame620.app_uid', ..., 'matrix_dim': 2}, ...]
```

### pytest

```
$ python -m pytest tests/ -v
tests/test_auth.py::test_signup_success PASSED                           [  7%]
tests/test_auth.py::test_signup_duplicate_email_rejected PASSED          [ 14%]
tests/test_auth.py::test_login_wrong_password_401 PASSED                 [ 21%]
tests/test_auth.py::test_me_requires_session PASSED                      [ 28%]
tests/test_parser.py::test_simple_measurement_fields PASSED              [ 35%]
tests/test_parser.py::test_dotted_bracketed_name_and_matrix_dim PASSED   [ 42%]
tests/test_parser.py::test_missing_ecu_address_is_null_not_a_crash PASSED [ 50%]
tests/test_parser.py::test_truncated_block_raises_parse_error PASSED     [ 57%]
tests/test_parser.py::test_non_a2l_input_raises_parse_error PASSED       [ 64%]
tests/test_parser.py::test_real_sample_ground_truth PASSED               [ 71%]
tests/test_signals_api.py::test_create_and_list_workspace PASSED         [ 78%]
tests/test_signals_api.py::test_upload_sample_and_get_signals PASSED     [ 85%]
tests/test_signals_api.py::test_reject_non_a2l_extension PASSED          [ 92%]
tests/test_signals_api.py::test_cross_user_workspace_access_is_404 PASSED [100%]
============================== 14 passed in 1.28s ==============================
```

### Two-user isolation cycle via curl (real running server)

```
--- signup userA ---
{"email": "phase2_alice@example.com", "id": 5}
HTTP:201
--- signup userB ---
{"email": "phase2_bob@example.com", "id": 6}
HTTP:201
--- userA creates workspace ---
{"created_at": "2026-07-22T17:07:33.759129", "has_a2l_file": false, "id": 1, "name": "Alice ECU project", "owner_id": 5}
workspace id: 1
--- userA uploads sample a2l ---
{"filename": "Reference_a2l.a2l", "summary": {"characteristic_count": 0,
  "datatypes_seen": ["A_UINT64","FLOAT32_IEEE","SBYTE","SLONG","SWORD","UBYTE","ULONG","UWORD"],
  "measurement_count": 173, "skipped": []}}
HTTP:201
--- userA gets signals (expect 173 measurements) ---
measurements: 173
characteristics: 0
[current_gear: address 0x280058C0, datatype UBYTE, limits 0..2, compu_method gear_state_t]
--- userA uploads a .txt (expect 400) ---
{"error": "only .a2l files are accepted"}
HTTP:400
--- userB tries to view userA workspace (expect 404) ---
{"error": "workspace not found"}
HTTP:404
--- userB tries to get userA signals (expect 404) ---
{"error": "workspace not found"}
HTTP:404
--- userB tries to upload to userA workspace (expect 404) ---
{"error": "workspace not found"}
HTTP:404
--- userB tries to delete userA workspace (expect 404) ---
{"error": "workspace not found"}
HTTP:404
```

## Notes for the next agent (phase 3)

- `GET /api/workspaces/<id>/signals` is the endpoint the editor will
  consume for signal discovery/autocomplete/header generation. Shape:
  `{"measurements": [...], "characteristics": [...], "summary": {...}}`,
  each signal matching the schema in `_plan/phase2.txt`.
- The parser module (`app/a2l_parser.py`) exposes `parse_a2l(text) ->
  {"measurements", "characteristics", "summary"}` and raises `ParseError`
  — reuse it directly if phase 3 needs to re-parse or validate.
  `ParseError` messages are user-facing (returned as the 422 body), so
  keep them clear if you touch them.
- Storage paths are `workspace_<id>/source.a2l` under
  `Config.UPLOAD_FOLDER` (default `backend/instance/uploads`); use
  `LocalStorage` rather than raw `open()` calls for consistency with the
  "storage behind an interface" rule.
- `backend/instance/app.db` and `backend/instance/uploads/` now contain
  test data from the curl verification above (users `phase2_alice`/
  `phase2_bob`, one workspace with the sample uploaded) — this is a local
  dev DB, already gitignored, harmless to reset with `flask db upgrade`
  against a fresh `instance/` if a clean slate is wanted.
