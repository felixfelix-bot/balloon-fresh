#!/usr/bin/env python3
"""RFA-1b PRAM-patch bench matrix runner (card t_0eaed49b).

Sweeps the FLRC cells that carry the anomaly — 64 B and 128 B at 260/650 kbps
with the 255 B control — on a two-board E80 bench pair, for each patch arm:

    none  : the unmodified binary (baseline firmware, no PATCH command)
    off   : patched binary, PATCH OFF   (control within the new binary)
    on    : patched binary, PATCH ON    (ExpressLRS sequence)

Boards live on different hosts in the current topology (x240 = TX arm,
x280 = RX arm). Every console interaction is delegated to
tools/e80_serial_agent.py, local or over ssh, so both paths are identical; the
runner itself can sit on either host.

Usage (from firmware/e80-stm32-bench):
    python3 tools/rfa1b_pram_matrix.py --arm none --outdir ~/rfa1b/arm-none
    python3 tools/rfa1b_pram_matrix.py --arm on   --outdir ~/rfa1b/arm-on

Env overrides: RFA1B_TX_PORT / RFA1B_RX_PORT / RFA1B_TX_HOST / RFA1B_RX_HOST
               RFA1B_BAUD (default 115200)
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import subprocess
import sys
import time
from dataclasses import dataclass, field

HERE = os.path.dirname(os.path.abspath(__file__))
AGENT = os.path.join(HERE, "e80_serial_agent.py")
REMOTE_AGENT = "/tmp/e80_serial_agent.py"

FREQ_HZ = 869850000          # in-band (863-870 MHz), max-power sub-band neighbour
PA_DBM = 22                  # default; overridden by --pa (POWER MODE OUTDOOR 2026
                             # unlocks up to +22, the historical v5/v6 matrix used 10)
N_PKTS = 200
GAP_US = 10000               # START GAP is MICROSECONDS
CELLS = [(260, 64), (650, 64), (260, 128), (650, 128), (260, 255), (650, 255)]

# RFA-1c pre-flash control (env RFA1C_TX_RATE_DETOUR=1). On the pre-fix firmware
# a 650 cell that follows a 260 cell is deaf, because apply_cfg() only re-ran the
# chip bring-up (reset + calibrate) on a FLRC<->LoRa change. This prelude makes
# the TX re-enter apply_cfg() with a changed modulation right before each
# intra-FLRC rate change, i.e. the exact control the RFA-1b follow-up used by
# hand (TX 260 -> lora -> 650 = HEALTHY rx=100 @ -57 dBm). It does NOT test the
# fixed firmware — that needs the SWD flash. It confirms, harness-driven, that a
# bring-up re-run on the TX cures every 650-after-260 cell, so the flashed fix
# is expected to land clean.
DETOUR_SF = 8
DETOUR_BW_KHZ = 125


@dataclass
class Board:
    name: str
    host: str | None      # None = local
    port: str
    baud: int = 115200
    sentinel: object = field(default=None, repr=False)


def sh(cmd: list[str], **kw) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, text=True, **kw)


def push_agent(board: Board) -> None:
    if board.host is None:
        return
    r = sh(["scp", "-q", AGENT, f"{board.host}:{REMOTE_AGENT}"])
    if r.returncode != 0:
        raise SystemExit(f"scp agent to {board.host} failed: {r.stderr}")


def run_ops(board: Board, ops: list[dict], out_local: str, tag: str,
            wait: bool = True, mark_file: str | None = None,
            timeout_s: float = 300.0) -> dict:
    """Run an ops script on the board's host; return the parsed result JSON."""
    b64 = base64.b64encode(json.dumps(ops).encode()).decode()
    remote_out = f"/tmp/rfa1b_{tag}.json"
    mark = mark_file or f"/tmp/rfa1b_{tag}.mark"
    inner = (f"python3 {REMOTE_AGENT if board.host else AGENT} --port {board.port} "
             f"--baud {board.baud} "
             f"--ops-b64 {b64} --out {remote_out} --mark-file {mark}")
    cmd = ["sg", "dialout", "-c", inner]
    if board.host:
        cmd = ["ssh", "-o", "BatchMode=yes", board.host, " ".join(
            ["sg", "dialout", "-c", f"'{inner}'"])]
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if not wait:
        # Hand the marker path back with its host prefix so wait_mark() probes
        # it REMOTELY. Without the prefix wait_mark() stats a local path, never
        # sees the remote marker, burns the full timeout, and the TX burst fires
        # into the void -> phantom "0 packets" cells (found 2026-10-14).
        mark_handle = f"{board.host}:{mark}" if board.host else mark
        return {"proc": proc, "out": remote_out, "mark": mark_handle}
    try:
        stdout, stderr = proc.communicate(timeout=timeout_s)
    except subprocess.TimeoutExpired:
        proc.kill()
        return {"error": f"agent timeout after {timeout_s}s", "lines": []}
    if board.host:
        fetched = sh(["ssh", "-o", "BatchMode=yes", board.host, f"cat {remote_out}"])
        raw = fetched.stdout
    else:
        if os.path.exists(remote_out):
            with open(remote_out) as fh:
                raw = fh.read()
        else:
            raw = ""
    if not raw.strip():
        return {"error": f"no agent output (rc={proc.returncode} stderr={stderr.strip()[:200]})",
                "lines": []}
    return json.loads(raw)


