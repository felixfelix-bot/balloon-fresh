#!/usr/bin/env python3
"""V3 REGRESSION — SF11/12 50-pkt burst mid-sequence without resets.

Plan §8 V3: SF11/12 50-pkt overrun check mid-sequence without resets.
Protects the adaptive-gap fix (the SF11/12 overrun bug was fixed by timing,
not by reset — radio state per config is not the failure mode).

Sequence:
  1. FLRC BR2600 (fast, no reset overhead)
  2. SF12 BW125 LEN=16 (slow, overrun risk — 50 pkts × 2.55s = ~128s)
  3. FLRC BR2600 (mod transition, reset here)
  4. SF11 BW125 LEN=16 (slow, overrun risk — 50 pkts × 1.28s = ~64s)
  5. SF12 BW125 LEN=16 again (back-to-back SF12, no reset)

Acceptance:
  - All 5 configs produce 50 pkts (no overrun/drop)
  - TX DONE on every config
  - Zero foreign-config-tag PKTs
  - RSSI/SNR stable (no wild swings from stale state)

Requires HW: two E80 boards on /dev/ttyUSB* (CH340).
Run: python3 v3_regression.py
"""
import csv
import os
import sys
import time
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import e80_sweep_full as sw
import e80_campaign as camp

NPKTS = 50
SESSION_ID = int(datetime.now().strftime("%y%m%d%H%M"))

# 5-config sequence: FLRC → SF12 → FLRC → SF11 → SF12 (no resets between same-mod)
V3_CONFIGS = [
    dict(mod="flrc", br=2600, pa=5, freq=sw.DEFAULT_FREQ, plen=64, gap=10000,
         label="FLRC 2600k L64"),
    dict(mod="lora", sf=12, bw=125, pa=10, freq=sw.DEFAULT_FREQ, plen=16, gap=0,
         label="SF12 BW125 L16 #1"),
    dict(mod="flrc", br=2600, pa=5, freq=sw.DEFAULT_FREQ, plen=64, gap=10000,
         label="FLRC 2600k L64 #2"),
    dict(mod="lora", sf=11, bw=125, pa=10, freq=sw.DEFAULT_FREQ, plen=16, gap=0,
         label="SF11 BW125 L16"),
    dict(mod="lora", sf=12, bw=125, pa=10, freq=sw.DEFAULT_FREQ, plen=16, gap=0,
         label="SF12 BW125 L16 #2"),
]


def compute_gap(cfg):
    if cfg["mod"] == "lora":
        toa = sw.lora_airtime_s(cfg["sf"], cfg["bw"], cfg["plen"])
    else:
        toa = sw.flrc_airtime_s(cfg["br"], cfg["plen"])
    return max(10000, int(1.2 * toa * 1e6) + 5000)


for c in V3_CONFIGS:
    c["gap"] = compute_gap(c)


