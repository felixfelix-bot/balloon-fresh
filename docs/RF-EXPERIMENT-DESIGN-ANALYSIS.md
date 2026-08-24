# RF Experiment Design Analysis: Min Configs × Distances for E80 Envelope

**Date:** 2026-08-24
**Analyst:** RF experiment design consultant (Hermes subagent)
**Subject:** Optimal test matrix for E80 STM32/LR2021 radio characterization at 868 MHz

---

## Executive Summary

The user's "max payload, 3 configs, 3 distances" strategy is **90% sound** but has
one critical gap: **the distance spacing is too wide to bracket any cliff**. The
proposed 450m → 1.5km → 5km jumps are 10 dB steps. A radio cliff edge is typically
3-6 dB wide. A 10 dB step straddles the cliff without resolving it — you get
"pass" at one distance and "fail" at the next, with no idea where in that 10 dB
gap the cliff actually sits.

**Recommended fix:** Insert 872m between 450m and 1.5km. Use doubling distances
(436m, 872m, 1744m, 5km) with selective config skips. This gives **8 test runs**
(1 fewer than the user's 9) with **all 3 cliffs bracketed at 6 dB resolution**
plus a propagation slope from 4 SF12 RSSI points.

---

## User Decisions (2026-08-24)

The user reviewed the consultant's recommendations and made the following
decisions, which **override** the analysis below where they conflict:

1. **FLRC-2600: KEEP.** "I'm reluctant to drop high data rates because our
   high data rate is exactly what we're trying to achieve at a distance."
   The consultant recommended dropping FLRC-2600 (dead at 218m at 868 MHz),
   but the user wants to know *where* FLRC-2600 dies vs FLRC-650. It stays
   in the campaign as a 4th config (FLRC-2600 511B).
2. **Packet count: KEEP 10.** "Let's not reduce the number of tries since
   that doesn't save us a lot of time." 10 packets gives 10% PER resolution;
   reducing to fewer saves only ~18s out of 3+ min. Keep 10 per config.
3. **Payload size: MAX.** "Drop smaller packet sizes, always measure with
   the largest packet size." 511B FLRC, 255B LoRa — worst-case sensitivity
   and best throughput. No intermediate payload sizes.
4. **Guard time: REDUCE.** "We can assume network time isn't going to be
   seconds apart on two computers that are both online." Both machines
   NTP-synced = within 1s. Reduced defaults: t0_margin=30s, guard=5s,
   rx_lead=3s, settle=1s, swd_reset_s=2s.
5. **CVM: INTEGRATE (optional layer).** "The Python script could be a CVM,
   and Hermes could provide configs remotely as a CVM." Implement CVM as an
   optional enhancement (`make range-cvm-server`); fixed-schedule mode
   (`make tx`/`make rx`) remains the fallback when no internet in the field.
6. **70 km extension.** The Madeira–Porto Santo inter-island distance is
   ~70 km — the mission-relevant maximum range. Extend the distance matrix
   to 70 km (6 stops: 218m/436m/872m/1744m/5km/11km/70km) so LoRa SF12 is
   tested at the true mission boundary. If SF12 passes at 70 km ground-level
   (two-ray d⁻⁴), it will work at balloon altitude (FSPL d⁻², much less
   lossy) → mission GO.

**Net effect on the matrix:** 4 configs (FLRC-650 511B, FLRC-2600 511B,
LoRa-SF7 255B, LoRa-SF12 255B) × 6 distances with selective skips = 15 runs
(see the 70 km matrix in the plan). The consultant's 3-config / 8-run
recommendation below is superseded by these decisions.

---

## 1. Payload Size vs Receiver Sensitivity

### 1.1 Theory: Does larger payload affect sensitivity?

**Sensitivity** (minimum receivable power for a target PER) and **PER at a given
SNR** are related but distinct:

- **Sensitivity threshold** is set by the modem's required Eb/N0, which depends
  on modulation, coding rate, and bandwidth — **not payload size**. The receiver
  demodulates each symbol identically regardless of how many symbols follow.
- **PER at a given SNR** scales with payload length: PER ≈ 1 − (1 − BER)^N, where
  N = payload bits. More bits = more chances for a bit error = higher PER at the
  same SNR.

**Quantitative impact for FLRC-650 (CR 3/4):**

At the 1% PER sensitivity threshold:
- 64B (512 bits): requires BER ≈ 1.96 × 10⁻⁵
- 511B (4088 bits): requires BER ≈ 2.45 × 10⁻⁶

The 511B packet needs **~8× lower BER**. On the FLRC waterfall curve (which is
moderate steepness — GFSK with 3/4 FEC), this translates to approximately
**1-3 dB higher required SNR**. So 511B sensitivity is ~1-3 dB worse than 64B.

**For LoRa (strong FEC, steep waterfall):**

LoRa's forward error correction creates a very steep BER-vs-SNR waterfall. The
difference between 64B and 255B required SNR at 1% PER is typically **<1 dB**.
LoRa's interleaver spreads burst errors across the entire packet, so payload
length has minimal effect on the cliff position.

### 1.2 Can 511B fail where 64B succeeds at the same RSSI?

**Yes, but only within 1-3 dB of the cliff.** Header/syncword acquisition is
identical — the receiver locks onto the preamble and syncword the same way
regardless of payload length. The difference is purely in payload decoding:
more bits = more exposure to random bit errors.

**Practical scenarios:**
- At 10 dB margin (well above cliff): 511B and 64B both pass 100%. No difference.
- At 3 dB margin (near cliff): 511B might show 10-30% PER while 64B shows 0-5%.
  The 511B packet "feels" the cliff 1-3 dB sooner.
- At 0 dB margin (at cliff): both fail, but 64B might偶尔 succeed where 511B
  never does.

### 1.3 If 511B works at distance X, can we assume 64B also works?

**Yes, with very high confidence.** If 511B passes at 0% PER, the link has enough
margin for 64B (which needs 1-3 dB less). The only exception would be a
firmware-level issue specific to 511B (e.g., buffer handling, CRC computation
on longer payloads) — but that's a firmware bug, not an RF phenomenon.

**The reverse is NOT guaranteed:** 64B working does NOT mean 511B works. At the
cliff edge, 64B might pass while 511B fails. This is the key reason to test at
max payload: **511B is the worst case for sensitivity.** If 511B works, all
smaller payloads work. This is exactly the user's intuition, and it's correct.

### 1.4 The AGC RSSI artifact (LR2021-specific)

From `docs/analysis-flrc-rssi-cliff.md`: the LR2021 chip has an AGC settling
artifact where short FLRC packets (<6 ms airtime) show **depressed RSSI readings**
by 25-35 dB. This is a **reporting artifact**, not a sensitivity difference —
the packets are still received correctly (10/10 at 218m with 64B, 0% PER).

**Impact on this experiment:** The RSSI values from 511B packets (11 ms airtime)
will be **more accurate** than from 64B packets (2 ms airtime). So switching to
511B actually **improves RSSI data quality** as a bonus.

| Payload | Airtime @ 650 kbps | RSSI quality | Sensitivity vs 64B |
|---------|-------------------|--------------|---------------------|
| 64B     | 2 ms              | Depressed 25-35 dB (AGC artifact) | Baseline |
| 255B    | 6 ms              | Correct (above 6 ms threshold) | -1 to -2 dB |
| 511B    | 11 ms             | Correct | -1 to -3 dB |

**Bottom line:** 511B gives better RSSI data, slightly worse sensitivity
(1-3 dB), and is the worst-case payload. If 511B works, everything works.
The user's strategy of using max payload is **correct and conservative**.

---

## 2. Throughput Characterization with Max Payload

### 2.1 Throughput vs payload size: is the curve predictable?

**Yes — it's a simple overhead-amortization model.**

Effective throughput = (payload_bytes × 8) / (airtime + gap)

Where airtime = (preamble + syncword + header + payload + CRC) / bitrate

For FLRC-650:
- Overhead: ~10 bytes (preamble 4B + syncword 4B + CRC 2B) = 0.012 ms
- Payload airtime: N_bytes / 81,250 bytes/s
- Gap: 5 ms (fixed)

| Payload | Airtime (ms) | Total w/ gap (ms) | Goodput (kbps) |
|---------|-------------|-------------------|----------------|
| 64B     | 0.89        | 5.89              | 87             |
| 128B    | 1.67        | 6.67              | 153            |
| 255B    | 3.24        | 8.24              | 248            |
| 511B    | 6.39        | 11.39             | 359            |

The curve is smooth and monotonically increasing. **One measurement at max
payload gives the peak; the shape is fully determined by the overhead model.**
Testing an intermediate payload (128B) would confirm the model but adds no
new information — the prediction would be validated within measurement noise.

### 2.2 LoRa throughput: SF dominates, not payload

For LoRa, airtime is dominated by spreading factor, not payload:

| Config | SF | Payload | Airtime/pkt (s) | Goodput w/ 10ms gap (kbps) |
|--------|----|---------|--------------------|---------------------------|
| SF7    | 7  | 64B     | 0.10               | 5.1                       |
| SF7    | 7  | 255B    | 0.13               | 14.2                      |
| SF12   | 12 | 64B     | 2.50               | 0.20                      |
| SF12   | 12 | 255B    | 2.97               | 0.68                      |

SF7 255B gives 2.8× better throughput than SF7 64B. SF12 255B gives 3.4× better
than SF12 64B. The throughput gain from max payload is significant for LoRa too.

**Conclusion:** Max payload is sufficient for throughput characterization.
An intermediate payload adds no information — the curve is smooth and
predictable from the overhead model. **Skip it.**

---

## 3. Dropping FLRC-2600

### 3.1 At 868 MHz: Confidently drop

**Data:** FLRC-2600 (64B) was 0/10 at 218m (RSSI -91.5 dBm). The 2600 kHz
bitrate has ~8-10 dB worse sensitivity than 650 kHz (~-88.5 dBm practical vs
~-102 dBm). At 218m with -91.5 dBm received, FLRC-2600 is 3 dB below its
sensitivity floor. Max range < 183m. **Dead and useless at any test distance
≥ 218m.**

### 3.2 At 2.4 GHz: Different physics, but wrong hardware

The LR2021 chip supports 2.4 GHz, but the E80-900MBL-02 board's RF front end
(matching network, PA, antenna) is tuned for 902-928 MHz. At 2.4 GHz:

- **Matching network insertion loss:** 15-20 dB (designed for 900 MHz, not
  2.4 GHz — the LC matching transforms impedance for one band)
- **PA gain:** Likely 0 or negative at 2.4 GHz (the PA is a sub-GHz part)
- **Antenna:** Sub-GHz whip, completely wrong for 2.4 GHz

Testing FLRC-2600 at 2.4 GHz on this board would measure **board incompetence,
not radio performance.** The 2.4 GHz path would need a different board with
proper 2.4 GHz matching (e.g., EBYTE's 2.4 GHz variant or a custom board).

**Verdict: Drop FLRC-2600 entirely from this campaign.** If 2.4 GHz testing
is needed later, it's a separate experiment with different hardware.

---

## 4. The 3-Config Proposal Analysis

### 4.1 What the 3 configs cover

| Config | Modulation | Payload | Sensitivity (est.) | Role |
|--------|-----------|---------|--------------------|------|
| 1 | FLRC-650 | 511B | ~-100 to -103 dBm | Short-range high-throughput |
| 2 | LoRa SF7 | 255B | ~-115 to -118 dBm | Medium-range telemetry |
| 3 | LoRa SF12 | 255B | ~-130 to -133 dBm | Long-range backup |

These three configs cover the full operational envelope:
- **Peak throughput** (FLRC-650 511B): ~360 kbps goodput
- **Operational telemetry** (SF7 255B): ~14 kbps, medium range
- **Emergency backup** (SF12 255B): ~0.7 kbps, max range

### 4.2 Do we need both SF7 and SF12?

**Yes — they bracket the LoRa envelope and serve different mission roles.**

- SF7 is the **operational mode**: fast enough for real-time telemetry (GPS
  position, sensor data), moderate range. If SF7 works at the balloon's max
  distance, use it for the entire flight.
- SF12 is the **backup mode**: if SF7 fails at altitude (balloon drifts beyond
  SF7 range), switch to SF12 for critical commands (cutdown, status polling).

Interpolation between SF7 and SF12 is **not reliable** for mission planning.
The SF-vs-range relationship is nonlinear (each SF step adds ~3-6 dB processing
gain but also 2× airtime). You can't predict SF9 performance from SF7 + SF12
data points without knowing the propagation environment. However, for mission
planning, you **choose one mode**, not interpolate — so SF7 and SF12 endpoints
are what you need.

### 4.3 Do we need a mid-SF (SF9, SF10)?

**No, for the balloon mission.** The balloon mission has two telemetry phases:
1. **Ascent/cruise (near):** FLRC-650 or SF7 — both work, FLRC preferred for
   throughput.
2. **Drift/descent (far):** SF7 if it reaches, SF12 if it doesn't.

There's no mission role for SF9 or SF10 — they're intermediate modes that
don't offer a compelling tradeoff. SF9 has ~6 dB less range than SF12 but
4× less airtime — not enough throughput gain to justify the complexity of
a third LoRa mode in the flight firmware.

**Exception:** If you're writing an academic paper on SF-vs-range curves, test
SF7, SF9, SF11, SF12. But for mission planning, 2 endpoints suffice.

### 4.4 What's missing from the 3-config proposal?

**Nothing critical for 868 MHz balloon mission planning.** The 3 configs cover:
- ✅ FLRC range + throughput (511B is worst case for sensitivity, best for throughput)
- ✅ LoRa operational mode (SF7, medium range, usable throughput)
- ✅ LoRa backup mode (SF12, max range, minimal throughput)
- ✅ Firmware self-reset validation (modulation switching: FLRC → LoRa → FLRC)

**Not covered (acceptable):**
- FLRC-2600 (dead at 218m, irrelevant for balloon)
- Mid-SF LoRa (no mission role)
- Small payload sizes (511B is conservative worst case)
- 2.4 GHz band (different hardware needed)

---

## 5. Distance Selection Analysis

### 5.1 The critical problem: distance spacing

The user's proposed distances (450m, 1.5km, 5km) have spacing of ~10 dB per step:

| Distance step | Ratio | Path loss delta |
|---------------|-------|-----------------|
| 218m → 450m   | 2.1×  | 6.5 dB          |
| 450m → 1.5km  | 3.3×  | 10.4 dB         |
| 1.5km → 5km   | 3.3×  | 10.4 dB         |

A radio cliff edge is typically **3-6 dB wide** (the transition from 0% to
100% PER). A 10 dB step **straddles the cliff without resolving it**:

```
RSSI:  ----[pass]----------|cliff|----------[fail]----
      450m                ↑ unresolved ↑          1.5km
```

You know the cliff is somewhere between 450m and 1.5km, but not where. That's
a 3.3:1 uncertainty — a factor of 3 in distance, which is huge for mission
planning.

**The doubling strategy** (6 dB steps) puts each step right at the cliff width:

| Distance step | Ratio | Path loss delta |
|---------------|-------|-----------------|
| 218m → 436m  | 2×   | 6 dB            |
| 436m → 872m  | 2×   | 6 dB            |
| 872m → 1744m | 2×   | 6 dB            |

With 6 dB steps, each cliff is bracketed to within 6 dB (one doubling), giving
a 2:1 distance resolution. Much tighter.

### 5.2 Analysis: 3 configs × 3 distances = 9 data points

With the user's distances (450m, 1.5km, 5km):

|          | FLRC-650 511B | LoRa SF7 255B | LoRa SF12 255B |
|----------|:---:|:---:|:---:|
| 450m     | Near cliff (~8 dB margin) — **informative** | Should pass (~23 dB) — low info | Trivial pass (~38 dB) — **wasted** |
| 1.5km    | Dead — **wasted** | Near cliff (~11 dB) — **informative** | Should pass (~26 dB) — low info |
| 5km      | Dead — **wasted** | Dead — **wasted** | Near cliff (~14-20 dB) — **informative** |

**Informative cells: 4 out of 9 (44%). Wasted cells: 5 out of 9 (56%).**

### 5.3 Can 9 points answer the key questions?

**a. Map the FLRC-650 cliff (need 2 points: one pass, one fail)**
- 218m: PASS (already confirmed with 64B)
- 450m: Near cliff, might pass or fail
- 1.5km, 5km: Will be dead — skipped
- **Result: 2 points if 450m fails (218m pass, 450m fail). Only 1 if 450m passes.**
- If 450m passes, cliff is > 450m but we have no fail point. **Insufficient.**

**b. Map the LoRa SF7 cliff (need 2 points)**
- 450m: Should pass (no LoRa range data yet — this is the FIRST real test)
- 1.5km: Near cliff
- 5km: Dead
- **Result: 2 points (450m pass, 1.5km pass/fail). If 1.5km fails, cliff is
  bracketed 450m-1.5km (10 dB, too wide). If 1.5km passes, no fail point.**

**c. Map the LoRa SF12 range (need 2 points)**
- 1.5km: Should pass
- 5km: Near cliff (at ground level with two-ray)
- **Result: 2 points. If 5km fails, cliff bracketed 1.5-5km (10 dB, too wide).
  If 5km passes, cliff > 5km (no bracket, but acceptable for balloon).**

**d. Disambiguate propagation model (FSPL vs two-ray)**
- Need 3+ RSSI points at different distances for the same config
- FLRC: 2 points max (218m, 450m) — can't fit a slope
- SF7: 2 points max (450m, 1.5km) — can't fit a slope
- SF12: 2 points max (1.5km, 5km) — can't fit a slope
- **Result: Insufficient. Need ≥3 RSSI points per config for slope fitting.**

### 5.4 Verdict on 9 points

**9 points is numerically sufficient but spatially misallocated.** The problem
isn't the count — it's that 5 of the 9 cells are wasted (trivial pass or certain
fail). The same 9 runs at better-chosen distances would answer all 4 questions.

---

## 6. Alternative: 4 Configs × 2 Distances vs 3 Configs × 3 Distances

### 4 configs (add FLRC-2600 511B at 2.4 GHz) × 2 distances (450m + 1.5km) = 8 points

**This is worse than 3 × 3 = 9 points. Reasons:**

1. **FLRC-2600 at 2.4 GHz is invalid on this hardware.** The E80-900MBL-02
   board's RF front end (matching network, PA, antenna) is tuned for 902-928
   MHz. At 2.4 GHz, expect 15-20 dB insertion loss in the matching network.
   You'd be measuring board incompetence, not radio performance. Need a
   different board for valid 2.4 GHz testing.

2. **2 distances can't bracket any cliff.** With only 2 distances per config,
   you get at most 1 pass + 1 fail = bracket. But the bracket width is 10.4 dB
   (450m to 1.5km), which is too wide for mission planning.

3. **No propagation slope.** 2 RSSI points per config can't distinguish FSPL
   (20 log d) from two-ray (40 log d or ~10 dB/octave). Need ≥3 points.

4. **8 points with 4 configs gives LESS info than 8 points with 3 configs at
   4 distances.** The 4th config (FLRC-2600 2.4 GHz) is invalid, so it's really
   3 configs × 2 distances = 6 valid points — worse than the 9-point plan.

**Verdict: 3 × 3 is better than 4 × 2. But 3 × 4 with selective skips is
better than both.**

---

## 7. Final Recommendation: Optimal Config × Distance Matrix

### 7.1 Recommended distances

Replace the user's 450m / 1.5km / 5km with **doubling distances** plus a
long-range SF12 probe:

| Stop | Distance | Justification |
|------|----------|---------------|
| D1   | 436m     | 2× from 218m baseline. FLRC cliff zone (8 dB margin for 64B, ~5-6 dB for 511B). First real LoRa range data. |
| D2   | 872m     | 2× from D1. FLRC should fail (~2 dB margin). SF7 should pass (~17 dB). SF12 easy (~32 dB). **Critical stop — resolves FLRC cliff.** |
| D3   | 1744m    | 2× from D2. SF7 cliff zone (~11 dB margin). SF12 comfortable (~26 dB). |
| D4   | 5000m    | SF12 cliff probe (~14-20 dB margin depending on propagation model). Distinguishes FSPL from two-ray. |

### 7.2 Optimal test matrix

|          | FLRC-650 511B | LoRa SF7 255B | LoRa SF12 255B | Runs/stop |
|----------|:---:|:---:|:---:|:---:|
| 436m     | **TEST** — near FLRC cliff, must resolve | **TEST** — first SF7 range data point | SKIP — 38 dB margin, trivially passes, 0 info | 2 |
| 872m     | **TEST** — FLRC cliff (pass/fail resolves cliff) | **TEST** — SF7 should pass, confirms range | **TEST** — first SF12 range data, baseline for slope | 3 |
| 1744m    | SKIP — 12+ dB past FLRC cliff, certainly dead | **TEST** — SF7 cliff zone (pass/fail resolves cliff) | **TEST** — SF12 mid-range, slope data point | 2 |
| 5000m    | SKIP — dead | SKIP — dead (5+ dB past SF7 cliff) | **TEST** — SF12 cliff probe, propagation model discriminator | 1 |

**Total: 8 test runs across 4 distances.**

### 7.3 What this matrix delivers

| Question | Answer | How |
|----------|--------|-----|
| FLRC-650 511B cliff | Bracketed to 6 dB (436-872m) | D1 pass + D2 pass/fail |
| LoRa SF7 255B cliff | Bracketed to 6 dB (872-1744m) | D2 pass + D3 pass/fail |
| LoRa SF12 255B range | Bounded: works to ≥1.7km (ground) | D2 + D3 both pass |
| SF12 cliff at 5km | Resolved (pass = cliff > 5km; fail = cliff 1.7-5km) | D4 |
| Propagation model | 4 RSSI points for SF12 (872, 1744, 5000m) → slope fit | D2 + D3 + D4 RSSI values |
| Throughput | FLRC-650 511B gives peak; SF7/SF12 255B give LoRa throughput | All test runs report kbps |
| Firmware self-reset | Validated: FLRC → LoRa → FLRC at 3 distances | Config ordering per stop |

### 7.4 Comparison: user's 9-run plan vs recommended 8-run plan

| Metric | User's plan (3 × 3) | Recommended (3 × 4, skip 4) |
|--------|:---:|:---:|
| Total runs | 9 | 8 |
| Informative runs | 4 (44%) | 8 (100%) |
| Wasted runs | 5 (56%) | 0 (0%) |
| FLRC cliff resolution | 6 dB (if 450m fails) or none | 6 dB (guaranteed) |
| SF7 cliff resolution | 10 dB (if 1.5km fails) or none | 6 dB (guaranteed) |
| SF12 cliff resolution | 10 dB (if 5km fails) or none | 6 dB or bounded (at 5km) |
| Propagation slope | Impossible (≤2 points/config) | 3-4 points for SF12 |
| Throughput data | 3 configs measured | 3 configs measured |

**The 8-run plan is strictly better: fewer runs, more information, all cliffs
guaranteed bracketed at 6 dB resolution.**

### 7.5 If only 3 stops are possible

If physical access limits to 3 stops, use **436m, 872m, 1744m** (drop the 5km
SF12 probe). This gives:

|          | FLRC-650 511B | SF7 255B | SF12 255B | Runs |
|----------|:---:|:---:|:---:|:---:|
| 436m     | TEST | TEST | SKIP | 2 |
| 872m     | TEST | TEST | TEST | 3 |
| 1744m    | SKIP | TEST | TEST | 2 |
| **Total** | | | | **7** |

All 3 cliffs bracketed at 6 dB. No SF12 cliff found (acceptable: confirms SF12
has >26 dB margin at 1.7km, which is ample for balloon at altitude). No
propagation slope (only 2 RSSI points per config — acceptable, can add 5km
later if needed).

### 7.6 Sanity check: 218m re-test

The user's existing 218m data is for 64B only. The 511B payload has never
been tested at range. Before driving to 436m, do a **2-minute sanity check
at 218m** with all 3 new configs (FLRC-650 511B, SF7 255B, SF12 255B). This
validates:
- Firmware self-reset works with 511B payload
- 511B doesn't have a surprise CRC issue (the RSSI cliff analysis noted
  a separate CRC bug at plen ≠ 255 in older firmware — confirm it's fixed)
- SF7/SF12 LoRa modulation switching works at range (never tested outside 0m)

**This is a 3-run quick check at a known location. If any config fails here,
fix the firmware before wasting field time at distant stops.**

### 7.7 Config ordering per stop (matters for LR2021 self-reset)

The LR2021 chip requires a self-reset when switching between FLRC and LoRa
modulation. The firmware (c70f582+) handles this automatically, but the order
matters for minimizing resets:

```
1. FLRC-650 511B  (FLRC mode)
   --- self-reset (FLRC → LoRa) ---
2. LoRa SF7 255B   (LoRa mode)
3. LoRa SF12 255B  (LoRa mode, SF change only — no full reset needed)
```

This ordering requires only 1 modulation switch per stop (FLRC → LoRa),
not 2. If testing SF7 then SF12, the chip stays in LoRa mode — only SF/BW
parameters change, which doesn't require a full chip reset.

### 7.8 Estimated field time

| Stop | Distance | Configs | Active time | Notes |
|------|----------|---------|-------------|-------|
| 218m | 0        | 3 (sanity) | ~8 min | Quick check, close to RX position |
| 436m | ~6 min drive | 2 | ~5 min | FLRC 35s + SF7 2 min |
| 872m | ~10 min drive | 3 | ~8 min | FLRC 35s + SF7 2 min + SF12 5 min |
| 1744m | ~15 min drive | 2 | ~7 min | SF7 2 min + SF12 5 min |
| 5000m | ~25 min drive | 1 | ~5 min | SF12 only |

**Total active test time: ~33 min. Total field time (incl. drive + setup): ~2.5 hours.**

Compare to user's 9-run plan: ~35 min active, ~2 hours field. Similar time,
but the 8-run plan delivers 2× the information.

---

## 8. Summary of Recommendations

1. **Max payload strategy is correct.** 511B FLRC and 255B LoRa are the
   conservative worst case for sensitivity. If they work, smaller payloads
   work. One payload per modulation is sufficient — no intermediate sizes
   needed. Bonus: 511B airtime >6 ms, which avoids the LR2021 AGC RSSI
   artifact and gives more accurate RSSI readings.

2. **Drop FLRC-2600 confirmed.** Dead at 218m at 868 MHz. 2.4 GHz testing
   needs different hardware (sub-GHz RF front end is useless at 2.4 GHz).

3. **3 configs are sufficient.** FLRC-650 511B, SF7 255B, SF12 255B cover
   the full operational envelope. No mid-SF needed for balloon mission
   planning.

4. **Replace 450m / 1.5km / 5km with 436m / 872m / 1744m / 5km.** Doubling
   distances give 6 dB cliff resolution. The user's 10 dB steps are too wide
   to resolve any cliff.

5. **Skip trivially-passing and certainly-dead cells.** This reduces 12
   potential cells to 8 actual runs — fewer than the user's 9, with more
   information.

6. **Add a 218m sanity check** (3 runs, 8 minutes) before field testing to
   validate firmware + 511B payload at a known-good distance.

7. **Final matrix: 8 runs at 4 distances + 3 sanity runs = 11 total.**
   All 3 cliffs bracketed at 6 dB. Propagation slope from 3-4 SF12 RSSI
   points. Throughput measured for all 3 configs.

---

## Appendix A: Existing Data Summary

### Valid test sessions

| Session | Distance | C0 FLRC-650 64B | C1 FLRC-2600 64B | C2 LoRa SF7 64B | C3 LoRa SF12 64B | C4 FLRC-650 255B |
|---------|----------|-----------------|-----------------|-----------------|------------------|-------------------|
| 2608231820 | ~0 m | 10/10 RSSI -24 | 10/10 RSSI -23 | 10/10 SNR 15 | 10/10 SNR 18 | 10/10 RSSI -21 |
| 2608232130 | ~0 m | 10/10 RSSI -52 | 10/10 RSSI -52 | 0/10 fw bug | 0/10 fw bug | 10/10 RSSI -60 |
| 2608232205 | ~218 m | 10/10 RSSI -91.5 | 0/10 dead | 0/10 fw bug | 0/10 fw bug | 0/10 cascade |

### Sensitivity estimates (from RANGE-TEST-PLAN-MINIMAL.md)

| Config | Sensitivity (est.) | Margin at 218m (-91.5 dBm) | Est. cliff distance |
|--------|--------------------|-----------------------------|---------------------|
| FLRC-650 64B | -105 dBm | 14 dB | ~872m (2 dB margin) |
| FLRC-650 511B | -102 dBm (−3 dB for payload) | 11 dB | ~700m (2 dB margin) |
| FLRC-2600 64B | -88.5 dBm | -3 dB (DEAD) | < 183m |
| LoRa SF7 64B | -120 dBm | 29 dB | ~3.5km (5 dB margin) |
| LoRa SF7 255B | -119 dBm (−1 dB for payload) | 28 dB | ~3.3km |
| LoRa SF12 64B | -135 dBm | 44 dB | ~14km (ground) |
| LoRa SF12 255B | -134 dBm (−1 dB for payload) | 43 dB | ~13km (ground) |

### RSSI at doubling distances (estimated, 6 dB per doubling from 218m)

| Distance | Est. RSSI | FLRC-650 511B (-102) | SF7 255B (-119) | SF12 255B (-134) |
|----------|-----------|----------------------|------------------|-------------------|
| 218m | -91.5 (measured) | 11 dB ✓ | 28 dB ✓ | 43 dB ✓ |
| 436m | -97.5 | 5 dB ✓ (near cliff) | 22 dB ✓ | 37 dB ✓ |
| 872m | -103.5 | -1 dB ✗ (cliff!) | 16 dB ✓ | 31 dB ✓ |
| 1744m | -109.5 | dead | 11 dB ✓ (near cliff) | 25 dB ✓ |
| 3488m | -115.5 | dead | 4 dB (cliff!) | 19 dB ✓ |
| 5000m | -119.0 | dead | dead | 15 dB ✓ (near cliff?) |

*Note: These are FSPL estimates. Ground-level two-ray propagation adds
~10 dB/octave beyond the break point (~400m at 1.5m antenna height at 868 MHz),
which would make the actual RSSI worse than these estimates at longer distances.
This is exactly what the 5km SF12 test will disambiguate.*

---

*End of analysis.*