# PCB-S2 — residual DRC adjudication (adversarial)

**Date:** 2026-09-17 · **Card:** `t_9a6424cd` · **Parent:** `t_a93eab7b` (S1, gate PASS)
**Frozen basis:** rule file sha `5acd7dce…` · placement sha `f3cf0143…` · project sha `a29acec3…`
**Trap suite:** `drc_traps.py` — T1-T8 all PASS (8/8)

---

## 1. Residual violation adjudication

Every residual class on every attempt board is classified below. The rule: **cosmetic** means
fab-irrelevant and suppressible via `.kicad_dru`; **real** means fab-relevant and must be
fixed or explicitly justified.

### Attempt A — `v8_krt_routed.kicad_pcb` (10 violations, 0/0/0)

| # | class | count | position | adjudication | reason |
|---|-------|-------|----------|--------------|--------|
| 1 | `via_diameter` 0.45 vs 0.60 | 1 | U4 pad 2 (GND) @ (18.35, 30.15) | **REAL — justified** | Via sits inside a 1.325×0.6 mm SMD pad. A 0.6 mm via cannot keep annular ring on a 0.6 mm pad. 0.45/0.2 is JLCPCB's published standard floor. Assembly note: may need plugged via if reflow wicks solder. |
| 2 | `via_diameter` 0.45 vs 0.60 | 1 | U5 pad 4 (I2C_SCL) @ (23.975, 34.975) | **REAL — justified** | Same via-in-pad; pad is 0.35×0.5 mm. No off-pad site exists for this net on this placement. |
| 3 | `drill_out_of_range` 0.2 vs 0.3 | 2 | same vias as above | **REAL — justified** | Hole side of the same two vias. 0.2 mm drill is JLCPCB-legal. |
| 4 | `silk_edge_clearance` | 4 | U2 ref, C_CAP ref, U1 segments ×2 | **COSMETIC** | Silkscreen clipped by board edge on the S0 placement too; JLCPCB ignores; no copper involved. |

### Attempt A2 — `v8_krt_v2_routed.kicad_pcb` (9 violations, 0/0/0)

| # | class | count | position | adjudication | reason |
|---|-------|-------|----------|--------------|--------|
| 1 | `via_diameter` 0.45 vs 0.60 | 2 | (23.3, 36.3) + (22.25, 36.3) | **REAL — mitigated** | Both are freestanding +3V3 plane taps (no containing pad). Tap relocation moved them off-pad but could not reach 0.6 mm without a longer path. Fab-legal at 0.45/0.2. |
| 2 | `drill_out_of_range` 0.2 vs 0.3 | 2 | same vias | **REAL — mitigated** | Same holes. |
| 3 | `track_width` 0.1998 vs 0.2000 | 1 | VDIV_MID @ (5.5, 38.0) | **COSMETIC** | 200 nm rounding artifact on one 3.0 mm segment. Not a fab issue. |
| 4 | `silk_edge_clearance` | 4 | same as A | **COSMETIC** | Same S0 placement artifacts. |

### Attempt B — `v8_freerouting_routed.kicad_pcb` (18 violations, 0/0/1)

| # | class | count | position | adjudication | reason |
|---|-------|-------|----------|--------------|--------|
| 1 | `track_width` 0.15 vs 0.20 | 14 | GND ×10, +3V3 ×2, SPI_NSS ×1, LR_DIO0 ×1 | **REAL — fab-legal** | Freerouting's `-mt 4` optimizer descended below the DSN floor (documented bug). 0.15 mm is within JLCPCB's 0.10–0.15 mm capability but below our chosen 2× margin. |
| 2 | `silk_edge_clearance` | 4 | same as A | **COSMETIC** | Same S0 placement artifacts. |
| 3 | `unconnected` | 1 | Via [GND] F.Cu–B.Cu @ (34.25, 21.72) ↔ U2 pad 8 | **REAL — blocking** | Open GND link to In1.Cu plane. Attempt B fails gate S1. |

---

## 2. Non-DRC finding handed to RF review

**RF_OUT impedance mismatch** (not a DRC violation): `RF_OUT` is routed at 0.20 mm
on F.Cu in all three attempts (4 segments, ~11 mm, U2 pad 9 → ANT1 pad 1).
JLCPCB 4-layer microstrip at h≈0.21 mm wants ≈0.39 mm for 50 Ω.
DRC's `shorts/clearance/unconnected = 0` does **not** imply RF sign-off.
A separate impedance pass + stitching confirmation is required before S3.

---

## 3. Verdicts per attempt

| attempt | gate S1 | blocking residuals | fab-legal? | notes |
|---------|---------|-------------------|------------|-------|
| A (`v8_krt_routed`) | **PASS** | 0 | **YES** | 2 via-in-pad justified; 4 silk cosmetic |
| A2 (`v8_krt_v2_routed`) | **PASS** | 0 | **YES** | 2 freestanding tap vias justified; 1 rounding artifact; 4 silk cosmetic |
| B (`v8_freerouting`) | **FAIL** | 1 unconnected | NO | 14× 0.15 mm tracks fab-legal but below margin; 1 open GND link |

**Best fab candidate:** attempt A (`v8_krt_routed.kicad_pcb`) — fewest justified
residuals, shortest route time (19 s), 57 vias, 663.5 mm copper.
