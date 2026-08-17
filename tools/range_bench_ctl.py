#!/usr/bin/env python3
"""Range bench controller — host-driven PER bench + range-campaign matrix runner.

LR2021 RP2040 firmware (balloon-fresh, branch feat/host-driven-bench).
Ported from e80_bench_ctl.py (E80 STM32+SX1280@2.4 GHz) — protocol patterns,
Wilson math, safety math, and host-script architecture carried over; radio
register sequences and frequency/band constants adapted for LR2021 LF path.

Console protocol v1 (plan §1):
    Single-line, case-insensitive, \\r\\n-terminated, accepted on both USB CDC
    (Serial) and UART (Serial1 -> ESP32 bridge).  Every reply echoed on both.

HS-1a scope: scaffold + pure helpers (airtime_s, n_for_mod, VirtualClock).
HS-1b scope: matrix cells (make_cell / build_matrix_cells — LF cells v1 with
    the grill-B2 feasible=pending flag on LF-FLRC, HF cells listed but
    excluded from the default matrix), T0 stop schedule (parse_t0 /
    build_stop_schedule with rx_lead + guard / fmt_offset / fmt_hms), and
    freq_gate (EU SRD 863-870 MHz hard clamp v1 — no override).
    parse_stat, CsvLog, session runner, and dry-run arrive in HS-2+.

Usage (scaffold — full CLI wired in HS-4+):
    python3 tools/range_bench_ctl.py --dry-run --matrix flrc650,sf7
"""
import argparse
import datetime
import sys

# ---------------------------------------------------------------------------
# Constants (plan §1 + BW-1 single source: vendored Semtech lr20xx_driver)
# ---------------------------------------------------------------------------

BAND_MIN_HZ = 863_000_000          # EU SRD clamp (firmware-identical, LF path)
BAND_MAX_HZ = 870_000_000
UNLOCK_PIN = 2026
INDOOR_CAP_DBM = 10
TXPOW_MAX_DBM = 22

CSV_COLUMNS = [
    "site", "stop", "dist_m", "repeat", "mod", "len", "pa", "freq_hz",
    "n", "sent", "recv", "per", "per_ci_lo", "per_ci_hi", "rssi",
    "snr", "kbps", "elapsed_s", "timestamp",
]

# ---------------------------------------------------------------------------
# Modulation definitions (plan §3 — BW values from BW-1 single source)
# ---------------------------------------------------------------------------

# FLRC bitrates (bps) — LR2021 FLRC modes per Semtech datasheet.
# LoRa BW=125 kHz = 125_000 Hz (BW code from BW-1: vendored lr20xx_driver).
MOD_DEFS: dict = {
    # --- LF path (EU SRD 863-870 MHz) ---
    # feasible: "pending" = LF-FLRC unproven on this module until the HW-B2
    # first-cell smoke passes (grill B2); LoRa LF is proven hardware-default.
    "flrc650":  dict(kind="flrc", mod_lines=["MOD FLRC 650 {dbm}"],
                     gap_us=5000, label="FLRC-650", band="lf",
                     feasible="pending"),
    "flrc2600": dict(kind="flrc", mod_lines=["MOD FLRC 2600 {dbm}"],
                     gap_us=5000, label="FLRC-2600", band="lf",
                     feasible="pending"),
    "sf7":      dict(kind="lora", mod_lines=["MOD LORA 7 125", "PA {dbm}"],
                     gap_us=1000, label="LoRa-SF7", band="lf",
                     feasible="ok"),
    "sf12":     dict(kind="lora", mod_lines=["MOD LORA 12 125", "PA {dbm}"],
                     gap_us=1000, label="LoRa-SF12", band="lf",
                     feasible="ok"),
    # --- HF path (2.4 GHz, listed for completeness; excluded from v1 matrix) ---
    "hf_flrc2600": dict(kind="flrc", mod_lines=["MOD FLRC 2600 {dbm}"],
                        gap_us=5000, label="HF-FLRC-2600", band="hf",
                        feasible="pending"),
    "hf_flrc1300": dict(kind="flrc", mod_lines=["MOD FLRC 1300 {dbm}"],
                        gap_us=5000, label="HF-FLRC-1300", band="hf",
                        feasible="pending"),
}
MATRIX_KEYS = ["flrc650", "flrc2600", "sf7", "sf12"]
HF_KEYS = ["hf_flrc2600", "hf_flrc1300"]

