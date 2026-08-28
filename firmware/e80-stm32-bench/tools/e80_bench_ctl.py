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
--band-override is given (firmware window 410-2483 MHz, pin-gated). +dBm above
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
OVERRIDE_MAX_HZ = 2483500000
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


# --- Prime-discard helpers (AGC warmup) ---

DEFAULT_PRIME_DISCARD = 2


def compute_tx_total(n_pkts, prime_discard):
    """Total packet count for the firmware START command.

    TX sends n_pkts measured packets PLUS prime_discard warmup ("prime")
    packets at the start of the burst, so the AGC has time to settle before
    the measured window begins. Returns the N value to pass to START.
    """
    return n_pkts + prime_discard


def discard_prime_pkts(pkts, prime_discard):
    """Drop the first prime_discard packets (by seq) from a parsed PKT
    list. The firmware assigns seq 0..N-1 sequentially; the first
    prime_discard indices (0..prime_discard-1) are warmup packets that the
    RX must not log for measurement. Packets with missing seq default
    to 0 and are eligible for discard.

    Falls back to legacy 'pkt_idx' key for backward compatibility with
    --format legacy.
    """
    if prime_discard <= 0:
        return pkts
    return [p for p in pkts if p.get("seq", p.get("pkt_idx", 0)) >= prime_discard]


def adjust_stat_for_prime(stat, prime_discard):
    """Subtract prime_discard from stat['recv'] (clamped at 0) so the
    reported recv count and PER reflect measured packets only. The
    firmware's STAT? includes ALL received packets (prime + measured).
    Modifies stat in place."""
    stat["recv"] = max(0, int(stat.get("recv", 0)) - prime_discard)


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
    # Accept raw epoch integer (timezone-safe for distributed operation)
    try:
        return int(s)
    except (ValueError, TypeError):
        pass
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%dT%H:%M:%S",
                "%Y-%m-%d %H:%M", "%Y-%m-%dT%H:%M"):
        try:
            return datetime.datetime.strptime(s, fmt).timestamp()
        except ValueError:
            continue
    raise ValueError("bad --t0 {!r}; want epoch int or 'YYYY-MM-DD HH:MM:SS'".format(s))


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
        if not expect_ok:
            # Fire-and-forget: send the line, don't wait for a reply
            self.ser.write((line + "\r\n").encode())
            try:
                self.ser.readline()  # consume any immediate echo
            except Exception:
                pass
            return None
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
    tx_total = compute_tx_total(args.n, getattr(args, 'prime_discard', 0))
    rx_cmds = ["ID?"] + pre + [
        "ROLE RX",
        "FREQ {}".format(args.freq),
        "MOD flrc 650 {}".format(args.dbm),
        "START N={} LEN={} GAP={}".format(tx_total, args.length, args.gap_us),
    ]
    tx_cmds = ["ID?"] + pre + [
        "ROLE TX",
        "ARM TX",
        "FREQ {}".format(args.freq),
        "MOD flrc 650 {}".format(args.dbm),
        "START N={} LEN={} GAP={}".format(tx_total, args.length, args.gap_us),
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
            prime_discard = getattr(args, 'prime_discard', 0)
            tx_total = compute_tx_total(cell["n"], prime_discard)
            start_line = "START N={} LEN={} GAP={}".format(
                tx_total, cell["len_bytes"], cell["gap_us"])

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
                if s["sent_ok"] >= tx_total:
                    break
                if now_fn() >= deadline:
                    raise RuntimeError("cell {} TIMEOUT: TX sent_ok={}/{}".format(
                        cell["label"], s["sent_ok"], tx_total))
                sleep_fn(5.0 if cell["expected_s"] > 120 else 2.0)
            sleep_fn(args.settle)       # let last packets land
            rx_stat = parse_stat(rx.stat())
            adjust_stat_for_prime(rx_stat, prime_discard)
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


# ---------------------------------------------------------------------------
# Distributed range test: config presets, PKT parsing, TX/RX log writers
# ---------------------------------------------------------------------------

def load_config_preset(preset_or_path):
    """Load a config preset from a JSON file path or a dict.

    Returns a list of validated config dicts with added fields:
      idx, airtime_s, expected_s

    Each config must have: mod, sf|br, bw, pa, freq, plen, gap, n_pkts, label
    LoRa configs must have sf + bw; FLRC configs must have br.

    Raises ValueError for invalid configs, FileNotFoundError for missing files.
    """
    import json as _json

    if isinstance(preset_or_path, str):
        path = preset_or_path
        if not os.path.isfile(path):
            # Try preset name lookup in configs/ dirs
            name = path[:-5] if path.endswith(".json") else path
            repo_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
            for c in [
                # repo-root-relative path (e.g. CONFIGS=configs/resend-...json
                # typed at the repo root; this tool runs with cwd=e80-stm32-bench)
                os.path.join(repo_root, path),
                os.path.join(repo_root, "configs", "per-stop", name + ".json"),
                os.path.join(repo_root, "configs", name + ".json"),
                os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "configs", "per-stop", name + ".json"),
                os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "configs", name + ".json"),
                name + ".json",
            ]:
                if os.path.isfile(c):
                    path = c
                    break
        with open(path) as f:
            preset = _json.load(f)
    elif isinstance(preset_or_path, dict):
        preset = preset_or_path
    else:
        raise ValueError("preset must be a file path or dict")

    if "configs" not in preset:
        raise ValueError("preset missing 'configs' key")
    raw_cfgs = preset["configs"]
    if not raw_cfgs:
        raise ValueError("preset has empty configs list")

    cfgs = []
    for i, c in enumerate(raw_cfgs):
        mod = c.get("mod", "").lower()
        if mod not in ("lora", "flrc"):
            raise ValueError("config {}: invalid mod {!r} (want 'lora' or 'flrc')".format(i, c.get("mod")))

        if mod == "lora":
            if c.get("sf") is None:
                raise ValueError("config {}: lora requires sf".format(i))
            if c.get("bw") is None:
                raise ValueError("config {}: lora requires bw".format(i))
            airtime = lora_airtime_s(c["plen"], c["sf"], c["bw"] * 1000)
            sf_or_br = c["sf"]
        else:  # flrc
            if c.get("br") is None:
                raise ValueError("config {}: flrc requires br".format(i))
            airtime = flrc_airtime_s(c["plen"], c["br"] * 1000)
            sf_or_br = c["br"]

        gap = c.get("gap", 5000)
        n_pkts = c.get("n_pkts", 10)
        expected_s = n_pkts * (airtime + gap / 1e6)

        cfgs.append({
            "idx": i,
            "label": c.get("label", "cfg{}".format(i)),
            "mod": mod,
            "sf": c.get("sf"),
            "br": c.get("br"),
            "bw": c.get("bw"),
            "pa": c.get("pa", 10),
            "freq": c.get("freq", 868000000),
            "plen": c.get("plen", 64),
            "gap": gap,
            "n_pkts": n_pkts,
            "airtime_s": round(airtime, 4),
            "expected_s": round(expected_s, 2),
        })

    return cfgs


BAND_THRESHOLD_HZ = 1_600_000_000  # 1.6 GHz — sub-GHz vs 2.4 GHz boundary


