# Phase 3 Hand-off — Editor + Signal Discovery + Header Generation

## What was built

- `backend/app/header_gen.py`: `generate_header(measurements)` — turns the
  parsed MEASUREMENT list into a deterministic `signals.h` string. Fixed
  `TYPE_MAP` (A2L datatype -> `<stdint.h>` type); unmapped datatypes are
  skipped with a `/* unsupported type X */` comment, never guessed.
  `sanitise_identifier(name)` maps illegal-for-C names (dots/brackets) to
  valid identifiers; collisions after sanitising get a numeric suffix
  (`_2`, `_3`, ...); every renamed signal keeps a
  `/* original A2L name: ... */` trailing comment. `MATRIX_DIM` signals
  become array declarations (`type name[n];`). Banner comment documents
  what the file is and the "compile-time contract, not real linkage"
  caveat.
- `backend/app/models.py`: `Workspace.source_code` (nullable `Text`).
  Migration `d1bbb003f98f_add_source_code_to_workspaces` applied.
- `backend/app/workspaces.py` new routes (all `login_required` +
  ownership-checked, 404 on someone else's workspace, consistent with
  phase 2):
  - `GET /api/workspaces/<id>/source` -> `{"code": <str-or-null>}`
  - `PUT /api/workspaces/<id>/source` `{code}` -> save; rejects non-string
    `code` (400) and payloads over 256 KB (measured on UTF-8 byte length,
    400)
  - `GET /api/workspaces/<id>/signals.h` -> `text/plain`, generated fresh
    from the workspace's cached parsed signals on every request (so
    re-uploading the A2L automatically changes what this endpoint
    returns next call — no separate cache to invalidate); 404 if no A2L
    uploaded yet
- `backend/tests/test_header_gen.py` (9 tests): datatype mapping for all
  10 documented A2L types, `current_gear` -> `uint8_t` spot check, unknown
  datatype skipped with comment (asserts the raw type name never appears
  as a bare identifier), dotted/bracketed name sanitised with
  original-name comment, the sanitisation helper directly, sanitisation
  collision resolved with a `_2` suffix, `MATRIX_DIM` -> array decl,
  include-guard/`#include <stdint.h>` present, empty signal list still
  produces a valid header.
- Frontend (`frontend/src/`):
  - `package.json`: added `@monaco-editor/react`.
  - `pages/WorkspaceList.jsx` (new): list/create workspaces — this page
    didn't exist before phase 3 (phase 2 was backend-only), added because
    there was otherwise no way to reach "an open workspace" from the UI.
  - `pages/Workspace.jsx` (new): the editor view — Monaco (`language="c"`)
    loads saved source on mount (falls back to a starter template that
    `#include`s `"signals.h"` and has a `main()` stub), explicit Save
    button (see `docs/DECISIONS.md` for why not autosave-on-debounce), an
    A2L upload control, a link to `GET /signals.h`, and a searchable
    signal panel (client-side substring filter over
    `GET /api/workspaces/<id>/signals`) where clicking a row inserts the
    signal's sanitised identifier at the Monaco cursor via
    `editor.executeEdits`.
  - `api.js`: added `listWorkspaces`, `createWorkspace`, `getWorkspace`,
    `deleteWorkspace`, `uploadA2L`, `getSignals`, `getSource`,
    `saveSource`, `signalsHeaderUrl`.
  - `App.jsx`: added `/workspaces` and `/workspaces/:id` routes (both
    behind the existing `RequireAuth`), landing page links to
    `/workspaces`.
  - `App.css`: styles for the new pages (plain, functional — per ground
    rules, polished visual design is out of scope).
- `docs/DECISIONS.md`: phase 3 section — header-vs-alternatives choice,
  datatype mapping table rationale, name-sanitisation + collision rules,
  "compile-time contract, not real linkage" caveat, why generate-on-demand
  instead of a cached header, Save-button-not-autosave choice, 256 KB
  cap, Monaco requirement, and a documented known cut (client-side insert
  preview doesn't replicate server-side collision suffixing — verified
  zero collisions in the real sample, so left unfixed).
