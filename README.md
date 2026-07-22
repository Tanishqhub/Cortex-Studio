# Cortex Studio

Browser-based C development environment for embedded (Cortex-M) targets.
Built in phases; see `plan/` for the phase-by-phase spec and
`docs/DECISIONS.md` for design decisions and scope cuts.

## Status

Phase 4 complete: workspace source compiles against a real `arm-none-eabi-gcc`
inside a locked-down Podman sandbox, with compiler output (warnings and
errors, not just pass/fail) shown in the browser. See `docs/SECURITY.md`
for the full threat model — read this before touching anything in
`backend/app/compiler.py` or `backend/sandbox/`. No marketplace yet (Phase 5).

## Architecture (phase 4 additions)

- **Compiler** (`backend/app/compiler.py`): given a workspace's saved
  source and parsed A2L signals, writes an isolated per-build temp dir
  (`user.c`, generated `signals.h`/`signals_def.c`, the fixed
  `build/startup.c`/`build/link.ld`) and runs a single, fully
  server-controlled `podman run` against it — `--network none`, memory/pids/
  cpu caps, `--read-only` rootfs, `--cap-drop=ALL`,
  `--security-opt no-new-privileges`, non-root `--user`, and a wall-clock
  timeout that force-kills the container. The user never supplies a
  compiler flag or path — only the contents of `user.c`. Full threat model,
  exact flags, and honest residual risks: **`docs/SECURITY.md`**.
