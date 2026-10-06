# ADR-034 — v9 radio band split: 433 MHz TX / 2.4 GHz RX on two separate chips

- Status: **Proposed** — the *design direction* this ADR records was ratified by the
  operator on 2026-10-07; the *text* has not been accepted by a human, so it does not
  say Accepted. Two items are left open for the operator (the 5 V rail, carried forward
  from ADR-029 O5, and the legality of 2 W on 433 MHz in DE).
- Date: 2026-10-07
- Decision owner: Felix (operator)
- Author: worker-balloon (Hermes agent), promoting the operator's 2026-10-07 radio
  decisions into a decision record.
- Related: ADR-029 (`docs/adr/029-dual-band-flight-board.md`, superseded **in part** —
  see "What this changes relative to ADR-029" below), ADR-035 (TDM radio schedule,
  `docs/adr/035-tdm-radio-schedule.md`, the schedule that makes this split flyable),
  ADR-030 (deterministic zero-inference PCB placement/routing), ADR-031 (board bring-up
  isolation), ADR-032 (simulation evidence).
- Related artefacts in this repo:
  `docs/f33-module/LoRa2021F33-2G4-datasheet-v1.1.pdf` (G-NiceRF, Rev 1.1 — the F33-2G4
  module's datasheet), `docs/COEXISTENCE-V9.md` (the 2026-10-04 source memo ADR-029
  promotes), `docs/F33-MODULE-PLAN.md` (5 V rail candidates, open).

> Numbering note: next-free-number check performed on this branch (see below). 034 was
> chosen because 033 is already claimed elsewhere in the tree
> (`docs/adr/033-giftwrap-single-construction-path.md` on an unmerged branch), and no
> `034-*` or `035-*` file exists on any branch.

---

## Context

ADR-029 records v9 as **ESP32-S3-WROOM-1U + LoRa2021F33-2G4 + SX1280 + MAX-M10S**, and
its **D2** decision collapses the sub-GHz and 2.4 GHz links into **one** module — the
`LoRa2021F33-2G4` — served by two independent 50 Ω ports of a single half-duplex chip
(pin 9 `ANT` sub-GHz, pin 10 `ANT-2G4`).

On 2026-10-07 the operator recorded a decision that **reverses that collapse** in a
specific direction: the two link directions must live on **two separate chips** so they
can be **simultaneous**, and the band assignment is **TX on 433 MHz, RX on 2.4 GHz**.

### What this changes relative to ADR-029 (stated, not silent)

ADR-029 D2 held that one `LoRa2021F33-2G4` module could carry both directions across its
two ports, because the module *has* two independent 50 Ω ports. That is true of the
ports; it is **not** true of the transceiver behind them. The LR2021 is **half-duplex**:
it cannot TX on one port while RX-ing on the other, so the two directions are mutually
exclusive in time by construction (ADR-029 itself admits this in §3 R2: "the two ports
belong to one transceiver core, so the two links are mutually exclusive in time").

This ADR supersedes **D2's single-module collapse** and lands closest to **D2-alt** (the
two-radio fallback ADR-029 kept live), with a specific band assignment D2-alt did not
fix:

- **TX = 433 MHz, on the F33-2G4's 2 W sub-GHz port.**
- **RX = 2.4 GHz, on a separate bare `LoRa2021` module.**

The consequence is that **simultaneous TX and RX on separated bands** becomes possible —
the one thing a single half-duplex module could never offer. The link-budget gain of this
split is *simultaneity*, not parallel throughput (ADR-035 states the honest throughput
consequence: N radios at one-transmitter-at-a-time do not give N× throughput).

---

## Decision

### D1 — The two directions are carried by two separate radio chips

**Decision.** v9 carries **two** LR2021-family radios on two chips, not one module with
two ports:

| Direction | Part | Band | Port |
|---|---|---|---|
| TX | `LoRa2021F33-2G4` | 433 MHz (sub-GHz) | pin 9 `ANT`, the 2 W port |
| RX | bare `LoRa2021` (castellated, the v8h part) | 2.4 GHz | its 2.4 GHz feed |

Rationale:

1. **One LR2021 is half-duplex.** Two RF ports do not make two transceivers. To TX and
   RX *simultaneously* across the two directions, the directions must be on two
   independent chips. This is the operator's stated reason for the split, and it is the
   one thing D2's single-module collapse could never provide.
