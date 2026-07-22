========================================================================
PLAN INDEX - Browser-Based C Dev Environment (Bosch SDV assignment)
========================================================================
Due: 30 July 2026. Read files in this order.

  00_agent_ground_rules.txt   READ FIRST, EVERY TIME. Anti-hallucination
                              rules, locked tech decisions, scope, git &
                              "definition of done" discipline. Overrides
                              the phase files on conflict.

  phase1.txt                  Skeleton + auth (Flask+React one origin,
                              session cookie + werkzeug hashing).
  phase2.txt                  Workspaces + A2L upload + parser + /signals
                              API. (Sample = 173 MEASUREMENT, 0 CHAR.)
  phase3.txt                  Monaco C editor + signal discovery panel +
                              signals.h header generation.
  phase4.txt                  Compilation via arm-none-eabi-gcc inside a
                              rootless Podman sandbox + threat model.
                              THE most-graded phase.
  phase5.txt                  Artifact marketplace + README/walkthrough/
                              test-accounts finalisation.

  06_devops_instructions.txt  For Tanishq: AWS free-tier EC2 + rootless
                              Podman + Cloudflare (Tunnel for public URL,
                              R2 for storage; DB guidance). App stays
                              provider-agnostic via env vars.

HOW AGENTS SHOULD WORK
----------------------
- One phase at a time, in order. Meet the phase "Definition of Done"
  (verified by real command output) before moving on.
- Commit incrementally (evaluators grade project evolution).
- Log every scope cut + design decision in docs/DECISIONS.md; the
  evaluators will ask you to defend choices and cuts.
- When unsure, STOP and ask Tanishq. Never invent APIs, flags, or A2L facts.

SINGLE SOURCE OF TRUTH FOR THE A2L DOMAIN
-----------------------------------------
  resources/Reference_a2l.a2l  (the real sample; grep it, don't guess)
  Technical Assignment - Tanishq.pdf  (the brief)
========================================================================
