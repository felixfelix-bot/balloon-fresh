#!/usr/bin/env python3
"""e80_range_test.py — distributed E80 range test client.

Connects to two board servers (one on each machine) over TCP and runs
a complete range-test campaign. Auto-detects which server is TX and which
is RX — the operator doesn't need to know which board is plugged into
which machine.

Reuses the campaign logic from e80_bench_ctl.py (matrix cells, N regime
rules, CSV format) but replaces BoardSerial with RemoteBoard (TCP client).

Output:
  - CSV file (append-only, one row per cell, '#' metadata comments)
  - Metadata JSON (test params, GPS, operator, timestamp, board IDs)

Usage:
    # Both servers already running on their machines:
    python3 e80_range_test.py TX_HOST=localhost TX_PORT=7780 \\
        RX_HOST=192.168.1.20 RX_PORT=7780 \\
        --site fieldA --stop S3 --dist-m 200 --repeat 1 \\
        --freq 868000000 --dbm 10

    # Let the client auto-detect roles (operator doesn't know which is TX):
    python3 e80_range_test.py HOST_A=localhost HOST_B=192.168.1.20 \\
        --site fieldA --stop S3 --dist-m 200

    # With GPS metadata:
    python3 e80_range_test.py TX_HOST=localhost RX_HOST=192.168.1.20 \\
        --operator alice --site fieldA --stop S3 --dist-m 200 \\
        --gps-tx 52.0123,4.0456 --gps-rx 52.0234,4.0123 \\
        --h-tx 1.5 --h-rx 1.5 --ground grass --weather "12C clear"
"""

from __future__ import annotations

import argparse
import json
import os
import socket
import sys
import time
import datetime

# Add sibling directory for imports
_TOOLS_DIR = os.path.dirname(os.path.abspath(__file__))
_REPO_TOOLS = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(_TOOLS_DIR))), "tools")
for p in (_TOOLS_DIR, _REPO_TOOLS):
    if p not in sys.path:
        sys.path.insert(0, p)

# Reuse campaign logic from e80_bench_ctl
from e80_bench_ctl import (
    BAUD,
    CSV_COLUMNS,
    INDOOR_CAP_DBM,
    TXPOW_MAX_DBM,
    UNLOCK_PIN,
    MOD_DEFS,
    MATRIX_KEYS,
    ANCHOR_KEY,
    ANCHOR_LEN,
    MATRIX_LEN,
    N_HI_DEFAULT,
    N_LO_DEFAULT,
    N_SF12_CAP,
    CI_HI_NHI_PCT,
    BAND_MIN_HZ,
    BAND_MAX_HZ,
    OVERRIDE_MIN_HZ,
    OVERRIDE_MAX_HZ,
    airtime_s,
    make_cell,
    n_for_mod,
    read_prior_rows,
    parse_stat,
    freq_gate,
    fmt_offset,
    fmt_hms,
    parse_t0,
    build_stop_schedule,
    build_matrix_cells,
)


# -----------------------------------------------------------------------
# RemoteBoard — drop-in replacement for BoardSerial over TCP
# -----------------------------------------------------------------------

