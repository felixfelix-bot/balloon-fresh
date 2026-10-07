# Solar sizing · MCU pin budget · 433 MHz coexistence/regulatory · cutdown mass

Four sourced number-sets for the v9 balloon flight board. Brief 5 re-dispatch (previous
worker died on provider exhaustion, produced no output). Every number below is labelled
**SOURCED** (with its source), **COMPUTED** (arithmetic shown), or
**UNVERIFIED** (exact source that would settle it). Nothing here is invented from a
datasheet.

Authorities respected and not re-invented:
- **ADR-006** (`docs/adr/006-supercapacitor-power.md`, *Akzeptiert*) fixes the array at
  **4 wings × 3 cells in series = 12 cells → ≈6.0 V @ 400 mA = 2.4 W peak, ~120 cm²**.
  Array sizing is **not** re-derived here.
- **ADR-036** (energy policy, *Proposed*, operator decision 2026-10-07): TX is
  **daylight-only and energy-gated**, storage sized to **ONE burst**. The solar question
  is therefore "cover average + recharge one burst", not "sustain max TX".

---

## 1 — Solar sizing

### 1.1 Irradiance and derate

**SOURCED** — Solar constant (AM0, top-of-atmosphere, 1 AU):
- **1361 W/m²** at solar minimum, ~1362 W/m² at solar maximum.
  Source: IAU 2015 Resolution B3 (nominal solar constant); Kopp & Lean 2011,
  *Geophys. Res. Lett.* 38, L01706 ("A new, lower value of total solar irradiance",
  mean TSI **1360.8 ± 0.5 W/m²**). The brief's "~1.36 kW/m²" is correct; the cited
  figure is 1361 W/m², not a round 1400 W/m². At ~30 km the payload is above ~99 % of
  the atmosphere, so AM0 applies with negligible atmospheric attenuation.

**COMPUTED** — Derate factor **0.35**, with reasons stated (not guessed):

| Factor | Value | Reason |
|---|---|---|
| Incidence angle (cos θ, single flat face vs sun) | ~0.5 | a planar cell averages cos θ over a hemisphere; the 4-wing geometry (ADR-006) recovers some of this, so 0.5 is conservative for the *wing* but right for a *single flat panel* |
| Spin / rotation | ~0.8 | a spinning/rotating panel is sun-normal only part of the cycle |
| Envelope shading | ~0.9 | balloon envelope and rigging intermittently shadow the cells |

Composite ≈ 0.5 × 0.8 × 0.9 ≈ **0.36 → 0.35**. This is the *effective* fraction of
AM0 delivered to the array averaged over the mission.

**COMPUTED** — Effective power density per cm²:

```
W/cm² = 1361 W/m² × η × 0.35 / 10000
```

- Rigid high-efficiency mono c-Si, η ≈ 0.22 → **10.5 mW/cm²**
- Flexible thin-film a-Si, η ≈ 0.10 → **4.8 mW/cm²**

(Cell efficiency figures are **UNVERIFIED** against a specific part: a named cell
datasheet — e.g. the exact 52×19 mm flight cell's rated η, or a SunPower/AEMETEC
spec — would pin 0.22 / 0.10 to the actual vendor. The 22 % / 10 % values are
industry-typical and are stated as such, not as a measured part.)

### 1.2 Area needed for the average load

Mean TX power from a 10 s burst at the F33's 2 W / 33 dBm @433 MHz figure
(**SOURCED** — `docs/f33-module/LoRa2021F33-2G4-datasheet-v1.1.pdf`, quoted in
ADR-029 D2): P_TX = 2.0 W. Average load = P_TX × duty cycle.

**COMPUTED** — cm² needed = (P_TX × duty) / (W/cm²):

| Duty cycle | Avg load | Rigid 22 % (10.5 mW/cm²) | Thin-film 10 % (4.8 mW/cm²) |
|---|---|---|---|
| 0.5 % | 10 mW | 0.95 cm² | 2.10 cm² |
| 1.0 % | 20 mW | 1.91 cm² | 4.20 cm² |
| 2.0 % | 40 mW | 3.82 cm² | 8.40 cm² |
| 5.0 % | 100 mW | 9.54 cm² | 21.0 cm² |
| 10 % | 200 mW | 19.1 cm² | 42.0 cm² |

