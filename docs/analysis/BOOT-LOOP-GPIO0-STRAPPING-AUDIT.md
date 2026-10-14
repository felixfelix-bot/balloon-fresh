# Boot-loop triage: GPIO0 / strapping-pin audit across the balloon boards

**Date:** 2026-10-14 · **Trigger:** operator report — a board is in a **boot loop**.
**Method:** repo-wide assignment audit (`tracker/hardware/audit_gpio0_strapping.py`), then
read the records that own each assignment. **No hardware was touched.** Nothing below is
inferred from a schematic image — every claim cites a file and line.

---

## 0. The one thing that must be checked FIRST, because it decides everything

**Is the boot-looping board an ESP32-S3 / ESP32, or an ESP32-C3?**

The answer changes the diagnosis completely:

| Chip | Is GPIO0 a strapping pin? | Consequence for our designs |
|---|---|---|
| **ESP32 / ESP32-S3** | **YES** — sampled at reset; LOW ⇒ UART download mode | **A boot loop is the expected symptom** of a GPIO0 conflict |
| **ESP32-C3** | **NO** — *"GPIO0 is NOT a strapping pin on C3 (unlike ESP32/S3)"* — `docs/STATUS-balloon-pow.md:155` | A GPIO0 conflict **cannot** cause a boot loop on C3 |

**The C3's strapping pins are `GPIO2` (float), `GPIO8` (float) and `GPIO9` (weak pull-up)**
— same source, line 156. So on a C3 the audit must be re-run against **GPIO2/8/9**, not GPIO0.

**This is the first question to settle, and the board identity decides whether GPIO0 is even
a suspect.**

---

## 1. The audit result: our boards carry a REPEATED GPIO0 conflict, on the ADC side

The repo already records the same defect class at least **four separate times**, and in three
of them GPIO0 carries the **supercap voltage-divider ADC** while something else also wants it:

| Record | What it says |
|---|---|
| `docs/adr/006-supercapacitor-power.md:84` | *"ADC an GPIO0 misst Supercap-Spannung ueber Spannungsteiler (2x 1MOhm)"* — the supercap divider is on **GPIO0** |
| `docs/adr/029-dual-band-flight-board.md:544-546` | *"`SUPERCAP_ADC_CHANNEL = ADC1_CHANNEL_0` (= GPIO0) was also assigned to the GPS UART TX, so **the supercap sense and the GPS TX were the same physical pin**"* — recorded as **"a real defect in an earlier plan"** and the **V7 ADC collision** |
| `docs/PCB-LESSONS-LEARNED-2026-08-05.md:91` | **"FEM_RX moved from GPIO0 (strapping pin) to GPIO8"** — a fix already applied once |
| `docs/STATUS-balloon-pow.md:153` | **"GPIO8 has NO ADC channel (V2-ADC plan was broken, corrected to GPIO0/ADC1_CH0)"** — the *opposite* move, back onto GPIO0 |

**Note the contradiction between the last two rows.** One record moves a signal **off** GPIO0
because GPIO0 is a strapping pin; another moves an ADC **onto** GPIO0 because GPIO8 has no ADC
channel. Both are locally correct — and they are only compatible if the two boards use
**different chips** (S3 strapping vs C3 non-strapping). **Do not resolve this by picking a side;
it is a chip-identity question.**

## 2. The mechanism, if the board is an S3/ESP32 (this is the boot-loop path)

On ESP32/S3, GPIO0 is sampled at reset: **LOW ⇒ UART download/bootloader; HIGH ⇒ normal boot.**
Anything that can hold GPIO0 **LOW** at reset re-enters the bootloader **on every reset** — which
presents exactly as a boot loop. Candidates that can do this:

- a **driven** logic output (a push-pull signal actively low at power-up),
- an **NPN base / opto / relay coil** with a pull-down,
- an **external pull-down resistor**,
- **or the supercap divider itself**: a 2 × 1 MΩ divider to ground, read through a charged
  capacitor, can present a LOW at reset — which is precisely what `docs/adr/006` puts on GPIO0.

