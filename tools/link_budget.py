#!/usr/bin/env python3
"""LoRa Link Budget Calculator for Pico Balloon Tracker.

Calculates link margin, expected range, throughput, and time-on-air
for given LoRa parameters. Pre-computed scenarios included.

Usage:
    python3 tools/link_budget.py --freq 868 --sf 9 --bw 125 --tx 22 --dist 300
    python3 tools/link_budget.py --scenario tracker
    python3 tools/link_budget.py --scenario mesh_v1
    python3 tools/link_budget.py --list-scenarios
"""

import argparse
import math
import sys

SPEED_OF_LIGHT = 299792458.0

LORA_SENSITIVITY = {
    (7, 125): -123, (7, 250): -120, (7, 500): -117,
    (8, 125): -126, (8, 250): -123,
    (9, 125): -129, (9, 250): -126,
    (10, 125): -132, (10, 250): -129,
    (11, 125): -134.5,
    (12, 125): -137,
}

LORA_AIR_RATE = {
    (7, 125): 5469, (7, 250): 10938, (7, 500): 21875,
    (8, 125): 3125, (8, 250): 6250,
    (9, 125): 1768, (9, 250): 3536,
    (10, 125): 977, (10, 250): 1953,
    (11, 125): 537,
    (12, 125): 293,
}

LORA_MAX_PAYLOAD = {
    7: 222, 8: 222, 9: 115, 10: 51, 11: 51, 12: 51,
}

SCENARIOS = {
    "tracker": {
        "name": "Minimal Tracker (first flight)",
        "freq_mhz": 868.0, "sf": 9, "bw": 125, "tx_dbm": 22,
        "tx_antenna_dbi": 2.15, "rx_antenna_dbi": 5.0,
        "cable_loss_db": 1.0, "distance_km": 300,
        "payload_bytes": 28,
    },
    "mesh_v1": {
        "name": "Mesh V1 (omni, +22 dBm, night-off)",
        "freq_mhz": 2400.0, "sf": 7, "bw": 125, "tx_dbm": 22,
        "tx_antenna_dbi": 2.15, "rx_antenna_dbi": 5.0,
        "cable_loss_db": 1.0, "distance_km": 300,
        "payload_bytes": 200,
    },
    "mesh_v2": {
        "name": "Mesh V2 (PCB Yagi, +30 dBm, night-active)",
        "freq_mhz": 2400.0, "sf": 7, "bw": 125, "tx_dbm": 30,
        "tx_antenna_dbi": 10.0, "rx_antenna_dbi": 12.0,
        "cable_loss_db": 2.0, "distance_km": 300,
        "payload_bytes": 200,
    },
    "tracker_long_range": {
        "name": "Tracker (SF12, max range)",
        "freq_mhz": 868.0, "sf": 12, "bw": 125, "tx_dbm": 22,
        "tx_antenna_dbi": 2.15, "rx_antenna_dbi": 5.0,
        "cable_loss_db": 1.0, "distance_km": 700,
        "payload_bytes": 28,
    },
    "ground_station_2g4": {
        "name": "Ground Station (2.4 GHz FLRC high-rate)",
        "freq_mhz": 2400.0, "sf": 7, "bw": 125, "tx_dbm": 27,
        "tx_antenna_dbi": 12.0, "rx_antenna_dbi": 10.0,
        "cable_loss_db": 2.0, "distance_km": 300,
        "payload_bytes": 222,
    },
}


def free_space_path_loss_db(freq_mhz, distance_km):
    distance_m = distance_km * 1000
    return 20 * math.log10(distance_m) + 20 * math.log10(freq_mhz) + 20 * math.log10(1e6) - 147.55


def get_sensitivity(sf, bw):
    return LORA_SENSITIVITY.get((sf, bw), -130 + sf)


def get_air_rate_bps(sf, bw):
    return LORA_AIR_RATE.get((sf, bw), 0)


def get_max_payload(sf):
    return LORA_MAX_PAYLOAD.get(sf, 51)


def estimate_toa_ms(payload_bytes, sf, bw, cr=4, header=1, crc=1, de=1):
    air_rate = get_air_rate_bps(sf, bw)
    if air_rate == 0:
        return 0
    symbol_duration_ms = (2 ** sf) / bw
    preamble_symbols = 8
    header_bits = 20 if header else 0
    crc_bits = 16 if crc else 0
    payload_bits = payload_bytes * 8 + header_bits + crc_bits
    overhead = 8
    if de and sf > 6:
        overhead = 8 + (sf - 4 if sf > 10 else 0)
    n_payload_symbols = max(1, math.ceil((payload_bits + overhead) / (4 * sf)))
    total_symbols = preamble_symbols + 4.25 + n_payload_symbols * (cr + 4)
    return total_symbols * symbol_duration_ms


