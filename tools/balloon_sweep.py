#!/usr/bin/env python3
"""balloon_sweep.py — cross-family host sweep tool (HARM-T2, RED stub).

Generalizes e80_sweep_full.py to all three bench board families
(E80 / ESP32 / RP2040) per docs/BENCH-CONSOLE-SPEC.md v1.0:

  * BoardDriver per family: port detection, reset, console open
  * ID? handshake with board-tag auto-detection (E80BENCH/...)
  * Shared LEN_CAP + per-board FREQ_ALLOWED (refuses non-intersecting
    cross-board pairs BEFORE any hardware is touched)
  * Cross-board pair planner: TX family A + RX family B, same SESSION
  * Sweep matrices / CSV / MD emission identical to the e80 tool

This is the TDD RED stub: importable, zero logic. All functions return
None / empty; constants deliberately wrong. Tests must FAIL.
"""

__version__ = "0.0.0-red"

BOARD_TAGS = {}
FREQ_ALLOWED = {}
LEN_CAP = {}
GAP_LARGE_BYTES = 0
GAP_LARGE_MIN_US = 0


class ConfigError(ValueError):
    """Raised when a requested pair/config violates the console spec."""


def parse_id_line(line):
    return None


def parse_pkt(line):
    return None


def parse_stat(line):
    return {}


def parse_config_start(line):
    return None


def freq_ok(tag, freq_hz):
    return None


def freq_pair_ok(tag_tx, tag_rx, freq_hz):
    return None


def validate_config(cfg, tx_tag, rx_tag):
    return None


def validate_configs(cfgs, tx_tag, rx_tag):
    return None


def family_for_tag(tag):
    return None


def detect_family(id_line):
    return None


class BoardDriver:
    family = None
    tag = None

    def detect_ports(self):
        return None

    def reset(self, port):
        return None

    def open(self, port, baud=115200):
        return None


class E80Driver(BoardDriver):
    pass


class ESP32Driver(BoardDriver):
    pass


class RP2040Driver(BoardDriver):
    pass


DRIVERS = {}


def build_configs():
    return None


SUMMARY_FIELDS = []
PKT_FIELDS = []


def pkt_row(meta, pkt):
    return None


def replay(lines):
    return None


def new_session_id():
    return None


class PlannedPair:
    tx_family = None
    rx_family = None
    session_id = None
    configs = None


def plan_pairs(tx_family, rx_family, configs=None, session_id=None):
    return None


def main(argv=None):
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