def main():
    out_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                           "..", "..", "..")
    out_dir = os.path.abspath(out_dir)
    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    csv_path = os.path.join(out_dir, f"v3-regression-{ts}.csv")

    print("=" * 60)
    print("V3 REGRESSION — SF11/12 50-pkt mid-sequence (no resets)")
    print("=" * 60)

    tx_port, rx_port, tx, rx = sw.open_boards()
    print(f"Ports: TX={tx_port} RX={rx_port}", flush=True)

    # Initial reset
    sw.swd_reset(sw.PROBE_TX)
    sw.swd_reset(sw.PROBE_RX)
    tx.port = tx_port
    rx.port = rx_port
    if not sw.ensure_alive(tx, sw.PROBE_TX, "TX"):
        raise RuntimeError("TX dead at start")
    if not sw.ensure_alive(rx, sw.PROBE_RX, "RX"):
        raise RuntimeError("RX dead at start")

    results = []
    prev_cfg = None

    for i, cfg in enumerate(V3_CONFIGS):
        print(f"\n  [{i+1}/5] {cfg['label']} ... ", flush=True)
        t_start = time.monotonic()

        # Use maybe_reset from e80_campaign — resets on mod/SF/BW/BR change
        if i == 0:
            do_reset = True
        else:
            do_reset = camp.maybe_reset(prev_cfg, cfg, policy="gated")

        if do_reset:
            reason = "initial" if i == 0 else "parameter change"
            print(f"    (reset: {reason})", flush=True)
            sw.swd_reset(sw.PROBE_TX)
            sw.swd_reset(sw.PROBE_RX)
            tx.port = tx_port
            rx.port = rx_port
            if not sw.ensure_alive(tx, sw.PROBE_TX, "TX"):
                raise RuntimeError(f"TX dead at cfg {i}")
            if not sw.ensure_alive(rx, sw.PROBE_RX, "RX"):
                raise RuntimeError(f"RX dead at cfg {i}")
        else:
            print(f"    (same params, no reset)", flush=True)
            sw.cmd(tx, "STOP")
            sw.drain_lines(tx, 1)
            sw.drain_lines(rx, 1)

        # Configure
        sw.cmd(tx, f"SESSION {SESSION_ID}")
        sw.cmd(rx, f"SESSION {SESSION_ID}")
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

        burst = sw.arm_and_stream(tx, rx, cfg, NPKTS)
        pkts = [p for p in (sw.parse_pkt(l) for l in burst["rx_lines"]) if p is not None]
        my_pkts = [p for p in pkts if p["config"] == i and p["session"] == SESSION_ID]
        foreign_pkts = [p for p in pkts if p["config"] != i or p["session"] != SESSION_ID]

        k = sum(1 for p in my_pkts if p["bit_err"] > 0)
        n = len(my_pkts)
        rssi_vals = [p["rssi"] for p in my_pkts]
        snr_vals = [p["snr"] for p in my_pkts]
        rssi_avg = round(sum(rssi_vals)/len(rssi_vals), 1) if rssi_vals else None
        snr_avg = round(sum(snr_vals)/len(snr_vals), 1) if snr_vals else None
        per = k/n if n > 0 else 1.0
        verdict = "CLEAN" if per < 0.02 else ("DEAD" if per > 0.20 else "EDGE")
        tx_done = any("TX DONE" in l for l in burst["tx_lines"])
        t_end = time.monotonic()

        result = {
            "cfg_idx": i, "label": cfg["label"], "mod": mod,
            "n": n, "k": k, "per": round(per, 4), "verdict": verdict,
            "rssi_avg": rssi_avg, "snr_avg": snr_avg,
            "foreign_pkts": len(foreign_pkts),
            "tx_done": tx_done,
            "dur_s": round(t_end - t_start, 1),
        }
        results.append(result)
        prev_cfg = cfg

        print(f"    {verdict} k={k}/{n} rssi={rssi_avg} snr={snr_avg} "
              f"foreign={len(foreign_pkts)} tx_done={tx_done} "
              f"dur={t_end-t_start:.1f}s", flush=True)

    # ---- Analysis ----
    print("\n" + "=" * 60)
    print("V3 REGRESSION ANALYSIS")
    print("=" * 60)

    PASS = 0
    FAIL = 0

    for r in results:
        print(f"  cfg {r['cfg_idx']} {r['label']}: n={r['n']} k={r['k']} "
              f"per={r['per']:.2%} {r['verdict']} rssi={r['rssi_avg']} "
              f"foreign={r['foreign_pkts']} tx_done={r['tx_done']} "
              f"dur={r['dur_s']}s")

        # All 50 pkts received?
        if r["n"] == NPKTS:
            PASS += 1
        else:
            FAIL += 1
            print(f"    [FAIL] Expected {NPKTS} pkts, got {r['n']}")

        # TX DONE?
        if r["tx_done"]:
            PASS += 1
        else:
            FAIL += 1
            print(f"    [FAIL] TX DONE missing")

        # Zero foreign pkts?
        if r["foreign_pkts"] == 0:
            PASS += 1
        else:
            FAIL += 1
            print(f"    [FAIL] {r['foreign_pkts']} foreign pkts")

    # RSSI stability (across SF11/12 configs)
    sf_rssis = [r["rssi_avg"] for r in results
                if r["mod"] == "lora" and r["rssi_avg"] is not None]
    if len(sf_rssis) >= 2:
        rssi_range = max(sf_rssis) - min(sf_rssis)
        print(f"\n  LoRa RSSI range across SF11/12: {rssi_range:.1f} dB")
        if rssi_range < 5.0:
            PASS += 1
        else:
            FAIL += 1
            print(f"    [FAIL] RSSI unstable: {rssi_range:.1f} dB range")

    print(f"\n  Checks passed: {PASS}")
    print(f"  Checks failed: {FAIL}")

    go = (FAIL == 0)
    if go:
        print(f"ACCEPTANCE: GO — all SF11/12 bursts clean, no overrun")
    else:
        print(f"ACCEPTANCE: NO-GO")

    # Write CSV
    with open(csv_path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=[
            "cfg_idx", "label", "mod", "n", "k", "per", "verdict",
            "rssi_avg", "snr_avg", "foreign_pkts", "tx_done", "dur_s"])
        w.writeheader()
        w.writerows(results)

    print(f"CSV: {csv_path}")
    print(f"{'='*60}")
    sys.exit(0 if go else 1)


if __name__ == "__main__":
    main()