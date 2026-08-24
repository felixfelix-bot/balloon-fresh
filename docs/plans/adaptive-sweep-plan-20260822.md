# Adaptive / Time-Optimal Sweep Plan — E80 bench + range campaign

Date: 2026-08-21/22. Status: DRAFT FOR OPERATOR REVIEW — not committed, no
code changed, no hardware touched. Companion docs: `docs/RANGE-TEST-PLAN.md`
(campaign protocol), `firmware/e80-stm32-bench/tools/e80_sweep_full.py`
(current orchestrator), `docs/rca-fix-plan-20260821.md` (fw evidence base).

## 0. Objective

Formalize the operator's intuition:

> "Would it make sense to sweep only the high throughput things when the
> signal quality is good and to regress to the more robust / low throughput
> things when we start hitting errors with the fast / high throughput
> measurements?"

**FULL sweeps stay unchanged** (baseline characterization; comparability
anchor). This plan adds focused host-side modes that maximize information per
minute, aimed at the range campaign (kanban t_8d7c52c8) where per-stop time is
the scarce resource (setup + walk + battery).

### Operator constraints honored

- **Host-side only.** Zero firmware changes. One verify-only fw dependency
  (mid-burst `STOP` semantics) with a no-fw fallback (§7).
- **ECON: DEFER > downgrade.** Nothing existing is modified; new modes are
  additive (`tools/e80_campaign.py` sibling). Reset-relaxation is *gated*
  behind an A/B bench validation, not assumed.
- **Honest cost estimates.** All time numbers derive from measured sweep
  timing (61-cfg 868 sweep = 42 min ≈ 41 s/cfg; SF12 BW125 ≈ 90 s ≈ 1.5–1.8
  s/pkt airtime-bound; FLRC ≈ 15 s reset-overhead-bound; reset+reconfig
  overhead R ≈ 10–15 s/cfg).
- **Percentile/CI gates.** Decisions are stated as binomial CI statements,
  matching the RANGE-TEST-PLAN Wilson-CI convention.

---

## 1. Modes

| Mode | Purpose | Configs | Pkt tier | When |
|---|---|---|---|---|
| **FULL** | Baseline characterization — UNCHANGED | 61 (868) / 113 (dual) | 50 fixed | bench, pre/post campaign |
| **CAMPAIGN-PROBE** | Link-state classification at a stop | 2 | SPRT ≤20 | every range stop, first |
| **CAMPAIGN-GOOD** | Throughput matrix (clean link) | ~25 | SPRT ≤20, reset-skip | probe verdict CLEAN |
| **CAMPAIGN-DEGRADED** | Robustness ladder + telemetry (poor link) | ~8 | SPRT ≤20 | probe verdict DEAD |
| **CLIFF-SEARCH** | Localize PER cliff on SF axis | ~5 probes | SPRT ≤20 | EDGE verdict, or core range deliverable |

### 1.1 CAMPAIGN-PROBE (the branch decider)

Two canaries, ~1 min total:

1. `LoRa SF7 BW125 LEN=51 PA=<stop plan>` — mid/fast telemetry reference,
   ~0.23 s/pkt incl. gap. Sensitive in both directions (dies before FLRC,
   survives after FLRC dies).
2. `FLRC BR650 LEN=51` — fast-path canary, ~12 ms/pkt (reset-bound; ~2 s of
   airtime total).

Verdict thresholds (SPRT with p₀=2%, p₁=20%, §3):

- **CLEAN** (PER ≲ 2%, 95% conf) → CAMPAIGN-GOOD
- **DEAD** (PER ≳ 20%) on the SF7 probe → CAMPAIGN-DEGRADED
- **EDGE** (gray zone: SPRT undecided at n=20) → CLIFF-SEARCH first, then
  the degraded ladder.

Rule of thumb mapping to the operator's thresholds: PER<2% → good,
PER>20% → degraded, 2–20% → edge.

### 1.2 CAMPAIGN-GOOD (throughput matrix, clean link)

- FLRC BR ladder {650, 1300, 2600} × LEN {128, 255, 511} (9) + fine BR
  {325, 520, 1040, 2080} @ LEN255 (4)
- LoRa fast set SF{5,6,7} × BW{125,500} × LEN{128,255} (12)
- Optional 2.4 GHz mini-matrix if the stop is dual-band (flag: skip-list will
  prune it fast at range; 2.4 G dies early)

~25 configs, early-stop (clean ⇒ 15 pkts), reset-skip inside each mod section
(2–3 resets total). Est. **4–6 min**.

### 1.3 CAMPAIGN-DEGRADED (robustness ladder, poor link)