The repo documents the mechanism being noticed and mitigated before, in the same words:
*"GPIO0 ist Strapping-Pin — GPS TX ist High-Z bei Boot, kein Konflikt"*
(`docs/component-guide.md:211`, `docs/breadboard-wiring-guide.md:76`) — i.e. the existing
mitigation is **"the thing on GPIO0 is high-Z at boot"**. That mitigation is **valid only if the
attached net really is high-Z at reset.** A divider held by a charged supercap is not.

## 3. What the operator should check on the actual board (cheap, decisive)

1. **Read the reset reason from the serial log.** The ROM prints `rst:0x…` / `boot:0x…` on every
   boot. A **`boot:0x` in download/bootloader range repeating** is the signature of a GPIO0 strap
   being pulled LOW. If the log instead shows a **TG0WDT / task-watchdog reset**, it is *not* a
   strap problem and this audit is the wrong path.
2. **Yes — an opto/relay coil or a transistor base on GPIO0 can absolutely cause this**, if its
   network holds GPIO0 LOW at reset. Our own manifests place such drivers on the **`U_CUT1–4`**
   latched-cut drivers and **`U_HUB_CVT`** — and those five parts are **still `TODO(unverified)`
   with no part chosen**, so **whether they load GPIO0 is currently unknown and unverifiable from
   the repo.** That is the gap to close before blaming them. The `U_CUT*` channel assignments are
   **not** forced onto GPIO0 by any record I can find.
3. **Confirm the chip identity of the loop board** (S3 vs C3) — see §0. If it is a **C3**, stop
   looking at GPIO0 and audit **GPIO2 / GPIO8 / GPIO9** instead.

## 4. What the repo does NOT establish (stated as negatives)

- **No record ties `U_CUT*` or `U_HUB_CVT` to GPIO0.** Their channel assignment is undefined
  because the parts are undefined.
- **No serial log, reset-reason dump or strap measurement from the looping board is in the repo.**
  Every statement above is a schematic/manifest audit, not a measurement of the failing unit.
- **v9's own pin plan is clean:** `docs/adr/108-f33-sx1280-pin-plan.md:25,78-79` — *"IO45 and
  IO46 are boot strapping pins and are deliberately not assigned"*, and the explicit audit says
  **"No strapping pins are touched."** The v9 flight netlist likewise marks IO3/IO45/IO46 as
  **"boot strap: no external load"** (`build_flight_sch.py:1567-1569`). **So the v9 design is not
  the source of this class of bug** — the exposure is in the **earlier C3/V2 boards** and in the
  **base-station design that does not exist yet**.

## 5. Recommendation

1. **Identify the looping board's chip first.** It is the difference between "GPIO0 conflict" and
   "not GPIO0 at all". Do not skip this.
2. **If S3/ESP32:** capture the ROM reset-reason line, then measure GPIO0 at reset with a scope or
   DMM. A strap held LOW is the whole answer.
3. **If C3:** re-audit **GPIO2/GPIO8/GPIO9** (the C3 straps). GPIO0 is not the cause.
4. **Design rule to lock into the base station and any respin** (the operator's *"would the GPIO0
   and opto be an issue on the base station or higher voltage archetypes"*): **never place a
   supercap/voltage divider, a driven output, an opto, a relay coil, or a transistor base on a
   strapping pin.** If a divider is needed, put it on a **non-strapping ADC pin**, and if a
   driver is needed, add a **strap-safe pull-up** on the strapping pin so the reset sample is HIGH.
   ADR-008 already protects one specific instance of this (LED on a non-strapping pin) — the rule
   above is the generalisation, and it is currently **not written down anywhere as a rule.**
5. **On the base station specifically:** because that board is **not yet designed**, this is a
   zero-cost fix there. It becomes a re-spin if ignored until after routing.

## Reproduce

```
python3 tracker/hardware/audit_gpio0_strapping.py     # greps every board source in the repo
```