2. **The RX side is deliberately unamplified.** The ground station can afford
   amplification and a large antenna, so the higher 2.4 GHz path loss is paid for on the
   *ground* side. A receiver gains nothing from an amplifier, so the airborne RX side is
   deliberately unamplified. (Operator's rationale, recorded in spirit.)

### D2 — Why 433 MHz for TX

1. **+3 dB for free.** The module's full 2 W is only available on the sub-GHz port. Per
   the committed datasheet (`docs/f33-module/LoRa2021F33-2G4-datasheet-v1.1.pdf`),
   quoted in ADR-029 D2: **2 W / 33 dBm @433 MHz (< 1200 mA)** vs **+30 dBm / 1 W @868
   and @2.4 GHz (< 800–900 mA)**. TX on 433 buys **+3 dB** over TX on 2.4 GHz — an
   independent, decisive reason to put the *transmit* direction on 433, not 2.4.
2. **433 is the PA-rated band.** The datasheet's sub-GHz power table lists "433/470 MHz
   2 W" as the headline capability, and note 1 states verbatim: *"For 433 MHz, setting
   the register value to 36 is sufficient to achieve optimal efficiency."* The high-power
   band is sub-GHz, and 433 is its 2 W corner.

### D3 — Why 2.4 GHz for RX (and why 868 is forbidden)

1. **The only viable far-band partner.** 433 × 2 = **866 MHz**, which falls *inside* the
   868 MHz receive band (863–870 MHz). So "433 TX + 868 RX" is a **self-inflicted
   harmonic collision** — the 2nd harmonic of the transmitter lands exactly on the
   companion receiver. That pairing is **forbidden**. 433 TX + 2.4 GHz RX is the safe
   pairing, and it closes the logic of D1/D2.
2. The ground side absorbs the 2.4 GHz path loss (D1 item 2), so the RX direction's band
   choice is not punished on the airborne power budget.

### D4 — Filtering obligations (recorded as design requirements, not options)

- **TX low-pass on the 433 MHz feed.** The 2nd harmonic at 866 MHz must be suppressed so
  the 868 MHz band is not polluted regardless of the RX choice (and so the forbidden
  433-TX/868-RX collision of D3 is not re-created by leakage even if a future board
  revisits 868).
- **RX band-pass on the 2.4 GHz feed.** A SAW/BPF is required if the bench shows the 2.4
  GHz RX floor moving when 433 transmits — decide by measurement, not datasheet margin
  (the same measurement-first stance ADR-029 §2(c) takes for its harmonic LPF).

### D5 — RF parts on the board (explicit, kept current)

| Role | Part | Band |
|---|---|---|
| TX | `LoRa2021F33-2G4` | 433 MHz (2 W port) |
| RX | bare `LoRa2021` | 2.4 GHz |
| Ranging | `SX1280` | 2.4 GHz (dedicated time windows, see ADR-035) |
| Position / time | `MAX-M10S` | GNSS L1 |

Four RF parts. (ADR-029's D2b table listed the F33 carrying *both* link directions plus
the SX1280 and MAX-M10S; this ADR re-points the RX direction at the bare module, so the
F33 carries TX only.)

### D6 — Recorded alternative (do NOT silently pick it): the SX1280 as the 2.4 RX path

The SX1280 is itself a 2.4 GHz radio with a receiver, so it **could** serve as the 2.4
GHz RX path and the bare `LoRa2021` could be dropped — **3 RF parts**, less mass, fewer
pins. Recorded as a **recorded option requiring a bench measurement**, in the same style
ADR-029 uses for D2-alt. Costs, stated honestly so the option is not silently adopted:

- **No independent 2.4 GHz receiver during a ranging window.** Ranging is bidirectional
  (the SX1280 both TX and RX), so the link's RX role and the ranging role would contend
  for the same front end inside one chip.
- **The SX1280's sensitivity and data-rate differ from the LR2021's.** On-air behaviour
  against the existing link is not established.

This option is **not** selected here. It needs a bench measurement of SX1280 sensitivity
vs the bare LR2021's 2.4 GHz RX before it may be adopted.

---

## Open items (kept open, not resolved here)

- **The 5 V rail (ADR-029 O5).** The F33-2G4 reaches full output only at 5 V (its 2 W /
  33 dBm @433 is a 5 V figure; at 3.3 V it loses ~3.5 dB). `docs/F33-MODULE-PLAN.md`
  records three candidate chains and the 1200 mA burst / supercap question as undecided.
  This ADR does not decide the rail.
- **Legality of 2 W on 433 MHz in DE.** 433.05–434.79 MHz is licence-free only at very
  low ERP; higher power implies an amateur licence. The 2 W TX figure is a capability of
  the part, not an asserted legal operating point. Flagged, not resolved.

## Ordering trap (repeat, do not re-learn)

The LCSC/JLC listing **`LoRa1121F33-2G4-868MHz`** is a **different** module on the
LR1121 chip and must **not** be ordered. Ours is G-NiceRF **`LoRa2021F33-2G4`** on
Semtech **LR2021**. (Already recorded in ADR-029 D2; repeated here because the band
split moves the F33 to a TX-only role and the person placing the order must not grab the
LR1121 part while sourcing it.)

---

## What would falsify this

- A bench measurement showing the SX1280's 2.4 GHz RX is as sensitive as (or more
  sensitive than) the bare LR2021's **and** that the ranging window can be made long
  enough that no independent link receiver is needed — this would make D6's 3-part
  option preferable and should reopen D1.
- A regulatory determination that 2 W on 433 in DE is unavailable at the target licence
  level, which would erode the +3 dB rationale in D2 and force the TX direction back to
  a reduced-power band.

## Next-free-number check (recorded)

Run on branch `adr/radioband-tdm` (base `4059860`, tip of `pr/029-dual-band-flight-board`):

```
git ls-tree -r --name-only HEAD docs/adr          # in-tree: ... 031, 032; no 034/035
git log --all --oneline --name-only -- 'docs/adr/*'  # all branches: 033-giftwrap... present; no 034/035
```

033 is claimed on an unmerged branch; 034 and 035 are free on every branch inspected.
