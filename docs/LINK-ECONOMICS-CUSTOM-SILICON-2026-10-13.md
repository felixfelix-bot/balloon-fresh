# Custom Silicon vs Link Economics — why the S1G range tricks are firmware, not silicon

**Date:** 2026-10-13 · **Trigger:** operator question after the HaLow verdict (RFA-2): *"is it
possible to order custom silicon that does this?"* — "this" being the 802.11ah S1G range
mechanisms (1 MHz narrowband, MCS10 2×-repetition, long GI).
**Companion docs:** `docs/RFA-LEARNINGS-2026-10-13.md`, `docs/RFA1-ELRS-LR2021-DIFF-2026-10-12.md`
(both on main), hermes-manager-skills `rfa2-halow-coverage-class-verdict-2026-10-12.md`.

---

## 1. The three S1G range regulators, mapped to our stack

802.11ah buys range with exactly three mechanisms. None of them requires special silicon —
each has a firmware-or-config equivalent we already own on the LR2021:

| 802.11ah mechanism | What it is | Our equivalent | Verdict |
|---|---|---|---|
| **1 MHz narrowband** | Bandwidth knob (vs 2/4/8/16 MHz) | LoRa mode: BW programmable down to **7.8 kHz** — two orders of magnitude narrower than HaLow's floor. FLRC mode: 0.307–2.666 MHz occupied BW per datasheet Table 18-1. | already in the chip |
| **MCS10 = 2× repetition** (BPSK ½, 0.17 Mbps @ −107 dBm) | the crudest FEC: send everything twice | frame-layer repeat (N-send) or real FEC (convolutional/LDPC-style + interleaving) on a raw modem. **Precedent: ExpressLRS runs exactly this on the same Semtech family** — its FEC/interleaving stack is the existence proof that frame-layer FEC works on this silicon. | firmware |
| **Long guard interval** | inter-symbol guard time against delay spread | in a proprietary raw mode the preamble/guard structure is **ours to choose** — no standard dictates it | firmware/config |

**Why does 802.11ah cast these in silicon at all?** Because it is a *compatibility standard*:
certification, power-class enforcement, MAC integration, and interoperability between
unrelated vendors. A certification regime cannot rely on every vendor implementing soft
FEC correctly, so the range tricks are frozen into the PHY. **A custom link has none of these
constraints** — the silicon packaging of a coding trick buys us nothing firmware doesn't
deliver for free.

## 2. When custom silicon IS the right answer

Silicon earns its NRE where **physics** forces it, not where coding can substitute:

- lower **noise figure** (a better LNA front end),
- higher **OIP3/linearity** (surviving a strong interferer next to a weak signal),
- a more **efficient PA** (same watts from less battery mass — the pico-balloon currency).

Coding gains (repetition, FEC, interleaving, narrowband) are math, and math runs free on any
MCU next to the modem. The rule: **doubt the physics only after the firmware is exhausted** —
which is why the PRAM-patch experiment (RFA-1b, card `t_0eaed49b`) comes before any thought
of different silicon: an unpatched PHY misbehaving on short payloads is a far more likely
explanation of our FLRC anomaly than demodulator species.

### The procurement ladder, for completeness

| Rung | Cost | What you get |
|---|---|---|
| 0 — firmware/config | €0 | everything in §1; ELRS-style FEC; mode/band/ramp choices |
| 1 — SDR (LimeSDR/AD9361 class) | ~€100–2,000 | fully custom PHY for ground-station experiments, no fab |
| 2 — open MPW shuttles (IHP SG13G2 130 nm SiGe BiCMOS, open PDK) | small €, months | real "ordered silicon", but realistically simple blocks (OOK/FSK demod), not a full sub-GHz transceiver — that is person-years of analog design |
| 3 — design house + foundry (CEVA-style IP, TSMC/GF) | $2–50 M NRE, 12–18 mo | a product; rational only at volume. (Efabless/ChipIgnite — the indie middle rung — folded in 2024; the scene has narrowed.) |

We are on rung 0 and it is not yet exhausted.

## 3. Link-budget economics: the binding constraint is not the demodulator

Our link-budget work (`rf-link-budget` skill; worked examples in its references) says the
bent-pipe link is limited by, in order:

1. **The EIRP ceiling** — on a licence-exempt footing, if `cap_shortfall > 0` then **no
   antenna gain and no amplifier can close the link** (both raise EIRP and hit the same
   ceiling). The only fixes are a higher legal footing or a better ground RX.
2. **Ground-station antenna gain** — receive-side gain is unregulated, and the ground end
   costs the balloon **0 g and 0 W** (the platform asymmetry: every airborne dB costs solar
   area and battery mass; every ground dB costs a longer mast).
3. **Demodulation species** — last. Sensitivity spread across our own modes is 38 dB
   (LoRa SF12 ≈ −137 dBm vs FLRC 2.6 Mbit ≈ −99 dBm), but a data link cannot live at SF12;
   within the usable FLRC/LoRa-range band the spread is a few dB — **exactly the magnitude
   custom silicon would buy for millions**, while a ground Yagi buys more for €50.

## 4. COST-EFFECTIVE PERFORMANCE RANK LIST (the focus)

Ordered by dB-per-Euro, from cheapest to first-hardware. Items 1–5 are already carded or
config-level; items 6–8 are the hardware/legal steps that actually move the budget.

| # | Action | Cost | Expected effect | Status |
|---|---|---|---|---|
| 1 | **868 MHz over 2.4 GHz** for the long link | config | **+19 dB** link budget at equal distance (measured, our dual-band analysis) | default already; keep 2.4 for short-range/bench |
| 2 | **FLRC-260 as robust mode** (vs 650) | config | **~4 dB** robustness (bench-proven: 0.5 % PER; best FLRC mode) | in use for range work |
| 3 | **RFA-1a init deltas**: CALIBRATE `0x5F→0x7F`, settle 5/5→10/30 ms | one line each | removes unsettled-calibration flakiness; vendor-adjacent value | carded `t_08df35a5` (scheduled) |
| 4 | **PRAM patch experiment** (RFA-1b) | firmware toggle + bench time | potential root cause of the 64/128 B CRC anomaly — a correctness fix worth more than dB | carded `t_0eaed49b`, **flash-gated on operator** |
| 5 | **Frame FEC + interleaving** (ELRS-style), RX boost mode, Long Interleaver, CR_NONE | firmware | the MCS10-equivalent done properly; several dB effective margin at equal rate, our own E80 analysis ranked these | next firmware feature after 3+4 |
| 6 | **Ground station: 868 MHz Yagi (10–12 dBi) + masthead LNA** | €30–60 antenna, €20–40 LNA | the single biggest $/dB win on the downlink; LNA chain NF ≈ 1.0 dB (0.5 dB LNA + 0.5 dB BPF/feed) | **next hardware buy** |
| 7 | **EU high-power sub-band 869.525 MHz** (+22 dBm PA, legal to +27 dBm ERP, duty-cycled) | config + regulatory care | last legal +5 dB on the airborne TX without hardware | outdoor PIN already implemented on E80 fw |
| 8 | **Licensing footing move** (licence-exempt → amateur licence) | exam fee + operator time | **tens of dB legal EIRP**, no duty cycle in relevant bands, zero hardware — the cheapest large margin that exists | operator decision |
| — | *Custom silicon / HaLow modules* | €k–M | a few dB sensitivity, unknown schedule | **not now** — revisit only after 1–8 are exhausted |

**Decision rule to keep:** buy dB where mass and power are free (ground before air);
firmware before hardware; legal footing before amplifier; patch hunt before physics doubt.

## 5. Sources

- S1G mechanisms + NOT-REACHABLE verdict: RFA-2 report (skills repo, `b6f4594`).
- LR2021 PRAM patch, calibrate/ramp deltas: `docs/RFA1-ELRS-LR2021-DIFF-2026-10-12.md`.
- FLRC BW table (Table 18-1), ramp table (Table 7-21): LR2021 datasheet text at
  `~/worktrees/rfa1-elrs/ds.txt` (sections 7.4.3, 18.4.x).
- 19 dB band delta, FLRC-260 robustness, +22/+27 dBm sub-band, EIRP-cap logic, platform
  asymmetry: our E80 bench analyses and `rf-link-budget` worked examples
  (`e80-max-power-dual-band-analysis-2026-08-24`, `433-2g4-bent-pipe-relay-worked-example`).
- ELRS FEC-on-same-silicon precedent: ExpressLRS master `src/lib/` (FEC/interleaving used
  alongside `src/lib/LR2021Driver/`).
