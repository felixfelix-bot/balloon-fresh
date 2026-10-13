#!/usr/bin/env python3
"""e80_campaign.py — adaptive / time-optimal sweep controller for E80 bench.

Implements the adaptive campaign plan (docs/plans/adaptive-sweep-plan-20260822.md):
  - SPRT early-stop (§3): CLEAN/DEAD/EDGE verdicts per config
  - Campaign modes (§1): PROBE, GOOD, DEGRADED, CLIFF, FULL-STOP
  - Carry-forward state DB (§4.1): DEAD/CLEAN skips, anchor contradiction
  - Walk-order-symmetric (D4): no near/far prior in code
  - Dual-band stops (D3): 868 + 2.4G probe pairs
  - Boundary validation at n=50 (D2)
  - Anchors: FLRC-650 + SF7 every stop (D6)

Imports helpers from e80_sweep_full.py (§7): find_ch340_ports, identify_boards,
cmd, drain_lines, parse_pkt, swd_reset, lora_airtime_s, flrc_airtime_s,
arm_and_stream.

CLI: --mode probe|good|degraded|cliff|full-stop --band 868|2g4|both
     --reset-policy strict|gated --tier --stop-id

NO hardware in tests — all HW interaction is in sprt_run/stop_at_distance
which are thin wrappers over e80_sweep_full serial helpers.
"""

import math
import os
import sys
import json
import time
import csv
from datetime import datetime
from collections import namedtuple

# ---- e80_sweep_full imports (§7) ----
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import e80_sweep_full as sw  # noqa: E402

# ---- Constants (plan §3, §5) ----

SPRT = dict(p0=0.02, p1=0.20, alpha=0.05, beta=0.05, n_min=10, n_cap=20)

TIER = dict(full=50, campaign=20, probe=20)

# SPRT boundaries (plan §3): ln(beta/(1-alpha)), ln((1-beta)/alpha)
_LLR_LOW = math.log(SPRT["beta"] / (1 - SPRT["alpha"]))    # -2.944
_LLR_HIGH = math.log((1 - SPRT["beta"]) / SPRT["alpha"])    # +2.944
_LLR_ERR = math.log(SPRT["p1"] / SPRT["p0"])                # +2.303
_LLR_OK = math.log((1 - SPRT["p1"]) / (1 - SPRT["p0"]))     # -0.203

# Wilson z for 95% CI
_Z95 = 1.959964

VERDICTS = ("CLEAN", "DEAD", "EDGE", "UNDECIDED")

# Frequency constants (from e80_sweep_full)
FREQ_868 = sw.DEFAULT_FREQ       # 868000000
FREQ_2G4 = sw.DEFAULT_FREQ_2G4   # 2440000000

# SF axis for cliff search (plan §1.4)
SF_AXIS = [5, 6, 7, 8, 9, 10, 11, 12]

# ---- Data types ----

SprtResult = namedtuple("SprtResult", ["verdict", "k", "n"])
CliffResult = namedtuple("CliffResult", ["boundary_lo", "boundary_hi",
                                          "summary", "validations"])


# ---- SPRT (plan §3) ----

def sprt_decide(k, n, policy=None):
    """Wald SPRT decision on k errors in n packets.

    Returns SprtResult(verdict, k, n).
    - CLEAN: LLR <= ln(beta/(1-alpha))  AND n >= n_min
    - DEAD:  LLR >= ln((1-beta)/alpha)  AND n >= n_min
    - EDGE:  undecided at n >= n_cap (gray zone)
    - UNDECIDED: below n_min or below n_cap without crossing
    """
    p = policy or SPRT
    if n < p["n_min"]:
        return SprtResult("UNDECIDED", k, n)
    llr = k * _LLR_ERR + (n - k) * _LLR_OK
    if llr <= _LLR_LOW:
        return SprtResult("CLEAN", k, n)
    if llr >= _LLR_HIGH:
        return SprtResult("DEAD", k, n)
    if n >= p["n_cap"]:
        return SprtResult("EDGE", k, n)
    return SprtResult("UNDECIDED", k, n)