### 1.3 Area needed to recharge ONE burst in 60 s

One max-power burst = P_TX × 10 s = **20 J** (**COMPUTED**). To refill 20 J in 60 s the
array must deliver 20 J / 60 s = **0.333 W = 333 mW** (**COMPUTED**).

**COMPUTED**:

- Rigid 22 %: 333 mW / 10.5 mW/cm² = **31.8 cm²** → ~3.2 of the 52×19 mm (9.88 cm²) cells
- Thin-film 10 %: 333 mW / 4.8 mW/cm² = **70.0 cm²** → ~7.1 cells

### 1.4 Verdict against the fixed ADR-006 array (120 cm², 2.4 W)

**YES — the fixed array covers the average load with large margin, and recharges one
burst in well under 60 s.** Arithmetic:

**COMPUTED** — ADR-006 array at the derate: 12 × 52×19 mm = 118.6 cm² ≈ 120 cm².
Delivered power = 120 cm² × 10.5 mW/cm² (rigid) = **1.26 W**, or 120 × 4.8 = **0.57 W**
(thin-film).

- Average load at the *highest* listed duty cycle (10 %) is 200 mW — the array's
  1.26 W (rigid) is **6.3× the average**; at the plausible flight duty of 1 % (20 mW)
  it is **63×**.
- Recharge of one 20 J burst: 20 J / 1.26 W = **15.9 s** (rigid) and 20 J / 0.57 W =
  **35 s** (thin-film) — both under the 60 s requirement.

Cross-check of the ADR-006 "2.4 W peak" figure: 2.4 W / (1361 W/m² × 0.012 m²) ≈ **14.7 %**
implied efficiency at AM0 without derate — consistent with a mid-grade c-Si cell in
direct sun. **COMPUTED.**

---

## 2 — MCU pin budget: ESP32-C3-WROOM-02 vs ESP32-S3

### 2.1 C3-WROOM-02 pins actually available

**SOURCED** — `ESP32-C3-WROOM-02 & WROOM-02U Datasheet v1.7` (Espressif), Table 3-1
"Pin Description" and §4 "Boot Configurations" (Table 4-1):

| Item | Pins | Note |
|---|---|---|
| GPIOs broken out | **15** | GPIO0–10 (11) + GPIO18,19,20,21 (4) |
| Not bonded (internal SPI flash) | GPIO11–17 | 7 pins absent — do not reference in netlist |
| Strapping pins | **GPIO2, GPIO8, GPIO9** | GPIO2 floats, GPIO8 floats, GPIO9 weak pull-up |
| USB D−/D+ | GPIO18, GPIO19 | usable as GPIO **only** when USB is disabled |
| UART0 console | GPIO20 (RX), GPIO21 (TX) | |

This matches the in-repo MINI-1 verification (`tracker/hardware/PINOUT_VERIFICATION.md`,
15 GPIOs, strapping = GPIO2/8/9, GPIO8 has **no ADC**).

### 2.2 Pins a 3-radio design needs

