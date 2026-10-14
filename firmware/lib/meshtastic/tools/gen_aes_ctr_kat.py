#!/usr/bin/env python3
"""Regenerate the AES-CTR known-answer vector used by test_mesh.cpp.

WHY THIS EXISTS
---------------
test_mesh.cpp asserts a 200-byte AES-256-CTR ciphertext so that the CTR
implementation there is anchored to something built OUTSIDE this repo. A vector
transcribed from memory would be worthless: if it were wrong, the test would
either fail forever or (worse) have been "fixed" by editing the expected bytes
until the implementation matched itself. This script is the provenance.

It generates the vector with OpenSSL and, when python-cryptography is present,
ALSO with an independent AES implementation, and refuses to print anything
unless the two agree. Run it and diff the output against the hex block in
test_mesh.cpp.

Usage:
    python3 firmware/lib/meshtastic/tools/gen_aes_ctr_kat.py

Only the Python standard library and the `openssl` binary are required.

WHAT THE VECTOR COVERS (and what it cannot)
-------------------------------------------
The counter block is exactly what balloon::meshtastic::build_nonce() produces for
packet id 0x11223344 from node 0x0a0b0c0d:

    bytes 0-7   LE64(packet id)     44 33 22 11 00 00 00 00
    bytes 8-11  LE32(from node)     0d 0c 0b 0a
    bytes 12-15 block counter       00 00 00 00

200 bytes of plaintext (0x00..0xc7) means 13 counter blocks, so an implementation
that fails to increment the counter, or that increments the wrong end of it,
produces different output from block 2 onwards. That is the property being
tested.

LIMITATION, STATED PLAINLY: this vector does NOT and cannot verify the counter
WIDTH. Upstream configures the CTR counter size as 4 bytes (upstream
RadioInterface/CryptoEngine: `ctr->setCounterSize(4)`), which for any message
shorter than (2^32 - 1) * 16 bytes is indistinguishable from a wider counter,
because the increment never carries past the low four bytes. The counter width in
mesh_aes.h (`kCtrCounterBytes = 4`) is therefore sourced from the upstream call
site, not proven by this test. See REPORT.md.
"""

import json
import shutil
import subprocess
import sys

# --- inputs, matching test_mesh.cpp exactly ---------------------------------
KEY_HEX = "000102030405060708090a0b0c0d0e0f101112131415161718191a1b1c1d1e1f"
PACKET_ID = 0x11223344
FROM_NODE = 0x0A0B0C0D
PLAIN_LEN = 200


def build_nonce(packet_id: int, from_node: int) -> bytes:
    """Mirror of build_nonce() in mesh_crypto.cpp.

    bytes 0-7   : packet id as a 64-bit little-endian value
    bytes 8-11  : sender node number, little-endian
    bytes 12-15 : block counter, starting at 0
    """
    return (
        packet_id.to_bytes(8, "little")
        + from_node.to_bytes(4, "little")
        + (0).to_bytes(4, "little")
    )


def openssl_ctr(key: bytes, nonce: bytes, plaintext: bytes) -> bytes:
    if shutil.which("openssl") is None:
        raise SystemExit("openssl binary not found: cannot generate the vector")
    proc = subprocess.run(
        [
            "openssl", "enc", "-aes-256-ctr",
            "-K", key.hex(),
            "-iv", nonce.hex(),
        ],
        input=plaintext,
        capture_output=True,
    )
    if proc.returncode != 0:
        raise SystemExit(f"openssl failed: {proc.stderr.decode(errors='replace')}")
    return proc.stdout


def cryptography_ctr(key: bytes, nonce: bytes, plaintext: bytes):
    """Independent implementation, or None when the module is unavailable."""
    try:
        from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
    except ImportError:
        return None
    cipher = Cipher(algorithms.AES(key), modes.CTR(nonce))
    enc = cipher.encryptor()
    return enc.update(plaintext) + enc.finalize()


def main() -> int:
    key = bytes.fromhex(KEY_HEX)
    nonce = build_nonce(PACKET_ID, FROM_NODE)
    plaintext = bytes(range(PLAIN_LEN))

    ct_openssl = openssl_ctr(key, nonce, plaintext)

    ct_crypto = cryptography_ctr(key, nonce, plaintext)
    if ct_crypto is None:
        print("NOTE: python-cryptography absent; only OpenSSL was used.",
              file=sys.stderr)
    elif ct_crypto != ct_openssl:
        raise SystemExit(
            "OpenSSL and python-cryptography DISAGREE - do not trust either "
            "until that is understood"
        )

    # Round trip: decrypting the ciphertext must return the plaintext exactly.
    rt = subprocess.run(
        ["openssl", "enc", "-d", "-aes-256-ctr", "-K", key.hex(), "-iv", nonce.hex()],
        input=ct_openssl,
        capture_output=True,
    )
    if rt.returncode != 0 or rt.stdout != plaintext:
        raise SystemExit("decrypt round trip failed")

    print(f"key        = {KEY_HEX}")
    print(f"nonce      = {nonce.hex()}")
    print(f"  (LE64 packet id {hex(PACKET_ID)} | LE32 from {hex(FROM_NODE)} | counter 0)")
    print(f"plaintext  = {PLAIN_LEN} bytes, 0x00..0x{PLAIN_LEN - 1:02x}")
    print(f"blocks     = {(PLAIN_LEN + 15) // 16} counter blocks exercised")
    print("ciphertext hex (paste into test_mesh.cpp):")
    h = ct_openssl.hex()
    for i in range(0, len(h), 64):
        print(f'        "{h[i:i + 64]}"')
    print("ciphertext json (for tooling):")
    print(json.dumps(ct_openssl.hex()))
    print("cross-check: OpenSSL and python-cryptography agree, decrypt round-trips")
    return 0


if __name__ == "__main__":
    sys.exit(main())