# ---- Wilson CI (plan §5) ----

def wilson_ci(k, n, z=_Z95):
    """Wilson score interval for k successes in n trials.

    Returns (lo, hi) as fractions [0, 1].
    k = error count, n = total packets (all are "trials", k are "errors").
    """
    if n == 0:
        return 0.0, 1.0
    p_hat = k / n
    denom = 1 + z * z / n
    center = (p_hat + z * z / (2 * n)) / denom
    margin = z * math.sqrt(p_hat * (1 - p_hat) / n + z * z / (4 * n * n)) / denom
    lo = max(0.0, center - margin)
    hi = min(1.0, center + margin)
    return lo, hi


# ---- Campaign config builders (plan §1.1–§1.4) ----

def _gap_for_lora(sf, bw, plen):
    toa = sw.lora_airtime_s(sf, bw, plen)
    return max(10000, int(1.2 * toa * 1e6) + 5000)


def _gap_for_flrc(br, plen):
    return 10000  # FLRC gap floor 10ms


def _probe_configs(freq):
    """2 canaries: FLRC-650 + LoRa SF7 (D6 anchors)."""
    return [
        dict(mod="flrc", br=650, pa=5, freq=freq, plen=51,
             gap=_gap_for_flrc(650, 51), label=f"PROBE FLRC-650 @{freq/1e6:.0f}"),
        dict(mod="lora", sf=7, bw=125, pa=10, freq=freq, plen=51,
             gap=_gap_for_lora(7, 125, 51), label=f"PROBE SF7 BW125 @{freq/1e6:.0f}"),
    ]


def _good_configs(freq):
    """~25 throughput matrix configs (plan §1.2)."""
    cfgs = []
    # FLRC BR ladder {650,1300,2600} × LEN {128,255,511} = 9
    for br in (650, 1300, 2600):
        for plen in (128, 255, 511):
            cfgs.append(dict(mod="flrc", br=br, pa=5, freq=freq, plen=plen,
                             gap=_gap_for_flrc(br, plen),
                             label=f"GOOD FLRC-{br}k L{plen}"))
    # Fine BR {325,520,1040,2080} @ LEN255 = 4
    for br in (325, 520, 1040, 2080):
        cfgs.append(dict(mod="flrc", br=br, pa=5, freq=freq, plen=255,
                         gap=_gap_for_flrc(br, 255),
                         label=f"GOOD FLRC-{br}k L255"))
    # LoRa fast set SF{5,6,7} × BW{125,500} × LEN{128,255} = 12
    for sf in (5, 6, 7):
        for bw in (125, 500):
            for plen in (128, 255):
                cfgs.append(dict(mod="lora", sf=sf, bw=bw, pa=10, freq=freq,
                                 plen=plen, gap=_gap_for_lora(sf, bw, plen),
                                 label=f"GOOD SF{sf} BW{bw} L{plen}"))
    return cfgs


def _degraded_configs(freq):
    """~8 robustness ladder configs (plan §1.3)."""
    cfgs = []
    # SF {9,10,11,12} BW125 LEN=16 = 4
    for sf in (9, 10, 11, 12):
        cfgs.append(dict(mod="lora", sf=sf, bw=125, pa=10, freq=freq, plen=16,
                         gap=_gap_for_lora(sf, 125, 16),
                         label=f"DEG SF{sf} BW125 L16"))
    # PA margin cells: SF10 LEN16 × PA {0, 5, 22} = 3
    for pa in (0, 5, 22):
        cfgs.append(dict(mod="lora", sf=10, bw=125, pa=pa, freq=freq, plen=16,
                         gap=_gap_for_lora(10, 125, 16),
                         label=f"DEG SF10 BW125 PA{pa} L16"))
    # FLRC-260 dead-check = 1
    cfgs.append(dict(mod="flrc", br=260, pa=5, freq=freq, plen=51,
                     gap=_gap_for_flrc(260, 51),
                     label="DEG FLRC-260 dead-check"))
    return cfgs