- **Sandbox image** (`backend/sandbox/Containerfile`): Debian bookworm-slim
  + the `gcc-arm-none-eabi` package (GNU Arm Embedded Toolchain — upstream:
  https://developer.arm.com/downloads/-/arm-gnu-toolchain-downloads),
  non-root `builder` user, fixed `ENTRYPOINT` (`build.sh`) that always runs
  the same two commands (`arm-none-eabi-gcc ... -o out.elf` then
  `arm-none-eabi-objcopy -O binary`) regardless of any argv passed in.
  Build it once locally: `podman build -t c-sandbox:latest -f
  backend/sandbox/Containerfile backend/sandbox`.
- **Fixed build contract** (`build/startup.c`, `build/link.ld`): a minimal
  Cortex-M4 vector table + reset handler and a generic-but-fixed linker
  script, checked into the repo so builds are deterministic and never
  depend on user-supplied linker bits.
- **`signals_def.c`** (`header_gen.py::generate_definitions`): a companion
  to `signals.h` — one zero-initialised tentative definition per declared
  signal, so the `extern`s in `signals.h` have something to link against
  (compile-time contract only, see `signals.h`'s own banner comment).
- **Build model + API** (`backend/app/models.py::Build`,
  `backend/app/builds.py`):
  - `POST /api/workspaces/<id>/builds` → enqueue a build of the current
    saved source (owner only); rejects with 429 if the caller already has
    a build queued/running.
  - `GET /api/builds/<id>` → poll status + full log (owner only).
  - `GET /api/workspaces/<id>/builds` → recent builds for a workspace.
  - Runs on a bounded `ThreadPoolExecutor` (`BUILD_WORKER_COUNT`, default
    2) so a burst of requests queues instead of spawning unbounded
    containers.
- **Frontend**: a Compile button + log console panel in the workspace view
  (`frontend/src/pages/Workspace.jsx`) — polls `GET /api/builds/<id>` and
  shows the real compiler stdout/stderr (warnings and errors, not a
  pass/fail badge), plus final status and duration.

## Architecture (phase 3 additions)

- **Editor** (`frontend/src/pages/Workspace.jsx`): `@monaco-editor/react`
  (`language="c"`) loads the workspace's saved source on open (falling back
  to a starter template that `#include`s `"signals.h"`), edits locally,
  and saves via an explicit Save button (see `docs/DECISIONS.md` for why
  not autosave-on-debounce).
- **Source persistence**: `Workspace.source_code` (nullable `TEXT`) via
  `GET`/`PUT /api/workspaces/<id>/source`, owner-only, 256 KB cap enforced
  server-side on the UTF-8 byte length.
- **Signal discovery panel**: same page, calls the phase 2
  `GET /api/workspaces/<id>/signals` endpoint, is searchable (client-side
  filter over the 173-signal sample), and clicking a signal inserts its
  sanitised C identifier at the Monaco cursor.
- **Header generation** (`backend/app/header_gen.py`): `generate_header()`
  turns the parsed MEASUREMENT list into a deterministic `signals.h` —
  A2L datatype → `<stdint.h>` type via a fixed table (unknown datatypes are
  skipped with a comment, never guessed), illegal-for-C names (dots/
  brackets) sanitised into identifiers with the original name kept in a
  trailing comment, `MATRIX_DIM` signals become array declarations. Served
  at `GET /api/workspaces/<id>/signals.h` (`text/plain`, owner-only,
  regenerated fresh from the workspace's current parsed signals on every
  request — no stale-cache problem on re-upload). See `docs/DECISIONS.md`
  for why a header (not accessor stubs or `-D` injection) and the "not
  real linkage" caveat.

## Architecture (phase 2 additions)

- **Workspaces** (`backend/app/models.py`): a `Workspace` belongs to one
  `User` (`owner_id`) and has at most one `A2LFile`. Every workspace route
  (`backend/app/workspaces.py`) looks the workspace up scoped to
  `owner_id == session["user_id"]` and returns 404 (not 403) if it doesn't
  belong to the caller — see `docs/DECISIONS.md`.
- **Storage** (`backend/app/storage.py`): uploaded `.a2l` files are written
  through a small `LocalStorage` interface (`write_bytes`/`read_text`/
  `delete`) rather than direct filesystem calls, so a Cloudflare R2-backed
  implementation can be dropped in later without touching the routes.
- **A2L parser** (`backend/app/a2l_parser.py`): a line-scanner (not a full
  ASAM grammar) that extracts MEASUREMENT and CHARACTERISTIC blocks —
  name, datatype, ECU address, limits, compu_method, matrix_dim — and
  normalises them into the signal shape the API returns. Verified against
  `_resources/Reference_a2l.a2l`: 173 measurements, 0 characteristics.
  CHARACTERISTIC field extraction is intentionally not implemented (see
  `docs/DECISIONS.md`) since the sample has none to verify against.
- **API**:
  - `POST /api/workspaces` `{name}` → create
  - `GET /api/workspaces` → list caller's workspaces
  - `GET /api/workspaces/<id>` → details (owner only)
  - `DELETE /api/workspaces/<id>` → delete (owner only)
  - `POST /api/workspaces/<id>/a2l` → multipart upload, field name `file`,
    `.a2l` extension only, 5 MB cap; stores the raw file and the parsed
    signals/summary
  - `GET /api/workspaces/<id>/signals` → parsed signals + summary
    (measurement/characteristic counts, datatypes seen, skipped blocks)
  - `GET /api/workspaces/<id>/source` → `{code}` saved C source (or `null`)
  - `PUT /api/workspaces/<id>/source` `{code}` → save C source, 256 KB cap
  - `GET /api/workspaces/<id>/signals.h` → generated header (`text/plain`)

## Run locally

### Sandbox image (required for compilation, Phase 4)

Needs [Podman](https://podman.io/) installed (on Windows: `podman machine
init` + `podman machine start` first). Build the sandbox image once:

```bash
podman build -t c-sandbox:latest -f backend/sandbox/Containerfile backend/sandbox
```

Verify the toolchain (matches what `docs/SECURITY.md` documents as tested):

```bash
podman run --rm --entrypoint arm-none-eabi-gcc c-sandbox:latest --version
```

Without this image, workspace source can still be saved/edited, but
`POST /api/workspaces/<id>/builds` will fail (podman/image not found) — the
error shows up in the build's log, not a silent failure.

### Backend (Flask)

```bash
cd backend
python -m venv venv
source venv/Scripts/activate   # Windows Git Bash; use `venv\Scripts\activate` in cmd, or `source venv/bin/activate` on Linux/Mac
pip install -r requirements.txt

cp .env.example .env
# edit .env and set a real SECRET_KEY, e.g.:
#   python -c "import secrets; print(secrets.token_hex(32))"

export FLASK_APP=app.py
flask db upgrade   # applies migrations, creates the sqlite DB

python app.py       # runs on http://127.0.0.1:5000
```

Required env vars (see `backend/.env.example`):
- `SECRET_KEY` — required, no default. Used to sign the Flask session cookie.
- `DATABASE_URL` — defaults to `sqlite:///app.db`.
- `ENV` — `development` (default) or `production`. Controls the
  `Secure` flag on the session cookie.

### Frontend (Vite React)

Two workflows:

**Dev mode** (hot reload, Vite dev server proxies `/api/*` to Flask on
`127.0.0.1:5000`):

```bash
cd frontend
npm install
npm run dev   # http://localhost:5173, proxies /api to Flask
```

Run the Flask backend at the same time (see above) — the Vite dev
server does not serve the API itself.

**Production build** (single origin — Flask serves the built SPA):

```bash
cd frontend
npm install
npm run build   # outputs frontend/dist
```

Then just run the Flask backend (`python app.py` from `backend/`) and
visit `http://127.0.0.1:5000/` — Flask serves `frontend/dist/index.html`
and its assets, and the whole auth flow (signup/login/logout) works on
that single port with no CORS configuration.

### Tests

```bash
cd backend
source venv/Scripts/activate
python -m pytest tests/ -v
```

## Repo layout

```
/backend           Flask app (app factory, models, auth blueprint, migrations)
/backend/sandbox    Containerfile + fixed entrypoint script for the compile sandbox
/build              Fixed startup.c + link.ld shared by every sandboxed build
/frontend          Vite + React SPA
/docs              DECISIONS.md, SECURITY.md — decisions/cuts and the compile threat model
/plan              Phase specs for AI-agent-driven development
```
