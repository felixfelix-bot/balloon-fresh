# V9 RADIO-SLOT CONSOLIDATION — three LR2021 slots (operator ruling, 2026-10-14)

**Status:** ✅ **OPERATOR DECISION, CONSOLIDATED.** Supersedes the "two-site" framing in
`docs/V9-RADIO-SITE-MATRIX.md` §1 and my earlier F33 Option-B recommendation.

## The ruling, verbatim in substance

> The two 2.4 GHz radios are **mutually exclusive with each other**, not only with 433. ADR-034's win
> was **simultaneous TX and RX on separated bands** — true for 433 vs 2.4, and it does not cover
> **2.4 RX against 2.4 ranging**. R7 makes that the arbiter's **explicit contract** rather than
> something implied by a table, plus a semantics note: **what's exclusive is the slot, not the chip.**
>
> So we should have **three LR2021 slots in total. Two slots for the low-power radios and one slot
> for the F33 radio.** How many we populate and which ones we populate is something we will decide at
> a later point in time.

## Measured against the current design

Hub netlist `tracker/hardware/schematics/flight_board/v9_flight.net`, radio modules:

| ref | value | role |
|---|---|---|
| **U2** | `LoRa2021F33-2G4` | Site **A** — HP/F33, on the **nested** pad field |
| **U3** | `LoRa2021_Castellated` | Site **B** — bare LP |
| U4 | `SX1280` | **separate silicon** (LR2021 is not the ranging radio) |

`docs/V9-RADIO-SITE-MATRIX.md` §1 declares exactly **two** sites, and Site A is documented as
*"bare `LoRa2021` (LP) **or** `LoRa2021F33-2G4` (HP) — **mutually exclusive**"*.

### ⚠ Gap: the BOM is three parts short of the ruling

| | LR2021 LP slots | F33 slots | netlisted radio sites |
|---|---|---|---|
| **current** | 1 (Site B) | 1 (Site A) | **2** |
| **ruled** | **2** | **1** | **3** |

**Site A cannot become the third slot.** Its design is *nested* — the bare `LoRa2021` lands **inside**
the F33 ring, so **the two occupants of Site A are mutually exclusive by construction**. The ruling's
*"what's exclusive is the slot, not the chip"* means exclusivity must attach to **2.4 GHz operation**,
not to *where a part is soldered* — and a nested field physically cannot hold both at once.

**So one genuinely new LR2021 LP site is required** (call it **Site C**), with its own:

- land field (verified against the vendor pad file — Site B's bare land pattern is itself
  `UNVERIFIED` per `V9-RADIO-SITE-MATRIX.md` §2 and open item 6)
- `CS` / `RESET` / `BUSY` / `DIO1` GPIO allocation (base pin plan `docs/adr/108`)
- rail: `+3V3` via the TPS7A02 (LP path), **not** the `VSCAP` F33 path
- **2.4 GHz antenna port + the RF switch**, since 2.4 GHz *operation* is what the arbiter
  mutual-excludes
- placement: a second 19.8 × 15 mm body plus its antenna port

**Consequence to plan for, not hide:** a third site plus its antenna port at ~20 × 15 mm body is a
**real area add** on a 70 × 70 mm board that is already at the seat-probe limit. **Site C is a
placement/outline question as much as a schematic one**, and it must be resolved *before* the hub
outline is frozen again.

## R7 — the arbiter contract (as the ruling requires)

From the ruling: R7 is to make the 2.4 GHz exclusivity the **arbiter's explicit contract**, not an
inference from a table:

1. **Contract:** at most **one 2.4 GHz radio in TX or RX at any instant.** A 2.4 GHz *request* while
   another 2.4 GHz radio holds the band is **refused or queued**, but must never be granted.
2. **Scope is the SLOT, not the chip.** Holding the 2.4 GHz slot excludes *all other 2.4 GHz users*
   — including SX1280 **ranging** and the F33's own 2.4 GHz TX. A chip that is otherwise idle still
   occupies the slot the moment it operates at 2.4 GHz.
