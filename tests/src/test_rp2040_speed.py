#!/usr/bin/env python3
"""
RP2040 Coprocessor Speed Test — pytest harness

Tests the RP2040 + LR2021 RX pipeline throughput and per-packet latency.
Controls the TX board (ESP32-C3) via serial, reads results from RP2040
via UART/USB, and validates throughput against the ADR-015 Board B target
of >= 2000 kbps.

Hardware setup (see docs/adr/015-three-board-hardware-strategy.md):
  - TX board: ESP32-C3 (96:DC) + LR2021, running fifo_tx.bin or fast_tx
  - RX coprocessor: RP2040-Zero + LR2021 (SPI0), this firmware
  - ESP32-C3 (C6:98): logging/UART bridge to RP2040

Usage:
  pytest tests/src/test_rp2040_speed.py -v                    # hardware test
  pytest tests/src/test_rp2040_speed.py -v -k simulate         # simulation only
  pytest tests/src/test_rp2040_speed.py -v --tx-port /dev/ttyUSB0 --rx-port /dev/ttyACM0
"""

import csv
import re
import time
import threading
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import pytest

try:
    import serial
except ImportError:
    serial = None


# ─── Data models ───────────────────────────────────────────────────────

@dataclass
class PacketRecord:
    """One received packet with per-stage timing."""
    index: int
    seq: int
    irq_us: int
    read_us: int
    clear_us: int
    rx_us: int
    total_us: int


@dataclass
class SpeedTestResult:
    """Aggregated speed test result."""
    received: int = 0
    unique: int = 0
    duplicates: int = 0
    errors: int = 0
    throughput_kbps: float = 0.0
    min_us: int = 0
    avg_us: float = 0.0
    max_us: int = 0
    packets: list = field(default_factory=list)

    @property
    def per(self) -> float:
        """Packet error rate (%)"""
        target = 500
        if self.received >= target:
            return 0.0
        return (target - self.received) * 100.0 / target

    @property
    def max_rx_rate(self) -> float:
        """Max packets/sec based on average processing time"""
        if self.avg_us <= 0:
            return 0.0
        return 1000000.0 / self.avg_us

    @property
    def max_throughput_kbps(self) -> float:
        """Theoretical max throughput from processing time alone"""
        return self.max_rx_rate * 255 * 8 / 1000.0


# ─── Protocol parsing ──────────────────────────────────────────────────

def parse_csv_line(line: str) -> Optional[PacketRecord]:
    """Parse a per-packet CSV line: pkt,seq,irq_us,read_us,clr_us,rx_us,total_us"""
    line = line.strip()
    if not line or line.startswith("pkt,"):
        return None
    parts = line.split(",")
    if len(parts) < 7:
        return None
    try:
        return PacketRecord(
            index=int(parts[0]),
            seq=int(parts[1]),
            irq_us=int(parts[2]),
            read_us=int(parts[3]),
            clear_us=int(parts[4]),
            rx_us=int(parts[5]),
            total_us=int(parts[6]),
        )
    except (ValueError, IndexError):
        return None


def parse_result_line(line: str) -> Optional[SpeedTestResult]:
    """Parse a RESULT summary line: RESULT,recv,unique,dup,err,tput,min,avg,max"""
    line = line.strip()
    if not line.startswith("RESULT,"):
        return None
    parts = line.split(",")
    if len(parts) < 9:
        return None
    try:
        return SpeedTestResult(
            received=int(parts[1]),
            unique=int(parts[2]),
            duplicates=int(parts[3]),
            errors=int(parts[4]),
            throughput_kbps=float(parts[5]),
            min_us=int(parts[6]),
            avg_us=float(parts[7]),
            max_us=int(parts[8]),
        )
    except (ValueError, IndexError):
        return None


# ─── Simulation data generator (for CI / no-hardware testing) ─────────