N_HI_DEFAULT = 10_000             # S0 / low-PER regime (plan §3)
N_LO_DEFAULT = 1_000              # high-PER edge regime
N_SF12_CAP = 1_000                # SF12 time cap (10^4 would be ~7 h/cell)
ANCHOR_KEY = "flrc650"
ANCHOR_LEN = 255
MATRIX_LEN = 51
CI_HI_NHI_PCT = 2.0               # Wilson ci_hi threshold for the 10^4 regime

# FLRC bitrate lookup (bps) — keyed by mod name.
_FLRC_BR = {"flrc650": 650_000, "flrc2600": 2_600_000,
            "hf_flrc2600": 2_600_000, "hf_flrc1300": 1_300_000}

# LoRa (sf, bw_hz) lookup — keyed by mod name.
_LORA_PARAMS = {"sf7": (7, 125_000), "sf12": (12, 125_000)}


# ---------------------------------------------------------------------------
# Pure helpers: airtime, N-regime, VirtualClock
# ---------------------------------------------------------------------------

def lora_airtime_s(length, sf, bw_hz, preamble=8, cr=1, crc=1, ih=0):
    """Standard LoRa airtime estimate (s), LDRO for SF>=11 (AN1200.24)."""
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
    """Return airtime (seconds) for a given modulation key and payload length.

    Raises ValueError if mod_key is not in MOD_DEFS.
    """
    if mod_key not in MOD_DEFS:
        raise ValueError("unknown mod {!r}".format(mod_key))
    d = MOD_DEFS[mod_key]
    if d["kind"] == "flrc":
        br = _FLRC_BR[mod_key]
        return flrc_airtime_s(length, br)
    sf, bw = _LORA_PARAMS[mod_key]
    return lora_airtime_s(length, sf, bw)


def n_for_mod(mod_key, prior_rows):
    """Plan §3 N rule: 10^4 if the latest previous LEN=51 row for this mod has
    Wilson ci_hi <= 2 %, else 10^3.  No prior row -> 10^4 (S0 start rule).
    SF12 is time-capped at 10^3 regardless.
    """
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


class VirtualClock:
    """Deterministic time source for schedule tests and dry-run simulation.

    Replaces time.time / time.sleep in run_matrix() so the full session
    runner can be exercised without real delays.
    """

    def __init__(self, t0):
        self.t = float(t0)

    def now(self):
        return self.t

    def sleep(self, d):
        self.t += max(0.0, d)


# ---------------------------------------------------------------------------
# HS-1b: matrix cells, T0 stop schedule, freq gate
# ---------------------------------------------------------------------------

def make_cell(mod_key, n, length=None, anchor=False):
    """Build one MatrixCell dict (plan §3) from a MOD_DEFS entry.

    anchor=True forces the LEN=255 FLRC-650 comparability anchor; otherwise
    LEN defaults to the matrix payload length (51 B).  Carries band and the
    grill-B2 feasibility flag through for the runner / CSV layer.
    """
    d = MOD_DEFS[mod_key]
    len_bytes = ANCHOR_LEN if anchor else (MATRIX_LEN if length is None
                                           else length)
    return dict(key=mod_key, label=d["label"], anchor=anchor,
                band=d["band"], feasible=d["feasible"],
                mod_lines=list(d["mod_lines"]),
                gap_us=d["gap_us"], n=n,
                len_bytes=len_bytes,
                expected_s=n * (airtime_s(mod_key, len_bytes)
                                + d["gap_us"] / 1e6))


def build_matrix_cells(args, prior_rows):
    """Cell list for one stop: requested mods (LEN=51) + optional anchor.

    Each matrix mod's N comes from the plan §3 N-regime (n_for_mod) fed with
    prior CSV rows; the anchor always runs N=10^4.  HF-band mods are listed
    in MOD_DEFS but rejected here — the 2.4 GHz path is out of scope for
    firmware v1 (plan §5).
    """
    cells = []
    for key in args.matrix:
        if key not in MOD_DEFS:
            raise ValueError(
                "unknown mod {!r} (default matrix: {})".format(
                    key, ",".join(MATRIX_KEYS)))
        if MOD_DEFS[key]["band"] == "hf":
            raise ValueError(
                "HF cell {!r} excluded from v1 matrix (2.4 GHz path out of "
                "scope; firmware v1 is LF-only)".format(key))
        cells.append(make_cell(key, n_for_mod(key, prior_rows)))
    if args.anchor:
        cells.append(make_cell(ANCHOR_KEY, N_HI_DEFAULT, anchor=True))
    return cells


