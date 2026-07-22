# Cortex Studio

Browser-based C development environment for embedded (Cortex-M) targets.
Built in phases; see `plan/` for the phase-by-phase spec and
`docs/DECISIONS.md` for design decisions and scope cuts.

## Status

Phase 1 complete: project skeleton + session-cookie authentication.
Flask serves the built React SPA on a single origin. No workspaces, A2L
parsing, or compilation yet (later phases).

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
