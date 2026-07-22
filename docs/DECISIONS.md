# Design Decisions

Append-only log of design decisions and scope cuts, with reasons. Evaluators
will ask us to defend these.

## Phase 1

- **Auth = session cookie + werkzeug hashing; React served by Flask (single
  origin).** Rejected JWT/OAuth as over-scoped for the brief. A session
  cookie (httpOnly, SameSite=Lax, Secure in prod) avoids token-storage/XSS
  pitfalls that come with JWT-in-localStorage, and serving the built React
  SPA from Flask means there is no cross-origin request in production, so
  no CORS configuration and no cross-site cookie edge cases to get wrong.

- **Frontend pinned to Vite 5 + React 18, not the Vite 8 default scaffold.**
  `npm create vite@latest` currently scaffolds Vite 8, which bundles a
  rolldown native binding that failed to load on this Windows/Node 22.11
  setup (`Cannot find module './rolldown-binding.win32-x64-msvc.node'`),
  breaking `npm run build`. Downgraded `frontend/package.json` to Vite 5 /
  `@vitejs/plugin-react` 4 / React 18, which builds cleanly and was
  verified with a real `npm run build` + browser smoke test. Revisit once
  the deployment toolchain (Node version in the Podman image, etc.) is
  finalized — see `plan/06_devops_instructions.txt`.

## Phase 2

- **MEASUREMENT = "input", CHARACTERISTIC = "output" direction convention.**
  A MEASUREMENT is a value the ECU/C code produces and the tool reads (a
  sensor/state value) — from the C program's perspective that's an input
  it reads. A CHARACTERISTIC is a writable calibration parameter — the tool
  writes/tunes it, so from the C program's perspective it's an output.
  `backend/app/a2l_parser.py::_direction_for` is the single place this
  mapping lives.

- **Line-scanner, not a grammar/parser, for A2L.** Per ground rules rule 6/7
  ("do not build full ASAM A2L spec coverage"), `a2l_parser.py` walks lines
  looking for `/begin MEASUREMENT` / `/begin CHARACTERISTIC` ... `/end ...`
  pairs and ignores every other block kind (COMPU_METHOD, COMPU_VTAB, etc).
  A real grammar would need to handle nested/other block kinds, escaping,
  multi-line strings — none of which the graded sample exercises, and the
  brief explicitly asks for the MEASUREMENT/CHARACTERISTIC subset only.

