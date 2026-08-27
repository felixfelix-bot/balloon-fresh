#!/usr/bin/env python3
"""balloon_sweep.py — cross-family host sweep tool (HARM-T2).

Generalizes firmware/e80-stm32-bench/tools/e80_sweep_full.py to all three
bench board families per docs/BENCH-CONSOLE-SPEC.md v1.0:

  Board families / tags (spec §2.1, §10):
    e80    E80BENCH    STM32F103 + CH340 ttyUSB, SWD reset via openocd
    esp32  ESP32BENCH  USB-CDC ttyACM, esptool hard reset
    rp2040 RP2040BENCH USB-CDC ttyACM, picotool reboot

  * ID? handshake with board-tag auto-detection
  * Shared LEN_CAP (lora 255 / flrc 511, spec §6) and per-board FREQ
    plan (spec §9) enforced host-side (spec §11.6): non-intersecting
    cross-board pairs are refused BEFORE any hardware is touched
  * Cross-board pair planner: TX from family A + RX from family B,
    same SESSION id
  * Sweep matrices, CSV columns and MD emission identical to the e80
    tool (tools/test_balloon_sweep.py pins parity) — including the
    2.4 GHz dual-band sections; those configs only run on pairs whose
    FREQ plans (spec §9) intersect on the 2.4 GHz band
  * ttyACM boards open through BoardSerial (tools/board-serial.py)
    so the BALLOON board lock + tracking stays enforced

Spec safety rules enforced here:
  §6  LEN <= 255 (LoRa) / <= 511 (FLRC)
  §7  LEN > 256 requires GAP >= 40 ms (2.4G note)
  §9  FREQ per board: E80 863-870 MHz only; ESP32 863-870 + 2400-2480;
      RP2040 863-870 + 2440 point
  §1  unknown console lines are ignored by every parser
"""

import abc
import argparse
import csv
import glob
import importlib.util
import json
import math
import os
import re
import subprocess
import sys
import time
from datetime import datetime

__version__ = "1.0.0"

HERE = os.path.dirname(os.path.abspath(__file__))

# ---------------------------------------------------------------------------
# Spec tables (docs/BENCH-CONSOLE-SPEC.md §6 §7 §9 §10)
# ---------------------------------------------------------------------------

BOARD_TAGS = {
    "e80": "E80BENCH",
    "esp32": "ESP32BENCH",
    "rp2040": "RP2040BENCH",
}

LEN_CAP = {
    "lora": 255,   # LoRa silicon cap (spec §6)
    "flrc": 511,   # FLRC fw cap (spec §6)
}

GAP_LARGE_BYTES = 256       # spec §7: LEN > 256 ...
GAP_LARGE_MIN_US = 40000    # ... requires GAP >= 40 ms

# Spec §9: per-board allowed bands (inclusive), MHz ranges.
FREQ_ALLOWED = {
    "E80BENCH":    [(863_000_000, 870_000_000)],
    "ESP32BENCH":  [(863_000_000, 870_000_000),
                    (2_400_000_000, 2_480_000_000)],
    "RP2040BENCH": [(863_000_000, 870_000_000),
                    (2_440_000_000, 2_440_000_000)],
}

_INT_RE = re.compile(r"^-?\d+$")


class ConfigError(ValueError):
    """A requested pair/config violates docs/BENCH-CONSOLE-SPEC.md."""


# ---------------------------------------------------------------------------
# Console-line parsers (spec §1: unknown lines -> None / ignored)
# ---------------------------------------------------------------------------

def parse_id_line(line):
    """Parse an ID? reply: ID <TAG> <ver> fw=<sha> k=v k=v ...

    Returns dict with tag/version/fw + kv keys (ints when numeric),
    or None if the line is not an ID reply. Optional keys (buf= on
    newer fw, boot= E80-only) are absent/None on older replies.
    """
    if not isinstance(line, str):
        return None
    parts = line.strip().split()
    if len(parts) < 4 or parts[0] != "ID":
        return None
    d = {"tag": parts[1], "version": parts[2]}
    for tok in parts[3:]:
        if "=" not in tok:
            continue
        k, v = tok.split("=", 1)
        if _INT_RE.match(v):
            d[k] = int(v)
        else:
            d[k] = v
    if "fw" not in d:
        return None
    d.setdefault("buf", None)
    d.setdefault("boot", None)
    return d


def parse_pkt(line):
    """Parse a PKT row; accepts 24-col (no pcrc16) and 25-col (pcrc16).

    Field layout (firmware bench_pkt.c):
      [0]PKT [1]session [2]config [3]replicate [4]pkt_idx [5]ts_ms
      [6]rssi_dbm [7]snr_db [8]crc_ok [9]bit_err [10]? [11]freq_hz
      [12]mod [13]sf|br [14]bw [15]cr [16]pa_dbm [17]len [18-23]0
      [24]pcrc16
    """
    if not isinstance(line, str) or not line.startswith("PKT,"):
        return None
    p = line.strip().split(",")
    if len(p) < 18:
        return None
    try:
        return {
            "session": int(p[1]), "config": int(p[2]), "replicate": int(p[3]),
            "idx": int(p[4]), "ts_ms": int(p[5]),
            "rssi": float(p[6]), "snr": float(p[7]), "crc_ok": int(p[8]),
            "bit_err": int(p[9]), "freq": int(p[11]), "mod": p[12],
            "sf": int(p[13]), "bw": int(p[14]), "cr": int(p[15]),
            "pa": int(p[16]), "pkt_len": int(p[17]),
            "pcrc16": int(p[24]) if len(p) > 24 else None,
        }
    except (ValueError, IndexError):
        return None