class RemoteBoard:
    """Talks to a board server over TCP. Same interface as BoardSerial."""

    def __init__(self, host: str, port: int = 7780, label: str = "?"):
        self.host = host
        self.tcp_port = port
        self.label = label
        self.sock: socket.SocketType | None = None
        self._buf = ""
        self.hello: dict = {}
        self.role: str = "?"
        self.probe_serial: str | None = None
        self.port_name: str | None = None
        self.fw_hash: str | None = None
        self.id_reply: str | None = None

    def connect(self) -> dict:
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.settimeout(10.0)
        self.sock.connect((self.host, self.tcp_port))
        # Read hello
        hello = self._recv_json()
        if not hello or hello.get("type") != "hello":
            raise RuntimeError(f"no hello from {self.label} ({self.host})")
        self.hello = hello
        self.role = hello.get("role", "?")
        self.probe_serial = hello.get("probe_serial")
        self.port_name = hello.get("port")
        self.fw_hash = hello.get("fw")
        self.id_reply = hello.get("id")
        return hello

    def _recv_json(self) -> dict | None:
        assert self.sock is not None
        while "\n" not in self._buf:
            data = self.sock.recv(4096).decode(errors="replace")
            if not data:
                return None
            self._buf += data
        line, self._buf = self._buf.split("\n", 1)
        return json.loads(line.strip())

    def _send(self, obj: dict) -> dict:
        assert self.sock is not None
        self.sock.sendall((json.dumps(obj) + "\n").encode())
        resp = self._recv_json()
        if resp is None:
            raise RuntimeError(f"connection closed by {self.label}")
        return resp

    def query(self, line: str, prefixes=("OK", "ERR", "STAT", "ID"), timeout=15.0) -> str:
        resp = self._send({"cmd": "query", "line": line,
                           "prefixes": list(prefixes), "timeout": timeout})
        if not resp.get("ok"):
            raise RuntimeError(f"{self.label} query '{line}': {resp.get('error')}")
        return resp["reply"]

    def cmd(self, line: str, timeout=15.0) -> str:
        resp = self._send({"cmd": "cmd", "line": line, "timeout": timeout})
        if not resp.get("ok"):
            raise RuntimeError(f"{self.label} cmd '{line}': {resp.get('error')}")
        return resp["reply"]

    def stat(self) -> str:
        resp = self._send({"cmd": "stat"})
        if not resp.get("ok"):
            raise RuntimeError(f"{self.label} stat: {resp.get('error')}")
        return resp["reply"]

    def drain(self, seconds: float = 1.0) -> list[str]:
        resp = self._send({"cmd": "drain", "seconds": seconds})
        if not resp.get("ok"):
            return []
        return resp.get("lines", [])

    def swd_reset(self) -> bool:
        resp = self._send({"cmd": "swd_reset"})
        return resp.get("ok", False)

    def ensure_alive(self) -> bool:
        resp = self._send({"cmd": "ensure_alive"})
        return resp.get("alive", False)

    def close(self):
        if self.sock:
            try:
                self._send({"cmd": "close"})
            except Exception:
                pass
            try:
                self.sock.close()
            except Exception:
                pass
            self.sock = None

    # Make RemoteBoard compatible with BoardSerial API used by run_matrix
    def drain_serial(self, quiet=0.4):
        """BoardSerial-compatible drain (no-op for remote)."""
        pass


# -----------------------------------------------------------------------
# Auto-role-detect: figure out which host is TX, which is RX
# -----------------------------------------------------------------------

def auto_assign_roles(host_a: RemoteBoard, host_b: RemoteBoard) -> tuple[RemoteBoard, RemoteBoard]:
    """Given two connected RemoteBoard servers, return (tx_board, rx_board).

    Uses the hello message's role field (from SWD probe serial detection).
    Falls back to ID? role= field.
    """
    # Primary: probe serial → role (set during server auto-detection)
    if host_a.role in ("TX", "RX") and host_b.role in ("TX", "RX"):
        if host_a.role == "TX":
            return host_a, host_b
        else:
            return host_b, host_a

    # Fallback: check ID? role= field (runtime setting)
    for board, other in [(host_a, host_b), (host_b, host_a)]:
        try:
            reply = board.id_reply or board.query("ID?", prefixes=("ID", "ERR"), timeout=5.0)
            if reply:
                role = None
                for tok in reply.split():
                    if tok.startswith("role="):
                        role = tok.split("=", 1)[1].upper()
                        break
                if role == "TX":
                    return board, other
                if role == "RX":
                    return other, board
        except Exception:
            pass

    raise RuntimeError(
        f"could not auto-detect roles. Host A role={host_a.role}, "
        f"Host B role={host_b.role}. Use ID? to check manually."
    )


# -----------------------------------------------------------------------
# Metadata JSON writer
# -----------------------------------------------------------------------

