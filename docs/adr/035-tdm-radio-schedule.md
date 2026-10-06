# ADR-035 — TDM radio schedule: dedicated ranging windows, one transmitter at a time

- Status: **Proposed** — the *design direction* this ADR records was ratified by the
  operator on 2026-10-07; the *text* has not been accepted by a human, so it does not
  say Accepted. Two items are left open for the operator (whether a storage element is
  kept, and the 433 MHz duty-cycle/power legality carried from ADR-034).
- Date: 2026-10-07
- Decision owner: Felix (operator)
- Author: worker-balloon (Hermes agent), promoting the operator's 2026-10-07 radio
  decisions into a decision record.
- Related: ADR-034 (`docs/adr/034-radio-band-split-433-tx-2g4-rx.md`, the band split this
  schedule makes flyable), ADR-029 (`docs/adr/029-dual-band-flight-board.md`, whose §3
  arbiter this ADR extends from a two-port single-module schedule to a multi-chip
  schedule), ADR-030 (placement gate), ADR-031 (isolation links).
- Related artefacts in this repo:
  `docs/f33-module/LoRa2021F33-2G4-datasheet-v1.1.pdf`, `docs/COEXISTENCE-V9.md`,
  `tracker/firmware/` (the flight firmware that must implement this schedule).

> Numbering note: 035 follows ADR-034 on the same branch (`adr/radioband-tdm`); the
> next-free-number check that selected 034/035 is recorded in ADR-034.

---

## Context

The operator's verbatim intent, 2026-10-07 (Felix / c08r4d0r):

> "The SX1280 doesn't need to be ranging all the time. We can have time windows dedicated
> to ranging."

ADR-034 places four RF parts on the v9 board — TX 433 (F33-2G4), RX 2.4 (bare LoRa2021),
SX1280 (2.4 GHz ranging), MAX-M10S (GNSS L1). This ADR records the **schedule** that lets
them coexist on one ~55 × 45 mm board, and it upgrades the arbiter from ADR-029 §3
(which scheduled two ports of one half-duplex module) to a **multi-chip** arbiter.

### Why a schedule is mandatory, not a nicety

Co-located radios cannot run in parallel. On a ~45 × 55 mm board with U.FL pigtails,
antenna-to-antenna isolation is roughly **15–25 dB**, so a **+30 dBm (1 W)** or
**+33 dBm (2 W)** transmitter presents tens of dB above a neighbour receiver's noise
floor. "Different channels" does not rescue it — the interferer is wideband and the
victim is a wideband front end. Therefore **exactly one radio transmits at a time**, and
the design must contain an **arbiter that enforces it**. Ranging is **bidirectional**
(the SX1280 both TX and RX), so it needs its own slot too.

---

## Decision

### D1 — The flight-side radio plan (named, so the schedule has named owners)

| Role | Part | Band | Contends for a slot? |
|---|---|---|---|
| TX | `LoRa2021F33-2G4` | 433 MHz | **yes** — TX slot |
| RX | bare `LoRa2021` | 2.4 GHz | **yes** — RX slot (receive-arm window) |
| Ranging | `SX1280` | 2.4 GHz | **yes** — ranging slot (bidirectional) |
| Position / time | `MAX-M10S` | GNSS L1 (1575 MHz) | **no** — see D3 |

### D2 — The TDM contract: named slot classes and ordering

The schedule is a **firmware contract** with four named slot classes, in a fixed order:

1. **Ranging window** — the SX1280's dedicated slot (the operator's stated window). The
   SX1280 both transmits and receives here.
2. **TX window** — the F33-2G4 on 433 MHz transmits; all other transmitters disabled.
3. **RX window** — the bare LoRa2021 on 2.4 GHz arms its receiver; no transmitter keyed.
4. **Idle window** — Wi-Fi/BLE configuration and logging flush; no radio transmitter
   active.

GNSS is continuous and outside the schedule (D3).

### D3 — GNSS is continuous and does not need a slot (state it, do not imply it)

The MAX-M10S is **receive-only** at **1575 MHz**, far from 433 MHz and 2.4 GHz. It does
not transmit, so it does not contend for the one-transmitter-at-a-time invariant. It runs
**continuously** and is excluded from the slot table. (ADR-029's §3 table gave GNSS a
"quiet" capture slot because it was scheduling a *port switch* on one module; with
separate chips there is no port switch, and GNSS need not be gated at all.)

### D4 — The invariant

**At most one transmitter is active at any instant**, and any transmitter not in its own
slot is **disabled** (deasserted / powered down), not merely idle. "Idle" is not a
state a radio can be trusted to be in; it must be *disabled*. The arbiter owns the
enable/disable state of every transmitter and restores the safe state on any failure
path (carried forward from ADR-029 §3 R5).

### D5 — Honest throughput consequence

With one transmitter at a time, **N radios do NOT give N× throughput**. The link-budget
gain of the ADR-034 433/2.4 split is **simultaneous TX and RX on separated bands** — not
parallel throughput. The schedule trades peak per-radio duty cycle for the ability to TX
and RX at once where a single half-duplex module could not. This is recorded so the split
is not later oversold as a bandwidth win.

### D6 — Where the schedule lives, and how it is tested

The schedule is a **firmware contract** in `tracker/firmware/`. The firmware side must
implement:

- a **schedule table** (slot class, owner, duration, enabled/disabled map per slot), and
- **assertions** over it, as the minimum testable artefact.

