# ADR-038 — v9 ESP32-S3: Wi-Fi/BT is never enabled, external antenna path left unpopulated

- Status: **Proposed** — the *design direction* this ADR records was ratified by the
  operator on 2026-10-07 (question below, answered); the *text* has not been accepted by
  a human, so it does not say Accepted.
- Date: 2026-10-07
- Decision owner: Felix (operator)
- Author: worker (Hermes agent), answering the operator's 2026-10-07 question and
  promoting the answer into a decision record.
- Related: ADR-029 (`docs/adr/029-dual-band-flight-board.md`, the v9 board record — this
  ADR amends its config/telemetry row), ADR-034 (radio band split, the separate 2.4 GHz
  receiver this ADR confirms stands), ADR-035 (TDM schedule, the `WIFI_2G4` slot this ADR
  retires), ADR-037 (in flight, records v9 = ESP32-S3 — do not duplicate).
- Related artefacts in this repo: `tracker/firmware/sdkconfig.defaults.esp32s3`
  (`CONFIG_ESP_WIFI_ENABLED=n`, `CONFIG_ESP_BT_ENABLED=n` — the in-repo S3 defaults
  already compile the stacks out), `docs/COEXISTENCE-V9.md` (the source memo ADR-029
  promotes).

> Numbering note: 038 is the next free number. 036 is claimed by
> `docs/adr/036-energy-policy-burst-storage-daylight-only-tx.md` (branch
> `adr/energy-policy`, commit `b304efd`), and 037 is being written concurrently by
> another worker. No `038-*` file exists on any branch inspected (see "Next-free-number
> check" below).

---

## Context

**Operator decision, 2026-10-07 (verbatim):**

> "can we leave out the esp32's wifi and bluetooth to save power and weight?"

The honest answer is recorded here, including the parts where the saving is smaller than
the operator hoped. The decision is: **the v9 ESP32-S3's Wi-Fi/BT is never enabled, and
its external antenna path is not populated.** This ADR also states plainly what that
*cannot* buy.

---

## Decision

### D1 — Never enable the Wi-Fi/BT PHY; leave the external antenna path unpopulated

**The PHY is on-die and cannot be left out.** The ESP32-S3 is not a radio-plus-host
assembly with a removable Wi-Fi/BT block; the radio is part of the SoC, and the
`ESP32-S3-WROOM-1`/`-1U` modules are built around that SoC. "Leaving it out" therefore
means exactly three things, none of which is a BOM removal of the radio:

1. **Never initialise the PHY** — no `esp_wifi_init()`, no `esp_bt_controller_init()`.
2. **Do not compile in the stacks** — the in-repo S3 defaults already do this
   (`tracker/firmware/sdkconfig.defaults.esp32s3`:
   `CONFIG_ESP_WIFI_ENABLED=n`, `CONFIG_ESP_BT_ENABLED=n`).
3. **Do not populate the external antenna path** — the `-1U` U.FL connector is left
   unpopulated, and no pigtail or antenna is fitted.

*Provenance (external datasheet, not committed in this repo — no ESP32-S3 datasheet is
committed here, matching ADR-029 D1.1's treatment of external S3 claims):*

- **ESP32-S3 Series Datasheet v2.2**, §1 (overview): *"ESP32-S3 is a low-power MCU-based
  system on a chip (SoC) with integrated 2.4 GHz Wi-Fi and Bluetooth® 5 (LE)."* The radio
  is integrated, on the die, not a daughter block.
- **ESP32-S3-WROOM-1 & WROOM-1U Datasheet v1.8**, §1.2: both modules are *"generic Wi-Fi +
  Bluetooth LE MCU modules that are built around the ESP32-S3 series of SoCs."* The
  variant tables 1-1 and 1-2 list flash/PSRAM combinations only — **every** listed
  variant is a Wi-Fi + BT LE module. **There is no radio-free variant of the
  `-WROOM-1` or `-1U`.**
- §10.2: the `-1U` external connector is the *first-generation* external antenna connector,
  compatible with Hirose U.FL / I-PEX MHF I / Amphenol AMC, and *"the module does not
  include an external antenna upon shipment."*

### D2 — Part and variant verdict: the part does **not** change; the connector is left unpopulated

ADR-029 D1 mandates `ESP32-S3-WROOM-1U-N8R8` (the U.FL variant). With Wi-Fi/BT never
enabled, the question is whether the `-1U` (external connector) choice still stands, or
whether the cheaper `-1` (on-module PCB antenna) becomes strictly better.

**Conclusion: the part is unchanged — `ESP32-S3-WROOM-1U-N8R8` stays, and the U.FL
connector is simply left unpopulated.** Rationale:

1. **The `-1U` was chosen for coexistence, and this decision makes that reason stronger,
   not weaker.** ADR-029 D3 selected `-1U` so the Wi-Fi radiator *could* be a pigtail
   routed off-board to the opposite end of the payload. With Wi-Fi/BT never enabled, there
   is no radiator at all — which is the best possible outcome of D3's separation logic,
   not a reason to switch variants. Leaving the connector unpopulated removes the feed
   entirely rather than leaving an open, unterminated RF stub.
2. **Switching to the `-1` (PCB-antenna) variant would buy nothing here.** The PCB antenna
   variant exists solely to carry the very radio this ADR disables; its on-module antenna
   would be an inert, radiating-adjacent metal structure sitting ~2 cm from the other
   2.4 GHz-capable radios with no signal to carry. It is neither cheaper in a way that
   matters nor strictly better — the `-1U` part is already the ADR-029 selection, and
   keeping it (connector unpopulated) costs zero BOM lines and zero schematic rework.
3. **Not a decision, but recorded as a recommendation if it is ever revisited:** if a
   future board drops Wi-Fi/BT *and* the U.FL connector's board-area/cost is being
   counted, a dedicated non-radio host would be the honest answer — but that is exactly
   the MCU substitution ADR-029 rejected (see D5 below), so it is not on the table here.

### D3 — Power, quantified with citations (honest: the marginal idle saving is small)

*Provenance: ESP32-S3 Series Datasheet v2.2, §5.6.2, tables 5-7, 5-8, 5-9, 5-10.*

| Mode | Figure (datasheet) | What it means here |
|---|---|---|
| Wi-Fi TX, 802.11b @ 21 dBm | **340 mA** peak (Table 5-7) | The +20 dBm burst cost, gone entirely when never enabled |
| Wi-Fi RX | **88–91 mA** (Table 5-7) | Gone entirely when never enabled |
| BLE TX @ 21 dBm | **335 mA** peak (Table 5-8) | Gone entirely when never enabled |
| Modem-sleep (Wi-Fi clock-gated) | **13.2–66.7 mA** (Table 5-9, all-peripheral-clocks-disabled column) | Only relevant if the PHY is kept associated; never-enable never enters it |
| Light-sleep (VDD_SPI + Wi-Fi down) | **240 µA** (Table 5-10) | Unaffected by this decision |
| Deep-sleep (RTC only) | **7–8 µA** (Table 5-10) | Unaffected by this decision |

The honest reading of these numbers:

- **If the PHY is never initialised, the marginal idle saving over "enabled but idle" is
  small.** The PHY is on-die; when never initialised it draws only its (near-zero)
  quiescent/leakage current. The 13.2–66.7 mA modem-sleep figure is what an *associated,
  beacon-listening* radio costs — a state the never-enable decision means the board never
  enters. The gap between "never initialised" and "initialised but never associated" is
  single-digit milliamps, not tens.
- **The real cost of leaving Wi-Fi/BT enabled was never the idle current.** It is the
  **+20 dBm TX bursts (340 mA peak) and the periodic 2.4 GHz activity** on a board that
  already carries three other 2.4 GHz-capable radios (ADR-029 §2(b), §3). Those bursts are
  what D4 (below) removes.
- **UNVERIFIED: the exact never-initialised quiescent current of the S3 RF subsystem.**
  The datasheet does not publish a "Wi-Fi/BT never initialised" current figure distinct
  from the low-power tables above. It would be settled by a bench measurement: ESP32-S3
  with `CONFIG_ESP_WIFI_ENABLED=n` / `CONFIG_ESP_BT_ENABLED=n`, CPU at the flight
  frequency, measuring active-mode supply current with a multimeter — and comparing
  against the same build with Wi-Fi initialised but unassociated.

### D4 — Mass, quantified (honest: single-digit to low-teens grams — not a mass lever)

The saving is the **connector + pigtail + antenna that are not fitted**, not the radio
(the radio is on-die and cannot be removed). Quantified:

| Item not fitted | Mass (range) | Basis |
|---|---|---|
| U.FL/MHF-I connector (on-board) | ~0.1–0.3 g | connector-body estimate; the part is sub-gram by inspection of the §10.2 connector drawing |
| Pigtail / coax jumper | ~0.5–2 g | depends on length and cable |
| Antenna (2.4 GHz whip or flex) | ~2–10 g | depends on choice |

**Total: roughly 3–12 g, i.e. single-digit to low-teens grams — and the bulk of it is the
antenna, which was already sized off-board in 3D.** *Label: ESTIMATE — no module/connector
mass is published in the Espressif datasheets, and the antenna is unselected.* This is
**not** a mass lever. It is two orders of magnitude below the enclosure and the
solar/substrate decisions that actually move the payload's mass, and it must not be
dressed up as one. The value of this decision is in D5–D9 below, not in the grams.

---

## Consequences (these matter more than the grams)

### D5 — A self-jamming source is removed

ADR-029 §2(b) recorded the S3's Wi-Fi/BT as a fourth 2.4 GHz emitter at **+20 dBm ~2 cm**
from the modules it must coexist with, mitigated only by TDM (Wi-Fi forced *off and
confirmed down* whenever a 2.4 GHz grant is issued) plus the U.FL pigtail routing. With
Wi-Fi/BT never enabled, **that interferer is removed outright, not merely scheduled
around.** ADR-029 §2(b) (S3 ↔ module 2.4 GHz) and the §3 arbiter's `WIFI_2G4` slot become
simpler: the arbiter no longer has a third 2.4 GHz contender to serialize, and the
"stop-and-confirm-down" binding for Wi-Fi (ADR-029 D4) is retired with it. The remaining
2.4 GHz coexistence is the F33 TX port vs the bare `LoRa2021` RX (ADR-034) and the SX1280 —
a two-way, not three-way, problem.

### D6 — The regulatory picture gets cleaner

With Wi-Fi/BT disabled, **all** 2.4 GHz use on the payload falls under the operator's
**amateur licence**. Leaving Wi-Fi/BT enabled would have mixed an amateur-band transmitter
with a **licence-exempt** Wi-Fi/BT transmitter (different regulatory regimes — EN 300 328
short-range-device rules vs the amateur allocation). This decision removes that mixing.
The amateur-licence position itself is the subject of a separate worker's
`docs/REGULATORY-AMATEUR-LICENCE.md`; this ADR records the class of issue (single-regime
2.4 GHz) and does not redo that work. ADR-034's open item on 433 MHz power legality in DE
is unaffected and remains open.

### D7 — The parked question is foreclosed: the separate 2.4 GHz receiver stands

An open item asked whether the S3's own on-die 2.4 GHz radio could replace the
**separate** 2.4 GHz receiver (the fourth RF part — the bare `LoRa2021` RX that ADR-034 D1
mandates). With Wi-Fi/BT disabled, that answer is **no**: the S3's on-die radio is exactly
what this ADR never enables, so it cannot serve as the link's RX path. **ADR-034's
separate 2.4 GHz receiver stands**, and the question is closed rather than left dangling.
(The independent SX1280-as-2.4 GHz-RX option ADR-034 D6 records is a *different* question
— that option concerns the SX1280, not the S3, and is unaffected.)

### D8 — The config path must move

ADR-029's table row *"Config / telemetry when radios idle → ESP32-S3 Wi-Fi/BT"* (line 261)
becomes false. The config path is now:

- **USB/serial via the programming pads on the bench**, and
- **commands over the radio link in flight.**

Whether config *over the link* is implemented is a **firmware** question, not decided here;
this ADR only records that the Wi-Fi/BT path is gone. A pointer is added to ADR-029's row
so it does not sit there contradicting this record (see "Changes to ADR-029" below).

### D9 — This does **not** reopen the MCU choice

ADR-029 selected the ESP32-S3 for **octal PSRAM (flight log), GPIO count, and USB** — not
for Wi-Fi (ADR-029 D1 items 1–3, 5; Wi-Fi was item 4, and D1 explicitly records that
`CONFIG_ESP_WIFI_ENABLED=n` / `CONFIG_ESP_BT_ENABLED=n` were already the in-repo S3
defaults for power parity). Disabling Wi-Fi/BT therefore removes **none** of the load-bearing
rationale for the S3, and does **not** reopen the MCU decision. v9 = ESP32-S3 is recorded
in ADR-037 (in flight); this ADR points at it and does not duplicate its content.

---

## Changes to ADR-029

`docs/adr/029-dual-band-flight-board.md` is amended in place: the config/telemetry row
(line 261) is re-pointed from "ESP32-S3 Wi-Fi/BT" to reference this ADR, so the record no
longer implies a Wi-Fi/BT config path that this ADR retires. The edit is a one-line
pointer, not a rewrite of ADR-029.

---

## What would falsify this

- A bench measurement showing that the never-initialised S3's active-mode current is
  materially *higher* than the enabled-but-unassociated baseline (i.e. that the PHY cannot
  actually be held fully quiescent) — this would not reverse D1 (the self-jammer and
  regulatory arguments are independent of the current), but it would correct D3's
  "marginal saving is small" claim.
- A flight requirement that *demands* over-the-air configuration with no bench access —
  this would reopen D8's "USB + radio link" config path, and with it the Wi-Fi/BT enable
  decision.

---

## Next-free-number check (recorded)

Run on branch `adr/wifi-bt-disabled` (base `8b46f68`, the observed tip of
`adr/radioband-tdm`):

```
git ls-tree -r --name-only HEAD docs/adr        # in-tree: ... 031, 032, 034, 035; no 036/037/038
git log --all --oneline --name-only -- 'docs/adr/*'   # all branches: 036 (energy-policy); no 038
```

036 is claimed on branch `adr/energy-policy`; 037 is reserved by a concurrent worker; 038
is free on every branch inspected.
