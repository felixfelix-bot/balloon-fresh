# ADR-134 — The wing tab is TWO pins; GND and RF_FEED are removed as dead copper, and antennas attach to the hub by U.FL

> Numbered **134** on 2026-10-25. Verified free with `scripts/adr_next_number.py
> --number 134` (exit 0) and across all refs.

- **Status:** **Accepted by operator** (Felix, 2026-10-25, verbatim): *"we will be
  connecting the antennas to the board via ufl. No need to put antennas in the wing board.
  Please get rid of those contacts and update the ADR since that was an outdated
  instruction."* and *"lets remove the pin and any other dead copper that is no longer
  needed as well."*
- **Date:** 2026-10-25
- **Author:** balloon-hermes (manager CW), branch `pr/wing-interconnect-v2`.
- **Supersedes:** **ADR-046 §2.1** — the 4-pin tab. The pinout becomes **2 pins**.
  ADR-046 §2.3 (series order) stands; §2.2 (land geometry) stands for the pads that remain.
- **Supersedes:** **ADR-133** — which explained GND and RF_FEED because they still existed.
  Both are now **gone**; ADR-133 is retained as history so the reasoning is not lost.
- **Amends:** **ADR-132** — the interconnect board carries **2** tab pads and **4** nets,
  not 4 pads and 6 nets.
- **Amends:** **ADR-004** (3D Yagi, 4 wings + hub) — its per-wing Yagi is **abandoned**,
  not merely deferred. Antennas are on the **hub** with **U.FL** connectors.
- **Reads with:** ADR-034/ADR-040 (all v9 radios on the hub), ADR-129 D5, ADR-052.

---

## 0. The decision, in one paragraph

**The wing tab carries two pins: `SOLAR_P` and `SOLAR_N`. `GND` and `RF_FEED` are
removed.** `RF_FEED` was the feed for a per-wing PCB Yagi (ADR-004) that no longer exists
— every v9 radio is on the hub (ADR-034/040) and **antennas attach to the hub through U.FL
connectors**, so the wing has no RF path and no antenna. `GND` existed only as that Yagi's
ground plane. With no antenna on the wing it is dead copper too.

---

## 1. Why `RF_FEED` goes

ADR-046 §2.4 already recorded that `RF_FEED` *"carries no net on v9"* and that the wing's
2.4 GHz PCB Yagi *"is deferred to V2 and is NOT etched on the v9 wing"*. It was kept as a
**provision** so a V2 wing could be ordered with the same tab.

The operator's instruction retires the provision: **antennas go on the hub via U.FL.**
That kills the only reason the pin existed. It is not deferred now — it is **removed**.

## 2. Why `GND` goes

`GND` was never a solar return (ADR-046 §2.3, ADR-133 §1). It was the **ground plane of the
wing's own Yagi**. No Yagi on the wing → no plane to reference → **no reason for the pin**.

**The solar return is unaffected and must stay exactly as it is:** the only return is
`W4.SOLAR_N` at the stack bottom. Removing `GND` removes a *reference* pin that was already
doing nothing; it does **not** touch the series string.

> **The trap survives the deletion and is worth restating:** with `GND` gone there is even
> less excuse to tie a wing's `SOLAR_N` to chassis/ground anywhere except the stack bottom.
> Doing so shorts that wing out of the series string.

## 3. The tab after this record

| Pin | Net | Function |
|---|---|---|
| 1 | `SOLAR_P` | this wing's solar **positive** terminal |
| 2 | `SOLAR_N` | this wing's solar **negative** terminal |

- **Pad geometry unchanged** where it still applies: 4.0 × 1.2 mm, 1.8 mm pitch (ADR-046 §2.2).
- **The insert stays 9.0 mm wide mechanically** — it is bonded into foam and needs the
  surface area. The two pads sit centred inside it.
- **Orientation is now a live risk that the 4-pin layout did not have.** With four pads
  keyed by two outer solar terminals, polarity was hard to get wrong. With two identical
  pads, **the tab can be inserted backwards.** Mitigations, both mandatory:
  1. **Asymmetric pad placement on the insert** (the two pads deliberately off-centre from
     the insert's midline) so a backwards insertion is mechanically impossible, and
  2. **silkscreen `+` on both the wing insert and the hub land**, plus the first-article
     continuity check already required by ADR-132 §4.2.

  `TODO(unverified)`: the asymmetric offset is a **layout** number and is not frozen here.
  If the layout cannot make it asymmetric, **polarity becomes a hand-assembly check only**,
  and that must be stated on the build sheet rather than assumed.

## 4. What this changes downstream

- **Hub:** the land row shrinks from 4 lands per face to **2** (`W<n>_SOLAR_P`,
  `W<n>_SOLAR_N`). The hub is routed against the 4-land row, so **this is a hub respin
  item**, not a free change. It is recorded as such and is **not** authorised for order by
  this record.
- **Interconnect board (ADR-132):** 2 tab pads, **4 nets** (`SOLAR_P`, `SOLAR_MID1`,
  `SOLAR_MID2`, `SOLAR_N`), 10 pads total. Board is **44 × 20 mm = 8.8 cm², 0.79 g/wing,
  3.18 g for four**.
- **`WING-TO-HUB-SOCKET-SPEC.md`** §2/§3 lists four lands and four net names per interface;
  it is **stale** for the two removed pins and must be corrected the same day (AGENTS.md
  SSOT rule).
- **ADR-129 D5's `RF_FEED` cut-sense conductor on the hub side** was an independent use of
  the same *name* on the hub; it is unaffected by the wing-side removal **only if** the hub
  keeps its own conductor for it. **The layout must confirm the hub's cut-sense path does not
  depend on the wing's pin 3.** `TODO(unverified)` — flagged, not assumed.

## 5. What this record does NOT do

- No hub respin, no schematic, no netlist, no BOM freeze, no order.
- No change to ADR-046 §2.3 (series order) or to the two remaining nets.
- No change to the bypass diode scheme (ADR-132) beyond the pin count.

## 6. For future sessions

- **Two pins: `SOLAR_P`, `SOLAR_N`.** No `GND`, no `RF_FEED`.
- **Antennas are on the hub, U.FL.** There is no wing RF path and no per-wing Yagi; ADR-004's
  4× Yagi 3D is abandoned, not deferred.
- **Two identical pads can be inserted backwards.** The asymmetric-offset mitigation is a
  layout task that is NOT yet frozen — do not treat the tab as keyed until it is.
- **The solar return is `W4.SOLAR_N`, never chassis.** Unchanged by this record.

---

*Accepted by operator 2026-10-25. Design only: no board, BOM, order or fab authorisation.*

> **CORRECTION 2026-11-10 — the size in the paragraph above is STALE.** Measured from the board
> (`wing_interconnect_v1.kicad_pcb`, `Edge.Cuts` centreline): **34.60 × 20.00 mm**, not 44 × 20.
> The generator derives the width from the pad extents — *"pads end at x=33.00, +1.6 edge = 34.6"* —
> because the original 44 mm outline left **11 mm of the right-hand side with no copper at all**.
> Mass therefore improves: **0.62 g/wing, 2.50 g for four** (was 0.79 / 3.18).
> The BOARD is correct; this record's figure is stale. Fab bundle and full derivation:
> `docs/fab/wing-interconnect-order/README.md`. Everything else in this record stands.