- SF {9,10,11,12} BW125 LEN=16 (4) [LEN=32 variant optional]
- PA margin cells: SF10 LEN16 × PA {0, 5, 22-outdoor} (3)
- FLRC-260 dead-check (1; expected DEAD ⇒ costs 10 pkts)
- RSSI/SNR telemetry: per-packet fields already in PKT lines — no extra
  configs, no extra time. Report slope-only usage per RANGE-TEST-PLAN §3.

Est. **4–5 min** worst case (all-clean at 20 pkts); ~3 min with dead early-stops.

### 1.4 CLIFF-SEARCH (range campaign core deliverable)

Find the smallest SF (fastest config) with PER ≤ target on the SF5–12 axis at
BW125, plus the FLRC-vs-LoRa boundary (1 probe: FLRC-650):

```
test SF5   (fast sentinel):  DEAD  → cliff is below SF5: no fast LoRa; report
test SF12  (robust sentinel): CLEAN → whole axis clean at this stop; done
bisect between sentinels:    while hi-lo > 1:
                                 mid; verdict = sprt(axis[mid])
                                 CLEAN → hi = mid ; DEAD → lo = mid
validate: full-tier (n = tier cap) at axis[lo] and axis[hi]
          → local monotonicity spot-check before trusting the boundary
```

Expected cost: 2 sentinels + ~3 bisections ≈ 5 probes ≈ **2.5–3.5 min**
(SF12 probe dominates: 20 × 2.55 s + R ≈ 63 s).

