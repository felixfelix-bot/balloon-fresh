# ADR-031 — Board bring-up isolation, testability, and staged population

- Status: Accepted
- Date: 2026-10-05
- Deciders: Felix (operator), manager
- Related: ADR-029 (v9 dual-band flight board, pending), ADR-030 (zero-inference PCB pipeline, pending), ADR-022 (mandatory test coverage), ADR-025 (shared-hardware flock mutex)

> Numbering note: 029 and 030 are reserved by open cards (t_2e4f134d, t_2357ae6a).
> This ADR is filed at 031 to avoid a collision.

## Context

A first-article PCB in this project is expected to be wrong somewhere. The
expensive failure mode is not the $30 board — it is *not being able to tell which
part is wrong*, and having to scrap the whole board because one subsystem is dead
and the others cannot be exercised.

The operator asked for two things that sound like one:

1. "Break the board into sections so if one fails I can still use the rest."
2. "Give me isolation so I can prove each subsystem independently."

These are different. Idea (1) — break-away / V-score / perforated sub-boards — is
**rejected**. Every RF section depends on the reference plane, the keep-out and the
feed geometry of the *whole* board; snapping a GNSS section off destroys the
reference plane and the matching, and the fragment has no MCU or regulator. It
destroys exactly the subsystems it was meant to preserve. Idea (2) is what is
actually wanted, and it is cheap.

## Decision

Every designable board in this project (v8i onward) shall provide:

**D1 — Isolation at every subsystem boundary.**
- A **0 Ω link or jumper** in series with *each* power rail (per rail, not per
  board): 5 V, 3.3 V, 2.4 GHz PA rail, GNSS rail.
- A **0 Ω link** on each digital bus line from MCU to a peripheral (SPI SCK/MOSI/MISO/NSS,
  UART TX/RX, I2C), so a peripheral can be electrically removed without cutting traces.
- A **0 Ω link** in each RF feed, between the module antenna pad and the matching
  network / U.FL, so the module's RF port can be isolated from the board's RF.
- Unless a link would break an RF ground return or an impedance-controlled line.
  Where it would, use a test pad instead.

**D2 — Test points, one per net of interest.**
- Every power rail (with a local ground pad next to it).
- Every bus line at the MCU pin and at the peripheral pin (so the link can be
  measured open-circuit in both directions).
- Every RF node: module ANT, module ANT-2G4, after the matching network, at the
  connector. Grounded coplanar test pads so a probe does not detune the line.
- Not on the 50 Ω feed itself unless the pad is GCPW and the line is re-matched.

**D3 — Modules are reworkable, not scrap.**
- No module (radio, GNSS, MCU) is placed such that hot-air removal endangers
  neighbours: keep-out for rework on all four sides, no tall parts downwind.
- Prefer a header/socket only where it does not compromise RF (MCU, GNSS may be
  socketed at first article; the radio module footprint stays castellated SMD).

**D4 — Staged population.**
- One PCB order. Populate the cheap, robust passives and connectors on all N.
- Leave the exotic/expensive modules (radio, GNSS, MCU) **unpopulated on the
  spares** and populate on demand. This cuts first-article capital and keeps the
  option open, at the cost of one hand/hot-air placement step per unit later.
- Ship the exotics as a **consigned loose-parts bag** with the board order.

**D5 — Batch ladder.**
- First article: **5 boards** (design proof, failure attribution, cost inflection
  is between 2 and 5).
- Once proven: **10–20**. Above 10 the per-board cost curve is essentially flat
  (~11 % further saving from 20 vs 10), so a larger batch is justified by
  *spares and inventory*, not by cost, and must be argued on that basis.

**D6 — Tuning pads are insurance, never a requirement.**
- The pi/T-network pads stay in copper with the ability to fit alternatives.
- The **shipped** configuration carries computed fixed C0G/NP0 values selected
  against the pinned JLCPCB 4-layer stackup, so an assembled board needs no
  hand fitting to work.
- Pads exist so that a *measured* deviation can be corrected without a respin —
  not as a substitute for computing the line correctly the first time.

**D7 — Report format.**
- Bring-up results are reported per **isolated block**, each with its own verdict
  (power / MCU / radio 868 / radio 2.4G / GNSS / sensors), so a failure to one
  block never masks the state of the others.

## Consequences

- Slightly larger board area and a handful of extra 0 Ω parts per board
  (free at JLC qty; each is one more BOM line at $0).
- Requires the DRC/layout pipeline to know which nets must *not* be broken by a
  link (the RF ground returns) — an explicit exclude list, checked in review.
- Bring-up becomes a matrix of independent verdicts instead of one pass/fail,
  which is what makes a first article worth the money.
- Break-away sub-board reuse is explicitly off the table; if the operator wants
  a reusable GNSS *module*, the correct answer is a small separate GNSS carrier,
  not a snapped-off corner.

## Rejected alternatives

- **V-score / perforated break-away sections** — destroys the RF reference plane
  and leaves fragments with no MCU/regulator (see Context).
- **Per-board single rail link only** — cannot distinguish "rail is dead" from
  "one subsystem is shorting the rail".
- **No links, rely on DRC + bench probing** — probing a 4-layer board to *isolate*
  a short means cutting traces; the link is strictly cheaper and reversible.
- **Populate everything at once** — higher first-article capital with no
  attribution benefit.