def write_metadata_json(path: str, tx: RemoteBoard, rx: RemoteBoard, args,
                        t0_epoch: float, cells: list, csv_path: str | None):
    """Write a structured metadata JSON alongside the CSV."""
    meta = {
        "test_id": datetime.datetime.now().strftime("%Y%m%d-%H%M%S"),
        "timestamp_start": datetime.datetime.fromtimestamp(t0_epoch).isoformat(),
        "operator": args.operator,
        "tx": {
            "host": tx.host,
            "tcp_port": tx.tcp_port,
            "probe_serial": tx.probe_serial,
            "port": tx.port_name,
            "fw_hash": tx.fw_hash,
            "id": tx.id_reply,
            "gps": args.gps_tx,
            "antenna_height_m": args.h_tx,
        },
        "rx": {
            "host": rx.host,
            "tcp_port": rx.tcp_port,
            "probe_serial": rx.probe_serial,
            "port": rx.port_name,
            "fw_hash": rx.fw_hash,
            "id": rx.id_reply,
            "gps": args.gps_rx,
            "antenna_height_m": args.h_rx,
        },
        "params": {
            "site": args.site,
            "stop": args.stop,
            "distance_m": args.dist_m,
            "repeat": args.repeat,
            "frequency_hz": args.freq,
            "tx_power_dbm": args.dbm,
            "band_override": args.band_override,
            "matrix": args.matrix or MATRIX_KEYS,
            "cells": [{"label": c["label"], "n": c["n"], "len": c["len_bytes"],
                        "gap_us": c["gap_us"]} for c in cells],
        },
        "environment": {
            "ground": args.ground,
            "weather": args.weather,
        },
        "csv_file": csv_path,
    }
    with open(path, "w") as f:
        json.dump(meta, f, indent=2)
    return path


# -----------------------------------------------------------------------
# Distributed range test runner
# -----------------------------------------------------------------------

