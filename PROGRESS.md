# PROGRESS — v8j MS5611 board to passing order gate

Branch: `pr/v8j-ms5611-reroute` @ d6ef953 (worktree `/home/c03rad0r/worktrees/v8j-ms5611-reroute`)
Gate: `~/.hermes/profiles/manager/scripts/fleet/pcb_order_gate.py` (UNCHANGED, authority)

## Reference / PASSING baseline
- `v8i_krt_gnss.kicad_pcb` 397,725 B, sha256 `638de5638772...` — DRC-clean 4-layer 45x55mm BMP280 board.
- `v8j_krt_ms5611.kicad_pcb` 384,420 B, sha256 `cb6e61094455...` — MS5611 swap; FAIL.

## BEFORE (clusterer, `v8j_drc_cluster.py`, severity-all)
violations=174 unconnected=11

| class | count | note |
|---|---|---|
| clearance | 138 | all identical: zone clearance 0.22mm vs actual 0.2005mm — stale mask/zone geometry at U5 site |
| drill_out_of_range | 12 | min hole 0.30mm, actual 0.20mm — clustered @ (13,12),(13,13),(14,12),(14,13) |
| hole_clearance | 9 | 8x 0.25mm vs 0.2005mm, 1x 0.2142mm |
| track_dangling | 4 | stale track ends left behind by U5 swap |
| (warnings) silk_overlap/silk_over_copper/silk_edge_clearance | 3/3/3 | pre-existing v8i silk, not gate errors... verify |
| (warnings) lib_footprint_mismatch | 1 | `LGA-8_3x5mm_P1.25mm` does not match library `Package_LGA` |
| (warnings) via_dangling | 1 | |

gate record `v8j-GATE-RECORD.json`: status FAIL, errors=170, warnings=15, unconnected=11,
board_sha256 `cb6e6109445574cbea5d55ab276081401102e7a874a2eabf98244e7c03880131`,
fab_sha256 `ae1bae58dee7615c0c46b41db8e43827c8e340df2c3aa47f4a25be1b09353be1`.

## DIAGNOSIS (root cause CONFIRMED)
The MS5611 swap at U5 was a *footprint-only* swap: it replaced BMP280
(Bosch_LGA-8_2.5x2.5mm, 0.65mm pitch, CW pin numbering) with MS5611
(LGA-8_3x5mm_P1.25mm) but:
1. left the old BMP280-era placement/geometry (mask openings, zone cutouts,
   tracks) in place — hence 138 clearance + 4 dangling tracks all around U5;
2. assigned pad nets using BMP280 pin positions (pad3=SDA/pad4=SCL) which on
   MS5611 are GND/PS — hence the 11 unconnected_items at U5 (pads 1,2,4,5,6,8);
3. the 12 under-size drills @(13-14,12-13) and 9 hole_clearance are the
   MS5611's own via/thermal geometry not legalised against the 0.30mm/0.25mm
   board rules.

Evidence: unconnected list references Pad1/2/4/5/6/8 of **U5** at
(21.9..24.1, 34.1..37.9) — the MS5611 site — plus stale tracks at the old
BMP280 fanout.

## FIX PLAN (ADR-030 deterministic, scripted only — no hand-edit)
1. `build_v8j.py` — load PASSING v8i, replace U5 with MS5611 LGA-8_3x5mm_P1.25mm,
   assign correct I2C nets (1=VDD,2=GND,3=GND,4=PS,GND,5=CSB=+3V3,6=SDO=GND,
   7=SDA,8=SCL), strip ALL tracks+vias -> `v8j_krt_ms5611_unrouted.kicad_pcb`.
2. Route from the legalised placement (KRT / freerouting pipeline used by v8i).
3. Refill zones, run legalise/escape passes (v8g_escape_fix, v8g2_via_legalise).
4. Re-run gate UNCHANGED -> require exit 0.
5. Progressive push per verified class improvement: github -> ngit -> origin,
   each verified with `git ls-remote <remote> refs/heads/pr/v8j-ms5611-reroute`.

## MILESTONE LOG
- [x] clusterer run — 174 viol / 11 unconn, classes captured above.
