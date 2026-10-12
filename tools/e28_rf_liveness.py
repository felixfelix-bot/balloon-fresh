#!/usr/bin/env python3
"""Cross-board RF liveness test for two LILYGO T3S3 + E28-2G4M27S (SX1280/SX1282)
boards running the `esp32-e28-range` console firmware.

WHY THIS EXISTS
---------------
Ranging (RANGE / RANGE-SLAVE) returns 0/N exchanges on BOTH our firmware and
LILYGO's vendor example. With two independent software stacks failing the same
way, the remaining suspect is the RF chain (PA / front-end switch / antenna
path), not the code. This tool asks the simplest possible question, with no
ranging involved:

    when board A transmits a packet, does board B's radio see a rise in
    received energy?

It does that with two existing firmware commands:
  * TXPROBE -> transmits ONE 12-byte packet at the current power, no IRQ wait
  * RSSI?   -> RECEIVE-ONLY probe; prints the instantaneous RSSI register
               (`inst=`), which is ambient RF energy and needs no packet decode.

A rise in `inst` WITHOUT a `lora-preamble` scan state means energy is present
but the packet is not being decoded. A rise WITH `lora-preamble` means the
packet is actually being seen. The tool reports which one happened.

SAFETY
------
  * Minimum power first (PA -18 dBm). Power is only escalated in the defined
    staircase (phase 4), only when phases 2/3 detected nothing, and never
    above the firmware's +10 dBm indoor cap.
  * Every phase ends with no TXPROBE loop running.
  * Final state is always role=idle, PA -18 on both boards.
  * Ports are opened with dtr=False, rts=False. Asserting DTR parks these
    ESP32-S3 boards in ROM mode and wastes the run.

USAGE
-----
    python3 tools/e28_rf_liveness.py \
        --port-a /dev/serial/by-id/usb-Espressif_USB_JTAG_..._9C:13:9E:F1:0C:28-if00 \
        --port-b /dev/serial/by-id/usb-Espressif_USB_JTAG_..._9C:13:9E:F1:0C:60-if00

Writes a raw timestamped transcript to captures/e28-rf-liveness-<UTC>.log and
the parsed numbers next to it as captures/e28-rf-liveness-<UTC>.json.
"""

from __future__ import annotations

import argparse
import datetime as _dt
import glob
import json
import os
import re
import statistics
import subprocess
import sys
import time

try:
    import serial  # pyserial
except ImportError:  # pragma: no cover
    sys.stderr.write("ERROR: pyserial is required (pip install pyserial)\n")
    sys.exit(2)

# ---------------------------------------------------------------------------
# Test constants (all from the task spec — do not tune silently)
# ---------------------------------------------------------------------------

FREQ_HZ = 2445000000
SF = 8
BW_KHZ = 812.5
PA_MIN_DBM = -18          # firmware PA floor
PA_CAP_DBM = 10           # firmware indoor cap — never exceed
STAIRCASE_DBM = [-10, 0, 10]

BASELINE_SAMPLES = 20     # phase 1
BASELINE_WINDOW_S = 10.0
DURING_SAMPLES = 40       # phases 2/3
DURING_WINDOW_S = 25.0
TXPERIOD_S = 1.0          # one TXPROBE per second on the transmitting board
STAIRCASE_WINDOW_S = 15.0

# Verdict thresholds (spec)
LIVE_DELTA_DB = 15.0
LIVE_COUNT_ABOVE = 3
COUNT_ABOVE_MARGIN_DB = 10.0
DEAD_TOLERANCE_DB = 5.0

BAUD = 115200

# ---------------------------------------------------------------------------
# Raw transcript logger
# ---------------------------------------------------------------------------


class Transcript:
    """Append-only raw log. Every byte we send or receive is timestamped."""

    def __init__(self, path: str, echo: bool = True):
        self.path = path
        self.echo = echo
        self.fh = open(path, "a", buffering=1, encoding="utf-8")

    def _ts(self) -> str:
        return _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"

    def line(self, text: str) -> None:
        rec = "[%s] %s" % (self._ts(), text)
        self.fh.write(rec + "\n")
        if self.echo:
            print(rec, flush=True)

    def raw(self, tag: str, data: bytes) -> None:
        """Log raw bytes as an escaped one-liner (keeps CR/LF visible)."""
        self.line("%s %s" % (tag, data.decode("utf-8", errors="replace")
                             .replace("\r", "\\r").replace("\n", "\\n")))

    def close(self) -> None:
        try:
            self.fh.close()
        except Exception:
            pass


# ---------------------------------------------------------------------------
# Board
# ---------------------------------------------------------------------------


class BoardError(RuntimeError):
    pass