3. **433 is unaffected.** 433 and 2.4 GHz may operate **simultaneously** (ADR-034's win). A 433 TX
   must not be blocked by a 2.4 GHz holder.
4. **The F33's 2.4 GHz TX is the dangerous one** (+30 dBm, 1 W) and must be inside the exclusion.
5. **Arbitration must be enforced in firmware, not documented.** A table is not a contract.

**Flagged, not resolved:** whether SX1280 **RX** during F33 2.4 GHz **TX** is tolerable (LNA
desense vs absolute exclusion) is an **RF question**. The ruling's contract is absolute exclusion;
if measurement later shows RX-during-TX is benign, that is a **deliberate relaxation with evidence**,
not a default.

## Population, per the ruling

**How many and which slots are populated is DEFERRED — explicitly and by the operator.** The board
must therefore **carry all three slots** with all three **DNP by default** (consistent with
`ADR-040` D2: DNP-by-default, operator hand-solders).

## Order-impacting decisions taken in the same message

| decision | ruling | was |
|---|---|---|
| **F33 population** | ✅ **POPULATE** | my Option B said don't |
| **4G / LTE** | ✅ **GO — include `SIM7600E-H`** (SIM7600E-H/G-H/SA-H/JC-H/NA-H Core Board Development LTE CAT4 Module 4G+Voice+GNSS Breakout Kit) | was open |
| **which board is "looping"** | ✅ **the C3** — *"the S3 hasn't been tested yet"* | was ambiguous |

**My Option-B recommendation is REVERSED on the operator's authority.** The reason I recommended
against was **regulatory**: the F33's +30 dBm (1 W) at 2.4 GHz is not licence-free-legal in Germany.
**That reason is unchanged and must still be honoured** — so the F33 being **populated** and the F33
being **permitted to transmit indoors** are now **two separate questions**, and the second remains
**open**. Populating does not authorise operating.

## Also fixed in the same pass (the stale-artifact class)

**Measured:** `tracker/hardware/hub_board_v9.kicad_pcb` — the **committed repo source** — is
**103.15 × 115.05 mm** and carries 39 footprints, while the board that was actually
**packaged and 3D-exported** (`docs/fab/hub-v9/gerbers/hub_v9.kicad_pcb`) is **70.00 × 70.00 mm**
(also 39 footprints — same netlist and placement, **different Edge.Cuts**).

**So the repo source carries a superseded outline** that no future re-export would notice, because
nothing compares the two. **A regression test now does** (see below).

## Regression tests added

`tracker/hardware/tests/test_v9_board_invariants.py` — asserts, from live files:

1. **Radio sites:** the hub has **≥ 3** netlisted LR2021 slots and Site A is **not** relied on to
   yield two (it is nested → mutually exclusive). **Fails today**, which is correct: it records the
   gap until Site C exists.
2. **Outline agreement:** every committed hub board and every packaged hub board agree on their
   Edge.Cuts extent. **Fails today** on the 103.15 × 115.05 vs 70 × 70 divergence.
3. **DNP consistency:** `C_CAP1`/`C_CAP2` populate state in the CPL agrees with the accepted-risks
   register — one authority, not two.
4. **No `TODO(unverified)` on populated rows:** every populated CPL row has a real part number; the
   `TODO(unverified)` parts (`R_NTC1`, `TH_NTC1`) must be either selected or explicitly DNP.

## Open, and owned by name

| item | owner | note |
|---|---|---|
| **Site C** schematic + land pattern + GPIO + rail | design | new work, needed for the ruling |
| Site C placement / outline (70×70 is tight) | design | must precede the next outline freeze |
| R7 arbiter implementation | firmware | contract above |
| F33 **operate** legality (vs populate) | operator | +1 W at 2.4 GHz, DE |
| `R_NTC1` / `TH_NTC1` selection | operator | both are on the **populated** list |
| `C_CAP1`/`C_CAP2` DNP ruling | operator | changes stored energy, not just the CPL |
| SIM7600E-H integration (rail, SIM, antenna, Enclosure) | design | base station, off the D14-frozen 5 V section |