def run_distributed(args) -> int:
    """Run a full range-test campaign across two board servers."""

    # --- Connect to servers ---
    print(f"[client] Connecting to {args.tx_host}:{args.tcp_tx} ...", flush=True)
    host_a = RemoteBoard(args.tx_host, args.tcp_tx, label="HOST_A")
    host_a.connect()
    print(f"  HOST_A: role={host_a.role} probe={host_a.probe_serial or 'N/A'} "
          f"port={host_a.port_name} fw={host_a.fw_hash or '?'}", flush=True)

    print(f"[client] Connecting to {args.rx_host}:{args.tcp_rx} ...", flush=True)
    host_b = RemoteBoard(args.rx_host, args.tcp_rx, label="HOST_B")
    host_b.connect()
    print(f"  HOST_B: role={host_b.role} probe={host_b.probe_serial or 'N/A'} "
          f"port={host_b.port_name} fw={host_b.fw_hash or '?'}", flush=True)

    # --- Auto-assign TX/RX ---
    tx, rx = auto_assign_roles(host_a, host_b)
    print(f"[client] TX = {tx.label} ({tx.host}), RX = {rx.label} ({rx.host})", flush=True)

    if tx.role != "TX" or rx.role != "RX":
        print(f"[client] WARNING: roles from probe serial didn't match cleanly "
              f"(TX.role={tx.role}, RX.role={rx.role})", file=sys.stderr)

    # --- Validate args ---
    ok, msg = freq_gate(args.freq, args.band_override)
    if not ok:
        print(f"ERROR: {msg}", file=sys.stderr)
        tx.close(); rx.close()
        return 1
    if args.dbm > TXPOW_MAX_DBM:
        print(f"ERROR: dbm {args.dbm} above firmware max {TXPOW_MAX_DBM}", file=sys.stderr)
        tx.close(); rx.close()
        return 1

    matrix = args.matrix or list(MATRIX_KEYS)
    power_unlock = args.dbm > INDOOR_CAP_DBM

    # --- Build cells ---
    csv_path = args.csv or os.path.join(
        os.getcwd(),
        f"range-{args.site}-{args.stop}-r{args.repeat}.csv"
    )
    prior_rows = read_prior_rows(csv_path) if os.path.exists(csv_path) else []
    cells = build_matrix_cells(
        _make_args_namespace(args),
        prior_rows,
    )

    # --- Schedule ---
    t0 = parse_t0(args.t0) if args.t0 else time.time()
    starts = build_stop_schedule(cells, t0, args.t0_margin, args.guard)

    print(f"\n== RANGE MATRIX: site={args.site} stop={args.stop} dist={args.dist_m}m "
          f"repeat={args.repeat} | {args.freq/1e6} MHz +{args.dbm} dBm ==", flush=True)
    for c, s in zip(cells, starts):
        print(f"  cell {c['label']:<18} N={c['n']:<6} LEN={c['len_bytes']:<4} "
              f"GAP={c['gap_us']:<5} start={fmt_offset(s, t0)} ({fmt_hms(c['expected_s'])})",
              flush=True)

    # --- CSV log setup ---
    log = _CsvLogLite(csv_path)
    log.session_start(tx.fw_hash or "?", rx.fw_hash or "?", args.operator)
    log.stop_meta(args, id_tx=tx.id_reply or "", id_rx=rx.id_reply or "",
                   t0_str=datetime.datetime.fromtimestamp(t0).isoformat())

    # --- Metadata JSON path ---
    json_path = csv_path.replace(".csv", "-meta.json")
    if csv_path == json_path:
        json_path = csv_path + "-meta.json"

    # --- Pre-flight ---
    print("\n-- RX pre-flight --", flush=True)
    _preflight(rx, args, "RX", power_unlock)
    print("-- TX pre-flight --", flush=True)
    _preflight(tx, args, "TX", power_unlock)

    # --- Run cells ---
    def wait_until(ts):
        while True:
            d = ts - time.time()
            if d <= 0:
                return
            time.sleep(min(d, 30.0))

    try:
        for idx, (cell, start) in enumerate(zip(cells, starts)):
            print(f"\n-- cell {idx+1}/{len(cells)} {cell['label']} "
                  f"N={cell['n']} LEN={cell['len_bytes']} --", flush=True)
            mod_lines = [ln.format(dbm=args.dbm) for ln in cell["mod_lines"]]
            start_line = f"START N={cell['n']} LEN={cell['len_bytes']} GAP={cell['gap_us']}"

            # RX arms first
            wait_until(start - args.rx_lead)
            for ln in mod_lines:
                rx.cmd(ln)
            rx.cmd(start_line)

            # TX starts
            wait_until(start)
            for ln in mod_lines:
                tx.cmd(ln)
            tx.cmd(start_line, timeout=max(30.0, cell["expected_s"] + 60))

            # Poll TX until burst complete
            deadline = time.time() + cell["expected_s"] + 120
            while True:
                s = parse_stat(tx.stat())
                if s["sent_ok"] >= cell["n"]:
                    break
                if time.time() >= deadline:
                    raise RuntimeError(f"cell {cell['label']} TIMEOUT: "
                                       f"TX sent_ok={s['sent_ok']}/{cell['n']}")
                time.sleep(5.0 if cell["expected_s"] > 120 else 2.0)

            time.sleep(args.settle)
            rx_stat = parse_stat(rx.stat())
            tx_stat = parse_stat(tx.stat())

            ts = datetime.datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
            row = log.cell_row(args, cell, rx_stat, tx_stat, ts=ts)
            print(f"   -> recv={row[10]}/{cell['n']} per={row[11] or '?'} "
                  f"ci=[{row[12] or '?'},{row[13] or '?'}] rssi={row[14] or '?'} "
                  f"snr={row[15] or '?'}", flush=True)

        # Walk discipline
        tx.cmd("ROLE NONE")
        rx.cmd("ROLE NONE")
        print(f"\n[client] Campaign complete. CSV: {csv_path}", flush=True)

    except BaseException as e:
        log.abort(f"{type(e).__name__}: {e}")
        for b in (tx, rx):
            try:
                b.cmd("STOP", timeout=3.0) if False else b._send({"cmd": "query", "line": "STOP", "prefixes": ["OK", "ERR"], "timeout": 3.0})
            except Exception:
                pass
        raise

    finally:
        # Write metadata JSON
        write_metadata_json(json_path, tx, rx, args, t0, cells, csv_path)
        print(f"[client] Metadata: {json_path}", flush=True)
        tx.close()
        rx.close()

    return 0


# -----------------------------------------------------------------------
# Pre-flight helper (adapted from e80_bench_ctl.preflight)
# -----------------------------------------------------------------------

