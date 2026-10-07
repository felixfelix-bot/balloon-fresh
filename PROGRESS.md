# PROGRESS — fix/record-contradictions (worktree /home/c03rad0r/worktrees/bf-ssot)

Base: `github/main` tip `e03696a`. Branch: `fix/record-contradictions`.
NOTE: this file is gitignored (.gitignore:67); committed with `git add -f` on THIS branch only.

## Cluster 1 — precedence established (Part A)

Read in full: ADR-049 §5 item 6; ADR-048 §5 item 6 (+ sheet OPEN-23 +
`build_flight_sch.py:1906`); `docs/WING-TO-HUB-SOCKET-SPEC.md` §1; ADR-046 §4.1;
ADR-051 §1.4; ADR-055 §1/§3; `docs/hardware-design.md` §3D-Assembly;
`docs/analysis/wing-insolation-geometry.md` §0; `docs/analysis/hub-thickness-deflection.md`
(on branch `analysis/hub-thickness-deflection`, NOT on main) §0/§5/§6.

VERDICT — **governing: `docs/adr/049-wing-architecture.md` §5 item 6 (VERTICAL blade)**.
**Stale: `docs/WING-TO-HUB-SOCKET-SPEC.md` §1 prose** ("Wings 1–2 horizontal…" and its
self-contradicting "long axis perpendicular to the hub plane"); its derivative carry in
ADR-048 §5 item 6 / sheet OPEN-23 is resolved by citation (ADR-048 itself deliberately
asserts no rotation and that stands).

Evidence (record-only, no re-decision):
- the socket spec §1 DECLARES its authority is ADR-046; ADR-046 §4.1 itself says "90° to the
  hub plane, wing plane normal to the hub plane" = vertical. A derivative cannot override its
  source → §1's prose is stale.
- ADR-051 §1.4 and ADR-055 §1 independently derive four VERTICAL blades.
- `wing-insolation-geometry.md` §0 derives VERTICAL mechanically (0.9 mm slot / 0.6 mm tab /
  0.30 mm gap; 9.0 mm tab cannot fit a 6.0 mm in-plane slot) and names the spec's "long axis
  perpendicular" phrase the wrong one.
- origin of "horizontal": `hardware-design.md` §3D-Assembly (2026-05-20, v1-era), an
  ANTENNA-coverage statement for a wing that carried a Yagi — V2-only, absent on v9 (ADR-046 §2.4).
- `hub-thickness-deflection.md` §5/§6 treats VERTICAL as the ADR-049 value and flags the 7×.

Confidence: HIGH (see REPORT.md). The ONLY live counter-assertions were the socketspec §1
prose + its derivative carry; every other record that speaks to the orientation says vertical.

Loop closed: appended CORRECTION blocks to `docs/WING-TO-HUB-SOCKET-SPEC.md` §1 (orientation +
its stale 22 × 22 hub figures) and to `docs/adr/048-*.md`; rewrote sheet `OPEN-23` to
RESOLVED with citations (still keeps a TODO(unverified) for the ±30° droop, which stays open).

Moment consequence: freezing VERTICAL adopts the LARGER (7×) root moment (end-only wing
1.685 mN·m vs 0.24 mN·m axial). It does NOT settle the 0.4 mm verdict — the analysis's own
verdict is "cannot be settled from the record" because FR4 modulus, joint allowable, rotation
rate and launch acceleration are all still absent. Stated, not invented.

## Cluster 2 — registry + fail-closed checker + test (Part B)

- `docs/ssot/parameters.json` — JSON registry (repo already uses JSON for its SSoT:
  `tracker/hardware/placement-source-of-truth.json`). 5 entries: esp32s3_flash_size (8 MB),
  v9_2g4_rx_radio (bare LoRa2021), wing_plane_orientation (VERTICAL), hub_outline
  (103.0 × 103.0 mm), f33_castellation_land_size (1.30 × 1.30 mm). Each names ONE owner, a
  canonical value, anchors that prove the owner still asserts it, a `who_else_asserted` note,
  a `scan` set, reasoned `exempt` entries, and `forbid` regexes.
- `scripts/param_ssot_check.py` — FAIL-CLOSED: exit 0 PASS / 1 FAIL (conflict) /
  2 UNDETERMINED (unreadable file, missing registry, empty scan surface, un-reasoned exemption).
  Annotation-aware (line markers `was`/`stale`/`TODO(unverified)`/…; file markers
  `CORRECTION`/registry citation/`INHERITED`), so a correction block does not itself fail.
- First run caught FOUR genuine un-annotated contentions (socket spec §1/§4, ADR-048 §2.1/§2.2/
  §2.4, `hardware-design.md:21`, `adr/040:164`) — resolved by the correction blocks above
  (hardware-design.md and ADR-040 got new ones for the hub outline). Second run: PASS.
- `tests/test_param_ssot.py` — mutation tests on a fixture tree + a real-repo PASS test.

## Cluster 3 — wiring + gates

- `scripts/param_ssot_check.py` in `tests/` (auto-collected by `pytest tests/`).
- AGENTS.md section added.

## Gate tallies to record in REPORT.md
(filled after the runs)

FINAL:
- `python3 -m pytest tests/ -q --continue-on-collection-errors` → **564 passed, 37 skipped, exit 0**
  (baseline 550 + my 14 = 564). An earlier run hit 1 failure in
  `tests/test_board_lock.py::test_lock_status` (a 10 s subprocess timeout on
  `tools/board-lock.py status` under a load-average of 8.4); that test passes in
  isolation (2 passed, 6 skipped) and passes in the confirming full run — it is
  environmental load, not this change.
- `scripts/hub_array_topology_check.py` → PASS (exit 0)
- `scripts/bypass_diode_check.py v9_flight.net` → PASS (exit 0)
- `check_sch_gates.py v9` → V9 GATES PASS (TODO 60, registered 33, min 14)
- `check_sch_gates.py` (C3) → ALL GATES PASS (C3 sha256 `4dd7e3fc…` unchanged)
- `scripts/param_ssot_check.py` → PASS (exit 0); planted contradiction → FAIL (exit 1)

Reverted generated churn (not committed): `v9_flight.net`, `v9_flight-erc.rpt`,
`v_c3_flight.net`, `v_c3_flight-erc.rpt` (generator embeds the absolute worktree
path `bf-main`→`bf-ssot` + a date), and the two rebuilt tracked test binaries
`fips_transport/test/test_fips*` (the suite recompiles them).