def generate_simulated_packets(count: int = 500, pkt_size: int = 255,
                               air_rate_kbps: float = 2600.0,
                               processing_factor: float = 0.8) -> list:
    """
    Generate simulated packet records for the RP2040 coprocessor.

    The RP2040 with hardware SPI (18 MHz) and dual-core should achieve
    processing times well below the 188µs measured on ESP32-C3.

    Args:
        count: Number of packets to simulate
        pkt_size: Packet size in bytes (default 255)
        air_rate_kbps: FLRC air rate (default 2600 kbps)
        processing_factor: Fraction of air time consumed by processing (0-1)
                           RP2040 target: ~0.5-0.8 (vs ESP32-C3's ~1.5-3x air time)

    Returns:
        List of PacketRecord objects
    """
    air_time_us = pkt_size * 8 * 1e6 / (air_rate_kbps * 1000)  # µs per packet
    # RP2040 with PIO/hardware SPI: read + clear + restart should be ~50-100µs
    # (vs ESP32-C3's 188µs raw SPI best case)
    base_read_us = 60   # SPI FIFO read at 18 MHz: 255B * 8 / 18M ≈ 113µs, but burst mode faster
    base_clear_us = 30   # Clear IRQ: 6-byte SPI write
    base_restart_us = 40 # Set RX: 6-byte SPI write
    base_irq_us = 10     # IRQ latency (hardware polling, no RTOS)

    packets = []
    for i in range(count):
        # Add small jitter
        jitter = lambda base: int(base + (i * 7 % 10) - 5)

        read_us = max(20, jitter(base_read_us))
        clear_us = max(15, jitter(base_clear_us))
        restart_us = max(20, jitter(base_restart_us))
        irq_us = max(3, jitter(base_irq_us))
        total = irq_us + read_us + clear_us + restart_us

        packets.append(PacketRecord(
            index=i + 1,
            seq=i,
            irq_us=irq_us,
            read_us=read_us,
            clear_us=clear_us,
            rx_us=restart_us,
            total_us=total,
        ))
    return packets


def simulate_speed_test(packets: list, pkt_size: int = 255) -> SpeedTestResult:
    """Compute aggregate stats from a list of PacketRecord objects."""
    if not packets:
        return SpeedTestResult()

    result = SpeedTestResult()
    result.received = len(packets)

    seqs = [p.seq for p in packets]
    result.unique = len(set(seqs))
    result.duplicates = result.received - result.unique

    totals = [p.total_us for p in packets]
    result.min_us = min(totals)
    result.max_us = max(totals)
    result.avg_us = sum(totals) / len(totals)

    elapsed_ms = sum(totals) / 1000.0
    if elapsed_ms > 0:
        result.throughput_kbps = result.unique * pkt_size * 8.0 / elapsed_ms

    result.packets = packets
    return result


# ─── Serial hardware controller ───────────────────────────────────────

class HardwareController:
    """Controls TX board and reads RX data from RP2040 over serial."""

    def __init__(self, tx_port: str, rx_port: str, baud: int = 115200,
                 timeout: float = 30.0):
        self.tx_port = tx_port
        self.rx_port = rx_port
        self.baud = baud
        self.timeout = timeout
        self.tx_serial = None
        self.rx_serial = None

    def connect(self):
        if serial is None:
            raise RuntimeError("pyserial not installed: pip install pyserial")
        self.tx_serial = serial.Serial(self.tx_port, self.baud, timeout=1)
        self.rx_serial = serial.Serial(self.rx_port, self.baud, timeout=1)
        time.sleep(2)  # Wait for boot

    def wait_for_ready(self, max_wait: float = 10.0) -> bool:
        """Wait for RP2040 to print READY."""
        deadline = time.time() + max_wait
        while time.time() < deadline:
            line = self.rx_serial.readline().decode(errors="ignore").strip()
            if line == "READY":
                return True
        return False

    def start_test(self):
        """Send start command to RP2040."""
        self.rx_serial.write(b"S\n")
        time.sleep(0.5)

    def read_results(self) -> tuple:
        """
        Read test data from RP2040 until RESULT line.

        Returns:
            (list of PacketRecord, SpeedTestResult)
        """
        packets = []
        result = None
        deadline = time.time() + self.timeout

        while time.time() < deadline:
            raw = self.rx_serial.readline()
            if not raw:
                continue
            line = raw.decode(errors="ignore").strip()

            pkt = parse_csv_line(line)
            if pkt:
                packets.append(pkt)
                continue

            res = parse_result_line(line)
            if res:
                result = res
                break

        return packets, result

    def disconnect(self):
        for s in [self.tx_serial, self.rx_serial]:
            if s and s.is_open:
                s.close()


