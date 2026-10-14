# U4 (SX1280) PIN ESCAPE — I cannot do this as the operator decided, and here is why

**Date:** 2026-10-14 · **Operator decision:** *"re order its pin escape."*
**Finding: the pin escape is not ours to re-order, because the pin numbering it would follow is
itself a PLACEHOLDER.**

## What the repo says about U4, in its own words

Two records, both pre-existing and both unambiguous:

> **`TODO(unverified) OPEN-13 SX1280 PIN NUMBERS + LAND PATTERN`** — *"The Semtech SX1280 datasheet
> could not be retrieved on this host. The symbol's QFN pad numbering and `SX1280_QFN24.kicad_mod`
> geometry are **PLACEHOLDERS** — every SX1280 pin is `TODO(unverified)`. ADR-045 D1 files the same
> gap as a blocker."*

> **`U4` Description field** — *"*** PIN NUMBERING AND LAND PATTERN NOT VERIFIED - Semtech datasheet
> unreachable on this host; see `TODO(unverified)` notes on the sheet. ***"*

## Why that makes the decision impossible as stated

**A pin escape IS the pin numbering.** "Re-order the escape" means choosing which signal leaves which
side of U4 — and that mapping is exactly what `OPEN-13` says is unverified.

**Measured, from the symbol:** `SX1280_QFN24` is a vendored footprint (not the Semtech part), with
pads 1–25. `RFIO` is **pin 14**, placed on the **right** side of the symbol; the twelve GND pins are
pins 15–24 (right) and pin 3 (left); and the whole SPI/DIO group — `NRESET, BUSY, NSS, SCK, MOSI,
MISO, DIO1, DIO2, DIO3` — sits on the **left**, pins 4–12.

On the real SX1280 (QFN24), the pad functions are **fixed by silicon**. So the escape can only be
re-ordered by either:

1. **Rotating or flipping the FOOTPRINT** — which is a statement about the land pattern, i.e. about
   `OPEN-13`; or
2. **Re-mapping the symbol's pins** — which asserts a pin-to-function table that the repo says is
   unverified, i.e. **inventing the datasheet**.

**Both require resolving `OPEN-13` first. Neither is a placement edit.**

## Second blocker: the spice is the unverified part

`U4` is **`SX1280IMLTRT`, LCSC `C125969`** per the order BOM — so the part is real and stocked, **but
it is the actual SX1280 die** whose pad functions are what `OPEN-13` says we never verified.

And note **`U2` and `U3` are `DNP`** in the same BOM ("not stocked at LCSC"). So of the four radio
sites, **the one with the unverified land pattern is the one being populated.** DNP parts cannot
cause a fab defect; `U4` can.

## Third: two of `U4`'s own opens are still live

- **`OPEN-1 SX1280 SUPPLY` (U4 pins 1, 2)** — *"SX1280 VDD_IN/VDD_IO rail not fixed by any record and
  the Semtech datasheet is unreachable here. Left open deliberately. ADR-060 §5 RE-FILES this as
  unfixed."* (Partly settled by ADR-108 R1 putting it on the shared `+3V3`, but the **provision** —
  "each radio rail gets its own ferrite + bulk cap from 3V3" per ADR-029 §2(f) — is still
  `OPEN-33 SX1280 RAIL DECOUPLING PROVISION`.)
- **`OPEN-2 SX1280 RF PORT` (U4 pin 14 `RFIO`)** — *"No antenna feed is assigned to the SX1280 RFIO.
  ADR-029 D3 enumerates the FOUR connectors as {GNSS, F33 sub-GHz, F33 ANT-2G4, SX1280}, but ADR-034
  D1 re-points the 2.4 GHz RX at a SEPARATE bare LoRa2021."* **So `RFIO`'s destination is contested
  between two ADRs and currently unresolved.**

## What this means, stated plainly

**Routing `/SX1280_DIO1` to close the last open net would be polishing a part that may have to be
re-laid entirely.** If `OPEN-13` resolves with a different land pattern, every U4 trace is redone —
so the 15 mm hand-route I was about to attempt could be **wasted work on a possibly-wrong footprint.**

This is the **same rule the operator already applied earlier in this campaign: FIX THE SCHEMATIC
FIRST.** Applied consistently, U4 must not be routed further until `OPEN-13` closes.

## CORRECTION to my own earlier recommendation

I recommended *"re-order U4's pin escape — more surgical, doesn't disturb the F33 antenna keep-out."*
**That recommendation was wrong, and I can now show why:** I treated the escape as a free placement
variable. **It is not** — it is a function of a pin map the repo marks unverified, so "re-order the
escape" silently **asserts** that unverified map. **The honest options are the ones below, and the
first is to verify the datasheet.**

