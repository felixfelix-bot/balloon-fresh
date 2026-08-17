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
    Matrix cells, schedule, freq_gate, parse_stat, CsvLog, BoardSerial,
    session runner, and dry-run arrive in HS-1b / HS-2+.

Usage (scaffold — full CLI wired in HS-1b+):
    python3 tools/range_bench_ctl.py --dry-run --matrix flrc650,sf7
"""
import argparse
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
    "flrc650":  dict(kind="flrc", mod_lines=["MOD FLRC 650 {dbm}"],
                     gap_us=5000, label="FLRC-650"),
    "flrc2600": dict(kind="flrc", mod_lines=["MOD FLRC 2600 {dbm}"],
                     gap_us=5000, label="FLRC-2600"),
    "sf7":      dict(kind="lora", mod_lines=["MOD LORA 7 125", "PA {dbm}"],
                     gap_us=1000, label="LoRa-SF7"),
    "sf12":     dict(kind="lora", mod_lines=["MOD LORA 12 125", "PA {dbm}"],
                     gap_us=1000, label="LoRa-SF12"),
}
MATRIX_KEYS = ["flrc650", "flrc2600", "sf7", "sf12"]

N_HI_DEFAULT = 10_000             # S0 / low-PER regime (plan §3)
N_LO_DEFAULT = 1_000              # high-PER edge regime
N_SF12_CAP = 1_000                # SF12 time cap (10^4 would be ~7 h/cell)
ANCHOR_KEY = "flrc650"
ANCHOR_LEN = 255
MATRIX_LEN = 51
CI_HI_NHI_PCT = 2.0               # Wilson ci_hi threshold for the 10^4 regime

# FLRC bitrate lookup (bps) — keyed by mod name.
_FLRC_BR = {"flrc650": 650_000, "flrc2600": 2_600_000}

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