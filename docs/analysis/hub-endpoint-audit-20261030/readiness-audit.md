# Hub endpoint readiness audit — 2026-10-30

## Verdict

**NOT FAB READY.** Fresh remote master `c7074ddbd574f0b677161f1609abfbedef61faf0` reproduces **40 DRC violations and 86 unconnected records** after copy-only refill. All **nine U1 ↔ U_LORA1280 signal paths are proven** by both layer-aware polygon paths and an independent native KiCad connectivity traversal. This does not establish power/ground completeness, RF quality, schematic parity or fabrication sign-off.

**Correction:** the earlier “84 of 86 are planes” claim is false. Exact UUID-to-object net attribution gives **42 records on +3V3/GND, 44 on other nets**; even power-net membership is not evidence that a plane automatically fixes a record. ADR-140's absence-of-module-pad criterion is not a connectivity proof. Its nine-signal conclusion is independently supported here by actual endpoint paths instead.

## Frozen inputs and reproduction

- Board SHA256 `732bfe889020b3c957fb778f1c30f2a84a3e96171cec37c1fa51dae58a9c6561`.
- Matching `.kicad_pro` SHA256 `01063b32bcba962ba2ee89fa5acbd55a96b006d78567a3037403b05965a75b02`.
- Matching `.kicad_dru`: **absent**; not silently borrowed from a sibling board.
- Refilled copy SHA256 `732bfe889020b3c957fb778f1c30f2a84a3e96171cec37c1fa51dae58a9c6561`.
- KiCad 9.0.9; distro `/usr/bin/python3`; Shapely 2.0.3.
- `manifest.json` hashes project table and repository footprint libraries. Original board, rules and libraries remained byte-identical. No source copper, rules, thresholds or placement changed.

Run from repo root in an isolated worktree at the frozen commit with these evidence scripts available:

```
/usr/bin/python3 docs/analysis/hub-endpoint-audit-20261030/run_audit.py
/usr/bin/python3 docs/analysis/hub-endpoint-audit-20261030/classify.py
/usr/bin/python3 docs/analysis/hub-endpoint-audit-20261030/verify.py
```

First wrapper exit **0**, refill subprocess **0**, direct `kicad-cli pcb drc --format json --severity-all --exit-code-violations ...` **5** (violations, not pass). Classification **0**; verification **0**. Full direct command/output/status is in `commands.json`. Copy lives in `.audit-hub-copy/`, deliberately not committed. `fab_grade.sh` and all routers were **NOT RUN**. Scripts require the frozen tree; running at another revision produces a different measurement.

## Endpoint ledger and remaining scope

`ledger.json` covers **86/86** records, stable 1-based IDs in DRC order, original item UUIDs/positions/descriptions, resolved node IDs, component IDs, net, classification and rationale. `by-net.json` groups records and disconnected components. `connectivity.json` contains every copper node and graph edge; `radio-paths.json` gives reproducible path witnesses.

Classification: **59 real copper disconnections**, **0 intentional-with-evidence waivers**, **27 unresolved record-to-island attributions**. “Real” means electrical discontinuity confirmed on PCB copper, not a decision that every gap must receive a PCB track: off-board wiring, populations and socket mechanics still need endpoint-specific evidence before waiver. No unsupported intentional waiver is applied.

The 27 unresolved rows are **26 GND and one +3V3**. KiCad JSON repeats a zone's outline anchor (e.g. 0.45,0.45), not the island's actual endpoint. A zone UUID can own many islands. We preserve candidate component sets and explicitly refuse to choose an island from that anchor. Native DRC still reports these as missing connections; unresolved does **not** mean benign.

The independent geometry graph has exactly `records + 1` components on each affected net, summing to **86 minimum component joins across 22 nets**, consistent with DRC. This is a topological scope, not 86 independent routing tasks, route length, or effort estimate. Intentional external connections could reduce required PCB routing only after evidence. Routing cost/feasibility was not measured.

| Net | DRC records | Components | Real / unresolved |
|---|---:|---:|---:|
| `+3V3` | 15 | 16 | 14 / 1 |
| `/CUT_SENSE_W1` | 1 | 2 | 1 / 0 |
| `/CUT_SENSE_W2` | 1 | 2 | 1 / 0 |
| `/CUT_SENSE_W3` | 1 | 2 | 1 / 0 |
| `/CUT_SENSE_W4` | 1 | 2 | 1 / 0 |
| `/F33_IRQ` | 1 | 2 | 1 / 0 |
| `/SPI2_SCK` | 1 | 2 | 1 / 0 |
| `/F33_VSENSE` | 3 | 4 | 3 / 0 |
| `/HUB_PV_MID1` | 2 | 3 | 2 / 0 |
| `/HUB_PV_N` | 2 | 3 | 2 / 0 |
| `/HUB_PV_P` | 2 | 3 | 2 / 0 |
| `/SPI1_MISO` | 2 | 3 | 2 / 0 |
| `/SPI1_MOSI` | 2 | 3 | 2 / 0 |
| `/SPI1_SCK` | 2 | 3 | 2 / 0 |
| `/U3_IRQ` | 1 | 2 | 1 / 0 |
| `/VSCAP` | 5 | 6 | 5 / 0 |
| `/W1_SOLAR_N` | 5 | 6 | 5 / 0 |
| `/W1_SOLAR_P` | 1 | 2 | 1 / 0 |
| `/W2_SOLAR_N` | 5 | 6 | 5 / 0 |
| `/W3_SOLAR_N` | 5 | 6 | 5 / 0 |
| `GND` | 27 | 28 | 1 / 26 |
| `/EN` | 1 | 2 | 1 / 0 |