def rx_bg_mark(tag: str) -> str:
    """Mark file the RX agent touches when its listen window opens."""
    return f"/tmp/rfa1b_rx_{tag}.mark"


def wait_mark(path: str, timeout_s: float) -> bool:
    if ":" in path:  # remote marker fetched over ssh
        host, rpath = path.split(":", 1)
        deadline = time.time() + timeout_s
        while time.time() < deadline:
            r = sh(["ssh", "-o", "BatchMode=yes", host, f"cat {rpath} 2>/dev/null"])
            if r.stdout.strip():
                return True
            time.sleep(0.2)
        return False
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        if os.path.exists(path):
            return True
        time.sleep(0.2)
    return False


def parse_lines(lines: list[str], config_id: int | None = None) -> dict:
    """Pull the PKT lines + STAT/ID lines out of a console capture.

    config_id filters the PKT lines to one cell (the RX board emits packets
    for every burst it hears, including the previous cell's tail; the TX
    sequence counter is persistent, so seq alone cannot delimit a cell)."""
    pkts = []
    stats = None
    ids = []
    markers = []
    other_cfg = 0
    for line in lines:
        if line.startswith("PKT,"):
            f = line.split(",")
            if len(f) >= 10:
                try:
                    rec = {"seq": int(f[4]), "ts_ms": int(f[5]), "rssi": int(f[6]),
                           "snr": int(f[7]), "crc_ok": int(f[8]), "config": int(f[2]),
                           "len": int(f[17]) if len(f) > 17 else None}
                except ValueError:
                    continue
                if config_id is not None and rec["config"] != config_id:
                    other_cfg += 1
                    continue
                pkts.append(rec)
        elif line.startswith("STAT "):
            stats = parse_kv(line, "STAT")
        elif line.startswith("CONFIG_START,"):
            markers.append(line)
        elif line.startswith("ID E80BENCH"):
            ids.append(parse_kv(line, "ID"))
    return {"pkts": pkts, "stat": stats, "id": ids[-1] if ids else None,
            "config_markers": markers, "pkts_other_config": other_cfg}


def parse_kv(line: str, _tag: str) -> dict:
    out: dict = {}
    for tok in line.split():
        if "=" in tok:
            k, v = tok.split("=", 1)
            out[k] = v
    return out


def detour_enabled(env_var: str, flag: bool | None) -> bool:
    """Resolve the RFA-1c rate-detour switch.

    DEFAULT ON since 2026-10-14. Rationale: the boards still run the pre-fix
    firmware (5fa7912) — there is no reachable write path to the MCU (BOOT0 is
    tied to GND, the SWD header has never linked up), so the merged RFA-1c fix
    cannot be flashed. Until it is, EVERY matrix run must detour or a 260->650
    cell silently measures the bug instead of the radio.

    Precedence: explicit --detour / --no-detour beats the env var.
      RFA1C_TX_RATE_DETOUR=1 / RFA1C_RX_RATE_DETOUR=1  -> force on for that arm
      RFA1C_TX_RATE_DETOUR=0 / RFA1C_RX_RATE_DETOUR=0  -> force off for that arm
      unset                                            -> ON (flag or default)
    Pass --no-detour once the fixed firmware is verified on the boards: with it
    the detour is wrong, because the firmware then re-calibrates by itself.
    """
    if flag is not None:
        return flag
    env = os.environ.get(env_var)
    if env is not None and env != "":
        return env not in ("0", "false", "False", "no", "off")
    return True


