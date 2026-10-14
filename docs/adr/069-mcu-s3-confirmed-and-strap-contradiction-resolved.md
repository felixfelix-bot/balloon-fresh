# ADR-069 — MCU: ESP32-S3-WROOM-1U is CONFIRMED, and the C3/S3 strapping contradiction is resolved

> Numbered **069** on 2026-10-14 by `scripts/adr_next_number.py`.
> The allocator's failure path was checked in the same run: the number is not
> hard-coded past this allocation and no file is renamed.

- Status: **Proposed** — direction is the operator's, given 2026-10-14:
  *"Personally I would prefer S3 if possible."* The text is not human-accepted.
- Date: 2026-10-14
- Decision owner: Felix (operator).
- Author: subagent (Hermes), worktree `~/worktrees/v9-route`.
- Confirms: **ADR-029 D1** (the ESP32-S3-WROOM-1U-N8R8 choice — this record
  re-verifies it on new grounds and does **not** supersede it).
- Resolves: the **C3/S3 strapping contradiction** flagged in
  `docs/analysis/BOOT-LOOP-GPIO0-STRAPPING-AUDIT.md` §1 — a
  *"contradiction that names no winner"* per the repo's own defect class.
- Related: ADR-028/ADR-001 (C3 as *bench* MCU), ADR-108 (S3 pin plan + strapping
  audit), ADR-047 (power), ADR-006 (supercap divider), ADR-008 (LED pin).

---

## 0. The decision

**The S3 is correct and is confirmed. No change is needed to ADR-029 D1.** The
operator's preference matches the record. The "upgrade" introduces **no new
problem class** — it introduces **four strap pins that must be left unloaded**,
and ADR-108 **already leaves all four unloaded**. The C3's apparent advantage on
this point is real but is **not a reason to go back**: the C3 cannot carry v9 at
all.

## 1. Resolving the contradiction (the defect, fixed rather than sided)

> **SEE ALSO `docs/CHIP-AND-PIN-PLANE-INDEX.md`** — the one-page index that makes
> this unmistakable and maps every record that touches it. **Both of the records
> below are correct; neither is superseded.** Each now carries a **CHIP SCOPE**
> banner so it cannot be read out of context again.

The two records appeared to disagree:

| Record | Says | True for |
|---|---|---|
| `docs/STATUS-balloon-pow.md:155` | *"GPIO0 is NOT a strapping pin on C3 (unlike ESP32/S3) — safe for ADC/GPIO"* | **C3** |
| `docs/PCB-LESSONS-LEARNED-2026-08-05.md:91` | *"FEM_RX moved from GPIO0 (strapping pin) to GPIO8"* | **the S3-class board it was fixing** |

**Both are correct. They are not in conflict.** The resolution is that they describe
**different chips**, and the repo had simply not written that down in one place:

- **ESP32-C3 straps:** `GPIO2` (float), `GPIO8` (float), `GPIO9` (weak pull-up).
  **GPIO0 is not a strap** → the C3/V2-ADC design that put the supercap divider on
  GPIO0 (`docs/STATUS-balloon-pow.md:153`) was **legitimate on the C3**.
- **ESP32-S3 straps:** `IO0`, `IO3`, `IO45`, `IO46` (ADR-108). → the same divider
  planted on an S3's IO0 would **hold the chip in the bootloader**.

So the "V7 ADC collision" in ADR-029 §4 was a **real defect**, not a style point:
a supercap divider on a **strap** pin. On the C3 it was harmless; the moment the
part changed to the S3 it became a **boot-loop generator**. That is the actual
lesson, and it is why this record exists.

## 2. Why the S3, on hard grounds (not preference)

ADR-029 D1 already reasoned this; verified again here:

1. **Pin budget — decisive.** v9 needs **two independent SPI masters** (F33 on
   SPI2, SX1280 on SPI3) plus GNSS UART, I²C, USB-Serial-JTAG and sense lines.
   ADR-029 DR1: the C3 has **one usable general SPI master**, so a peripheral must
   **share** the radio's bus. ADR-029's own summary: the S3 is required because
   *"an ESP32-C3 could not carry it."*