def _preflight(board: RemoteBoard, args, role: str, power_unlock: bool):
    """ID? capture, unlocks, role, FREQ — plan §1 pre-flight on one board."""
    id_before = board.query("ID?")
    if args.band_override:
        board.cmd(f"BAND OVERRIDE {UNLOCK_PIN}")
    if power_unlock:
        board.cmd(f"POWER MODE OUTDOOR {UNLOCK_PIN}")
    board.cmd(f"ROLE {role}")
    if role == "TX":
        board.cmd("ARM TX")
    board.cmd(f"FREQ {args.freq}")
    id_after = board.query("ID?")
    want_band = "band=OVERRIDE" if args.band_override else "band=863-870MHz"
    if want_band not in id_after:
        raise RuntimeError(f"{board.label}: ID? shows '{id_after}' missing {want_band}")
    if power_unlock and "pcap=+22dBm(OUTDOOR)" not in id_after:
        raise RuntimeError(f"{board.label}: power unlock not accepted")
    print(f"  {board.label}: ID? verified ({want_band})", flush=True)


# -----------------------------------------------------------------------
# Namespace adapter for reusing e80_bench_ctl functions
# -----------------------------------------------------------------------

def _make_args_namespace(args):
    """Create a namespace compatible with e80_bench_ctl.build_matrix_cells."""
    import types
    return types.SimpleNamespace(
        matrix=args.matrix or list(MATRIX_KEYS),
        anchor=args.anchor,
    )


# -----------------------------------------------------------------------
# CSV logger (lightweight, writes same format as e80_bench_ctl.CsvLog)
# -----------------------------------------------------------------------

class _CsvLogLite:
    """Append-only campaign CSV with '#' metadata, same format as CsvLog."""

    def __init__(self, path: str):
        self.path = path
        try:
            with open(path) as f:
                has_header = bool(f.readline().strip())
        except FileNotFoundError:
            has_header = False
        if not has_header:
            os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
            with open(path, "w", newline="") as f:
                f.write(",".join(CSV_COLUMNS) + "\n")

    def _comment(self, text: str):
        with open(self.path, "a") as f:
            f.write(f"# {text}\n")

    def session_start(self, tx_fw: str, rx_fw: str, operator: str):
        iso = datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
        self._comment(f"SESSION_START {iso} tx_fw={tx_fw} rx_fw={rx_fw} "
                      f"operator={operator} rig=e80-range-test-distributed")

    def stop_meta(self, args, id_tx="", id_rx="", t0_str=""):
        self._comment(f"STOP site={args.site} stop={args.stop} dist_m={args.dist_m} "
                      f"repeat={args.repeat} freq_hz={args.freq} dbm={args.dbm} t0={t0_str}")
        self._comment(f"gps_tx={args.gps_tx} gps_rx={args.gps_rx} "
                      f"h_tx_agl_m={args.h_tx} h_rx_agl_m={args.h_rx} "
                      f"ground={args.ground} weather={args.weather}")
        if id_tx:
            self._comment(f"id_tx: {id_tx}")
        if id_rx:
            self._comment(f"id_rx: {id_rx}")

    def abort(self, reason: str):
        self._comment(f"ABORT {reason}: stop invalid, re-run after clear")

    def cell_row(self, args, cell, rx_stat, tx_stat, ts=None) -> list:
        ts = ts or datetime.datetime.now().strftime("%Y-%m-%dT%H:%M:%S")

        def pct(v):
            return "" if v is None else f"{v:.6f}"
        def num(v):
            return "" if v is None else str(v)

        row = [args.site, args.stop, args.dist_m, args.repeat,
               cell["key"] + ("+anchor" if cell.get("anchor") else ""),
               cell["len_bytes"], args.dbm, args.freq, cell["n"],
               tx_stat.get("sent_ok"), rx_stat.get("recv"),
               pct(rx_stat.get("per_pct")), pct(rx_stat.get("per_ci_lo_pct")),
               pct(rx_stat.get("per_ci_hi_pct")), num(rx_stat.get("rssi")),
               num(rx_stat.get("snr")), num(rx_stat.get("kbps")),
               num(rx_stat.get("elapsed_s")), ts]
        with open(self.path, "a") as f:
            f.write(",".join(str(x) for x in row) + "\n")
        return row


