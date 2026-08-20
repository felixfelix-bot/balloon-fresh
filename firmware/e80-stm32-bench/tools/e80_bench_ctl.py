#!/usr/bin/env python3
"""E80 bench controller — two-board PER bench + outdoor range-campaign matrix runner.

Board A = TX, Board B = RX. Run: RX arm first, then TX burst, then poll STAT.

Single-shot FLRC-650 run (indoor bench default):
    ./e80_bench_ctl.py --tx /dev/ttyUSB3 --rx /dev/ttyUSB4
    ./e80_bench_ctl.py --tx /dev/ttyUSB3 --rx /dev/ttyUSB4 --freq 868000000 \
        --n 1000 --len 255 --dbm 10
    ./e80_bench_ctl.py --dry-run          # print command script, no ports opened

Outdoor range campaign (docs/RANGE-TEST-PLAN.md §5 — single trigger per stop):
    ./e80_bench_ctl.py --tx /dev/ttyUSB3 --rx /dev/ttyUSB4 \
        --matrix flrc650,flrc2600,sf7,sf12 --anchor \
        --csv range/siteA_S3_r2.csv --site siteA --stop S3 --dist-m 200 --repeat 2 \
        --freq 915000000 --dbm 22 --band-override \
        --gps-tx 52.0123,4.0456 --gps-rx 52.0234,4.0123 \
        --h-tx 1.5 --h-rx 1.5 --ground grass --weather "12C clear" \
        --t0 "2026-08-30 14:05:00" --dry-run

Matrix mode runs all requested modulations back-to-back per stop (LEN=51,
GAP=5000 us FLRC / 1000 us LoRa) plus a LEN=255 FLRC-650 comparability anchor,
driven from a wall-clock schedule anchored at T0 so the two hosts stay in sync
without further operator input (plan §5). N per cell follows the plan §3
regime rule: 10^4 when the previous stop's same-mod Wilson ci_hi <= 2 %,
else 10^3; SF12 is time-capped at 10^3. Results append to --csv.

Safety policy: freq outside 863-870 MHz (EU SRD) is rejected host-side unless
--band-override is given (firmware window 410-960 MHz, pin-gated). +dBm above
10 requires POWER MODE OUTDOOR 2026 on the TX board; the tool issues both
unlocks and verifies acceptance via ID? (band=/pcap= echo) before any TX.
Ctrl-C at any time sends STOP to both boards and marks the stop ABORTED.
"""
import argparse
import csv
import datetime
import os
import re
import sys
import time

# Firmware hash gate (M2) — local copy in tools/
_TOOLS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "tools")
# When running from firmware/e80-stm32-bench/tools/, the repo tools/ dir is two levels up
_REPO_TOOLS = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "tools")
if _REPO_TOOLS not in sys.path:
    sys.path.insert(0, _REPO_TOOLS)
try:
    from firmware_hash_gate import parse_fw_hash, validate_fw_hash, format_session_start as fmt_session_start
except ImportError:
    parse_fw_hash = None
    validate_fw_hash = None
    fmt_session_start = None

BAUD = 2000000
PARITY = "N"
STOPBITS = 1

BAND_MIN_HZ = 863000000          # EU SRD clamp (firmware-identical)
BAND_MAX_HZ = 870000000
OVERRIDE_MIN_HZ = 410000000      # firmware override window (sub-GHz LF path)
OVERRIDE_MAX_HZ = 960000000
UNLOCK_PIN = 2026
INDOOR_CAP_DBM = 10
TXPOW_MAX_DBM = 22

CSV_COLUMNS = ["site", "stop", "dist_m", "repeat", "mod", "len", "pa", "freq_hz",
               "n", "sent", "recv", "per", "per_ci_lo", "per_ci_hi", "rssi",
               "snr", "kbps", "elapsed_s", "timestamp"]

# Campaign cells (plan §3). gap defaults: 5000 us FLRC / 1000 us LoRa.
MOD_DEFS: dict = {
    "flrc650":  dict(kind="flrc", mod_lines=["MOD flrc 650 {dbm}"],
                     gap_us=5000, label="FLRC-650"),
    "flrc2600": dict(kind="flrc", mod_lines=["MOD flrc 2600 {dbm}"],
                     gap_us=5000, label="FLRC-2600"),
    "sf7":      dict(kind="lora", mod_lines=["MOD loRa 7 125", "PA {dbm}"],
                     gap_us=1000, label="LoRa-SF7"),
    "sf12":     dict(kind="lora", mod_lines=["MOD loRa 12 125", "PA {dbm}"],
                     gap_us=1000, label="LoRa-SF12"),
}
MATRIX_KEYS = ["flrc650", "flrc2600", "sf7", "sf12"]
N_HI_DEFAULT = 10000             # S0 / low-PER regime (plan §3)
N_LO_DEFAULT = 1000              # high-PER edge regime
N_SF12_CAP = 1000                # SF12 time cap (10^4 would be ~7 h/cell)
ANCHOR_KEY = "flrc650"
ANCHOR_LEN = 255
MATRIX_LEN = 51
CI_HI_NHI_PCT = 2.0              # Wilson ci_hi threshold for the 10^4 regime

