# REPORT — v8j MS5611 board: 170 DRC errors → PASSING order gate

**Status: DONE.** The v8j MS5611 flight board passes the deterministic order gate.
Gate run UNCHANGED, exit 0, `--verify` VERIFIED.

## The gate record (raw)

```
ORDER GATE: PASS board=v8j_krt_ms5611.kicad_pcb board_sha256=f6f40338e312
fab_sha256=937e4eda1e9c errors=0 unconnected=0 warnings=14 excluded=0 kicad=9.0.8
```

`tracker/hardware/v8j-GATE-RECORD.json`:
```json
{"tool":"pcb_order_gate","status":"PASS","errors":0,"warnings":14,"unconnected":0,
 "excluded":0,"reason":"",
 "rules":{"violations:silk_overlap":3,"violations:silk_over_copper":3,
          "violations:lib_footprint_mismatch":1,"violations:silk_edge_clearance":3,
          "violations:track_dangling":3,"violations:via_dangling":1},
 "board":"v8j_krt_ms5611.kicad_pcb",
 "board_sha256":"f6f40338e312c65202659d49dab40600415416b6a04f173e6f72863df9228422",
 "fab":"tracker/hardware/output/gerbers_v8j",
 "fab_sha256":"937e4eda1e9cd8b47f4920a68a663e09b6bdaf4340c3362368f500e0715ec644",
 "kicad_version":"9.0.8"}
```

Before (salvaged board): `status=FAIL errors=170 warnings=15 unconnected=11`,
board_sha256 `cb6e6109445574cbea5d55ab276081401102e7a874a2eabf98244e7c03880131`,
fab_sha256 `ae1bae58dee7615c0c46b41db8e43827c8e340df2c3aa47f4a25be1b09353be1`.

## Exact failure-class counts, BEFORE → AFTER

| class | before | after |
|---|---|---|
| clearance | 138 | 0 |
| drill_out_of_range | 12 | 0 |
| hole_clearance | 9 | 0 |
| unconnected_items | 11 | 0 |
| via_diameter | 0 (5 transient during the fix) | 0 |
| track_dangling (warn) | 4 | 3 |
| via_dangling (warn) | 1 | 1 |
| silk_overlap (warn) | 3 | 3 |
| silk_over_copper (warn) | 3 | 3 |
| silk_edge_clearance (warn) | 3 | 3 |
| lib_footprint_mismatch (warn) | 1 | 1 |

Gate errors 170 → 0. Gate unconnected 11 → 0. All 14 residual items are
warnings; the gate's own contract is "warnings (silk etc.) are reported but do
NOT block a board order". The PASSING reference v8i carries 8 silk warnings of
the same kind, so the residual is inherited, not new.

## What was actually wrong (3 independent defects)

The handover hypothesis ("stale placement/geometry") was directionally right but
the details mattered — two of the three defects had nothing to do with geometry:

1. **Stale inner-layer zone fills.** All 138 `clearance` violations were
   `Zone[GND] on In1` / `Zone[+3V3] on In2` against vias and pads, reported as
   "zone clearance 0.2200 mm; actual 0.2005 mm". The fills were computed before
   the U5 swap and never regenerated. Proven with `v8j_refill_test.py`: refilling
   alone took the board from 170 errors to **11**. This is the single biggest
   fix and it touched no copper.
2. **The wrong project rule file.** The salvaged `v8j_krt_ms5611.kicad_pro` was
   KRT's own output, not the frozen sibling the board is judged against: it had
   `min_through_hole_diameter` 0.3 (v8i: 0.2) and `min_hole_clearance` 0.25
   (v8i: 0.2). That alone manufactured all 12 `drill_out_of_range` (U1 pad 19 is
   a legal 0.2 mm PTH under the frozen set) plus most of the 9 `hole_clearance`.
   There was also **no `v8j_krt_ms5611.kicad_dru`** sibling at all. Restoring the
   frozen v8i `.kicad_dru` + `.kicad_pro` (byte copies, filename updated) fixed 21
   gate errors without weakening a rule — the rules are now *identical* to the
   ones the accepted reference board passed under.