class Board:
    """One E28 board. The serial port is opened ONCE and kept open."""

    def __init__(self, name: str, port: str, log: Transcript):
        self.name = name
        self.port = port
        self.log = log
        self._buf = ""
        self.ser: serial.Serial | None = None

    # -- lifecycle ---------------------------------------------------------

    def open(self) -> None:
        s = serial.Serial()
        s.port = self.port
        s.baudrate = BAUD
        s.timeout = 0.2
        s.write_timeout = 2.0
        # NEVER assert DTR/RTS on open — these boards park in ROM mode.
        s.dtr = False
        s.rts = False
        try:
            s.open()
        except Exception as exc:  # noqa: BLE001
            raise BoardError("open %s (%s) failed: %r" % (self.name, self.port, exc))
        self.ser = s
        self.log.line("%s open %s (dtr=False rts=False)" % (self.name, self.port))

    def close(self) -> None:
        if self.ser is not None:
            try:
                self.ser.close()
            except Exception:
                pass
            self.ser = None
            self.log.line("%s closed %s" % (self.name, self.port))

    def reboot_and_capture_banner(self, settle_s: float = 4.0) -> str:
        """Pulse RTS to reboot into the application and capture the boot banner.

        This is exactly esptool's `--after hard_reset` sequence (RTS = EN).
        DTR is held False (IO0 HIGH), so the chip boots the application rather
        than entering the ROM downloader.
        """
        assert self.ser is not None
        self.ser.reset_input_buffer()
        self._buf = ""
        self.log.line("%s reboot: RTS pulse (EN reset, DTR held False)" % self.name)
        self.ser.rts = True
        time.sleep(0.2)
        self.ser.rts = False
        deadline = time.time() + settle_s
        while time.time() < deadline:
            self._pump()
            time.sleep(0.05)
        banner = "\n".join(self.drain_lines())
        self.log.line("%s banner: %s" % (self.name, banner.replace("\r", "").replace("\n", " | ")))
        return banner

    # -- low level ---------------------------------------------------------

    def _pump(self) -> None:
        assert self.ser is not None
        n = self.ser.in_waiting
        data = self.ser.read(n if n else 0)
        if data:
            self.log.raw("%s<--" % self.name, data)
            self._buf += data.decode("utf-8", errors="replace")

    def drain_lines(self) -> list[str]:
        """Return complete lines seen so far; keep the partial tail buffered."""
        out = []
        while "\n" in self._buf:
            line, self._buf = self._buf.split("\n", 1)
            line = line.strip()
            if line:
                out.append(line)
        return out

    def send(self, cmd: str) -> None:
        assert self.ser is not None
        payload = (cmd + "\n").encode()
        self.log.raw("%s-->" % self.name, payload.rstrip(b"\n"))
        self.ser.write(payload)
        self.ser.flush()

    def command(self, cmd: str, pattern: str, timeout: float = 2.5) -> tuple[list[str], str | None]:
        """Send `cmd`, collect lines until one matches `pattern` (regex) or timeout.

        Returns (all_lines, matching_line_or_None). ERR lines are included in
        all_lines and are also treated as terminal on timeout.
        """
        rx = re.compile(pattern)
        self.send(cmd)
        lines: list[str] = []
        deadline = time.time() + timeout
        while time.time() < deadline:
            self._pump()
            for line in self.drain_lines():
                lines.append(line)
                if rx.search(line):
                    return lines, line
            time.sleep(0.02)
        self._pump()
        lines.extend(self.drain_lines())
        return lines, None

    # -- firmware commands -------------------------------------------------

    def send_raw(self, cmd: str) -> None:
        """Fire a command and return immediately (non-blocking read model)."""
        self.send(cmd)

    def poll_lines(self) -> list[str]:
        """Non-blocking: pump the port and return any complete lines."""
        self._pump()
        return self.drain_lines()

    def id(self) -> str:
        _, m = self.command("ID?", r"^E28-RANGE")
        return m or ""

    def stat(self) -> str:
        _, m = self.command("STAT?", r"^role=")
        return m or ""

    def rssi(self, timeout: float = 2.5) -> tuple[str, dict | None]:
        lines, m = self.command("RSSI?", r"^RSSI\s", timeout=timeout)
        if not m:
            return ("\n".join(lines), None)
        return (m, parse_rssi(m))

    def txprobe(self, timeout: float = 3.0) -> tuple[str, dict | None]:
        lines, m = self.command("TXPROBE", r"^TXPROBE\s", timeout=timeout)
        if not m:
            return ("\n".join(lines), None)
        return (m, parse_txprobe(m))

    def set_param(self, cmd: str, settle: float = 0.8) -> list[str]:
        """Send a parameter command and surface any ERR reply.

        The firmware's parameter handlers answer only with an ERR line on
        rejection (a successful set re-applies RadioLib config silently and is
        confirmed by a following STAT?). So we wait out `settle`, collect what
        came back, and raise if any line was an error.
        """
        self.send(cmd)
        lines: list[str] = []
        deadline = time.time() + settle
        while time.time() < deadline:
            self._pump()
            lines.extend(self.drain_lines())
            time.sleep(0.02)
        errs = [ln for ln in lines if ln.startswith("ERR")]
        if errs:
            raise BoardError("%s: %r rejected: %s" % (self.name, cmd, "; ".join(errs)))
        return lines


# ---------------------------------------------------------------------------
# Parsers
# ---------------------------------------------------------------------------

RE_RSSI = re.compile(
    r"^RSSI\s+(?P<pkt>-?\d+(?:\.\d+)?)\s+dBm\s+"
    r"inst=(?P<inst>-?\d+(?:\.\d+)?)\s+dBm\s+"
    r"state=(?P<state>-?\d+)\s+\((?P<verdict>[a-z\-]+)\)"
)

RE_TXPROBE = re.compile(
    r"^TXPROBE\s+start=(?P<start>-?\d+)\s+txdone_irqbit=(?P<irqbit>[01])\s+"
    r"dio1_pin=(?P<dio1>[01])\s+irqstatus=0x(?P<irqstatus>[0-9A-Fa-f]+)"
)

RE_ROLE = re.compile(r"role=(?P<role>\w+)")