BOOT_BANNER_TIMEOUT = 10.0  # seconds to wait for FW_HASH in boot banner


def firmware_hash_gate(board, port_label, skip=False):
    """M2: Read boot banner lines from a freshly opened board, look for
    FW_HASH=<7+hexchars>, refuse to proceed if missing/invalid.

    Returns the validated hash string, or None if skipped.
    Returns False if the gate FAILED (no valid hash found).
    """
    if skip or parse_fw_hash is None:
        print("[FW GATE] SKIPPED (--skip-fw-check or firmware_hash_gate not available)")
        return None

    print("[FW GATE] Waiting for boot banner on {} (timeout {:.0f}s)…".format(
        port_label, BOOT_BANNER_TIMEOUT))
    buf = ""
    gate_start = time.time()
    while (time.time() - gate_start) < BOOT_BANNER_TIMEOUT:
        data = board.ser.read(256)
        if not data:
            continue
        text = data.decode("ascii", errors="replace")
        buf += text
        while "\n" in buf:
            line, buf = buf.split("\n", 1)
            line = line.strip()
            if not line:
                continue
            candidate = parse_fw_hash(line)
            if candidate:
                if validate_fw_hash(candidate):
                    print("[FW GATE] Valid FW_HASH={} on {} — authorised.".format(
                        candidate, port_label))
                    return candidate
                else:
                    print("[FW GATE] Found FW_HASH={} but invalid (too short or 'unknown').".format(
                        candidate))
    print("[FW GATE] ERROR: No valid FW_HASH found in boot banner on {}!".format(port_label))
    print("[FW GATE] Refusing to proceed. Flash firmware with FW_HASH or use --skip-fw-check.")
    return False  # False = gate failed (distinct from None = skipped)


def write_session_start_header(log, tx_fw, rx_fw, operator="?", rig="?"):
    """Write a SESSION_START comment header to the campaign CSV."""
    if fmt_session_start is not None:
        log._comment(fmt_session_start(tx_fw or "unknown", rx_fw or "unknown",
                                       operator, rig))
    else:
        log._comment("SESSION_START tx_fw={} rx_fw={}".format(
            tx_fw or "unknown", rx_fw or "unknown"))


# ---------------------------------------------------------------------------
# Pure helpers: airtime, schedule, cells, CSV, stat parsing, gates
# ---------------------------------------------------------------------------

