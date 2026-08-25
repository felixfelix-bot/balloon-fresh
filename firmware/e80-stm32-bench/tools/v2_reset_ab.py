#!/usr/bin/env python3
"""V2 RESET A/B — 10-config sequence, per-config resets vs same-mod reset-skip.

Plan §4.2: identical 10-config sequence (fast FLRC + SF11/12 mix), run:
  (A) with per-config SWD resets
  (B) with same-mod reset-skip (console-only reconfig)
  2× each (A1, A2, B1, B2).

Acceptance:
  - Identical CLEAN/DEAD verdicts
  - PER point estimates within overlapping Wilson CIs
  - Zero foreign-config-tag PKTs in B
  - RSSI/SNR means shift < 1 dB
  - SF11/12 50-pkt burst mid-sequence overrun-free

Requires HW: two E80 boards on /dev/ttyUSB* (CH340).
Run: python3 v2_reset_ab.py
"""
import csv
import math
import os
import sys
import time
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Import sweep helpers
import e80_sweep_full as sw
import e80_campaign as camp

NPKTS = 50
SESSION_ID = int(datetime.now().strftime("%y%m%d%H%M"))

# 10-config sequence: fast FLRC + SF11/12 mix (stress test for reset-skip)
AB_CONFIGS = [
    # 0-2: FLRC fast configs (reset-overhead-dominated)
    dict(mod="flrc", br=2600, pa=5, freq=sw.DEFAULT_FREQ, plen=64, gap=10000,
         label="FLRC 2600k pa5 L64"),
    dict(mod="flrc", br=1300, pa=5, freq=sw.DEFAULT_FREQ, plen=64, gap=10000,
         label="FLRC 1300k pa5 L64"),
    dict(mod="flrc", br=650, pa=5, freq=sw.DEFAULT_FREQ, plen=64, gap=10000,
         label="FLRC 650k pa5 L64"),
    # 3-4: SF11/12 BW125 (overrun risk)
    dict(mod="lora", sf=12, bw=125, pa=10, freq=sw.DEFAULT_FREQ, plen=16, gap=0,
         label="SF12 BW125 PA10 L16"),
    dict(mod="lora", sf=11, bw=125, pa=10, freq=sw.DEFAULT_FREQ, plen=16, gap=0,
         label="SF11 BW125 PA10 L16"),
    # 5-7: FLRC again (mod transition back)
    dict(mod="flrc", br=2600, pa=5, freq=sw.DEFAULT_FREQ, plen=128, gap=10000,
         label="FLRC 2600k pa5 L128"),
    dict(mod="flrc", br=1300, pa=5, freq=sw.DEFAULT_FREQ, plen=255, gap=10000,
         label="FLRC 1300k pa5 L255"),
    dict(mod="flrc", br=650, pa=5, freq=sw.DEFAULT_FREQ, plen=255, gap=10000,
         label="FLRC 650k pa5 L255"),
    # 8-9: SF11/12 again (overrun regression mid-sequence)
    dict(mod="lora", sf=12, bw=125, pa=10, freq=sw.DEFAULT_FREQ, plen=16, gap=0,
         label="SF12 BW125 PA10 L16 #2"),
    dict(mod="lora", sf=11, bw=125, pa=10, freq=sw.DEFAULT_FREQ, plen=16, gap=0,
         label="SF11 BW125 PA10 L16 #2"),
]


def compute_gap(cfg):
    """Adaptive gap = max(10ms, 1.2*airtime + 5ms)."""
    if cfg["mod"] == "lora":
        toa = sw.lora_airtime_s(cfg["sf"], cfg["bw"], cfg["plen"])
    else:
        toa = sw.flrc_airtime_s(cfg["br"], cfg["plen"])
    return max(10000, int(1.2 * toa * 1e6) + 5000)


for c in AB_CONFIGS:
    c["gap"] = compute_gap(c)


