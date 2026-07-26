#!/usr/bin/env python3
"""
Air-time calculator for LR2021 LoRa + FLRC modes.
Computes exact on-air time for 32-byte and 255-byte payloads in all 14 sweep phases.

LoRa formula: Semtech AN1200.13 (SX127x modem, also valid for SX1280/LR2021 LoRa)
  T_sym = 2^SF / BW
  PayloadSymbNb = 8 + ceil( max(8*PL - 4*SF + 28 + 16*CRC, 0) / (4*(SF - 2*DE)) ) * (CR_denom)
  T_packet = (preamble + 4.25 + PayloadSymbNb) * T_sym
  where:
    CRC = 1 (hardware CRC on)
    CR_denom = 5 for CR 4/5 (CR param = 1)
    DE = 1 when T_sym > 16ms (low data rate optimize)
    preamble = 8 symbols

FLRC formula (simple bitrate):
  T_packet = (preamble_bits + sync_bits + payload_bits + crc_bits) / bitrate
  preamble = 16 bits (from packet params agcPblLen=3 → 16b)
  sync = 32 bits (sync word matched)
  crc = 0 (FLRC CRC off in sweep firmware — app-layer CRC handles integrity)
"""

import math

# Phase table (exact copy from firmware)
# (name, type, freq, sf, bw_hz, cr_param, flrc_kbps, pktCount, slot_s)
phases = [
    ("HF-LoRa-SF7",   "LoRa", 2440, 7,  812500, 1, None, 50, 15),
    ("HF-LoRa-SF9",   "LoRa", 2440, 9,  812500, 1, None, 50, 15),
    ("HF-LoRa-SF12",  "LoRa", 2440, 12, 812500, 1, None, 30, 30),
    ("HF-FLRC-2600",  "FLRC", 2440, 0,  0,      0, 2600, 200, 8),
    ("HF-FLRC-1300",  "FLRC", 2440, 0,  0,      0, 1300, 200, 8),
    ("HF-FLRC-650",   "FLRC", 2440, 0,  0,      0, 650,  200, 8),
    ("HF-FLRC-325",   "FLRC", 2440, 0,  0,      0, 325,  200, 8),
    ("LF-LoRa-SF7",   "LoRa", 868,  7,  250000, 1, None, 50, 8),
    ("LF-LoRa-SF9",   "LoRa", 868,  9,  250000, 1, None, 50, 20),
    ("LF-LoRa-SF12",  "LoRa", 868,  12, 250000, 1, None, 20, 50),
    ("LF-FLRC-2600",  "FLRC", 868,  0,  0,      0, 2600, 200, 8),
    ("LF-FLRC-1300",  "FLRC", 868,  0,  0,      0, 1300, 200, 8),
    ("LF-FLRC-650",   "FLRC", 868,  0,  0,      0, 650,  200, 8),
    ("LF-FLRC-325",   "FLRC", 868,  0,  0,      0, 325,  200, 8),
]

def lora_airtime_ms(pl, sf, bw_hz, cr_param=1, preamble=8, crc=True):
    """Exact LoRa air time in milliseconds."""
    t_sym = (2 ** sf) / bw_hz  # seconds
    de = 1 if t_sym > 0.016 else 0  # low data rate optimize
    crc_val = 1 if crc else 0
    cr_denom = cr_param + 4  # CR=1 → 5 (4/5 rate)
    numerator = 8 * pl - 4 * sf + 28 + 16 * crc_val
    if numerator < 0:
        numerator = 0
    payload_symb = 8 + math.ceil(numerator / (4 * (sf - 2 * de))) * cr_denom
    t_packet = (preamble + 4.25 + payload_symb) * t_sym
    return t_packet * 1000, de

def flrc_airtime_ms(pl, bitrate_kbps, preamble_bits=16, sync_bits=32, crc_bits=0):
    """FLRC air time in milliseconds."""
    total_bits = preamble_bits + sync_bits + pl * 8 + crc_bits
    return (total_bits / (bitrate_kbps * 1000)) * 1000

print("=" * 110)
print(f"{'Phase':<16} {'Type':<5} {'BW/BR':<12} {'PL':>4}  {'T_air':>10}  {'LDRO':>5}  {'pkts fit':>9}  {'pktCount':>9}  {'slot':>5}  {'feasible':>8}")
print("=" * 110)

for pl in [32, 255]:
    print(f"\n{'─'*22} PAYLOAD = {pl} bytes {'─'*22}")
    for name, typ, freq, sf, bw, cr, flrc_br, pkt_count, slot_s in phases:
        if typ == "LoRa":
            t_ms, de = lora_airtime_ms(pl, sf, bw, cr)
            bw_str = f"{bw//1000}kHz"
            ldro_str = f"{'YES' if de else 'no'}"
        else:
            t_ms = flrc_airtime_ms(pl, flrc_br)
            de = 0
            bw_str = f"{flrc_br}kbps"
            ldro_str = "—"

        pkts_fit = int((slot_s * 1000) / t_ms) if t_ms > 0 else 999
        feasible = "YES" if pkts_fit >= 5 else ("MARGINAL" if pkts_fit >= 3 else "NO")
        # Add TX turnaround overhead (~3ms per packet for SPI + FIFO write)
        t_with_overhead = t_ms + 3
        pkts_fit_realistic = int((slot_s * 1000) / t_with_overhead) if t_with_overhead > 0 else 999

        fit_str = f"{pkts_fit_realistic}/{pkt_count}"
        print(f"{name:<16} {typ:<5} {bw_str:<12} {pl:>4}  {t_ms:>8.1f}ms  {ldro_str:>5}  {fit_str:>9}  {pkt_count:>9}  {slot_s:>4}s  {feasible:>8}")

    print()

# Detailed breakdown for 255 bytes
print("\n" + "=" * 90)
print("DETAILED 255-BYTE BREAKDOWN")
print("=" * 90)
for name, typ, freq, sf, bw, cr, flrc_br, pkt_count, slot_s in phases:
    if typ == "LoRa":
        t_ms, de = lora_airtime_ms(255, sf, bw, cr)
        t_sym = (2 ** sf) / bw * 1000
        bw_str = f"BW={bw//1000}kHz"
        extra = f"T_sym={t_sym:.2f}ms LDRO={de}"
    else:
        t_ms = flrc_airtime_ms(255, flrc_br)
        bw_str = f"BR={flrc_br}kbps"
        extra = ""

    t_with_overhead = t_ms + 3
    pkts_in_slot = int((slot_s * 1000) / t_with_overhead)
    utilization = min(pkts_in_slot, pkt_count) / pkt_count * 100

    print(f"  {name:<16} {bw_str:<14} {t_ms:>8.2f}ms/pkt  {extra:<28} → {pkts_in_slot}pkts/{pkt_count} ({utilization:.0f}% slot used)")