def lora_airtime_s(length, sf, bw_hz, preamble=8, cr=1, crc=1, ih=0):
    """Standard SX127x-family LoRa airtime estimate (s), LDRO for SF>=11."""
    t_sym = (2 ** sf) / float(bw_hz)
    de = 1 if sf >= 11 else 0
    num = 8 * length - 4 * sf + 28 + 16 * crc - 20 * ih
    den = 4 * (sf - 2 * de)
    n_payload = 8 + max(0, -(-num // den)) * (cr + 4)   # ceil division
    return (preamble + 4.25 + n_payload) * t_sym


def flrc_airtime_s(length, br_bps):
    """FLRC airtime estimate: payload + ~64 bit overhead, +100 us margin."""
    return (length * 8 + 64) / float(br_bps) + 0.0001


def airtime_s(mod_key, length):
    if mod_key not in MOD_DEFS:
        raise ValueError("unknown mod {!r}".format(mod_key))
    d = MOD_DEFS[mod_key]
    if d["kind"] == "flrc":
        br = {"flrc650": 650000, "flrc2600": 2600000}[mod_key]
        return flrc_airtime_s(length, br)
    sf, bw = (7, 125000) if mod_key == "sf7" else (12, 125000)
    return lora_airtime_s(length, sf, bw)


def make_cell(mod_key, n, length=None, anchor=False):
    d = MOD_DEFS[mod_key]
    len_bytes = ANCHOR_LEN if anchor else (MATRIX_LEN if length is None else length)
    return dict(key=mod_key, label=d["label"], anchor=anchor,
                mod_lines=list(d["mod_lines"]),
                gap_us=d["gap_us"], n=n,
                len_bytes=len_bytes,
                expected_s=n * (airtime_s(mod_key, len_bytes)
                                + d["gap_us"] / 1e6))


def n_for_mod(mod_key, prior_rows):
    """Plan §3 N rule: 10^4 if the latest previous LEN=51 row for this mod has
    Wilson ci_hi <= 2 %, else 10^3. No prior row -> 10^4 (S0 start rule).
    SF12 is time-capped at 10^3 regardless."""
    if mod_key == "sf12":
        return N_SF12_CAP
    for row in reversed(prior_rows):
        if row.get("mod") == mod_key and row.get("len") == str(MATRIX_LEN):
            try:
                ci_hi = float(row.get("per_ci_hi") or "nan")
            except ValueError:
                ci_hi = float("nan")
            if ci_hi == ci_hi:  # not NaN
                return N_HI_DEFAULT if ci_hi <= CI_HI_NHI_PCT else N_LO_DEFAULT
    return N_HI_DEFAULT


def build_matrix_cells(args, prior_rows):
    """Cell list for one stop: requested mods (LEN=51) + optional anchor."""
    cells = []
    for key in args.matrix:
        cells.append(make_cell(key, n_for_mod(key, prior_rows)))
    if args.anchor:
        cells.append(make_cell(ANCHOR_KEY, N_HI_DEFAULT, anchor=True))
    return cells


def parse_t0(s):
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S"):
        try:
            return datetime.datetime.strptime(s, fmt).timestamp()
        except ValueError:
            continue
    raise ValueError("bad --t0 {!r}; want 'YYYY-MM-DD HH:MM:SS' local time".format(s))


def build_stop_schedule(cells, t0_epoch, t0_margin_s, guard_s, settle_s=5.0):
    """Absolute epoch start time per cell. RX arms rx_lead earlier (runner)."""
    starts = []
    t = t0_epoch + t0_margin_s
    for c in cells:
        starts.append(t)
        t += c["expected_s"] + settle_s + guard_s
    return starts


def fmt_offset(epoch, t0_epoch):
    s = int(max(0, epoch - t0_epoch))
    return "T0+{:02d}:{:02d}:{:02d}".format(s // 3600, (s % 3600) // 60, s % 60)


def fmt_hms(seconds):
    s = int(seconds)
    return "{:02d}:{:02d}".format(s // 60, s % 60)


def freq_gate(freq_hz, band_override):
    """Host-side mirror of the firmware FREQ gate (plan §1)."""
    if band_override:
        if not (OVERRIDE_MIN_HZ <= freq_hz <= OVERRIDE_MAX_HZ):
            return False, ("freq {} outside override window {}-{} MHz "
                           "(firmware will reject)".format(
                               freq_hz, OVERRIDE_MIN_HZ // 1000000,
                               OVERRIDE_MAX_HZ // 1000000))
        return True, ""
    if not (BAND_MIN_HZ <= freq_hz <= BAND_MAX_HZ):
        return False, ("freq {} outside EU SRD 863-870 MHz; pass --band-override "
                       "for out-of-region range sessions".format(freq_hz))
    return True, ""


_CI_RE = re.compile(r"per_ci_x1e6=\[(\d+),(\d+)\]")


def parse_stat(reply):
    """Parse firmware 'STAT role=.. sent=.. sent_ok=.. rx=.. crc_err=..
    per_x1e6=.. per_ci_x1e6=[lo,hi] elapsed_s=.. kbps=.. rssi_avg_dbm=..
    snr_avg_db=.. drops=..' (also tolerates the legacy 'OK STAT sent=.. recv=..
    per=.. rssi=..' shape) into a normalized dict. PER values become percent.
    """
    fields = {}
    for tok in reply.split():
        if "=" in tok:
            k, v = tok.split("=", 1)
            fields[k] = v
    m = _CI_RE.search(reply)
    out: dict = {"per_pct": None, "per_ci_lo_pct": None, "per_ci_hi_pct": None}
    def _f(key, alias=None):
        for k in (key, alias or ""):
            if k and k in fields:
                try:
                    return float(fields[k])
                except ValueError:
                    return None
        return None
    out["sent"] = int(_f("sent") or 0)
    out["sent_ok"] = int(_f("sent_ok") or 0)
    out["recv"] = int(_f("rx", "recv") or 0)
    out["crc_err"] = int(_f("crc_err") or 0)
    if "per_x1e6" in fields:
        p = _f("per_x1e6")
        out["per_pct"] = p / 1e4 if p is not None else None
    elif "per" in fields:
        out["per_pct"] = _f("per")
    if m:
        out["per_ci_lo_pct"] = int(m.group(1)) / 1e4
        out["per_ci_hi_pct"] = int(m.group(2)) / 1e4
    else:
        lo, hi = _f("per_ci_lo"), _f("per_ci_hi")
        if lo is not None:
            out["per_ci_lo_pct"] = lo
        if hi is not None:
            out["per_ci_hi_pct"] = hi
    out["elapsed_s"] = _f("elapsed_s")
    out["kbps"] = _f("kbps")
    out["rssi"] = _f("rssi_avg_dbm", "rssi")
    out["snr"] = _f("snr_avg_db", "snr")
    out["drops"] = int(_f("drops") or 0)
    out["gap_us"] = int(_f("gap_us") or 0)
    return out


def read_prior_rows(path):
    """Rows from an existing campaign CSV (append-only, '#' = metadata)."""
    try:
        with open(path, newline="") as f:
            return list(csv.DictReader(ln for ln in f if not ln.startswith("#")))
    except FileNotFoundError:
        return []


class CsvLog:
    """Append-only campaign CSV: header once, '#' metadata per stop, one row
    per cell (plan §5)."""

    def __init__(self, path):
        self.path = path
        try:
            with open(path) as f:
                has_header = bool(f.readline().strip())
        except FileNotFoundError:
            has_header = False
        if not has_header:
            with open(path, "w", newline="") as f:
                f.write(",".join(CSV_COLUMNS) + "\n")

    def _comment(self, text):
        with open(self.path, "a") as f:
            f.write("# {}\n".format(text))

    def stop_meta(self, args, id_tx="", id_rx="", t0_str=""):
        self._comment("STOP site={} stop={} dist_m={} repeat={} freq_hz={} dbm={} "
                      "t0={}".format(args.site, args.stop, args.dist_m,
                                     args.repeat, args.freq, args.dbm, t0_str))
        self._comment("gps_tx={} gps_rx={} h_tx_agl_m={} h_rx_agl_m={} "
                      "ground={} weather={}".format(
                          args.gps_tx, args.gps_rx, args.h_tx, args.h_rx,
                          args.ground, args.weather))
        if id_tx:
            self._comment("id_tx: {}".format(id_tx))
        if id_rx:
            self._comment("id_rx: {}".format(id_rx))

    def abort(self, reason):
        self._comment("ABORT {}: stop invalid, re-run after clear (plan §4)".format(reason))

    def cell_row(self, args, cell, rx_stat, tx_stat, ts=None):
        ts = ts or datetime.datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
        def pct(v):
            return "" if v is None else "{:.6f}".format(v)
        def num(v):
            return "" if v is None else str(v)
        row = [args.site, args.stop, args.dist_m, args.repeat,
               cell["key"] + ("+anchor" if cell["anchor"] else ""),
               cell["len_bytes"], args.dbm, args.freq, cell["n"],
               tx_stat.get("sent_ok"), rx_stat.get("recv"),
               pct(rx_stat.get("per_pct")), pct(rx_stat.get("per_ci_lo_pct")),
               pct(rx_stat.get("per_ci_hi_pct")), num(rx_stat.get("rssi")),
               num(rx_stat.get("snr")), num(rx_stat.get("kbps")),
               num(rx_stat.get("elapsed_s")), ts]
        with open(self.path, "a") as f:
            f.write(",".join(str(x) for x in row) + "\n")
        return row


# ---------------------------------------------------------------------------
# Serial console (BoardSerial pattern, inlined)
# ---------------------------------------------------------------------------

class BoardSerial:
    """Minimal line-oriented serial console (BoardSerial pattern, inlined).

    Boards reply 'OK ...' or 'ERR <reason>' to state commands; 'ID ...' to
    ID? and 'STAT ...' to STAT? (no OK prefix on those two).
    """

    def __init__(self, port, baud=BAUD, timeout=5.0):
        import serial  # pyserial

        self.ser = serial.Serial(
            port=port,
            baudrate=baud,
            parity=PARITY,
            stopbits=STOPBITS,
            bytesize=8,
            timeout=timeout,
        )
        self.port = port
        self.drain()

    def drain(self, quiet=0.4):
        """Consume boot noise / stale output until quiet for `quiet` seconds."""
        self.ser.timeout = quiet
        while True:
            line = self.ser.readline().decode(errors="replace").strip()
            if not line:
                break
        self.ser.timeout = 5.0

    def query(self, line, prefixes=("OK", "ERR", "STAT", "ID"), timeout=15.0):
        """Send a line, return the first reply starting with any prefix."""
        self.ser.write((line + "\r\n").encode())
        deadline = time.time() + timeout
        while time.time() < deadline:
            reply = self.ser.readline().decode(errors="replace").strip()
            if not reply:
                continue
            print("  [{}] {} -> {}".format(self.port, line, reply))
            for p in prefixes:
                if reply.startswith(p):
                    if reply.startswith("ERR"):
                        raise RuntimeError("{} rejected '{}': {}".format(
                            self.port, line, reply))
                    return reply
        raise RuntimeError("{}: timeout waiting for reply to '{}'".format(self.port, line))

    def cmd(self, line, expect_ok=True, timeout=15.0):
        return self.query(line, prefixes=("OK", "ERR"), timeout=timeout)

    def stat(self):
        return self.query("STAT?", prefixes=("STAT", "ERR", "OK"))

    def close(self):
        self.ser.close()


# ---------------------------------------------------------------------------
# Single-shot FLRC-650 bench (original mode, kept)
# ---------------------------------------------------------------------------

def build_script(args):
    """Command sequences sent to each board for a single-shot run.
    Returns (tx_cmds, rx_cmds)."""
    pre = []
    if args.band_override:
        pre.append("BAND OVERRIDE {}".format(UNLOCK_PIN))
    if args.dbm > INDOOR_CAP_DBM:
        pre.append("POWER MODE OUTDOOR {}".format(UNLOCK_PIN))
    rx_cmds = ["ID?"] + pre + [
        "ROLE RX",
        "FREQ {}".format(args.freq),
        "MOD flrc 650 {}".format(args.dbm),
        "START N={} LEN={} GAP={}".format(args.n, args.length, args.gap_us),
    ]
    tx_cmds = ["ID?"] + pre + [
        "ROLE TX",
        "ARM TX",
        "FREQ {}".format(args.freq),
        "MOD flrc 650 {}".format(args.dbm),
        "START N={} LEN={} GAP={}".format(args.n, args.length, args.gap_us),
    ]
    return tx_cmds, rx_cmds


def run(args):
    tx_cmds, rx_cmds = build_script(args)

    print("== E80 FLRC bench: {} pkts x {} B @ FLRC-650, {} MHz, +{} dBm ==".format(
        args.n, args.length, args.freq / 1e6, args.dbm))

    print("-- RX board (arm first) --")
    rx = BoardSerial(args.rx)
    rx_fw = firmware_hash_gate(rx, args.rx, skip=args.skip_fw_check)
    if rx_fw is False:
        rx.close()
        sys.exit("ERROR: FW hash gate failed on RX board")
    rx.drain()
    for c in rx_cmds:
        rx.cmd(c)

    print("-- TX board --")
    tx = BoardSerial(args.tx)
    tx_fw = firmware_hash_gate(tx, args.tx, skip=args.skip_fw_check)
    if tx_fw is False:
        tx.close()
        rx.close()
        sys.exit("ERROR: FW hash gate failed on TX board")
    tx.drain()
    for c in tx_cmds:
        tx.cmd(c, timeout=max(30.0, args.n * (args.length * 8 / 650e3) + 30))

    # Poll TX until burst complete, then read RX stats.
    burst_s = max(args.n * (args.length * 8 / 650e3) + args.n * args.gap_us / 1e6, 2.0)
    deadline = time.time() + burst_s + 60
    while time.time() < deadline:
        s = parse_stat(tx.stat())
        if s["sent_ok"] >= args.n:
            break
        time.sleep(2.0)
    time.sleep(2.0)  # let last packets land
    rx_stat = parse_stat(rx.stat())

    print()
    print("========= RESULTS =========")
    print("mode        FLRC-650")
    print("freq        {:.1f} MHz".format(args.freq / 1e6))
    print("tx power    +{} dBm".format(args.dbm))
    print("payload     {} B x {} pkts".format(args.length, args.n))
    for k in ("sent_ok", "recv", "per_pct", "per_ci_lo_pct", "per_ci_hi_pct",
              "rssi", "snr", "kbps", "drops"):
        print("{:<12} {}".format(k, rx_stat.get(k, "?")))

    if args.csv:
        cell = make_cell("flrc650", args.n, length=args.length)
        log = CsvLog(args.csv)
        write_session_start_header(log, tx_fw, rx_fw,
                                   operator=os.environ.get("USER", "?"),
                                   rig="e80-bench")
        log.cell_row(args, cell, rx_stat, parse_stat(tx.stat()))
        print("CSV row appended: {}".format(args.csv))

    tx.close()
    rx.close()
    return 0


# ---------------------------------------------------------------------------
# Range-campaign matrix runner (plan §3/§5)
# ---------------------------------------------------------------------------

def preflight(board, args, role, power_unlock):
    """ID? capture, unlocks, role, FREQ — the plan §1 pre-flight on one board.
    Returns (id_before, id_after) with gate verification via ID? echo."""
    id_before = board.query("ID?")
    if args.band_override:
        board.cmd("BAND OVERRIDE {}".format(UNLOCK_PIN))
    if power_unlock:
        board.cmd("POWER MODE OUTDOOR {}".format(UNLOCK_PIN))
    board.cmd("ROLE {}".format(role))
    if role == "TX":
        board.cmd("ARM TX")
    board.cmd("FREQ {}".format(args.freq))
    id_after = board.query("ID?")
    want_band = "band=OVERRIDE" if args.band_override else "band=863-870MHz"
    if want_band not in id_after:
        raise RuntimeError("{}: ID? shows '{}' missing {} — BAND gate not "
                           "accepted, refusing to TX".format(board.port, id_after, want_band))
    if power_unlock and "pcap=+22dBm(OUTDOOR)" not in id_after:
        raise RuntimeError("{}: ID? shows '{}' missing pcap=+22dBm(OUTDOOR) — "
                           "power unlock not accepted, refusing to TX".format(board.port, id_after))
    return id_before, id_after


def run_matrix(args, board_cls=None, sleep_fn=time.sleep, now_fn=time.time):
    """Live single-trigger matrix run (plan §5). One invocation = one stop."""
    if board_cls is None:
        board_cls = BoardSerial
    power_unlock = args.dbm > INDOOR_CAP_DBM
    prior_rows = read_prior_rows(args.csv) if args.csv else []
    cells = build_matrix_cells(args, prior_rows)
    t0 = parse_t0(args.t0)
    starts = build_stop_schedule(cells, t0, args.t0_margin, args.guard)
    log = CsvLog(args.csv)

    def wait_until(ts):
        while True:
            d = ts - now_fn()
            if d <= 0:
                return
            sleep_fn(min(d, 30.0))

    print("== RANGE MATRIX: site={} stop={} dist={}m repeat={} | {} MHz +{} dBm | "
          "T0={} ==".format(args.site, args.stop, args.dist_m, args.repeat,
                            args.freq / 1e6, args.dbm,
                            datetime.datetime.fromtimestamp(t0).isoformat()))
    for c, s in zip(cells, starts):
        print("  cell {:<18} N={:<6} LEN={:<4} GAP={:<5} start={} (exp {} s)".format(
            c["label"], c["n"], c["len_bytes"], c["gap_us"],
            fmt_offset(s, t0), fmt_hms(c["expected_s"])))

    rx = board_cls(args.rx)
    tx = None
    try:
        rx_fw = firmware_hash_gate(rx, args.rx, skip=args.skip_fw_check)
        if rx_fw is False:
            raise RuntimeError("FW hash gate failed on RX board")
        rx.drain()
        print("-- RX pre-flight --")
        _, id_rx = preflight(rx, args, "RX", power_unlock)
        tx = board_cls(args.tx)
        print("-- TX pre-flight --")
        tx_fw = firmware_hash_gate(tx, args.tx, skip=args.skip_fw_check)
        if tx_fw is False:
            raise RuntimeError("FW hash gate failed on TX board")
        tx.drain()
        _, id_tx = preflight(tx, args, "TX", power_unlock)
        write_session_start_header(log, tx_fw, rx_fw,
                                   operator=os.environ.get("USER", "?"),
                                   rig="e80-bench")
        log.stop_meta(args, id_tx=id_tx, id_rx=id_rx,
                      t0_str=datetime.datetime.fromtimestamp(t0).isoformat())

        for idx, (cell, start) in enumerate(zip(cells, starts)):
            print("-- cell {}/{} {} N={} LEN={} --".format(
                idx + 1, len(cells), cell["label"], cell["n"], cell["len_bytes"]))
            mod_lines = [ln.format(dbm=args.dbm) for ln in cell["mod_lines"]]
            start_line = "START N={} LEN={} GAP={}".format(
                cell["n"], cell["len_bytes"], cell["gap_us"])

            wait_until(start - args.rx_lead)
            for ln in mod_lines:
                rx.cmd(ln)
            rx.cmd(start_line)          # RX: reset stats + arm expected LEN

            wait_until(start)
            for ln in mod_lines:
                tx.cmd(ln)
            tx.cmd(start_line, timeout=max(30.0, cell["expected_s"] + 60))

            deadline = now_fn() + cell["expected_s"] + 120
            while True:
                s = parse_stat(tx.stat())
                if s["sent_ok"] >= cell["n"]:
                    break
                if now_fn() >= deadline:
                    raise RuntimeError("cell {} TIMEOUT: TX sent_ok={}/{}".format(
                        cell["label"], s["sent_ok"], cell["n"]))
                sleep_fn(5.0 if cell["expected_s"] > 120 else 2.0)
            sleep_fn(args.settle)       # let last packets land
            rx_stat = parse_stat(rx.stat())
            tx_stat = parse_stat(tx.stat())
            row = log.cell_row(args, cell, rx_stat, tx_stat, ts=ts_now(now_fn))
            print("   -> recv={}/{} per={} ci=[{},{}] rssi={} snr={}".format(
                row[10], cell["n"], row[11] or "?", row[12] or "?",
                row[13] or "?", row[14] or "?", row[15] or "?"))

        # Walk discipline (plan §5): radios to sleep between stops.
        tx.cmd("ROLE NONE")
        rx.cmd("ROLE NONE")
    except BaseException as e:  # includes KeyboardInterrupt (Ctrl-C = STOP)
        log.abort("{}: {}".format(type(e).__name__, e))
        for b in (tx, rx):
            if b is not None:
                try:
                    b.cmd("STOP", expect_ok=False, timeout=3.0)
                    b.cmd("ROLE NONE", expect_ok=False, timeout=3.0)
                except Exception:
                    pass
        raise
    finally:
        if tx is not None:
            tx.close()
        rx.close()
    return 0


def ts_now(now_fn):
    return datetime.datetime.fromtimestamp(now_fn()).strftime("%Y-%m-%dT%H:%M:%S")


def dry_run(args):
    """Offline test surface: full matrix + schedule + scripts, no ports, no CSV."""
    power_unlock = args.dbm > INDOOR_CAP_DBM
    prior_rows = read_prior_rows(args.csv) if args.csv else []
    cells = build_matrix_cells(args, prior_rows)
    t0 = parse_t0(args.t0) if args.t0 else time.time()
    starts = build_stop_schedule(cells, t0, args.t0_margin, args.guard)

    print("== DRY RUN == site={} stop={} repeat={} | {} MHz +{} dBm{}{} ==".format(
        args.site, args.stop, args.repeat, args.freq / 1e6, args.dbm,
        " | BAND OVERRIDE" if args.band_override else "",
        " | POWER OUTDOOR" if power_unlock else ""))
    print("T0 = {} (margin {} s, guard {} s, rx_lead {} s)".format(
        datetime.datetime.fromtimestamp(t0).isoformat(),
        args.t0_margin, args.guard, args.rx_lead))
    print()
    print("-- unlock / pre-flight (both boards) --")
    print("ID?")
    if args.band_override:
        print("BAND OVERRIDE {}".format(UNLOCK_PIN))
    if power_unlock:
        print("POWER MODE OUTDOOR {}".format(UNLOCK_PIN))
    print("FREQ {}".format(args.freq))
    print("ID?   # verify band=/pcap= echo (plan pre-flight step 3-4)")
    print()
    for i, (c, s) in enumerate(zip(cells, starts)):
        if c["anchor"]:
            n_src = "anchor cell"
        elif c["key"] == "sf12":
            n_src = "SF12 time cap"
        elif c["n"] == N_HI_DEFAULT:
            n_src = "regime: prev-stop ci_hi<=2% (or S0)"
        else:
            n_src = "regime: edge/prev ci_hi>2%"
        print("-- cell {} {} N={} LEN={} GAP={}us start={} (exp {}) [{}] --".format(
            i + 1, c["label"], c["n"], c["len_bytes"], c["gap_us"],
            fmt_offset(s, t0), fmt_hms(c["expected_s"]), n_src))
        mod_lines = [ln.format(dbm=args.dbm) for ln in c["mod_lines"]]
        start_line = "START N={} LEN={} GAP={}".format(
            c["n"], c["len_bytes"], c["gap_us"])
        print("   RX @ {}:".format(fmt_offset(s - args.rx_lead, t0)))
        for ln in mod_lines + [start_line]:
            print("      " + ln)
        print("   TX @ {}:".format(fmt_offset(s, t0)))
        for ln in mod_lines + [start_line]:
            print("      " + ln)
        print("   then: TX STAT? until sent_ok=={}; settle {} s; RX STAT? -> CSV row".format(
            c["n"], args.settle))
        print()
    print("-- teardown: both boards ROLE NONE --")
    if args.csv:
        print("-- csv {} (append-only; header {} cols; '#' metadata per stop) --".format(
            args.csv, len(CSV_COLUMNS)))
        print(",".join(CSV_COLUMNS))
    print("-- Ctrl-C during a live run sends STOP to both boards and marks the "
          "stop ABORTED --")
    return 0


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser(
        description="E80 two-board bench controller (single-shot FLRC-650 or "
                    "range-campaign matrix per docs/RANGE-TEST-PLAN.md)")
    ap.add_argument("--tx", default="/dev/ttyUSB3", help="TX board serial port")
    ap.add_argument("--rx", default="/dev/ttyUSB4", help="RX board serial port")
    ap.add_argument("--freq", type=int, default=868000000,
                    help="Hz; 863-870 MHz (EU SRD) unless --band-override "
                         "(then firmware window 410-960 MHz)")
    ap.add_argument("--n", type=int, default=1000,
                    help="single-shot packet count (default 1000)")
    ap.add_argument("--length", type=int, default=255,
                    help="single-shot payload bytes (default 255)")
    ap.add_argument("--gap-us", dest="gap_us", type=int, default=5000,
                    help="single-shot inter-packet gap in us (default 5000)")
    ap.add_argument("--dbm", type=int, default=10,
                    help="TX power dBm, firmware caps at +10 indoor (default 10)")
    ap.add_argument("--dry-run", action="store_true",
                    help="print the command script/schedule without opening ports")
    # range-campaign matrix (plan §5)
    ap.add_argument("--matrix", default=None, metavar="M1,M2,...",
                    help="comma list from {} — runs back-to-back per stop".format(
                        ",".join(MATRIX_KEYS)))
    ap.add_argument("--no-anchor", dest="anchor", action="store_false", default=True,
                    help="skip the LEN=255 FLRC-650 comparability anchor cell")
    ap.add_argument("--csv", default=None,
                    help="append-only campaign CSV (one row per cell)")
    ap.add_argument("--band-override", action="store_true",
                    help="issue BAND OVERRIDE {} on both boards for out-of-region "
                         "freq (915 MHz sites); verified via ID?".format(UNLOCK_PIN))
    ap.add_argument("--site", default="?", help="campaign site name (CSV)")
    ap.add_argument("--stop", default="?", help="stop id S0..S5 (CSV)")
    ap.add_argument("--dist-m", dest="dist_m", default="?", help="stop distance m (CSV)")
    ap.add_argument("--repeat", type=int, default=1, help="repeat number 1-3 (CSV)")
    ap.add_argument("--gps-tx", default="?", help="GPS lat,lon of TX rig (CSV meta)")
    ap.add_argument("--gps-rx", default="?", help="GPS lat,lon of RX rig (CSV meta)")
    ap.add_argument("--h-tx", default="?", help="TX antenna height AGL m (CSV meta)")
    ap.add_argument("--h-rx", default="?", help="RX antenna height AGL m (CSV meta)")
    ap.add_argument("--ground", default="?", help="ground type (CSV meta)")
    ap.add_argument("--weather", default="?", help="weather string (CSV meta)")
    ap.add_argument("--t0", default=None, metavar="'YYYY-MM-DD HH:MM:SS'",
                    help="sync point exchanged by phone (plan §5); schedule runs "
                         "from wall clock T0. Required for live matrix runs")
    ap.add_argument("--t0-margin", dest="t0_margin", type=int, default=120,
                    help="seconds after T0 before cell 1 (default 120)")
    ap.add_argument("--guard", type=int, default=20,
                    help="inter-cell guard seconds (default 20)")
    ap.add_argument("--rx-lead", dest="rx_lead", type=int, default=10,
                    help="seconds RX arms before cell start (default 10)")
    ap.add_argument("--settle", type=int, default=2,
                    help="post-burst settle seconds before RX STAT? (default 2)")
    ap.add_argument("--skip-fw-check", action="store_true",
                    help="skip firmware hash gate (not recommended)")
    args = ap.parse_args()

    if args.matrix:
        args.matrix = [k.strip() for k in args.matrix.split(",") if k.strip()]
        bad = [k for k in args.matrix if k not in MOD_DEFS]
        if bad:
            sys.exit("unknown --matrix entry(ies) {}; valid: {}".format(
                ",".join(bad), ",".join(MATRIX_KEYS)))

    ok, msg = freq_gate(args.freq, args.band_override)
    if not ok:
        sys.exit(msg)
    if args.dbm > TXPOW_MAX_DBM:
        sys.exit("dbm {} above firmware max {}".format(args.dbm, TXPOW_MAX_DBM))
    if args.dbm > INDOOR_CAP_DBM:
        print("note: +{} dBm exceeds indoor cap; issuing POWER MODE OUTDOOR {} "
              "before TX (logged on board)".format(args.dbm, UNLOCK_PIN))

    if args.dry_run:
        if args.matrix:
            return dry_run(args)
        tx_cmds, rx_cmds = build_script(args)
        print("-- RX board --")
        for c in rx_cmds:
            print(c)
        print("-- TX board --")
        for c in tx_cmds:
            print(c)
        print("-- then poll: TX 'STAT?' until sent_ok==N; read RX 'STAT?' --")
        return 0

    if args.matrix and not args.csv:
        sys.exit("--matrix (live) requires --csv for the campaign log")
    if args.matrix and not args.t0:
        sys.exit("--matrix (live) requires --t0 'YYYY-MM-DD HH:MM:SS' for "
                 "schedule sync (plan §5)")

    try:
        sys.exit(run_matrix(args) if args.matrix else run(args))
    except RuntimeError as e:
        sys.exit("ERROR: {}".format(e))
    except KeyboardInterrupt:
        sys.exit("ERROR: interrupted — STOP sent, stop marked ABORTED in CSV")


if __name__ == "__main__":
    main()
