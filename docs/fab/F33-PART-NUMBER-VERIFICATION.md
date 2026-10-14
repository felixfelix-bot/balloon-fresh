# F33 / RADIO MODULE PART-NUMBER VERIFICATION — live JLCPCB API, 2026-10-14

**Status:** ✅ **VERIFIED against JLCPCB's live API with positive controls.** Two substantive
findings: **our documented LCSC number does not exist**, and the **F33 price is 2.7× the figure in
our docs.** Neither breaks the order (both radio sites are already DNP), but both mattered.

## Method, and why the controls matter

Queried the live component-search endpoint
`POST jlcpcb.com/api/overseas-pcb-order/v1/shoppingCart/smtGood/selectSmtComponentList/v2`.

**Every batch included a POSITIVE CONTROL** — a code already verified live in the hub BOM
mapping — because an endpoint that returns `total: 0` for everything looks identical to *"part not
found"* when it is really *"my query is broken"*:

| control | result |
|---|---|
| `C50645` (SS24) | ✅ found, stock 774 321, $0.0257 |
| `C2876746` (BQ25504RGTR) | ✅ found, stock 21, $4.5857 |

**Both controls returned matches, so the `total: 0` results below are REAL negatives**, not query
failures. (This is the same discipline the campaign needed after getting a *"MISMATCH"* verdict
from its own broken CPL checker.)

## Finding 1 — `C5913567` DOES NOT EXIST ⛔

Our docs — `docs/DUAL-VARIANT-DESIGN.md:192`, `ground-station-flrc-max-throughput.md`,
`REPORT-design-ground-station-flrc-max.md` — carry:

> `NiceRF LoRa2021F33-2G4 | C5913567 (check) | ~$8 | V2`

**Live: `C5913567` → `total: 0`.** It does not exist on LCSC. **Our own docs flagged it `(check)`
and it was never checked. Had this gone into a paid order it would have failed.**

## Finding 2 — the part NAME is also wrong: it is `LoRa1121F33-2G4`, not `LoRa2021F33-2G4`

The real family on LCSC, with live stock and price:

| LCSC | part | stock | price |
|---|---|---:|---:|
| `C52140340` | LoRa1121F33-2G4 | **0** | $0.0397 *(placeholder price)* |
| **`C53243927`** | **LoRa1121F33-2G4-433MHz** | **3** | **$21.8467** |
| `C53243928` | LoRa1121F33-2G4-868MHz | 31 | $21.8467 |
| `C53243929` | LoRa1121F33-2G4-915MHz | 12 | $21.2594 |
| `C53243930` | LoRa1121F33-2G4-470MHz | 10 | $21.8467 |

**`1121`, not `2021`.** And a `LoRa2021F33-2G4-868/915MHz` exists under `C99003002xx`, but with
**stock 0** and brand `JLCPCB Assembly` — a **system-generated code**, not a stocked part.

**The price is the substantive number: `$21.85`, against our docs' `~$8`. That is 2.7×.**

## Finding 3 — the BOM's "not stocked" claim is CORRECT, but its REASON was imprecise

The shipped BOM says of both radio sites:

> `DNP LoRa2021F33-2G4 (not stocked at LCSC)` / `not stocked; 433/470/868/915 module variants only`

**Measured:**

| site | variant our board was specified for | carried? |
|---|---|---|
| `U2` F33 | **2.4 GHz** (`LoRa1121F33-2G4` bare) | **NO** — `C52140340` stock 0, `$0.0397` placeholder |
| `U3` bare | **2.4 GHz** (`lora2021-2.4G`) | **NO** — `total: 0` |
| — | 433 MHz F33 | ✅ yes, `C53243927`, stock 3, $21.85 |
| — | 433 MHz bare | ✅ yes, `C53243919`, stock 128, $15.54 |

**So "not stocked" is TRUE**, and **the DNP decision stands — but the BOM's phrasing implies the
whole module family is unavailable, when in fact the 433 MHz variants ARE carried.** The precise
statement is: **the 2.4 GHz variants are not carried on LCSC.** That distinction matters because
it means the sites are **sourceable** if a future revision wants them.

## Consequence for the order: none — but for the record: important

Both `U2` and `U3` are **already DNP** in the BOM (hand-installed or not stocked), and the F33
Option-B recommendation was **DNP on legality grounds anyway** (2 W is not licence-free legal in
Germany). **So the order is unaffected.**

**What changes:**

1. **`C5913567` must be struck from every document** — it is not a real part number, and docs
   citing it read as though the module is orderable. Replacement: **the family name
   `LoRa1121F33-2G4` with the correct 433 MHz code `C53243927`** if ever needed.
2. **The `~$8` F33 cost figure is retired: measured `$21.85`.** This was a **planning figure used
   in trade studies**; every downstream cost comparison that used ~$8 is now known to be **~2.7×
   optimistic.**
3. **Confirms the Option-B recommendation financially as well as legally** — at `$21.85` each, the
   "buy 1–2, not 10" advice saves **~$175–196**, not the ~$64–72 estimated from the wrong price.
4. **`U3`'s replacement candidate needs re-checking at design time:** only `lora2021-433MHz`
   (`C53243919`, $15.54, stock 128) is carried, **not a 2.4 GHz variant** — so a future 2.4 GHz
   uplink site must source elsewhere or use a different part entirely.

## Honest limits

- **Stock figures are a snapshot** (2026-10-14) and move; the `stock=3` on the F33 433 MHz variant
  means it could dry up quickly.
- **`C52140340`'s `$0.0397` is a placeholder**, not a real price — do not read it as cheap; read
  `stock=0`.
- I did **not** verify the F33 module's **pinout or land pattern** against the NiceRF datasheet —
  the board's footprint is `balloon_flight_v9:LoRa2021F33_2G4` from the repo. **If the family name
  is wrong, the footprint-to-part mapping deserves a check before any populated build.**

## Reproduce

```
python3 ~/verify_c5913567.py      # controls + target
python3 ~/verify_f33_family.py    # the real family, stock, price
python3 ~/check_bom_claim.py      # is "not stocked" accurate
```