def parse_t0(s):
    """Parse --t0 into a local-time epoch.  Accepts 'YYYY-MM-DD HH:MM:SS'
    and the ISO 'T' form."""
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S"):
        try:
            return datetime.datetime.strptime(s, fmt).timestamp()
        except ValueError:
            continue
    raise ValueError(
        "bad --t0 {!r}; want 'YYYY-MM-DD HH:MM:SS' local time".format(s))


def build_stop_schedule(cells, t0_epoch, t0_margin_s, guard_s,
                        rx_lead_s=0.0, settle_s=5.0):
    """Absolute per-cell schedule anchored at T0 (plan §5).

    Returns one dict per cell, in cell order:
        {"key": <mod key>, "start": <epoch>, "rx_arm": <epoch>}

    start  — epoch when this cell's TX burst begins.  First cell starts at
             T0 + t0_margin_s; each subsequent cell at the previous start +
             expected_s + settle_s + guard_s.
    rx_arm — start - rx_lead_s: the epoch when the RX board must already be
             listening (runner sets ROLE RX + START here).  Pass the CLI
             --rx-lead value; defaults to 0 (arm at TX start).
    """
    entries = []
    t = t0_epoch + t0_margin_s
    for c in cells:
        entries.append(dict(key=c["key"], start=t, rx_arm=t - rx_lead_s))
        t += c["expected_s"] + settle_s + guard_s
    return entries


def fmt_offset(epoch, t0_epoch):
    """T0+HH:MM:SS relative to T0; negative offsets clamp to zero."""
    s = int(max(0, epoch - t0_epoch))
    return "T0+{:02d}:{:02d}:{:02d}".format(s // 3600, (s % 3600) // 60,
                                            s % 60)