def calculate_link(freq_mhz, sf, bw, tx_dbm, tx_antenna_dbi, rx_antenna_dbi,
                   cable_loss_db, distance_km, payload_bytes):
    fspl = free_space_path_loss_db(freq_mhz, distance_km)
    eirp = tx_dbm + tx_antenna_dbi - cable_loss_db
    received_power = eirp - fspl + rx_antenna_dbi
    sensitivity = get_sensitivity(sf, bw)
    link_margin = received_power - sensitivity
    air_rate = get_air_rate_bps(sf, bw)
    toa_ms = estimate_toa_ms(payload_bytes, sf, bw)
    max_payload = get_max_payload(sf)

    if link_margin > 0:
        max_range_km = distance_km * (10 ** (link_margin / 20))
    else:
        max_range_km = distance_km

    return {
        "frequency_mhz": freq_mhz,
        "sf": sf,
        "bw_khz": bw,
        "tx_power_dbm": tx_dbm,
        "tx_antenna_dbi": tx_antenna_dbi,
        "rx_antenna_dbi": rx_antenna_dbi,
        "cable_loss_db": cable_loss_db,
        "eirp_dbm": eirp,
        "distance_km": distance_km,
        "fspl_db": fspl,
        "received_power_dbm": received_power,
        "sensitivity_dbm": sensitivity,
        "link_margin_db": link_margin,
        "air_rate_bps": air_rate,
        "toa_ms": toa_ms,
        "max_payload_bytes": max_payload,
        "payload_bytes": payload_bytes,
        "max_range_km": max_range_km,
        "feasible": payload_bytes <= max_payload and link_margin >= 0,
    }


def print_result(r, name=""):
    if name:
        print(f"\n{'='*50}")
        print(f"  {name}")
        print(f"{'='*50}")
    print(f"  Frequency:      {r['frequency_mhz']:.1f} MHz")
    print(f"  Spreading:      SF{r['sf']} / BW{r['bw_khz']} kHz")
    print(f"  TX Power:       {r['tx_power_dbm']} dBm")
    print(f"  TX Antenna:     {r['tx_antenna_dbi']:.1f} dBi")
    print(f"  RX Antenna:     {r['rx_antenna_dbi']:.1f} dBi")
    print(f"  Cable Loss:     {r['cable_loss_db']:.1f} dB")
    print(f"  EIRP:           {r['eirp_dbm']:.1f} dBm")
    print(f"  Distance:       {r['distance_km']:.0f} km")
    print(f"  FSPL:           {r['fspl_db']:.1f} dB")
    print(f"  RX Power:       {r['received_power_dbm']:.1f} dBm")
    print(f"  Sensitivity:    {r['sensitivity_dbm']:.1f} dBm")
    print(f"  Link Margin:    {r['link_margin_db']:.1f} dB {'OK' if r['link_margin_db'] >= 0 else 'INSUFFICIENT'}")
    print(f"  Max Range:      {r['max_range_km']:.0f} km")
    print(f"  Air Rate:       {r['air_rate_bps']} bps")
    print(f"  Time-on-Air:    {r['toa_ms']:.1f} ms ({r['payload_bytes']} bytes)")
    print(f"  Max Payload:    {r['max_payload_bytes']} bytes")
    print(f"  Feasible:       {'YES' if r['feasible'] else 'NO'}")
    print()


def main():
    parser = argparse.ArgumentParser(description="LoRa Link Budget Calculator")
    parser.add_argument("--freq", type=float, default=868.0, help="Frequency (MHz)")
    parser.add_argument("--sf", type=int, default=9, help="Spreading factor")
    parser.add_argument("--bw", type=int, default=125, help="Bandwidth (kHz)")
    parser.add_argument("--tx", type=int, default=22, help="TX power (dBm)")
    parser.add_argument("--tx-ant", type=float, default=2.15, help="TX antenna gain (dBi)")
    parser.add_argument("--rx-ant", type=float, default=5.0, help="RX antenna gain (dBi)")
    parser.add_argument("--cable-loss", type=float, default=1.0, help="Cable loss (dB)")
    parser.add_argument("--dist", type=float, default=300, help="Distance (km)")
    parser.add_argument("--payload", type=int, default=28, help="Payload size (bytes)")
    parser.add_argument("--scenario", type=str, help="Pre-computed scenario name")
    parser.add_argument("--list-scenarios", action="store_true", help="List scenarios")
    args = parser.parse_args()

    if args.list_scenarios:
        print("Available scenarios:")
        for key, s in SCENARIOS.items():
            print(f"  {key:25s} {s['name']}")
        return

    if args.scenario:
        if args.scenario == "all":
            for key, s in SCENARIOS.items():
                r = calculate_link(**{k: v for k, v in s.items() if k != "name"})
                print_result(r, s["name"])
            return
        s = SCENARIOS.get(args.scenario)
        if not s:
            print(f"Unknown scenario: {args.scenario}")
            print(f"Available: {', '.join(SCENARIOS.keys())}")
            sys.exit(1)
        r = calculate_link(**{k: v for k, v in s.items() if k != "name"})
        print_result(r, s["name"])
        return

    r = calculate_link(
        args.freq, args.sf, args.bw, args.tx, args.tx_ant, args.rx_ant,
        args.cable_loss, args.dist, args.payload,
    )
    print_result(r)


if __name__ == "__main__":
    main()