def _cliff_configs(freq):
    """Cliff search axis: SF5–SF12 at BW125 (plan §1.4)."""
    cfgs = []
    for sf in SF_AXIS:
        cfgs.append(dict(mod="lora", sf=sf, bw=125, pa=10, freq=freq, plen=51,
                         gap=_gap_for_lora(sf, 125, 51),
                         label=f"CLIFF SF{sf} BW125"))
    return cfgs


def build_campaign_configs(mode, band="868"):
    """Build config set for a campaign mode.

    mode: probe, good, degraded, cliff, full-stop
    band: 868, 2g4, both (D3 dual-band)
    Returns list of config dicts.
    """
    if mode == "full-stop":
        return sw.build_configs()  # delegate to FULL sweep

    freqs = []
    if band in ("868", "both"):
        freqs.append(FREQ_868)
    if band in ("2g4", "both"):
        freqs.append(FREQ_2G4)

    cfgs = []
    for freq in freqs:
        if mode == "probe":
            cfgs.extend(_probe_configs(freq))
        elif mode == "good":
            cfgs.extend(_good_configs(freq))
        elif mode == "degraded":
            cfgs.extend(_degraded_configs(freq))
        elif mode == "cliff":
            cfgs.extend(_cliff_configs(freq))
        else:
            raise ValueError(f"unknown mode: {mode}")
    return cfgs


# ---- Reset policy (plan §4.2) ----

def _band_for_freq(freq):
    if 863e6 <= freq <= 870e6:
        return "868"
    if 2400e6 <= freq <= 2484e6:
        return "2g4"
    return "unknown"


def maybe_reset(prev, cur, policy="strict"):
    """Decide whether to SWD-reset between configs.

    Returns True if reset required, False if skippable.
    prev/cur: dicts with keys mod, band (or freq), pa, error, stop_id,
              sf, bw, br (radio parameters within a modulation).
    policy: 'strict' (always reset) or 'gated' (skip only when radio
            parameters are truly unchanged — same mod, same SF/BW/BR,
            same band, same stop, no error, no PA22).

    V3 finding (2026-08-23): the SX1280 cannot hot-switch spreading factor
    (SF11→SF12) without a full radio reset. The firmware MOD command
    returns OK but the radio does not reconfigure, resulting in 0 packets.
    Same applies to bandwidth (BW) and bit-rate (BR) changes within the
    same modulation. Therefore 'gated' must reset on any radio-parameter
    change, not just modulation change.
    """
    # Always reset on: mod change, band change, error, PA22, stop change
    if prev.get("mod") != cur.get("mod"):
        return True
    # Handle band via 'band' key or infer from 'freq'
    prev_band = prev.get("band") or _band_for_freq(prev.get("freq", 0))
    cur_band = cur.get("band") or _band_for_freq(cur.get("freq", 0))
    if prev_band != cur_band:
        return True
    if cur.get("error", False):
        return True
    if cur.get("pa", 0) >= 22:
        return True
    if prev.get("stop_id") != cur.get("stop_id"):
        return True
    # V3 fix: reset on radio-parameter change within same modulation
    # SX1280 requires full reset to change SF/BW/BR — MOD command alone
    # returns OK but radio doesn't reconfigure (0 packets observed).
    if prev.get("sf") != cur.get("sf"):
        return True
    if prev.get("bw") != cur.get("bw"):
        return True
    if prev.get("br") != cur.get("br"):
        return True
    # Same mod, same radio params, same band, no error, same stop, no PA22
    if policy == "gated":
        return False
    # strict: reset everything
    return True


# ---- Carry-forward state DB (plan §4.1, D4) ----

