# REPORT — fix/record-contradictions

Branch `fix/record-contradictions`, worktree `/home/c03rad0r/worktrees/bf-ssot`,
base `github/main` tip `e03696a`. Task: resolve the live wing-orientation
contradiction, and build a single-source-of-truth registry with a fail-closed
checker so the class is caught mechanically.

> `PROGRESS.md` and `REPORT.md` are gitignored (`.gitignore:67/68`) and are
> committed with `git add -f` on THIS branch only. They are NOT on `main`.

---

## Part A — the wing-orientation contradiction

Schema answers:

- **`governing_record`** — `docs/adr/049-wing-architecture.md` §5 item 6
  ("Wing plane orientation is VERTICAL … resolved by arithmetic", dated 2026-10-07).
  Corroborated by `docs/adr/046-wing-board-interface.md` §4.1, `docs/adr/051-*` §1.4,
  `docs/adr/055-*` §1, and `docs/analysis/wing-insolation-geometry.md` §0.
- **`stale_record`** — `docs/WING-TO-HUB-SOCKET-SPEC.md` §1: "Wings 1–2 horizontal,
  3–4 inclined ≈30° below the hub plane", and (two sentences earlier) "the wing's long
  axis is perpendicular to the hub plane" — self-contradictory within one paragraph.
  Its derivative carry, **`docs/adr/048-*` §5 item 6 / v9 sheet item `OPEN-23`**, held
  the contradiction open.

  Evidence that §1 is the stale record (record-only, no re-decision):
  1. **Authority chain.** §1 declares its authority is ADR-046. ADR-046 §4.1 itself says
     "Attach angle **90° to the hub plane, wing plane normal to the hub plane**" = the
     wing plane is perpendicular to the hub plane = VERTICAL. A derivative record cannot
     override its own declared source, so §1's prose is stale.
  2. **Independence.** ADR-051 §1.4 ("the wing planes are perpendicular to it (vertical)")
     and ADR-055 §1 ("four near-vertical blades") derive VERTICAL on their own.
  3. **Mechanics.** `wing-insolation-geometry.md` §0 derives VERTICAL from the tab/slot
     arithmetic both records already agree on (0.9 mm slot admits a 0.6 mm tab + 0.30 mm
     gap; a 9.0 mm tab cannot fit a 6.0 mm in-plane slot) and names §1's "long axis
     perpendicular" phrase the wrong one.
  4. **Provenance of "horizontal".** `docs/hardware-design.md` §3D-Assembly (2026-05-20,
     v1-era) used "horizontal" as an **antenna**-coverage statement for a wing that
     carried a Yagi — and the wing antenna is V2-only and **absent on v9** (ADR-046 §2.4).
  5. **The 7× number was checked, not assumed.** `docs/analysis/hub-thickness-deflection.md`
     §5 (table row) and §6.1 (caveat) both take VERTICAL from ADR-049 §5 item 6 as the
     orientation and quote the 7× axial-vs-radial spread. (That analysis lives on branch
     `analysis/hub-thickness-deflection`, not on `main` at `e03696a`.)

- **`precedence_confidence`** — **HIGH.** The only live counter-assertions were §1's own
  prose and its carry in ADR-048/OPEN-23; every other record that speaks to the
  orientation (ADR-046 §4.1, ADR-049 §5 item 6, ADR-051 §1.4, ADR-055 §1, the insolation
  analysis, the thickness analysis) says VERTICAL, and §1 contradicts its own declared
  source. The residual uncertainty is not about *which record governs* — that is
  unambiguous — but about the **status** of the winning record (ADR-049 is **Proposed**,
  not human-accepted) and about the **±30° droop of wings 3–4**, which is a *separate*
  open question no v9 record fixes. Both are stated as open, not resolved.
- **`open23_resolved`** — **yes.** `tracker/hardware/schematics/flight_board/build_flight_sch.py`
  `V9_TODO` entry retitled and rewritten to "OPEN-23 WING ATTACH ORIENTATION — RESOLVED
  2026-10-08 (ADR-049 §5 item 6)" with the citation; it still carries a
  `TODO(unverified)` for the ±30° droop, so the sheet's TODO register is not weakened
  (60 markers, 33 registered open questions, min gate 14). The regenerated
  `v9_flight.kicad_sch` carries the new note text.