# -----------------------------------------------------------------------
# CLI
# -----------------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser(
        description="Distributed E80 range test client. Connects to two board servers."
    )
    ap.add_argument("--tx-host", dest="tx_host", default="localhost",
                    help="TX board server host (default: localhost)")
    ap.add_argument("--rx-host", dest="rx_host", required=False,
                    help="RX board server host (required, or use HOST_A/HOST_B)")
    ap.add_argument("--tcp-tx", dest="tcp_tx", type=int, default=7780,
                    help="TX server TCP port (default 7780)")
    ap.add_argument("--tcp-rx", dest="tcp_rx", type=int, default=7780,
                    help="RX server TCP port (default 7780)")
    # HOST_A/HOST_B for when operator doesn't know which is TX
    ap.add_argument("--host-a", dest="host_a", default=None,
                    help="First board server host (auto-detects role)")
    ap.add_argument("--host-b", dest="host_b", default=None,
                    help="Second board server host (auto-detects role)")

    # Test params
    ap.add_argument("--freq", type=int, default=868000000,
                    help="Hz; 863-870 MHz (EU SRD) unless --band-override")
    ap.add_argument("--n", type=int, default=1000, help="packet count (default 1000)")
    ap.add_argument("--length", type=int, default=255, help="payload bytes (default 255)")
    ap.add_argument("--gap-us", dest="gap_us", type=int, default=5000,
                    help="inter-packet gap us (default 5000)")
    ap.add_argument("--dbm", type=int, default=10,
                    help="TX power dBm (default 10, indoor cap)")
    ap.add_argument("--matrix", default=None, metavar="M1,M2,...",
                    help=f"comma list from {','.join(MATRIX_KEYS)} (default: all)")
    ap.add_argument("--no-anchor", dest="anchor", action="store_false", default=True,
                    help="skip LEN=255 FLRC-650 comparability anchor")
    ap.add_argument("--csv", default=None, help="CSV output path (default: auto)")
    ap.add_argument("--band-override", action="store_true",
                    help="allow out-of-EU-SRD frequencies")

    # Stop/campaign metadata
    ap.add_argument("--site", default="?", help="site name (CSV)")
    ap.add_argument("--stop", default="?", help="stop ID, e.g. S0..S5 (CSV)")
    ap.add_argument("--dist-m", dest="dist_m", default="?", help="stop distance m (CSV)")
    ap.add_argument("--repeat", type=int, default=1, help="repeat number 1-3 (CSV)")

    # Operator + GPS metadata
    ap.add_argument("--operator", default=os.environ.get("USER", "?"),
                    help="operator name (default: $USER)")
    ap.add_argument("--gps-tx", dest="gps_tx", default="?",
                    help="GPS lat,lon of TX rig (metadata)")
    ap.add_argument("--gps-rx", dest="gps_rx", default="?",
                    help="GPS lat,lon of RX rig (metadata)")
    ap.add_argument("--h-tx", dest="h_tx", default="?",
                    help="TX antenna height AGL m (metadata)")
    ap.add_argument("--h-rx", dest="h_rx", default="?",
                    help="RX antenna height AGL m (metadata)")
    ap.add_argument("--ground", default="?", help="ground type (metadata)")
    ap.add_argument("--weather", default="?", help="weather string (metadata)")

    # Schedule
    ap.add_argument("--t0", default=None, metavar="'YYYY-MM-DD HH:MM:SS'",
                    help="schedule sync point (default: now)")
    ap.add_argument("--t0-margin", dest="t0_margin", type=int, default=10,
                    help="seconds after T0 before cell 1 (default 10)")
    ap.add_argument("--guard", type=int, default=20, help="inter-cell guard seconds")
    ap.add_argument("--rx-lead", dest="rx_lead", type=int, default=5,
                    help="seconds RX arms before cell start (default 5)")
    ap.add_argument("--settle", type=int, default=2,
                    help="post-burst settle seconds before RX STAT? (default 2)")

    args = ap.parse_args()

    # Resolve host_a/host_b → tx_host/rx_host
    if args.host_a and args.host_b:
        args.tx_host = args.host_a
        args.rx_host = args.host_b
    elif not args.rx_host:
        ap.error("--rx-host (or --host-a + --host-b) is required")

    # Parse matrix
    if args.matrix:
        args.matrix = [k.strip() for k in args.matrix.split(",") if k.strip()]
        bad = [k for k in args.matrix if k not in MOD_DEFS]
        if bad:
            ap.error(f"unknown --matrix entry(ies) {bad}; valid: {','.join(MATRIX_KEYS)}")

    try:
        sys.exit(run_distributed(args))
    except RuntimeError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)
    except KeyboardInterrupt:
        print("\nERROR: interrupted — STOP sent to both boards, stop marked ABORTED",
              file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