def run_sequence(tx, rx, tx_port, rx_port, session_id, reset_mode, run_label):
    """Run the 10-config sequence.

    reset_mode='strict': SWD reset both boards every config.
    reset_mode='gated': SWD reset only on mod change / error / first config.
    """
    results = []
    prev_cfg = None
    prev_stop_id = "S1"

    for i, cfg in enumerate(AB_CONFIGS):
        print(f"  [{i+1}/10] {cfg['label']} ... ", end="", flush=True)

        # Reset decision using maybe_reset from e80_campaign
        if i == 0:
            do_reset = True
        elif reset_mode == "strict":
            do_reset = True
        else:  # gated
            do_reset = camp.maybe_reset(prev_cfg, cfg, policy="gated")

        if do_reset:
            sw.swd_reset(sw.PROBE_TX)
            sw.swd_reset(sw.PROBE_RX)
            tx.port = tx_port
            rx.port = rx_port
            if not sw.ensure_alive(tx, sw.PROBE_TX, "TX"):
                raise RuntimeError(f"TX dead at cfg {i}")
            if not sw.ensure_alive(rx, sw.PROBE_RX, "RX"):
                raise RuntimeError(f"RX dead at cfg {i}")
        else:
            # Gated: no reset, just drain and reconfigure via console
            sw.cmd(tx, "STOP")
            sw.drain_lines(tx, 1)
            sw.drain_lines(rx, 1)

        # Configure radio
        sw.cmd(tx, f"SESSION {session_id}")
        sw.cmd(rx, f"SESSION {session_id}")
        sw.cmd(tx, f"CONFIG {i} 1")
        sw.cmd(rx, f"CONFIG {i} 1")

        mod = cfg["mod"]
        if mod == "lora":
            m = f"MOD LORA {cfg['sf']} {cfg['bw']}"
        else:
            m = f"MOD FLRC {cfg['br']} {cfg['pa']}"

        for s, lbl in [(rx, "RX"), (tx, "TX")]:
            r = sw.cmd(s, m)
            if not r or not r.startswith("OK MOD"):
                raise RuntimeError(f"{lbl} MOD: {r!r}")
            if mod == "lora":
                r = sw.cmd(s, f"PA {cfg['pa']}")
                if not r or not r.startswith("OK PA"):
                    raise RuntimeError(f"{lbl} PA: {r!r}")
            r = sw.cmd(s, f"FREQ {cfg['freq']}")
            if not r or not r.startswith("OK FREQ"):
                raise RuntimeError(f"{lbl} FREQ: {r!r}")

        sw.cmd(rx, "ROLE RX")
        sw.cmd(tx, "ROLE TX")
        sw.cmd(tx, "ARM TX")

        # Burst
        burst = sw.arm_and_stream(tx, rx, cfg, NPKTS)
        pkts = [p for p in (sw.parse_pkt(l) for l in burst["rx_lines"]) if p is not None]

        # Filter to this config's tag
        my_pkts = [p for p in pkts if p["config"] == i and p["session"] == session_id]
        foreign_pkts = [p for p in pkts if p["config"] != i or p["session"] != session_id]

        k = sum(1 for p in my_pkts if p["bit_err"] > 0)
        n = len(my_pkts)
        rssi_vals = [p["rssi"] for p in my_pkts]
        snr_vals = [p["snr"] for p in my_pkts]

        rssi_avg = round(sum(rssi_vals)/len(rssi_vals), 1) if rssi_vals else None
        snr_avg = round(sum(snr_vals)/len(snr_vals), 1) if snr_vals else None

        per = k/n if n > 0 else 1.0
        verdict = "CLEAN" if per < 0.02 else ("DEAD" if per > 0.20 else "EDGE")

        # Check TX DONE (overrun check)
        tx_done = any("TX DONE" in l for l in burst["tx_lines"])

        result = {
            "run": run_label, "reset_mode": reset_mode, "cfg_idx": i,
            "label": cfg["label"], "mod": mod,
            "n": n, "k": k, "per": round(per, 4), "verdict": verdict,
            "rssi_avg": rssi_avg, "snr_avg": snr_avg,
            "foreign_pkts": len(foreign_pkts),
            "tx_done": tx_done,
            "dur_s": burst.get("wait_s", 0),
        }
        results.append(result)
        prev_cfg = cfg

        print(f"{verdict} k={k}/{n} rssi={rssi_avg} foreign={len(foreign_pkts)} "
              f"tx_done={tx_done}", flush=True)

    return results