- **CHARACTERISTIC blocks: name/kind only, no field extraction.** The ASAM
  CHARACTERISTIC definition line has a different shape than MEASUREMENT's
  (`TYPE address record_layout max_diff conversion lower upper` vs.
  `DATATYPE conversion res res lower upper`), and `Reference_a2l.a2l` has
  **zero** CHARACTERISTIC blocks to verify field positions against. Rather
  than guess a mapping and risk silently wrong data (ground rule #3: fail
  loudly, don't fake it), the parser only captures `name` + `kind` for
  CHARACTERISTIC and reports every such block in the `skipped` list with an
  explicit reason. If/when a real sample with CHARACTERISTIC blocks shows
  up, this should be revisited and the same treatment MEASUREMENT gets can
  be extended once verified against ground truth.

- **Cross-user workspace access returns 404, not 403.** Returning 403 would
  confirm a workspace ID exists but belongs to someone else; 404 makes
  "doesn't exist" and "exists but isn't yours" indistinguishable from the
  outside. Enforced in one place: `workspaces.py::_get_owned_workspace`.

- **Storage behind a small interface (`storage.py: LocalStorage`), local
  disk only for now.** Per ground rules ("app code must never assume a
  specific cloud provider"), the upload route calls `write_bytes` /
  `read_text` / `delete` — swapping in an R2-backed implementation later
  (DevOps phase) means changing one class, not every call site.

- **One A2L file per workspace, re-upload replaces it.** The brief scopes
  this to "one .a2l file per workspace"; re-uploading overwrites the
  stored file and re-parses rather than versioning multiple files, since
  no phase asks for A2L file history.

- **5 MB upload cap.** The sample file is ~40 KB; 5 MB is a generous but
  finite ceiling to reject obviously-wrong uploads before they hit the
  parser, not a tuned production limit.

## Phase 3

- **Signals reach C code via a generated header (`signals.h`), not accessor
  `.c` stubs or compile-time `-D` injection.** A header is the most
  transparent, ordinary way for C code to see externally-defined symbols —
  it needs no runtime support and matches how embedded developers already
  work with memory-mapped signals (`extern` + a header, `#include` it,
  done). Rejected alternatives:
  - *Accessor stub `.c` files* (e.g. `get_current_gear()` functions) — adds
    a function-call layer and a second generated file to keep in sync with
    the header; more indirection for no benefit at this scope.
  - *Compile-time `-D` injection* (e.g. `-Dcurrent_gear=...`) — works for
    scalar constants but not arrays/structs, is invisible in the editor
    (the "magic" the ground rules warn against), and couples signal
    plumbing to the compiler invocation instead of to source the user can
    read. A header is inspectable, diffable, and `#include`-able like any
    other embedded project.

  `backend/app/header_gen.py::generate_header` implements this
  deterministically: signals are emitted in parser order, one `extern`
  line each (or a `/* unsupported type X */` comment — never a guess).

- **A2L datatype → C type mapping** (`header_gen.py::TYPE_MAP`), fixed and
  exhaustive for the ASAM types this project claims to support:
  `UBYTE/SBYTE/UWORD/SWORD/ULONG/SLONG/A_UINT64/A_INT64` → the matching
  `<stdint.h>` fixed-width type, `FLOAT32_IEEE`/`FLOAT64_IEEE` → `float`/
  `double`. Any datatype not in this table (including one the parser
  itself doesn't recognise) is **skipped** with a `/* unsupported type X
  */` comment rather than guessed — same "fail loudly" rule as the parser.
  All 8 datatypes seen in `Reference_a2l.a2l` are in the table, so nothing
  is skipped for the reference sample (verified: 173/173 signals emitted).

- **Name sanitisation for illegal C identifiers.** A2L signal names can
  contain `.` and `[]` (e.g. `ctx[0].state`, `AppStatusListFrame620.app_uid`)
  which are not legal in a C identifier. `sanitise_identifier()` replaces
  every character outside `[A-Za-z0-9_]` with `_`, and prefixes a leading
  digit with `_` (a name can't start with a digit in C either). Collisions
  after sanitising (e.g. `a.b` and `a_b` both becoming `a_b`) are resolved
  by appending `_2`, `_3`, ... in signal order — the first one keeps the
  clean name, later collisions get a numeric suffix, and every renamed
  signal keeps its original A2L name in a `/* original A2L name: ... */`
  trailing comment so nothing is silently lost.

- **`signals.h` is a compile-time contract only, not real linkage.** This
  webapp does not flash real ECU memory or run against real hardware (out
  of scope per ground rules), so the `extern` declarations have nothing
  real to link against yet. The header's banner comment says this
  explicitly. Phase 4 (compilation sandbox) is responsible for giving
  these externs *some* storage to satisfy the linker (e.g. a generated
  zero-initialised definitions file) — that is a Phase 4 concern, not
  addressed here.

- **`signals.h` is generated on-demand from the cached parsed signals**,
  not written to disk/DB and re-served. `GET /api/workspaces/<id>/signals.h`
  calls `generate_header()` against the same `signals_json` the `/signals`
  endpoint already reads. This trivially satisfies "regenerate on re-upload"
  (there is no stale copy to invalidate — every request reflects whatever
  A2L is currently on the workspace) at the cost of re-running the
  (cheap, deterministic) generator per request instead of caching it;
  acceptable at this scale (173 signals, sub-millisecond).

- **Source persistence: explicit Save button, not autosave-on-debounce.**
  The brief allowed either. A debounce adds a timer/race to reason about
  (save-in-flight vs. component unmount vs. rapid typing) for no real
  benefit in a single-user editor with no compile step yet; an explicit
  button is simpler to explain and test, and is what task 2 called "keep
  simple." Autosave can be revisited if user testing shows lost edits are
  a real problem.

- **256 KB max source size**, enforced server-side in
  `workspaces.py::save_source` on the UTF-8 byte length. A generous ceiling
  for what is still meant to be a small embedded `main.c`-style file, not a
  tuned production limit (same rationale as the 5 MB A2L cap).

- **Monaco via `@monaco-editor/react`, not hand-rolled.** Required by the
  ground rules for this phase ("do NOT build a custom editor... the point
  of the exercise is elsewhere"); `language="c"` gives C syntax
  highlighting out of the box with zero custom grammar work.

- **Clicking a signal inserts its sanitised identifier at the cursor** (not
  the raw A2L name) — that's the identifier that actually exists in
  `signals.h`, so inserting anything else would produce code that doesn't
  compile. The frontend keeps a small copy of the same sanitisation
  function (`Workspace.jsx::sanitiseIdentifier`) purely for *display* of
  what will be inserted; the header itself remains the single source of
  truth for what identifiers actually exist (uniqueness/collision handling
  only happens server-side, since it depends on the full signal list).
  **Known cut:** if two signal names collide after sanitisation, the click
  panel's suffix-free preview would not match the `_2`/`_3` suffix
  `signals.h` actually assigns to the second signal — verified this does
  not occur in `Reference_a2l.a2l` (0 collisions across all 173 names), so
  left unfixed rather than adding client-side collision tracking for a
  case the graded sample never hits.