class CampaignState:
    """Crash-safe JSON state DB for carry-forward across distance stops.

    Stores per-stop, per-config verdicts. Computes skip-list for a given
    distance based on monotone carry-forward rules (D4 symmetric).
    """

    def __init__(self, path):
        self.path = path
        self._data = {"stops": {}, "verdicts": []}
        self._load()

    def _load(self):
        """Load from JSON file, crash-safe (corrupt = fresh start)."""
        if not os.path.exists(self.path):
            return
        try:
            with open(self.path, "r") as f:
                raw = f.read().strip()
            if raw:
                self._data = json.loads(raw)
        except (json.JSONDecodeError, IOError, ValueError):
            self._data = {"stops": {}, "verdicts": []}

    def _save(self):
        """Atomic write: temp file + rename."""
        tmp = self.path + ".tmp"
        with open(tmp, "w") as f:
            json.dump(self._data, f, indent=1)
        os.rename(tmp, self.path)

    def record_verdict(self, stop_id, d, config_label, verdict, k, n,
                       is_anchor=False):
        """Record a verdict for a config at a distance stop."""
        entry = {
            "stop_id": stop_id, "distance": d,
            "config": config_label, "verdict": verdict,
            "k": k, "n": n, "anchor": is_anchor,
            "ts": datetime.now().isoformat(),
        }
        self._data["verdicts"].append(entry)
        # Index by stop
        if stop_id not in self._data["stops"]:
            self._data["stops"][stop_id] = {"distance": d, "configs": {}}
        stop = self._data["stops"][stop_id]
        stop["distance"] = d
        if config_label not in stop["configs"]:
            stop["configs"][config_label] = []
        stop["configs"][config_label].append(entry)

    def commit(self):
        """Persist state to disk (crash-safe)."""
        self._save()

    def get_stop_data(self, stop_id):
        """Return configs dict for a stop, or None."""
        stop = self._data["stops"].get(stop_id)
        if stop is None:
            return None
        return stop.get("configs", {})

    def get_skips(self, stop_id, d):
        """Compute carry-forward skip set for distance d.

        DEAD@d' → skip if d > d' (farther than where it died).
        CLEAN@d' → skip if d < d' (closer than where it was clean).
        Anchor contradiction invalidates skips for that config.
        """
        # Collect all verdicts per config, check for contradictions
        config_verdicts = {}  # label → list of (distance, verdict, is_anchor)
        for v in self._data["verdicts"]:
            lbl = v["config"]
            if lbl not in config_verdicts:
                config_verdicts[lbl] = []
            config_verdicts[lbl].append((v["distance"], v["verdict"],
                                          v.get("anchor", False)))

        # Detect anchor contradictions: anchor CLEAN at d' where DEAD was
        # carry-forwarded from d < d', or anchor DEAD at d' where CLEAN was
        # carry-forwarded from d > d'
        invalidated = set()
        for lbl, vs in config_verdicts.items():
            # Sort by distance
            vs_sorted = sorted(vs, key=lambda x: x[0])
            for i, (d_i, v_i, a_i) in enumerate(vs_sorted):
                if not a_i:
                    continue
                # This is an anchor — check against non-anchor verdicts
                for d_j, v_j, a_j in vs_sorted:
                    if a_j:
                        continue
                    if d_j < d_i and v_j == "DEAD":
                        # DEAD at closer d_j but anchor CLEAN at farther d_i
                        if v_i == "CLEAN":
                            invalidated.add(lbl)
                            break
                    if d_j > d_i and v_j == "CLEAN":
                        # CLEAN at farther d_j but anchor DEAD at closer d_i
                        if v_i == "DEAD":
                            invalidated.add(lbl)
                            break

        skips = set()
        for lbl, vs in config_verdicts.items():
            if lbl in invalidated:
                continue
            for d_v, v_v, a_v in vs:
                if v_v == "DEAD" and d > d_v:
                    skips.add(lbl)
                if v_v == "CLEAN" and d < d_v:
                    skips.add(lbl)
        return skips


# ---- Branch decision (plan §1.1) ----

def branch(v_sf7, v_flrc):
    """Branch verdict from probe results.

    v_sf7: SprtResult for LoRa SF7 probe.
    v_flrc: SprtResult for FLRC-650 probe.
    Returns: GOOD, DEGRADED, or EDGE.

    Logic:
    - SF7 DEAD → DEGRADED (regardless of FLRC; SF7 is the sensitive canary)
    - SF7 CLEAN → GOOD (FLRC may be dead; it dies first at range)
    - SF7 EDGE → EDGE (cliff search first)
    """
    if v_sf7.verdict == "DEAD":
        return "DEGRADED"
    if v_sf7.verdict == "CLEAN":
        return "GOOD"
    return "EDGE"


