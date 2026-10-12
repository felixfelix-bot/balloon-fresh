# WING-TO-HUB SOCKET SPEC — hub-side requirement for the v9 board

**Audience:** the engineer/worker laying out the v9 hub board.
**Authority:** derived from `docs/adr/046-wing-board-interface.md` (Status **Proposed**, text
not human-accepted). The wing side of this interface is fixed in copper by
`tracker/hardware/wing_board/wing_board_v9.kicad_pcb`.
**Scope of this file:** the **hub side only**. It is written so the hub layout can be changed
without asking the wing author anything. Read this together with ADR-046 §2 (electrical) and
ADR-046 §4 (mechanical).

> This document does **not** authorise any edit to
> `tracker/hardware/schematics/flight_board/build_flight_sch.py`, the v9 schematic, or any v9
> board file. It is a requirement record for the orchestrator to fold into v9.

---

## 1. How many interfaces

**Four (4) identical wing interfaces**, one per hub edge, at **90° spacing** around the hub
perimeter (`docs/hardware-design.md` lines 46–48).

Each interface is one wing **socket** = one 4-pad land set (repeated on both the top and the
bottom face of the hub edge) + one optional milled slot.

Wing arm orientation (carried from `docs/hardware-design.md` §3D-Assembly, unchanged):
the wing's long axis is **perpendicular to the hub plane**, tab inserted inward, wing body
extending outward from the hub edge. Wings 1–2 horizontal, 3–4 inclined ≈30° below the hub
plane. **The socket land geometry is identical for all four; only the assembly tilt differs,
and the tilt is set at soldering time, not by copper.**

> **CORRECTION (2026-10-08, `fix/record-contradictions`) — the two orientation sentences
> above are STALE. The wing plane is VERTICAL (a blade); the governing record is
> `docs/adr/049-wing-architecture.md` §5 item 6.** Read this section as: long axis **radial**
> in the hub plane and pointing outward, **25 mm width vertical** — the socket land row, the
> slot and the keep-out are unaffected. The sentences above are inherited v1-era prose
> (`docs/hardware-design.md` §3D-Assembly, committed 2026-05-20) and are self-contradictory
> with each other ("long axis is perpendicular to the hub plane" vs "Wings 1–2 horizontal").
> They are excluded by the tab/slot arithmetic the two records agree on: a 0.9 mm slot admits
> a 0.6 mm tab plus a 0.30 mm gap (ADR-046 §4.1), and a 9.0 mm tab cannot fit a 6.0 mm
> in-plane slot — so the wing plane cannot be coplanar with the hub. This agrees with
> `ADR-046 §4.1` ("90° to the hub plane, wing plane normal to the hub plane"), ADR-051 §1.4
> and ADR-055 §1. The "horizontal" in the source document was an **antenna**-coverage
> statement for a wing that carried a Yagi — and the wing antenna is V2-only and **absent on
> v9** (ADR-046 §2.4). **The ±30° droop of wings 3–4 is NOT resolved here** — it had no v9
> rationale and no v9 record fixes it; it stays `TODO(unverified)`. This section is otherwise
> unchanged: the land geometry is identical for all four and the ADR-048 datum asserts no
> rotation. Registered as `wing_plane_orientation` in `docs/ssot/parameters.json`; enforced by
> `scripts/param_ssot_check.py`.