def fmt_hms(seconds):
    """MM:SS for schedule tables."""
    s = int(seconds)
    return "{:02d}:{:02d}".format(s // 60, s % 60)


def freq_gate(freq_hz):
    """Host-side mirror of the firmware FREQ gate (plan §1): EU SRD
    863-870 MHz LF path, hard clamp for v1 — no band override (plan §5).

    Returns (ok, message); message is "" when ok.
    """
    if not (BAND_MIN_HZ <= freq_hz <= BAND_MAX_HZ):
        return False, ("freq {} Hz outside EU SRD 863-870 MHz (LF path, "
                       "hard clamp v1, no override)".format(freq_hz))
    return True, ""


# ---------------------------------------------------------------------------
# HS-3: Port resolution, FakeBoard, BoardCtl (protocol §1)
# ---------------------------------------------------------------------------

# BoardSerial is the mandatory serial wrapper (tools/board_serial.py).
# Imported lazily so pure tests using FakeBoard don't require pyserial.
try:
    from board_serial import BoardSerial  # noqa: F401
except Exception:  # pragma: no cover — pyserial / board_serial not available
    BoardSerial = None


def resolve_port(port):
    """Resolve a serial port path to a usable device path.

    /dev/serial/by-id/ paths are stable across replug — returned as-is.
    Raw /dev/ttyXXX paths are also returned as-is (already usable).
    None/empty → None.
    """
    if not port:
        return None
    return port


# §1 protocol constants (mirrors firmware flrc_range_host.cpp)

_FLRC_VALID_BR_KBPS = {260, 325, 520, 650, 1040, 1300, 2080, 2600}
_LORA_VALID_SF = set(range(5, 13))           # 5–12
_LORA_VALID_BW_KHZ = {125, 250, 500}
_FREQ_MIN_HZ = 863_000_000
_FREQ_MAX_HZ = 870_000_000
_PA_MIN_DBM = -18
_PA_MAX_DBM = 22
_PA_INDOOR_CAP_DBM = INDOOR_CAP_DBM          # 10
_LEN_MIN = 8
_LEN_MAX = 255
_N_MIN = 1
_N_MAX = 1_000_000
_GAP_MIN_US = 100
_GAP_MAX_US = 100_000_000
_UNLOCK_PIN = UNLOCK_PIN                    # 2026


class FakeBoard:
    """Test double implementing the §1 console protocol for offline tests.

    Simulates the RP2040 range-host firmware: parses commands, updates a
    world-state dict, and returns protocol-correct replies.  Used by
    BoardCtlTests and FakeBoardTests without any hardware.
    """

    BANNER = "ID range-host v1 role=NONE tx_inhibited=1"

    def __init__(self, port, world):
        self.port = port
        self.world = world
        self.log = []
        # Determine which side this board controls
        self.side = "tx" if "tx" in world else "rx"
        self._banner_pending = True

    @property
    def st(self):
        """Shorthand for this board's state dict in the world."""
        return self.world[self.side]

    # -- serial-like interface ----------------------------------------------

    def drain(self):
        """Drain/discard any pending boot banner data (no-op sim)."""
        self._banner_pending = False

    def close(self):
        """Close the board connection (simulated — just logs)."""
        self.log.append("CLOSE")

    # -- protocol command interface -----------------------------------------

    def _send(self, command):
        """Log a command, process it, and return the reply string."""
        self.log.append(command)
        cmd = command.strip().upper()
        return self._handle(cmd)

    def cmd(self, command, expect_ok=True):
        """Send command, return reply.  Raise RuntimeError on ERR when
        expect_ok is True (default).  With expect_ok=False, return the
        ERR reply string without raising."""
        reply = self._send(command)
        if expect_ok and reply.startswith("ERR"):
            raise RuntimeError(reply)
        return reply

    def query(self, command):
        """Send command and return reply without raising on ERR."""
        return self._send(command)

    def stat(self):
        """Query STAT? and return the reply string."""
        return self.query("STAT?")

    # -- §1 protocol handler ------------------------------------------------

    def _handle(self, cmd):
        """Process a §1 command string (uppercased) and return reply."""
        st = self.st
        parts = cmd.split()
        if not parts:
            return "ERR UNKNOWN"

        op = parts[0]

        # ID? ---------------------------------------------------------------
        if op == "ID?":
            return "ID range-host v1 role={} tx_inhibited=1".format(st["role"])

        # ROLE TX / RX / NONE ------------------------------------------------
        if op == "ROLE":
            if len(parts) < 2 or parts[1] not in ("TX", "RX", "NONE"):
                return "ERR ARG"
            st["role"] = parts[1]
            return "OK ROLE {}".format(parts[1])

        # MOD FLRC <br_kbps> / MOD LORA <sf> <bw_khz> -------------------------
        if op == "MOD":
            if len(parts) < 2:
                return "ERR ARG"
            if parts[1] == "FLRC":
                if len(parts) < 3:
                    return "ERR ARG"
                try:
                    br_kbps = int(parts[2])
                except ValueError:
                    return "ERR ARG"
                if br_kbps not in _FLRC_VALID_BR_KBPS:
                    return "ERR RANGE"
                br_bps = br_kbps * 1000
                st["mod"] = "FLRC"
                st["br"] = br_bps
                return "OK MOD FLRC br_hz={}".format(br_bps)
            if parts[1] == "LORA":
                if len(parts) < 4:
                    return "ERR ARG"
                try:
                    sf = int(parts[2])
                    bw_khz = int(parts[3])
                except ValueError:
                    return "ERR ARG"
                if sf not in _LORA_VALID_SF:
                    return "ERR RANGE"
                if bw_khz not in _LORA_VALID_BW_KHZ:
                    return "ERR RANGE"
                st["mod"] = "LORA"
                return "OK MOD LORA sf={} bw_hz={}".format(sf, bw_khz * 1000)
            return "ERR ARG"

        # FREQ <hz> ----------------------------------------------------------
        if op == "FREQ":
            if len(parts) < 2:
                return "ERR ARG"
            try:
                freq = int(parts[1])
            except ValueError:
                return "ERR ARG"
            if freq < _FREQ_MIN_HZ or freq > _FREQ_MAX_HZ:
                return "ERR RANGE"
            st["freq"] = freq
            return "OK FREQ {}".format(freq)

        # PA <dbm> -----------------------------------------------------------
        if op == "PA":
            if len(parts) < 2:
                return "ERR ARG"
            try:
                dbm = int(parts[1])
            except ValueError:
                return "ERR ARG"
            if dbm < _PA_MIN_DBM or dbm > _PA_MAX_DBM:
                return "ERR RANGE"
            if dbm > _PA_INDOOR_CAP_DBM and not st.get("power_outdoor", False):
                return "ERR POWER-LOCKED"
            st["dbm"] = dbm
            return "OK PA {}".format(dbm)

        # LEN <bytes> --------------------------------------------------------
        if op == "LEN":
            if len(parts) < 2:
                return "ERR ARG"
            try:
                length = int(parts[1])
            except ValueError:
                return "ERR ARG"
            if length < _LEN_MIN or length > _LEN_MAX:
                return "ERR RANGE"
            st["len"] = length
            return "OK LEN {}".format(length)

        # N <count> ----------------------------------------------------------
        if op == "N":
            if len(parts) < 2:
                return "ERR ARG"
            try:
                n = int(parts[1])
            except ValueError:
                return "ERR ARG"
            if n < _N_MIN or n > _N_MAX:
                return "ERR RANGE"
            st["n"] = n
            return "OK N {}".format(n)

        # GAP <us> ------------------------------------------------------------
        if op == "GAP":
            if len(parts) < 2:
                return "ERR ARG"
            try:
                gap = int(parts[1])
            except ValueError:
                return "ERR ARG"
            if gap < _GAP_MIN_US or gap > _GAP_MAX_US:
                return "ERR RANGE"
            st["gap_us"] = gap
            return "OK GAP {}".format(gap)

        # POWER MODE OUTDOOR <pin> -------------------------------------------
        if (op == "POWER" and len(parts) >= 4
                and parts[1] == "MODE" and parts[2] == "OUTDOOR"):
            try:
                pin = int(parts[3])
            except ValueError:
                return "ERR ARG"
            if pin != UNLOCK_PIN:
                return "ERR ARG"
            st["power_outdoor"] = True
            return "OK POWER OUTDOOR"

        # START --------------------------------------------------------------
        if op == "START":
            if st["role"] not in ("TX", "RX"):
                return "ERR INHIBITED"
            st["state"] = "RUN"
            if st["role"] == "TX":
                return "OK START n={} len={} gap_us={}".format(
                    st["n"], st["len"], st["gap_us"])
            return "OK START RX"

        # STOP ---------------------------------------------------------------
        if op == "STOP":
            st["state"] = "IDLE"
            return "OK STOP"

        # STAT? --------------------------------------------------------------
        if op == "STAT?":
            return self._format_stat()

        # REBOOT -------------------------------------------------------------
        if op == "REBOOT":
            st["role"] = "NONE"
            st["state"] = "IDLE"
            self._banner_pending = True
            return "OK REBOOT"

        # HELP / ? -----------------------------------------------------------
        if op == "HELP" or op == "?":
            return ("OK HELP ROLE MOD FREQ PA LEN N GAP POWER START STOP "
                    "STAT? REBOOT HELP")

        return "ERR UNKNOWN {}".format(cmd)

    def _format_stat(self):
        """Format a §1 STAT? reply line from the current state."""
        st = self.st
        return ("STAT role={} mod={} br_hz={} freq_hz={} dbm={} len={} n={} "
                "gap_us={} sent={} sent_ok={} rx={} crc_err={} state={}".format(
                    st["role"], st["mod"], st["br"], st["freq"], st["dbm"],
                    st["len"], st["n"], st["gap_us"],
                    st["sent"], st["sent_ok"], st["rx"], st["crc_err"],
                    st["state"]))


class BoardCtl:
    """Wraps a board (FakeBoard or BoardSerial-adapter) with §1 protocol
    conveniences.

    - open():       drain boot banner, ID? handshake, role check
    - cmd():        send command, raise on ERR (expect_ok=True by default)
    - query():      send command, return reply (never raises)
    - stat():       query STAT? and return reply
    - reboot():     send REBOOT, drain new banner, re-handshake
    - close():      close the board
    """

    def __init__(self, board):
        self.board = board
        self.info = None

    def open(self, expected_role=None):
        """Drain boot banner, send ID? handshake, parse and check role.

        Returns a dict with parsed ID? fields (at minimum 'role').
        Raises RuntimeError if expected_role is given and doesn't match.
        """
        self.board.drain()
        reply = self.board.query("ID?")
        self.info = self._parse_id(reply)
        if expected_role is not None:
            actual = self.info.get("role", "?")
            if actual != expected_role:
                raise RuntimeError(
                    "board role mismatch: expected {}, got {}".format(
                        expected_role, actual))
        return self.info

    @staticmethod
    def _parse_id(reply):
        """Parse 'ID range-host v1 role=NONE tx_inhibited=1' into a dict."""
        info = {"ID": reply}
        for token in reply.split():
            if "=" in token:
                k, v = token.split("=", 1)
                info[k] = v
        return info

    def cmd(self, command, expect_ok=True):
        """Send command via board.cmd(), return reply."""
        return self.board.cmd(command, expect_ok=expect_ok)

    def query(self, command):
        """Send query via board.query(), return reply."""
        return self.board.query(command)

    def stat(self):
        """Query STAT? and return the reply string."""
        return self.board.stat()

    def reboot(self):
        """Send REBOOT, drain new boot banner, re-handshake with ID?.

        The board resets role to NONE on REBOOT.  We drain the new banner,
        do a quick liveness ID? check, then a full open() re-handshake.
        """
        self.board.cmd("REBOOT")
        self.board.drain()
        self.board.query("ID?")   # liveness check after reset
        return self.open()         # full re-handshake (drain + ID? + role)

    def close(self):
        """Close the board connection."""
        self.board.close()


# ---------------------------------------------------------------------------
# CLI scaffold (full argument set; wiring in HS-1b+)
# ---------------------------------------------------------------------------

def build_parser():
    """Construct the argparse parser for range_bench_ctl.

    HS-1a: scaffold only — main() is a stub that prints --dry-run info.
    HS-1b+ wires matrix cells, schedule, freq_gate, session runner.
    """
    ap = argparse.ArgumentParser(
        description="LR2021 range bench controller — host-driven PER bench "
                    "and range-campaign matrix runner (plan §1/§3/§5).")
    ap.add_argument("--tx-port", default=None,
                    help="TX board serial port (by-id path preferred)")
    ap.add_argument("--rx-port", default=None,
                    help="RX board serial port (by-id path preferred)")
    ap.add_argument("--matrix", default=None, metavar="M1,M2,...",
                    help="comma list from {} — runs back-to-back per stop".format(
                        ",".join(MATRIX_KEYS)))
    ap.add_argument("--anchor", action=argparse.BooleanOptionalAction,
                    default=True,
                    help="include LEN=255 FLRC-650 comparability anchor cell "
                         "(default: on; --no-anchor to skip)")
    ap.add_argument("--csv", default=None,
                    help="append-only campaign CSV (one row per cell)")
    ap.add_argument("--freq", type=int, default=868000000,
                    help="Hz; 863-870 MHz EU SRD (LF path, hard clamp v1)")
    ap.add_argument("--dbm", type=int, default=10,
                    help="TX power dBm (firmware caps +10 indoor, "
                         "+22 requires POWER MODE OUTDOOR)")
    ap.add_argument("--n", type=int, default=1000,
                    help="single-shot packet count (default 1000)")
    ap.add_argument("--len", dest="length", type=int, default=255,
                    help="single-shot payload bytes 8-255 (default 255)")
    ap.add_argument("--gap", dest="gap_us", type=int, default=5000,
                    help="single-shot inter-packet gap us (default 5000)")
    ap.add_argument("--t0", default=None, metavar="'YYYY-MM-DD HH:MM:SS'",
                    help="sync point for schedule (plan §5); int epoch or "
                         "ISO T form also accepted")
    ap.add_argument("--dry-run", action="store_true",
                    help="print command script/schedule without opening ports")
    ap.add_argument("--rx-lead", type=int, default=10,
                    help="seconds RX arms before cell start (default 10)")
    ap.add_argument("--i-trust-clock", action="store_true",
                    help="proceed without NTP sync check (HS-6)")
    ap.add_argument("--site", default="?", help="campaign site name (CSV)")
    ap.add_argument("--stop", default="?", help="stop id S0..S5 (CSV)")
    ap.add_argument("--dist-m", dest="dist_m", default="?",
                    help="stop distance m (CSV)")
    ap.add_argument("--repeat", type=int, default=1,
                    help="repeat number 1-3 (CSV)")
    return ap


def main():
    """HS-1a scaffold: parse args, print summary. Full runner in HS-1b+."""
    ap = build_parser()
    args = ap.parse_args()

    if args.matrix:
        keys = [k.strip() for k in args.matrix.split(",") if k.strip()]
        bad = [k for k in keys if k not in MOD_DEFS]
        if bad:
            sys.exit("unknown --matrix entry(ies) {}; valid: {}".format(
                ",".join(bad), ",".join(MATRIX_KEYS)))
        args.matrix = keys

    print("== range_bench_ctl (HS-1a scaffold) ==")
    print("  freq:   {} Hz".format(args.freq))
    print("  dbm:    {}".format(args.dbm))
    if args.matrix:
        print("  matrix: {}".format(",".join(args.matrix)))
    print("  dry_run: {}".format(args.dry_run))
    print("  (full runner wired in HS-1b+)")
    return 0


if __name__ == "__main__":
    sys.exit(main())