def pre_ops(br: int, role: str, patch_arm: str, config_id: int,
            pa_dbm: int = PA_DBM, freq_hz: int = FREQ_HZ,
            detour: bool = False) -> list[dict]:
    """Configure a board and put it in its role / arm it. No length-dependent
    work, so it can run on the TX board while the RX agent is not yet up.

    CONFIG tags every PKT line with this cell's id, so host-side counting can
    never mix bursts: the RX board keeps receiving whenever the TX transmits,
    and the TX sequence counter persists across cells.

    detour (RFA-1c, pre-flash control): prefix the cell with a LoRa hop so the
    board re-enters the bring-up before an intra-FLRC rate change. MOD alone
    only rewrites cfg on a TX board, so the hop is paired with a ROLE re-issue,
    which is what calls apply_cfg() and performs the reset+calibrate. On an RX
    board the hop is enough by itself (MOD re-arms RX through radio_rearm_rx)
    but the extra ROLE keeps both arms byte-identical."""
    ops: list[dict] = []
    if detour:
        ops += [
            {"op": "send", "cmd": f"MOD loRa {DETOUR_SF} {DETOUR_BW_KHZ}",
             "expect": "OK MOD", "retries": 3},
            {"op": "send", "cmd": f"ROLE {role}", "expect": f"OK ROLE {role}", "retries": 3},
        ]
    if patch_arm in ("on", "off"):
        ops.append({"op": "send", "cmd": f"PATCH {patch_arm.upper()}",
                    "expect": "OK PATCH", "retries": 3, "timeout_s": 8.0})
    ops.append({"op": "send", "cmd": f"CONFIG {config_id} 0", "expect": "OK CONFIG",
                "retries": 3})
    ops += [
        {"op": "send", "cmd": f"MOD flrc {br} 10", "expect": "OK MOD", "retries": 3},
        {"op": "send", "cmd": f"FREQ {freq_hz}", "expect": "OK FREQ", "retries": 3},
        {"op": "send", "cmd": "POWER MODE OUTDOOR 2026", "expect": "OK POWER", "retries": 3},
        {"op": "send", "cmd": f"PA {pa_dbm}", "expect": "OK PA", "retries": 3},
        {"op": "send", "cmd": f"ROLE {role}", "expect": f"OK ROLE {role}", "retries": 3},
    ]
    return ops


def rx_ops(br: int, patch_arm: str, len_bytes: int) -> list[dict]:
    """RX arm: set the expected length (START), then listen for the burst.

    START is what arms the RX with the FIX_LEN window and resets its stats, so
    it must run immediately before the listen window — that is why the RX
    config runs as ONE agent invocation, launched just before the TX burst."""
    airtime_ms = {260: 12.0, 650: 5.0}.get(br, 12.0)
    hold_s = 25.0 + N_PKTS * (airtime_ms + GAP_US / 1000.0) / 1000.0
    return [
        # RX START reply is "OK RX ARMED len=<n>" (bench.c RX branch). A retry
        # here would re-reset the RX stats, so one attempt, longer timeout.
        {"op": "send", "cmd": f"START N={N_PKTS} LEN={len_bytes} GAP={GAP_US}",
         "expect": "OK RX ARMED", "retries": 1, "timeout_s": 5.0},
        {"op": "listen", "seconds": hold_s, "mark": f"LISTENING {br} {len_bytes}"},
        {"op": "send", "cmd": "STAT?", "expect": "STAT role=", "retries": 3},
    ]


def tx_burst_ops(len_bytes: int) -> list[dict]:
    """ARM TX + START as ONE write (2-4 s IWDG window), then wait for the end."""
    return [
        {"op": "send", "cmd": f"ARM TX\nSTART N={N_PKTS} LEN={len_bytes} GAP={GAP_US}",
         "expect": "OK START", "retries": 2, "timeout_s": 8.0},
        {"op": "wait", "expect": "TX DONE", "timeout_s": 120.0},
        {"op": "send", "cmd": "STAT?", "expect": "STAT role=", "retries": 3},
    ]