- **`socket_spec_corrected`** — **yes.** A `CORRECTION (2026-10-08)` block was APPENDED
  to `docs/WING-TO-HUB-SOCKET-SPEC.md` §1 (body untouched, per the repo's convention —
  cf. the corrections appended to ADR-042/ADR-056). A second appended block records that
  the file's `22 × 22 mm` figures are stale (hub outline). A reciprocal correction block
  was appended to `docs/adr/048-*` (its §5 item 6 / `OPEN-23` is resolved; §2's datum and
  the "footprint asserts no rotation" decision are explicitly unchanged).
- **`orientation_frozen`** — **VERTICAL wing plane (a blade): long axis radial in the hub
  plane and pointing outward, 25 mm width vertical.** Not frozen: the ±30° droop of
  wings 3–4 (`TODO(unverified)` — no v9 rationale).
- **`moment_consequence`** — Freezing VERTICAL **adopts the LARGER (7×) root moment**
  (end-only wing `M_w = m g × 0.088 m = 1.685 mN·m` vs the axial/horizontal-plane reading
  `m g × 12.5 mm = 0.24 mN·m`), i.e. the conservative reading. It does **not** settle the
  0.4 mm verdict: `hub-thickness-deflection.md`'s own verdict is "**cannot be settled from
  the record**" — under the global-plate model 0.4 mm sits inside a defensible joint
  budget, under the local-socket model it sits 1.4–2.7× outside — because **FR4 elastic
  modulus, the joint's allowable shear strain, the vehicle's rotation rate and its
  launch/release acceleration are all still absent**. Freezing the orientation removes
  ONE of the seven missing/contradictory inputs; the other six remain. **Stated as open,
  not invented.**

---

## Part B — the SSoT registry + fail-closed checker

Schema answers:

- **`registry_path`** — `docs/ssot/parameters.json` (JSON, matching the repo's existing
  machine-readable SSoT convention: `tracker/hardware/placement-source-of-truth.json`).
- **`registry_entries`** — five, each with ONE owner, the canonical value, `anchors[]`
  proving the owner still asserts it, a `who_else_asserted` note, a `scan[]` set, reasoned
  `exempt[]`, and `forbid[]` regexes:
  1. `esp32s3_flash_size` = 8 MB (owner ADR-029; also `sdkconfig.defaults.esp32s3` + `sdkconfig`) — was "16 MB".
  2. `v9_2g4_rx_radio` = bare `LoRa2021` (owner ADR-034 D1/D4; also V9-RADIO-SITE-MATRIX) — was "2.4 GHz RX on the F33".
  3. `wing_plane_orientation` = VERTICAL (owner ADR-049 §5 item 6) — was "wings 1–2 horizontal" (socket spec §1).
  4. `hub_outline` = 103.0 × 103.0 mm (owner `placement-source-of-truth.json` + the generated v9 hub board) — was 22 × 22 mm and 55 × 45 mm.
  5. `f33_castellation_land_size` = 1.30 × 1.30 mm (owner `scripts/gen_f33_landpattern.py`) — was the 2.0 × 1.0 mm guess (the value that had just changed, so the pattern is exercised on it).
- **`checker_path`** — `scripts/param_ssot_check.py` (FAIL-CLOSED; exit 0 PASS / 1 FAIL /
  2 UNDETERMINED). It verifies the owner anchors, then scans the declared file set for the
  `forbid` regexes and fails on any **un-annotated** conflicting assertion. Annotation =
  a line marker (`was`, `stale`, `superseded`, `guess`, `TODO(unverified)`, `→` …) or a
  file marker (an appended `CORRECTION` block, a citation of `docs/ssot/parameters.json`,
  or a statement that the figure is `INHERITED`/`RESOLVED`).
- **`checker_fails_on_planted_contradiction`** — **yes.** Demonstrated twice, both for real:
  1. **Live on the real tree.** A temporary `docs/adr/046-zzz-planted.md` asserting
     "The v9 hub outline is 22 x 22 mm." was created, the gate run, and it returned
     **exit 1**, naming `docs/adr/046-zzz-planted.md:3` and the `HUB-22` rule; the file
     was then removed and the gate returned **exit 0**.
  2. **Committed mutation test.** `tests/test_param_ssot.py::test_planted_contradiction_fails`
     builds a fixture tree, plants an un-annotated `22 x 22 mm` in `docs/bad.md`, and
     asserts the real subprocess exit code is 1 and the report names `docs/bad.md:1`.
     `test_json_report_names_the_violation` asserts the same via `--json`.
