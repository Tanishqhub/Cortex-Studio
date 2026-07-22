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