## Proven radio endpoints

| Net | U_LORA1280 pad | U1 pad |
|---|---:|---:|
| `/E28_DIO2` | 1 | 11 |
| `/E28_DIO3` | 2 | 34 |
| `/SPI1_MISO` | 5 | 9 |
| `/SPI1_MOSI` | 6 | 8 |
| `/SPI1_SCK` | 7 | 22 |
| `/E28_CS_N` | 8 | 10 |
| `/E28_RESET_N` | 13 | 32 |
| `/E28_BUSY` | 15 | 31 |
| `/E28_DIO1` | 16 | 33 |

Shared SPI still has two missing component joins per net elsewhere. Do not rip up the proven operator paths to solve those other branches.

## DRC classes and limits

| Class | Count | Interpretation |
|---|---:|---|
| copper_edge_clearance | 16 | Actual measured edge rule violations; no connector exception granted |
| lib_footprint_mismatch | 11 | Board/library divergence; not itself proof of bad copper |
| lib_footprint_issues | 8 | Project table fails to resolve embedded library names |
| silk_over_copper | 3 | Still unresolved, not silently waived |
| starved_thermal | 2 | U_LORA1280 pad 14 and J_PROG pad 1; one spoke vs required two |

No reported clearance, shorting_items or solder_mask_bridge. This is not “no rule-breaking copper”: edge and thermal violations remain. Library names unresolved in the checked-in project setup: `tracker_mechanical` (4), `NiceRF` (1), `balloon_flight_v10` (3). The checked-in table instead includes case-sensitive `Tracker_Mechanical`, `balloon_flight_v9`, `balloon_flight`. We used matching tracked inputs as-is, rather than hiding this by editing configuration. Fully library-resolved footprint comparison remains **blocked**, and host-independent library parity is not claimed.

Geometry uses KiCad polygon conversion (rotated/custom pads and track arcs), layer-specific zones split into islands, and board/footprint copper graphics (two `/USB_DN` shapes found). Only plated through-hole pads and vias bridge layers. Opposite-face SMD XY overlap alone **does not short**. Polygon error bound 1 µm, contact tolerance 1 nm; negative separations at approximation boundaries require review. Netless copper cannot silently bridge named nets in this model (none appears in the copper-shape inventory). This is not an independent cross-net shorts checker; direct DRC owns that result.

Verification covers all records, net tallies, nine polygon witness paths, native pad/track/via reachability, and nine graph negative controls with module escape edges removed. Whole-repository tests, schematic parity/ERC, fab stackup/drill suitability, RF/impedance, assembly and mechanical checks were **NOT RUN**.

## Existing work and conflicts

Before creating this branch, inspected local worktrees and open PRs. Original `foam-wing-3d` checkout on `docs/adr-141-and-d3` was clean and untouched. Fresh audit is isolated in `~/worktrees/hub-endpoint-audit`. Full worktree/open-PR snapshot is in `commands.json`; targeted file lists in `active-pr-files.json`.

Open #372 (`feat/board-nets`), #373 (`feat/route-board-nets`), #374 (`fix/kicad-tested`) all touch the exact audited board: **semantic collision risk if merged later**, not work to duplicate. Other footprint/routing PRs remain open; this audit changes only a new evidence directory and does not reconcile or merge them. Remote master recheck still returned `c7074ddbd574f0b677161f1609abfbedef61faf0`. Later approved connector inward relocation and pigtail planning are out of scope. Re-run audit after any board/rule/library merge.

## Decisions and next actions

1. Preserve all source copper; nine signal paths have affirmative endpoint evidence, so no reroute is justified by their shared net names appearing in DRC.
2. Resolve island-specific identities for 27 rows using KiCad internal ratsnest endpoints or an interactive selection export; never invent endpoint positions from zone anchors.
3. Review 59 confirmed copper gaps against current population/socket/external-wire intent, then plan by connected components. No intentional exemption without endpoint evidence.
4. Repair library naming/configuration in a separate change, then re-run footprint parity; address edge relocation, two thermal spokes and silk separately.
5. Do not order from this snapshot. No physical sign-off or fab-release claim is made.