def parse_stat(line):
    """Parse a STAT line (spec §2.10), old and current shapes.

    per_ci_x1e6=[lo,hi] is split into per_ci_lo_x1e6/per_ci_hi_x1e6.
    A "recv" alias mirrors the rx= counter (both keys stay present).
    """
    if not isinstance(line, str):
        return {}
    d = {}
    for tok in line.split()[1:]:
        if "=" not in tok:
            continue
        k, v = tok.split("=", 1)
        if k == "per_ci_x1e6" and v.startswith("[") and v.endswith("]"):
            try:
                lo, hi = (int(x) for x in v[1:-1].split(","))
                d["per_ci_lo_x1e6"] = lo
                d["per_ci_hi_x1e6"] = hi
            except ValueError:
                pass
            continue
        try:
            d[k] = float(v) if "." in v else int(v)
        except ValueError:
            d[k] = v
    if "rx" in d:
        d["recv"] = d["rx"]
    return d


def parse_config_start(line):
    """Parse CONFIG_START,<config>,<replicate>,<ts_ms> (async marker)."""
    if not isinstance(line, str) or not line.startswith("CONFIG_START,"):
        return None
    p = line.strip().split(",")
    if len(p) != 4:
        return None
    try:
        return {"config": int(p[1]), "replicate": int(p[2]),
                "ts_ms": int(p[3])}
    except ValueError:
        return None


def replay(lines):
    """Replay console transcript lines -> structured events.

    Unknown/unrecognized lines are ignored (spec §1). Returns
    {"id":..., "pkts":[...], "stats":[...], "config_starts":[...],
     "replies":[...]} with events in transcript order.
    """
    out = {"id": None, "pkts": [], "stats": [], "config_starts": [],
           "replies": []}
    for line in lines:
        if not isinstance(line, str):
            continue
        s = line.strip()
        if not s:
            continue
        if s.startswith("PKT,"):
            p = parse_pkt(s)
            if p is not None:
                out["pkts"].append(p)
        elif s.startswith("STAT "):
            out["stats"].append(parse_stat(s))
        elif s.startswith("CONFIG_START,"):
            cs = parse_config_start(s)
            if cs is not None:
                out["config_starts"].append(cs)
        elif s.startswith("ID "):
            d = parse_id_line(s)
            if d is not None and out["id"] is None:
                out["id"] = d
        else:
            out["replies"].append(s)
    return out


# ---------------------------------------------------------------------------
# Spec §6/§7/§9 enforcement — pure functions, hardware-free
# ---------------------------------------------------------------------------

def freq_ok(tag, freq_hz):
    """True if freq_hz is inside any allowed band of the board tag."""
    for lo, hi in FREQ_ALLOWED.get(tag, []):
        if lo <= freq_hz <= hi:
            return True
    return False


def freq_pair_ok(tag_tx, tag_rx, freq_hz):
    """True if BOTH boards allow freq_hz (pair intersection, spec §9)."""
    return freq_ok(tag_tx, freq_hz) and freq_ok(tag_rx, freq_hz)


def validate_config(cfg, tx_tag, rx_tag):
    """Validate one sweep config against the console spec.

    Returns a list of human-readable error strings ([] = valid).
    Errors are prefixed LEN/GAP/FREQ for tooling.
    """
    errs = []
    mod = str(cfg.get("mod", "")).lower()
    plen = int(cfg.get("plen", 0))
    gap = int(cfg.get("gap", 0))
    freq = int(cfg.get("freq", 0))

    cap = LEN_CAP.get(mod)
    if cap is None:
        errs.append(f"MOD {mod!r} has no LEN cap table entry")
    elif plen > cap:
        errs.append(f"LEN {plen} > cap {cap} for {mod} (spec S6)")

    if plen > GAP_LARGE_BYTES and gap < GAP_LARGE_MIN_US:
        errs.append(f"GAP {gap}us < {GAP_LARGE_MIN_US}us required for "
                    f"LEN {plen} > {GAP_LARGE_BYTES} (spec S7)")

    if not freq_pair_ok(tx_tag, rx_tag, freq):
        errs.append(f"FREQ {freq} not allowed for pair {tx_tag}<->{rx_tag} "
                    f"(spec S9)")
    return errs


def validate_configs(cfgs, tx_tag, rx_tag):
    """Validate all configs; returns list of 'label: error' strings."""
    errs = []
    for i, cfg in enumerate(cfgs):
        for e in validate_config(cfg, tx_tag, rx_tag):
            errs.append(f"[{cfg.get('label', i)}] {e}")
    return errs


# ---------------------------------------------------------------------------
# Families / handshake (spec §2.1, §10)
# ---------------------------------------------------------------------------

