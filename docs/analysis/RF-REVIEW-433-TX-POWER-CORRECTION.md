# CORRECTION — the 10 mW ERP cap does NOT break the 300 km link (27.3 dB margin remains)

**Date:** 2026-10-14 · **Status:** CORRECTION of `RF-REVIEW-433-TX-POWER.md` §1's range table.
**Supersedes:** that document's claim that *"the 300 km design slant range is not reachable
at 10 mW ERP — it becomes ~27 km."* **That was WRONG.** Here is the measured correction.

---

## 0. What I got wrong

In `RF-REVIEW-433-TX-POWER.md` I applied a **20.9 dB power reduction** to the range with
`range ∝ 10^(−Δ/20)` and concluded the 300 km design collapses to ~27 km.

**I conflated "range at which the link is at zero margin" with "the design range".** The
correct question is not *"how far does 20.9 dB less power reach?"* — it is *"does the link
still close at the design distance with the power we are allowed?"* It does, because the
original design had **enormous margin to spare**.

## 1. The measured result — repo's own `tools/link_budget.py`

**433 MHz DOWNLINK at the licence-exempt cap** (`--tx 12` dBm EIRP, balloon antenna
+2 dBi, ground RX **12 dBi** Yagi, 1 dB cable, SF12 / BW125):

| distance | RX power | sensitivity | **link margin** | feasible |
|---:|---:|---:|---:|:--:|
| 27 km | −88.8 dBm | −137.0 dBm | **48.2 dB** | YES |
| 50 km | −94.2 dBm | −137.0 dBm | **42.8 dB** | YES |
| 100 km | −100.2 dBm | −137.0 dBm | **36.8 dB** | YES |
| **300 km** | **−109.7 dBm** | −137.0 dBm | **27.3 dB** | **YES** |
| *(max range at the cap)* | | | | **6934 km** |

**For contrast, the 2 W design at 300 km:** link margin **48.4 dB**.

**So the cap costs 21.1 dB of margin — and 27.3 dB of margin still remains at 300 km.**
The link closes comfortably at lawful power.

## 2. Why the margin table and the range rule disagree — and which to trust

My flat "range × 0.0907" rule is **only valid for a link at zero margin**. Applying it to a
link with 48 dB of margin is meaningless: you spend the margin *before* you lose range.

**The proper relation** for a link with power change ΔP:

```
new_max_range = old_max_range × 10^(ΔP/20)
```

The 2 W design's **computed max range is 79 161 km** (it is a wildly over-provisioned
link — SF12 at 293 bps). 20.9 dB less power gives:

```
79161 × 10^(−20.9/20) = 79161 × 0.0907 = 7180 km
```

and the tool independently reports **6934 km** at +12 dBm EIRP. **They agree** (the small
difference is my 12 dBm rounding vs the tool's 13.0 dBm EIRP).

**Both numbers say the same thing: at the lawful cap the link still reaches thousands of
km.** The 300 km design point has **27.3 dB of margin**, which is a healthy link.

## 3. What the correction does NOT change

- **The regulatory gap is real and unchanged: the design's +33 dBm is 20.9 dB over the
  10 mW ERP licence-exempt cap.** That remains the open item, and it remains a "can it fly
  legally" question rather than a physics one.
- **The mission is not actually range-limited by the cap.** This is good news and it
  **strengthens** the case for simply **operating within the cap**: we give up 21 dB of a
  48 dB margin and keep 27 dB at 300 km.
- **The F33 question changes shape.** The previous document suggested the F33 (2 W) might
  not be worth populating. **That conclusion needs re-examination:** if the bare LoRa2021 at
  **+22 dBm** also exceeds the 10 mW ERP cap (it does — by ~10 dB), then *neither* part is
  licence-free lawful at full power, and the F33's extra 11 dB buys margin we do not need
  at 300 km. **So the argument for the cheap part is stronger, not weaker.**

## 4. The honest lesson

I published a range claim from a **rule of thumb applied outside its validity domain** — a
flat dB-to-range factor is for zero-margin links, and this link has 48 dB of margin. The
repo's own tool would have told me immediately, and **I should have run it before writing
the range table.** Recording it because the campaign's whole method is *measure, don't
assert* — and here I asserted.

## 5. Reproduce

```
cd tracker/..  # repo root
# at the licence-exempt cap
python3 tools/link_budget.py --freq 433 --sf 12 --bw 125 \
    --tx 12 --tx-ant 2 --rx-ant 12 --cable-loss 1 --dist 300
# -> Link Margin: 27.3 dB OK   Max Range: 6934 km

# the 2 W design
python3 tools/link_budget.py --freq 433 --sf 12 --bw 125 \
    --tx 33 --tx-ant 2 --rx-ant 12 --cable-loss 1 --dist 300
# -> Link Margin: 48.4 dB OK   Max Range: 79161 km
```
