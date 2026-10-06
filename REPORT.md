# REPORT — ADR-036 energy policy

## Outcome

Wrote ADR-036 recording the operator's 2026-10-07 energy-policy decision, and amended
ADR-006 in part with a one-line pointer.

- **ADR number:** 036 (checked 002, 017, 018, 019, 020, 025, 028, 029 — all collide;
  031, 032, 034, 035 taken; 033 claimed elsewhere; 036/037/038 free).
- **New file:** `docs/adr/036-energy-policy-burst-storage-daylight-only-tx.md`.
- **Amended:** `docs/adr/006-supercapacitor-power.md` — one-line pointer added after
  `Status: Akzeptiert` ("Superseded in part by ADR-036 ..."). Solar architecture left
  untouched.
- **Cross-references:** ADR-035 D7 (hook → policy), ADR-029 O5 (5 V rail, still open).
- **Consequences stated:** overnight/shadow telemetry gaps, flight recorder as primary
  evidence, night LOG gap as the real risk (with µA sleep-current arithmetic, left
  open), mandatory night deep sleep, dawn cold start + GNSS cost.
- **Open items recorded (not decided):** burst energy vs modulation mode (FLRC ~2 mJ vs
  LoRa SF12 ~4 J), FLRC availability on the F33 sub-GHz port (unverified), cold
  characterisation at -60 C, night sleep current.

## Working notes

- Worktree `/home/c03rad0r/worktrees/bf-adr-energy`, branch `adr/energy-policy`, base
  `697fb73`.
- Documentation only; no schematic/placement/routing work.
- No supersede line existed in ADR-006 before my edit; none duplicated.
- No absolute `/home/` paths in committed files (Gate 5 aware).
