#!/usr/bin/env python3
"""LR2021 ESP-IDF Benchmarker - Automated Test Runner

Usage:
    python run_benchmark.py --tx /dev/ttyACM2 --rx /dev/ttyACM3 --test lora-baseline
    python run_benchmark.py --tx /dev/ttyACM2 --rx /dev/ttyACM3 --test flrc-sweep
    python run_benchmark.py --tx /dev/ttyACM2 --rx /dev/ttyACM3 --test flrc-2g4
    python run_benchmark.py --tx /dev/ttyACM2 --rx /dev/ttyACM3 --test power-sweep
    python run_benchmark.py --tx /dev/ttyACM2 --rx /dev/ttyACM3 --test all
"""

import argparse
import csv
import serial
import sys
import threading
import time
import re
from dataclasses import dataclass, field
from typing import Optional

@dataclass
class BenchResult:
    test_name: str = ""
    mode: str = ""
    freq: float = 0
    bitrate: int = 0
    sf: int = 0
    bw: float = 0
    cr: int = 0
    power: int = 0
    pkt_size: int = 0
    tx_delay: int = 0
    preamble: int = 0
    tx_sent: int = 0
    tx_errors: int = 0
    tx_elapsed_ms: int = 0
    tx_throughput_kbps: float = 0
    rx_received: int = 0
    rx_crc_errors: int = 0
    rx_lost: int = 0
    rx_total_sent: int = 0
    rx_elapsed_ms: int = 0
    rx_throughput_kbps: float = 0
    per_pct: float = 0
    ber_pct: float = 0
    avg_rssi: float = 0
    min_rssi: int = 0
    max_rssi: int = 0
    avg_snr: float = 0
    payload_corrupt: int = 0
    bit_errors: int = 0
    bits_checked: int = 0
    out_of_order: int = 0
    seq_gaps: str = ""

    def to_csv_row(self):
        return [self.test_name, self.mode, self.freq, self.bitrate, self.sf, self.bw,
                self.cr, self.power, self.pkt_size, self.tx_delay, self.preamble,
                self.tx_sent, self.tx_errors, self.tx_elapsed_ms, self.tx_throughput_kbps,
                self.rx_received, self.rx_crc_errors, self.rx_lost, self.rx_total_sent,
                self.rx_elapsed_ms, self.rx_throughput_kbps, self.per_pct, self.ber_pct,
                self.avg_rssi, self.min_rssi, self.max_rssi, self.avg_snr,
                self.payload_corrupt, self.bit_errors, self.bits_checked,
                self.out_of_order, self.seq_gaps]

CSV_HEADER = ["test_name", "mode", "freq", "bitrate", "sf", "bw", "cr", "power",
              "pkt_size", "tx_delay", "preamble", "tx_sent", "tx_errors",
              "tx_elapsed_ms", "tx_throughput_kbps", "rx_received", "rx_crc_errors",
              "rx_lost", "rx_total_sent", "rx_elapsed_ms", "rx_throughput_kbps",
              "per_pct", "ber_pct", "avg_rssi", "min_rssi", "max_rssi", "avg_snr",
              "payload_corrupt", "bit_errors", "bits_checked", "out_of_order", "seq_gaps"]