# --- SX128x CAD scan-state decoding ----------------------------------------
# RadioLib's SX128x::getChannelScanResult() returns RADIOLIB_LORA_DETECTED when
# the CAD detects preamble activity, and RADIOLIB_CHANNEL_FREE otherwise.
# Their actual values (RadioLib 7.7.1 TypeDef.h) are:
#     RADIOLIB_PREAMBLE_DETECTED = -14
#     RADIOLIB_CHANNEL_FREE      = -15
#     RADIOLIB_LORA_DETECTED     = -702   <-- NOT -14
# The firmware's probe_rssi() only compares against -14 and -15, so a REAL
# preamble detection arrives labelled "scan-error" with state=-702. Anything
# consuming this output must decode the state code, not the printed label.
CAD_STATE_FREE = -15
CAD_STATE_PREAMBLE = -14
CAD_STATE_LORA_DETECTED = -702   # what SX128x::getChannelScanResult() really returns
CAD_DETECTED_CODES = (CAD_STATE_PREAMBLE, CAD_STATE_LORA_DETECTED)


def classify_scan_state(state: int | None, label: str | None = None) -> str:
    """Decode the CAD state code into a trustworthy name."""
    if state is None:
        return "unknown"
    if state in CAD_DETECTED_CODES:
        return "lora-detected"
    if state == CAD_STATE_FREE:
        return "channel-free"
    return "scan-error"


def firmware_label_is_misleading(state: int | None, label: str | None) -> bool:
    """True when the firmware's printed label contradicts the state code."""
    if state is None:
        return False
    return classify_scan_state(state, label) != (label or "").replace("lora-preamble",
                                                                     "lora-detected")


def parse_rssi(line: str) -> dict | None:
    m = RE_RSSI.search(line)
    if not m:
        return None
    state = int(m.group("state"))
    return {
        "packet_dbm": float(m.group("pkt")),
        "inst_dbm": float(m.group("inst")),
        "state": state,
        "firmware_label": m.group("verdict"),
        "scan_state": classify_scan_state(state, m.group("verdict")),
    }


def parse_txprobe(line: str) -> dict | None:
    m = RE_TXPROBE.search(line)
    if not m:
        return None
    return {
        "start": int(m.group("start")),
        "txdone_irqbit": int(m.group("irqbit")),
        "dio1_pin": int(m.group("dio1")),
        "irqstatus": int(m.group("irqstatus"), 16),
    }


# ---------------------------------------------------------------------------
# Port resolution — never hardcode ttyACM numbers
# ---------------------------------------------------------------------------

_NORM = lambda s: re.sub(r"[^0-9a-f]", "", s.lower())  # noqa: E731


def resolve_port(serial_id: str, log: Transcript) -> str:
    """Resolve a USB serial (e.g. 9C:13:9E:F1:0C:28) to a live device path.

    Re-resolved every time it is called, because these ports re-enumerate
    after a flash. Preference order: /dev/serial/by-id symlink, then udevadm
    scan of /dev/ttyACM*, so the ttyACM number is never hardcoded.
    """
    want = _NORM(serial_id)
    for path in sorted(glob.glob("/dev/serial/by-id/*")):
        if want in _NORM(os.path.basename(path)):
            log.line("resolve %s -> %s" % (serial_id, path))
            return path

    for dev in sorted(glob.glob("/dev/ttyACM*")):
        try:
            out = subprocess.run(
                ["udevadm", "info", "-q", "property", "-n", dev],
                capture_output=True, text=True, timeout=5,
            ).stdout
        except Exception:
            continue
        for line in out.splitlines():
            if line.startswith("ID_SERIAL_SHORT="):
                if _NORM(line.split("=", 1)[1]) == want:
                    log.line("resolve %s -> %s (via udevadm)" % (serial_id, dev))
                    return dev
    raise BoardError("could not resolve serial %s to a device path" % serial_id)


# ---------------------------------------------------------------------------
# Statistics + verdicts
# ---------------------------------------------------------------------------


def stats(values: list[float]) -> dict:
    if not values:
        return {"n": 0}
    return {
        "n": len(values),
        "min": min(values),
        "median": statistics.median(values),
        "max": max(values),
    }


def verdict(baseline_max: float | None, during: list[float]) -> dict:
    """Apply the spec's LIVE / DEAD / INCONCLUSIVE rules."""
    if baseline_max is None or not during:
        return {"verdict": "INCONCLUSIVE", "reason": "missing samples"}
    d_max = max(during)
    delta = d_max - baseline_max
    thr = baseline_max + LIVE_DELTA_DB
    above = [v for v in during if v > baseline_max + COUNT_ABOVE_MARGIN_DB]
    worst_dev = max(abs(v - baseline_max) for v in during)

    if d_max >= thr and len(above) >= LIVE_COUNT_ABOVE:
        v = "LIVE"
        reason = ("during_max %.1f >= baseline_max %.1f + %.0f dB, and %d sample(s) "
                  "above baseline+%.0f dB (>= %d required)" %
                  (d_max, baseline_max, LIVE_DELTA_DB, len(above),
                   COUNT_ABOVE_MARGIN_DB, LIVE_COUNT_ABOVE))
    elif worst_dev <= DEAD_TOLERANCE_DB:
        v = "DEAD"
        reason = ("every during sample within +/-%.0f dB of baseline_max %.1f "
                  "(worst deviation %.1f dB); during_max %.1f" %
                  (DEAD_TOLERANCE_DB, baseline_max, worst_dev, d_max))
    else:
        v = "INCONCLUSIVE"
        reason = ("during_max %.1f vs baseline_max %.1f -> delta %+.1f dB "
                  "(LIVE needs >= +%.0f dB with %d samples above +%.0f); "
                  "worst deviation %.1f dB (DEAD needs <= %.0f)" %
                  (d_max, baseline_max, delta, LIVE_DELTA_DB, LIVE_COUNT_ABOVE,
                   COUNT_ABOVE_MARGIN_DB, worst_dev, DEAD_TOLERANCE_DB))
    return {
        "verdict": v,
        "reason": reason,
        "baseline_max_inst": baseline_max,
        "during_max_inst": d_max,
        "delta_db": round(delta, 2),
        "count_above_baseline_plus_10": len(above),
        "worst_deviation_db": round(worst_dev, 2),
    }