3. **U5 was never re-routed, and its nets were wrong.** The salvage removed U5's
   local copper and the EN run to J1.3 (the wider MS5611 courtyard crossed it)
   but left the **BMP280** pad→net assignment on the MS5611 footprint
   (`pad3=SDA`, `pad4=SCL`, `pads 2/3/6/7/8=GND`). The real MS5611-01BA I2C map,
   taken from the official KiCad `Sensor_Pressure:MS5611-01BA` symbol (which
   `extends` MS5607-02BA and matches `Package_LGA:LGA-8_3x5mm_P1.25mm`
   pad-for-pad), is:

   | pin | name | net |
   |---|---|---|
   | 1 | VDD | +3V3 |
   | 2 | PS | GND (low = I2C) |
   | 3 | GND | GND |
   | 4 | CSB | +3V3 (high = I2C) |
   | 5 | CSB | +3V3 |
   | 6 | SDO | GND (addr LSB = 0 → 0x76) |
   | 7 | SDI/SDA | I2C_SDA |
   | 8 | SCLK/SCL | I2C_SCL |

## ⚠ BUG FOUND in the salvaged `build_v8j.py` (not fixed in that file's net table by me — see note)

`build_v8j.py`'s `MS5611_NETS` maps **pin 4 → GND** while **pin 5 → +3V3**. The
official symbol defines pins **4 and 5 as the SAME net (both CSB)**. As written,
that assignment ties GND to +3V3 through the part — a supply short. This is why
the shipped mapping could never have been right. `v8j_u5_netfix.py` implements
the corrected table (pins 4 and 5 both +3V3).

Under the alternative reading (some datasheet revisions put pin 5 = SDO), pin 5
at +3V3 is still electrically valid — it only selects I2C address 0x77. The
firmware probe (`tools/balloon_pressure_test/main/main.c`) walks **both 0x76 and
0x77**, so the board is correct under either reading. **Recommend a human confirm
the MS5611-01BA03 datasheet pin 5 before the first order**, since the KiCad symbol
is the only authority available here and it stacks pins 4/5 as one CSB net.

## How it was done (all scripted, zero hand-editing of the board file)

Every mutation went through pcbnew/KRT; no `read_file`→`write_file` round-trip of
the 384 KB board. Commands live in `PROGRESS.md` → "Pipeline used".

## Push evidence (each ref verified with `git ls-remote`, observed SHAs)

Commit `8590439f4d55e481be267b144b8203d758defc72` on `pr/v8j-ms5611-reroute`,
pushed SEQUENTIALLY (no force-push anywhere; feature ref only, never main/master):

| remote | push result | `git ls-remote <remote> refs/heads/pr/v8j-ms5611-reroute` |
|---|---|---|
| github | `d6ef953..8590439  pr/v8j-ms5611-reroute -> pr/v8j-ms5611-reroute` | `8590439f4d55e481be267b144b8203d758defc72` |
| ngit | `d6ef953..8590439  pr/v8j-ms5611-reroute -> pr/v8j-ms5611-reroute` (PR update published to 2/4 relays) | `8590439f4d55e481be267b144b8203d758defc72` |
| origin | `Everything up-to-date` (same GitHub URL as `github`) | `8590439f4d55e481be267b144b8203d758defc72` |

Progressive saves on the branch: `fe22daa` (diagnosis) → `389cf0a` (0 unconnected,
159 errors cleared) → `8590439` (gate PASS).

## Residual / honest limitations

- 3 `track_dangling` + 1 `via_dangling` + 9 silk + 1 `lib_footprint_mismatch`
  remain as **warnings**. They do not block the gate; the 4 copper ones are
  cosmetic stubs left by the router where it terminated on truncated bus ends.
  Left alone deliberately — re-touching copper after a verified PASS risks the
  PASS for zero gate benefit.
- The gerber layer set is the same 11 layers as the v8i package; the old v8j
  package had extra (Adhesive/Courtyard/Fab/Margin/User_*) layers which the v8i
  convention drops. The fab digest therefore changed — expected.
- `--fab` binds the directory `tracker/hardware/output/gerbers_v8j`; the
  convenience zip `gerbers_v8j_jlcpcb.zip` is beside it and is not part of the
  digest.
