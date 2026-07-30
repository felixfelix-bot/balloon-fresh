#!/usr/bin/env python3
"""
mock_template.py — Generate fake EHASH_TEMPLATE binary messages for testing.

Produces length-prefixed EHASH_TEMPLATE L7 envelopes (type byte + payload)
that can be piped to stratum_server.py's --template-input stdin.

Framing format (per stratum_server.py convention):
    [2-byte LE length] [L7 envelope bytes]

Usage:
    # Generate one template and print to stdout
    python3 mock_template.py

    # Generate templates every 30 seconds (pipe to stratum server)
    python3 mock_template.py --loop --interval 30 | python3 stratum_server.py --template-input stdin

    # Write to a file
    python3 mock_template.py --output templates.bin

No external dependencies — Python stdlib only.
"""

import argparse
import os
import struct
import sys
import time

# Add parent dir to path so we can import ehash_codec
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ehash_codec import (
    EHASH_PROTO_VERSION,
    EhashTemplate,
    encode_template_envelope,
)


def make_fake_template(job_id: int = 1) -> EhashTemplate:
    """Create a realistic-looking fake block template for testing.

    Uses Bitcoin testnet-like values. The hashes are deterministic but fake.
    """
    # Deterministic fake prevhash (32 bytes) — pattern for easy identification
    prevhash = bytes(range(32))  # 00 01 02 ... 1f

    # Bitcoin mainnet-like values
    btc_version = 0x20000000
    nbits = 0x1D00FFFF  # Genesis-block difficulty target
    ntime = int(time.time())  # Current time

    # Fake coinbase parts (typical pool coinbase structure)
    coinbase1 = bytes(
        0x01,  # TX version
        0x00, 0x00,  # TX input count (1)
        0x00, *([0] * 31),  # Previous TX hash (null - coinbase)
        0xFF, 0xFF, 0xFF, 0xFF,  # Previous TX out index
        0x03,  # Script length
    ) if False else b"\x01\x00\x00\x01" + b"\x00" * 32 + b"\xff\xff\xff\xff\x03"

    # Coinbase script: block height (simplified BIP34)
    coinbase1 += b"/ehash-mock/"  # Pool identifier
    coinbase1 += struct.pack("<I", job_id)  # Job ID for uniqueness

    coinbase2 = (
        b"\xff\xff\xff\xff"  # Sequence
        + b"\x01"  # TX output count (1)
        + b"\x00\xf2\x05\x2a\x01"  # Output value (dummy)
        + b"\x19"  # Script length (25 bytes)
        + b"\x76\xa9\x14"  # OP_DUP OP_HASH160
        + bytes(range(20))  # 20-byte pubkey hash (fake)
        + b"\x88\xac"  # OP_EQUALVERIFY OP_CHECKSIG
        + b"\x00"  # Locktime
    )

    # Two fake merkle branches (32 bytes each)
    branch1 = bytes([(i * 7 + 3) & 0xFF for i in range(32)])
    branch2 = bytes([(i * 11 + 5) & 0xFF for i in range(32)])

    return EhashTemplate(
        version=EHASH_PROTO_VERSION,
        job_id=job_id,
        prevhash=prevhash,
        btc_version=btc_version,
        nbits=nbits,
        ntime=ntime,
        coinbase1=coinbase1,
        coinbase2=coinbase2,
        merkle_branches=[branch1, branch2],
        clean_jobs=1,
    )


def make_minimal_template(job_id: int = 1) -> EhashTemplate:
    """Create a minimal template (empty coinbase, no merkle branches).

    This is the 55-byte minimum from the spec's size analysis.
    """
    return EhashTemplate(
        version=EHASH_PROTO_VERSION,
        job_id=job_id,
        prevhash=bytes(range(32)),
        btc_version=0x20000000,
        nbits=0x1D00FFFF,
        ntime=int(time.time()),
        coinbase1=b"",
        coinbase2=b"",
        merkle_branches=[],
        clean_jobs=1,
    )


def frame_message(envelope: bytes) -> bytes:
    """Wrap an L7 envelope in a 2-byte LE length prefix."""
    return struct.pack("<H", len(envelope)) + envelope


def write_template(output, tmpl: EhashTemplate) -> None:
    """Write a single framed template to the output stream (binary mode)."""
    envelope = encode_template_envelope(tmpl)
    framed = frame_message(envelope)
    output.write(framed)
    output.flush()


def main():
    parser = argparse.ArgumentParser(
        description="Generate fake EHASH_TEMPLATE binary messages for testing"
    )
    parser.add_argument(
        "--loop", action="store_true", help="Generate templates continuously"
    )
    parser.add_argument(
        "--interval",
        type=float,
        default=30.0,
        help="Seconds between templates in loop mode (default: 30)",
    )
    parser.add_argument(
        "--job-id-start", type=int, default=1, help="Starting job ID (default: 1)"
    )
    parser.add_argument(
        "--minimal", action="store_true", help="Generate minimal templates (55 bytes)"
    )
    parser.add_argument(
        "--output", "-o", default=None, help="Output file (default: stdout)"
    )
    args = parser.parse_args()

    if args.output:
        out = open(args.output, "wb")
    else:
        out = sys.stdout.buffer

    job_id = args.job_id_start

    try:
        if args.loop:
            while True:
                tmpl = (
                    make_minimal_template(job_id)
                    if args.minimal
                    else make_fake_template(job_id)
                )
                write_template(out, tmpl)
                print(
                    f"[mock] Generated template job_id={job_id} "
                    f"({len(encode_template_envelope(tmpl))} bytes envelope)",
                    file=sys.stderr,
                )
                job_id += 1
                time.sleep(args.interval)
        else:
            tmpl = (
                make_minimal_template(job_id)
                if args.minimal
                else make_fake_template(job_id)
            )
            write_template(out, tmpl)
            print(
                f"[mock] Generated template job_id={job_id} "
                f"({len(encode_template_envelope(tmpl))} bytes envelope)",
                file=sys.stderr,
            )
    except BrokenPipeError:
        pass
    except KeyboardInterrupt:
        print("\n[mock] Stopped", file=sys.stderr)
    finally:
        if args.output:
            out.close()


if __name__ == "__main__":
    main()