# ---------------------------------------------------------------------------
# Phases
# ---------------------------------------------------------------------------


RE_STAT = re.compile(
    r"^role=(?P<role>\w+)\s+freq=(?P<freq>\d+)\s+sf=(?P<sf>\d+)\s+bw=(?P<bw>[\d.]+)\s+"
    r"pa=(?P<pa>-?\d+)\s+addr=0x(?P<addr>[0-9A-Fa-f]+)\s+"
    r"last=(?P<last>\S+)\s+err=(?P<err>-?\d+)"
)


def parse_stat(line: str) -> dict | None:
    m = RE_STAT.search(line)
    if not m:
        return None
    return {
        "role": m.group("role"),
        "freq_mhz": int(m.group("freq")),
        "sf": int(m.group("sf")),
        "bw_khz": float(m.group("bw")),
        "pa_dbm": int(m.group("pa")),
        "addr": int(m.group("addr"), 16),
        "last": m.group("last"),
        "err": int(m.group("err")),
    }


def configure(board: Board, pa: int) -> dict:
    """Phase 0: identical RF config on both ends, minimum power.

    Every parameter is verified by reading STAT? back — the firmware only
    prints ERR on rejection, so a silent success must be confirmed.
    """
    dump: dict = {"id": board.id(), "stat_before": board.stat()}
    for cmd in ("FREQ %d" % FREQ_HZ,
                "SF %d" % SF,
                "BW %s" % ("812.5" if BW_KHZ == 812.5 else str(BW_KHZ)),
                "PA %d" % pa):
        dump.setdefault("replies", []).append({"cmd": cmd, "lines": board.set_param(cmd)})
    board._pump()  # drain any trailing bytes before the confirmation read
    st_line = board.stat()
    st = parse_stat(st_line)
    dump["stat_after"] = st_line
    dump["stat_parsed"] = st
    if st is None:
        raise BoardError("%s: unparseable STAT? after configure: %r" % (board.name, st_line))
    if st["freq_mhz"] != FREQ_HZ // 1000000:
        raise BoardError("%s: FREQ did not stick (want %d MHz, got %s)"
                         % (board.name, FREQ_HZ // 1000000, st["freq_mhz"]))
    if st["sf"] != SF:
        raise BoardError("%s: SF did not stick (want %d, got %s)" % (board.name, SF, st["sf"]))
    if abs(st["bw_khz"] - BW_KHZ) > 0.01:
        raise BoardError("%s: BW did not stick (want %s, got %s)"
                         % (board.name, BW_KHZ, st["bw_khz"]))
    if st["pa_dbm"] != pa:
        raise BoardError("%s: PA did not stick (want %d, got %s)" % (board.name, pa, st["pa_dbm"]))
    return dump


def sample_phase(log: Transcript, phase: str, tx: Board | None, rx: Board,
                 window_s: float, rssi_samples: int, tx_every: float | None,
                 pa: int, extra: dict | None = None) -> dict:
    """Sample the receiver for `window_s`, optionally keying TXPROBE on `tx`."""
    rec = {
        "phase": phase,
        "window_s": window_s,
        "transmitter": (tx.name if tx else "none (idle)"),
        "receiver": rx.name,
        "pa_dbm": pa,
        "rssi_samples_requested": rssi_samples,
        "series": [],       # [{t, inst_dbm, packet_dbm, scan_state, raw}]
        "txprobes": [],     # [{t, raw, parsed}]
        "rx_failures": [],
    }
    if extra:
        rec.update(extra)

    log.line("--- %s : tx=%s rx=%s pa=%d dBm window=%.1fs rssi_samples=%d ---"
             % (phase, rec["transmitter"], rx.name, pa, window_s, rssi_samples))

    t_start = time.monotonic()
    t_end = t_start + window_s
    next_rssi = t_start
    next_tx = t_start
    rssi_period = window_s / max(1, rssi_samples)

    while time.monotonic() < t_end:
        now = time.monotonic()

        # Transmit side: one TXPROBE per `tx_every` seconds.
        if tx is not None and tx_every and now >= next_tx:
            raw, parsed = tx.txprobe()
            rec["txprobes"].append({
                "t_rel_s": round(time.monotonic() - t_start, 3),
                "raw": raw,
                "parsed": parsed,
            })
            # Never let a slow/failed TXPROBE cause a burst of catch-up probes.
            next_tx = max(next_tx + tx_every, time.monotonic())

        # Receive side: sampled strictly on cadence.
        if now >= next_rssi:
            raw, parsed = rx.rssi()
            if parsed is None:
                rec["rx_failures"].append({"t_rel_s": round(time.monotonic() - t_start, 3),
                                           "raw": raw})
            else:
                rec["series"].append({
                    "t_rel_s": round(time.monotonic() - t_start, 3),
                    "inst_dbm": parsed["inst_dbm"],
                    "packet_dbm": parsed["packet_dbm"],
                    "scan_state": parsed["scan_state"],
                    "state": parsed["state"],
                    "raw": raw,
                })
            next_rssi += rssi_period

        time.sleep(0.01)

    inst = [s["inst_dbm"] for s in rec["series"]]
    rec["stats"] = stats(inst)
    rec["scan_states"] = sorted({s["scan_state"] for s in rec["series"]})
    rec["state_codes"] = sorted({s["state"] for s in rec["series"]})
    rec["detections"] = sum(1 for s in rec["series"] if s["scan_state"] == "lora-detected")
    rec["preamble_samples"] = rec["detections"]
    rec["packet_rssi_nonzero"] = sum(1 for s in rec["series"] if s["packet_dbm"] != 0.0)
    irqbits = [t["parsed"]["txdone_irqbit"] for t in rec["txprobes"] if t["parsed"]]
    dio1s = [t["parsed"]["dio1_pin"] for t in rec["txprobes"] if t["parsed"]]
    starts = [t["parsed"]["start"] for t in rec["txprobes"] if t["parsed"]]
    rec["tx_summary"] = {
        "txprobe_count": len(rec["txprobes"]),
        "parsed_ok": len(irqbits),
        "txdone_irqbit_all_1": (all(b == 1 for b in irqbits) if irqbits else None),
        "dio1_pin_all_1": (all(b == 1 for b in dio1s) if dio1s else None),
        "start_codes": sorted(set(starts)),
    }

    log.line("%s stats: %s | scan_states=%s codes=%s detections=%d"
             % (phase, rec["stats"], rec["scan_states"], rec["state_codes"],
                rec["detections"]))
    log.line("%s tx: %s" % (phase, rec["tx_summary"]))
    return rec


def highrate_phase(log: Transcript, phase: str, tx: Board, rx: Board,
                   window_s: float, pa: int) -> dict:
    """NON-SPEC extra phase: sample the receiver as fast as it answers while the
    transmitter fires TXPROBE back-to-back.

    WHY: the mandated cadence (one `RSSI?` every ~0.6 s) has an expected
    CAD/burst overlap count of ~0.05 per phase, so it cannot distinguish a dead
    RF chain from a sampling miss. Measured rates on this hardware are
    TXPROBE 436 ms (2.29/s) and RSSI? 52 ms (19.2/s). The CAD window is
    8 symbols x 315 us = 2.52 ms at SF8/BW812.5, and the packet burst is
    ~12.6 ms of air time. Expected overlaps in `window_s` seconds are therefore

        window_s * tx_rate * rx_rate * (cad_window + burst) / 1000

    which is ~20 detections in 30 s if the link works -- a decisive test, and
    zero detections is then real evidence rather than a miss.
    """
    tx.set_param("PA %d" % pa)
    log.line("--- %s : tx=%s rx=%s pa=%d dBm window=%.1fs (HIGH-RATE, non-spec) ---"
             % (phase, tx.name, rx.name, pa, window_s))

    rec = {"phase": phase, "non_spec_extension": True, "window_s": window_s,
           "transmitter": tx.name, "receiver": rx.name, "pa_dbm": pa,
           "series": [], "txprobes": [], "rx_failures": [],
           "tx_requested": 0, "rx_requested": 0}

    t_start = time.monotonic()
    t_end = t_start + window_s
    tx_pending = False
    rx_pending = False
    next_tx = t_start
    MIN_TX_GAP = 0.30     # TXPROBE takes ~436 ms; do not queue another early

    while time.monotonic() < t_end:
        now = time.monotonic()

        # --- collect whatever both boards have said -----------------------
        for line in tx.poll_lines():
            parsed = parse_txprobe(line)
            tx_pending = False
            if parsed:
                rec["txprobes"].append({"t_rel_s": round(now - t_start, 4),
                                        "raw": line, "parsed": parsed})
        for line in rx.poll_lines():
            parsed = parse_rssi(line)
            if parsed:
                rx_pending = False
                rec["series"].append({
                    "t_rel_s": round(now - t_start, 4),
                    "inst_dbm": parsed["inst_dbm"],
                    "packet_dbm": parsed["packet_dbm"],
                    "scan_state": parsed["scan_state"],
                    "firmware_label": parsed["firmware_label"],
                    "state": parsed["state"],
                    "raw": line,
                })

        # --- key the transmitter as fast as its own replies allow ----------
        if not tx_pending and now >= next_tx:
            tx.send_raw("TXPROBE")
            rec["tx_requested"] += 1
            tx_pending = True
            next_tx = now + MIN_TX_GAP

        # --- ask the receiver again the moment it answers ------------------
        if not rx_pending:
            rx.send_raw("RSSI?")
            rec["rx_requested"] += 1
            rx_pending = True

        time.sleep(0.002)

    # drain anything still in flight
    for _ in range(20):
        for line in tx.poll_lines():
            p = parse_txprobe(line)
            if p:
                rec["txprobes"].append({"t_rel_s": round(time.monotonic() - t_start, 4),
                                        "raw": line, "parsed": p})
        for line in rx.poll_lines():
            p = parse_rssi(line)
            if p:
                rec["series"].append({
                    "t_rel_s": round(time.monotonic() - t_start, 4),
                    "inst_dbm": p["inst_dbm"], "packet_dbm": p["packet_dbm"],
                    "scan_state": p["scan_state"], "firmware_label": p["firmware_label"],
                    "state": p["state"], "raw": line,
                })
        time.sleep(0.05)

    inst = [s["inst_dbm"] for s in rec["series"]]
    rec["stats"] = stats(inst)
    rec["state_codes"] = sorted({s["state"] for s in rec["series"]})
    rec["scan_states"] = sorted({s["scan_state"] for s in rec["series"]})
    rec["detections"] = sum(1 for s in rec["series"] if s["scan_state"] == "lora-detected")
    rec["packet_rssi_nonzero"] = sum(1 for s in rec["series"] if s["packet_dbm"] != 0.0)

    rate_tx = len(rec["txprobes"]) / window_s if window_s else 0.0
    rate_rx = len(rec["series"]) / window_s if window_s else 0.0
    CAD_WINDOW_MS, BURST_MS = 2.52, 12.6
    rec["rates"] = {"txprobe_per_s": round(rate_tx, 3), "rssi_per_s": round(rate_rx, 3)}
    rec["expected_cad_burst_overlaps"] = round(
        window_s * rate_tx * rate_rx * (CAD_WINDOW_MS + BURST_MS) / 1000.0, 2)

    irqbits = [t["parsed"]["txdone_irqbit"] for t in rec["txprobes"]]
    rec["tx_summary"] = {
        "txprobe_count": len(rec["txprobes"]),
        "txdone_irqbit_all_1": (all(b == 1 for b in irqbits) if irqbits else None),
    }
    log.line("%s: tx=%d (%.2f/s) rx=%d (%.2f/s) expected_overlaps=%.2f detections=%d"
             % (phase, len(rec["txprobes"]), rate_tx, len(rec["series"]), rate_rx,
                rec["expected_cad_burst_overlaps"], rec["detections"]))
    log.line("%s stats: %s codes=%s" % (phase, rec["stats"], rec["state_codes"]))
    return rec


def safe_end_state(log: Transcript, boards: list[Board]) -> dict:
    """PA -18, nothing transmitting, confirmed by STAT?."""
    out = {}
    for b in boards:
        log.line("--- SAFE END STATE: %s ---" % b.name)
        try:
            b.set_param("PA %d" % PA_MIN_DBM)
        except BoardError as exc:
            log.line("%s PA reset failed: %s" % (b.name, exc))
        st = b.stat()
        out[b.name] = st
        log.line("%s final STAT?: %s" % (b.name, st))
    return out


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--serial-a", default="9C:13:9E:F1:0C:28",
                    help="USB serial of board A (default: 9C:13:9E:F1:0C:28)")
    ap.add_argument("--serial-b", default="9C:13:9E:F1:0C:60",
                    help="USB serial of board B (default: 9C:13:9E:F1:0C:60)")
    ap.add_argument("--port-a", default=None, help="explicit device path for board A")
    ap.add_argument("--port-b", default=None, help="explicit device path for board B")
    ap.add_argument("--firmware-sha256", default=None,
                    help="sha256 of the flashed firmware.bin (recorded in the JSON)")
    ap.add_argument("--out-dir", default=None,
                    help="output dir for .log/.json (default: <repo>/captures)")
    ap.add_argument("--stem", default=None,
                    help="output filename stem (default: e28-rf-liveness-<UTC>)")
    ap.add_argument("--skip-banner-reboot", action="store_true",
                    help="do not RTS-pulse the boards to capture the boot banner")
    ap.add_argument("--no-staircase", action="store_true",
                    help="do not run phase 4 even if phases 2/3 detect nothing")
    ap.add_argument("--baseline-samples", type=int, default=BASELINE_SAMPLES)
    ap.add_argument("--during-samples", type=int, default=DURING_SAMPLES)
    ap.add_argument("--baseline-window", type=float, default=BASELINE_WINDOW_S)
    ap.add_argument("--during-window", type=float, default=DURING_WINDOW_S)
    ap.add_argument("--staircase-window", type=float, default=STAIRCASE_WINDOW_S)
    ap.add_argument("--highrate-window", type=float, default=30.0,
                    help="seconds per high-rate sensitivity phase (non-spec extension)")
    ap.add_argument("--no-highrate", action="store_true",
                    help="skip the high-rate sensitivity phase")
    ap.add_argument("--dry-run", action="store_true",
                    help="resolve ports + capture banners + ID?/STAT? only, then stop")
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args()

    stamp = _dt.datetime.now(_dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    stem = args.stem or ("e28-rf-liveness-%s" % stamp)
    out_dir = args.out_dir or os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "captures")
    os.makedirs(out_dir, exist_ok=True)
    log_path = os.path.join(out_dir, stem + ".log")
    json_path = os.path.join(out_dir, stem + ".json")

    log = Transcript(log_path, echo=not args.quiet)
    log.line("=" * 78)
    log.line("E28 RF liveness test — two LILYGO T3S3 + E28-2G4M27S (SX1280/SX1282)")
    log.line("UTC start: %s" % _dt.datetime.now(_dt.timezone.utc).isoformat())
    log.line("config: freq=%d Hz sf=%d bw=%s kHz pa_min=%d dBm cap=%d dBm"
             % (FREQ_HZ, SF, BW_KHZ, PA_MIN_DBM, PA_CAP_DBM))
    if args.firmware_sha256:
        log.line("firmware.bin sha256: %s" % args.firmware_sha256)
    log.line("=" * 78)

    result: dict = {
        "generated_utc": _dt.datetime.now(_dt.timezone.utc).isoformat(),
        "firmware_sha256": args.firmware_sha256,
        "config": {"freq_hz": FREQ_HZ, "sf": SF, "bw_khz": BW_KHZ,
                   "pa_min_dbm": PA_MIN_DBM, "pa_cap_dbm": PA_CAP_DBM},
        "thresholds": {
            "live_delta_db": LIVE_DELTA_DB,
            "live_count_above": LIVE_COUNT_ABOVE,
            "count_above_margin_db": COUNT_ABOVE_MARGIN_DB,
            "dead_tolerance_db": DEAD_TOLERANCE_DB,
        },
        "ports": {},
        "banners": {},
        "config_dumps": {},
        "phases": [],
        "analysis": {},
        "final_state": {},
        "errors": [],
    }

    boards: list[Board] = []
    try:
        # ---- resolve ports (re-resolved here, not from a cached guess) ----
        port_a = args.port_a or resolve_port(args.serial_a, log)
        port_b = args.port_b or resolve_port(args.serial_b, log)
        result["ports"] = {"A": port_a, "B": port_b, "serial_a": args.serial_a,
                           "serial_b": args.serial_b}

        A = Board("A", port_a, log)
        B = Board("B", port_b, log)
        boards = [A, B]

        # ---- open both, keep both open for the whole test ----
        A.open()
        B.open()
        time.sleep(0.5)

        # ---- boot banner ----
        if not args.skip_banner_reboot:
            for b in boards:
                banner = b.reboot_and_capture_banner()
                result["banners"][b.name] = banner
                if 'chip=""' in banner or "ranging_capable=0" in banner:
                    raise BoardError(
                        "%s boot banner indicates no usable ranging silicon: %r"
                        % (b.name, banner))
                if "E28-RANGE" not in banner:
                    raise BoardError("%s: no E28-RANGE boot banner seen: %r"
                                     % (b.name, banner))

        # ---- ID? / STAT? ----
        for b in boards:
            log.line("--- %s identity ---" % b.name)
            log.line("%s ID?  : %s" % (b.name, b.id()))
            log.line("%s STAT?: %s" % (b.name, b.stat()))

        # ---- phase 0: identical config, minimum power ----
        for b in boards:
            log.line("--- %s configure (freq/sf/bw/pa) ---" % b.name)
            result["config_dumps"][b.name] = configure(b, PA_MIN_DBM)

        if args.dry_run:
            log.line("--dry-run: config applied, stopping before phases")
            result["final_state"] = safe_end_state(log, boards)
            raise SystemExit(0)

        # ---- phase 1: BASELINE ----
        # 1 = B listening with A silent (the spec's phase 1)
        # 1b = A listening with B silent, so the B->A direction is judged
        #      against its OWN receiver's noise floor rather than B's.
        p1 = sample_phase(log, "phase1-baseline-B-listening", None, B,
                          args.baseline_window, args.baseline_samples, None, PA_MIN_DBM)
        result["phases"].append(p1)
        p1b = sample_phase(log, "phase1b-baseline-A-listening", None, A,
                           args.baseline_window, args.baseline_samples, None, PA_MIN_DBM)
        result["phases"].append(p1b)

        # ---- phase 2: A -> B ----
        p2 = sample_phase(log, "phase2-A-to-B", A, B,
                          args.during_window, args.during_samples, TXPERIOD_S, PA_MIN_DBM)
        result["phases"].append(p2)
        time.sleep(0.5)

        # ---- phase 3: B -> A (roles swapped) ----
        p3 = sample_phase(log, "phase3-B-to-A", B, A,
                          args.during_window, args.during_samples, TXPERIOD_S, PA_MIN_DBM)
        result["phases"].append(p3)

        # ---- verdicts at minimum power ----
        base_max = p1["stats"].get("max")    # B's floor (the spec's phase-1 baseline)
        base_max_a = p1b["stats"].get("max")  # A's own floor
        ab = verdict(base_max, [s["inst_dbm"] for s in p2["series"]])
        ba = verdict(base_max_a, [s["inst_dbm"] for s in p3["series"]])
        result["analysis"]["A_to_B_pa_minus18"] = ab
        result["analysis"]["B_to_A_pa_minus18"] = ba
        # Spec-literal cross-check: both directions against the phase-1 (B) baseline.
        result["analysis"]["B_to_A_vs_phase1_B_baseline"] = verdict(
            base_max, [s["inst_dbm"] for s in p3["series"]])
        result["analysis"]["A_to_B_vs_own_baseline"] = verdict(
            base_max_a, [s["inst_dbm"] for s in p2["series"]])

        # ---- phase 4: power staircase, only if nothing was detected ----
        staircase = []
        if not args.no_staircase and ab["verdict"] != "LIVE" and ba["verdict"] != "LIVE":
            log.line("=== no detectable rise at PA %d dBm -> power staircase ===" % PA_MIN_DBM)
            for pa in STAIRCASE_DBM:
                if pa > PA_CAP_DBM:
                    break
                ps = sample_phase(log, "phase4-staircase-%+d" % pa, A, B,
                                  args.staircase_window,
                                  max(8, int(args.staircase_window / 0.6)),
                                  TXPERIOD_S, pa)
                v = verdict(base_max, [s["inst_dbm"] for s in ps["series"]])
                ps["verdict_vs_baseline"] = v
                staircase.append(ps)
                result["phases"].append(ps)
            result["analysis"]["staircase"] = [
                {"pa_dbm": s["pa_dbm"], "stats": s["stats"], "verdict": s["verdict_vs_baseline"]}
                for s in staircase
            ]
        else:
            log.line("=== staircase skipped (a direction already reads LIVE) ===")

        # ---- phase 5: high-rate sensitivity check (NON-SPEC extension) ----
        # The mandated cadence cannot reach the LIVE criteria on its own, so
        # this phase samples fast enough that a working link MUST produce CAD
        # detections. Zero detections here is real evidence, not a miss.
        hr: list[dict] = []
        if not args.no_highrate:
            log.line("=== HIGH-RATE sensitivity check (non-spec extension) ===")
            hr_ab = highrate_phase(log, "phase5-highrate-A-to-B", A, B,
                                   args.highrate_window, PA_MIN_DBM)
            hr.append(hr_ab)
            hr_ba = highrate_phase(log, "phase5-highrate-B-to-A", B, A,
                                   args.highrate_window, PA_MIN_DBM)
            hr.append(hr_ba)
            if hr_ab["detections"] == 0 and hr_ba["detections"] == 0:
                log.line("=== no CAD detection at PA %d dBm -> repeat A->B at PA +%d dBm "
                         "(level already exercised in the phase-4 staircase) ==="
                         % (PA_MIN_DBM, PA_CAP_DBM))
                hr.append(highrate_phase(log, "phase5-highrate-A-to-B-pa+10", A, B,
                                         args.highrate_window, PA_CAP_DBM))
            for h in hr:
                result["phases"].append(h)

            ab_hr = next(h for h in hr if h["receiver"] == "B")
            ba_hr = next(h for h in hr if h["receiver"] == "A")
            best_ab = max(h["detections"] for h in hr if h["receiver"] == "B")
            best_ba = max(h["detections"] for h in hr if h["receiver"] == "A")

            def hr_verdict(det: int, expected: float) -> str:
                if det >= 1:
                    return "LIVE"
                if expected >= 3.0:
                    return "DEAD"
                return "INCONCLUSIVE"

            result["analysis"]["highrate"] = [
                {"phase": h["phase"], "pa_dbm": h["pa_dbm"], "receiver": h["receiver"],
                 "samples": len(h["series"]), "txprobes": len(h["txprobes"]),
                 "rates": h.get("rates"),
                 "expected_cad_burst_overlaps": h["expected_cad_burst_overlaps"],
                 "detections": h["detections"],
                 "packet_rssi_nonzero": h["packet_rssi_nonzero"],
                 "stats": h["stats"], "state_codes": h["state_codes"]}
                for h in hr
            ]
            result["analysis"]["highrate_verdict_A_to_B"] = hr_verdict(
                best_ab, ab_hr["expected_cad_burst_overlaps"])
            result["analysis"]["highrate_verdict_B_to_A"] = hr_verdict(
                best_ba, ba_hr["expected_cad_burst_overlaps"])
            result["analysis"]["highrate_expected_overlaps_A_to_B"] = \
                ab_hr["expected_cad_burst_overlaps"]
            result["analysis"]["highrate_expected_overlaps_B_to_A"] = \
                ba_hr["expected_cad_burst_overlaps"]

        # ---- safe end state ----
        result["final_state"] = safe_end_state(log, boards)

    except (BoardError, KeyboardInterrupt) as exc:
        msg = "%s: %s" % (type(exc).__name__, exc)
        log.line("ABORT: %s" % msg)
        result["errors"].append(msg)
        try:
            result["final_state"] = safe_end_state(log, boards)
        except Exception as exc2:  # noqa: BLE001
            log.line("safe end state failed: %r" % exc2)
            result["errors"].append("safe end state failed: %r" % exc2)
    finally:
        for b in boards:
            b.close()
        log.line("raw log: %s" % log_path)
        log.line("json   : %s" % json_path)
        result["artifacts"] = {"log": log_path, "json": json_path}
        with open(json_path, "w", encoding="utf-8") as fh:
            json.dump(result, fh, indent=2)
        log.close()

    # ---- console summary ----
    print("\n" + "=" * 78)
    print("SUMMARY")
    for phase in result["phases"]:
        st = phase.get("stats", {})
        print("  %-24s tx=%-16s pa=%+3d n=%-3s min=%-7s med=%-7s max=%-7s states=%s"
              % (phase["phase"], phase["transmitter"], phase["pa_dbm"],
                 st.get("n"), st.get("min"), st.get("median"), st.get("max"),
                 phase.get("scan_states")))
    for key, val in result["analysis"].items():
        if isinstance(val, dict) and "verdict" in val:
            print("  %-28s %-13s %s" % (key, val["verdict"], val["reason"]))
    print("  final state:", result["final_state"])
    print("  artifacts  :", result.get("artifacts"))
    if result["errors"]:
        print("  ERRORS     :", result["errors"])
    print("=" * 78)
    return 0 if not result["errors"] else 1


if __name__ == "__main__":
    sys.exit(main())
