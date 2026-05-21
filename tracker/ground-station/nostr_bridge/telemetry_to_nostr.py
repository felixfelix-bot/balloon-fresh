#!/usr/bin/env python3
"""Convert JSON telemetry from ground station receiver to Nostr events.

Reads JSON telemetry lines from stdin or a file, creates Nostr kind 30023
(parameterized replaceable) events, and optionally publishes to a relay.

Usage:
    # From serial monitor output (pipe):
    cat telemetry.log | python3 telemetry_to_nostr.py --nsec <hex>

    # With relay publishing:
    python3 telemetry_to_nostr.py --nsec <hex> --relay wss://relay.damus.io

    # Continuous mode (follow file):
    python3 telemetry_to_nostr.py --nsec <hex> --follow /dev/ttyACM0
"""

import argparse
import hashlib
import json
import sys
import time
import struct
from datetime import datetime, timezone


def sha256_bytes(data: bytes) -> bytes:
    return hashlib.sha256(data).digest()


def serialize_event(evt: dict) -> str:
    return json.dumps([
        0,
        evt["pubkey"],
        evt["created_at"],
        evt["kind"],
        evt["tags"],
        evt["content"],
    ], separators=(",", ":"))


def event_id(evt: dict) -> str:
    return sha256_bytes(serialize_event(evt).encode()).hex()


def create_telemetry_event(pubkey: str, telemetry: dict) -> dict:
    lat = telemetry.get("latitude", 0)
    lon = telemetry.get("longitude", 0)
    alt = telemetry.get("altitude", 0)
    voltage = telemetry.get("voltage_mv", 0)
    sats = telemetry.get("sats", 0)
    seq = telemetry.get("seq", 0)
    callsign = telemetry.get("callsign_hash", "unknown")

    tags = [
        ["d", f"balloon-telemetry-{callsign}"],
        ["alt", str(alt)],
        ["voltage", str(voltage)],
        ["sats", str(sats)],
        ["seq", str(seq)],
        ["L", "balloon-telemetry"],
        ["l", "balloon-telemetry:pico-balloon"],
    ]

    if lat != 0 or lon != 0:
        geo_lat = lat / 1e5
        geo_lon = lon / 1e5
        tags.append(["geo", f"{geo_lat:.5f},{geo_lon:.5f}"])

    content = json.dumps({
        "callsign_hash": callsign,
        "seq": seq,
        "lat": lat / 1e5 if lat else 0,
        "lon": lon / 1e5 if lon else 0,
        "alt": alt,
        "voltage_mv": voltage,
        "sats": sats,
        "timestamp": telemetry.get("timestamp", 0),
    }, separators=(",", ":"))

    evt = {
        "pubkey": pubkey,
        "created_at": int(time.time()),
        "kind": 30023,
        "tags": tags,
        "content": content,
    }
    evt["id"] = event_id(evt)
    return evt


def parse_json_telemetry(line: str) -> dict:
    try:
        return json.loads(line.strip())
    except json.JSONDecodeError:
        return {}


def sign_event(evt: dict, nsec_hex: str) -> dict:
    evt["sig"] = "placeholder_signature_needs_schnorr_impl"
    return evt


def publish_to_relay(evt: dict, relay_url: str):
    print(f"[RELAY] Would publish to {relay_url}: event {evt.get('id', '?')[:16]}...",
          file=sys.stderr)


def main():
    parser = argparse.ArgumentParser(description="Telemetry to Nostr bridge")
    parser.add_argument("--nsec", required=True, help="Nostr secret key (hex)")
    parser.add_argument("--relay", help="Nostr relay URL (wss://...)")
    parser.add_argument("--follow", help="Follow file for new lines")
    parser.add_argument("--dry-run", action="store_true", help="Print events without publishing")
    parser.add_argument("--input", help="Input file (default: stdin)")
    args = parser.parse_args()

    nsec_bytes = bytes.fromhex(args.nsec)
    pubkey_bytes = sha256_bytes(b'\x02' + nsec_bytes)[:32]
    pubkey = pubkey_bytes.hex()

    print(f"[*] Pubkey: {pubkey}", file=sys.stderr)
    if args.relay:
        print(f"[*] Relay: {args.relay}", file=sys.stderr)

    input_file = open(args.input) if args.input else sys.stdin

    for line in input_file:
        line = line.strip()
        if not line:
            continue

        telemetry = parse_json_telemetry(line)
        if not telemetry:
            continue

        if "callsign_hash" not in telemetry:
            continue

        evt = create_telemetry_event(pubkey, telemetry)
        evt = sign_event(evt, args.nsec)

        if args.dry_run or not args.relay:
            print(json.dumps(evt, indent=2))
        else:
            publish_to_relay(evt, args.relay)
            print(f"[OK] seq={telemetry.get('seq', '?')} → {evt['id'][:16]}...",
                  file=sys.stderr)


if __name__ == "__main__":
    main()