> **CORRECTION (2026-10-08, same branch) — the hub-outline figures in this file are STALE.**
> Every "22 × 22 mm" in §4 and §7 is the inherited v1-era figure (`docs/hardware-design.md`
> line 13). The current v9 hub is **103.0 × 103.0 mm** (the first v9 hub PCB,
> `tracker/hardware/hub_board_v9.kicad_pcb`, S0 placement), owned by
> `tracker/hardware/placement-source-of-truth.json`. The arithmetic in §4 ("(22 − 9)/2 = 6.5 mm
> per side") and §7 must be re-read against the real outline before use. Registered as
> `hub_outline` in `docs/ssot/parameters.json`.

---

## 2. Land geometry per interface

Both options below reproduce the **same 4 lands on BOTH faces** of the hub edge (top and
bottom), so the wing tab can be soldered from both sides. Pad numbering must match the wing
tab exactly.

| Item | Value |
|---|---|
| Lands per interface per face | **4** |
| Total copper lands per interface | **8** (4 on the hub top face, 4 on the hub bottom face) |
| Land size | **4.0 mm × 1.2 mm** (4.0 mm along the insertion axis, 1.2 mm across) |
| Land pitch | **1.8 mm** (0.6 mm between land edges) |
| Land centre offset from the hub's outer edge | **1.0 mm inboard** (lands span 0.0…4.0 mm from the edge if the edge margin allows; see §4) |
| Land shape | rectangular (rect), SMD, on the face + that face's mask |
| Layer count touched | the **outer layers** of the hub (F.Cu/F.Mask and B.Cu/B.Mask). If the hub is 4-layer, the lands are still on the two **outer** layers only. |
| Copper-to-board-edge clearance | **≥ 0.5 mm** for the land copper to the hub **perimeter** edge; the land's own inboard end is the only place it approaches the interface edge (see §4) |

**Land placement order across the edge** (looking at the hub from the top face, insertion axis
pointing inward): the 4 lands are in a single straight row perpendicular to the insertion
direction, on the **centre line of the slot**.

### 2.1 Option A — milled edge slot (recommended; ADR-046 §4.2)

- Routed slot in the hub edge: **0.9 mm wide × 6.0 mm deep**, tolerance **±0.10 mm**
  (`TODO(unverified)` — supplier tolerance, ADR-046 §4.3).
- The slot runs on the **insertion axis**, centred on the 4-land row.
- The 4 lands are on the **hub faces immediately flanking the slot** — i.e. the row is laid
  across the wing's tab footprint, so that the tab, once inserted, sits directly over all four
  lands on each face. Nominal lateral offset of each land centre from the slot centre line is
  **the same as on the wing tab: pitch 1.8 mm, land 1.2 mm** (ADR-046 §2.2).
- Slot depth **6.0 mm** = the wing's insertion depth. **The slot must stop ≥ 5.0 mm short of
  the hub's centre** so it cannot enter the hub component court.
  `TODO(unverified)` — the hub component court's actual extent is a hub-layout number; the
  slot must be routed to the hub's keep-out, and the wing author does not own that number.

### 2.2 Option B — plain pad pair, no slot (fallback)

- No routing. The same 4 lands on each face, extended to **5.0 mm along the insertion axis**
  (so the fillet has more area), edge margin as §4.
- The wing tab is laid **flat onto** the hub edge and soldered. Alignment is by hand/fixture.
- Strengthens nothing mechanically beyond the fillet — ADR-046 §4.2 records this as the cost
  of this option.

---

## 3. Net name of every pad

Per interface, in order along the land row (this order **must** match the wing tab, or the
series stack will be wired backwards):

| Land # | Net name | Wing side net | Function |
|---|---|---|---|
| 1 | `W<n>_SOLAR_P` | `SOLAR_P` | wing n solar **positive** terminal (top of that wing's 1.5 V string) |
| 2 | `GND` | `GND` | system ground / wing plane reference |
| 3 | `W<n>_RF` | `RF_FEED` | **V2-only provision** — leave as a land with **no net** on v9 (see §3.2) |
| 4 | `W<n>_SOLAR_N` | `SOLAR_N` | wing n solar **negative** terminal |

where `<n>` ∈ {1,2,3,4} is the slot index.

### 3.1 The stack wiring the hub must implement (ADR-046 §2.3)

```
stack_top  = W1_SOLAR_P   -> BAT54 -> supercap bank -> TPS7A02 (ADR-006)
             W1_SOLAR_N —(hub link)— W2_SOLAR_P
             W2_SOLAR_N —(hub link)— W3_SOLAR_P
             W3_SOLAR_N —(hub link)— W4_SOLAR_P
stack_bot  = W4_SOLAR_N   -> GND plane
```

**Mandatory:** the `GND` land of each interface ties directly to the hub ground plane. It is
**not** in the solar string. Do not tie any `W<n>_SOLAR_N` to `GND` except `W4_SOLAR_N`.

### 3.2 `W<n>_RF` on v9

Leave the land in copper with **no net assigned** (an isolated provision pad) — ADR-046 §2.4.
An unnetted pad creates no ratsnest and no DRC item, and it keeps the V2 wing-walk possible
without re-spinning the hub. Do **not** tie it to GND.

---

## 4. Keep-out around each interface, and edge clearance

- **Slot keep-out (Option A):** a rectangular keep-out of **the slot outline + 1.0 mm** on all
  sides. No copper (other than the four `W<n>_*` lands), no vias, no component courtyard, and
  no silkscreen may enter it. This is the milled/routed cut-out zone.
  `TODO(unverified)` — the hub's own routing/keep-out clearance rule (which may be > 1.0 mm)
  governs; take the larger of the two.
- **Land keep-out:** 0.5 mm around each land that is not another land of the same interface
  set. The 1.8 mm pitch / 1.2 mm land already leaves exactly 0.6 mm between neighbours.
- **Component keep-out:** **no component body or courtyard within 1.5 mm** of the socket
  land row on either face, because four 176 mm wings are soldered by hand at a 90° angle and
  the iron needs access to both faces. `TODO(unverified)` — the hub worker's placement gate may
  impose a larger value; use the larger.
- **Board-edge clearance:** the four lands must keep **≥ 0.5 mm** of copper-to-hub-perimeter-
  edge clearance where they do not cross the interface edge. Across the interface edge itself
  the land is the interface — that edge is the one place copper intentionally reaches the
  outline, and it must be the **slot's centre line** (Option A) or the **land row's axis**
  (Option B).
- **Slot-to-slot:** the 4 slots at 90° must not intersect each other or the corner; on a
  22 × 22 mm hub an 8 mm-wide tab centred on a 22 mm edge leaves 7 mm per side — **no
  interference**, but the routed slot length (6.0 mm) plus its 1.0 mm keep-out must be checked
  against the hub's corner radius.

---

## 5. Bypass-diode provision (mandated, DNP for the first prototype)

Per interface, one **Schottky bypass diode provision across `W<n>_SOLAR_P` ↔ `W<n>_SOLAR_N`**,
cathode to `W<n>_SOLAR_P`. Rationale: ADR-046 §2.3 — without it one shaded wing collapses and
reverse-stresses the whole 6.0 V series string.

- Package suggestion: SOD-323 or SMA (BAT54 family, matching ADR-006's existing BAT54).
- **DNP on the first prototype build**; the two pads must still be laid out and routed so the
  part can be fitted later.
- The series-blocking BAT54 at the stack output (ADR-006) is **separate** and is **not**
  replaced by this.

---

## 6. Silkscreen marking

Per interface, on **F.Silkscreen** (and mirrored on **B.Silkscreen** where the interface is a
through feature):

| Marking | Text / shape | Position |
|---|---|---|
| Wing number | `W1` … `W4` | beside the land row, clear of the keep-out, ≥ 1.0 mm from copper |
| Pin 1 marker | a `1` (or a dot/bar) | at the `W<n>_SOLAR_P` end of the row |
| Pin 4 marker | a `4` or an arrow | at the `W<n>_SOLAR_N` end of the row |
| Slot centre | a centre-line tick on the interface edge | on the slot axis (Option A); on the land-row axis (Option B) |
| Orientation | `90` (or a right-angle glyph) | beside the slot, to mark the wing's perpendicular attach |

Silkscreen must not cross any land or pad (JLCPCB `silk_over_copper` is a warning, not a
blocker, but the hub is being kept warning-clean). Text height ≥ 0.8 mm, stroke ≥ 0.12 mm.

---

## 7. Summary table the hub engineer needs

| Requirement | Value |
|---|---|
| Interfaces | 4, at 90° |
| Lands per interface per face | 4 (8 per interface) |
| Land size / pitch | 4.0 × 1.2 mm / 1.8 mm |
| Net order (1→4) | `W<n>_SOLAR_P`, `GND`, `W<n>_RF`(no net on v9), `W<n>_SOLAR_N` |
| Slot (Option A) | 0.9 mm × 6.0 mm, ±0.10 mm, keep-out +1.0 mm |
| Insertion depth | 6.0 mm |
| Edge clearance | ≥ 0.5 mm (except at the interface edge itself) |
| Bypass diode | 1 per interface, `W<n>_SOLAR_P`(K)–`W<n>_SOLAR_N`(A), DNP |
| Silkscreen | `W<n>`, pin 1 / pin 4 markers, slot centre tick, `90` |
| Stack wiring | W1.N→W2.P, W2.N→W3.P, W3.N→W4.P; top=W1.P, bottom=W4.N |

## 8. Explicit open items (do not guess these in the hub layout)

1. `TODO(unverified)` — the hub's actual component keep-out at the slot location (owns the
   slot depth ≤ 6.0 mm).
2. `TODO(unverified)` — JLCPCB's routed-slot width tolerance (0.9 mm ± 0.10 mm assumed).
3. `TODO(unverified)` — the hub v9 layer count; the lands are on the outer layers only.
4. `TODO(unverified)` — the hub's placement gate's minimum component-to-interface clearance
   if it exceeds the 1.5 mm given in §4.