class BenchRunner:
    def __init__(self, tx_port: str, rx_port: str, baud: int = 115200):
        self.tx_port = tx_port
        self.rx_port = rx_port
        self.baud = baud
        self.rx_ser: Optional[serial.Serial] = None
        self.tx_ser: Optional[serial.Serial] = None
        self._stop = False
        self._rx_lines: list[str] = []
        self._tx_lines: list[str] = []
        self._rx_thread: Optional[threading.Thread] = None
        self._tx_thread: Optional[threading.Thread] = None
        self.results: list[BenchResult] = []

    def open(self):
        self.rx_ser = serial.Serial(self.rx_port, self.baud, timeout=1)
        self.tx_ser = serial.Serial(self.tx_port, self.baud, timeout=1)
        time.sleep(0.5)
        for s in [self.rx_ser, self.tx_ser]:
            while s.in_waiting:
                s.read(s.in_waiting)
        self._stop = False
        self._rx_thread = threading.Thread(target=self._reader, args=(self.rx_ser, self._rx_lines), daemon=True)
        self._tx_thread = threading.Thread(target=self._reader, args=(self.tx_ser, self._tx_lines), daemon=True)
        self._rx_thread.start()
        self._tx_thread.start()

    def close(self):
        self._stop = True
        time.sleep(0.5)
        if self.rx_ser:
            self.rx_ser.close()
        if self.tx_ser:
            self.tx_ser.close()

    def _reader(self, ser, lines):
        while not self._stop:
            if ser.in_waiting:
                data = ser.read(ser.in_waiting).decode(errors='replace')
                for line in data.strip().split('\n'):
                    line = line.strip()
                    if line:
                        lines.append(line)
            else:
                time.sleep(0.02)

    def _cmd(self, ser, cmd, delay=0.3):
        ser.write((cmd + '\n').encode())
        time.sleep(delay)

    def _drain(self):
        self._rx_lines.clear()
        self._tx_lines.clear()
        time.sleep(0.2)

    def _wait_for(self, lines, marker, timeout=60):
        start = time.time()
        collected = []
        while time.time() - start < timeout:
            while lines:
                line = lines.pop(0)
                collected.append(line)
                if marker in line:
                    return collected
            time.sleep(0.1)
        return collected

    def _parse_kv(self, lines, prefix):
        result = {}
        for line in lines:
            m = re.match(r'I \(\d+\) BENCH: ' + prefix + r',(.+)', line)
            if m:
                try:
                    val = float(m.group(1))
                    result[prefix] = val
                except ValueError:
                    result[prefix] = m.group(1)
        return result

    def _parse_results(self, lines, side):
        r = {}
        for line in lines:
            m = re.match(r'I \(\d+\) BENCH: (\w+),(.+)', line)
            if m:
                key, val = m.group(1), m.group(2)
                try:
                    r[key] = float(val) if '.' in val else int(val)
                except ValueError:
                    r[key] = val
        return r

    def run_test(self, name, mode, freq, bitrate=0, sf=0, bw=0, cr=0x02,
                 power=22, pkt_size=100, count=100, tx_delay=20, preamble=16,
                 timeout=60):
        self._drain()

        max_pwr = 12 if freq > 1500 else 22
        power = min(power, max_pwr)

        cr_val = cr
        if mode == "LORA":
            cr_str = str(cr)
        else:
            cr_str = f"0x{cr:02X}"

        # Setup RX
        self._cmd(self.rx_ser, f'MODE {mode}')
        self._cmd(self.rx_ser, f'FREQ {freq}')
        if mode == "FLRC" and bitrate:
            self._cmd(self.rx_ser, f'BR {bitrate}')
        if mode == "LORA" and sf:
            self._cmd(self.rx_ser, f'SF {sf}')
        if mode == "LORA" and bw:
            self._cmd(self.rx_ser, f'BW {bw}')
        self._cmd(self.rx_ser, f'CR {cr_str}')
        self._cmd(self.rx_ser, f'PWR {power}')
        self._cmd(self.rx_ser, f'SIZE {pkt_size}')
        self._cmd(self.rx_ser, f'COUNT {count}')
        self._cmd(self.rx_ser, f'PREAMBLE {preamble}')
        self._cmd(self.rx_ser, 'ROLE RX')
        self._cmd(self.rx_ser, 'RUN', 1.0)
        time.sleep(1.5)

        # Setup TX
        self._cmd(self.tx_ser, f'MODE {mode}')
        self._cmd(self.tx_ser, f'FREQ {freq}')
        if mode == "FLRC" and bitrate:
            self._cmd(self.tx_ser, f'BR {bitrate}')
        if mode == "LORA" and sf:
            self._cmd(self.tx_ser, f'SF {sf}')
        if mode == "LORA" and bw:
            self._cmd(self.tx_ser, f'BW {bw}')
        self._cmd(self.tx_ser, f'CR {cr_str}')
        self._cmd(self.tx_ser, f'PWR {power}')
        self._cmd(self.tx_ser, f'SIZE {pkt_size}')
        self._cmd(self.tx_ser, f'COUNT {count}')
        self._cmd(self.tx_ser, f'DELAY {tx_delay}')
        self._cmd(self.tx_ser, f'PREAMBLE {preamble}')
        self._cmd(self.tx_ser, 'ROLE TX')
        self._cmd(self.tx_ser, 'RUN', 0.5)

        # Wait for completion
        rx_lines = self._wait_for(self._rx_lines, "RX END", timeout)
        tx_lines = self._wait_for(self._tx_lines, "TX END", timeout)

        rx_r = self._parse_results(rx_lines, "RX")
        tx_r = self._parse_results(tx_lines, "TX")

        result = BenchResult(
            test_name=name,
            mode=mode,
            freq=freq,
            bitrate=bitrate,
            sf=sf,
            bw=bw,
            cr=cr_val,
            power=power,
            pkt_size=pkt_size,
            tx_delay=tx_delay,
            preamble=preamble,
            tx_sent=int(tx_r.get('sent', 0)),
            tx_errors=int(tx_r.get('tx_errors', 0)),
            tx_elapsed_ms=int(tx_r.get('elapsed_ms', 0)),
            tx_throughput_kbps=tx_r.get('throughput_kbps', 0),
            rx_received=int(rx_r.get('received', 0)),
            rx_crc_errors=int(rx_r.get('crc_errors', 0)),
            rx_lost=int(rx_r.get('lost', 0)),
            rx_total_sent=int(rx_r.get('total_sent_by_tx', 0)),
            rx_elapsed_ms=int(rx_r.get('elapsed_ms', 0)),
            rx_throughput_kbps=rx_r.get('throughput_kbps', 0),
            per_pct=rx_r.get('per_pct', 0),
            ber_pct=rx_r.get('ber_pct', 0),
            avg_rssi=rx_r.get('avg_rssi', 0),
            min_rssi=int(rx_r.get('min_rssi', 0)),
            max_rssi=int(rx_r.get('max_rssi', 0)),
            avg_snr=rx_r.get('avg_snr', 0),
            payload_corrupt=int(rx_r.get('payload_corrupt', 0)),
            bit_errors=int(rx_r.get('bit_errors_total', 0)),
            bits_checked=int(rx_r.get('bits_checked_total', 0)),
            out_of_order=int(rx_r.get('out_of_order', 0)),
        )

        self.results.append(result)
        status = "PASS" if result.per_pct == 0 and result.tx_errors == 0 else "FAIL"
        print(f"  {name}: {status} | TX={result.tx_sent}/{count} RX={result.rx_received}/{result.rx_total_sent} "
              f"PER={result.per_pct:.1f}% BER={result.ber_pct:.6f}% Tput={result.tx_throughput_kbps:.1f}kbps "
              f"RSSI={result.avg_rssi:.0f}dBm")
        return result

    def save_csv(self, filename):
        with open(filename, 'w', newline='') as f:
            w = csv.writer(f)
            w.writerow(CSV_HEADER)
            for r in self.results:
                w.writerow(r.to_csv_row())
        print(f"Results saved to {filename}")


