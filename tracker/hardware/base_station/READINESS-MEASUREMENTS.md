# Base-station readiness measurement

**Follow-up:** `RP2040-CAPTURE-EVIDENCE.md` records the datasheet-backed corrected
source and isolated netlist candidate. The original boards/netlist below remain
unchanged; this baseline's "no spec change" statement describes the initial audit,
not the subsequent candidate work. Analog/flash/clock/USB completion remain blocked.

Input: origin/master `2449ad8a` (fetched before creating this worktree).
Authoritative newest tracked placement: `base_station_v1_placed_v2.kicad_pcb`.
No board, netlist, spec, MCU choice, or project rules were changed. This is still RP2040.

## Exercised fix

Both existing checks initially crashed on a nonexistent hardcoded `~/worktrees/v9-route` path.
They now resolve their own checkout. Regression tests copy inputs to an isolated tree and execute
both real scripts there. A separate 95 -> 9 mA mutation demonstrated the transcription check
previously passed an incorrect spec (33/33). Added a focused check for the frozen LNA current;
it now fails that mutation. The old counter-test combined two faults and edited the live spec;
it now runs isolated single-fault controls without modifying source data.

Results: transcription 34/34; netlist invariants 25/25; three portability/mutation tests pass.
These tests are NOT pinout verification or fault-isolation electrical proof.

## Native DRC baseline

Command from repository root:

```
kicad-cli pcb drc --format json --units mm --severity-all --exit-code-violations -o tracker/hardware/base_station/output/readiness/baseline-drc.json tracker/hardware/base_station/base_station_v1_placed_v2.kicad_pcb
```

KiCad 9.0.9, exit 5. As-stored board (no refill), original same-stem project; no same-stem
`.kicad_dru` exists. 44 footprints, 44 named nets (45 including net 0), zero tracks/vias,
three zones. **143 violations + 63 raw unconnected records**:
37 clearance errors, 37 solder-mask-bridge errors, 48 silk-overlap warnings,
16 silk-over-copper warnings, five silk-edge-clearance warnings.

Board SHA256 `095d0278410465f24a2f229969a21017d469bfd34c31f597fea24a6d6afe61af`.
Project SHA256 `d2d19f93e8df91d04bf8a0c3bcd10f25e863d3948a38412be4d17b15cc51d214`.
Detailed measured inventory and pin comparison: `output/readiness/audit.json` (local evidence).

## Routing is blocked by design capture, not just opens

`gen_base_station_netlist.py` assigns RP2040 USB_DM/DP to pads 33/34; installed official KiCad
RP2040 symbol says 46/47. XIN/XOUT assigned 24/25 vs symbol 20/21; SWCLK/SWDIO assigned
28/29 vs 24/25. All 13 examined dedicated-function assignments disagree with the symbol.
This is not permission to replace the MCU: retain RP2040 and validate the entire power/support
circuit and pin map against the manufacturer's datasheet before routing. The 25/25 topology
checks cannot catch these defects. Symbol source and hash are in the audit JSON.

Nine single-pad nets are invisible to open-count completeness: ADC_AVDD, USB_DM, USB_DP,
LDO_EN, RF_TEE_MAST, RF_COAX_RX, RF_LNA_OUT, VGA_RF_OUT, RF_2450_TX. The latter is deliberately
single-ended in the frozen test contract; the others require circuit/interface review.

Part identity gaps remain in D_REV, D_TVS, Q_LNA_SW, R_LNA_ILIM, U_FLASH, U_LDO,
C_TAP, FLT_433_A/B and the ferrite beads. `docs/fab/BASE-STATION-NETLIST-CAPTURE.md`
explicitly records generic packages for flash/load-switch/LDO/tap/clamp, not selected devices.
Search of docs/adr and docs/fab found no superseding selection for those placeholders.
VIN_GS 18 V vs TPS62162 17 V remains recorded as open in spec.json. The freeze's four
pre-layout gates are still explicitly unpassed. Prior route-rejection documentation is not
an accepted routed artifact: only two unrouted placements and an empty scaffold are tracked.

Decision: do not spend routing effort on these fabricated pin connections and placeholder
packages. The next board step is a datasheet-backed corrected RP2040/support-circuit netlist,
selected protection/regulator/load-switch/filter components, then regenerated placement and DRC.
No claim of order readiness; no purchase, upload, push, merge or tag.
