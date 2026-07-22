# Phase 1 Hand-off — Project Skeleton + Authentication

## What was built

- `/backend`: Flask app factory (`app/__init__.py`), config read from env
  (`app/config.py`, `SECRET_KEY` required, no default, no hardcoded
  secrets), `User` model with werkzeug password hashing (`app/models.py`),
  auth blueprint at `/api/auth/*` (`app/auth.py`) with signup/login/logout/me,
  a reusable `login_required` decorator (used by `/api/protected-example`
  as the example route required by task 5), Flask-Migrate migration
  creating the `users` table, and a catch-all route serving the built
  React SPA (`frontend/dist`) for everything except `/api/*`.
- `/frontend`: Vite + React (JS, not TS) app with `src/api.js` (fetch
  wrapper, `credentials: 'include'`), `pages/Login.jsx`, `pages/Signup.jsx`,
  and `App.jsx` (landing page "Logged in as <email>" + Logout, client-side
  route guard that redirects to `/login` when `/api/auth/me` is 401).
  react-router-dom for routing. Vite dev server proxies `/api` to Flask
  (`vite.config.js`) for the dev workflow; `npm run build` produces
  `frontend/dist` for the single-origin production workflow.
- `/backend/tests/test_auth.py`: 4 tests (signup success, duplicate email
  rejected, wrong password 401, `/api/auth/me` requires session).
- `docs/DECISIONS.md`: phase 1 entry documenting the session-cookie +
  werkzeug / single-origin decision and why JWT/OAuth were rejected.
- `README.md`: "Run locally" section for both backend and frontend,
  dev and prod (single-origin) workflows, required env vars.

## What was cut / deferred (per ground rules — later phases)

- No workspaces, A2L parsing, compilation, or marketplace code — all
  out of scope for phase 1, per `00_agent_ground_rules.txt`.
- No password-reset / email-verification flow — not asked for by the
  phase spec; signup immediately logs the user in.
- No rate limiting on login/signup — not mentioned in phase 1 scope;
  worth revisiting before the app is public (flag for a later phase or
  for Tanishq's DevOps pass).

## Real command output

### Backend starts, health check

```
$ python app.py
 * Serving Flask app 'app'
 * Debug mode: on
 * Running on http://127.0.0.1:5000

$ curl -s -w "\nHTTP:%{http_code}\n" http://127.0.0.1:5000/api/health
{
  "status": "ok"
}
HTTP:200
```

### Migration applied

```
$ flask db migrate -m "create users table"
INFO  [alembic.autogenerate.compare.tables] Detected added table 'users'
INFO  [alembic.autogenerate.compare.constraints] Detected added index 'ix_users_email' on '('email',)'
Generating F:\Task\backend\migrations\versions\234b5b908c95_create_users_table.py ...  done

$ flask db upgrade
INFO  [alembic.runtime.migration] Running upgrade  -> 234b5b908c95, create users table

$ python -c "import sqlite3; print(sqlite3.connect('instance/app.db').execute(\"select name from sqlite_master where type='table'\").fetchall())"
[('alembic_version',), ('users',)]
```

### Full signup -> me -> logout -> me(401) cycle via curl

```
--- signup ---
{"email": "alice@example.com", "id": 1}
HTTP:201
--- signup duplicate ---
{"error": "an account with this email already exists"}
HTTP:409
--- me (should be alice) ---
{"email": "alice@example.com", "id": 1}
HTTP:200
--- protected-example (should be ok) ---
{"ok": true}
HTTP:200
--- logout ---
{"ok": true}
HTTP:200
--- me after logout (should be 401) ---
{"error": "authentication required"}
HTTP:401
--- protected-example after logout (should be 401) ---
{"error": "authentication required"}
HTTP:401
--- login wrong password ---
{"error": "invalid email or password"}
HTTP:401
--- login correct ---
{"email": "alice@example.com", "id": 1}
HTTP:200
```

### pytest

```
$ python -m pytest tests/ -v
tests/test_auth.py::test_signup_success PASSED                     [ 25%]
tests/test_auth.py::test_signup_duplicate_email_rejected PASSED    [ 50%]
tests/test_auth.py::test_login_wrong_password_401 PASSED           [ 75%]
tests/test_auth.py::test_me_requires_session PASSED                [100%]
============================== 4 passed in 0.92s ==============================
```

### Real browser verification (Playwright against the Flask-served build)

Drove a headless Chromium session against `http://127.0.0.1:5000/`
(the built SPA served by Flask, single origin, no dev server involved):
visited `/` while logged out -> redirected to `/login`; navigated to
`/signup`, filled in a new email/password, submitted -> redirected to `/`
and saw "Logged in as `<email>`"; reloaded the page -> still logged in
(session cookie persisted); clicked Logout -> redirected to `/login`.
Screenshots taken at each step confirmed the UI rendered correctly.
No unexpected console errors (the one console entry logged is the
expected 401 from the initial unauthenticated `/api/auth/me` check).

## Notes for the next agent (phase 2)

- Entrypoint is `backend/app.py`; app factory is `create_app()` in
  `backend/app/__init__.py`. Extend it with new blueprints the same way
  `auth_bp` is registered.
- `login_required` lives in `backend/app/auth.py` — reuse it directly for
  any new protected routes (e.g. workspace / A2L endpoints).
- The frontend build must exist at `frontend/dist` for Flask's catch-all
  route to serve anything at `/`; if you see a 404 with a
  "frontend build not found" message, run `npm run build` in `frontend/`.
- `backend/.env` is gitignored; only `.env.example` is committed. Anyone
  running this fresh must copy it and generate their own `SECRET_KEY`.
- Frontend was scaffolded with Vite's default template, which currently
  ships Vite 8 (rolldown-based) — that build was broken on this Windows/
  Node 22.11 combination (`Cannot find module
  './rolldown-binding.win32-x64-msvc.node'`). Pinned `frontend/package.json`
  to Vite 5 / React 18 / `@vitejs/plugin-react` 4 instead, which builds
  cleanly. Worth revisiting the Vite version once the platform/toolchain
  is finalized for deployment.