- `README.md`: phase 3 status + architecture section, new endpoints listed.

## What was cut / deferred (per ground rules)

- **Autosave** — explicit Save button chosen instead (brief allowed
  either); see DECISIONS.md.
- **Client-side collision-safe identifier preview** — the signal panel
  shows/inserts the *unsuffixed* sanitised identifier; if two signal names
  collided after sanitisation, `signals.h` would give the second one a
  `_2` suffix that the click-to-insert wouldn't know about. Verified this
  never happens in `Reference_a2l.a2l` (0 collisions across 173 names), so
  not fixed — documented as a known gap in DECISIONS.md rather than
  silently working around it.
- **No compilation triggered anywhere in this phase** — confirmed no route
  or button shells out to a compiler; that's Phase 4.
- **CHARACTERISTIC signals are not included in `signals.h`** — the header
  generator is only ever called with `measurements` (the phase 2 parser
  already only extracts name/kind for CHARACTERISTIC blocks, no
  datatype/limits to map); consistent with the phase 2 cut, not a new one.

## Real command output

### Backend tests

```
$ python -m pytest tests/ -v
tests/test_auth.py::test_signup_success PASSED                           [  4%]
tests/test_auth.py::test_signup_duplicate_email_rejected PASSED          [  8%]
tests/test_auth.py::test_login_wrong_password_401 PASSED                 [ 13%]
tests/test_auth.py::test_me_requires_session PASSED                      [ 17%]
tests/test_header_gen.py::test_datatype_mapping PASSED                   [ 21%]
tests/test_header_gen.py::test_current_gear_maps_to_uint8_t PASSED       [ 26%]
tests/test_header_gen.py::test_unknown_datatype_is_skipped_with_comment_not_guessed PASSED [ 30%]
tests/test_header_gen.py::test_dotted_bracketed_name_is_sanitised_with_original_name_comment PASSED [ 34%]
tests/test_header_gen.py::test_name_sanitisation_helper PASSED           [ 39%]
tests/test_header_gen.py::test_uniqueness_after_sanitising_collision PASSED [ 43%]
tests/test_header_gen.py::test_matrix_dim_produces_array_declaration PASSED [ 47%]
tests/test_header_gen.py::test_header_has_include_guard_and_stdint_include PASSED [ 52%]
tests/test_header_gen.py::test_empty_measurement_list_still_produces_valid_header PASSED [ 56%]
tests/test_parser.py::test_simple_measurement_fields PASSED              [ 60%]
tests/test_parser.py::test_dotted_bracketed_name_and_matrix_dim PASSED   [ 65%]
tests/test_parser.py::test_missing_ecu_address_is_null_not_a_crash PASSED [ 69%]
tests/test_parser.py::test_truncated_block_raises_parse_error PASSED     [ 73%]
tests/test_parser.py::test_non_a2l_input_raises_parse_error PASSED       [ 78%]
tests/test_parser.py::test_real_sample_ground_truth PASSED               [ 82%]
tests/test_signals_api.py::test_create_and_list_workspace PASSED         [ 86%]
tests/test_signals_api.py::test_upload_sample_and_get_signals PASSED     [ 91%]
tests/test_signals_api.py::test_reject_non_a2l_extension PASSED          [ 95%]
tests/test_signals_api.py::test_cross_user_workspace_access_is_404 PASSED [100%]
============================== 23 passed in 1.37s ==============================
```

### Migration applied

```
$ flask db migrate -m "add source_code to workspaces"
INFO  [alembic.autogenerate.compare.tables] Detected added column 'workspaces.source_code'
Generating F:\Task\backend\migrations\versions\d1bbb003f98f_add_source_code_to_workspaces.py ...  done

$ flask db upgrade
INFO  [alembic.runtime.migration] Running upgrade 3fdd17621eb0 -> d1bbb003f98f, add source_code to workspaces
```

### Header generator against the real sample (spot checks from the DoD)