def probe_ids(tx: Board, rx: Board) -> dict:
    out = {}
    for key, board in (("tx", tx), ("rx", rx)):
        res = run_ops(board, [{"op": "send", "cmd": "ID?", "expect": "ID E80BENCH", "retries": 3}],
                      f"/tmp/rfa1b_id_{key}.json", f"id_{key}")
        out[key] = (res or {}).get("id")
    return out


def run_cell(tx: Board, rx: Board, arm: str, br: int, len_bytes: int, outdir: str,
             config_id: int, pa_dbm: int = PA_DBM, freq_hz: int = FREQ_HZ,
             tx_detour: bool = False, rx_detour: bool = False) -> dict:
    tag = f"{arm}_{br}_{len_bytes}_{config_id}"
    print(f"--- cell {tag}", flush=True)

    # 1. TX pre-config (idle radio). Slow over ssh, so it runs BEFORE the RX
    #    listen window opens — otherwise the config eats the RX window.
    tx_pre = run_ops(tx, pre_ops(br, "TX", arm, config_id, pa_dbm, freq_hz, tx_detour),
                     f"/tmp/rfa1b_txpre_{tag}.json", f"txpre_{tag}", timeout_s=180.0)

    # 2. RX: one agent run (configure -> START -> listen -> STAT?). The marker
    #    is written the moment the listen window opens, i.e. once the RX holds
    #    the FIX_LEN window for this cell. Any stale marker from an earlier run
    #    of the same tag MUST be gone first, or the burst fires into the RX's
    #    config phase (learned the hard way).
    if rx.host is None:
        stale = rx_bg_mark(tag)
        if os.path.exists(stale):
            os.remove(stale)
    rx_bg = run_ops(rx, pre_ops(br, "RX", arm, config_id, pa_dbm, freq_hz, rx_detour) +
                    rx_ops(br, arm, len_bytes),
                    f"/tmp/rfa1b_rx_{tag}.json", f"rx_{tag}", wait=False,
                    timeout_s=300.0)
    if "proc" not in rx_bg:
        raise SystemExit(f"RX agent failed to start for {tag}: {rx_bg}")
    mark_ok = wait_mark(rx_bg["mark"], 60.0)
    if not mark_ok:
        print(f"    WARN: RX did not reach listen phase for {tag}", flush=True)

    # 3. Burst.
    tx_res = run_ops(tx, tx_burst_ops(len_bytes), f"/tmp/rfa1b_tx_{tag}.json",
                     f"tx_{tag}", timeout_s=180.0)

    rx_proc = rx_bg["proc"]
    try:
        rx_proc.communicate(timeout=120.0)
    except subprocess.TimeoutExpired:
        rx_proc.kill()
    rx_out = run_ops_fetch(rx, rx_bg["out"])
    tx_out = tx_res if isinstance(tx_res, dict) and "lines" in tx_res else {"lines": [], "error": str(tx_res)}

    rx_parsed = parse_lines(rx_out.get("lines", []), config_id)
    tx_parsed = parse_lines(tx_out.get("lines", []))

    cell = {
        "arm": arm, "br_kbps": br, "len": len_bytes,
        "pa_dbm": pa_dbm, "freq_hz": freq_hz,
        "tx_detour": tx_detour, "rx_detour": rx_detour,
        "tx_port": tx.port, "rx_port": rx.port,
        "rx_lines": rx_out.get("lines", []),
        "tx_lines": tx_out.get("lines", []),
        "rx_stat": rx_parsed["stat"], "tx_stat": tx_parsed["stat"],
        "rx_id": rx_parsed["id"], "tx_id": tx_parsed["id"],
        "config_id": config_id,
        "rx_config_markers": rx_parsed["config_markers"],
        "rx_pkts_other_config": rx_parsed["pkts_other_config"],
        "rx_pkts": len(rx_parsed["pkts"]),
        "rx_crc_ok": sum(1 for p in rx_parsed["pkts"] if p["crc_ok"] == 1),
        "rx_crc_bad": sum(1 for p in rx_parsed["pkts"] if p["crc_ok"] != 1),
        "tx_ops_ok": all(o.get("ok") for o in (tx_out.get("ops") or [])),
        "rx_ops_ok": all(o.get("ok") for o in (rx_out.get("ops") or [])),
        "tx_pre_ok": all(o.get("ok") for o in ((tx_pre or {}).get("ops") or [])),
        "rx_error": rx_out.get("error"), "tx_error": tx_out.get("error"),
        "tx_pre_ops": (tx_pre or {}).get("ops"),
        "rx_ops": rx_out.get("ops"), "tx_ops": tx_out.get("ops"),
    }
    os.makedirs(outdir, exist_ok=True)
    with open(os.path.join(outdir, f"cell-{tag}.json"), "w") as fh:
        json.dump(cell, fh, indent=1)
    print(f"    rx_pkts={cell['rx_pkts']} crc_ok={cell['rx_crc_ok']} "
          f"crc_bad={cell['rx_crc_bad']} rx_stat={cell['rx_stat']}", flush=True)
    return cell