def is_band_transition(prev_freq, cur_freq, threshold=BAND_THRESHOLD_HZ):
    """Return True if prev_freq and cur_freq are on different sides of the
    1.6 GHz band boundary (sub-GHz vs 2.4 GHz).

    A band transition means the operator must physically swap the antenna
    cable from the sub-GHz jack (Pin 9) to the 2.4 GHz jack (Pin 10) or
    vice versa.
    """
    if prev_freq is None or cur_freq is None:
        return False
    return (prev_freq < threshold) != (cur_freq < threshold)


def _band_label(freq_hz):
    """Return a human-readable band label for antenna swap messages."""
    if freq_hz < BAND_THRESHOLD_HZ:
        return "869 MHz"
    return "2.4 GHz"


def _antenna_jack(freq_hz):
    """Return the antenna jack name for antenna swap messages."""
    if freq_hz < BAND_THRESHOLD_HZ:
        return "sub-GHz jack (Pin 9)"
    return "2.4 GHz jack (Pin 10)"


def _mod_params_changed(prev, cur):
    """Return True if radio parameters changed between two preset configs.
    SX1280 can't hot-switch mod/sf/br/bw — needs SWD reset."""
    if prev.get("mod") != cur.get("mod"):
        return True
    if prev.get("sf") != cur.get("sf"):
        return True
    if prev.get("bw") != cur.get("bw"):
        return True
    if prev.get("br") != cur.get("br"):
        return True
    return False


def build_preset_schedule(cfgs, t0_epoch, t0_margin=120, guard=20,
                          settle=2.0, rx_lead=0,
                          t0_margin_s=None, guard_s=None,
                          settle_s=None, swd_reset_s=0, band_swap_s=0):
    """Absolute epoch start times for each config in a preset.

    Like build_stop_schedule but works on preset configs (which have
    their own airtime + gap, not MOD_DEFS cells).

    Accepts both short-form (t0_margin, guard, settle) and long-form
    (t0_margin_s, guard_s, settle_s) keyword arguments for compatibility.

    rx_lead is added to the inter-config gap so the RX has time to
    re-arm between capture windows (capture_duration = expected_s +
    settle + guard; without rx_lead the gap equals the capture window,
    leaving zero re-arming time for subsequent configs).

    swd_reset_s: extra seconds added to the inter-config gap when
    modulation parameters change between consecutive configs. This
    accounts for the SWD reset + board reopen time (~6s) needed when
    the SX1280 can't hot-switch mod/sf/br/bw.

    band_swap_s: extra seconds added to the inter-config gap when
    the frequency crosses the 1.6 GHz band boundary between consecutive
    configs (sub-GHz ↔ 2.4 GHz). This gives the operator time to
    physically swap the antenna cable between jacks (default 0; the
    CLI --band-swap-s default is 30).
    """
    if t0_margin_s is not None:
        t0_margin = t0_margin_s
    if guard_s is not None:
        guard = guard_s
    if settle_s is not None:
        settle = settle_s

    starts = []
    t = t0_epoch + t0_margin
    prev = None
    for c in cfgs:
        # Add SWD reset extra time BEFORE this config's start (the reset
        # happens when transitioning FROM prev TO this config, so the
        # extra gap must precede this config, not follow it).
        extra = swd_reset_s if (prev is not None and _mod_params_changed(prev, c)) else 0
        # Add band swap delay when frequency crosses the 1.6 GHz boundary
        if prev is not None and is_band_transition(prev.get("freq"), c.get("freq")):
            extra += band_swap_s
        t += extra
        starts.append(t)
        t += c["expected_s"] + settle + guard + rx_lead
        prev = c
    return starts


def compute_late_skip(starts, now, rx_lead=0, min_ahead_s=5.0):
    """Return the index into `starts` where the schedule can still be
    joined, or `None` if the entire schedule has already passed.

    The returned index `i` is the first entry whose *effective arm point*
    (`starts[i] - rx_lead`) is at least `min_ahead_s` seconds in the
    future relative to `now`. This gives the local machine enough time
    to finish board open + drain + (optional FW hash gate) + config
    command sequence before needing to arm/start.

    Returns 0 if the whole schedule is still in the future (no skip
    needed). Returns None if even the last config's arm point is in
    the past — the operator must re-T0 and relaunch.

    Pure function: no side effects, no time.time() calls. Both
    `run_tx_mode` and `run_rx_mode` use this to detect late launches
    before the schedule loop, turning silent desync (the previous
    behaviour, where wait_until() silently no-ops on past timestamps)
    into a clear abort or, with --skip-late-configs, an explicit
    recovery of the remaining future configs. See
    docs/timing-tolerance-analysis.md §3 (failure modes) and §6
    (implementation notes) for the design rationale.
    """
    earliest = now + min_ahead_s
    for i, s in enumerate(starts):
        if (s - rx_lead) >= earliest:
            return i
    return None


def apply_late_skip(cfgs, starts, now, rx_lead, min_ahead_s=5.0,
                    skip_late=False, mode_label=""):
    """Apply the launch-lateness check + (optional) skip to a schedule.

    Returns `(cfgs, starts)` sliced to the recovered starting index, or
    raises SystemExit with an actionable message describing lateness and
    how to recover.

    - If the schedule is still on time (returned index == 0): returns the
      original lists unchanged (no missed configs).
    - If returned index > 0 and `skip_late` is True: slices cfgs/starts
      to that index (recovered case — both machines launched equally
      late). Prints a [LATE] notice on stdout.
    - If returned index == None: all start times are past; raises
      SystemExit telling the operator to re-T0.
    - Otherwise (index > 0 and not skip_late): raises SystemExit with
      the seconds-late and the suggested --skip-late-configs command.
    """
    idx = compute_late_skip(starts, now, rx_lead=rx_lead,
                            min_ahead_s=min_ahead_s)
    if idx is None:
        sys.exit("ERROR [{}]: all {} config start times are already in the "
                 "past (last start was {:.0f}s ago). Re-set T0 to a "
                 "future time and relaunch.".format(
                     mode_label or "?", len(starts), now - starts[-1]))
    if idx == 0:
        # On time, nothing to do
        return cfgs, starts
    # idx > 0: some configs already past
    if not skip_late:
        sys.exit("ERROR [{}]: launched {:.0f}s after T0 — configs 0..{} "
                 "have already started (their start - rx_lead timestamps "
                 "are in the past). Aborting to avoid silent desync: "
                 "wait_until() would no-op and the RX would capture "
                 "noise under the wrong config header. Re-set T0 to a "
                 "future time, or pass --skip-late-configs to start "
                 "from config {} ({}).".format(
                     mode_label or "?",
                     now - (starts[0] - rx_lead),
                     idx - 1,
                     idx + 1,
                     cfgs[idx]["label"]))
    print("[LATE - {}] Skipping configs 0..{} (start arm-points passed "
          "{:.0f}..{:.0f}s ago). Resuming from config {}: {}.".format(
              mode_label or "?", idx - 1,
              now - (starts[0] - rx_lead),
              now - (starts[idx - 1] - rx_lead),
              idx + 1, cfgs[idx]["label"]))
    return cfgs[idx:], starts[idx:]