- **`checker_passes_on_clean_tree`** — **yes.** `python3 scripts/param_ssot_check.py`
  → `VERDICT: PASS (exit 0)`. (The first run caught FOUR genuine un-annotated contentions —
  socket spec §1/§4, ADR-048 §2.1/§2.2/§2.4, `hardware-design.md:21`, `adr/040:164` — which
  were resolved with the correction blocks above; the mechanism found real defects on its
  first use, which is why the exemptions were tightened and `hardware-design.md` / ADR-040
  got new correction blocks rather than being silenced.)
- **`gate_wired_into`** — the repo's pytest surface: `tests/test_param_ssot.py` is
  auto-collected by `python3 -m pytest tests/ -q --continue-on-collection-errors`. The
  checker is a standalone script (run directly, and from the test via subprocess). Also
  documented in `AGENTS.md` (new section "Single-Source-of-Truth Parameter Registry").
- **`tests_after`** — `python3 -m pytest tests/ -q --continue-on-collection-errors`
  → **564 passed, 37 skipped, exit 0** (baseline 550 passed + this branch's 14 new tests
  = 564). An earlier run had 1 failure in
  `tests/test_board_lock.py::test_lock_status` — a 10 s subprocess timeout on
  `tools/board-lock.py status` while the machine's load average was 8.4; that test
  passes in isolation (2 passed, 6 skipped) and in the confirming full run. It is
  environmental load, not this change (this branch touches no board-lock code).
- **`unsourced_assumptions`** — see below.

### SSoT-gate evidence (real runs)

```
$ python3 scripts/param_ssot_check.py
  ok   [esp32s3_flash_size] anchor ok: docs/adr/029-dual-band-flight-board.md asserts '8\s*MB'
  ... (12 ok lines) ...
VERDICT: PASS (exit 0)

$ python3 -m pytest tests/test_param_ssot.py -q
14 passed in 0.87s
```

Live planted-contradiction demonstration (real tree):

```
$ printf '...\nThe v9 hub outline is 22 x 22 mm.\n' > docs/adr/046-zzz-planted.md
$ python3 scripts/param_ssot_check.py ; echo $?
  FAIL [hub_outline] CONFLICT docs/adr/046-zzz-planted.md:3 matches HUB-22 ('22 x 22') but is NOT annotated ...
VERDICT: FAIL (exit 1)
1
$ rm docs/adr/046-zzz-planted.md
$ python3 scripts/param_ssot_check.py ; echo $?
VERDICT: PASS (exit 0)
0
```

### Gates (all must stay green)

| Gate | Result |
|---|---|
| `python3 -m pytest tests/ -q --continue-on-collection-errors` | **564 passed, 37 skipped, exit 0** |
| `scripts/hub_array_topology_check.py` | **PASS (exit 0)** |
| `scripts/bypass_diode_check.py v9_flight.net` | **PASS (exit 0)** |
| `check_sch_gates.py v9` | **V9 GATES PASS** (TODO markers 60, registered 33, min 14) |
| `check_sch_gates.py` (C3) | **ALL GATES PASS** (C3 sha256 `4dd7e3fc…` unchanged) |

### Note on the one generated artifact touched

Resolving sheet item `OPEN-23` necessarily edits `build_flight_sch.py` (the sheet-item
source) and regenerates `v9_flight.kicad_sch`, where the note text lives as a `text`
element. That is the **only** substantive generated change. The pure path/date churn in
`v9_flight.net`, `v9_flight-erc.rpt`, `v_c3_flight.net`, `v_c3_flight-erc.rpt` (the
generator embeds the absolute worktree path `bf-main`→`bf-ssot` and a timestamp) was
**reverted** so the diff stays honest. **No connectivity, copper, component, netlist,
placement, board, footprint or part was changed**; the ERC error count is unchanged.

---

## Unsourced assumptions / open items (nothing invented)

- `TODO(unverified)` — the **±30° droop of wings 3–4**: no v9 record fixes it; retained as
  open in the socket spec, ADR-048's correction and sheet `OPEN-23`.
- The registry entry `hub_outline` canonical is the **103.0 × 103.0 mm S0 placement-stage
  floorplan**, NOT a frozen fab outline (ADR-051/ADR-055 are Proposed and the array area is
  the operator's duty choice) — recorded as such in the registry.
- ADR-049 and ADR-046/048 are **Status Proposed** (text not human-accepted) — the registry
  records the precedence among the records, it does not promote any record to accepted.
- The `2.0 × 1.0 mm` and `55 × 45 mm` exemptions/annotations rest on the records that
  documented those corrections (`F33-LANDPATTERN-VERIFICATION.md` §11; `hub-outline-authority.md`).
- No value, date, citation or rule was invented. Every registry entry cites an in-repo record.
