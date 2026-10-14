# MCU & pin-plane index — READ THIS BEFORE touching any GPIO

**Purpose:** one page that makes the **chip-identity** and **pin-plane** facts
unmistakable, so the C3-vs-S3 confusion recorded on 2026-10-14 cannot recur.
**Established:** 2026-10-14, after a boot-loop report exposed a contradiction that
had been sitting in the repo unresolved.

---

## 1. THE RULE, FIRST

> **v9 FLIGHT BOARDS ARE ESP32-S3.** v8x and older, and the *bench* boards, are
> **ESP32-C3**. **The strapping pins are DIFFERENT between them**, so a GPIO finding
> from one chip **does not transfer** to the other.

If you are about to reason about a strapping pin, a boot loop, or an ADC pin, **stop
and confirm which chip the board in front of you carries.**

## 2. The pin-plane table — the single place both chips live

| | **ESP32-S3** (v9 flight) | **ESP32-C3** (v8x, bench) |
|---|---|---|
| **Strapping pins** | **IO0, IO3, IO45, IO46** | **GPIO2, GPIO8, GPIO9** |
| Is GPIO0 a strap? | **YES** — LOW ⇒ UART download ⇒ **boot loop** | **NO** — safe for ADC/GPIO |
| PSRAM | **8 MB** (`-N8R8`); IO35/36/37 become octal-PSRAM, **not GPIO** | **none** (512 KB SRAM) |
| Usable general SPI masters | **2** (SPI2/SPI3) | **1** |
| ADC1 channels | **GPIO1–GPIO10** | GPIO0–GPIO4 |
| ADC2 | GPIO11–GPIO20; unusable with Wi-Fi/BT (never enabled, ADR-038) | GPIO5 |
| Native JTAG | IO39–IO42 (spent on SX1280 → **USB-Serial-JTAG is the debug path**) | — |
| Authority | **ADR-029 D1**, re-verified by **ADR-069**; pin plan **ADR-108** | ADR-028, ADR-001 |

## 3. The defect this index exists to prevent (recorded, not hidden)

Two committed records appeared to contradict each other:

| Record | Claim | True for |
|---|---|---|
| `docs/STATUS-balloon-pow.md:155` | *"GPIO0 is NOT a strapping pin on C3 (unlike ESP32/S3) — safe for ADC/GPIO"* | **C3** |
| `docs/PCB-LESSONS-LEARNED-2026-08-05.md:91` | *"FEM_RX moved from GPIO0 (strapping pin) to GPIO8"* | **S3-class** |

**Both were correct. Neither named its chip.** The repo's own rule (AGENTS.md) calls a
contradiction that names no winner a **DEFECT** — so it was one, and this page is the
fix.

**The real history, now legible:** the supercap voltage divider was specified on
**GPIO0** in ADR-006, in the **C3** era, where GPIO0 is **not** a strap and was
therefore legitimate. On the **S3**, IO0 **is** a strap — so the same divider would
**hold the chip in the bootloader**. ADR-029 §4 recorded the symptom as the
*"V7 ADC collision"* (the supercap sense and the GPS TX on the same physical pin) but
**never recorded the chip-identity reason**, which is why the contradiction survived.

**Therefore:** the V7 collision was a **real defect**, harmless on the C3 and a
**boot-loop generator the moment the part changed to the S3**. Same divider, same pin
number, opposite consequence.

## 4. The design rule (binding, all boards)

> **Never place a supercap / voltage divider, a driven logic output, an opto, a relay
> coil, or a transistor base on a strapping pin.**
>
> **Divider** → an ADC-capable **non-strap** pin.
> **Driver** → add a **strap-safe pull-up** so the reset sample is at the required level.
>
> Applies to **every** board: v9 hub, wing, pre-stretch, and **the base station**
> (not yet designed → zero cost to obey now, a re-spin to discover later).

ADR-008 previously protected **one instance** of this (an LED on a non-strapping pin).
This is the generalisation, and it is now recorded rather than rediscovered.

## 5. Live pin resource — the thing that actually bites

**On v9 there is NO free ADC-capable pin.** ADC1 is GPIO1–GPIO10 and **all ten are
spent**; 11–20 have no ADC and are spent; the 13 free pins (**IO22–IO34**) are
**digital-only**. See **`docs/analysis/ADC-PIN-RESOLUTION-OPEN17-OPEN25.md`**
(reproduce: `python3 tracker/hardware/solve_open25_pin.py`).

**`OPEN-17` (rail-monitor ADC channel) and `OPEN-25` (cut-sense ADC) are ONE item** —
they compete for the last ADC input on the board. `OPEN-17` and `OPEN-25` should be
closed together or not at all.

## 6. Cross-reference map (every record that touches this)

| Record | What it owns |
|---|---|
| **ADR-069** | MCU = S3 confirmed; the C3/S3 strap contradiction **RESOLVED**; the strap design rule |
| **ADR-029 D1 / §4** | the S3 choice; forecloses GPIO0 for the divider; the V7 ADC collision |
| **ADR-108** | the v9 pin plan; the explicit strapping audit (*"No strapping pins are touched"*); `OPEN-25` |
| **ADR-047 §6** | spends IO13 on `F33_VSENSE`; `OPEN-17` |
| **ADR-051 §2.6** | the cut-sense provision; the one-GPIO + mux/ladder shape |
| **ADR-006** | the supercap divider on GPIO0 — **C3 era**, legitimate then |
| **ADR-008** | the one pre-existing instance of the strap rule (LED) |
| **`docs/analysis/BOOT-LOOP-GPIO0-STRAPPING-AUDIT.md`** | the boot-loop triage + reproduce tool |
| **`docs/analysis/ADC-PIN-RESOLUTION-OPEN17-OPEN25.md`** | the ADC arithmetic and recommendation |
| **`tracker/hardware/audit_gpio0_strapping.py`** | greps every board for strap pins |
| **`tracker/hardware/solve_open25_pin.py`** | computes the free / ADC-capable pin sets |
| `docs/STATUS-balloon-pow.md:153-156` | the **C3** strap facts (unchanged, correct) |
| `docs/PCB-LESSONS-LEARNED-2026-08-05.md:91` | the **S3** GPIO0 fix (unchanged, correct) |

**Both of the last two are correct.** Neither is superseded. **They simply describe
different chips** — which this page now states in the one place both are visible.
