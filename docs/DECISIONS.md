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
