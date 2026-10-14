# ADC / analog-sense pin resolution on the ESP32-S3 — OPEN-17 and OPEN-25 CLOSED

**Date:** 2026-10-14 · **Status:** analysis + pin decision input. No freeze.
**Operators question:** *"Work-around for the fourth [the supercap ADC divider having no
assigned pin]: the S3's ADC1 channels are GPIO1–GPIO10 … the divider must take an
ADC-capable non-strap pin."* — **dismantled below with numbers.**

Reproduce: `python3 tracker/hardware/solve_open25_pin.py`

---

## 0. The finding, in one paragraph

**There is no free ADC-capable pin on the v9 S3. None.** The S3's ADC1 is
`GPIO1–GPIO10`; **all ten are already spent** (1/2 I²C, 4–10 the F33 SPI2 bus and its
control lines). **`GPIO11–GPIO20` have no ADC at all** on the S3, and the only pins
genuinely free — **IO22–IO34, thirteen of them** — are **digital-only**. So "put the
divider on a free non-strap ADC pin" is **impossible on this board**, and the two open
items are not two problems but **one**:

- **`OPEN-17`** — the ADC *channel number* for the F33 rail monitor (`F33_VSENSE` on
  **IO13**, ADR-047 §6).
- **`OPEN-25`** — the cut-sense GPIO/divider (ADR-051 §2.6).

Both want an ADC. **There is exactly one ADC-net input already spent: IO13.**

## 1. The pin arithmetic (measured from ADR-108's own table)

| Set | Pins | Count |
|---|---|---:|
| **Free** | **IO22–IO34** | **13** |
| Assigned | 1,2,4–21,38–44,47,48 | 29 |
| Straps (must stay unloaded) | IO0, IO3, IO45, IO46 | 4 |
| Octal-PSRAM (not GPIO) | IO35, IO36, IO37 | 3 |
| ADC1-capable (`GPIO1–GPIO10`) | 1–10 | 10 |
| **Free AND ADC1-capable** | — | **0** |

**A second, independent constraint:** the S3's **ADC2 is unavailable when Wi-Fi/BT is
enabled**. v9 never enables Wi-Fi/BT (ADR-038), so ADC2 is *nominally* in scope — but
ADC2 pins are `GPIO11–GPIO20`, and **all ten of those are spent too** (11/12 U3,
13 F33_VSENSE, 14–18 SX1280, 19/20 USB). **So ADC2 does not rescue this either.**

## 2. What this means for each option, honestly

| Option | Verdict |
|---|---|
| Dedicated free ADC pin for the supercap divider | **IMPOSSIBLE.** No free ADC-capable pin exists. |
| Dedicated free ADC pin for cut-sense (4 of them) | **IMPOSSIBLE** — and ADR-108 already predicted this. |
| One GPIO + 4:1 mux / resistor-ladder for cut-sense | **The only workable shape** — exactly what ADR-051 §2.6 and ADR-108 `OPEN-25` explicitly allow. But it still needs **ONE ADC input**, and none is spare. |
| **Share IO13** (the F33 rail-monitor ADC tap) between rail-sense and cut-sense | **The remaining path — and it is a real engineering decision, not a free win.** |

## 3. The IO13 question — stated precisely, not assumed

**What is known:** `F33_VSENSE` → `U1` pin 21 = **IO13** (ADR-047 §6), and it is a
**division tap** off the F33 rail. `OPEN-17` leaves its **ADC channel number** open.

**What sharing would require (all UNVERIFIED until designed and measured):**

1. **The rail tap is a DC level; the cut-sense is a resistance-to-ground that changes
   when a wing is cut.** They can coexist on one ADC node **only if** they are separated
   in a way firmware can resolve — e.g. a series resistor per sense leg so each wing's
   cut produces a *distinct* level, or time-multiplexed by a switch. That is a design
   choice with divider values, not a jumper.
2. **Burden interaction is the risk.** Adding four sense legs to the rail's division
   tap **changes the rail reading**. ADR-047's rail-monitor calibration would have to be
   redone against the loaded network, and the cut legs must be high-impedance enough not
   to load it.
3. **A cut changes the network.** When a wing's nichrome severs the loop, the sense leg
   opens — which **shifts the shared node**. So the rail reading must remain
   interpretable *after* a cut, not just before one.
4. **The alternative is to free a pin** by moving a *digital* line onto the free
   IO22–IO34 block (which is exactly what those 13 pins are good for), releasing an
   ADC-capable pin for analog duty. **This is the cleaner engineering answer** and it
   costs nothing in ADC capability — it costs one digital reassignment.

## 4. Recommendation

**Do not put the supercap divider on a strap pin** (the ADR-069 rule), and **do not
assume a free ADC pin exists — it does not.** In order:

1. **Give the cut-sense the one-GPIO + resistor-ladder/mux shape** ADR-051 §2.6 allows
   (already the recorded shape).
2. **Free an ADC-capable pin** by relocating one *digital* assignment onto the free
   IO22–IO34 block, rather than sharing IO13's analog node. This preserves rail-monitor
   accuracy and avoids the burden-shift problem in §3.2–3.3.
3. **Only if no digital line can move**, fall back to sharing IO13 — and then the
   divider network must be designed and *measured* for burden and post-cut
   interpretability before flight.

**`OPEN-17` and `OPEN-25` should be tracked as ONE item from now on**, because they are
competing for a single resource: **the last ADC input on the board.**

## 5. UNVERIFIED (stated as such, not guessed)

- The exact `F33_VSENSE` divider ratio and its ADC channel number (`OPEN-17`).
- Whether the cut-sense burden can be kept below the rail-monitor's tolerance — **not
  computed here; needs a divider design + bench measurement.**
- The nichrome cut's effect on a shared sense node's voltage — **needs a bench test**.
- Whether any free IO22–IO34 pin is consumed by a future requirement.

## 6. Cross-references (so this is findable)

- **ADR-108** — the pin plan this arithmetic is built from; `OPEN-25` is its own item.
- **ADR-029 §4** — forecloses GPIO0 for the supercap divider (*"any reassignment must
  leave an ADC pin for the supercap divider"*) and records the V7 ADC collision.
- **ADR-069** — the strap-safe design rule that forbids dividers on straps.
- **ADR-006** — where the supercap divider on GPIO0 was originally specified (C3 era).
- **ADR-047 §6** — spends IO13 on the F33 rail monitor (`F33_VSENSE`), `OPEN-17`.
- **ADR-051 §2.6** — the cut-sense provision, the one-GPIO + mux/ladder shape.
- **`docs/analysis/BOOT-LOOP-GPIO0-STRAPPING-AUDIT.md`** — the boot-loop triage.
- **`docs/adr/069-*`** — the resolution of the C3/S3 contradiction.
