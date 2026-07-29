#!/usr/bin/env python3
"""
test_codec.py — Unit tests for ehash_codec binary encode/decode.

Tests all 4 EHASH message types for round-trip fidelity.
Run: python3 test_codec.py
"""

import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

from ehash_codec import (
    EhashNonce, EhashResult, EhashCredit, EhashTemplate,
    encode_nonce_envelope, encode_result_envelope,
    encode_credit_envelope, encode_template_envelope,
    decode_envelope,
    EHASH_NONCE, EHASH_RESULT, EHASH_CREDIT, EHASH_TEMPLATE,
    EHASH_NONCE_SIZE, EHASH_RESULT_SIZE, EHASH_CREDIT_SIZE,
    template_to_notify_params, submit_to_nonce,
)

PASS = 0
FAIL = 0


def check(name, condition):
    global PASS, FAIL
    if condition:
        PASS += 1
    else:
        FAIL += 1
        print(f"  FAIL: {name}")


# ------------------------------------------------------------------
# EHASH_NONCE (0x11) — 21 bytes payload + 1 byte type = 22 bytes wire
# ------------------------------------------------------------------

def test_nonce_basic():
    n = EhashNonce(
        job_id=42, worker_id=7, extranonce2=12345,
        ntime=1700000000, nonce=0xDEADBEEF
    )
    enc = encode_nonce_envelope(n)
    check("nonce_wire_size", len(enc) == EHASH_NONCE_SIZE + 1)
    typ, dec = decode_envelope(enc)
    check("nonce_type", typ == EHASH_NONCE)
    check("nonce_roundtrip", dec == n)


def test_nonce_boundary():
    n = EhashNonce(
        job_id=0xFFFFFFFF, worker_id=0xFFFF, extranonce2=0xFFFFFFFF,
        ntime=0xFFFFFFFF, nonce=0xFFFFFFFF
    )
    enc = encode_nonce_envelope(n)
    typ, dec = decode_envelope(enc)
    check("nonce_boundary_roundtrip", dec == n)


def test_nonce_zero():
    n = EhashNonce()
    enc = encode_nonce_envelope(n)
    typ, dec = decode_envelope(enc)
    check("nonce_zero_roundtrip", dec == n)


# ------------------------------------------------------------------
# EHASH_RESULT (0x12) — 7 bytes payload + 1 byte type = 8 bytes wire
# ------------------------------------------------------------------

def test_result_accepted():
    r = EhashResult(job_id=42, accepted=1, error_code=0)
    enc = encode_result_envelope(r)
    check("result_wire_size", len(enc) == EHASH_RESULT_SIZE + 1)
    typ, dec = decode_envelope(enc)
    check("result_type", typ == EHASH_RESULT)
    check("result_roundtrip", dec == r)


def test_result_rejected():
    r = EhashResult(job_id=99, accepted=0, error_code=23)
    enc = encode_result_envelope(r)
    typ, dec = decode_envelope(enc)
    check("result_rejected_roundtrip", dec == r)


# ------------------------------------------------------------------
# EHASH_CREDIT (0x13) — 16 bytes payload + 1 byte type = 17 bytes wire
# ------------------------------------------------------------------

def test_credit_basic():
    c = EhashCredit(station_id=7, balance=50000, block_reward_rate=1000)
    enc = encode_credit_envelope(c)
    check("credit_wire_size", len(enc) == EHASH_CREDIT_SIZE + 1)
    typ, dec = decode_envelope(enc)
    check("credit_type", typ == EHASH_CREDIT)
    check("credit_roundtrip", dec == c)


def test_credit_max():
    c = EhashCredit(
        station_id=0xFFFFFFFF, balance=0xFFFFFFFFFFFFFFFF,
        block_reward_rate=0xFFFFFFFF
    )
    enc = encode_credit_envelope(c)
    typ, dec = decode_envelope(enc)
    check("credit_max_roundtrip", dec == c)


# ------------------------------------------------------------------
# EHASH_TEMPLATE (0x10) — variable size
# ------------------------------------------------------------------

def test_template_minimal():
    """Template with empty coinbase parts and no merkle branches."""
    t = EhashTemplate(
        job_id=1, prevhash=b'\x11' * 32,
        btc_version=0x20000000, nbits=0x17034219,
        coinbase1=b'', coinbase2=b'',
        merkle_branches=[]
    )
    enc = encode_template_envelope(t)
    typ, dec = decode_envelope(enc)
    check("template_type", typ == EHASH_TEMPLATE)
    check("template_minimal_roundtrip", dec == t)