The arbiter interface from ADR-029 §3 carries over and is extended to named slots:
`radio_arbiter_acquire(slot)` / `radio_arbiter_release(slot)`, with the same
`BUSY`-line honesty and TTL-reclaim rules, now applied per chip. ADR-029 §5 test 5 (the
host-side arbiter fuzz with a baseline build that must fail) is the normative proof and
is extended to the four slot classes.

### D7 — Energy-opportunistic TX: the schedule is the hook

The schedule is also what makes **energy-opportunistic TX** possible: the **TX slot may
be gated on stored energy being sufficient**. This is recorded as the **intended hook**,
not as a decided feature. Whether a storage element (supercap) is kept is a **separate
open decision** — an operator question is pending and is **not** resolved here.

### D8 — Duty-cycle / regulatory coupling (reference, do not resolve)

The 433 MHz slot's **duty cycle** and **power limits** are an open item: the legality of
2 W on 433 MHz in DE is unresolved (carried from ADR-034). The schedule bounds the duty
cycle but does **not** resolve the legal ceiling; that stays open.

---

## Relationship to standing decisions

This ADR records the TDM schedule that makes ADR-034's band split flyable. It
cross-references the older ADR set; contradictions are stated, not resolved
silently.

### Decisions that remain in force and are unaffected

- **ADR-020 `020-deprecate-radiolib-adopt-raw-lr2021-spi.md`: "Accepted (2026-07-23)" — raw 2-byte opcode protocol.**
  The schedule is implemented above the raw LR2021/SX1280 drivers. ADR-020's
  protocol mandate is unchanged.
- **ADR-022 `022-mandatory-test-coverage.md`: "Accepted" — mandatory test coverage.**
  ADR-035 D6's firmware schedule table and assertions are a testable contract
  under ADR-022.
- **ADR-029 `029-dual-band-flight-board.md`: "Proposed" — arbiter framework remains in force.**
  ADR-035 extends ADR-029 §3's arbiter from a two-port single-module schedule
  to a multi-chip schedule. The `radio_arbiter_acquire/release` interface, the
  `BUSY`-line honesty rule, and the TTL-reclaim rules are carried forward.
- **ADR-030/031/032 (placement, isolation, simulation evidence).**
  These records remain in force as implementation methods; the schedule does
  not change their scope.

### Decisions these records supersede in part

- **ADR-029 `029-dual-band-flight-board.md`: "Proposed" — supersedes the §3 slot table.**
  ADR-029 §3 scheduled two ports of one half-duplex module. ADR-035 replaces
  that with a four-slot multi-chip schedule (ranging, TX, RX, idle) that owns
  the F33-2G4, the bare LoRa2021, the SX1280 and the Wi-Fi/BT transmitter.
- **ADR-017 `017-lr2021-only-ban-sx1280.md`: "SUPERSEDED by ADR-020" — no live SX1280 ban exists.**
  The original ADR-017 incorrectly banned the SX1280 and was superseded by
  ADR-020. ADR-035's use of an SX1280 as a dedicated ranging radio is therefore
  **not a violation of any standing decision**.

### Decisions that conflict and are left open

- **ADR-006 `006-supercapacitor-power.md`: "Akzeptiert" — energy-opportunistic TX vs. storage element.**
  ADR-035 D7 records the schedule as the hook for energy-opportunistic TX but
  deliberately does **not** decide whether a storage element (supercap) is kept.
  That question is carried as an open item. ADR-006's supercap decision remains
  in force for the older architecture but is **not reconciled** with the v9
  power budget; a new power ADR (or an amendment to ADR-006) is required.
- **ADR-005 `005-sky66112-fem.md`: "Akzeptiert" — 2.4 GHz FEM no longer in the v9 path.**
  The v9 schedule assumes the bare LoRa2021's 2.4 GHz RX is unamplified (D1 of
  ADR-034). ADR-005's SKY66112 FEM remains in force for older boards but is not
  part of the v9 schedule's RF plan.
- **ADR-026 `026-dual-mcu-radio-architecture.md`: "ACCEPTED" — dual-MCU architecture not adopted for v9 schedule.**
  ADR-035 assumes a single ESP32-S3 host runs the arbiter. The accepted
  dual-MCU (ESP32-C3 + RP2040) architecture has not been formally superseded;
  it remains an open fork that the operator must resolve for v9.
- **433 MHz duty-cycle / power legality in DE — carried open item.**
  The schedule can bound TX duty cycle, but it cannot resolve the legal
  operating power. Remains unresolved until the operator/regulatory check is
  done.

---

## Open items (kept open, not resolved here)

- **Storage element kept or dropped?** — operator question pending (D7). The
  energy-opportunistic TX hook is recorded; whether a supercap is on the board is not.
- **433 MHz duty-cycle / power legality in DE** — carried from ADR-034, not resolved.

## What would falsify this

- A bench measurement showing antenna-to-antenna isolation on the routed board is
  **≥ 40 dB** (not the assumed 15–25 dB), which would relax the one-transmitter
  invariant and allow some slots to overlap — this should reopen D4.
- A measured SX1280 ranging-window duration so long that the RX window is starved below
  the link's required duty cycle, which would force the D6 (ADR-034) three-part
  SX1280-as-RX option back onto the table.

## Next-free-number check (recorded)

See ADR-034 ("Next-free-number check"). 035 was selected on the same run; no `035-*`
file exists on any branch inspected.