## The actual options

| option | assessment |
|---|---|
| **Verify the SX1280 pin map** (Semtech DS + package drawing), fix `SX1280_QFN24`, then re-place and re-route | ✅ **CORRECT FIRST STEP.** Closes `OPEN-13`, `OPEN-1`, `OPEN-2` and `OPEN-33` together, and makes both the escape question and the DIO1 route meaningful. |
| **Move U4 to another quadrant without touching its pin map** | ✅ **VALID AND INDEPENDENT of `OPEN-13`.** It changes only U4's *position*, not its pad mapping — so it does not require the datasheet and cannot be invalidated by it. **It is also the fix the channel actually needs.** |
| Re-order the pin escape | ❌ **BLOCKED on `OPEN-13`.** Requires asserting an unverified pin table. |
| Hand-route DIO1 now | ❌ **PREMATURE** — may be discarded when `OPEN-13` closes; and the earlier base-station hand-route measured *worse*. |
| Order with a bench bodge for DIO1 | ❌ **NOT ADVISABLE** — it would ship a part whose land pattern is unverified. The bodge fixes a symptom; the footprint is the disease. |

## Recommendation

**Option 2, now** — move `U4` to open the 11-net channel, because it is **independent of `OPEN-13`** and
is the real cause of the routing failure. **And in parallel, resolve `OPEN-13`** (needs the Semtech
datasheet, which this host could not reach) so the land pattern is real before anything is ordered.

**I am not proceeding with the pin-escape re-order, and I am not hand-routing DIO1.** Both would be
work built on an unverified foundation. **This is a blocker I cannot clear myself: the Semtech SX1280
datasheet is not reachable from this host, and its pin table must not be invented.**

## ADR-060 §1.3 adds a SECOND constraint on any re-place

Recorded after the first draft of this note, and it **restricts option 2**:

**"No reference (crystal *or* TCXO) is drawn for the SX1280 anywhere in the v9 schematic."**
The symbol's pin list has **no `XTA`/`XTB` pin at all**, so the reference is an **undrawn schematic
slot** — and ADR-060 records that it *"inherits that gap"*.

**Consequence for re-placing U4:** the SX1280 needs a **crystal/TCXO plus its load capacitors** that
**do not exist on the board**, and a reference needs a **short, well-routed, low-capacitance
connection**. So U4's free placement is **not** free either — it must leave room for a reference plus a
quiet area for its load capacitors.

**And note the loop:** the reference cannot be placed until the **actual land pattern** is known, which
is the same `OPEN-13` gap. **A circuit element that exists in no netlist cannot be placed, and it
cannot be added until the pin map is real.**

## Also corrected: the "ban"

`docs/adr/101-lr2021-only-ban-sx1280.md` reads *"LR2021-only ban SX1280"* by filename, but its own
Status is **"SUPERSEDED by ADR-020 (2026-07-23)"** and it says of itself: *"This ADR was originally
written with incorrect diagnosis."* **ADR-060 §1.1 confirms: "the SX1280 is neither banned nor
superseded. It is retained."** So the file name is misleading; **U4 is live and retained**, and both
`OPEN-13` (pin map) and the undrawn reference are **current, open gaps**, not history.

## Blocker summary

| # | blocker | who can clear it |
|---|---|---|
| 1 | `OPEN-13` — SX1280 pin numbering + `SX1280_QFN24` land pattern are **placeholders** | needs the **Semtech SX1280 datasheet**; not reachable from this host |
| 2 | No **crystal/TCXO** drawn for the SX1280 (ADR-060 §1.3) | needs the land pattern first (to know which pins are the reference) |
| 3 | `OPEN-2` — `RFIO` (pin 14) destination contested between ADR-029 D3 and ADR-034 D1 | an operator/ADR ruling |
| 4 | `OPEN-33` — SX1280 rail decoupling provision (ferrite + bulk cap) | mechanical once the rail is fixed |

**All four are about the same part, and all four must close before U4 can be routed — or before the
hub board can be ordered, since U4 is a POPULATED part (`SX1280IMLTRT`, `C125969`) while `U2`/`U3` are
DNP.**

**This is the blocker I cannot clear.** The two paths that remain open to me are: (a) move `U4` in
position only — which must now also reserve reference-and-load-cap area — or (b) obtain the Semtech
datasheet. **I need the operator to choose, or to supply the datasheet.**
