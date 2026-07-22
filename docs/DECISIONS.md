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