def parse_pkt_line(line):
    """Parse a firmware PKT console line into a dict with 23 harmonized fields.

    Format: PKT,session_id,config_id,replicate,seq,ts_ms,rssi_dbm,snr_db,
    crc_ok,bit_err,bytes_bad,freq_hz,mod,sf,bw_khz,cr,power_dbm,pkt_size,
    gps_fix,gps_lat,gps_lon,gps_alt,gps_sats,gps_hdop

    The firmware always emits 24 comma-separated elements (PKT prefix + 23
    data fields). GPS fields are zero from firmware (no GPS on the bench
    board) and are populated host-side by gps_stitch.py.

    Returns None if the line is not a valid PKT line.
    """
    if not line or not line.strip().startswith("PKT,"):
        return None
    p = line.strip().split(",")
    # 23 data fields + "PKT" prefix = 24 elements
    if len(p) < 24:
        return None
    try:
        return {
            "session_id": int(p[1]),
            "config_id": int(p[2]),
            "replicate": int(p[3]),
            "seq": int(p[4]),
            "ts_ms": int(p[5]),
            "rssi_dbm": float(p[6]),
            "snr_db": float(p[7]),
            "crc_ok": int(p[8]),
            "bit_err": int(p[9]),
            "bytes_bad": int(p[10]),
            "freq_hz": int(p[11]),
            "mod": p[12],
            "sf": int(p[13]),
            "bw_khz": int(p[14]),
            "cr": int(p[15]),
            "power_dbm": int(p[16]),
            "pkt_size": int(p[17]),
            "gps_fix": int(p[18]),
            "gps_lat": float(p[19]),
            "gps_lon": float(p[20]),
            "gps_alt": float(p[21]),
            "gps_sats": int(p[22]),
            "gps_hdop": float(p[23]),
        }
    except (ValueError, IndexError):
        return None


def parse_pkt_line_legacy(line):
    """Legacy parser for the old 16-column CSV schema.

    Kept for backward compatibility with --format legacy. Parses a subset
    of the firmware PKT line using the old field names (session, config,
    pkt_idx, sf_or_br, bw, pa_dbm, len, pcrc16).
    """
    if not line or not line.strip().startswith("PKT,"):
        return None
    p = line.strip().split(",")
    if len(p) < 18:
        return None
    try:
        return {
            "session": int(p[1]),
            "config": int(p[2]),
            "pkt_idx": int(p[4]),
            "ts_ms": int(p[5]),
            "rssi_dbm": float(p[6]),
            "snr_db": float(p[7]),
            "crc_ok": int(p[8]),
            "bit_err": int(p[9]),
            "freq_hz": int(p[11]),
            "mod": p[12],
            "sf_or_br": int(p[13]) if p[13].lstrip("-").isdigit() else p[13],
            "bw": int(p[14]) if p[14].lstrip("-").isdigit() else p[14],
            "pa_dbm": int(p[16]),
            "len": int(p[17]),
            "pcrc16": int(p[24]) if len(p) > 24 else None,
        }
    except (ValueError, IndexError):
        return None


# ---------------------------------------------------------------------------
# Harmonized PKT/STAT formatters (inverse of parse_pkt_line)
# ---------------------------------------------------------------------------

PKT_FIELD_ORDER = [
    "session_id", "config_id", "replicate", "seq", "ts_ms",
    "rssi_dbm", "snr_db", "crc_ok", "bit_err", "bytes_bad",
    "freq_hz", "mod", "sf", "bw_khz", "cr", "power_dbm", "pkt_size",
    "gps_fix", "gps_lat", "gps_lon", "gps_alt", "gps_sats", "gps_hdop",
]


def format_pkt_line(d):
    """Format a parsed PKT dict back to a ``PKT,`` CSV line.

    Inverse of :func:`parse_pkt_line`. Missing fields default to 0.
    Used by gps_stitch.py when rewriting PKT lines with GPS data populated.
    """
    vals = []
    for f in PKT_FIELD_ORDER:
        v = d.get(f, 0)
        if v is None:
            v = 0
        vals.append(str(v))
    return "PKT," + ",".join(vals)


def format_stat_line(role, stat, session, config, replicate=1):
    """Format a parse_stat() dict as a ``STAT,role=...`` line.

    ``stat`` is the dict returned by :func:`parse_stat`. Fields not
    present in the dict default to 0 / empty.
    """
    parts = ["STAT,role={}".format(role)]
    parts.append("sent={}".format(stat.get("sent", 0)))
    parts.append("sent_ok={}".format(stat.get("sent_ok", 0)))
    parts.append("rx={}".format(stat.get("recv", 0)))
    parts.append("crc_err={}".format(stat.get("crc_err", 0)))
    per = stat.get("per_pct")
    parts.append("per_x1e6={}".format(
        int(round(per * 1e4)) if per is not None else 0))
    parts.append("per_ci_x1e6=[{},{}]".format(
        int(stat.get("per_ci_lo_pct", 0) or 0 * 1e4),
        int(stat.get("per_ci_hi_pct", 0) or 0 * 1e4)))
    elapsed = stat.get("elapsed_s")
    parts.append("elapsed_s={}".format(
        "{:.3f}".format(elapsed) if elapsed is not None else ""))
    kbps = stat.get("kbps")
    parts.append("kbps={}".format(
        "{:.3f}".format(kbps) if kbps is not None else ""))
    rssi = stat.get("rssi")
    parts.append("rssi_avg_dbm={}".format(
        "{:.3f}".format(rssi) if rssi is not None else ""))
    snr = stat.get("snr")
    parts.append("snr_avg_db={}".format(
        "{:.3f}".format(snr) if snr is not None else ""))
    parts.append("session={}".format(session))
    parts.append("config={}".format(config))
    parts.append("replicate={}".format(replicate))
    parts.append("drops={}".format(stat.get("drops", 0)))
    parts.append("gap_us={}".format(stat.get("gap_us", 0)))
    return ",".join(parts)