def test_lora_baseline(runner):
    print("\n=== LoRa Baseline (868 MHz) ===")
    runner.run_test("L1-lora-sf9", "LORA", 868.0, sf=9, bw=125, cr=7,
                    power=22, pkt_size=28, count=10, tx_delay=1000)


def test_flrc_sweep(runner):
    print("\n=== FLRC Bit Rate Sweep (868 MHz) ===")
    for br in [260, 325, 520, 650, 1040, 1300, 2080, 2600]:
        runner.run_test(f"F-{br}", "FLRC", 868.0, bitrate=br, cr=0x02,
                        power=22, pkt_size=100, count=100, tx_delay=20)


def test_flrc_2g4(runner):
    print("\n=== FLRC 2.4 GHz Tests ===")
    for br in [325, 650, 1300, 2600]:
        runner.run_test(f"2G4-{br}", "FLRC", 2450.0, bitrate=br, cr=0x02,
                        power=12, pkt_size=100, count=100, tx_delay=20)


def test_power_sweep(runner):
    print("\n=== Power Sweep (868 MHz FLRC 1300 kbps) ===")
    for pwr in [22, 18, 14, 10, 6, 2, -2, -6]:
        runner.run_test(f"PWR-{pwr:+d}", "FLRC", 868.0, bitrate=1300, cr=0x02,
                        power=pwr, pkt_size=100, count=50, tx_delay=20)


def test_power_sweep_2g4(runner):
    print("\n=== Power Sweep (2.4 GHz FLRC 1300 kbps) ===")
    for pwr in [12, 8, 4, 0, -4, -8, -12, -16]:
        runner.run_test(f"2G4-PWR-{pwr:+d}", "FLRC", 2450.0, bitrate=1300, cr=0x02,
                        power=pwr, pkt_size=100, count=50, tx_delay=20)


def test_pkt_size_sweep(runner):
    print("\n=== Packet Size Sweep (868 MHz FLRC 1300 kbps) ===")
    for size in [20, 50, 100, 150, 200, 255]:
        runner.run_test(f"SIZE-{size}", "FLRC", 868.0, bitrate=1300, cr=0x02,
                        power=22, pkt_size=size, count=100, tx_delay=20)


TESTS = {
    "lora-baseline": test_lora_baseline,
    "flrc-sweep": test_flrc_sweep,
    "flrc-2g4": test_flrc_2g4,
    "power-sweep": test_power_sweep,
    "power-sweep-2g4": test_power_sweep_2g4,
    "pkt-size-sweep": test_pkt_size_sweep,
    "all": lambda r: [t(r) for t in [test_lora_baseline, test_flrc_sweep, test_flrc_2g4,
                                       test_power_sweep, test_pkt_size_sweep]],
}


def main():
    parser = argparse.ArgumentParser(description="LR2021 Benchmarker Test Runner")
    parser.add_argument("--tx", required=True, help="TX serial port")
    parser.add_argument("--rx", required=True, help="RX serial port")
    parser.add_argument("--test", required=True, choices=list(TESTS.keys()), help="Test to run")
    parser.add_argument("--output", "-o", default="benchmark_results.csv", help="Output CSV file")
    args = parser.parse_args()

    runner = BenchRunner(args.tx, args.rx)
    try:
        runner.open()
        print(f"Connected: TX={args.tx} RX={args.rx}")
        time.sleep(1)
        TESTS[args.test](runner)
    except KeyboardInterrupt:
        print("\nInterrupted")
    finally:
        runner.close()
        if runner.results:
            runner.save_csv(args.output)
            print(f"\n{len(runner.results)} tests completed")
            passed = sum(1 for r in runner.results if r.per_pct == 0 and r.tx_errors == 0)
            print(f"Passed: {passed}/{len(runner.results)}")


if __name__ == "__main__":
    main()
