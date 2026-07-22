# Cortex Studio

Browser-based C development environment for embedded (Cortex-M) targets.
Built in phases; see `plan/` for the phase-by-phase spec and
`docs/DECISIONS.md` for design decisions and scope cuts.

## Status

Phase 3 complete: an in-browser Monaco C editor with source persistence, a
searchable signal-discovery panel, and generated `signals.h` headers so C
code in the editor can reference A2L signals by name. No compilation yet
(Phase 4) or marketplace (Phase 5).

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
/backend        Flask app (app factory, models, auth blueprint, migrations)
/frontend       Vite + React SPA
/docs           DECISIONS.md — design decisions & scope cuts, append-only
/plan           Phase specs for AI-agent-driven development
```