def _detect_board_for_mode(mode, port, probe_serial):
    """Auto-detect board for the given mode using e80_detect.

    Returns (port, probe_serial). Exits with clear error if no board found.
    """
    if port and probe_serial:
        return port, probe_serial

    # Try importing e80_detect
    _detect = None
    for p in [os.path.join(os.path.dirname(os.path.abspath(__file__)), "e80_detect.py")]:
        d = os.path.dirname(p)
        if d not in sys.path:
            sys.path.insert(0, d)
    try:
        import e80_detect as _detect_mod
        _detect = _detect_mod.detect_board
    except ImportError:
        pass

    if _detect is None:
        # Fallback: manual CH340 port detection (from e80_sweep_full.py pattern)
        import glob as _glob
        import platform as _platform
        _is_mac = _platform.system() == "Darwin"
        ch340_ports = []
        if _is_mac:
            # macOS: /dev/cu.usbserial-* ports, verify with ioreg
            for dev in sorted(_glob.glob("/dev/cu.usbserial-*")):
                ch340_ports.append(dev)
        else:
            # Linux: /dev/ttyUSB* + udevadm
            for dev in sorted(_glob.glob("/dev/ttyUSB*")):
                try:
                    import subprocess as _sp
                    r = _sp.run(["udevadm", "info", "-q", "property", "-n", dev],
                                capture_output=True, text=True, timeout=5)
                    if "CH340" in r.stdout:
                        ch340_ports.append(dev)
                except Exception:
                    pass
        if not ch340_ports:
            sys.exit("ERROR: No CH340 serial port found. Ensure the E80 board's "
                     "USB-serial cable is connected.")
        if len(ch340_ports) > 1:
            # Loud-fail: never silently pick the first CH340. On a 2-board desk
            # this handed the same port to both tx and rx → 'multiple access on
            # port' (9209aaf). Pin exact ports instead. (Known probe serials are
            # hardcoded here because this fallback runs only when e80_detect's
            # import failed — the constants aren't reachable.)
            sys.exit(
                "ERROR: Multiple CH340 ports found ({}). Board role cannot be "
                "determined. Use exact override commands:\n"
                "  make tx PORT=<tx-port> PROBE=148757200D2D1425\n"
                "  make rx PORT=<rx-port> PROBE=203584200D2D0D42".format(
                    ch340_ports,
                )
            )
        port = ch340_ports[0]
        probe_serial = probe_serial or None
        return port, probe_serial

    target_role = "TX" if mode == "tx" else "RX"
    result = _detect(target_role)
    if "error" in result:
        sys.exit("ERROR: {}".format(result["error"]))

    port = port or result.get("port")
    probe_serial = probe_serial or result.get("probe_serial")
    return port, probe_serial


class TxLogWriter:
    """tx-log.csv: one row per config cell. Incremental flush for crash safety."""

    COLUMNS = ["session", "config_idx", "label", "n_pkts", "sent_ok",
               "mod", "sf_or_br", "bw", "pa_dbm", "freq_hz", "plen",
               "gap_us", "t0_offset_s", "actual_start_ts", "error"]

    def __init__(self, path, session_id):
        self.path = path
        self.session_id = session_id
        if not os.path.exists(path) or os.path.getsize(path) == 0:
            with open(path, "w", newline="") as f:
                f.write(",".join(self.COLUMNS) + "\n")

    def config_row(self, config_idx, label, n_pkts, sent_ok,
                   mod, sf_or_br, bw, pa_dbm, freq_hz, plen, gap_us,
                   t0_offset_s, actual_start_ts, error=""):
        row = [str(self.session_id), str(config_idx), label, n_pkts, sent_ok,
               mod, sf_or_br, bw, pa_dbm, freq_hz, plen, gap_us,
               round(t0_offset_s, 1), actual_start_ts, error]
        with open(self.path, "a") as f:
            f.write(",".join(str(x) for x in row) + "\n")
            f.flush()

    def comment(self, text):
        with open(self.path, "a") as f:
            f.write("# {}\n".format(text))
            f.flush()


class RxLogWriter:
    """rx-log.csv: one row per received packet. Incremental flush."""

    COLUMNS = ["session", "config", "pkt_idx", "ts_ms", "rssi_dbm", "snr_db",
               "crc_ok", "bit_err", "freq_hz", "mod", "sf_or_br", "bw",
               "pa_dbm", "len", "pcrc16", "captured_ts"]

    def __init__(self, path):
        self.path = path
        if not os.path.exists(path) or os.path.getsize(path) == 0:
            with open(path, "w", newline="") as f:
                f.write(",".join(self.COLUMNS) + "\n")

    def pkt_row(self, session, config, pkt_idx, ts_ms, rssi_dbm, snr_db,
                crc_ok, bit_err, freq_hz, mod, sf_or_br, bw, pa_dbm, len,
                pcrc16, captured_ts=None):
        if captured_ts is None:
            captured_ts = datetime.datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
        row = [session, config, pkt_idx, ts_ms, rssi_dbm, snr_db,
               crc_ok, bit_err, freq_hz, mod, sf_or_br, bw, pa_dbm, len,
               pcrc16, captured_ts]
        with open(self.path, "a") as f:
            f.write(",".join(str(x) for x in row) + "\n")
            f.flush()


# ---------------------------------------------------------------------------
# Harmonized writers (PKT + STAT line format)
# ---------------------------------------------------------------------------

class HarmonizedRxLogWriter:
    """rx-log: PKT + STAT lines in harmonized format. Incremental flush.

    The output file is a plain text file with three line types:
      - ``PKT,<23 fields>``  — one per received packet
      - ``STAT,role=RX,...`` — one per config after burst capture
      - ``# <text>``         — metadata / comments

    No CSV header row — PKT/STAT lines are self-describing.
    """

    def __init__(self, path):
        self.path = path
        # No header row — PKT/STAT lines are self-describing

    def pkt_line(self, pkt_dict):
        """Write a PKT line from a parsed packet dict."""
        line = format_pkt_line(pkt_dict)
        with open(self.path, "a") as f:
            f.write(line + "\n")
            f.flush()

    def stat_line(self, role, stat, session, config, replicate=1):
        """Write a STAT line from a parse_stat() dict."""
        line = format_stat_line(role, stat, session, config, replicate)
        with open(self.path, "a") as f:
            f.write(line + "\n")
            f.flush()

    def comment(self, text):
        with open(self.path, "a") as f:
            f.write("# {}\n".format(text))
            f.flush()


class HarmonizedTxLogWriter:
    """tx-log: STAT lines for TX side. Incremental flush.

    The output file contains only STAT and comment lines (no PKT lines —
    TX does not receive packets).
    """

    def __init__(self, path, session_id):
        self.path = path
        self.session_id = session_id

    def stat_line(self, config_idx, stat_dict, replicate=1):
        """Write a ``STAT,role=TX`` line from a stat dict."""
        line = format_stat_line("TX", stat_dict,
                                self.session_id, config_idx, replicate)
        with open(self.path, "a") as f:
            f.write(line + "\n")
            f.flush()

    def comment(self, text):
        with open(self.path, "a") as f:
            f.write("# {}\n".format(text))
            f.flush()

