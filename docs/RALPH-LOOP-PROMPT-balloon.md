# RALPH LOOP PROMPT — balloon programme completion

Paste the block below to start the loop.

---

## PROMPT

```
RALPH LOOP: balloon-programme-completion

GOAL
Drive the pico-balloon programme to "ready for first flight" — boards ordered,
experiments designed and coded, flight software complete and tested, and every
gap-analysis finding either closed or explicitly accepted with a decision.
Work autonomously, one task per iteration, until the exit condition is met.

QUOTA GATE FIRST — EVERY ITERATION, NO EXCEPTIONS
Run: bash ~/.hermes/profiles/manager/scripts/dispatch-gate.sh
If exit 1, judge the reason from http://localhost:9099/v1/dispatch_gate:
  - deliverable=false        -> REAL STOP. Emit a one-line alert and end.
  - price-ceiling only       -> DEFERRAL, not a stop (dispatch_budget.yaml:
                                "bounds SPEND, not availability"). Prefer
                                deterministic work; if dispatch is needed, note
                                the cost and ask the operator to pick
                                DEFER / NOW / BATCH. NEVER raise urgency
                                unilaterally — that is an operator decision.
Also respect the freeze marker: test -f ~/.hermes/bot/.dispatch_frozen (use
test, NEVER touch — touch would CREATE it and stop the fleet).

REPO / ENVIRONMENT
  repo:     balloon-fresh — default branch master, remotes github + ngit
  worktree: ~/worktrees/e80-lr2021-audit  (master is checked out in
            ~/worktrees/adr-batch — do NOT try to switch to master elsewhere;
            push with `git push github HEAD:master` after verifying it is a
            fast-forward)
  firmware libs live in firmware/lib/ — host tests via `make -C firmware/lib test`
  python for pytest: ~/venvs/ho-test/bin/python (system python3 has NO pytest)
  measured facts: docs/analysis/ and docs/fab/hub-v9/
Never force-push. Never push to a branch other than the worktree's own.

PER-ITERATION PROTOCOL (death-proof)
1. Read PROGRESS.md + REPORT.md at the worktree root to resume.
2. Pick the SINGLE highest-value unblocked task from the scope below.
3. Do it. Commit atomically (conventional message), PUSH, and verify the push
   in tool output (`git ls-remote`) — an unobserved push is not a push.
4. Append one PROGRESS.md line: finding -> status -> files touched.
5. If blocked, write the blocker to REPORT.md with the exact command needed
   from the operator, mark it HANDOFF, and move to the next task.
6. Do not stop between tasks; "task N done" is a progress marker, not a pause.

SCOPE — in priority order

P0 · unblocked, highest value
  1. Create the missing `hub_v9` PlatformIO env (ESP32-S3-WROOM-1U). NO S3 env
     exists anywhere in the repo (only per-directory envs: esp32-uart-bridge,
     esp32-c3-bootsel-controller). This blocks ALL firmware build work.
     Match existing per-directory conventions; do not introduce a new framework.
  2. Land the 4 radio libraries (L0 radio_core + HAL, L2 LoRaWAN, L3 MeshCore,
     L4 Meshtastic) from their worktrees/branches — verify each branch against
     git (not the worker's self-report), run its host tests, then merge/sequence.
     FOLLOW-ON GATE pio now, because PIO was not installed during that dispatch.
  3. Consolidate the software-prepare items still unimplemented: telemetry
     schema versioning + ground-side decode, OTA-with-ringstore interaction.

P1 · experiments (design + code now, fly later)
  4. E-00 range & speed with LoRaWAN fallback — the first flight experiment.
     Implement the fallback switching logic as a tested library.
  5. E-CS1..6 cold-start rigs/protocols -> executable bench procedures.
  6. RFA-1c (LR2021 re-calibration after every bitrate change — 260->650
     deafness). Real silicon is on THIS host: /dev/ttyUSB0, E80BENCH v1.2
     fw=5fa7912. RECEIVE-ONLY discipline: never ARM TX / ROLE TX / START /
     PRBS9 (PRBS9 is a chip-level TX mode), because ARM TX starts the IWDG and
     needs a physical power-cycle to clear.

P2 · boards to order (operator-gated — prepare, do not place)
  7. Hub v9 x10 @ 0.8 mm, wing boards (0.6 mm 2-LAYER — legal), base station.
     Agent verifies packet + re-checks price; the OPERATOR places the order.
     Close the 6 blockers in docs/fab/hub-v9/PRE-ORDER-CHECKLIST.md
     (0.8 mm form selection, re-price, mass reconciliation, per-placement fee,
     envelope lock, EN pull-up).
  8. V9-D8 nested dual footprint (F33 or bare LoRa2021, selectable rail + DNP RF).

P3 · physics / envelope (needs operator measurements)
  9. Reconcile the ~57 g payload against the community's PROVEN
     9-22 g long-duration band (docs/analysis/pico-balloon-envelope-mass.md).
     Do NOT re-assert the superseded 6.4-9.5 km figure.
 10. Chase M1/M2/M3 (balloon mass, cell mass, latex mass) via the existing
     `balloon-human-measurements-nudge` job; do not block on them.

HANDOFF-ONLY — do NOT ralph on these (they need physical access; retrying wastes
turns): pio toolchain fix on the bench host, SPI clock 40->16 MHz change, board
flash + serial smoke, PCB-V2 DRC/SPI characterisation, RFA-1b PRAM reflash.
Detect each, write it to REPORT.md as HANDOFF with the exact operator action,
and continue.

HONESTY CONTRACT (non-negotiable)
  - Never claim a test, build, flash, push or measurement you did not observe in
    tool output. Quote the decisive line.
  - Distinguish MEASURED (from the board/datasheet/tool) from MODELLED.
  - Every library needs a counter-test proven to fail by deliberate sabotage —
    a green suite alone is not evidence.
  - No hardware behaviour may be claimed that was not exercised on real silicon.

EXIT CONDITION
Stop and report when ALL of:
  (a) `hub_v9` env builds green, host tests pass, and the S1-S6 + L0-L4 libraries
      are merged to master with tests passing;
  (b) every pre-order blocker is closed or explicitly accepted by the operator,
      and the order packets are verified and waiting;
  (c) every gap-analysis finding is closed, or recorded as an accepted risk with
      a cited decision;
  (d) remaining items are ONLY HANDOFF (physical access) or operator decisions.
```

---

## Why the loop is shaped this way

- **The backlog is not what it looks like.** 84 `blocked` on the balloon board,
  but most are *bench* items needing physical access (D1–D7). A naive loop would
  burn every iteration retrying them. The HANDOFF-ONLY section is the fix.
- **C4 (`hub_v9` env) is the top task** — genuinely unblocked, and it gates all
  firmware build work.
- **P2 is prepare-only.** The operator places orders (standing rule); the loop
  verifies and re-prices.
- **The quota gate is a deferral, not a veto** unless `deliverable=false`. The
  loop must not raise urgency on its own — that is the operator's spend call.