**Probe order justification**: binary search on a monotone axis is
info-theoretically optimal (⌈log₂ 9⌉ = 4 decisions + 2 sentinels for
bracketing). Starting at the *fast* end first also front-loads the
throughput-relevant answer (operator's priority).

**Where monotonicity breaks** (why sentinels + validation are mandatory):

- **Multipath nulls**: channel is frequency-selective; BW125 vs BW500 sample
  different fade depths → PER(BW) ordering can invert; PER(SF) at fixed BW is
  mostly monotone but a deep null shifts the SNR operating point enough for
  local inversions.
- **Near-field saturation (S0)**: RX front-end/AGC saturation destroys the
  sensitivity-vs-SF ordering.
- **Fresnel/grazing geometry (S5-type stops)**: ground reflection alternates
  constructive/destructive with position → PER vs distance is locally
  non-monotone (a farther stop can be cleaner).
- **Cross-band**: 868 and 2.4 GHz are independent ladders; never carry a
  verdict across bands.

---

## 2. Adaptive controller pseudocode (host-side)

New sibling tool `tools/e80_campaign.py`; imports helpers from
`e80_sweep_full.py` (§6). Reuses unchanged: CH340 auto-detect + radio
handshake ID, incremental CSV append, SESSION/CONFIG tagging, adaptive gap,
SWD reset machinery, PRBS bit_err integrity.

```python
# ---- one-time constants ----
SPRT = dict(p0=0.02, p1=0.20, alpha=0.05, beta=0.05, n_min=10, n_cap=20)
TIER = dict(full=50, campaign=20, probe=20)      # pkt-count tiering, §5

def sprt_run(cfg, tier, policy=SPRT):
    """Arm ONE burst at n_cap, stream RX PKT lines, decide early."""
    reset_if_policy_requires(cfg)                 # §4 reset-skip
    issue_console_config(cfg)                     # MOD/PA/FREQ/SESSION/CONFIG
    arm_and_start(N=policy["n_cap"], LEN=cfg.plen, GAP=adaptive(cfg))
    k = n = 0
    for pkt in stream_rx_pkts(expected_config=cfg.idx):   # tag-filtered
        n += 1
        k += 1 if pkt.bit_err > 0 else 0          # PRBS primary (FLRC CRC pre-fix)
        if n >= policy["n_min"]:
            llr = k*ln(p1/p0) + (n-k)*ln((1-p1)/(1-p0))
            if llr <= ln(beta/(1-alpha)): stop_tx(); return CLEAN(k, n)
            if llr >= ln((1-beta)/alpha): stop_tx(); return DEAD(k, n)
    return EDGE(k, n)                             # gray zone → full-tier data

def stop_at_distance(d, state):
    site_preflight()                              # RANGE-TEST-PLAN §1 checklist
    v_sf7  = sprt_run(PROBE_SF7,  "probe")
    v_flrc = sprt_run(PROBE_FLRC, "probe")
    verdict = branch(v_sf7, v_flrc)               # GOOD / DEGRADED / EDGE
    if verdict == GOOD:
        run_matrix(CAMPAIGN_GOOD, skip=skip_list(state, d))   # §4 carry-forward
    elif verdict == EDGE:
        cliff = cliff_search(SF_AXIS, d)                       # §1.4
        run_ladder(CAMPAIGN_DEGRADED)
    else:  # DEGRADED
        run_ladder(CAMPAIGN_DEGRADED)
        cliff_search(SF_AXIS, d)
    run_anchors(state, d)     # 1–2 configs at EVERY stop (monotonicity tripwire)
    state.commit(d)           # persist verdicts for carry-forward; crash-safe JSON
```

Notes:
- `stop_tx()` sends the fw `STOP` console command to the TX board and drains.
  **Verify-only fw dependency**: confirm `STOP` cleanly aborts an armed burst
  (RANGE-TEST-PLAN §1.7 already assumes a STOP path exists). Fallback if not:
  skip mid-burst abort, arm at the tier count directly (10/15/20) — keeps
  ~70% of the savings, zero fw work.
- All PKT accounting is per-packet from RX console lines (not `STAT?`
  counters), so reset-skip cannot contaminate counts (§4).

---

## 3. Statistical justification (SPRT, simple form)

Wald sequential probability ratio test on the per-packet error indicator,
H0: PER = p₀ = 0.02 vs H1: PER = p₁ = 0.20, α = β = 0.05:

- Per-packet log-likelihood ratio: an **error** adds `ln(p₁/p₀) = +2.303`;
  a **success** adds `ln(0.80/0.98) = −0.203`.
- Boundaries: CLEAN when LLR ≤ `ln(β/(1−α)) = −2.944`; DEAD when
  LLR ≥ `ln((1−β)/α) = +2.944`.

Decision table (deterministic given the error path):

| Errors k | Min n → CLEAN | Min n → DEAD (with n_min=10 floor) |
|---|---|---|
| 0 | **15** | — |
| 1 | 27 | — |
| 2 | 40 | — |
| = n (all err) | — | **10** (raw SPRT crosses at n=2; floor guards RX-arm latency / first-pkt loss) |

Packet cost vs fixed 50 (bench-relevant truth values):

| True PER | Expected pkts | Saving |
|---|---|---|
| 0.00 (clean) | 15 | **70%** |
| 0.50 | ~10–12 (drift 1.05/pkt toward DEAD, floor 10) | **~78%** |
| 1.00 (dead) | 10 | **80%** |
| 0.05–0.15 (gray zone) | runs to tier cap (20 campaign / 50 full) | ~0% — honest: SPRT saves only at the extremes, which is exactly the bench/range reality (configs are 0/50 or 50/50) |

Error indicator: `bit_err > 0` (PRBS-15) — primary; `crc_ok` secondary only
(chip CRC unreliable for FLRC pre-Match123-fix, per RCA).

Guard against i.i.d. violation (bursty channel memory): n_min=10 floor +
final Wilson CI recomputed on the stopped sample + anchors (§4). SPRT error
rates hold under i.i.d.; burstiness widens effective α — acceptable for a
*branching* decision that is re-checked by the branch content itself.

---

## 4. Cross-distance skip-list + reset policy

### 4.1 Monotone carry-forward

- Config proven **DEAD at distance d** ⇒ skip at all d′ > d (annotate
  carry-forward in CSV).
- Config proven **CLEAN at d** ⇒ skip retest at d′ < d.
- **Anchors at every stop** (FLRC-650 + SF7): if an anchor contradicts a
  carry-forward prediction → monotonicity violated at this leg → invalidate
  skips, retest the affected configs (multipath/Fresnel tripwire, §1.4).

Model estimate, 8 stops × 20 configs (cliff positions spread over stops 2–7):

- Naive: 160 cells × 50 pkts × ~41 s ≈ **109 min**.
- Adaptive: branch pruning (GOOD stops never run the ladder; DEGRADED stops
  never run the throughput matrix) + carry-forward + SPRT + reset-skip ⇒
  ~90–105 cheaper cells (≈18 s avg) ≈ **28–35 min**.
- **Headline: ~65–75% campaign-time saving (≈3×)**, with the model's
  assumptions stated (uniform cliff spread, monotonicity holding).

### 4.2 Reset-overhead reduction (gated)

Current: SWD reset both boards every config (R ≈ 10–15 s of the ~41 s avg;
FLRC configs are ~90% reset overhead). Proposal:

- **Reset REQUIRED**: mod transition (lora↔flrc), band change, any error/
  unresponsive event, every new distance stop, before PA-22 cells.
- **Reset SKIPPABLE (after A/B gate)**: same-mod adjacency (SF/BW/LEN/PA via
  console). Console `MOD`/`PA`/`FREQ` fully re-parameterize the radio each
  time; per-config PKT lines carry the config tag so stale packets are
  host-filterable; per-packet accounting removes `STAT?` counter bleed.
- Evidence for feasibility: the SF11/12 overrun was fixed by *timing*
  (adaptive gap), not by reset — radio state per config is not the failure
  mode. Residual risk: fw never calls `fifo_clear_rx` (RCA H2) — stale FIFO
  contents; mitigated by tag filtering + drain before START.
- Synergy: `BAND OVERRIDE` is RAM-resident and dies on every SWD reset —
  reset-skip in 2.4 GHz sections *removes* per-config re-arming.

**A/B validation (bench, gate before any range use):** identical 10-config
sequence (fast FLRC + SF11/12 mix), run (A) with per-config resets and (B)
with same-mod reset-skip, twice each. Acceptance: identical CLEAN/DEAD
verdicts; PER point estimates inside overlapping Wilson CIs; zero
foreign-config-tag PKTs in B; RSSI/SNR means shift < 1 dB; SF11/12 50-pkt
burst mid-sequence still overrun-free (regression for the gap fix).

Savings if gated in: FLRC/fast configs 15 s → ~3–5 s (−60–70%); GOOD matrix
~25 configs: ~6 min → ~3 min.

---

## 5. Packet-count tiering (CI justification)

Wilson 95% CI widths (the "what do we actually know" table):

| n | k | p̂ | Wilson 95% CI | Use |
|---|---|---|---|---|
| 50 | 0 | 0% | [0, 7.1%] | FULL characterization (unchanged) |
| 50 | 25 | 50% | [36.5, 63.5%] | FULL mid-PER resolution |
| 20 | 0 | 0% | [0, 16.1%] | campaign clean claim (classification, not precision) |
| 20 | 2 | 10% | [2.8, 30.1%] | campaign edge — coarse |
| 20 | 10 | 50% | [29.9, 70.1%] | campaign edge — coarse |
| 15 | 0 | 0% | [0, 20.4%] | SPRT clean stop point |
| 10 | 10 | 100% | [72.3, 100%] | SPRT dead stop point |

- **FULL = 50** (unchanged): ±7% at 0-err, ±13.5% at mid-PER.
- **CAMPAIGN = 20** (SPRT cap): sufficient for 2%/20% *classification* and
  cliff localization; NOT sufficient for precise PER curves — edge cells that
  matter get promoted to 50 (cliff validation step does exactly this).
- **PROBE = 20 cap / 10 floor**: only ever feeds the branch decision, which
  the branch content re-checks.

If the campaign deliverable must quote "PER < 1% with ci_hi < 1%" (RANGE-TEST
PLAN §3 convention), that stays with the existing N=10³/10⁴ cells in
`e80_bench_ctl.py` — this plan's tiers are for the *search*, not the
*certificate*.

---

## 6. Time budget per distance point (868 MHz)

| Mode stack | Configs | Pkts/cfg | Est. time |
|---|---|---|---|
| FULL sweep (baseline, unchanged) | 61 | 50 fixed | **~42 min** |
| FULL dual-band | 113 | 50 fixed | ~75 min |
| Naive 20-cfg campaign @ 50 fixed | 20 | 50 | ~14 min |
| CAMPAIGN-PROBE | 2 | SPRT ≤20 | **~1 min** |
| PROBE + CAMPAIGN-GOOD | 2+25 | SPRT ≤20, reset-skip | ~5–7 min |
| PROBE + CAMPAIGN-DEGRADED | 2+8 | SPRT ≤20 | ~5–6 min |
| PROBE + CLIFF-SEARCH (+ladder if EDGE) | 2+5(+8) | SPRT ≤20 | ~4–9 min |

**Typical adaptive stop: 5–9 min vs 42 min FULL (≈5–8×) or ~14 min naive
20-cfg (≈2–3×).** Derivation: R ≈ 12 s/config (2× openocd + sleeps + console
reconfig); burst time = pkts × (airtime + gap) from measured per-packet times
(SF7/51B ≈ 0.23 s, SF12/16B ≈ 2.55 s, FLRC/51B ≈ 12 ms); SPRT clean=15,
dead=10, gray=cap.

---

## 7. What changes in `e80_sweep_full.py` (function-level)

**Preferred: nothing.** New sibling `tools/e80_campaign.py` (~250–290 LOC)
imports `find_ch340_ports`, `identify_boards`, `cmd`, `drain_lines`,
`parse_pkt`, `swd_reset`, `lora_airtime_s`, `flrc_airtime_s`. Minor
import-friendliness tweaks in `e80_sweep_full.py` (~10 LOC):

| Change | Function | LOC |
|---|---|---|
| `NPKTS` global → parameter with default 50 (START line + wait_s) | `run_config()` | ~8 |
| expose `run_config` burst phase as reusable `arm_and_stream()` | refactor | ~20 |
| guard: none needed (`if __name__` already exists) | `main()` | 0 |

New code in `e80_campaign.py` (all host-side):

| Function | Purpose | LOC |
|---|---|---|
| `sprt_decide(k, n, p)` | boundary math, verdict | ~20 |
| `sprt_run(cfg)` | arm cap-N burst, stream, early-stop, `stop_tx()` | ~50 |
| `stop_tx()` | fw STOP + drain (**verify-only fw dependency**, §2) | ~15 |
| `maybe_reset(prev, cur)` | reset policy gate (mod/band/error) | ~15 |
| `build_campaign_configs(mode)` | probe/good/degraded/cliff sets | ~70 |
| `cliff_search(axis, d)` | sentinel+bisect+validate | ~45 |
| campaign state (JSON load/commit, carry-forward DB, crash-safe) | `state` | ~40 |
| CLI (`--mode --stop-policy --reset-policy --tier`) + MD report | `main()` | ~45 |

**Firmware changes: NONE.** Flagged verify-only: mid-burst `STOP` abort
semantics (fallback = fixed-N tiering, no fw work).

---

## 8. Risks + validation plan

| # | Risk | Likelihood | Mitigation / gate |
|---|---|---|---|
| R1 | SPRT misclassification under bursty (non-i.i.d.) errors | medium | n_min=10 floor; Wilson on final sample; branch content re-checks the verdict; anchors |
| R2 | Monotonicity violations at range (multipath nulls, Fresnel, S0 saturation) corrupt skip-list | medium | sentinel+validate in cliff-search; anchors every stop; contradiction → invalidate + retest rule (§4.1) |
| R3 | Reset-skip state bleed (stale RX FIFO per RCA H2, counter bleed) | medium | PKT config-tag filtering; per-packet accounting; A/B gate (§4.2) BEFORE any range use; resets kept on mod/band change |
| R4 | `STOP` doesn't abort armed burst cleanly | unknown | bench verify first; fallback fixed-N tiers (keeps ~70% of savings) |
| R5 | Reduced inference scope mistaken for full characterization | process | CSV `mode=` column on every row; report states classification-tier CIs (§5) |

**Validation ladder (bench, before range):**

- **V1 — Equivalence:** run FULL sweep, then adaptive modes on the same bench
  rig. Accept: 100% CLEAN/DEAD agreement on all shared configs; PER point
  estimates within overlapping Wilson CIs.
- **V2 — Reset A/B:** §4.2 protocol (2×2 runs). Accept per stated gates.
- **V3 — Regression:** SF11/12 50-pkt overrun check mid-sequence without
  resets (protects the gap-adaptive fix).
- **V4 — Rehearsal:** dry-run campaign controller on host tests (no HW) —
  branch logic, crash-resume, carry-forward DB.

Only after V1–V4 pass do adaptive modes go to range, and FULL sweeps remain
the periodic cross-check (e.g., one FULL per campaign day).

---

## 9. Operator decisions — RESOLVED 2026-08-22 (Felix, balloon-hermes)

1. **STOP semantics**: YES — bench-verify fw STOP mid-burst abort (task ADAPT-0).
   Fallback if broken: fixed-N tiering (keeps ~70% savings).
2. **Cliff edge precision**: boundary cells VALIDATED AT n=50 (the campaign's
   key deliverable gets characterization-grade CIs; interior search stays SPRT ≤20).
3. **Campaign bands**: DUAL-BAND stops (868 + 2.4G). Skip-list prunes 2.4G
   fast at range; per-stop probe cost accepted.
4. **Walk order**: NOT guaranteed. Controller must be symmetric — branch
   decision comes from the probe verdicts, never from position in the walk.
   Carry-forward DB works both directions (DEAD@d skips d'>d AND d'<d-carried
   CLEAN; anchors re-check either way). No near→far prior anywhere in code.
5. **PA ramp**: KEPT unchanged (safety rule: PA0 link check → PA10 → PA22
   only past 50m, never 0→22). SPRT applies per-cell only (PA0 dead check
   costs 10 pkts not 50). PA-22 cells always reset-guarded.
6. **Anchor set**: APPROVED — FLRC-650 + SF7 every-stop tripwires (~40 s/stop).

## Verification gates (this document)

- Written to `docs/plans/adaptive-sweep-plan-20260822.md`; NOT committed
  (manager/operator review first).
- No hardware access, no firmware changes, no sweep tool modifications.
