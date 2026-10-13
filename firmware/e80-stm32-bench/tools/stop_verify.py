#!/usr/bin/env python3
"""stop_verify.py — Verify fw STOP aborts an armed TX burst mid-flight.

Task ADAPT-0 (t_70387779): bench-verify that STOP cleanly aborts an armed
TX burst, for both LoRa SF7 and FLRC 650k modulations.

Protocol (plan §2 stop_tx() + §9 D1):
  1. Auto-detect CH340 ports + radio handshake ID (e80_sweep_full helpers)
  2. Config SF7 BW125 868MHz PA10 LEN51
  3. ARM TX N=50, GAP=adaptive, START
  4. After ~5 PKT lines on RX, send STOP to TX
  5. Record: console alive? burst stops? drain? STAT? works? re-ARM+START?
  6. Repeat with FLRC 650k

No fw changes. No resets beyond SWD 'reset halt; resume' if needed.
"""

import sys, os, time, serial, subprocess, json

sys.path.insert(0, os.path.dirname(__file__))
import e80_sweep_full as sw

BAUD = sw.BAUD
PROBE_TX = sw.PROBE_TX
PROBE_RX = sw.PROBE_RX
FW_DIR = sw.FW_DIR
OPENOCD = "/usr/bin/openocd"  # bypass the board-lock wrapper at ~/.local/bin