def run_tx_mode(args):
    """TX-only distributed mode. Sends bursts on T0-anchored schedule.

    With --loop N (default 1), the schedule is repeated N times (0 = infinite).
    Each cycle recomputes T0 = time.time() + t0_margin and regenerates the
    schedule via build_preset_schedule. The cycle number (1-based) is used
    as the replicate counter in CSV log lines.
    """

    # Load config preset
    cfgs = load_config_preset(args.configs)
    t0 = parse_t0(args.t0)

    # Auto-detect board
    port, probe_serial = _detect_board_for_mode("tx", args.port, args.probe)

    loop_count = getattr(args, "loop", 1)

    print("== DISTRIBUTED TX MODE ==")
    print("  T0:         {}".format(
        datetime.datetime.fromtimestamp(t0).isoformat()))
    print("  Port:       {}".format(port))
    print("  Probe:      {}".format(probe_serial or "(not detected)"))
    print("  Session ID: {}".format(args.session_id))
    print("  Configs:    {}".format(len(cfgs)))
    print("  Loop:       {}".format("infinite (Ctrl-C to stop)" if loop_count == 0 else loop_count))
    print()

    # Open board
    board = BoardSerial(port)
    if not args.skip_fw_check:
        fw = firmware_hash_gate(board, port, skip=False)
        if fw is False:
            sys.exit("ERROR: Firmware hash gate failed on TX board. "
                     "Use --skip-fw-check to bypass.")

    board.drain()
    # Send STOP to clear any leftover RX state from previous test.
    # Safe for RX (IWDG only starts at ARM TX, not RX).
    if args.no_swd_reset:
        try:
            board.cmd("STOP", expect_ok=False, timeout=3.0)
            board.drain(quiet=0.5)
        except Exception:
            pass
    use_harmonized = getattr(args, "format", "harmonized") == "harmonized"
    if use_harmonized:
        log = HarmonizedTxLogWriter(args.tx_log, session_id=args.session_id)
    else:
        log = TxLogWriter(args.tx_log, session_id=args.session_id)
    log.comment("DISTRIBUTED_TX_MODE session={} t0={} port={} probe={} loop={}".format(
        args.session_id, datetime.datetime.fromtimestamp(t0).isoformat(),
        port, probe_serial or "?", loop_count))

    def wait_until(ts):
        while True:
            d = ts - time.time()
            if d <= 0:
                return
            time.sleep(min(d, 30.0))

    cycle = 0
    try:
        while True:
            cycle += 1
            if loop_count > 0 and cycle > loop_count:
                break

            # Recompute T0 and schedule for this cycle
            t0_cycle = time.time() + args.t0_margin
            starts = build_preset_schedule(cfgs, t0_cycle, args.t0_margin,
                                           args.guard, args.settle, args.rx_lead,
                                           swd_reset_s=args.swd_reset_s,
                                           band_swap_s=args.band_swap_s)

            if loop_count != 1:
                print("\n--- TX Cycle {}/{} ---".format(
                    cycle if loop_count > 0 else cycle,
                    loop_count if loop_count > 0 else "∞"))
                print("  T0_cycle:   {}".format(
                    datetime.datetime.fromtimestamp(t0_cycle).isoformat()))
                for i, (c, s) in enumerate(zip(cfgs, starts)):
                    print("  [{}/{}] {} N={} LEN={} start={}".format(
                        i + 1, len(cfgs), c["label"], c["n_pkts"], c["plen"],
                        fmt_offset(s, t0_cycle)))
                print()

            # Launch-lateness guard
            cfgs_cycle, starts_cycle = apply_late_skip(
                cfgs, starts, time.time(),
                rx_lead=0,
                skip_late=args.skip_late_configs,
                mode_label="TX",
            )

            prev_cfg = None
            for idx, (cfg, start) in enumerate(zip(cfgs_cycle, starts_cycle)):
                # Drain stale data from previous config (don't send STOP — it
                # triggers an IWDG watchdog reset on the firmware)
                if idx > 0:
                    board.drain(quiet=0.5)

                # Band transition antenna swap reminder
                if prev_cfg is not None and is_band_transition(prev_cfg.get("freq"), cfg.get("freq")):
                    print("\n⚠️  BAND TRANSITION: {} → {} — SWAP ANTENNA to {} NOW\n".format(
                        _band_label(prev_cfg["freq"]), _band_label(cfg["freq"]),
                        _antenna_jack(cfg["freq"])))

                # --- Send radio config BEFORE the scheduled start time ---
                # This allows the firmware self-reset (TCXO startup + calibration
                # triggered by MOD command) to happen during the inter-config
                # gap, eliminating the 3-5s burst delay that required guard>=6s.
                # Firmware handles chip reset internally since c70f582 — no SWD
                # close/reopen needed.

                # Band override if needed
                if not (BAND_MIN_HZ <= cfg["freq"] <= BAND_MAX_HZ):
                    board.cmd("BAND OVERRIDE {}".format(UNLOCK_PIN))

                # Power unlock if needed
                if cfg["pa"] > INDOOR_CAP_DBM:
                    board.cmd("POWER MODE OUTDOOR {}".format(UNLOCK_PIN))

                # Session/config tagging
                board.cmd("SESSION {}".format(args.session_id))
                board.cmd("CONFIG {} {}".format(cfg["idx"], cycle))

                # Radio config
                if cfg["mod"] == "lora":
                    mod_line = "MOD LORA {} {}".format(cfg["sf"], cfg["bw"])
                else:
                    mod_line = "MOD FLRC {} {}".format(cfg["br"], cfg["pa"])
                board.cmd(mod_line)
                if cfg["mod"] == "lora":
                    board.cmd("PA {}".format(cfg["pa"]))
                board.cmd("FREQ {}".format(cfg["freq"]))

                # Role TX + arm
                board.cmd("ROLE TX")
                board.cmd("ARM TX")

                # Wait for scheduled start — config already sent, radio ready
                wait_until(start)

                # Burst
                prime_discard = getattr(args, 'prime_discard', 0)
                tx_total = compute_tx_total(cfg["n_pkts"], prime_discard)
                start_line = "START N={} LEN={} GAP={}".format(
                    tx_total, cfg["plen"], cfg["gap"])
                actual_start = datetime.datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
                board.cmd(start_line, timeout=max(30.0, cfg["expected_s"] + 60))

                # Poll for completion
                deadline = time.time() + cfg["expected_s"] + 120
                sent_ok = 0
                error = ""
                while time.time() < deadline:
                    try:
                        s = parse_stat(board.stat())
                        sent_ok = s.get("sent_ok", 0)
                    except Exception:
                        sent_ok = sent_ok  # keep last known value
                    if sent_ok >= tx_total:
                        break
                    time.sleep(2.0)
                else:
                    error = "TIMEOUT: sent_ok={}/{}".format(sent_ok, cfg["n_pkts"])

                time.sleep(args.settle)

                sf_or_br = cfg["sf"] if cfg["mod"] == "lora" else cfg["br"]
                bw = cfg["bw"] if cfg["bw"] is not None else 0

                if use_harmonized:
                    # Build a stat dict from the TX config + sent_ok count
                    tx_stat = {
                        "sent": tx_total,
                        "sent_ok": sent_ok,
                        "recv": 0, "crc_err": 0, "per_pct": 0.0,
                        "elapsed_s": cfg["expected_s"],
                        "kbps": None, "rssi": None, "snr": None,
                        "drops": 0, "gap_us": cfg["gap"],
                    }
                    if error:
                        log.comment("ERROR config={}: {}".format(cfg["idx"], error))
                    log.stat_line(cfg["idx"], tx_stat, replicate=cycle)
                else:
                    log.config_row(
                        config_idx=cfg["idx"], label=cfg["label"],
                        n_pkts=cfg["n_pkts"], sent_ok=sent_ok,
                        mod=cfg["mod"], sf_or_br=sf_or_br, bw=bw,
                        pa_dbm=cfg["pa"], freq_hz=cfg["freq"],
                        plen=cfg["plen"], gap_us=cfg["gap"],
                        t0_offset_s=start - t0_cycle, actual_start_ts=actual_start,
                        error=error,
                    )
                print("  [{}/{}] {} sent_ok={}/{}".format(
                    idx + 1, len(cfgs_cycle), cfg["label"], sent_ok, cfg["n_pkts"]))
                prev_cfg = cfg

            if loop_count != 1:
                print("  Cycle {} complete.".format(cycle))

        # Teardown
        board.cmd("ROLE NONE", expect_ok=False, timeout=3.0)
    except KeyboardInterrupt:
        log.comment("ABORTED by operator (Ctrl-C) at cycle {}".format(cycle))
        board.cmd("STOP", expect_ok=False, timeout=3.0)
        board.cmd("ROLE NONE", expect_ok=False, timeout=3.0)
        print("\nABORTED by operator at cycle {}. tx-log.csv has partial data.".format(cycle))
    except Exception as e:
        log.comment("ERROR: {}".format(e))
        print("ERROR: {}".format(e))
        raise
    finally:
        try:
            board.ser.close()
        except Exception:
            pass

    print("\n== TX MODE COMPLETE: {} ==".format(args.tx_log))