# ---- Cliff search (plan §1.4, D2) ----

def cliff_search(sf_axis, sprt_fn, d, state=None, band="868",
                 validate_fn=None):
    """Bisect search for PER cliff on SF axis.

    sf_axis: list of SF values [5, 6, ..., 12].
    sprt_fn: callable(sf_label, n_cap) → SprtResult for SPRT probes.
    d: current distance (for state recording).
    state: CampaignState or None.
    band: "868" or "2g4".
    validate_fn: callable(sf_label, n) → SprtResult for n=50 validation (D2).

    Returns CliffResult(boundary_lo, boundary_hi, summary, validations).
    """
    labels = [f"SF{sf}" for sf in sf_axis]

    # Sentinel probes: fast end (SF5) and robust end (SF12)
    v_fast = sprt_fn(labels[0])
    v_robust = sprt_fn(labels[-1])

    if state:
        state.record_verdict("cliff", d, labels[0], v_fast.verdict,
                             v_fast.k, v_fast.n)
        state.record_verdict("cliff", d, labels[-1], v_robust.verdict,
                             v_robust.k, v_robust.n)

    # SF5 CLEAN → whole axis clean (fastest works, slower all work too)
    if v_fast.verdict == "CLEAN":
        return CliffResult(sf_axis[0], sf_axis[-1],
                           "whole axis clean at this stop", [])

    # SF12 DEAD → all dead (slowest fails, faster all fail too)
    if v_robust.verdict == "DEAD":
        return CliffResult(None, None,
                           "all dead at this stop: cliff above SF12", [])

    # Bisect: SF5 is dead/edge (lo), SF12 is clean/edge (hi)
    lo_idx = 0
    hi_idx = len(sf_axis) - 1

    while hi_idx - lo_idx > 1:
        mid_idx = (lo_idx + hi_idx) // 2
        v_mid = sprt_fn(labels[mid_idx])
        if state:
            state.record_verdict("cliff", d, labels[mid_idx],
                                 v_mid.verdict, v_mid.k, v_mid.n)
        if v_mid.verdict == "CLEAN":
            hi_idx = mid_idx
        else:  # DEAD or EDGE → treat as DEAD side
            lo_idx = mid_idx

    # Validation at n=50 on boundary cells (D2)
    validations = []
    if validate_fn:
        for idx in (lo_idx, hi_idx):
            v_val = validate_fn(labels[idx], 50)
            validations.append((labels[idx], v_val))
            if state:
                state.record_verdict("cliff-validate", d, labels[idx],
                                     v_val.verdict, v_val.k, v_val.n)

    summary = (f"cliff boundary: {labels[lo_idx]} (dead) → "
               f"{labels[hi_idx]} (clean)")
    return CliffResult(sf_axis[lo_idx], sf_axis[hi_idx],
                       summary, validations)


# ---- sprt_run: HW-facing burst with early-stop (plan §2) ----

