#!/usr/bin/env python3
"""
Pico Balloon Ground Station
Receives and decodes 24-byte telemetry packets from balloon tracker.

Requirements: pip install pyserial crcmod
"""

import struct
import sys
import time
import argparse
from dataclasses import dataclass

try:
    import serial
except ImportError:
    print("Install pyserial: pip install pyserial")
    sys.exit(1)

CRC16_TABLE = [
    0x0000, 0x1021, 0x2042, 0x3063, 0x4084, 0x50A5, 0x60C6, 0x70E7,
    0x8108, 0x9129, 0xA14A, 0xB16B, 0xC18C, 0xD1AD, 0xE1CE, 0xF1EF,
    0x1231, 0x0210, 0x3273, 0x2252, 0x52B5, 0x4294, 0x72F7, 0x62D6,
    0x9339, 0x8318, 0xB37B, 0xA35A, 0xD3BD, 0xC39C, 0xF3FF, 0xE3DE,
    0x2462, 0x3443, 0x0420, 0x1401, 0x64E6, 0x74C7, 0x44A4, 0x5485,
    0xA56A, 0xB54B, 0x8528, 0x9509, 0xE5EE, 0xF5CF, 0xC5AC, 0xD58D,
    0x3653, 0x2672, 0x1611, 0x0630, 0x76D7, 0x66F6, 0x5695, 0x46B4,
    0xB75B, 0xA77A, 0x9719, 0x8738, 0xF7DF, 0xE7FE, 0xD79D, 0xC7BC,
    0x48C4, 0x58E5, 0x6886, 0x78A7, 0x0840, 0x1861, 0x2802, 0x3823,
    0xC9CC, 0xD9ED, 0xE98E, 0xF9AF, 0x8948, 0x9969, 0xA90A, 0xB92B,
    0x5AF5, 0x4AD4, 0x7AB7, 0x6A96, 0x1A71, 0x0A50, 0x3A33, 0x2A12,
    0xDBFD, 0xCBDC, 0xFBBF, 0xEB9E, 0x9B79, 0x8B58, 0xBB3B, 0xAB1A,
    0x6CA6, 0x7C87, 0x4CE4, 0x5CC5, 0x2C22, 0x3C03, 0x0C60, 0x1C41,
    0xEDAE, 0xFD8F, 0xCDEC, 0xDDCD, 0xAD2A, 0xBD0B, 0x8D68, 0x9D49,
    0x7E97, 0x6EB6, 0x5ED5, 0x4EF4, 0x3E13, 0x2E32, 0x1E51, 0x0E70,
    0xFF9F, 0xEFBE, 0xDFDD, 0xCFFC, 0xBF1B, 0xAF3A, 0x9F59, 0x8F78,
    0x9188, 0x81A9, 0xB1CA, 0xA1EB, 0xD10C, 0xC12D, 0xF14E, 0xE16F,
    0x1080, 0x00A1, 0x30C2, 0x20E3, 0x5004, 0x4025, 0x7046, 0x6067,
    0x83B9, 0x9398, 0xA3FB, 0xB3DA, 0xC33D, 0xD31C, 0xE37F, 0xF35E,
    0x02B1, 0x1290, 0x22F3, 0x32D2, 0x4235, 0x5214, 0x6277, 0x7256,
    0xB5EA, 0xA5CB, 0x95A8, 0x8589, 0xF56E, 0xE54F, 0xD52C, 0xC50D,
    0x34E2, 0x24C3, 0x14A0, 0x0481, 0x7466, 0x6447, 0x5424, 0x4405,
    0xA7DB, 0xB7FA, 0x8799, 0x97B8, 0xE75F, 0xF77E, 0xC71D, 0xD73C,
    0x26D3, 0x36F2, 0x0691, 0x16B0, 0x6657, 0x7676, 0x4615, 0x5634,
    0xD94C, 0xC96D, 0xF90E, 0xE92F, 0x99C8, 0x89E9, 0xB98A, 0xA9AB,
    0x5844, 0x4865, 0x7806, 0x6827, 0x18C0, 0x08E1, 0x3882, 0x28A3,
    0xCB7D, 0xDB5C, 0xEB3F, 0xFB1E, 0x8BF9, 0x9BD8, 0xABBB, 0xBB9A,
    0x4A75, 0x5A54, 0x6A37, 0x7A16, 0x0AF1, 0x1AD0, 0x2AB3, 0x3A92,
    0xFD2E, 0xED0F, 0xDD6C, 0xCD4D, 0xBDAA, 0xAD8B, 0x9DE8, 0x8DC9,
    0x7C26, 0x6C07, 0x5C64, 0x4C45, 0x3CA2, 0x2C83, 0x1CE0, 0x0CC1,
    0xEF1F, 0xFF3E, 0xCF5D, 0xDF7C, 0xAF9B, 0xBFBA, 0x8FD9, 0x9FF8,
    0x6E17, 0x7E36, 0x4E55, 0x5E74, 0x2E93, 0x3EB2, 0x0ED1, 0x1EF0,
]

