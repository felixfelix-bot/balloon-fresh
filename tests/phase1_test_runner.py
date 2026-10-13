#!/usr/bin/env python3
"""Phase 1 LR2021 Test Runner — serial orchestration of the 6-mode bench matrix.

Automates the Phase 1 hardware test matrix defined by task P1.4:

    1A: ESP32-B  TX -> RP2040-A RX   (500 pkt,  100 ms)
    1B: ESP32-C  TX -> RP2040-A RX   (500 pkt,  100 ms)
    1C: B+C      TX -> RP2040-A RX   (1000 pkt, staggered 50 ms, dual TX)
    1D: RP2040-A TX -> ESP32-B RX    (500 pkt,  100 ms)
    1E: ESP32-B  TX -> ESP32-C  RX   (500 pkt,  baseline)
    1F: ESP32-B  TX -> A+C      RX   (500 pkt,  RSSI comparison, dual RX)

Per mode the runner:
  1. connects to the TX node(s) and RX node(s) over serial,
  2. arms the RX node(s) into receive mode (waits for READY),
  3. sends START to the TX node(s),
  4. collects the RX output until a RESULT / END marker or timeout,
  5. parses the per-packet lines into structured records,
  6. computes packet-loss %, RSSI stats, and per-stage timing stats,
  7. writes results/phase1/test-<mode>.csv + appends to results/phase1/summary.json.

The script is firmware-agnostic: it understands three RX output dialects and a
configurable TX start command, so it works with the existing RP2040 coprocessor
firmware (firmware/rp2040/src/main.cpp — timing-only CSV) and the ESP32-C3
bench firmware (run_benchmark.py style — RSSI/SNR per packet). A ``--mock``
backend replays scripted serial output so the whole pipeline can be exercised
without any hardware (used by the pytest suite and CI).

Examples
--------
  # real hardware (config file maps node names -> ports):
  python3 tests/phase1_test_runner.py --config tests/phase1_config.yaml --all

  # override a single node's port on the command line:
  python3 tests/phase1_test_runner.py --port ESP32-B=/dev/ttyACM2 \
      --port RP2040-A=/dev/ttyACM0 --mode 1A

  # hardware-free self-test (writes to results/phase1/):
  python3 tests/phase1_test_runner.py --mock --all
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import statistics
import sys
import threading
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Callable, Optional

# --------------------------------------------------------------------------- #
# Optional dependencies — imported lazily so the module (and its test suite)
# loads even when pyserial / PyYAML are absent. The existing project tests
# (tests/src/test_rp2040_speed.py) follow the same pattern.
# --------------------------------------------------------------------------- #
try:  # pragma: no cover - exercised only on real hardware
    import serial as _pyserial
except ImportError:  # pragma: no cover
    _pyserial = None

try:
    import yaml as _yaml
except ImportError:  # pragma: no cover
    _yaml = None


REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OUT_DIR = REPO_ROOT / "results" / "phase1"


# --------------------------------------------------------------------------- #
# Data models
# --------------------------------------------------------------------------- #
@dataclass
class PacketRecord:
    """One received packet.

    ``rssi``/``snr`` are optional: the RP2040 coprocessor firmware currently
    emits timing-only CSV (no RSSI per packet), while the ESP32 bench firmware
    reports both. ``None`` means "not reported by this RX firmware".
    """

    index: int
    seq: int
    rssi: Optional[float] = None
    snr: Optional[float] = None
    irq_us: Optional[int] = None
    read_us: Optional[int] = None
    clear_us: Optional[int] = None
    rx_us: Optional[int] = None
    total_us: Optional[int] = None


@dataclass
class TestMode:
    """Definition of one row of the Phase 1 matrix."""

    code: str  # "1A" .. "1F"
    name: str
    tx_nodes: list[str]
    rx_nodes: list[str]
    expected_packets: int
    delay_ms: int  # inter-packet TX delay
    stagger_ms: int = 0  # offset between transmitters in a multi-TX mode
    note: str = ""


@dataclass
class ModeStats:
    """Aggregated statistics for one mode run."""

    packets_received: int = 0
    unique_seqs: int = 0
    duplicates: int = 0
    out_of_order: int = 0
    expected_packets: int = 0
    packet_loss_pct: float = 0.0

    # RSSI statistics (dBm) — None when the RX firmware did not report RSSI.
    rssi_min: Optional[float] = None
    rssi_avg: Optional[float] = None
    rssi_max: Optional[float] = None
    rssi_std: Optional[float] = None
    rssi_p95: Optional[float] = None
    rssi_count: int = 0

    # SNR statistics (dB) — same None convention as RSSI.
    snr_avg: Optional[float] = None
    snr_count: int = 0

    # Per-stage timing statistics (microseconds) — None for RX firmware that
    # does not break out timing (e.g. plain ESP32 bench RX).
    total_min_us: Optional[int] = None
    total_avg_us: Optional[float] = None
    total_max_us: Optional[int] = None

    elapsed_ms: int = 0  # wall-clock duration of the collection window


@dataclass
class ModeResult:
    """Full result of one mode run, for CSV footer + JSON summary."""

    mode: str
    name: str
    tx_nodes: list[str]
    rx_nodes: list[str]
    stats: ModeStats
    packets: list[PacketRecord] = field(default_factory=list)
    raw_log: list[str] = field(default_factory=list)
    ok: bool = True
    error: str = ""

    def to_summary_dict(self) -> dict:
        d = asdict(self)
        d.pop("packets", None)  # packets go to per-mode CSV, not the summary
        return d


# --------------------------------------------------------------------------- #
# Phase 1 test matrix (task P1.4)
# --------------------------------------------------------------------------- #
TEST_MODES: dict[str, TestMode] = {
    "1A": TestMode("1A", "ESP32-B -> RP2040-A", ["ESP32-B"], ["RP2040-A"],
                   expected_packets=500, delay_ms=100,
                   note="ESP32 TX board into RP2040 coprocessor"),
    "1B": TestMode("1B", "ESP32-C -> RP2040-A", ["ESP32-C"], ["RP2040-A"],
                   expected_packets=500, delay_ms=100,
                   note="second ESP32 TX board into RP2040 coprocessor"),
    "1C": TestMode("1C", "B+C -> RP2040-A (dual TX)", ["ESP32-B", "ESP32-C"],
                   ["RP2040-A"], expected_packets=1000, delay_ms=50,
                   stagger_ms=50,
                   note="both ESP32 boards transmit staggered by 50 ms"),
    "1D": TestMode("1D", "RP2040-A -> ESP32-B", ["RP2040-A"], ["ESP32-B"],
                   expected_packets=500, delay_ms=100,
                   note="reverse link: RP2040 as transmitter"),
    "1E": TestMode("1E", "ESP32-B -> ESP32-C (baseline)", ["ESP32-B"],
                   ["ESP32-C"], expected_packets=500, delay_ms=100,
                   note="ESP32-to-ESP32 baseline"),
    "1F": TestMode("1F", "ESP32-B -> A+C (dual RX RSSI)", ["ESP32-B"],
                   ["RP2040-A", "ESP32-C"], expected_packets=500, delay_ms=100,
                   note="two receivers compared for RSSI characterisation"),
}


# --------------------------------------------------------------------------- #
# Serial backends
# --------------------------------------------------------------------------- #
class SerialBackend:
    """Minimal serial-like interface used by the orchestrator.

    Implementations: :class:`RealSerialBackend` (pyserial) and
    :class:`MockSerialBackend` (scripted). Only ``write`` / ``readline`` /
    ``read_all`` / ``reset_input_buffer`` / ``close`` are required.
    """

    def write(self, data: bytes) -> None: ...
    def readline(self, timeout: float) -> bytes: ...
    def reset_input_buffer(self) -> None: ...
    def close(self) -> None: ...


class RealSerialBackend(SerialBackend):
    """pyserial-backed serial port. Created lazily from a device path."""

    def __init__(self, port: str, baud: int = 115200):
        if _pyserial is None:  # pragma: no cover
            raise RuntimeError("pyserial is not installed — run: pip install pyserial")
        self._ser = _pyserial.Serial(port, baudrate=baud, timeout=0.1)

    def write(self, data: bytes) -> None:
        self._ser.write(data)
        self._ser.flush()

    def readline(self, timeout: float) -> bytes:
        self._ser.timeout = timeout
        return self._ser.readline()

    def reset_input_buffer(self) -> None:
        self._ser.reset_input_buffer()

    def close(self) -> None:
        try:
            self._ser.close()
        except Exception:  # pragma: no cover
            pass


class MockSerialBackend(SerialBackend):
    """Scripted serial backend for ``--mock`` mode and the pytest suite.

    The node boots by emitting ``boot_lines``, then waits. Each ``write()``
    triggers any staged ``lines`` to be emitted on subsequent ``readline()``
    calls, so the orchestrator's normal "send START -> collect RX" flow works
    unchanged. ``on_write`` lets tests customise start-command reactions.
    """

    def __init__(self, boot_lines: Optional[list[str]] = None,
                 lines: Optional[list[str]] = None,
                 on_write: Optional[Callable[[str], list[str]]] = None,
                 per_line_delay: float = 0.0):
        self._boot = list(boot_lines or [])
        self._pending: list[str] = list(lines or [])
        self._on_write = on_write
        self._per_line_delay = per_line_delay
        self._started = False

    def write(self, data: bytes) -> None:
        text = data.decode(errors="replace")
        self._started = True
        if self._on_write:
            extra = self._on_write(text)
            if extra:
                self._pending.extend(extra)

    def readline(self, timeout: float) -> bytes:
        if self._boot:
            return (self._boot.pop(0) + "\n").encode()
        if self._pending:
            if self._per_line_delay:
                time.sleep(min(self._per_line_delay, timeout))
            return (self._pending.pop(0) + "\n").encode()
        # No data available within the window.
        time.sleep(min(0.01, timeout))
        return b""

    def reset_input_buffer(self) -> None:
        self._boot.clear()

    def close(self) -> None:
        pass


BackendFactory = Callable[[str, int], SerialBackend]


def real_backend_factory(baud: int = 115200) -> BackendFactory:
    def _make(port: str, _baud: int = baud) -> SerialBackend:
        return RealSerialBackend(port, baud)
    return _make


# --------------------------------------------------------------------------- #
# Protocol parsing
# --------------------------------------------------------------------------- #
# Three RX dialects are understood:
#   1. canonical   pkt,seq,rssi,snr,irq_us,read_us,clr_us,rx_us,total_us
#   2. RP2040      pkt,seq,irq_us,read_us,clr_us,rx_us,total_us   (timing only)
#   3. ESP32 bench I (<n>) BENCH: PKT,seq,rssi,snr,...            (log-wrapped)
_BENCH_PKT_RE = re.compile(r"^I \(\d+\) BENCH: PKT,(.+)$")
_BENCH_RESULT_RE = re.compile(r"^I \(\d+\) BENCH: RESULT,(.+)$")


def _to_float(v: str) -> Optional[float]:
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _to_int(v: str) -> Optional[int]:
    try:
        return int(v)
    except (TypeError, ValueError):
        return None


def parse_packet_line(line: str) -> Optional[PacketRecord]:
    """Parse one RX serial line into a PacketRecord, or None if not a packet.

    Returns None for blank lines, the CSV header, RESULT lines, and anything
    that doesn't look like per-packet data.
    """
    s = line.strip()
    if not s:
        return None

    # Dialect 3: ESP-IDF log-wrapped bench line.
    m = _BENCH_PKT_RE.match(s)
    if m:
        s = m.group(1)

    if s.startswith("pkt,") or s.startswith("I ("):
        return None
    if s.startswith("RESULT") or s.startswith("==="):
        return None

    parts = s.split(",")
    # Reject the RP2040 RESULT-ish footer that also has commas.
    if not parts or not parts[0].lstrip("-").isdigit():
        return None

    try:
        idx = int(parts[0])
        seq = int(parts[1])
    except (ValueError, IndexError):
        return None

    # Dialect 1: 9 fields with rssi/snr.
    if len(parts) >= 9:
        return PacketRecord(
            index=idx, seq=seq,
            rssi=_to_float(parts[2]), snr=_to_float(parts[3]),
            irq_us=_to_int(parts[4]), read_us=_to_int(parts[5]),
            clear_us=_to_int(parts[6]), rx_us=_to_int(parts[7]),
            total_us=_to_int(parts[8]),
        )
    # Dialect 2: 7 fields, timing only.
    if len(parts) == 7:
        return PacketRecord(
            index=idx, seq=seq,
            irq_us=_to_int(parts[2]), read_us=_to_int(parts[3]),
            clear_us=_to_int(parts[4]), rx_us=_to_int(parts[5]),
            total_us=_to_int(parts[6]),
        )
    return None


def parse_result_line(line: str) -> Optional[dict]:
    """Parse a RESULT footer line (either dialect) into a flat dict.

    RP2040:  RESULT,recv,unique,dup,err,tput,min,avg,max
    ESP32:   I (<n>) BENCH: RESULT,received,...
    Canonical/unknown RESULT,<key>=<val>,<key>=<val>... is also accepted.
    """
    s = line.strip()
    m = _BENCH_RESULT_RE.match(s)
    if m:
        s = "RESULT," + m.group(1)
    if not s.startswith("RESULT"):
        return None
    parts = s.split(",")
    if len(parts) < 2:
        return None
    body = parts[1:]
    # Positional RP2040 form: recv,unique,dup,err,tput,min,avg,max
    positional_keys = ["received", "unique", "duplicates", "errors",
                       "throughput_kbps", "min_us", "avg_us", "max_us"]
    if "=" not in body[0] and len(body) <= len(positional_keys):
        out = {}
        for key, val in zip(positional_keys, body):
            out[key] = _to_float(val) if key in {"throughput_kbps", "avg_us"} \
                else _to_int(val)
        return out
    # key=value form.
    out = {}
    for chunk in body:
        if "=" in chunk:
            k, _, v = chunk.partition("=")
            out[k] = _to_float(v)
    return out or None


# --------------------------------------------------------------------------- #
# Statistics
# --------------------------------------------------------------------------- #
def _percentile(values: list[float], pct: float) -> Optional[float]:
    if not values:
        return None
    s = sorted(values)
    k = (len(s) - 1) * (pct / 100.0)
    lo = int(k)
    hi = min(lo + 1, len(s) - 1)
    frac = k - lo
    return s[lo] * (1 - frac) + s[hi] * frac


def compute_stats(packets: list[PacketRecord], expected_packets: int,
                  elapsed_ms: int = 0) -> ModeStats:
    """Compute packet-loss, RSSI and timing statistics from received packets."""
    stats = ModeStats(expected_packets=expected_packets, elapsed_ms=elapsed_ms)
    stats.packets_received = len(packets)

    if packets:
        seqs = [p.seq for p in packets]
        unique = set(seqs)
        stats.unique_seqs = len(unique)
        stats.duplicates = stats.packets_received - stats.unique_seqs
        # Out-of-order: any packet whose seq is less than the running max.
        prev = seqs[0]
        oo = 0
        for s in seqs[1:]:
            if s < prev:
                oo += 1
            prev = max(prev, s)
        stats.out_of_order = oo

    if expected_packets > 0:
        lost = max(0, expected_packets - stats.unique_seqs)
        stats.packet_loss_pct = lost * 100.0 / expected_packets

    rssi_vals = [p.rssi for p in packets if p.rssi is not None]
    if rssi_vals:
        stats.rssi_count = len(rssi_vals)
        stats.rssi_min = round(min(rssi_vals), 1)
        stats.rssi_avg = round(statistics.fmean(rssi_vals), 1)
        stats.rssi_max = round(max(rssi_vals), 1)
        stats.rssi_std = round(statistics.pstdev(rssi_vals), 2) if len(rssi_vals) > 1 else 0.0
        stats.rssi_p95 = round(_percentile(rssi_vals, 95), 1)

    snr_vals = [p.snr for p in packets if p.snr is not None]
    if snr_vals:
        stats.snr_count = len(snr_vals)
        stats.snr_avg = round(statistics.fmean(snr_vals), 2)

    totals = [p.total_us for p in packets if p.total_us is not None]
    if totals:
        stats.total_min_us = min(totals)
        stats.total_avg_us = round(statistics.fmean(totals), 1)
        stats.total_max_us = max(totals)

    return stats


# --------------------------------------------------------------------------- #
# Orchestration
# --------------------------------------------------------------------------- #
class Phase1Runner:
    """Orchestrates one or more Phase 1 modes against a set of serial nodes."""

    def __init__(self, node_ports: dict[str, str], backend_factory: BackendFactory,
                 baud: int = 115200, timeout_s: float = 60.0,
                 start_cmd: str = "S\n", ready_marker: str = "READY",
                 settle_s: float = 1.0, logger: Optional[Callable[[str], None]] = None):
        self.node_ports = node_ports
        self.backend_factory = backend_factory
        self.baud = baud
        self.timeout_s = timeout_s
        self.start_cmd = start_cmd
        self.ready_marker = ready_marker
        self.settle_s = settle_s
        self._log = logger or (lambda _msg: None)

    # -- low-level helpers --------------------------------------------------
    def _open(self, name: str) -> SerialBackend:
        port = self.node_ports.get(name)
        if not port:
            raise KeyError(f"no port configured for node {name!r}")
        self._log(f"  open {name} @ {port}")
        return self.backend_factory(port, self.baud)

    def _wait_ready(self, backend: SerialBackend, max_wait: float = 15.0) -> bool:
        deadline = time.time() + max_wait
        while time.time() < deadline:
            line = backend.readline(timeout=1.0).decode(errors="replace").strip()
            if self.ready_marker in line:
                return True
        return False

    def _collect(self, backend: SerialBackend, timeout: float,
                 collector: list[str], stop_on: tuple[str, ...] = ("RESULT",)
                 ) -> Optional[dict]:
        """Read lines until timeout or a stop marker. Returns parsed footer (if any)."""
        deadline = time.time() + timeout
        result = None
        while time.time() < deadline:
            raw = backend.readline(timeout=0.5)
            if not raw:
                continue
            line = raw.decode(errors="replace").strip()
            if not line:
                continue
            collector.append(line)
            if any(line.startswith(m) or m in line for m in stop_on):
                result = parse_result_line(line)
                if result is None:
                    # Still a stop marker even if unparseable.
                    result = {}
                break
        return result

    # -- per-mode driver ----------------------------------------------------
    def run_mode(self, mode: TestMode) -> ModeResult:
        self._log(f"=== Mode {mode.code}: {mode.name} ===")
        result = ModeResult(
            mode=mode.code, name=mode.name,
            tx_nodes=list(mode.tx_nodes), rx_nodes=list(mode.rx_nodes),
            stats=ModeStats(expected_packets=mode.expected_packets),
        )
        rx_backends: dict[str, SerialBackend] = {}
        tx_backends: dict[str, SerialBackend] = {}
        try:
            # Open + arm RX node(s).
            for name in mode.rx_nodes:
                be = self._open(name)
                rx_backends[name] = be
                self._wait_ready(be)
            # Open TX node(s).
            for name in mode.tx_nodes:
                tx_backends[name] = self._open(name)
            time.sleep(self.settle_s)

            # Arm RX collectors in background threads, one per RX node.
            per_rx_lines: dict[str, list[str]] = {n: [] for n in mode.rx_nodes}
            per_rx_result: dict[str, Optional[dict]] = {n: None for n in mode.rx_nodes}
            threads: list[threading.Thread] = []

            def _rx_collect(name: str, be: SerialBackend) -> None:
                per_rx_result[name] = self._collect(
                    be, timeout=self.timeout_s, collector=per_rx_lines[name])

            for name, be in rx_backends.items():
                t = threading.Thread(target=_rx_collect, args=(name, be),
                                     daemon=True)
                t.start()
                threads.append(t)

            # Arm RX node(s) first so they are listening, then start TX.
            # Both the RP2040 coprocessor RX firmware (firmware/rp2040/src/
            # main.cpp — waits for 'S' on its own UART) and the ESP32 bench
            # firmware consume a start command; the RX command arms receiving
            # while the TX command begins transmission.
            for name, be in rx_backends.items():
                self._log(f"  ARM  -> {name}")
                be.write(self.start_cmd.encode())

            # Staggered TX start (dual-TX mode 1C).
            collect_start = time.time()
            for i, (name, be) in enumerate(tx_backends.items()):
                if i and mode.stagger_ms:
                    time.sleep(mode.stagger_ms / 1000.0)
                self._log(f"  START -> {name}")
                be.write(self.start_cmd.encode())

            for t in threads:
                t.join(timeout=self.timeout_s + 5)
            elapsed_ms = int((time.time() - collect_start) * 1000)

            # Merge packets from all RX nodes (dual-RX mode 1F keeps per-node
            # breakdown in raw_log; aggregated stats span both receivers).
            all_packets: list[PacketRecord] = []
            for name in mode.rx_nodes:
                lines = per_rx_lines[name]
                result.raw_log.extend(f"[{name}] {ln}" for ln in lines)
                for ln in lines:
                    pkt = parse_packet_line(ln)
                    if pkt is not None:
                        all_packets.append(pkt)
            result.stats = compute_stats(
                all_packets, mode.expected_packets, elapsed_ms=elapsed_ms)
            result.packets = all_packets

            n = len(all_packets)
            self._log(f"  {mode.code}: rx={n} unique={result.stats.unique_seqs} "
                      f"loss={result.stats.packet_loss_pct:.1f}% "
                      f"rssi_avg={result.stats.rssi_avg}")
            return result

        except Exception as exc:  # pragma: no cover - hardware error path
            result.ok = False
            result.error = f"{type(exc).__name__}: {exc}"
            self._log(f"  {mode.code} ERROR: {result.error}")
            return result
        finally:
            for be in list(rx_backends.values()) + list(tx_backends.values()):
                be.close()


# --------------------------------------------------------------------------- #
# Output writers
# --------------------------------------------------------------------------- #
CSV_FIELDS = ["index", "seq", "rssi", "snr", "irq_us", "read_us",
              "clear_us", "rx_us", "total_us"]


def write_mode_csv(result: ModeResult, out_dir: Path) -> Path:
    """Write results/phase1/test-<mode>.csv (per-packet rows + stats footer)."""
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"test-{result.mode}.csv"
    with open(path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(CSV_FIELDS)
        for p in result.packets:
            w.writerow([getattr(p, fld) if getattr(p, fld) is not None else ""
                        for fld in CSV_FIELDS])
        # Human-readable footer mirroring the RP2040 RESULT convention.
        w.writerow([])
        s = result.stats
        w.writerow(["# stat", "value"])
        w.writerow(["# packets_received", s.packets_received])
        w.writerow(["# unique_seqs", s.unique_seqs])
        w.writerow(["# duplicates", s.duplicates])
        w.writerow(["# out_of_order", s.out_of_order])
        w.writerow(["# expected_packets", s.expected_packets])
        w.writerow(["# packet_loss_pct", f"{s.packet_loss_pct:.2f}"])
        w.writerow(["# rssi_min", "" if s.rssi_min is None else s.rssi_min])
        w.writerow(["# rssi_avg", "" if s.rssi_avg is None else s.rssi_avg])
        w.writerow(["# rssi_max", "" if s.rssi_max is None else s.rssi_max])
        w.writerow(["# rssi_std", "" if s.rssi_std is None else s.rssi_std])
        w.writerow(["# rssi_p95", "" if s.rssi_p95 is None else s.rssi_p95])
        w.writerow(["# snr_avg", "" if s.snr_avg is None else s.snr_avg])
        w.writerow(["# total_min_us", "" if s.total_min_us is None else s.total_min_us])
        w.writerow(["# total_avg_us", "" if s.total_avg_us is None else s.total_avg_us])
        w.writerow(["# total_max_us", "" if s.total_max_us is None else s.total_max_us])
    return path


def write_summary_json(results: list[ModeResult], out_dir: Path) -> Path:
    """Write results/phase1/summary.json aggregating all modes."""
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / "summary.json"
    payload = {
        "generated_at": int(time.time()),
        "modes": {r.mode: r.to_summary_dict() for r in results},
    }
    with open(path, "w") as f:
        json.dump(payload, f, indent=2, default=str)
    return path


# --------------------------------------------------------------------------- #
# Config loading
# --------------------------------------------------------------------------- #
def load_config(path: Optional[Path]) -> dict:
    """Load node->port mapping + options from a YAML or JSON config file.

    Returns a dict with keys: ``baud`` (int) and ``nodes`` (dict[str,str]).
    Supports the example config in tests/phase1_config.example.yaml.
    """
    cfg: dict = {"baud": 115200, "nodes": {}}
    if path is None:
        return cfg
    text = Path(path).read_text()
    if _yaml is not None:
        loaded = _yaml.safe_load(text) or {}
    else:
        # JSON fallback (YAML without anchors is mostly JSON-compatible for our
        # simple {baud, nodes:{name:port}} shape).
        loaded = json.loads(text)
    cfg["baud"] = int(loaded.get("baud", cfg["baud"]))
    nodes = loaded.get("nodes") or {}
    # Accept either {NAME: {port: ...}} or {NAME: "/dev/..."}.
    for name, val in nodes.items():
        if isinstance(val, dict):
            cfg["nodes"][name] = val.get("port")
        else:
            cfg["nodes"][name] = str(val)
    cfg["baud"] = cfg["baud"]  # keep type-stable
    cfg.setdefault("start_cmd", loaded.get("start_cmd", "S\n"))
    cfg.setdefault("ready_marker", loaded.get("ready_marker", "READY"))
    cfg.setdefault("timeout_s", loaded.get("timeout_s", 60))
    return cfg


# --------------------------------------------------------------------------- #
# Mock data generator (mirrors test_rp2040_speed.py simulate pattern)
# --------------------------------------------------------------------------- #
def make_mock_nodes() -> dict[str, MockSerialBackend]:
    """Build MockSerialBackend nodes emitting a realistic Phase 1 exchange.

    The RX node boots (READY), then on receiving ``S\\n`` emits a canonical
    per-packet CSV stream + RESULT footer. Used by ``--mock`` and the tests.
    """
    def _rx_on_write(text: str) -> list[str]:
        if not text.strip().lower().startswith("s"):
            return []
        lines = ["START",
                 "pkt,seq,rssi,snr,irq_us,read_us,clr_us,rx_us,total_us"]
        for i in range(20):
            rssi = -75.0 + (i % 5)
            snr = 8.0 + (i % 3)
            lines.append(f"{i+1},{i},{rssi:.1f},{snr:.1f},"
                         f"10,{60 + (i % 3)},30,40,{140 + (i % 3)}")
        lines.append("RESULT,20,20,0,0,2600.0,140,141.2,143")
        return lines

    # All nodes share the RX emitter: in any given mode the RX node(s) must
    # stream packets on receiving the start command, and which node is RX
    # varies across the matrix (1D/1E use an ESP32 as RX, 1F uses two). TX
    # nodes also receive the start command but nothing reads their output, so
    # giving them the same emitter is harmless. Without this, modes whose RX
    # is not RP2040-A would block for the full per-mode timeout (the bug that
    # originally caused `--mock --all` to exceed the task runtime budget).
    return {
        "RP2040-A": MockSerialBackend(boot_lines=["BOOT", "READY"],
                                      on_write=_rx_on_write, per_line_delay=0.0),
        "ESP32-B": MockSerialBackend(boot_lines=["READY"],
                                     on_write=_rx_on_write, per_line_delay=0.0),
        "ESP32-C": MockSerialBackend(boot_lines=["READY"],
                                     on_write=_rx_on_write, per_line_delay=0.0),
    }


def mock_backend_factory(mock_nodes: dict[str, MockSerialBackend]) -> BackendFactory:
    """Backend factory that returns the pre-built mock node for a port key.

    The node *name* is used as the port string in mock mode, so the orchestrator
    looks up ``node_ports[name]`` -> "RP2040-A" and we resolve to the mock.
    """
    def _make(port: str, _baud: int = 115200) -> SerialBackend:
        # port is the node name in mock mode
        return mock_nodes[port]
    return _make


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #
def _parse_port_overrides(items: list[str]) -> dict[str, str]:
    out: dict[str, str] = {}
    for item in items or []:
        if "=" not in item:
            raise SystemExit(f"--port expects NAME=/dev/..., got {item!r}")
        name, _, port = item.partition("=")
        out[name.strip()] = port.strip()
    return out


def main(argv: Optional[list[str]] = None) -> int:
    p = argparse.ArgumentParser(
        description="Phase 1 LR2021 test runner (6-mode bench matrix)")
    p.add_argument("--config", type=Path, default=None,
                   help="YAML/JSON config with node->port mapping "
                        "(see tests/phase1_config.example.yaml)")
    p.add_argument("--port", action="append", default=[],
                   metavar="NAME=/dev/...",
                   help="override/add a node port (repeatable)")
    p.add_argument("--baud", type=int, default=115200)
    p.add_argument("--mode", choices=list(TEST_MODES.keys()),
                   help="run a single mode")
    p.add_argument("--all", action="store_true",
                   help="run all 6 modes (1A-1F)")
    p.add_argument("--list-modes", action="store_true",
                   help="print the mode table and exit")
    p.add_argument("--out", type=Path, default=DEFAULT_OUT_DIR,
                   help="output directory (default: results/phase1)")
    p.add_argument("--timeout", type=float, default=60.0,
                   help="per-mode RX collection timeout (seconds)")
    p.add_argument("--mock", action="store_true",
                   help="hardware-free mock run (writes example outputs)")
    args = p.parse_args(argv)

    if args.list_modes:
        print(f"{'Mode':<5}{'TX':<22}{'RX':<22}{'PKT':>5}{'Delay':>8}  Note")
        for m in TEST_MODES.values():
            print(f"{m.code:<5}{'+'.join(m.tx_nodes):<22}"
                  f"{'+'.join(m.rx_nodes):<22}{m.expected_packets:>5}"
                  f"{m.delay_ms:>5}ms  {m.note}")
        return 0

    # Resolve which modes to run.
    if args.all:
        modes = list(TEST_MODES.values())
    elif args.mode:
        modes = [TEST_MODES[args.mode]]
    else:
        p.error("specify --mode <code> or --all (or --list-modes)")

    # Resolve node ports.
    cfg = load_config(args.config)
    node_ports: dict[str, str] = dict(cfg["nodes"])
    node_ports.update(_parse_port_overrides(args.port))
    baud = args.baud or cfg["baud"]

    if args.mock:
        mock_nodes = make_mock_nodes()
        node_ports = {name: name for name in mock_nodes}  # name as port key
        backend_factory = mock_backend_factory(mock_nodes)
    else:
        missing = [n for m in modes for n in m.tx_nodes + m.rx_nodes
                   if n not in node_ports]
        if missing:
            p.error(f"missing port for node(s): {sorted(set(missing))} "
                    f"(use --config or --port NAME=/dev/...)")
        backend_factory = real_backend_factory(baud)

    runner = Phase1Runner(
        node_ports=node_ports, backend_factory=backend_factory, baud=baud,
        timeout_s=args.timeout,
        start_cmd=cfg.get("start_cmd", "S\n"),
        ready_marker=cfg.get("ready_marker", "READY"),
        logger=lambda msg: print(msg, flush=True),
    )

    results: list[ModeResult] = []
    for mode in modes:
        results.append(runner.run_mode(mode))

    # Write outputs.
    for r in results:
        write_mode_csv(r, args.out)
    summary_path = write_summary_json(results, args.out)

    ok = sum(1 for r in results if r.ok)
    print(f"\n{ok}/{len(results)} modes completed -> {args.out}")
    print(f"summary: {summary_path}")
    return 0 if ok == len(results) else 1


if __name__ == "__main__":
    sys.exit(main())