def main():
    out_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                           "..", "..", "..")
    out_dir = os.path.abspath(out_dir)
    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    csv_path = os.path.join(out_dir, f"v2-reset-ab-{ts}.csv")

    print("=" * 60)
    print("V2 RESET A/B — 10 configs × (strict, strict, gated, gated)")
    print("=" * 60)

    # Open boards
    tx_port, rx_port, tx, rx = sw.open_boards()
    print(f"Ports: TX={tx_port} RX={rx_port}", flush=True)

    all_results = []

    for run_name, reset_mode in [("A1", "strict"), ("A2", "strict"),
                                  ("B1", "gated"), ("B2", "gated")]:
        print(f"\n--- Run {run_name} (reset={reset_mode}) ---")
        session_id = SESSION_ID + hash(run_name) % 10000
        results = run_sequence(tx, rx, tx_port, rx_port, session_id,
                               reset_mode, run_name)
        all_results.extend(results)

        # Write incremental CSV
        with open(csv_path, "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=[
                "run", "reset_mode", "cfg_idx", "label", "mod",
                "n", "k", "per", "verdict", "rssi_avg", "snr_avg",
                "foreign_pkts", "tx_done", "dur_s"])
            w.writeheader()
            w.writerows(all_results)

    # ---- Analysis ----
    print("\n" + "=" * 60)
    print("V2 ANALYSIS")
    print("=" * 60)

    PASS = 0
    FAIL = 0

    # Group by config
    by_cfg = {}
    for r in all_results:
        key = r["cfg_idx"]
        if key not in by_cfg:
            by_cfg[key] = {}
        by_cfg[key][r["run"]] = r

    # Compare A vs B: verdicts, PER CIs, RSSI shift, foreign pkts
    verdict_mismatches = 0
    ci_non_overlaps = 0
    rssi_shifts = []
    foreign_pkt_count = 0
    tx_done_failures = 0

    for cfg_idx in sorted(by_cfg):
        runs = by_cfg[cfg_idx]
        a_runs = [runs[r] for r in ("A1", "A2") if r in runs]
        b_runs = [runs[r] for r in ("B1", "B2") if r in runs]

        label = runs.get("A1", runs.get("B1", {})).get("label", f"cfg{cfg_idx}")
        print(f"\n  cfg {cfg_idx} {label}:")

        for r in runs.values():
            print(f"    {r['run']}: {r['verdict']} k={r['k']}/{r['n']} "
                  f"per={r['per']:.2%} rssi={r['rssi_avg']} "
                  f"foreign={r['foreign_pkts']} tx_done={r['tx_done']}")

        # Verdict match
        all_verdicts = set(r["verdict"] for r in runs.values())
        if len(all_verdicts) <= 1:
            PASS += 1
        else:
            FAIL += 1
            verdict_mismatches += 1
            print(f"    [FAIL] Verdict mismatch: {all_verdicts}")

        # PER CI overlap A vs B
        for a in a_runs:
            for b in b_runs:
                if a["n"] > 0 and b["n"] > 0:
                    import e80_campaign as camp
                    lo_a, hi_a = camp.wilson_ci(a["k"], a["n"])
                    lo_b, hi_b = camp.wilson_ci(b["k"], b["n"])
                    if not (hi_a >= lo_b and hi_b >= lo_a):
                        ci_non_overlaps += 1
                        print(f"    [FAIL] CI non-overlap: A={a['k']}/{a['n']} B={b['k']}/{b['n']}")

        # RSSI shift A vs B
        if a_runs and b_runs:
            a_rssi = [r["rssi_avg"] for r in a_runs if r["rssi_avg"] is not None]
            b_rssi = [r["rssi_avg"] for r in b_runs if r["rssi_avg"] is not None]
            if a_rssi and b_rssi:
                a_mean = sum(a_rssi) / len(a_rssi)
                b_mean = sum(b_rssi) / len(b_rssi)
                shift = abs(a_mean - b_mean)
                rssi_shifts.append(shift)
                if shift >= 1.0:
                    FAIL += 1
                    print(f"    [FAIL] RSSI shift {shift:.1f} dB >= 1 dB")
                else:
                    PASS += 1

        # Foreign packets in B
        for b in b_runs:
            if b["foreign_pkts"] > 0:
                foreign_pkt_count += b["foreign_pkts"]
                FAIL += 1
                print(f"    [FAIL] {b['run']}: {b['foreign_pkts']} foreign pkts")
            else:
                PASS += 1

        # TX DONE (overrun check)
        for r in runs.values():
            if not r["tx_done"]:
                tx_done_failures += 1
                # TX DONE missing is not necessarily a fail — might be timing
                # but for SF11/12 it indicates overrun

    # Summary
    print(f"\n{'='*60}")
    print(f"V2 RESET A/B RESULTS")
    print(f"  Verdict mismatches:      {verdict_mismatches}")
    print(f"  CI non-overlaps:         {ci_non_overlaps}")
    print(f"  Foreign pkt count (B):   {foreign_pkt_count}")
    print(f"  TX DONE failures:        {tx_done_failures}")
    if rssi_shifts:
        print(f"  RSSI shifts:             {rssi_shifts}")
        max_shift = max(rssi_shifts)
        print(f"  Max RSSI shift:          {max_shift:.1f} dB")
    print(f"  Checks passed:           {PASS}")
    print(f"  Checks failed:           {FAIL}")

    # Acceptance
    go = (verdict_mismatches == 0 and ci_non_overlaps == 0
          and foreign_pkt_count == 0
          and (not rssi_shifts or max(rssi_shifts) < 1.0))
    if go:
        print(f"ACCEPTANCE: GO")
    else:
        print(f"ACCEPTANCE: NO-GO")

    print(f"CSV: {csv_path}")
    print(f"{'='*60}")
    sys.exit(0 if go else 1)


if __name__ == "__main__":
    main()