def crc16(data: bytes) -> int:
    crc = 0xFFFF
    for b in data:
        crc = ((crc << 8) ^ CRC16_TABLE[(crc >> 8) ^ b]) & 0xFFFF
    return crc

TELEMETRY_FMT = "<IHIiHHhHBBBBH"
TELEMETRY_SIZE = 28

@dataclass
class TelemetryPacket:
    callsign_hash: int
    latitude: float
    longitude: float
    altitude_m: int
    voltage_mv: int
    temp_c: float
    pressure_hpa: float
    sats: int
    tx_mode: int
    antenna: int
    flags: int
    crc_ok: bool

def decode_packet(data: bytes) -> TelemetryPacket | None:
    if len(data) != TELEMETRY_SIZE:
        return None

    received_crc = struct.unpack_from("<H", data, 26)[0]
    calculated_crc = crc16(data[:26])

    vals = struct.unpack(TELEMETRY_FMT, data)
    return TelemetryPacket(
        callsign_hash=vals[0],
        latitude=vals[2] / 1e5,
        longitude=vals[3] / 1e5,
        altitude_m=vals[4],
        voltage_mv=vals[5],
        temp_c=vals[6] / 100.0,
        pressure_hpa=vals[7] / 10.0,
        sats=vals[8],
        tx_mode=vals[9],
        antenna=vals[10],
        flags=vals[11],
        crc_ok=(received_crc == calculated_crc),
    )

def format_packet(pkt: TelemetryPacket) -> str:
    status = "OK" if pkt.crc_ok else "CRC FAIL"
    mode_names = {0: "LoRa", 1: "FLRC", 2: "FSK", 3: "LR-FHSS", 4: "SubGHz"}
    mode = mode_names.get(pkt.tx_mode, f"?{pkt.tx_mode}")
    return (
        f"[{status}] {time.strftime('%H:%M:%S')} | "
        f"Lat:{pkt.latitude:+.4f} Lon:{pkt.longitude:+.4f} "
        f"Alt:{pkt.altitude_m}m | "
        f"{pkt.temp_c:.1f}C {pkt.pressure_hpa:.1f}hPa | "
        f"Vcap:{pkt.voltage_mv}mV | "
        f"Ant:{pkt.antenna} Mode:{mode} Sats:{pkt.sats}"
    )

def decode_json_line(line: str) -> TelemetryPacket | None:
    import json
    try:
        j = json.loads(line)
    except json.JSONDecodeError:
        return None

    if j.get("type") != "telemetry":
        return None

    return TelemetryPacket(
        callsign_hash=j.get("callsign_hash", 0),
        latitude=j.get("lat", 0),
        longitude=j.get("lon", 0),
        altitude_m=j.get("alt", 0),
        voltage_mv=j.get("voltage_mv", 0),
        temp_c=j.get("temp_c", 0),
        pressure_hpa=j.get("pressure_hpa", 0),
        sats=j.get("sats", 0),
        tx_mode=j.get("tx_mode", 0),
        antenna=j.get("antenna", 0),
        flags=j.get("flags", 0),
        crc_ok=True,
    )

def main():
    parser = argparse.ArgumentParser(description="Pico Balloon Ground Station")
    parser.add_argument("port", help="Serial port (e.g. /dev/ttyUSB0)")
    parser.add_argument("-b", "--baud", type=int, default=115200, help="Baud rate")
    parser.add_argument("--mode", choices=["json", "binary"], default="json",
                        help="Input mode: json (from gs_main.cpp) or binary (raw frames)")
    args = parser.parse_args()

    print(f"Ground Station - listening on {args.port} @ {args.baud} baud ({args.mode} mode)")
    print(f"Waiting for telemetry packets...\n")

    buf = bytearray()
    with serial.Serial(args.port, args.baud, timeout=1) as ser:
        while True:
            data = ser.read(256)
            if data:
                buf.extend(data)

            if args.mode == "json":
                while b'\n' in buf:
                    line, buf = buf.split(b'\n', 1)
                    text = line.decode('utf-8', errors='replace').strip()
                    if not text:
                        continue
                    pkt = decode_json_line(text)
                    if pkt:
                        print(format_packet(pkt))
            else:
                while len(buf) >= TELEMETRY_SIZE:
                    idx = buf.find(b'\x42\x4C\x4E')
                    if idx < 0:
                        buf = buf[-(TELEMETRY_SIZE - 1):]
                        break

                    if idx > 0:
                        buf = buf[idx:]

                    if len(buf) >= TELEMETRY_SIZE:
                        pkt_data = bytes(buf[:TELEMETRY_SIZE])
                        buf = buf[TELEMETRY_SIZE:]
                        pkt = decode_packet(pkt_data)
                        if pkt:
                            print(format_packet(pkt))

if __name__ == "__main__":
    main()