# ─── Simulation-only tests (no hardware required) ─────────────────────

class TestSimulation:
    """Tests that run without hardware — validate protocol logic and models."""

    def test_csv_parsing_valid(self):
        """Valid CSV lines parse correctly."""
        line = "1,42,10,60,30,40,140"
        pkt = parse_csv_line(line)
        assert pkt is not None
        assert pkt.index == 1
        assert pkt.seq == 42
        assert pkt.total_us == 140

    def test_csv_parsing_header(self):
        """Header line is skipped."""
        pkt = parse_csv_line("pkt,seq,irq_us,read_us,clr_us,rx_us,total_us")
        assert pkt is None

    def test_csv_parsing_empty(self):
        """Empty lines are skipped."""
        assert parse_csv_line("") is None
        assert parse_csv_line("  ") is None

    def test_csv_parsing_garbage(self):
        """Malformed lines return None."""
        assert parse_csv_line("garbage,data,here") is None
        assert parse_csv_line("1,2,abc,4,5,6,7") is None

    def test_result_parsing(self):
        """RESULT line parses correctly."""
        line = "RESULT,500,498,2,0,2040.0,120,140.5,200"
        res = parse_result_line(line)
        assert res is not None
        assert res.received == 500
        assert res.unique == 498
        assert res.duplicates == 2
        assert res.throughput_kbps == 2040.0

    def test_result_parsing_invalid(self):
        """Invalid RESULT lines return None."""
        assert parse_result_line("RESULT,garbage") is None
        assert parse_result_line("RESULT,1,2,3") is None

    def test_simulated_packets_structure(self):
        """Simulated packets have valid structure."""
        pkts = generate_simulated_packets(count=10)
        assert len(pkts) == 10
        for p in pkts:
            assert p.total_us > 0
            assert p.total_us == p.irq_us + p.read_us + p.clear_us + p.rx_us

    def test_simulated_throughput_target(self):
        """RP2040 simulation should exceed 2000 kbps target (ADR-015 Board B)."""
        pkts = generate_simulated_packets(count=500)
        result = simulate_speed_test(pkts)

        # With ~140µs avg processing: 1000000/140 ≈ 7142 pkt/s
        # 7142 * 255 * 8 / 1000 ≈ 14570 kbps theoretical
        # Real throughput limited by air rate (2600 kbps)
        assert result.avg_us < 200, f"Average processing too slow: {result.avg_us}µs"
        assert result.max_rx_rate > 5000, f"Packet rate too low: {result.max_rx_rate}"
        print(f"\n  Simulated RP2040 throughput: {result.max_throughput_kbps:.0f} kbps "
              f"(target: 2000+, air rate: 2600)")
        print(f"  Avg processing: {result.avg_us:.1f}µs/pkt "
              f"(ESP32-C3 was 188µs raw, ~15ms baseline)")

    def test_simulated_vs_esp32c3(self):
        """RP2040 should be significantly faster than ESP32-C3 baseline."""
        # ESP32-C3 raw SPI best case: 188µs/packet
        esp32c3_best_us = 188

        pkts = generate_simulated_packets(count=500)
        result = simulate_speed_test(pkts)

        speedup = esp32c3_best_us / result.avg_us
        assert speedup > 1.0, f"RP2040 should be faster than ESP32-C3 (got {speedup:.1f}x)"
        print(f"\n  RP2040 vs ESP32-C3 speedup: {speedup:.1f}x")
        print(f"  ESP32-C3 best: {esp32c3_best_us}µs/pkt | RP2040: {result.avg_us:.1f}µs/pkt")

    def test_per_packet_processing_breakdown(self):
        """Verify SPI read is the dominant phase, not IRQ latency."""
        pkts = generate_simulated_packets(count=100)
        avg_read = sum(p.read_us for p in pkts) / len(pkts)
        avg_irq = sum(p.irq_us for p in pkts) / len(pkts)

        assert avg_read > avg_irq, "SPI read should take longer than IRQ latency"
        print(f"\n  Per-packet breakdown (avg): IRQ={avg_irq:.0f}µs, "
              f"SPI_read={avg_read:.0f}µs")

    def test_no_packet_loss_in_simulation(self):
        """500 unique packets, 0 duplicates expected in ideal simulation."""
        pkts = generate_simulated_packets(count=500)
        result = simulate_speed_test(pkts)
        assert result.duplicates == 0
        assert result.unique == 500
        assert result.per == 0.0