def family_for_tag(tag):
    """Board tag -> family key ('e80'/...), or None if unknown."""
    for fam, t in BOARD_TAGS.items():
        if t == tag:
            return fam
    return None


def detect_family(id_line):
    """ID? reply line -> family key via board-tag auto-detection."""
    d = parse_id_line(id_line)
    if d is None:
        return None
    return family_for_tag(d["tag"])


# ---------------------------------------------------------------------------
# Board drivers (hardware paths; unit tests never instantiate ports)
# ---------------------------------------------------------------------------

def _udev_prop(dev):
    try:
        r = subprocess.run(["udevadm", "info", "-q", "property", "-n", dev],
                           capture_output=True, text=True, timeout=5)
        return r.stdout
    except Exception:
        return ""


def _import_board_serial():
    """Load BoardSerial from board-serial.py (module name has a hyphen)."""
    for cand in (os.path.join(HERE, "board-serial.py"),
                 os.path.expanduser("~/repos/balloon-fresh/tools/board-serial.py")):
        if os.path.exists(cand):
            spec = importlib.util.spec_from_file_location("board_serial", cand)
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            return mod
    raise ImportError("board-serial.py not found (BALLOON board lock "
                      "enforcement unavailable)")


class BoardDriver(abc.ABC):
    """One bench board family: detect ports, reset, open console."""

    family = None
    tag = None
    # udev ID_VENDOR_ID match for port detection
    vendor_id = None

    def detect_ports(self):
        """Return list of console device candidates for this family."""
        out = []
        for dev in sorted(self._candidate_devs()):
            if self._dev_matches(dev):
                out.append(dev)
        return out

    @abc.abstractmethod
    def _candidate_devs(self):
        ...

    @abc.abstractmethod
    def _dev_matches(self, dev):
        ...

    @abc.abstractmethod
    def reset(self, port):
        """Reset the board hanging off `port` (SWD/esptool/picotool)."""

    @abc.abstractmethod
    def open(self, port, baud=115200):
        """Open the console (BoardSerial for ttyACM, pyserial otherwise)."""


