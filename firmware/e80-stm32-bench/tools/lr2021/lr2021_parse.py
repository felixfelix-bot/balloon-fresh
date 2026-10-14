"""Pure parsing + plan constants for the E80/LR2021 console.

No I/O, no pyserial, no board -- importable by host tests on any interpreter.
Kept separate from the audit scripts so the testable logic never drags in a
serial dependency.
"""
import re

# E80_BENCH_OVERRIDE_PIN, from firmware/e80-stm32-bench/src/main.h:75
PIN = "2026"

# EU868 LoRaWAN: default join channels
DEFAULT_CHANNELS_HZ = [868100000, 868300000, 868500000]
# EU868 LoRaWAN: extra channels in the 867.1-867.9 sub-band (200 kHz raster)
EXTRA_CHANNELS_HZ = [867100000, 867300000, 867500000, 867700000, 867900000]
# EU868 LoRaWAN datarates: DR0=SF12 ... DR5=SF7, all at BW125 kHz
DR_TO_SF = {0: 12, 1: 11, 2: 10, 3: 9, 4: 8, 5: 7}

_ID_FIELDS = (
    ("role", r"role=(\w+)"),
    ("armed", r"armed=(\d)"),
    ("mod", r"mod=(\w+)"),
    ("bitrate_bps", r"br=(\d+)"),
    ("freq_hz", r"freq=(\d+)"),
    ("band", r"band=([\w\-()]+)"),
    ("pa_dbm", r"pa=(\d+)"),
    ("pcap", r"pcap=(\S+)"),
    ("chip", r"chip=([\d.]+)"),
    ("radio", r"radio=(\w+)"),
    ("boot", r"boot=(\S+)"),
    ("quiet", r"quiet=(\d)"),
)


def parse_id(resp):
    """Parse an `ID?` response into a dict. Never raises on partial input."""
    out = {}
    # Capture the version exactly as the board spells it ("v1.2"), so the value
    # can be compared against an ID? transcript without normalisation.
    m = re.search(r"ID\s+(\S+)\s+(v[\d.]+)\s+fw=(\w+)", resp or "")
    if m:
        out.update(board=m.group(1), fw_version=m.group(2), fw=m.group(3))
    for key, pat in _ID_FIELDS:
        m = re.search(pat, resp or "")
        if m:
            out[key] = m.group(1)
    return out


def parse_stat(resp):
    """Parse a `STAT?` response into its key=value pairs."""
    return dict(re.findall(r"(\w+)=(\S+)", resp or ""))


def accepted(resp):
    """A console command is accepted only if the board did not answer ERR."""
    r = (resp or "").strip()
    return bool(r) and not r.upper().startswith("ERR")