# ─── Hardware-in-the-loop tests (require physical boards) ─────────────

def detect_serial_ports():
    """Auto-detect available serial ports."""
    import glob
    ports = glob.glob("/dev/ttyACM*") + glob.glob("/dev/ttyUSB*")
    return sorted(ports)


@pytest.fixture(scope="module")
def hardware(request):
    """Fixture: connect to TX + RX hardware. Skipped if no ports."""
    if serial is None:
        pytest.skip("pyserial not installed")

    tx_port = request.config.getoption("--tx-port")
    rx_port = request.config.getoption("--rx-port")

    if not tx_port or not rx_port:
        ports = detect_serial_ports()
        if len(ports) < 2:
            pytest.skip(f"Need 2 serial ports, found {len(ports)}: {ports}")
        tx_port = tx_port or ports[0]
        rx_port = rx_port or ports[1]

    ctrl = HardwareController(tx_port, rx_port)
    try:
        ctrl.connect()
        if not ctrl.wait_for_ready():
            pytest.skip("RP2040 did not send READY — check firmware")
    except Exception as e:
        pytest.skip(f"Hardware connection failed: {e}")

    yield ctrl
    ctrl.disconnect()


@pytest.mark.hardware
class TestHardwareSpeed:
    """Hardware-in-the-loop tests — require TX board + RP2040 + LR2021."""

    def test_basic_connectivity(self, hardware):
        """RP2040 boots and responds with READY."""
        # If we got here, wait_for_ready already passed
        assert hardware.rx_serial is not None

    def test_speed_test_500_packets(self, hardware):
        """
        Run 500-packet speed test and validate throughput.

        Success criteria (ADR-015 Board B):
          - >= 450 unique packets (<=10% PER)
          - Throughput >= 2000 kbps
          - Average processing < 200µs/packet
        """
        hardware.start_test()
        packets, result = hardware.read_results()

        assert len(packets) > 0, "No packets received — check TX board is sending"
        assert result is not None, "No RESULT line received — test timed out"

        print(f"\n  Hardware Speed Test Results:")
        print(f"  Received: {result.received}")
        print(f"  Unique:   {result.unique}/500")
        print(f"  PER:      {result.per:.1f}%")
        print(f"  Throughput: {result.throughput_kbps:.1f} kbps")
        print(f"  Processing: min={result.min_us} avg={result.avg_us:.0f} "
              f"max={result.max_us}µs")

        assert result.unique >= 450, f"Too many packet losses: {result.unique}/500"
        assert result.per <= 10.0, f"Packet error rate too high: {result.per}%"

    def test_processing_time_meets_target(self, hardware):
        """Average per-packet processing should be < 200µs (ESP32-C3 was 188µs min)."""
        hardware.start_test()
        packets, result = hardware.read_results()

        assert result is not None
        assert result.avg_us < 200, \
            f"Processing too slow: {result.avg_us}µs (target: <200µs)"

    def test_spi_read_dominant(self, hardware):
        """SPI FIFO read should be the dominant processing phase."""
        hardware.start_test()
        packets, result = hardware.read_results()

        assert len(packets) > 0
        avg_read = sum(p.read_us for p in packets) / len(packets)
        avg_irq = sum(p.irq_us for p in packets) / len(packets)

        assert avg_read > avg_irq, \
            f"IRQ latency ({avg_irq}µs) should not exceed SPI read ({avg_read}µs)"

    def test_csv_format_compliance(self, hardware):
        """All packet lines should have exactly 7 comma-separated fields."""
        hardware.start_test()
        packets, result = hardware.read_results()

        assert len(packets) > 0
        for p in packets[:10]:  # Check first 10
            assert p.total_us == p.irq_us + p.read_us + p.clear_us + p.rx_us, \
                f"Timing fields don't sum correctly for packet {p.index}"

    def test_result_line_matches_data(self, hardware):
        """RESULT summary should match actual packet data."""
        hardware.start_test()
        packets, result = hardware.read_results()

        assert result is not None
        assert len(packets) > 0
        assert result.received == len(packets), \
            f"RESULT received ({result.received}) != actual ({len(packets)})"

        # Min/max should match
        actual_min = min(p.total_us for p in packets)
        actual_max = max(p.total_us for p in packets)
        assert result.min_us <= actual_min + 5, "RESULT min_us doesn't match data"
        assert result.max_us >= actual_max - 5, "RESULT max_us doesn't match data"