def sprt_run(cfg, tx, rx, session_id, cfg_idx, policy=None,
             stop_fn=None):
    """Arm a burst at n_cap, stream RX PKT lines, decide early via SPRT.

    Uses STOP console command for early abort (verified in ADAPT-0).
    Falls back to fixed-N if stop_fn raises.
    Returns SprtResult(verdict, k, n).
    """
    p = policy or SPRT
    n_cap = p["n_cap"]
    n_min = p["n_min"]

    # Configure radio (reuse e80_sweep_full config sequence)
    mod = cfg["mod"]
    if mod == "lora":
        m = f"MOD LORA {cfg['sf']} {cfg['bw']}"
    else:
        m = f"MOD FLRC {cfg['br']} {cfg['pa']}"
    for s in (rx, tx):
        sw.cmd(s, m)
        if mod == "lora":
            sw.cmd(s, f"PA {cfg['pa']}")
        sw.cmd(s, f"FREQ {cfg['freq']}")
    sw.cmd(rx, "ROLE RX")
    sw.cmd(tx, "ROLE TX")
    sw.cmd(tx, f"SESSION {session_id}")
    sw.cmd(rx, f"SESSION {session_id}")
    sw.cmd(tx, f"CONFIG {cfg_idx} 1")
    sw.cmd(rx, f"CONFIG {cfg_idx} 1")

    # Band override for 2.4 GHz
    if not (sw.BAND_MIN_HZ <= cfg["freq"] <= sw.BAND_MAX_HZ):
        for s in (rx, tx):
            sw.cmd(s, f"BAND OVERRIDE {sw.BAND_OVERRIDE_PIN}")

    r = sw.cmd(tx, "ARM TX")
    if not r or not r.startswith("OK ARMED"):
        return SprtResult("DEAD", n_cap, n_cap)  # can't arm = dead

    # Arm burst at n_cap, stream and early-stop
    rx.reset_input_buffer()
    tx.write(f"START N={n_cap} LEN={cfg['plen']} GAP={cfg['gap']}\r\n".encode())
    # Read start reply (don't wait for full burst)
    sw.readline(tx, 3.0)

    k = 0
    n = 0
    if mod == "lora":
        toa_max = sw.lora_airtime_s(12, 125, cfg["plen"])
    else:
        toa_max = sw.flrc_airtime_s(260, cfg["plen"])
    deadline = time.monotonic() + n_cap * (toa_max + cfg["gap"] / 1e6) + 10

    while n < n_cap and time.monotonic() < deadline:
        line = sw.readline(rx, timeout=3.0)
        if line is None:
            break
        pkt = sw.parse_pkt(line)
        if pkt is None or pkt["config"] != cfg_idx:
            continue
        n += 1
        if pkt["bit_err"] > 0:
            k += 1
        if n >= n_min:
            res = sprt_decide(k, n, p)
            if res.verdict in ("CLEAN", "DEAD"):
                if stop_fn:
                    try:
                        stop_fn(tx)
                    except Exception:
                        pass
                return res

    # Reached n_cap without crossing → EDGE or final check
    res = sprt_decide(k, n, p)
    return res


def stop_tx(tx):
    """Send STOP console command to TX board and drain (ADAPT-0 verified)."""
    sw.cmd(tx, "STOP")
    sw.drain_lines(tx, 2)


# ---- MD report + CSV ----

CAMPAIGN_CSV_FIELDS = ["stop_id", "distance", "mode", "idx", "label", "mod",
                       "sf", "bw", "br", "pa", "freq", "plen", "verdict",
                       "k", "n", "rssi_avg", "snr_avg", "bit_err_total",
                       "ci_lo", "ci_hi"]


def write_csv_row(csv_writer, stop_id, d, mode, idx, cfg, result):
    """Write one row to campaign CSV with mode= column (R5)."""
    k = result.k if hasattr(result, "k") else 0
    n = result.n if hasattr(result, "n") else 0
    ci_lo, ci_hi = wilson_ci(k, n)
    csv_writer.writerow([
        stop_id, d, mode, idx, cfg["label"], cfg["mod"],
        cfg.get("sf", ""), cfg.get("bw", ""), cfg.get("br", ""),
        cfg["pa"], cfg["freq"], cfg["plen"],
        result.verdict, k, n, "", "", "",
        round(ci_lo, 4), round(ci_hi, 4),
    ])


def write_md_report(path, stop_id, d, mode, results, state=None):
    """Write MD report for a campaign stop."""
    with open(path, "w") as f:
        f.write(f"# Campaign Stop {stop_id} — d={d}m — mode={mode}\n\n")
        f.write(f"**Date:** {datetime.now().isoformat()}\n\n")
        f.write("## Verdicts\n\n")
        f.write("| # | Config | Mod | Verdict | k | n | PER | Wilson 95% CI |\n")
        f.write("|---|---|---|---|---|---|---|---|\n")
        for i, (cfg, res) in enumerate(results):
            k, n = res.k, res.n
            per = f"{k}/{n}" if n > 0 else "-"
            lo, hi = wilson_ci(k, n)
            f.write(f"| {i+1} | {cfg['label']} | {cfg['mod']} | {res.verdict} "
                    f"| {k} | {n} | {per} | [{lo:.1%}, {hi:.1%}] |\n")
        if state:
            skips = state.get_skips(stop_id, d)
            if skips:
                f.write(f"\n## Carry-forward skips\n\n")
                f.write(f"{', '.join(sorted(skips))}\n")