# ---------------------------------------------------------------------------
# Distributed RX mode
# ---------------------------------------------------------------------------

def run_rx_mode(args):
    """RX-only distributed mode. Arms RX and captures PKT lines on schedule.

    With --loop N (default 1), the schedule is repeated N times (0 = infinite).
    Each cycle recomputes T0 = time.time() + t0_margin and regenerates the
    schedule via build_preset_schedule. The cycle number (1-based) is used
    as the replicate counter in CSV log lines.
    """
    import subprocess as _sp

    # Load config preset
    cfgs = load_config_preset(args.configs)
    t0 = parse_t0(args.t0)

    # Auto-detect board
    port, probe_serial = _detect_board_for_mode("rx", args.port, args.probe)

    loop_count = getattr(args, "loop", 1)

    print("== DISTRIBUTED RX MODE ==")
    print("  T0:         {}".format(
        datetime.datetime.fromtimestamp(t0).isoformat()))
    print("  Port:       {}".format(port))
    print("  Probe:      {}".format(probe_serial or "(not detected)"))
    print("  Configs:    {}".format(len(cfgs)))
    print("  Loop:       {}".format("infinite (Ctrl-C to stop)" if loop_count == 0 else loop_count))
    print()

    # SWD reset if available (non-fatal if openocd missing)
    def swd_reset_maybe(label="RX"):
        if not probe_serial:
            print("  [SWD] WARNING: No SWD probe detected — board will NOT be reset.")
            print("  [SWD] WARNING: Modulation type change requires chip reset.")
            print("  [SWD] WARNING: LoRa configs will likely FAIL (0 packets received).")
            print("  [SWD] WARNING: Connect a CMSIS-DAP probe (Pico) to fix this.")
            return
        openocd_path = None
        for cand in ("/usr/bin/openocd", os.path.expanduser("~/.local/bin/openocd")):
            if os.path.isfile(cand) and os.access(cand, os.X_OK):
                openocd_path = cand
                break
        if not openocd_path:
            try:
                r = _sp.run(["which", "openocd"], capture_output=True, text=True, timeout=5)
                openocd_path = r.stdout.strip() or None
            except Exception:
                pass
        if not openocd_path:
            print("  [SWD] WARNING: openocd not found — board will NOT be reset.")
            print("  [SWD] WARNING: Install openocd to enable SWD reset between configs.")
            return
        fw_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        try:
            _sp.run(
                [openocd_path, "-f", "interface/cmsis-dap.cfg",
                 "-f", "target/stm32f1x.cfg",
                 "-c", "transport select swd; adapter serial {}; "
                       "init; reset halt; resume; exit".format(probe_serial)],
                stdout=_sp.DEVNULL, stderr=_sp.DEVNULL,
                timeout=30, cwd=fw_dir)
            time.sleep(2.0)
            print("[SWD] Reset {} board (probe={})".format(label, probe_serial))
        except Exception as e:
            print("[SWD] Reset failed (non-fatal): {}".format(e))

    # Helper: decide if SWD reset is needed between configs
    def _mod_changed(prev, cur):
        """Return True if radio parameters changed (SX1280 can't hot-switch)."""
        if prev is None:
            return False
        if prev.get("mod") != cur.get("mod"):
            return True
        if prev.get("sf") != cur.get("sf"):
            return True
        if prev.get("bw") != cur.get("bw"):
            return True
        if prev.get("br") != cur.get("br"):
            return True
        return False

    # Open board
    board = BoardSerial(port)
    if not args.skip_fw_check:
        fw = firmware_hash_gate(board, port, skip=False)
        if fw is False:
            board.close()
            sys.exit("ERROR: Firmware hash gate failed on RX board. "
                     "Use --skip-fw-check to bypass.")

    board.drain()
    # Send STOP to clear any leftover RX state from previous test.
    # Safe for RX (IWDG only starts at ARM TX, not RX).
    if args.no_swd_reset:
        try:
            board.cmd("STOP", expect_ok=False, timeout=3.0)
            board.drain(quiet=0.5)
        except Exception:
            pass
    use_harmonized = getattr(args, "format", "harmonized") == "harmonized"
    if use_harmonized:
        log = HarmonizedRxLogWriter(args.rx_log)
    else:
        log = RxLogWriter(args.rx_log)
    log_comment = "# DISTRIBUTED_RX_MODE t0={} port={} probe={} loop={}\n".format(
        datetime.datetime.fromtimestamp(t0).isoformat(),
        port, probe_serial or "?", loop_count)
    with open(args.rx_log, "a") as f:
        f.write(log_comment)

    def wait_until(ts):
        while True:
            d = ts - time.time()
            if d <= 0:
                return
            time.sleep(min(d, 30.0))

    def drain_pkt_lines(ser, duration_s):
        """Read serial lines for duration_s, return parsed PKT dicts.

        Uses harmonized parse_pkt_line when format=harmonized, legacy
        parse_pkt_line_legacy when format=legacy.
        """
        parser = parse_pkt_line if use_harmonized else parse_pkt_line_legacy
        pkts = []
        deadline = time.time() + duration_s
        buf = ""
        while time.time() < deadline:
            data = ser.read(2048)
            if data:
                buf += data.decode("ascii", errors="replace")
                while "\n" in buf:
                    line, buf = buf.split("\n", 1)
                    line = line.strip()
                    if not line:
                        continue
                    p = parser(line)
                    if p is not None:
                        pkts.append(p)
        return pkts

    cycle = 0
    try:
        while True:
            cycle += 1
            if loop_count > 0 and cycle > loop_count:
                break

            # Recompute T0 and schedule for this cycle
            t0_cycle = time.time() + args.t0_margin
            starts = build_preset_schedule(cfgs, t0_cycle, args.t0_margin,
                                           args.guard, args.settle, args.rx_lead,
                                           swd_reset_s=args.swd_reset_s,
                                           band_swap_s=args.band_swap_s)

            if loop_count != 1:
                print("\n--- RX Cycle {}/{} ---".format(
                    cycle if loop_count > 0 else cycle,
                    loop_count if loop_count > 0 else "∞"))
                print("  T0_cycle:   {}".format(
                    datetime.datetime.fromtimestamp(t0_cycle).isoformat()))
                for i, (c, s) in enumerate(zip(cfgs, starts)):
                    print("  [{}/{}] {} RX_arm={} start={}".format(
                        i + 1, len(cfgs), c["label"], c["n_pkts"],
                        fmt_offset(s - args.rx_lead, t0_cycle)))
                print()

            # Launch-lateness guard
            cfgs_cycle, starts_cycle = apply_late_skip(
                cfgs, starts, time.time(),
                rx_lead=args.rx_lead,
                skip_late=args.skip_late_configs,
                mode_label="RX",
            )

            prev_cfg = None
            for idx, (cfg, start) in enumerate(zip(cfgs_cycle, starts_cycle)):
                # When --no-swd-reset is set, send STOP before every config
                # to put the radio to sleep and clear any PKT flood from
                # continuous RX mode. This ensures MOD/FREQ/ROLE/START
                # commands get clean OK responses. Safe for RX (IWDG only
                # starts at ARM TX, not RX).
                if idx > 0 and args.no_swd_reset:
                    try:
                        board.cmd("STOP", expect_ok=False, timeout=3.0)
                    except Exception:
                        pass
                    board.drain(quiet=0.5)
                elif idx > 0:
                    board.drain(quiet=0.5)

                # Band transition antenna swap reminder
                if prev_cfg is not None and is_band_transition(prev_cfg.get("freq"), cfg.get("freq")):
                    print("\n⚠️  BAND TRANSITION: {} → {} — SWAP ANTENNA to {} NOW\n".format(
                        _band_label(prev_cfg["freq"]), _band_label(cfg["freq"]),
                        _antenna_jack(cfg["freq"])))

                # SWD reset if modulation parameters changed (SX1280 can't
                # hot-switch mod/sf/br/bw via MOD command — firmware returns
                # OK but radio doesn't reconfigure, resulting in 0 packets)
                # --no-swd-reset: skip openocd reset, just reconfigure radio
                # with MOD/FREQ/ROLE/START (firmware handles chip reset
                # internally since c70f582).
                if idx > 0 and _mod_changed(prev_cfg, cfg):
                    if args.no_swd_reset:
                        print("  [SWD] Mod params changed — STOP already sent, reconfiguring (--no-swd-reset)")
                    else:
                        print("  [SWD] Mod params changed, resetting RX board…")
                        board.close()
                        swd_reset_maybe(label="RX")
                        board = BoardSerial(port)
                        board.drain()

                # Arm RX rx_lead seconds before burst start
                wait_until(start - args.rx_lead)

                # Band override if needed
                if not (BAND_MIN_HZ <= cfg["freq"] <= BAND_MAX_HZ):
                    board.cmd("BAND OVERRIDE {}".format(UNLOCK_PIN))

                # Power unlock if needed (must be sent BEFORE any PA command)
                if cfg["pa"] > INDOOR_CAP_DBM:
                    board.cmd("POWER MODE OUTDOOR {}".format(UNLOCK_PIN))

                # Session/config tagging
                board.cmd("SESSION {}".format(args.session_id))
                board.cmd("CONFIG {} {}".format(cfg["idx"], cycle))

                # Radio config
                if cfg["mod"] == "lora":
                    mod_line = "MOD LORA {} {}".format(cfg["sf"], cfg["bw"])
                else:
                    mod_line = "MOD FLRC {} {}".format(cfg["br"], cfg["pa"])
                board.cmd(mod_line)
                if cfg["mod"] == "lora":
                    board.cmd("PA {}".format(cfg["pa"]))
                board.cmd("FREQ {}".format(cfg["freq"]))

                # Role RX
                board.cmd("ROLE RX")

                # Arm RX: START resets stats and arms listener
                start_line = "START N={} LEN={} GAP={}".format(
                    cfg["n_pkts"], cfg["plen"], cfg["gap"])
                board.cmd(start_line)

                # Wait for burst start + duration + settle
                wait_until(start)
                capture_duration = cfg["expected_s"] + args.settle + args.guard
                pkts = drain_pkt_lines(board.ser, capture_duration)

                # Discard prime (AGC warmup) packets before logging
                prime_discard = getattr(args, 'prime_discard', 0)
                pkts = discard_prime_pkts(pkts, prime_discard)

                # Write packets to log
                if use_harmonized:
                    for p in pkts:
                        log.pkt_line(p)
                else:
                    for p in pkts:
                        log.pkt_row(
                            session=p["session"], config=p["config"],
                            pkt_idx=p["pkt_idx"], ts_ms=p["ts_ms"],
                            rssi_dbm=p["rssi_dbm"], snr_db=p["snr_db"],
                            crc_ok=p["crc_ok"], bit_err=p["bit_err"],
                            freq_hz=p["freq_hz"], mod=p["mod"],
                            sf_or_br=p["sf_or_br"], bw=p["bw"],
                            pa_dbm=p["pa_dbm"], len=p["len"],
                            pcrc16=p["pcrc16"] or 0,
                        )

                # Read STAT for summary (non-fatal on error)
                try:
                    rx_stat = parse_stat(board.stat())
                except Exception:
                    rx_stat = {}
                # STAT? recv includes prime packets — subtract them
                adjust_stat_for_prime(rx_stat, prime_discard)
                if use_harmonized:
                    log.stat_line("RX", rx_stat, args.session_id, cfg["idx"],
                                  replicate=cycle)
                print("  [{}/{}] {} recv={}/{} rssi={} snr={}".format(
                    idx + 1, len(cfgs_cycle), cfg["label"],
                    len(pkts), cfg["n_pkts"],
                    rx_stat.get("rssi", "?"), rx_stat.get("snr", "?")))
                prev_cfg = cfg

            if loop_count != 1:
                print("  Cycle {} complete.".format(cycle))

        # Teardown
        board.cmd("ROLE NONE", expect_ok=False, timeout=3.0)
    except KeyboardInterrupt:
        with open(args.rx_log, "a") as f:
            f.write("# ABORTED by operator (Ctrl-C) at cycle {}\n".format(cycle))
        board.cmd("STOP", expect_ok=False, timeout=3.0)
        board.cmd("ROLE NONE", expect_ok=False, timeout=3.0)
        print("\nABORTED by operator at cycle {}. rx-log.csv has partial data.".format(cycle))
    except Exception as e:
        with open(args.rx_log, "a") as f:
            f.write("# ERROR: {}\n".format(e))
        print("ERROR: {}".format(e))
        raise
    finally:
        board.close()

    print("\n== RX MODE COMPLETE: {} ==".format(args.rx_log))
    return 0