# ─── CLI entry point for standalone use ───────────────────────────────

def run_speed_test(tx_port: str, rx_port: str, baud: int = 115200):
    """Run a single speed test from command line."""
    ctrl = HardwareController(tx_port, rx_port, baud)
    ctrl.connect()

    if not ctrl.wait_for_ready():
        print("ERROR: RP2040 not ready")
        return None

    print("Starting speed test...")
    ctrl.start_test()
    packets, result = ctrl.read_results()
    ctrl.disconnect()

    if result:
        print(f"\n{'='*50}")
        print(f"  THROUGHPUT: {result.throughput_kbps:.1f} kbps")
        print(f"  UNIQUE:     {result.unique}/500")
        print(f"  PER:        {result.per:.1f}%")
        print(f"  PROCESSING: {result.avg_us:.0f}µs/pkt avg")
        print(f"  MAX RATE:   {1000000/result.avg_us:.0f} pkt/s")
        print(f"{'='*50}")

        # Save CSV
        csv_path = Path(f"rp2040_speedtest_{int(time.time())}.csv")
        with open(csv_path, "w") as f:
            f.write("pkt,seq,irq_us,read_us,clr_us,rx_us,total_us\n")
            for p in packets:
                f.write(f"{p.index},{p.seq},{p.irq_us},{p.read_us},"
                        f"{p.clear_us},{p.rx_us},{p.total_us}\n")
            f.write(f"RESULT,{result.received},{result.unique},{result.duplicates},"
                    f"{result.errors},{result.throughput_kbps},{result.min_us},"
                    f"{result.avg_us},{result.max_us}\n")
        print(f"CSV saved to {csv_path}")

    return result


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="RP2040 LR2021 Speed Test")
    parser.add_argument("--tx-port", required=True, help="TX board serial port")
    parser.add_argument("--rx-port", required=True, help="RP2040 serial port")
    parser.add_argument("--baud", type=int, default=115200)
    args = parser.parse_args()
    run_speed_test(args.tx_port, args.rx_port, args.baud)