def run_ops_fetch(board: Board, remote_out: str) -> dict:
    if board.host:
        r = sh(["ssh", "-o", "BatchMode=yes", board.host, f"cat {remote_out}"])
        raw = r.stdout
    else:
        raw = open(remote_out).read() if os.path.exists(remote_out) else ""
    if not raw.strip():
        return {"lines": [], "error": f"no output at {remote_out}"}
    return json.loads(raw)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--arm", default="none", choices=["none", "off", "on"])
    ap.add_argument("--outdir", required=True)
    ap.add_argument("--cells", default="", help="override: '260:64,650:128'")
    ap.add_argument("--ids-only", action="store_true")
    ap.add_argument("--pa", type=int, default=PA_DBM, help="TX PA in dBm (10 indoor, 22 outdoor)")
    ap.add_argument("--freq", type=int, default=FREQ_HZ)
    ap.add_argument("--detour", dest="detour", action="store_true", default=None,
                    help="force the RFA-1c LoRa rate-detour ON for both arms")
    ap.add_argument("--no-detour", dest="detour", action="store_false",
                    help="force it OFF (only correct on firmware that "
                         "re-calibrates by itself, i.e. after the RFA-1c flash)")
    args = ap.parse_args()

    tx_host = os.environ.get("RFA1B_TX_HOST", "x240")
    tx_port = os.environ.get("RFA1B_TX_PORT", "/dev/ttyUSB0")
    rx_host = os.environ.get("RFA1B_RX_HOST") or None
    rx_port = os.environ.get("RFA1B_RX_PORT", "/dev/ttyUSB1")
    baud = int(os.environ.get("RFA1B_BAUD", "115200"))

    tx = Board("TX", tx_host or None, tx_port, baud)
    rx = Board("RX", rx_host, rx_port, baud)
    push_agent(tx)
    push_agent(rx)

    ids = probe_ids(tx, rx)
    print(f"IDs: TX={ids['tx']}\n     RX={ids['rx']}", flush=True)
    if args.ids_only:
        return 0

    cells = CELLS
    if args.cells:
        cells = [tuple(int(x) for x in c.split(":")) for c in args.cells.split(",")]
    os.makedirs(args.outdir, exist_ok=True)

    results = []
    detour_tx = detour_enabled("RFA1C_TX_RATE_DETOUR", args.detour)
    detour_rx = detour_enabled("RFA1C_RX_RATE_DETOUR", args.detour)
    if detour_tx or detour_rx:
        print(f"NOTE RFA-1c rate detour ON (tx={detour_tx} rx={detour_rx}): each cell "
              "whose bitrate differs from its predecessor makes that board re-enter "
              "the bring-up via a LoRa hop. This is the pre-flash CONTROL, not the "
              "fixed firmware.", flush=True)
    prev_br: int | None = None
    for idx, (br, ln) in enumerate(cells, start=1):
        moved = bool(prev_br is not None and prev_br != br)
        results.append(run_cell(tx, rx, args.arm, br, ln, args.outdir, idx,
                                args.pa, args.freq,
                                bool(detour_tx and moved), bool(detour_rx and moved)))
        prev_br = br
    with open(os.path.join(args.outdir, "summary.json"), "w") as fh:
        json.dump({"arm": args.arm, "pa_dbm": args.pa, "freq_hz": args.freq,
                   "tx_rate_detour": detour_tx, "rx_rate_detour": detour_rx,
                   "ids": ids, "cells": results}, fh, indent=1)
    print(f"\nsummary -> {os.path.join(args.outdir, 'summary.json')}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