class E80Driver(BoardDriver):
    """E80BENCH: STM32F103, CH340 ttyUSB console, openocd SWD reset."""

    family = "e80"
    tag = "E80BENCH"
    # Known CMSIS-DAP probe serials (from e80_sweep_full.py) keyed by role.
    default_probes = ("148757200D2D1425", "203584200D2D0D42")

    def _candidate_devs(self):
        return glob.glob("/dev/ttyUSB*")

    def _dev_matches(self, dev):
        return "CH340" in _udev_prop(dev)

    def reset(self, port, probe_serial=None):
        """SWD reset (reset halt; resume). Needs the board's probe serial;
        without one we can only reopen (CH340 has no remote reset line)."""
        if probe_serial is None:
            # Unknown mapping: try the two known probes (only 2 E80 boards
            # exist on the bench; hitting the wrong one is harmless because
            # both boards get SWD-reset anyway during a sweep).
            probe_serial = self.default_probes[0]
        subprocess.run(
            ["/usr/bin/openocd", "-f", "interface/cmsis-dap.cfg",
             "-f", "target/stm32f1x.cfg",
             "-c", f"transport select swd; adapter serial {probe_serial}; "
                   f"init; reset halt; resume; exit"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            timeout=30)
        time.sleep(2.0)

    def open(self, port, baud=115200):
        import serial
        return serial.Serial(port, baud, timeout=0.1)


class ESP32Driver(BoardDriver):
    """ESP32BENCH: native USB-CDC ttyACM, esptool hard reset."""

    family = "esp32"
    tag = "ESP32BENCH"
    vendor_id = "303a"          # Espressif native USB
    fallback_vendor_id = "10c4"  # CP210x bridge variant

    def _candidate_devs(self):
        return glob.glob("/dev/ttyACM*")

    def _dev_matches(self, dev):
        prop = _udev_prop(dev)
        return (f"ID_VENDOR_ID={self.vendor_id}" in prop
                or f"ID_VENDOR_ID={self.fallback_vendor_id}" in prop)

    def reset(self, port):
        """esptool chip reset (default_reset + hard_reset)."""
        subprocess.run(
            ["esptool", "--port", port, "--before", "default_reset",
             "--after", "hard_reset", "chip-id"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=30)
        time.sleep(1.5)

    def open(self, port, baud=115200):
        bs = _import_board_serial()
        return bs.BoardSerial(port, baud, timeout=0.1)


class RP2040Driver(BoardDriver):
    """RP2040BENCH: USB-CDC ttyACM, picotool reboot."""

    family = "rp2040"
    tag = "RP2040BENCH"
    vendor_id = "2e8a"          # Raspberry Pi

    def _candidate_devs(self):
        return glob.glob("/dev/ttyACM*")

    def _dev_matches(self, dev):
        return f"ID_VENDOR_ID={self.vendor_id}" in _udev_prop(dev)

    def reset(self, port):
        """picotool force reboot (reruns flash image)."""
        subprocess.run(
            ["picotool", "reboot", "-f", "-u"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=30)
        time.sleep(2.0)

    def open(self, port, baud=115200):
        bs = _import_board_serial()
        return bs.BoardSerial(port, baud, timeout=0.1)


DRIVERS = {
    "e80": E80Driver(),
    "esp32": ESP32Driver(),
    "rp2040": RP2040Driver(),
}


# ---------------------------------------------------------------------------
# Sweep matrices — IDENTICAL to e80_sweep_full.py (pinned by unit tests)
# ---------------------------------------------------------------------------

DEFAULT_FREQ = 868000000

LORA_SFS = [5, 6, 7, 8, 9, 10, 11, 12]
LORA_BWS = [125, 250, 500]
FLRC_BRS = [260, 325, 520, 650, 1040, 1300, 2080, 2600]  # kbps (1000 invalid)
FLRC_PAS = [0, 1, 3, 5, 7, 10]
PA_SWEEP = [0, 3, 6, 10]
LEN_SWEEP = [16, 64, 128, 255, 511]
FREQ_SWEEP = [863000000, 865000000, 868000000, 869525000, 870000000]

# 2.4 GHz ISM band (e80_sweep_full dual-band matrices; on the e80 pair
# these need fw 0561b29 BAND OVERRIDE + HF path — here they are gated by
# the per-board FREQ plan, spec §9: plan_pairs refuses any pair whose
# boards do not BOTH allow the frequency, before any hardware is touched).
FREQ_2G4_SWEEP = [2400000000, 2420000000, 2440000000, 2460000000, 2480000000]
DEFAULT_FREQ_2G4 = 2440000000


def lora_airtime_s(sf, bw_khz, plen):
    """Standard LoRa airtime: preamble 8, CR 4/5, explicit hdr, CRC on.

    Byte-identical to e80_sweep_full.lora_airtime_s (parity pinned by test).
    """
    bw = bw_khz * 1000
    t_sym = (2 ** sf) / bw
    num = 8 * plen - 4 * sf + 28 + 16
    den = 4 * (sf - 2 * 0)
    payload_symb = 8 + max(math.ceil(num / den) * (1 + 4), 0)
    return (8 + 4.25 + payload_symb) * t_sym


def flrc_airtime_s(br_kbps, plen):
    """FLRC rough airtime: preamble+sync ~7B, 4/5 FEC, CRC.

    Byte-identical to e80_sweep_full.flrc_airtime_s (parity pinned by test).
    """
    return (plen + 7) * 8 / (br_kbps * 1000) * 1.5 + 0.001


def build_configs():
    """Sweep matrices — byte-identical to e80_sweep_full.build_configs()."""
    cfgs = []
    # A. LoRa SF x BW matrix @ PA10, LEN64, 868MHz
    for bw in LORA_BWS:
        for sf in LORA_SFS:
            toa = lora_airtime_s(sf, bw, 64)
            gap = max(10000, int(1.2 * toa * 1e6) + 5000)
            cfgs.append(dict(mod="lora", sf=sf, bw=bw, pa=10, freq=DEFAULT_FREQ,
                             plen=64, gap=gap, label=f"SF{sf} BW{bw} PA10"))
    # B. LoRa PA sweep @ SF8 BW125 LEN64
    for pa in PA_SWEEP:
        if pa == 10:
            continue  # in matrix
        toa = lora_airtime_s(8, 125, 64)
        gap = max(10000, int(1.2 * toa * 1e6) + 5000)
        cfgs.append(dict(mod="lora", sf=8, bw=125, pa=pa, freq=DEFAULT_FREQ,
                         plen=64, gap=gap, label=f"SF8 BW125 PA{pa}"))
    # C. LEN sweep @ SF8 BW125 PA10
    for plen in LEN_SWEEP:
        if plen == 64:
            continue  # in matrix
        if plen > LEN_CAP["lora"]:
            continue  # LR2021 LoRa 8-bit length field: max 255 (L511 is
                      # FLRC-only; generates misleading 100% PER in LoRa)
        toa = lora_airtime_s(8, 125, plen)
        gap = max(10000, int(1.2 * toa * 1e6) + 5000)
        cfgs.append(dict(mod="lora", sf=8, bw=125, pa=10, freq=DEFAULT_FREQ,
                         plen=plen, gap=gap, label=f"SF8 BW125 PA10 L{plen}"))
    # D. FLRC BR sweep @ pa5
    for br in FLRC_BRS:
        cfgs.append(dict(mod="flrc", br=br, pa=5, freq=DEFAULT_FREQ,
                         plen=64, gap=10000, label=f"FLRC {br}k pa5"))
    # E. FLRC pa sweep @ BR650
    for pa in FLRC_PAS:
        if pa == 5:
            continue  # in D
        cfgs.append(dict(mod="flrc", br=650, pa=pa, freq=DEFAULT_FREQ,
                         plen=64, gap=10000, label=f"FLRC 650k pa{pa}"))
    # F. FREQ sweep @ SF8 BW125 PA10 (868 in matrix)
    for f in FREQ_SWEEP:
        if f == DEFAULT_FREQ:
            continue
        toa = lora_airtime_s(8, 125, 64)
        gap = max(10000, int(1.2 * toa * 1e6) + 5000)
        cfgs.append(dict(mod="lora", sf=8, bw=125, pa=10, freq=f,
                         plen=64, gap=gap, label=f"SF8 BW125 @ {f/1e6:.3f}MHz"))
    # G. FLRC LEN matrix @ BR650 pa5 — large-packet coverage (operator
    #    priority 2026-08-21; 511 = FLRC fw max, LoRa cap is 255). gap 40ms
    #    per spec S7 (console pressure headroom at 115200 baud).
    FLRC_LEN_MATRIX = [16, 64, 128, 192, 255, 256, 300, 384, 448, 511]
    for plen in FLRC_LEN_MATRIX:
        cfgs.append(dict(mod="flrc", br=650, pa=5, freq=DEFAULT_FREQ,
                         plen=plen, gap=40000,
                         label=f"FLRC 650k pa5 L{plen}"))
    # G2. large-packet x BR interaction (does 511 hold at higher BR?)
    for br, plen in ((1300, 384), (1300, 511), (2600, 511)):
        cfgs.append(dict(mod="flrc", br=br, pa=5, freq=DEFAULT_FREQ,
                         plen=plen, gap=40000,
                         label=f"FLRC {br}k pa5 L{plen}"))
    # ================= 2.4 GHz ISM band (e80_sweep_full dual-band port) =====
    # Matrices byte-identical to e80_sweep_full (spec §11.6 parity, pinned
    # by E80ParityTests). FREQ-plan gating per spec §9 happens in
    # plan_pairs: e.g. E80BENCH pairs (863-870 only) and RP2040 pairs
    # (2440 point only) are refused pre-hardware unless configs are
    # filtered to the pair's allowed band intersection.
    # G-2G4. LoRa SF x BW matrix @ 2440 MHz PA10 LEN64 (24 configs)
    for bw in LORA_BWS:
        for sf in LORA_SFS:
            toa = lora_airtime_s(sf, bw, 64)
            gap = max(10000, int(1.2 * toa * 1e6) + 5000)
            cfgs.append(dict(mod="lora", sf=sf, bw=bw, pa=10,
                             freq=DEFAULT_FREQ_2G4, plen=64, gap=gap,
                             label=f"2G4 SF{sf} BW{bw} PA10"))
    # H-2G4. LoRa PA sweep @ SF8 BW125 2440 MHz (4 configs; PA10 replicates
    # the matrix center for cross-section consistency check)
    for pa in PA_SWEEP:
        toa = lora_airtime_s(8, 125, 64)
        gap = max(10000, int(1.2 * toa * 1e6) + 5000)
        cfgs.append(dict(mod="lora", sf=8, bw=125, pa=pa,
                         freq=DEFAULT_FREQ_2G4, plen=64, gap=gap,
                         label=f"2G4 SF8 BW125 PA{pa}"))
    # I-2G4. LoRa LEN sweep @ SF8 BW125 PA10 2440 MHz. L511 filtered: the
    # LR2021 LoRa 8-bit length field caps at 255 bytes — L511 in LoRa is
    # untestable and was previously showing as misleading 100% PER.
    for plen in LEN_SWEEP:
        if plen > LEN_CAP["lora"]:
            continue
        toa = lora_airtime_s(8, 125, plen)
        gap = max(10000, int(1.2 * toa * 1e6) + 5000)
        cfgs.append(dict(mod="lora", sf=8, bw=125, pa=10,
                         freq=DEFAULT_FREQ_2G4, plen=plen, gap=gap,
                         label=f"2G4 SF8 BW125 PA10 L{plen}"))
    # J-2G4. FLRC BR sweep @ 2440 MHz pa5 (8 configs). gap floor 10 ms holds
    # for the shortest airtime (2600k: ~1.3 ms for 64 B) — min gap is the
    # binding constraint, exactly as on 868 MHz.
    for br in FLRC_BRS:
        cfgs.append(dict(mod="flrc", br=br, pa=5, freq=DEFAULT_FREQ_2G4,
                         plen=64, gap=10000, label=f"2G4 FLRC {br}k pa5"))
    # K-2G4. FLRC PA sweep @ 650k 2440 MHz (6 configs; pa5 replicates J)
    for pa in FLRC_PAS:
        cfgs.append(dict(mod="flrc", br=650, pa=pa, freq=DEFAULT_FREQ_2G4,
                         plen=64, gap=10000, label=f"2G4 FLRC 650k pa{pa}"))
    # L-2G4. FREQ sweep @ SF8 BW125 PA10 across 2.4 GHz points (5 configs;
    # 2440 replicates the matrix center)
    for f in FREQ_2G4_SWEEP:
        toa = lora_airtime_s(8, 125, 64)
        gap = max(10000, int(1.2 * toa * 1e6) + 5000)
        cfgs.append(dict(mod="lora", sf=8, bw=125, pa=10, freq=f,
                         plen=64, gap=gap, label=f"2G4 SF8 BW125 @ {f/1e6:.0f}MHz"))
    return cfgs


SUMMARY_FIELDS = ["idx", "label", "mod", "sf", "bw", "br", "pa", "freq", "plen",
                  "gap_us", "toa_s", "dur_s", "rx_pkts", "crc_err", "rssi_avg",
                  "rssi_min", "rssi_max", "snr_avg", "snr_min", "bit_err_total",
                  "tx_done", "error"]
PKT_FIELDS = ["idx", "label", "pkt_idx", "session", "config", "replicate",
              "ts_ms", "rssi_dbm", "snr_db", "crc_ok", "bit_err", "pcrc16"]


def pkt_row(meta, pkt):
    """Parsed PKT -> PKT_FIELDS row (meta carries idx/label of the config).

    Join keys for cross-board/cross-run analysis: session, config, pkt_idx.
    """
    return [
        meta.get("idx", ""),
        meta.get("label", ""),
        pkt.get("idx", ""),
        pkt.get("session", ""),
        pkt.get("config", ""),
        pkt.get("replicate", ""),
        pkt.get("ts_ms", ""),
        pkt.get("rssi", ""),
        pkt.get("snr", ""),
        pkt.get("crc_ok", ""),
        pkt.get("bit_err", ""),
        "" if pkt.get("pcrc16") is None else pkt["pcrc16"],
    ]


def new_session_id():
    """yymmddHHMM session id (same scheme as the e80 tool)."""
    return int(datetime.now().strftime("%y%m%d%H%M"))


# ---------------------------------------------------------------------------
# Pair planner
# ---------------------------------------------------------------------------

class PlannedPair:
    """A validated cross-board sweep plan (TX family A -> RX family B)."""

    def __init__(self, tx_family, rx_family, configs, session_id):
        self.tx_family = tx_family
        self.rx_family = rx_family
        self.configs = configs
        self.session_id = session_id

    @property
    def tx_tag(self):
        return BOARD_TAGS[self.tx_family]

    @property
    def rx_tag(self):
        return BOARD_TAGS[self.rx_family]

    def __repr__(self):
        return (f"PlannedPair(tx={self.tx_family}/{self.tx_tag}, "
                f"rx={self.rx_family}/{self.rx_tag}, "
                f"session={self.session_id}, configs={len(self.configs)})")


def plan_pairs(tx_family, rx_family, configs=None, session_id=None):
    """Validate a cross-board pair against the spec BEFORE any hardware.

    Raises ConfigError (with all LEN/GAP/FREQ reasons) on violation;
    returns a PlannedPair with one shared SESSION id otherwise.
    """
    for fam in (tx_family, rx_family):
        if fam not in DRIVERS:
            raise ConfigError(
                f"unknown board family {fam!r} "
                f"(known: {sorted(DRIVERS)})")
    tx_tag, rx_tag = BOARD_TAGS[tx_family], BOARD_TAGS[rx_family]
    if configs is None:
        configs = build_configs()
    errs = validate_configs(configs, tx_tag, rx_tag)
    if errs:
        raise ConfigError("; ".join(errs))
    if session_id is None:
        session_id = new_session_id()
    return PlannedPair(tx_family, rx_family, configs, session_id)


# ---------------------------------------------------------------------------
# Console I/O (works over pyserial and BoardSerial — same duck-typed API)
# ---------------------------------------------------------------------------

def readline(ser, timeout=3.0):
    deadline = time.monotonic() + timeout
    buf = bytearray()
    while time.monotonic() < deadline:
        chunk = ser.read(256)
        if chunk:
            buf += chunk
            while b"\n" in buf:
                line, buf = buf.split(b"\n", 1)
                txt = line.rstrip(b"\r").decode(errors="replace").strip()
                if txt:
                    return txt
    return None


def cmd(ser, line, timeout=5.0):
    for _ in range(2):
        ser.reset_input_buffer()
        ser.write((line + "\r\n").encode())
        r = readline(ser, timeout)
        if r:
            return r
        time.sleep(0.5)
    return None


def drain_lines(ser, seconds):
    out = []
    deadline = time.monotonic() + seconds
    leftover = bytearray()
    while time.monotonic() < deadline:
        chunk = ser.read(1024)
        if chunk:
            leftover += chunk
            while b"\n" in leftover:
                line, leftover = leftover.split(b"\n", 1)
                txt = line.rstrip(b"\r").decode(errors="replace").strip()
                if txt:
                    out.append(txt)
    return out


def handshake(ser, family, retries=2):
    """ID? handshake with board-tag auto-detection (spec §2.1/§10).

    Returns the parsed ID dict; raises RuntimeError on tag mismatch or
    unresponsive console.
    """
    expected = BOARD_TAGS[family]
    for attempt in range(retries + 1):
        ser.reset_input_buffer()
        ser.write(b"ID?\r\n")
        r = readline(ser, 3.0)
        d = parse_id_line(r) if r else None
        if d and d["tag"] == expected:
            return d
        if d and d["tag"] != expected:
            # Board answered but is the wrong family — hard error, do not
            # radio-probe a foreign board.
            raise RuntimeError(
                f"tag mismatch: expected {expected}, board answered "
                f"{d['tag']} (fw={d.get('fw')})")
        time.sleep(1.0)
    raise RuntimeError(f"{expected} handshake failed after {retries + 1} tries")


# ---------------------------------------------------------------------------
# Sweep runner (hardware path — exercised only with real boards attached)
# ---------------------------------------------------------------------------

NPKTS = 50


def run_config(idx, cfg, tx, rx, session_id, tx_driver=None, rx_driver=None):
    """Run one config across the opened TX/RX consoles.

    Mirrors e80_sweep_full.run_config, but board-agnostic: optional
    drivers give reset capability; LEN/FREQ were already validated by
    plan_pairs (spec S6/S7/S9 enforcement happens pre-hardware).
    """
    mod = cfg["mod"]
    # Wall-clock timing: from reset start to last packet drain (same
    # instrumentation as e80_sweep_full; feeds the dur_s summary column).
    t_cfg_start = time.monotonic()
    cfg_t_start_iso = datetime.now().isoformat()
    if tx_driver is not None:
        tx_driver.reset(cfg.get("_tx_port", ""))
    if rx_driver is not None:
        rx_driver.reset(cfg.get("_rx_port", ""))

    cmd(tx, f"SESSION {session_id}")
    cmd(rx, f"SESSION {session_id}")
    cmd(tx, f"CONFIG {idx} 1")
    cmd(rx, f"CONFIG {idx} 1")

    if mod == "lora":
        m = f"MOD LORA {cfg['sf']} {cfg['bw']}"
    else:
        m = f"MOD FLRC {cfg['br']} {cfg['pa']}"
    for s, label in [(rx, "RX"), (tx, "TX")]:
        r = cmd(s, m)
        if not r or not r.startswith("OK MOD"):
            raise RuntimeError(f"{label} MOD: {r!r}")
        if mod == "lora":
            r = cmd(s, f"PA {cfg['pa']}")
            if not r or not r.startswith("OK PA"):
                raise RuntimeError(f"{label} PA: {r!r}")
        r = cmd(s, f"FREQ {cfg['freq']}")
        if not r or not r.startswith("OK FREQ"):
            raise RuntimeError(f"{label} FREQ: {r!r}")

    r = cmd(rx, "ROLE RX")
    if not r or not r.startswith("OK ROLE RX"):
        raise RuntimeError(f"RX ROLE: {r!r}")
    r = cmd(tx, "ROLE TX")
    if not r or not r.startswith("OK ROLE TX"):
        raise RuntimeError(f"TX ROLE: {r!r}")
    r = cmd(tx, "ARM TX")
    if not r or not r.startswith("OK ARMED"):
        raise RuntimeError(f"TX ARM: {r!r}")

    rx.reset_input_buffer()
    tx.write(f"START N={NPKTS} LEN={cfg['plen']} GAP={cfg['gap']}\r\n".encode())
    start_reply = readline(tx, 3.0)

    if mod == "lora":
        toa = lora_airtime_s(cfg["sf"], cfg["bw"], cfg["plen"])
    else:
        toa = flrc_airtime_s(cfg["br"], cfg["plen"])
    wait_s = NPKTS * (toa + cfg["gap"] / 1e6) + 8

    tx_lines = drain_lines(tx, wait_s)
    rx_lines = drain_lines(rx, 5)
    tx_done = any("TX DONE" in l for l in tx_lines)

    stat = cmd(rx, "STAT?")
    sd = parse_stat(stat) if stat else {}
    t_cfg_end = time.monotonic()
    cfg_t_end_iso = datetime.now().isoformat()

    pkts = [p for p in (parse_pkt(l) for l in rx_lines) if p is not None]
    rssi = [p["rssi"] for p in pkts]
    snr = [p["snr"] for p in pkts]

    return {
        "idx": idx, "label": cfg["label"], "mod": mod,
        "sf": cfg.get("sf", ""), "bw": cfg.get("bw", ""),
        "br": cfg.get("br", ""), "pa": cfg["pa"], "freq": cfg["freq"],
        "plen": cfg["plen"], "gap_us": cfg["gap"], "toa_s": round(toa, 3),
        "dur_s": round(t_cfg_end - t_cfg_start, 3),
        "cfg_t_start": cfg_t_start_iso, "cfg_t_end": cfg_t_end_iso,
        "rx_pkts": len(pkts), "crc_err": sd.get("crc_err", 0),
        "rssi_avg": round(sum(rssi) / len(rssi), 1) if rssi else None,
        "rssi_min": round(min(rssi), 1) if rssi else None,
        "rssi_max": round(max(rssi), 1) if rssi else None,
        "snr_avg": round(sum(snr) / len(snr), 1) if snr else None,
        "snr_min": round(min(snr), 1) if snr else None,
        "bit_err_total": sum(p["bit_err"] for p in pkts),
        "tx_done": tx_done, "start_reply": start_reply, "pkts": pkts,
        "stat": sd,
    }


def _summary_row(rec, err=""):
    return [rec.get(k, "") for k in SUMMARY_FIELDS[:-1]] + [err]


def write_meta(path, plan, args_meta):
    meta = {
        "tool": "balloon_sweep.py", "version": __version__,
        "spec": "docs/BENCH-CONSOLE-SPEC.md v1.0",
        "tx_family": plan.tx_family, "rx_family": plan.rx_family,
        "tx_tag": plan.tx_tag, "rx_tag": plan.rx_tag,
        "session": plan.session_id, "configs": len(plan.configs),
        "started": datetime.now().isoformat(timespec="seconds"),
    }
    meta.update(args_meta or {})
    with open(path, "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2)


def write_report_md(path, plan, records):
    lines = [
        "# balloon_sweep cross-board run", "",
        f"- tx: `{plan.tx_family}` ({plan.tx_tag})  rx: `{plan.rx_family}` "
        f"({plan.rx_tag})", f"- session: {plan.session_id}",
        f"- configs: {len(plan.configs)}", "",
        "| # | label | rx_pkts | crc_err | rssi_avg | tx_done |",
        "|---|-------|---------|---------|----------|---------|",
    ]
    for r in records:
        lines.append(
            f"| {r['idx']} | {r['label']} | {r.get('rx_pkts', '')} "
            f"| {r.get('crc_err', '')} | {r.get('rssi_avg', '')} "
            f"| {r.get('tx_done', '')} |")
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")


def main(argv=None):
    ap = argparse.ArgumentParser(
        description="Cross-family balloon bench sweep (spec: "
                    "docs/BENCH-CONSOLE-SPEC.md)")
    ap.add_argument("--tx", required=True, choices=sorted(DRIVERS),
                    help="TX board family")
    ap.add_argument("--rx", required=True, choices=sorted(DRIVERS),
                    help="RX board family")
    ap.add_argument("--tx-port")
    ap.add_argument("--rx-port")
    ap.add_argument("--tx-probe", help="e80 TX SWD probe serial")
    ap.add_argument("--rx-probe", help="e80 RX SWD probe serial")
    ap.add_argument("--session", type=int)
    ap.add_argument("--only", type=int, nargs="*", metavar="IDX",
                    help="run only these config indexes")
    ap.add_argument("--out-prefix",
                    default=os.path.join(os.getcwd(), "balloon-sweep"))
    ap.add_argument("--dry-run", action="store_true",
                    help="validate the pair + configs and exit (no hardware)")
    args = ap.parse_args(argv)

    configs = build_configs()
    if args.only:
        configs = [c for i, c in enumerate(build_configs())
                   if i in set(args.only)]

    # Spec enforcement happens HERE, before any port is opened (S11.6).
    try:
        plan = plan_pairs(args.tx, args.rx, configs, args.session)
    except ConfigError as e:
        print(f"REFUSED (pre-hardware, spec enforcement): {e}", file=sys.stderr)
        return 2

    print(f"plan OK: {plan}")
    if args.dry_run:
        return 0

    tx_drv, rx_drv = DRIVERS[args.tx], DRIVERS[args.rx]
    tx_port = args.tx_port
    rx_port = args.rx_port
    if tx_port is None:
        cands = tx_drv.detect_ports()
        if not cands:
            print(f"no {args.tx} console ports found", file=sys.stderr)
            return 3
        tx_port = cands[0]
    if rx_port is None:
        cands = [p for p in rx_drv.detect_ports() if p != tx_port] or \
                rx_drv.detect_ports()
        rx_port = cands[0]
    print(f"tx={tx_port} rx={rx_port}")

    tx, rx = tx_drv.open(tx_port), rx_drv.open(rx_port)
    try:
        id_tx = handshake(tx, plan.tx_family)
        id_rx = handshake(rx, plan.rx_family)
        print(f"tx fw={id_tx.get('fw')} rx fw={id_rx.get('fw')}")

        sum_path = f"{args.out_prefix}-summary.csv"
        pkt_path = f"{args.out_prefix}-pkts.csv"
        with open(sum_path, "w", newline="", encoding="utf-8") as sum_f, \
                open(pkt_path, "w", newline="", encoding="utf-8") as pkt_f:
            sum_w = csv.writer(sum_f)
            sum_w.writerow(SUMMARY_FIELDS)
            sum_f.flush()
            pkt_w = csv.writer(pkt_f)
            pkt_w.writerow(PKT_FIELDS)
            pkt_f.flush()

            records = []
            base = 0 if not args.only else min(args.only)
            for i, cfg in enumerate(configs):
                idx = i if not args.only else args.only[i]
                cfg = dict(cfg)
                cfg["_tx_port"], cfg["_rx_port"] = tx_port, rx_port
                try:
                    rec = run_config(idx, cfg, tx, rx, plan.session_id)
                    records.append(rec)
                    sum_w.writerow(_summary_row(rec))
                    for p in rec["pkts"]:
                        pkt_w.writerow(
                            pkt_row({"idx": idx, "label": cfg["label"]}, p))
                    err = ""
                except Exception as e:  # noqa: BLE001 — record and continue
                    rec = {"idx": idx, "label": cfg["label"],
                           "mod": cfg["mod"]}
                    records.append(rec)
                    sum_w.writerow(_summary_row(rec, str(e)[:60]))
                    err = str(e)[:60]
                sum_f.flush()
                pkt_f.flush()
                print(f"[{idx}] {cfg['label']} -> "
                      f"rx={rec.get('rx_pkts', '?')} "
                      f"{'ERR ' + err if err else 'ok'}")
        write_meta(f"{args.out_prefix}-meta.json", plan,
                   {"tx_port": tx_port, "rx_port": rx_port,
                    "npkts": NPKTS})
        write_report_md(f"{args.out_prefix}-report.md", plan, records)
        print(f"wrote {args.out_prefix}-summary.csv / -pkts.csv / "
              f"-meta.json / -report.md")
    finally:
        try:
            tx.close()
        except Exception:
            pass
        try:
            rx.close()
        except Exception:
            pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