```
current_gear line: ['extern uint8_t current_gear;']
dotted example lines:
  ['extern uint8_t AppStatusListFrame620_app_uid[2];  /* original A2L name: AppStatusListFrame620.app_uid */',
   'extern uint8_t AppStatusListFrame620_seq_id;  /* original A2L name: AppStatusListFrame620.seq_id */']
total extern lines: 173
total unsupported-comment lines: 0   (all 8 datatypes in the sample are in TYPE_MAP)
collisions after sanitising (real sample, all 173 names): set()  -- none
```

### Full running-server flow via curl (real Flask process, real SQLite)

```
--- signup ---
{"email": "phase3_carl@example.com", "id": 7}          HTTP:201
--- create workspace ---
{"id": 2, "name": "Carl ws", "owner_id": 7, "has_a2l_file": false}
--- get source (expect null) ---
{"code": null}                                          HTTP:200
--- save source ---
{"ok": true}                                             HTTP:200
--- get source (expect saved code) ---
{"code": "#include \"signals.h\"\nint main(void){return 0;}"}   HTTP:200
--- oversized source (300000 bytes, expect 400) ---
{"error": "source exceeds the 256 KB size limit"}        HTTP:400
--- signals.h before upload (expect 404) ---
{"error": "no A2L file uploaded for this workspace yet"} HTTP:404
--- upload sample a2l ---
{"filename": "Reference_a2l.a2l", "summary": {"measurement_count": 173, "characteristic_count": 0, ...}}  HTTP:201
--- signals.h after upload ---
HTTP:200
extern-line count: 173
extern uint8_t current_gear;
extern uint8_t AppStatusListFrame620_app_uid[2];  /* original A2L name: AppStatusListFrame620.app_uid */
```

### Frontend build

```
$ npm run build
vite v5.4.21 building for production...
✓ 52 modules transformed.
dist/index.html                  0.46 kB │ gzip:  0.29 kB
dist/assets/index-BBY82WTs.css   3.72 kB │ gzip:  1.33 kB
dist/assets/index-Ba7n_l34.js  187.17 kB │ gzip: 60.53 kB
✓ built in 581ms
```

## Honesty note on browser verification

Per ground rules rule 5 ("don't claim something works unless you actually
ran it"): there is no browser-automation tool available in this
environment, so the editor/signal-panel/upload UI was **not** click-tested
in an actual browser by this agent. What *was* verified for real:
- the production build compiles cleanly (`npm run build`, above) — no
  JSX/import errors;
- every API call the UI makes (`/source` GET/PUT, `/a2l` upload,
  `/signals`, `/signals.h`) was exercised directly via curl against a real
  running Flask server with the exact payload shapes the frontend sends/
  expects (see above) and produced the expected responses;
- the sanitisation logic duplicated client-side for the insert-preview
  (`Workspace.jsx::sanitiseIdentifier`) was checked by hand against
  `header_gen.py::sanitise_identifier`'s test cases — same regex, same
  leading-digit rule.

If the next agent (or Tanishq) can run a browser, the golden path to
click-test is: log in -> Workspaces -> create one -> Upload A2L
(`_resources/Reference_a2l.a2l`) -> confirm the 173-row signal panel
appears and is searchable -> click a signal, confirm its identifier lands
in the editor at the cursor -> Save -> refresh the page -> confirm the
saved code and A2L-derived signal panel both reappear.

## Notes for the next agent (phase 4)

- `GET /api/workspaces/<id>/signals.h` is what Phase 4's build sandbox
  should drop into the compile directory as `signals.h` before invoking
  `arm-none-eabi-gcc` — it's already `text/plain` and workspace-scoped.
- The header only declares `extern`s; per DECISIONS.md, Phase 4 needs to
  give them *some* storage to link against (e.g. a generated
  zero-initialised `.c` definitions file) since there's no real ECU memory
  behind them. That generation was explicitly left for Phase 4.
- `GET /api/workspaces/<id>/source` is what Phase 4 should pull the user's
  C source from before compiling.
- `backend/app/header_gen.py::generate_header` and `sanitise_identifier`
  are already unit-tested in isolation — reuse them rather than
  re-deriving the mapping/sanitisation rules if Phase 4 needs to reason
  about identifiers (e.g. for the storage-stub generator above).