2. **PSRAM / flight log.** v9 uses `-N8R8` = **8 MB PSRAM**. The **C3 has 512 KB
   SRAM and no PSRAM** — *"no flight log"* (ADR-029 §4). For a balloon that must
   store telemetry across a multi-day flight and radio-dark periods, that is
   disqualifying on its own.
3. **GPIO count for the isolation/test-point requirement** (ADR-031): met on the
   S3, *"cannot be met with margin"* on the C3.
4. **CPU headroom:** dual-core S3 vs single-core RISC-V, and the F33's GNSS/serial
   work is bursty.

**The C3 keeps its real role: the bench MCU** (ADR-028, ADR-001). That is
unchanged — the SuperMini C3 is the cheap bench/LR2021 board, and the bring-up
bug list (`docs/esp32c3-supermini-bringup.md`) exists precisely because it is the
bench part. **Do not unify them;** the split is deliberate and correct.

## 3. Does the upgrade introduce problems? What are they, and how to work around them

**Four problems, all four already worked around in ADR-108 — except one that ADR-108
does not close.**

| # | Problem | Status |
|---|---|---|
| 1 | **IO0 / IO3 / IO45 / IO46 are straps.** Anything holding one LOW (or the wrong level) at reset changes the boot path. | **HANDLED.** ADR-108's explicit audit: *"No strapping pins are touched."* The v9 netlist marks all three of IO3/IO45/IO46 *"boot strap: no external load"*. |
| 2 | **IO35/IO36/IO37 are octal-PSRAM, not GPIO** on `-N8R8`. | **HANDLED.** ADR-108 forbids the old IO35/36/37 SPI1 proposal. |
| 3 | **IO39–IO42 are native JTAG** (MTCK/MTDO/MTDI/MTMS) and the plan spends them on SX1280. | **ACCEPTED TRADE-OFF**, explicit: the plan *"requires USB-Serial-JTAG (IO19/IO20) or an external debug strategy"*. Recovery is USB-JTAG, which works. |
| 4 | **The supercap ADC divider has no assigned pin on v9** — ADR-029 §4 forecloses GPIO0, and ADR-108's budget is fully spent. | **NOT CLOSED.** `OPEN-25` / `OPEN-14` remain open. |

**Work-around for #4 (the one that matters):** ADR-029 §4 already fixes the shape —
*"any reassignment must leave an ADC pin for the supercap divider"* — and the S3's
**ADC1 channels are GPIO1–GPIO10**. Note GPIO1/GPIO2 are spent on I²C and GPIO4–10
on the F33 bus, so the divider must take **an ADC-capable pin that is not a strap**,
with IO0/IO3/IO45/IO46 unconditionally excluded. **The strap-safe rule (below)
makes this mechanical rather than a judgment call.**

**And a second, cheaper work-around for both #1 and #4**, which is the real
engineering answer: **do not put a divider on a strap pin even when the chip allows
it.** Use a **strap-safe pull-up** on any strap that must carry a signal, and keep
dividers on non-strap ADC pins. ADR-008 already protects one instance of this (an
LED on a non-strapping pin); this generalises it.

## 4. Design rule this record establishes (currently written down nowhere)

> **Never place a supercap/voltage divider, a driven logic output, an opto, a relay
> coil, or a transistor base on a strapping pin.**
> Divider → a non-strap ADC-capable pin. Driver → add a strap-safe pull-up so the
> reset sample is at the required level. Applies to **every** board: S3, C3, hub,
> wing, pre-stretch, **and the base station** (not yet designed → zero cost to obey;
> a re-spin to discover).

## 5. What would falsify this

- A pin-budget audit showing the C3 can carry two independent SPI masters plus UART
  plus I²C plus sensing **with margin** — it cannot today (ADR-029 §4).
- 8 MB PSRAM turning out to be unnecessary for the flight log.
- The operator deciding the C3's smaller size/mass outweighs the flight log and the
  second bus. **That is a legitimate reversal and this record does not prevent it** —
  but it should be made explicitly, not by drift.