# ---------------------------------------------------------------------------
# Distributed dry-run (preset mode)
# ---------------------------------------------------------------------------

def dry_run_preset(args):
    """Print schedule from config preset without touching hardware."""
    cfgs = load_config_preset(args.configs)
    t0 = parse_t0(args.t0) if args.t0 else time.time()
    starts = build_preset_schedule(cfgs, t0, args.t0_margin, args.guard,
                                   args.settle, args.rx_lead,
                                   swd_reset_s=args.swd_reset_s,
                                   band_swap_s=args.band_swap_s)

    print("== DRY RUN (distributed preset) ==")
    print("Config file:  {}".format(args.configs))
    print("T0:           {}".format(
        datetime.datetime.fromtimestamp(t0).isoformat()))
    print("t0_margin:    {}s  guard: {}s  rx_lead: {}s  settle: {}s  swd_reset: {}s".format(
        args.t0_margin, args.guard, args.rx_lead, args.settle, args.swd_reset_s))
    print("Configs:      {}".format(len(cfgs)))
    print("=" * 80)

    for i, (c, s) in enumerate(zip(cfgs, starts)):
        sf_br = c["sf"] if c["mod"] == "lora" else "{}k".format(c["br"])
        bw = c["bw"] if c["bw"] is not None else "-"
        print("\n[{:>2}/{}] {}".format(i + 1, len(cfgs), c["label"]))
        print("  mod={}  sf/br={}  bw={}  pa={}dBm  freq={:.3f}MHz".format(
            c["mod"], sf_br, bw, c["pa"], c["freq"] / 1e6))
        print("  plen={}B  gap={}us  n_pkts={}  airtime={:.3f}s  expected={:.1f}s".format(
            c["plen"], c["gap"], c["n_pkts"], c["airtime_s"], c["expected_s"]))
        print("  RX arm @ {} | TX start @ {}".format(
            fmt_offset(s - args.rx_lead, t0),
            fmt_offset(s, t0)))
        print("  Capture duration: {:.1f}s".format(
            c["expected_s"] + args.settle + args.guard))

    print("\n" + "=" * 80)
    total_s = starts[-1] + cfgs[-1]["expected_s"] + args.settle + args.guard - t0
    print("Total wall time: {} (T0+0 to T0+{})".format(
        fmt_hms(total_s), fmt_hms(total_s)))
    return 0


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
            compute_tx_total(c["n"], getattr(args, 'prime_discard', 0)),
            c["len_bytes"], c["gap_us"])
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
        description="E80 two-board bench controller — single-shot FLRC-650, "
                    "range-campaign matrix, or distributed TX/RX split modes")
    # --- Distributed mode (new) ---
    ap.add_argument("--mode", choices=["tx", "rx"], default=None,
                    help="distributed mode: 'tx' = TX-only on schedule, "
                         "'rx' = RX-only capture on schedule. "
                         "Requires --configs and --t0.")
    ap.add_argument("--configs", default=None,
                    help="config preset JSON file (e.g. configs/outdoor-10.json)")
    ap.add_argument("--port", default=None,
                    help="serial port (auto-detected if omitted)")
    ap.add_argument("--probe", default=None,
                    help="SWD probe serial (auto-detected if omitted)")
    ap.add_argument("--tx-log", dest="tx_log", default="tx-log.csv",
                    help="TX log CSV output (default: tx-log.csv)")
    ap.add_argument("--rx-log", dest="rx_log", default="rx-log.csv",
                    help="RX log CSV output (default: rx-log.csv)")
    ap.add_argument("--session-id", dest="session_id", type=int, default=None,
                    help="session ID (auto-generated from timestamp if omitted)")
    # --- Legacy single-shot + matrix mode ---
    ap.add_argument("--tx", default="/dev/ttyUSB3", help="TX board serial port")
    ap.add_argument("--rx", default="/dev/ttyUSB4", help="RX board serial port")
    ap.add_argument("--freq", type=int, default=868000000,
                    help="Hz; 863-870 MHz (EU SRD) unless --band-override "
                         "(then firmware window 410-2483 MHz)")
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
    ap.add_argument("--t0-margin", dest="t0_margin", type=int, default=30,
                    help="seconds after T0 before cell 1 (default 30, was 120)")
    ap.add_argument("--guard", type=int, default=5,
                    help="inter-cell guard seconds (default 5, was 20)")
    ap.add_argument("--rx-lead", dest="rx_lead", type=int, default=3,
                    help="seconds RX arms before cell start (default 3, was 10)")
    ap.add_argument("--settle", type=int, default=1,
                    help="post-burst settle seconds before RX STAT? (default 1, was 2)")
    ap.add_argument("--swd-reset-s", dest="swd_reset_s", type=int, default=2,
                    help="extra inter-config gap seconds when mod params change "
                         "(SWD reset + board reopen time, default 2, was 10)")
    ap.add_argument("--no-swd-reset", dest="no_swd_reset", action="store_true",
                    help="skip openocd SWD reset between configs — just "
                         "reconfigure radio with MOD/FREQ/ROLE/START commands. "
                         "Firmware supports hot-switching modulation parameters "
                         "(since c70f582). Use for boat-rx and multi-config RX.")
    ap.add_argument("--band-swap-s", dest="band_swap_s", type=int, default=30,
                    help="extra inter-config gap seconds when frequency crosses "
                         "the 1.6 GHz band boundary (sub-GHz ↔ 2.4 GHz) — gives "
                         "operator time to physically swap antenna cable "
                         "(default 30)")
    ap.add_argument("--skip-late-configs", dest="skip_late_configs",
                    action="store_true",
                    help="if launched after one or more config start times "
                         "have already passed, skip those configs and resume "
                         "from the next future one (default: abort with an "
                         "error message). See "
                         "docs/timing-tolerance-analysis.md.")
    ap.add_argument("--skip-fw-check", action="store_true",
                    help="skip firmware hash gate (not recommended)")
    ap.add_argument("--prime-discard", dest="prime_discard", type=int,
                    default=DEFAULT_PRIME_DISCARD,
                    help="number of AGC warmup 'prime' packets to prepend "
                         "before the measured burst (default {}). TX sends "
                         "N+prime total; RX discards the first prime PKT "
                         "lines. Set to 0 to disable.".format(
                             DEFAULT_PRIME_DISCARD))
    ap.add_argument("--format", choices=["harmonized", "legacy"],
                    default="harmonized",
                    help="output format: 'harmonized' = PKT+STAT lines "
                         "(23-field, default); 'legacy' = 16-column CSV "
                         "with header row")
    ap.add_argument("--loop", type=int, default=1,
                    help="number of sweep cycles in distributed mode "
                         "(default 1; 0 = infinite until Ctrl-C). "
                         "Each cycle recomputes T0 and regenerates the "
                         "schedule. The cycle number is used as the "
                         "replicate counter in CSV logs.")
    args = ap.parse_args()

    # --- Distributed mode routing ---
    if args.mode:
        if not args.configs:
            sys.exit("--mode {} requires --configs <preset.json>".format(args.mode))
        if not args.t0 and not args.dry_run:
            sys.exit("--mode {} requires --t0 'YYYY-MM-DD HH:MM:SS'".format(args.mode))
        if args.session_id is None:
            args.session_id = int(datetime.datetime.now().strftime("%y%m%d%H%M"))
        if args.dry_run:
            return dry_run_preset(args)
        try:
            if args.mode == "tx":
                return run_tx_mode(args)
            else:
                return run_rx_mode(args)
        except RuntimeError as e:
            sys.exit("ERROR: {}".format(e))
        except KeyboardInterrupt:
            sys.exit("ERROR: interrupted — partial data in log CSV")

    # --- Legacy mode (single-shot or matrix) ---
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