# ---- CLI ----

def main():
    import argparse
    ap = argparse.ArgumentParser(
        description="E80 adaptive campaign controller (SPRT early-stop)")
    ap.add_argument("--mode", default="probe",
                    choices=["probe", "good", "degraded", "cliff", "full-stop"],
                    help="Campaign mode (default: probe)")
    ap.add_argument("--band", default="868",
                    choices=["868", "2g4", "both"],
                    help="Band: 868 MHz, 2.4 GHz, or both (D3 dual-band)")
    ap.add_argument("--reset-policy", default="strict",
                    choices=["strict", "gated"],
                    help="Reset policy: strict (every config) or gated (skip same-mod)")
    ap.add_argument("--tier", type=int, default=None,
                    help="Override packet tier (default: mode-based)")
    ap.add_argument("--stop-id", default="S1",
                    help="Distance stop identifier (e.g. S1, S2)")
    ap.add_argument("--distance", type=int, default=0,
                    help="Distance in meters for this stop")
    ap.add_argument("--state", default=None,
                    help="Path to campaign state JSON (carry-forward DB)")
    ap.add_argument("--out", default=None,
                    help="Output directory (default: repo root)")
    ap.add_argument("--dry-run", action="store_true",
                    help="Print configs only, no HW access")
    args = ap.parse_args()

    cfgs = build_campaign_configs(args.mode, band=args.band)
    print(f"E80 Campaign — mode={args.mode} band={args.band} "
          f"stop={args.stop_id} d={args.distance}m", flush=True)
    print(f"Configs: {len(cfgs)}", flush=True)

    if args.dry_run:
        for i, c in enumerate(cfgs):
            print(f"  [{i+1}] {c['label']}  mod={c['mod']} "
                  f"freq={c['freq']/1e6:.0f}MHz plen={c['plen']} "
                  f"pa={c['pa']} gap={c['gap']}")
        return 0

    # HW path (not exercised in tests — ADAPT-2 does HW validation)
    out_dir = args.out or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    ts_str = datetime.now().strftime("%Y%m%d-%H%M%S")
    csv_path = os.path.join(out_dir, f"campaign-{args.stop_id}-{ts_str}.csv")
    md_path = os.path.join(out_dir, f"campaign-{args.stop_id}-{ts_str}.md")

    state = CampaignState(args.state) if args.state else None

    tx_port, rx_port, tx, rx = sw.open_boards()
    print(f"Ports: TX={tx_port} RX={rx_port}", flush=True)

    session_id = int(datetime.now().strftime("%y%m%d%H%M"))
    results = []

    csv_f = open(csv_path, "w", newline="")
    csv_w = csv.writer(csv_f)
    csv_w.writerow(CAMPAIGN_CSV_FIELDS)

    for i, cfg in enumerate(cfgs):
        print(f"  [{i+1}/{len(cfgs)}] {cfg['label']} ... ", end="", flush=True)
        res = sprt_run(cfg, tx, rx, session_id, i, stop_fn=lambda t: stop_tx(t))
        results.append((cfg, res))
        write_csv_row(csv_w, args.stop_id, args.distance, args.mode, i, cfg, res)
        csv_f.flush()
        print(f"{res.verdict} k={res.k}/{res.n}", flush=True)
        if state:
            state.record_verdict(args.stop_id, args.distance, cfg["label"],
                                 res.verdict, res.k, res.n)

    if state:
        state.commit()
    csv_f.close()

    write_md_report(md_path, args.stop_id, args.distance, args.mode,
                    results, state)
    print(f"\nCSV: {csv_path}")
    print(f"Report: {md_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())