# Frequency plan & duty-cycle compliance — 868 MHz band (EU SRD)

Task: decode-gaps T5. Feeds T4 (duty guard in `e80_bench_ctl.py`).
Status: **regulatory data verified** against ERC Recommendation 70-03, latest
amended **5 June 2026 (FM#113)** — "ERC/REC 70-03 of 6 October 1997 on relating
to the use of Short Range Devices (SRD)", ECO DOCDB document
<https://docdb.cept.org/download/4980>, accessed 2026-08-17. Annex 1 table is
the October 2025 edition (per Document History, Table 18) — current as of the
5 June 2026 release.

This is an engineering compliance summary, not legal advice. National
implementations of REC 70-03 vary (Appendix 1 national implementation status /
Appendix 2 national restrictions in the Rec, live data in EFIS). Portugal:
ANACOM. Airborne (balloon) use of SRDs may be restricted nationally — verify
with ANACOM before any flight transmitting under this plan.

## 1. Verified sub-band table — ERC REC 70-03, Annex 1 (non-specific SRDs)

Our transmissions (bench telemetry, one-to-one/one-to-many links) fall under
**Annex 1, non-specific SRD** entries unless a specific application annex
applies (none does — we are not alarms, RFID, or an EN 303 659 data network).

| Frequency band (MHz) | Rec entry | Power limit | Spectrum access | Bench usable? |
|---|---|---|---|---|
| 863.000–865.000 | h1.3 | 25 mW e.r.p. (14 dBm) | ≤ 0.1 % DC or LBT+AFA | yes (0.1 %) |
| 865.000–868.000 | h1.4 | 25 mW e.r.p. (14 dBm) | ≤ 1 % DC or LBT+AFA | yes |
| 868.000–868.600 | h1.5 | 25 mW e.r.p. (14 dBm) | ≤ 1 % DC or LBT+AFA | **default EU cell** (868.0 MHz) |
| 868.600–868.700 | Annex 7a (alarms) | 10 mW e.r.p. | ≤ 1 % DC | **no — alarms only** |
| 868.700–869.200 | h1.6 | 25 mW e.r.p. (14 dBm) | ≤ 0.1 % DC or LBT+AFA | yes (0.1 %) |
| 869.200–869.400 | Annex 7b–d (alarms/social alarms) | 10 mW e.r.p. | ≤ 0.1 % / 1 % DC | **no — alarms only** |
| 869.400–869.650 | h1.7 | **500 mW e.r.p. (27 dBm)** | ≤ 10 % DC or LBT+AFA | **high-power channel** |
| 869.650–869.700 | Annex 7e (alarms) | 25 mW e.r.p. | ≤ 10 % DC | **no — alarms only** |
| 869.700–870.000 | h1.8 | 5 mW e.r.p. | no DC requirement | no (power too low) |
| 869.700–870.000 | h1.9 | 25 mW e.r.p. (14 dBm) | ≤ 1 % DC or LBT+AFA | yes |

All rows: EN 300 220. Generic fallback h1.2 (863–870 MHz, 25 mW e.r.p.,
≤ 0.1 % DC or LBT+AFA, non-FHSS) covers the whole band at the lowest DC tier.
**The LR2021 bench firmware implements no LBT/AFA**, so duty cycle is our only
compliance route; every "or LBT+AFA" above effectively reads as a hard DC cap.

## 2. Corrections vs. folklore (and vs. this repo's earlier brief)

Two numbers that circulated in the decode-gaps brief and in common LoRa
folklore are **wrong** for our application class, per the verified current
table:

1. **863–865 MHz is not "100 mW, no duty cycle".** It is 25 mW e.r.p. with
   ≤ 0.1 % DC (or LBT+AFA). (h1.3.)
2. **865–868 MHz is not "500 mW, 10 %" for us.** For non-specific SRDs it is
   25 mW e.r.p., ≤ 1 % DC (h1.4). A 500 mW entry in 865–868 does exist, but
   only as:
   - Annex 2 c1 — *data networks* under **EN 303 659** with **mandatory
     Adaptive Power Control** (must step down to ≤ 5 mW), ≤ 10 % DC for
     network access points / ≤ 2.5 % otherwise, **and** note 4 restricts
     operation to four 200 kHz channels: 865.6–865.8, 866.2–866.4,
     866.8–867.0, 867.4–867.6 MHz; and
   - Annex 11 RFID interrogators (EN 302 208, up to 2 W, same four channels
     plus 865–865.6 @ 100 mW / 867.6–868 @ 500 mW).

   The E80 bench has no APC and transmits on arbitrary channels, so neither
   applies. The only ≥ 500 mW slot available to us in the whole 863–870 band
   is **h1.7: 869.400–869.650 MHz**.

Also: the RANGE-TEST-PLAN §4 budgets (duty ≤ 15 % on 51 B cells, ≤ 40 % on the
255 B anchor) are **engineering budgets for override/cage sessions** (thermal +
RF exposure), *not* regulatory duty cycles. They are legal only under
`BAND OVERRIDE 2026` regimes outside the EU SRD plan (e.g. the 915 MHz
Americas reference campaign, which is outside EU SRD rules entirely). For any
in-EU transmission without an override, the Annex 1 limits in §1 are binding
and far stricter.

## 3. E80 mapping — clamp, power modes, e.r.p. math

Firmware/host policy (see `firmware/e80-stm32-bench/README.md` §"Safety
policy", binding 2026-08-16, and `tools/e80_bench_ctl.py`):

- Default EU policy: TX clamped to **863–870 MHz**
  (`BAND_MIN_HZ = 863000000` / `BAND_MAX_HZ = 870000000`, firmware-identical),
  power capped at **+10 dBm conducted** (`INDOOR_CAP_DBM = 10`).
- `BAND OVERRIDE 2026` (window 410–960 MHz) and `POWER MODE OUTDOOR 2026`
  (+22 dBm) are logged exceptions for range sessions.

Power limits in REC 70-03 for this band are **e.r.p.** (relative to a
half-wave dipole), not e.i.r.p. Conversion: EIRP = e.r.p. + 2.15 dB. Link
budget for compliance:

```
P_conducted (dBm) + G_antenna (dBi) − L_cable (dB) ≤ e.r.p. limit
```

- **Default / indoor (+10 dBm, stock ~2 dBi whip, negligible cable):**
  ≈ 12 dBm e.r.p. ≤ 14 dBm → compliant on any h1.3–h1.6/h1.9 sub-band.
- **Outdoor +22 dBm (`POWER MODE OUTDOOR 2026`):** legal **only inside
  h1.7 (869.400–869.650 MHz)**: 22 + 2 = 24 dBm e.r.p. ≤ 27 dBm → ≈ 3 dB
  margin. On every other sub-band the cap is 14 dBm e.r.p., so +22 dBm
  conducted overshoots by ≥ 8 dB → non-compliant in EU. This is why outdoor
  range sessions at high power either run in h1.7 or happen at 915 MHz under
  `BAND OVERRIDE 2026` (Americas ISM, reference campaign, outside EU SRD).
- With a higher-gain antenna the PA must be backed off one-for-one (e.g. a
  6 dBi antenna at +22 dBm conducted = 28 dBm e.r.p. > 27 dBm limit → cap PA
  at +21 dBm or lower in h1.7; on 14 dBm sub-bands cap at 14 − G dBm).

## 4. Duty-cycle accounting (feeds the T4 guard)

Definition (REC 70-03 Appendix 4): duty cycle = Σ(T_on) / T_obs where T_on is
the transmitter "on" time of a single device and **T_obs = a continuous
one-hour period**, evaluated **per sub-band** (F_obs = the applicable band).
Inter-packet gaps (`gap_us` in the scheduler) do not count — only airtime.

Hourly budgets: 0.1 % = 3.6 s/h · 1 % = 36 s/h · 10 % = 360 s/h (Table 17).

Airtimes below are computed with the repo's own estimator
(`lora_airtime_s()` / `flrc_airtime_s()` in `tools/e80_bench_ctl.py`;
offline twin `docs/airtime_calc.py`). Packet budgets are per hour, per
sub-band, per transmitter (floor(3600 × DC / airtime)); format 51 B / 255 B:

| Modulation | Airtime 51 B | Airtime 255 B | @0.1 % (h1.3/h1.6) | @1 % (h1.4/h1.5/h1.9) | @10 % (h1.7) |
|---|---|---|---|---|---|
| LoRa SF7/BW125 | 0.103 s | 0.400 s | 35 / 9 | 350 / 90 | 3506 / 900 |
| LoRa SF12/BW125 | 2.466 s | 9.019 s | 1 / **0** | 14 / 3 | 145 / 39 |
| FLRC 650 kbps | 0.8 ms | 3.3 ms | 4357 / 1078 | 43575 / 10788 | 435754 / 107883 |
| FLRC 2600 kbps | 0.3 ms | 0.9 ms | 12786 / 3959 | 127868 / 39593 | 1278688 / 395939 |

(SF12/255 B airtime is 9.0 s; the 18.1 s figure in the firmware README is the
chip TX-timeout = 2 × airtime + 50 ms, not airtime. FLRC airtimes follow
`flrc_airtime_s`: (payload·8 + 64)/bitrate + 0.1 ms.)

Consequences for campaign design:

- **SF12 at 255 B does not fit a 0.1 % sub-band at all** (9.0 s > 3.6 s/h).
  One packet per ~2.5 h maximum on h1.3/h1.6 — effectively unusable there.
- SF12/51 B fits a 0.1 % budget exactly once per hour. Sweeps at SF12 belong
  in h1.7 (145 packets/h @ 51 B) or under an override regime.
- The default EU cell (868.0 MHz, h1.5, 1 %) supports 14 SF12/255 B or
  350 SF7/51 B packets per hour — ample for telemetry cadence (e.g. 1 frame
  per 10 s at SF7/51 B = 360/h × 0.103 s ≈ 1.03 % → keep cadence ≤ 1 per 12 s,
  or use FLRC which is negligible).

## 5. Guard spec for T4 (machine-readable)

Sliding 1-hour window per sub-band bucket, counting airtime only. Fail-closed:
TX outside the enumerated buckets → block. Alarm sub-bands are no-TX zones for
this device (our PAs cannot reliably hit 10 mW e.r.p. and the application
class is wrong anyway).

```json
{
  "source": "ERC REC 70-03 amended 2026-06-05 (FM#113), Annex 1 + Annex 7",
  "window_s": 3600,
  "edges_mhz": [863.0, 865.0, 868.0, 868.6, 868.7, 869.2, 869.4, 869.65, 869.7, 870.0],
  "buckets": [
    {"lo": 863.0,  "hi": 865.0,  "dc_max": 0.001, "erp_dbm_max": 14, "entry": "h1.3", "policy": "allow"},
    {"lo": 865.0,  "hi": 868.0,  "dc_max": 0.01,  "erp_dbm_max": 14, "entry": "h1.4", "policy": "allow"},
    {"lo": 868.0,  "hi": 868.6,  "dc_max": 0.01,  "erp_dbm_max": 14, "entry": "h1.5", "policy": "allow"},
    {"lo": 868.6,  "hi": 868.7,  "dc_max": 0.01,  "erp_dbm_max": 10, "entry": "Annex7a", "policy": "block", "reason": "alarms only"},
    {"lo": 868.7,  "hi": 869.2,  "dc_max": 0.001, "erp_dbm_max": 14, "entry": "h1.6", "policy": "allow"},
    {"lo": 869.2,  "hi": 869.4,  "dc_max": 0.001, "erp_dbm_max": 10, "entry": "Annex7b-d", "policy": "block", "reason": "alarms only"},
    {"lo": 869.4,  "hi": 869.65, "dc_max": 0.10,  "erp_dbm_max": 27, "entry": "h1.7", "policy": "allow"},
    {"lo": 869.65, "hi": 869.7,  "dc_max": 0.10,  "erp_dbm_max": 14, "entry": "Annex7e", "policy": "block", "reason": "alarms only"},
    {"lo": 869.7,  "hi": 870.0,  "dc_max": 0.01,  "erp_dbm_max": 14, "entry": "h1.9", "policy": "allow"}
  ],
  "default_policy": "block",
  "override": "BAND OVERRIDE 2026 sessions run outside the EU plan entirely; guard bypass must be logged like the firmware override"
}
```

The guard should compute per-bucket Ton with the same estimators as §4 and
refuse any cell whose scheduled (n × airtime) would exceed the bucket budget
in any 1-hour-aligned window of the planned session.

## 6. References

- ERC REC 70-03 (current): ECO DOCDB `docdb.cept.org/download/4980`
  (ERC/REC 70-03, amended 5 June 2026, FM#113) — Annex 1 Table 1 (h-rows),
  Annex 2 Table 2 (c1 + note 4), Annex 7 Table 7, Appendix 4 (DC definition).
- EN 300 220 (harmonised standard for all rows above), EN 303 659 (data
  networks, not applicable), EN 302 208 (RFID, not applicable).
- In-repo: `docs/RANGE-TEST-PLAN.md` (override regimes, §4 engineering duty
  budgets), `firmware/e80-stm32-bench/README.md` (binding safety policy),
  `firmware/e80-stm32-bench/tools/e80_bench_ctl.py` (band clamp L44–45,
  indoor cap L49, airtime L82–105), `docs/airtime_calc.py`,
  `docs/link-budget.md`, `docs/antenna-strategy.md`.
