# ADR-070 — The v9 hub keeps BOTH LoRa2021 sites: F33 for TX, bare for RX

> Numbered **070** on 2026-10-14 by `scripts/adr_next_counter.py`. The allocator's
> failure path was checked in the same run: the number is not hard-coded past this
> allocation and no file is renamed.

- Status: **Proposed** — the direction is the operator's, given **explicitly on
  2026-10-14**: *"Please keep both the large LR2021 (F33) and the small LR2021. We
  want the high power one for transmitting and the low power one for receiving."*
  The **text** is not human-accepted.
- Date: 2026-10-14
- Decision owner: Felix (operator).
- Author: subagent (Hermes), worktree `~/worktrees/v9-route`.
- **Confirms and does not supersede:** ADR-029 **D8** (operator-ratified
  2026-10-05: *"nested dual footprint, F33 **or** bare LoRa2021"*), ADR-034 (the
  band split 433 MHz TX / 2.4 GHz RX), ADR-044 / ADR-047 (the selectable pin-1
  rail). This record **closes the D8 build question** that those records left to
  be decided at build time.
- Related: ADR-063 (array overhang), **ADR-068 as revised** (outline = 70 × 70 mm,
  which is what seats both sites), ADR-069 (MCU = S3).

---

## 0. The decision

**Both LoRa2021 sites are POPULATED and both are the design of record.**

| Site | Ref | Part | Role | Rail |
|---|---|---|---|---|
| **Large** | `U2` | `LoRa2021F33-2G4` | **433 MHz DOWNLINK TX** — +33 dBm / 2 W, ~1100 mA at 5 V, internal 0.5 ppm TCXO | **pre-regulator, raw `VSCAP`** (~5.4 V) |
| **Small** | `U3` | `LoRa2021_Castellated` (bare) | **2.4 GHz UPLINK RX** — crystal only, no TCXO | 1.8–3.6 V (3.3 V) |

Both are **already placed and fully routed** at 70 × 70 mm: `U2` at (25.84, 18.15)
and `U3` at (23.91, 37.84), 18 pads each, on the 48/48-net complete route
(`docs/fab/hub-v9/SEAT-PROBE-RESULT.md`).

## 1. Why this is the right split (the physics, not a preference)

**A transmitter wants power; a receiver wants sensitivity.** They are different
optimisation targets and the same silicon cannot serve both well:

- **TX at 433 MHz** needs **+33 dBm (2 W)**. That is a *power* problem: a
  high-efficiency PA and a rail that can supply ~1.1 A. The F33 has the PA and its
  internal TCXO gives 0.5 ppm — necessary for a narrowband downlink that a ground
  station must acquire without hunting.
- **RX at 2.4 GHz** needs **sensitivity and low current**. A receiver does not need
  2 W, does not need a TCXO (the crystal is adequate for receive-only), and *does*
  want the lowest possible quiescent draw — because on a solar/bank vehicle the
  receiver is the part that stays awake.
- **Running one part for both would force the receiver to carry the transmitter's
  bias network and power cost**, and would put the high-power PA's thermal load on
  the receive path. Splitting them is why the band split in ADR-034 is physical
  rather than a mode switch.

**The rail split is load-bearing and already recorded:** the F33's pin 1 must be fed
**pre-regulator from the raw storage node** for full power (ADR-047 §6: *"MUST be fed
pre-regulator"*), while the bare LoRa2021 takes **3.3 V**. That is why ADR-029 D8's
*"selectable pin-1 rail"* exists, and it is **not** a convenience — it is the only
way both sites can share a footprint family.

## 2. What this costs, honestly

- **+1.2 g class** for the second radio site (`IRLML`-class figures; see the mass
  budget). It is **not** free: two radios is two bodies.
- **Board area is why the outline is 70 × 70 mm.** `U2` alone is 39.65 × 22.30 mm
  and is the single part that does not fit at 60 mm
  (`tracker/hardware/seat_probe.py`). Keeping **both** sites is therefore the
  reason the board is not smaller. This is the direct trade: **both radios ⇔ 70 mm**.
- **Two SPI buses** — already required and already the reason the MCU is the **S3**
  (ADR-069), not the C3.

## 3. Consequence for the D8 provision

ADR-029 D8 created the nested dual footprint so the site could be built as `F33`
**or** bare `LoRa2021`, gated at build. **This record resolves that gate as: BOTH,
always.** The "or" becomes "and", so:

- **Neither site is DNP** on the flight variant.
- The **selectable pin-1 rail** (ADR-044/047) must **exist in hardware**, because the
  two sites need different rails — it is no longer optional insurance.
- A **future variant that wants only one radio** remains possible (the footprints are
  separate), but it is now a deliberate variant decision, not the baseline.

## 4. What would falsify this

- A mass budget showing the second radio site breaks the float ceiling at the chosen
  envelope. **This is a real risk and is not dismissed** — the payload is already
  ~57 g against a community 9–22 g band, and the outline grew 60 → 70 mm for exactly
  this reason.
- A bench measurement showing the bare LoRa2021's crystal is **not** adequate for
  2.4 GHz receive acquisition in the flight thermal profile.
- Evidence that one part can serve both directions at acceptable sensitivity and
  current. **Not demonstrated; the physics above argues against it.**

## 5. Reproduce

```
python3 tracker/hardware/seat_probe.py                      # outline seating, both radios
python3 tracker/hardware/check_wing_seat.py <board>         # wing-socket pads on-board
python3 tracker/hardware/list_unconnected.py <drc.json>     # open items, by net
```