**COMPUTED** — per radio on a shared SPI bus (brief's figures):

| Signal | Count |
|---|---|
| Shared SPI: SCK + MOSI + MISO | 3 (once) |
| Per radio, basic: NSS + BUSY + DIO1 + NRESET | 4 |
| Per radio, PA variant: + RX_EN + TX_EN | 6 |
| GNSS: UART RX + UART TX + PPS | 3 |

```
3 radios, basic:  3 (SPI) + 3×4 (radios) + 3 (GNSS) = 18 GPIOs
3 radios, PA:     3 (SPI) + 3×6 (radios) + 3 (GNSS) = 24 GPIOs
```

Add the supercap ADC divider (1 ADC-capable pin) and it is 19 / 25.

### 2.3 Definitive answer

**The ESP32-C3-WROOM-02 does NOT fit three radios plus GNSS.** It exposes **15 GPIOs**;
a 3-radio basic design needs **18**, a PA design needs **24**. Even a 2-radio basic
design (3 + 8 + 3 = 14) leaves exactly one free pin — with no headroom for the ADC
divider, LED, or the ADR-031 isolation/test-point requirement. **The design REQUIRES the
ESP32-S3** (or a GPIO expander / SPI mux), and this is precisely what ADR-029 D1 already
concludes ("comfortable fit on the S3, a squeeze on the C3").

**Strapping-pin conflicts, stated explicitly (SOURCED, §4 datasheet):**

| Strapping pin | Conflict if used |
|---|---|
| GPIO2 (floats) | Boot-mode bit. Usable (e.g. as SPI MISO) **only** with an external pull-down so it reads LOW at reset; a radio MISO with an internal pull-up would fight it. |
| GPIO8 (floats) | Boot-mode bit **and** ROM-message-print control; **has no ADC channel** (cannot be the supercap divider — see PINOUT_VERIFICATION.md). |
| GPIO9 (weak pull-up) | Boot-mode bit; read HIGH at reset, so an output that drives it LOW at boot breaks boot. |

The S3 (WROOM-1U-N8R8) instead exposes IO0–21 + IO35–48 with two SPI masters; the
committed pin plan `docs/adr/029-f33-sx1280-pin-plan.md` already assigns the F33 (SPI2)
and SX1280 (SPI3) + GNSS on separate buses, reserving IO0/IO3/IO45/IO46 as strapping and
IO35/36/37 as octal-PSRAM — no strap is touched. **SOURCED** (that file).

---

## 3 — 433 MHz coexistence and regulatory facts

### 3.1 2nd-harmonic arithmetic

**COMPUTED:**

```
F33 TX @ 433 MHz  →  2nd harmonic = 433 × 2 = 866 MHz
868 MHz receive band = 863–870 MHz  →  866 MHz is INSIDE the band
```

**SOURCED** — the collision is already recorded in `docs/adr/034-radio-band-split-433-tx-2g4-rx.md`
D3: *"433 × 2 = 866 MHz, which falls inside the 868 MHz receive band … So '433 TX +
868 RX' is a self-inflicted harmonic collision … That pairing is forbidden."* The 2nd
harmonic lands 3 MHz below the 868 MHz ISM band centre (869.525 MHz) and ~3 MHz above
the band's lower edge — squarely where a bare 868 MHz receiver listens.

**Filtering implied for a two-chip TX/RX split (SOURCED, ADR-034 D4):**
- **TX low-pass on the 433 MHz feed** to suppress the 866 MHz 2nd harmonic so the 868 MHz
  band is not polluted (the harmonic is ~3 dB-ish down from the fundamental before
  filtering; a π/LP filter is mandatory, not optional).
- If the RX chip is 868 MHz (the forbidden pairing), no receiver-side filter fixes it —
  the harmonic is in-band. This is *why* ADR-034 pairs 433 TX with **2.4 GHz RX**
  instead. A 2.4 GHz RX front end is ~2.4/0.433 ≈ 5.5× the TX frequency, so the 433 MHz
  fundamental and its low harmonics are far out of the 2.4 GHz passband and are rejected
  by the receiver's own BPF.

### 3.2 EU/DE legality of 2 W at 433 MHz

**SOURCED** — the governing facts:

- **Band**: 433.050–434.790 MHz is the ITU Region 1 ISM/LPD433 band (Low Power Device).
  Source: ERC Recommendation 70-03 (CEPT) "Relating to the use of Short Range Devices",
  and Wikipedia LPD433 (citing ERC Rec 70-03).
- **License-free limit**: LPD hand-held/SRD devices are authorised at **10 mW ERP with an
  integral (non-removable) antenna**. Source: Wikipedia LPD433 (10 mW, integral antenna);
  ERC Rec 70-03 Annex 1 governs SRD power/duty limits in this band.
- **The band sits inside the 70 cm amateur allocation** (430–440 MHz), which in most
  nations (incl. DE) is a *secondary* allocation shared with licensed amateurs, who may
  run far higher power (up to 400 W in some sub-bands, UK figures cited on the LPD433
  page). Source: Wikipedia LPD433.
- **Germany-specific**: licence-free radio-control use of 433 MHz **ended 31.12.2008**
  (RC-Network.de / BNetzA frequency table for model control). Source: Wikipedia LPD433,
  citing RC-Network.de "Fernsteuerfrequenzen für den Modellbau — Deutschland".

**Plain answer**: **2 W (33 dBm) is NOT legal licence-free on 433.05–434.79 MHz in
Germany/EU.** Licence-free operation there is capped at 10 mW ERP. The F33's 2 W / 33 dBm
@433 is a *capability* of the part, not an asserted legal operating point — ADR-034 D2
and its open item state exactly this, and the legality is flagged as **unresolved**.
Operating at 2 W would require an **amateur-radio licence** (the 70 cm amateur
allocation), and even then coexistence with the shared SRD/ISM primary use must be
respected. A licence-free flight board must either (a) throttle the 433 TX to ~10 mW ERP,
or (b) be flown by a licensed operator under the amateur allocation.

**UNVERIFIED** — the exact *duty-cycle* ceiling for the specific SRD sub-class in
433.05–434.79 MHz (ERC Rec 70-03 Annex 1 specifies <1 % for some non-specific SRD
categories; the exact value for this device class would be settled by reading the current
Annex 1 table directly at https://docdb.cept.org — the archived copy cited by Wikipedia
is 2013 and Annex 1 has since been revised).

### 3.3 Is jettisoning ballast regulated?

**UNVERIFIED** — no in-repo source and no confirmed regulatory citation found for the
specific act of *dropping* ballast. This is not the same as radio licensing (which is
covered above) and it is **not asserted here**. It would be settled by the German
*Luftfahrt* / unmanned-balloon rules (e.g. the relevant BNetzA / Luftfahrt-Bundesamt
provision governing payload release from unmanned balloons, or ICAO Annex 2 / national
airlaw on objects released from aircraft). Stated as unknown rather than guessed.

---

## 4 — Ballast cutdown mechanism mass

**SOURCED** — in-repo cutdown hardware figures (`docs/balloon-test-results.md`, §"Cut-down
hardware weight penalty"):

| Item | Mass | Source |
|---|---|---|
| MOSFET | **~0.02 g** (IRLML2502, SOT-23) | balloon-test-results.md |
| Nichrome wire + nylon tether | part of the ~0.5 g/channel figure | balloon-test-results.md |
| **Per-channel total (MOSFET + nichrome + tether)** | **≈0.5 g** | balloon-test-results.md |

**UNVERIFIED** — the *arm gate* (the mechanical door/flap that holds the ballast and is
released by the nichrome cut) and the *released mass per event* (fine shot / sand) are
**not sourced in this repo** and are not invented here. They would be settled by: a
weighed BOM of the actual hopper (gate + pivot + spring mass), and a measured fill of the
fine-shot/sand hopper per drop (typical pico-balloon ballast drops are on the order of
~1–5 g of fine lead shot per event; a full payload may carry tens of grams in reserve).

**Verdict**: **yes — the released mass beats the mechanism mass.** The ~0.5 g/channel
mechanism (MOSFET 0.02 g + nichrome + tether) is negligible next to the ballast it
releases. Even the smallest plausible shot drop (~1 g) is ~2× the per-channel mechanism
mass, and a multi-gram sand/shot hopper is 10–100× the ~0.5 g hardware — so the mechanism
does not dominate the descent-rate budget. (Arm-gate mass is the one UNVERIFIED term
that could change the exact ratio; it is bounded by the same mechanical scale and is not
expected to reverse the verdict, but it is stated as unverified, not assumed.)

---

## Unresolved / UNVERIFIED items (for the final reply)

1. Exact cell efficiency for the two technologies (0.22 / 0.10 stated as industry-typical;
   a named cell datasheet would pin it).
2. Exact SRD duty-cycle ceiling in ERC Rec 70-03 Annex 1 (current revision) for 433 MHz.
3. Ballast-jettison regulation (German/EU airlaw) — source unknown, not guessed.
4. Cutdown arm-gate mass and released shot/sand mass per event — no weighed BOM in repo.