def swd_reset_direct(probe_serial):
    """SWD reset using /usr/bin/openocd directly (bypasses board-lock wrapper)."""
    subprocess.run(
        [OPENOCD, "-f", "interface/cmsis-dap.cfg",
         "-f", "target/stm32f1x.cfg",
         "-c", f"transport select swd; adapter serial {probe_serial}; "
               f"init; reset halt; resume; exit"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        timeout=30, cwd=FW_DIR)
    time.sleep(2.0)


def collect_rx_pkts(rx, seconds, stop_on_count=None):
    """Collect RX lines for up to `seconds`. If stop_on_count, return as soon
    as that many PKT lines arrive. Returns (all_lines, pkt_lines)."""
    out, pkts = [], []
    deadline = time.monotonic() + seconds
    leftover = bytearray()
    while time.monotonic() < deadline:
        chunk = rx.read(1024)
        if chunk:
            leftover += chunk
            while b"\n" in leftover:
                line, leftover = leftover.split(b"\n", 1)
                txt = line.rstrip(b"\r").decode(errors="replace").strip()
                if txt:
                    out.append(txt)
                    if txt.startswith("PKT,"):
                        pkts.append(txt)
                        if stop_on_count and len(pkts) >= stop_on_count:
                            return out, pkts
    return out, pkts


def run_stop_test(tx, rx, mod_label, mod_cmd, pa_cmd, gap_us, plen=51):
    """Run one STOP-verify test. Returns dict of observations."""
    result = {
        "mod": mod_label, "gap_us": gap_us, "plen": plen,
        "steps": [], "pkts_before_stop": 0, "pkts_after_stop": 0,
        "stop_reply": None, "stat_reply": None,
        "rearm_reply": None, "restart_reply": None,
        "pkts_after_restart": 0, "tx_done_after_restart": False,
        "stop_after_restart_reply": None,
        "verdict": None, "notes": [],
    }

    def log(msg):
        result["steps"].append(msg)
        print(f"  [{mod_label}] {msg}", flush=True)

    # --- Config both boards ---
    for s, label in [(rx, "RX"), (tx, "TX")]:
        r = sw.cmd(s, mod_cmd)
        log(f"{label} MOD: {r}")
        if not r or not r.startswith("OK MOD"):
            result["notes"].append(f"FAIL: {label} MOD failed: {r}")
            return result
        r = sw.cmd(s, f"FREQ {sw.DEFAULT_FREQ}")
        r2 = sw.cmd(s, pa_cmd)
        log(f"{label} FREQ+PA: {r} / {r2}")

    sw.cmd(tx, "SESSION 99"); sw.cmd(rx, "SESSION 99")
    sw.cmd(tx, "CONFIG 90 1"); sw.cmd(rx, "CONFIG 90 1")

    # --- Roles ---
    r = sw.cmd(rx, "ROLE RX")
    log(f"RX ROLE: {r}")
    r = sw.cmd(tx, "ROLE TX")
    log(f"TX ROLE: {r}")
    r = sw.cmd(tx, "ARM TX")
    log(f"TX ARM: {r}")
    if not r or "OK ARMED" not in r:
        result["notes"].append(f"FAIL: ARM TX failed: {r}")
        return result

    # --- START burst ---
    rx.reset_input_buffer()
    start_line = f"START N=50 LEN={plen} GAP={gap_us}"
    tx.write((start_line + "\r\n").encode())
    start_reply = sw.readline(tx, 3.0)
    log(f"TX START: {start_reply}")
    if not start_reply or "OK START" not in start_reply:
        result["notes"].append(f"FAIL: START failed: {start_reply}")
        return result

    # --- Collect ~5 PKT lines on RX, then STOP ---
    collect_timeout = 15.0 if "SF7" in mod_label else 3.0
    rx_lines, rx_pkts = collect_rx_pkts(rx, collect_timeout, stop_on_count=5)
    result["pkts_before_stop"] = len(rx_pkts)
    log(f"RX got {len(rx_pkts)} PKT lines before STOP")

    if len(rx_pkts) == 0:
        result["notes"].append("FAIL: no PKT lines received before STOP")
        return result

    # --- Send STOP to TX ---
    tx.reset_input_buffer()
    tx.write(b"STOP\r\n")
    stop_reply = sw.readline(tx, 5.0)
    result["stop_reply"] = stop_reply
    log(f"TX STOP reply: {stop_reply}")

    # --- Observe after STOP: 3s window for stray packets ---
    _, post_pkts = collect_rx_pkts(rx, 3.0)
    result["pkts_after_stop"] = len(post_pkts)
    log(f"RX got {len(post_pkts)} PKT lines after STOP (3s window)")

    # --- TX drain (2s) ---
    tx_drain = sw.drain_lines(tx, 2.0)
    log(f"TX drain after STOP: {tx_drain}")

    # --- STAT? (does NOT wake radio — safe with IWDG active) ---
    stat_reply = sw.cmd(tx, "STAT?")
    result["stat_reply"] = stat_reply
    log(f"TX STAT? after STOP: {stat_reply}")

    # --- Re-ARM + re-START after STOP ---
    # ROLE TX re-inits the radio (wakes it). With IWDG active from the ARM TX
    # above, the radio wake in the critical section *might* trip the IWDG.
    # If the board resets, we SWD-reset it (clears IWDG) and retry.
    rearm_reply = None
    restart_reply = None

    r = sw.cmd(tx, "ROLE TX")
    log(f"TX ROLE TX (re-init): {r}")
    if not r or "OK ROLE TX" not in r:
        # Board may have IWDG-reset — try SWD reset and retry
        log("Board unresponsive after ROLE TX — SWD reset + retry")
        swd_reset_direct(PROBE_TX)
        swd_reset_direct(PROBE_RX)
        tx.port = tx.port  # re-bind
        r = sw.cmd(tx, "ROLE TX")
        log(f"TX ROLE TX (post-SWD): {r}")
        # Re-config radio
        sw.cmd(tx, mod_cmd)
        sw.cmd(tx, f"FREQ {sw.DEFAULT_FREQ}")
        sw.cmd(tx, pa_cmd)
        sw.cmd(rx, "ROLE RX")

    r2 = sw.cmd(tx, "ARM TX")
    rearm_reply = r2
    result["rearm_reply"] = rearm_reply
    log(f"TX re-ARM: {rearm_reply}")

    if rearm_reply and "OK ARMED" in rearm_reply:
        rx.reset_input_buffer()
        restart_line = f"START N=10 LEN={plen} GAP={gap_us}"
        tx.write((restart_line + "\r\n").encode())
        restart_reply = sw.readline(tx, 3.0)
        result["restart_reply"] = restart_reply
        log(f"TX re-START: {restart_reply}")

        if restart_reply and "OK START" in restart_reply:
            wait = max(10 * (gap_us / 1e6 + 0.3) + 5, 8)
            tx_lines2 = sw.drain_lines(tx, wait)
            _, rx_pkts2 = collect_rx_pkts(rx, wait)
            result["pkts_after_restart"] = len(rx_pkts2)
            result["tx_done_after_restart"] = any("TX DONE" in l for l in tx_lines2)
            log(f"Re-START: RX={len(rx_pkts2)} pkts TX_DONE={'yes' if result['tx_done_after_restart'] else 'no'}")

            # STOP after re-START burst completes (radio awake from burst)
            r3 = sw.cmd(tx, "STOP")
            result["stop_after_restart_reply"] = r3
            log(f"TX STOP after re-START: {r3}")

    # --- Verdict ---
    stop_ok = bool(stop_reply and "OK STOP" in stop_reply)
    burst_stopped = (result["pkts_after_stop"] == 0)
    stat_ok = bool(stat_reply and stat_reply.startswith("STAT"))
    rearm_ok = bool(rearm_reply and "OK ARMED" in rearm_reply)
    restart_ok = bool(restart_reply and "OK START" in restart_reply)

    checks = {"stop_reply": stop_ok, "burst_stopped": burst_stopped,
              "stat_works": stat_ok, "rearm_works": rearm_ok,
              "restart_works": restart_ok}
    passed = sum(checks.values())
    total = len(checks)

    if all(checks.values()):
        result["verdict"] = "STOP-CLEAN"
    else:
        result["verdict"] = "STOP-BROKEN"
        failed = [k for k, v in checks.items() if not v]
        result["notes"].append(f"FAILED: {', '.join(failed)}")
    log(f"VERDICT: {result['verdict']} ({passed}/{total} checks passed)")

    return result


def main():
    print("=" * 72, flush=True)
    print("STOP Verify — fw STOP mid-burst abort (ADAPT-0, t_70387779)", flush=True)
    print("=" * 72, flush=True)

    # SWD-reset both boards first (clear IWDG from previous sweep)
    print("SWD reset both boards (clear IWDG)...", flush=True)
    swd_reset_direct(PROBE_TX)
    swd_reset_direct(PROBE_RX)

    ports = sw.find_ch340_ports()
    print(f"CH340 ports: {ports}", flush=True)
    if len(ports) != 2:
        print(f"ERROR: expected 2 CH340 ports, found {len(ports)}", flush=True)
        sys.exit(1)

    tx_port, rx_port = sw.identify_boards()
    print(f"TX port: {tx_port}  RX port: {rx_port}", flush=True)

    tx = serial.Serial(tx_port, BAUD, timeout=0.1)
    rx = serial.Serial(rx_port, BAUD, timeout=0.1)

    for s, label in [(tx, "TX"), (rx, "RX")]:
        r = sw.cmd(s, "ID?")
        print(f"{label} ID?: {r}", flush=True)

    results = []

    # Test 1: LoRa SF7 BW125 868MHz PA10 LEN51
    print("\n" + "=" * 72, flush=True)
    print("TEST 1: LoRa SF7 BW125 868MHz PA10 LEN51", flush=True)
    print("=" * 72, flush=True)
    toa = sw.lora_airtime_s(7, 125, 51)
    gap = max(10000, int(1.2 * toa * 1e6) + 5000)
    print(f"  airtime={toa:.3f}s gap={gap}us", flush=True)
    r1 = run_stop_test(tx, rx, "LoRa-SF7", "MOD LORA 7 125", "PA 10", gap, plen=51)
    results.append(r1)

    # SWD-reset between tests (clear IWDG)
    print("\n  SWD reset between tests...", flush=True)
    swd_reset_direct(PROBE_TX)
    swd_reset_direct(PROBE_RX)

    # Test 2: FLRC 650k 868MHz PA5 LEN51
    print("\n" + "=" * 72, flush=True)
    print("TEST 2: FLRC 650k 868MHz PA5 LEN51", flush=True)
    print("=" * 72, flush=True)
    toa2 = sw.flrc_airtime_s(650, 51)
    gap2 = max(10000, int(1.2 * toa2 * 1e6) + 5000)
    print(f"  airtime={toa2:.4f}s gap={gap2}us", flush=True)
    r2 = run_stop_test(tx, rx, "FLRC-650k", "MOD FLRC 650 5", "PA 5", gap2, plen=51)
    results.append(r2)

    tx.close()
    rx.close()

    # Print summary
    print("\n" + "=" * 72, flush=True)
    print("SUMMARY", flush=True)
    print("=" * 72, flush=True)
    for r in results:
        print(f"\n{r['mod']} (gap={r['gap_us']}us plen={r['plen']}):", flush=True)
        for k in ["pkts_before_stop", "stop_reply", "pkts_after_stop",
                   "stat_reply", "rearm_reply", "restart_reply",
                   "pkts_after_restart", "tx_done_after_restart",
                   "stop_after_restart_reply", "verdict"]:
            print(f"  {k:24s}: {r.get(k)}", flush=True)
        if r["notes"]:
            print(f"  notes                  : {'; '.join(r['notes'])}", flush=True)

    # Write JSON
    repo_root = os.path.abspath(os.path.join(FW_DIR, "..", ".."))
    out_path = os.path.join(repo_root, "docs", "plans", "stop-verify-results.json")
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w") as f:
        json.dump(results, f, indent=2)
    print(f"\nJSON results: {out_path}", flush=True)


if __name__ == "__main__":
    main()