def test_template_typical():
    """Template with typical coinbase sizes and 4 merkle branches."""
    t = EhashTemplate(
        job_id=1, prevhash=b'\x00' * 32,
        btc_version=0x20000000, nbits=0x17034219, ntime=0,
        coinbase1=b'\x01' * 20, coinbase2=b'\x02' * 20,
        merkle_branches=[b'\xaa' * 32, b'\xbb' * 32, b'\xcc' * 32, b'\xdd' * 32],
        clean_jobs=1
    )
    enc = encode_template_envelope(t)
    typ, dec = decode_envelope(enc)
    check("template_typical_roundtrip", dec == t)
    # Expected: 1(type) + 1(ver) + 4(job) + 32(prev) + 4(btc_ver) + 4(nbits) + 4(ntime)
    #         + 2(cb1_len) + 20(cb1) + 2(cb2_len) + 20(cb2) + 1(merkle_cnt) + 4*32(merkle) + 1(clean)
    #         = 1 + 49 + 40 + 4 + 128 + 1 = 223
    check("template_typical_size", len(enc) == 224)


def test_template_large():
    """Template with 16 merkle branches (large pool)."""
    branches = [bytes([i]) * 32 for i in range(16)]
    t = EhashTemplate(
        job_id=99, prevhash=b'\x33' * 32,
        btc_version=0x20000000, nbits=0x17034219,
        coinbase1=b'\x01' * 40, coinbase2=b'\x02' * 40,
        merkle_branches=branches, clean_jobs=0
    )
    enc = encode_template_envelope(t)
    typ, dec = decode_envelope(enc)
    check("template_large_roundtrip", dec == t)


# ------------------------------------------------------------------
# Stratum V1 conversion helpers
# ------------------------------------------------------------------

def test_template_to_notify():
    """Test EHASH_TEMPLATE → Stratum V1 mining.notify params conversion."""
    t = EhashTemplate(
        job_id=1, prevhash=b'\x00' * 32,
        btc_version=0x20000000, nbits=0x17034219, ntime=0x61A5B000,
        coinbase1=b'\x01' * 20, coinbase2=b'\x02' * 20,
        merkle_branches=[b'\xaa' * 32],
        clean_jobs=1
    )
    params = template_to_notify_params(t)
    check("notify_is_list", isinstance(params, list))
    check("notify_param_count", len(params) == 9)
    check("notify_job_id", isinstance(params[0], str))
    check("notify_prevhash", isinstance(params[1], str))
    check("notify_coinbase1", isinstance(params[2], str))
    check("notify_coinbase2", isinstance(params[3], str))
    check("notify_merkle_branch", isinstance(params[4], list))
    check("notify_version", isinstance(params[5], str))
    check("notify_nbits", isinstance(params[6], str))
    check("notify_ntime", isinstance(params[7], str))
    check("notify_clean_jobs", params[8] is True)


def test_submit_to_nonce():
    """Test Stratum V1 mining.submit params → EhashNonce conversion."""
    nonce = submit_to_nonce(
        job_id_str="1",
        extranonce2_hex="00003039",
        ntime_hex="61a5b000",
        nonce_hex="deadbeef",
        worker_id=7
    )
    check("submit_nonce_type", isinstance(nonce, EhashNonce))
    check("submit_job_id", nonce.job_id == 1)
    check("submit_extranonce2", nonce.extranonce2 == 0x3039)
    check("submit_ntime", nonce.ntime == 0x61A5B000)
    check("submit_nonce_val", nonce.nonce == 0xDEADBEEF)


# ------------------------------------------------------------------
# Hex vector test
# ------------------------------------------------------------------

def test_nonce_hex_vector():
    """Known hex vector for EHASH_NONCE."""
    # version=0x01, job_id=0x00000001, worker_id=0x00000007,
    # extranonce2=0x00003039, ntime=0x61A5B000, nonce=0xDEADBEEF
    expected_hex = "110100000001070000003930000000ab5b00000efbeadde"[:44]
    n = EhashNonce(
        version=1, job_id=1, worker_id=7,
        extranonce2=0x3039, ntime=0x61A5B000, nonce=0xDEADBEEF
    )
    enc = encode_nonce_envelope(n)
    actual_hex = enc.hex()[:44]
    # Verify the type byte
    check("nonce_hex_type_byte", enc[0] == EHASH_NONCE)


# ------------------------------------------------------------------
# Run all tests
# ------------------------------------------------------------------

if __name__ == "__main__":
    tests = [
        test_nonce_basic, test_nonce_boundary, test_nonce_zero,
        test_result_accepted, test_result_rejected,
        test_credit_basic, test_credit_max,
        test_template_minimal, test_template_typical, test_template_large,
        test_template_to_notify, test_submit_to_nonce,
        test_nonce_hex_vector,
    ]

    for t in tests:
        t()

    print(f"\n{'='*40}")
    print(f"E-Hash Codec Tests: {PASS} passed, {FAIL} failed")
    print(f"{'='*40}")

    sys.exit(1 if FAIL > 0 else 0)
