#!/usr/bin/env python3
"""
ehash_codec.py — Binary encode/decode for EHASH relay messages.

Python port of mesh-stack/protocol/ehash_messages.h.
Implements all four L7 message types defined in ADR-025 / ehash-spec.md:

    EHASH_TEMPLATE  (0x10) — Binary block template (downlink, broadcast)
    EHASH_NONCE     (0x11) — Binary nonce submission (uplink, unicast)
    EHASH_RESULT    (0x12) — Share accepted/rejected (downlink, unicast)
    EHASH_CREDIT    (0x13) — Credit balance update (downlink, unicast)

All multi-byte integers are little-endian (matching ESP32-C3 native order).
Hash fields are opaque 32-byte blobs in raw internal byte order.

Wire format: 1-byte type tag (opcode) + payload.
The entire envelope (type + payload) is treated as one blob by L3 fragmentation.

No external dependencies — Python stdlib only.
"""

import struct
from dataclasses import dataclass, field
from typing import List

# ========================================================================
#  Message Type Opcodes
# ========================================================================

EHASH_TEMPLATE = 0x10
EHASH_NONCE = 0x11
EHASH_RESULT = 0x12
EHASH_CREDIT = 0x13

_ALL_TYPES = frozenset({EHASH_TEMPLATE, EHASH_NONCE, EHASH_RESULT, EHASH_CREDIT})

# ========================================================================
#  Size Constants
# ========================================================================

EHASH_PROTO_VERSION = 0x01

EHASH_NONCE_SIZE = 21       # Fixed payload size
EHASH_RESULT_SIZE = 7       # Fixed payload size
EHASH_CREDIT_SIZE = 16      # Fixed payload size
EHASH_TEMPLATE_FIXED_SIZE = 55  # Fixed fields (excludes variable coinbase/merkle)
EHASH_COINBASE_MAX_LEN = 128
EHASH_MERKLE_BRANCH_MAX = 16
EHASH_MERKLE_HASH_SIZE = 32
EHASH_TEMPLATE_MAX_SIZE = (
    EHASH_TEMPLATE_FIXED_SIZE
    + EHASH_COINBASE_MAX_LEN * 2
    + EHASH_MERKLE_HASH_SIZE * EHASH_MERKLE_BRANCH_MAX
)  # = 823 bytes

# ========================================================================
#  Data Classes
# ========================================================================


@dataclass
class EhashNonce:
    """EHASH_NONCE (0x11) — Binary nonce submission. 21 bytes fixed."""

    version: int = EHASH_PROTO_VERSION
    job_id: int = 0
    worker_id: int = 0       # uint16 station ID, zero-padded to 4 bytes
    extranonce2: int = 0
    ntime: int = 0
    nonce: int = 0


@dataclass
class EhashResult:
    """EHASH_RESULT (0x12) — Share accepted/rejected. 7 bytes fixed."""

    job_id: int = 0
    accepted: int = 0        # 1 = accepted, 0 = rejected
    error_code: int = 0      # Stratum V1 error code (0 = no error)


@dataclass
class EhashCredit:
    """EHASH_CREDIT (0x13) — Credit balance update. 16 bytes fixed."""

    station_id: int = 0
    balance: int = 0         # E-hash tokens in satoshis (uint64)
    block_reward_rate: int = 0  # Satoshis per accepted share


@dataclass
class EhashTemplate:
    """EHASH_TEMPLATE (0x10) — Binary block template. Variable length."""

    version: int = EHASH_PROTO_VERSION
    job_id: int = 0
    prevhash: bytes = b""    # 32 bytes, raw internal byte order
    btc_version: int = 0
    nbits: int = 0
    ntime: int = 0           # 0 = use current time
    coinbase1: bytes = b""
    coinbase2: bytes = b""
    merkle_branches: List[bytes] = field(default_factory=list)  # each 32 bytes
    clean_jobs: int = 1


# ========================================================================
#  EHASH_NONCE Encode / Decode
# ========================================================================

# struct format: version(B) job_id(I) worker_id(I) extranonce2(I) ntime(I) nonce(I)
_NONCE_FMT = "<BIIIII"
assert struct.calcsize(_NONCE_FMT) == EHASH_NONCE_SIZE


def encode_nonce(nonce: EhashNonce) -> bytes:
    """Encode an EhashNonce into the 21-byte wire payload."""
    return struct.pack(
        _NONCE_FMT,
        EHASH_PROTO_VERSION,
        nonce.job_id,
        nonce.worker_id,
        nonce.extranonce2,
        nonce.ntime,
        nonce.nonce,
    )


def decode_nonce(buf: bytes) -> EhashNonce:
    """Decode a 21-byte payload into an EhashNonce.

    Raises ValueError if buffer is wrong size or version mismatch.
    """
    if len(buf) < EHASH_NONCE_SIZE:
        raise ValueError(
            f"Nonce buffer too short: {len(buf)} < {EHASH_NONCE_SIZE}"
        )
    version, job_id, worker_id, extranonce2, ntime, nonce = struct.unpack(
        _NONCE_FMT, buf[:EHASH_NONCE_SIZE]
    )
    if version != EHASH_PROTO_VERSION:
        raise ValueError(f"Bad nonce protocol version: {version} != {EHASH_PROTO_VERSION}")
    return EhashNonce(
        version=version,
        job_id=job_id,
        worker_id=worker_id,
        extranonce2=extranonce2,
        ntime=ntime,
        nonce=nonce,
    )


# ========================================================================
#  EHASH_RESULT Encode / Decode
# ========================================================================

# struct format: job_id(I) accepted(B) error_code(H)
_RESULT_FMT = "<IBH"
assert struct.calcsize(_RESULT_FMT) == EHASH_RESULT_SIZE


def encode_result(result: EhashResult) -> bytes:
    """Encode an EhashResult into the 7-byte wire payload."""
    return struct.pack(
        _RESULT_FMT,
        result.job_id,
        result.accepted,
        result.error_code,
    )


def decode_result(buf: bytes) -> EhashResult:
    """Decode a 7-byte payload into an EhashResult."""
    if len(buf) < EHASH_RESULT_SIZE:
        raise ValueError(
            f"Result buffer too short: {len(buf)} < {EHASH_RESULT_SIZE}"
        )
    job_id, accepted, error_code = struct.unpack(
        _RESULT_FMT, buf[:EHASH_RESULT_SIZE]
    )
    return EhashResult(
        job_id=job_id,
        accepted=accepted,
        error_code=error_code,
    )


# ========================================================================
#  EHASH_CREDIT Encode / Decode
# ========================================================================

# struct format: station_id(I) balance(Q) block_reward_rate(I)
_CREDIT_FMT = "<IQI"
assert struct.calcsize(_CREDIT_FMT) == EHASH_CREDIT_SIZE


def encode_credit(credit: EhashCredit) -> bytes:
    """Encode an EhashCredit into the 16-byte wire payload."""
    return struct.pack(
        _CREDIT_FMT,
        credit.station_id,
        credit.balance,
        credit.block_reward_rate,
    )


def decode_credit(buf: bytes) -> EhashCredit:
    """Decode a 16-byte payload into an EhashCredit."""
    if len(buf) < EHASH_CREDIT_SIZE:
        raise ValueError(
            f"Credit buffer too short: {len(buf)} < {EHASH_CREDIT_SIZE}"
        )
    station_id, balance, block_reward_rate = struct.unpack(
        _CREDIT_FMT, buf[:EHASH_CREDIT_SIZE]
    )
    return EhashCredit(
        station_id=station_id,
        balance=balance,
        block_reward_rate=block_reward_rate,
    )


# ========================================================================
#  EHASH_TEMPLATE Encode / Decode
# ========================================================================

# Fixed header format (first 51 bytes):
# version(B) job_id(I) prevhash(32s) btc_version(I) nbits(I) ntime(I) coinbase1_len(H)
_TEMPLATE_HDR_FMT = "<BI32sIIIH"
assert struct.calcsize(_TEMPLATE_HDR_FMT) == 51  # 1+4+32+4+4+4+2


def template_wire_size(tmpl: EhashTemplate) -> int:
    """Compute total payload size of a template without encoding it."""
    n = len(tmpl.coinbase1)
    m = len(tmpl.coinbase2)
    k = len(tmpl.merkle_branches)
    return EHASH_TEMPLATE_FIXED_SIZE + n + m + EHASH_MERKLE_HASH_SIZE * k


def encode_template(tmpl: EhashTemplate) -> bytes:
    """Encode an EhashTemplate into the variable-length wire payload.

    Raises ValueError on validation errors.
    """
    # --- Validate ---
    if len(tmpl.prevhash) != EHASH_MERKLE_HASH_SIZE:
        raise ValueError(
            f"prevhash must be {EHASH_MERKLE_HASH_SIZE} bytes, got {len(tmpl.prevhash)}"
        )
    n = len(tmpl.coinbase1)
    m = len(tmpl.coinbase2)
    if n > EHASH_COINBASE_MAX_LEN:
        raise ValueError(f"coinbase1 too long: {n} > {EHASH_COINBASE_MAX_LEN}")
    if m > EHASH_COINBASE_MAX_LEN:
        raise ValueError(f"coinbase2 too long: {m} > {EHASH_COINBASE_MAX_LEN}")
    k = len(tmpl.merkle_branches)
    if k > EHASH_MERKLE_BRANCH_MAX:
        raise ValueError(f"too many merkle branches: {k} > {EHASH_MERKLE_BRANCH_MAX}")
    for i, branch in enumerate(tmpl.merkle_branches):
        if len(branch) != EHASH_MERKLE_HASH_SIZE:
            raise ValueError(
                f"merkle branch {i} must be {EHASH_MERKLE_HASH_SIZE} bytes, got {len(branch)}"
            )

    total = template_wire_size(tmpl)
    if total > EHASH_TEMPLATE_MAX_SIZE:
        raise ValueError(f"template too large: {total} > {EHASH_TEMPLATE_MAX_SIZE}")

    # --- Encode ---
    parts = []

    # Fixed header + coinbase1_len
    parts.append(
        struct.pack(
            _TEMPLATE_HDR_FMT,
            EHASH_PROTO_VERSION,
            tmpl.job_id,
            tmpl.prevhash,
            tmpl.btc_version,
            tmpl.nbits,
            tmpl.ntime,
            n,
        )
    )

    # coinbase1
    parts.append(tmpl.coinbase1)

    # coinbase2_len + coinbase2
    parts.append(struct.pack("<H", m))
    parts.append(tmpl.coinbase2)

    # merkle_branch_count + branches
    parts.append(struct.pack("<B", k))
    for branch in tmpl.merkle_branches:
        parts.append(branch)

    # clean_jobs
    parts.append(struct.pack("<B", tmpl.clean_jobs))

    result = b"".join(parts)
    assert len(result) == total, f"encoded size {len(result)} != expected {total}"
    return result


def decode_template(buf: bytes) -> EhashTemplate:
    """Decode a variable-length template payload into an EhashTemplate.

    Raises ValueError on malformed input.
    """
    if len(buf) < 51:
        raise ValueError(
            f"Template buffer too short: {len(buf)} < 51 (minimum header)"
        )

    # --- Unpack fixed header ---
    (
        version,
        job_id,
        prevhash,
        btc_version,
        nbits,
        ntime,
        coinbase1_len,
    ) = struct.unpack(_TEMPLATE_HDR_FMT, buf[:51])

    if version != EHASH_PROTO_VERSION:
        raise ValueError(
            f"Bad template protocol version: {version} != {EHASH_PROTO_VERSION}"
        )

    offset = 51

    # --- coinbase1 ---
    coinbase1 = buf[offset : offset + coinbase1_len]
    if len(coinbase1) < coinbase1_len:
        raise ValueError("Buffer truncated in coinbase1")
    offset += coinbase1_len

    # --- coinbase2_len + coinbase2 ---
    if offset + 2 > len(buf):
        raise ValueError("Buffer truncated before coinbase2_len")
    (coinbase2_len,) = struct.unpack("<H", buf[offset : offset + 2])
    offset += 2

    coinbase2 = buf[offset : offset + coinbase2_len]
    if len(coinbase2) < coinbase2_len:
        raise ValueError("Buffer truncated in coinbase2")
    offset += coinbase2_len

    # --- merkle_branch_count + branches ---
    if offset + 1 > len(buf):
        raise ValueError("Buffer truncated before merkle_branch_count")
    (merkle_count,) = struct.unpack("<B", buf[offset : offset + 1])
    offset += 1

    if merkle_count > EHASH_MERKLE_BRANCH_MAX:
        raise ValueError(f"merkle_branch_count too high: {merkle_count}")

    branches = []
    for i in range(merkle_count):
        start = offset + i * EHASH_MERKLE_HASH_SIZE
        end = start + EHASH_MERKLE_HASH_SIZE
        if end > len(buf):
            raise ValueError(f"Buffer truncated in merkle branch {i}")
        branches.append(buf[start:end])
    offset += merkle_count * EHASH_MERKLE_HASH_SIZE

    # --- clean_jobs ---
    if offset + 1 > len(buf):
        raise ValueError("Buffer truncated before clean_jobs")
    (clean_jobs,) = struct.unpack("<B", buf[offset : offset + 1])
    offset += 1

    return EhashTemplate(
        version=version,
        job_id=job_id,
        prevhash=prevhash,
        btc_version=btc_version,
        nbits=nbits,
        ntime=ntime,
        coinbase1=coinbase1,
        coinbase2=coinbase2,
        merkle_branches=branches,
        clean_jobs=clean_jobs,
    )


# ========================================================================
#  L7 Envelope Helpers
# ========================================================================

# Full message encode: prepend type byte to payload
# Full message decode: read type byte, dispatch to decoder


def wrap_envelope(msg_type: int, payload: bytes) -> bytes:
    """Wrap a payload in the L7 envelope: 1-byte type tag + payload."""
    if msg_type not in _ALL_TYPES:
        raise ValueError(f"Unknown message type: 0x{msg_type:02x}")
    return struct.pack("<B", msg_type) + payload


def get_envelope_type(buf: bytes) -> int:
    """Get the message type from the first byte of an L7 envelope.

    Returns the opcode (0x10-0x13).
    Raises ValueError if invalid.
    """
    if len(buf) < 1:
        raise ValueError("Empty envelope buffer")
    msg_type = buf[0]
    if msg_type not in _ALL_TYPES:
        raise ValueError(f"Unrecognized message type: 0x{msg_type:02x}")
    return msg_type


def encode_nonce_envelope(nonce: EhashNonce) -> bytes:
    """Full L7 envelope for EHASH_NONCE (22 bytes)."""
    return wrap_envelope(EHASH_NONCE, encode_nonce(nonce))


def encode_template_envelope(tmpl: EhashTemplate) -> bytes:
    """Full L7 envelope for EHASH_TEMPLATE."""
    return wrap_envelope(EHASH_TEMPLATE, encode_template(tmpl))


def encode_result_envelope(result: EhashResult) -> bytes:
    """Full L7 envelope for EHASH_RESULT (8 bytes)."""
    return wrap_envelope(EHASH_RESULT, encode_result(result))


def encode_credit_envelope(credit: EhashCredit) -> bytes:
    """Full L7 envelope for EHASH_CREDIT (17 bytes)."""
    return wrap_envelope(EHASH_CREDIT, encode_credit(credit))


def decode_envelope(buf: bytes):
    """Decode a full L7 envelope, dispatching to the appropriate decoder.

    Returns a tuple (msg_type, decoded_object).
    """
    msg_type = get_envelope_type(buf)
    payload = buf[1:]

    if msg_type == EHASH_TEMPLATE:
        return msg_type, decode_template(payload)
    elif msg_type == EHASH_NONCE:
        return msg_type, decode_nonce(payload)
    elif msg_type == EHASH_RESULT:
        return msg_type, decode_result(payload)
    elif msg_type == EHASH_CREDIT:
        return msg_type, decode_credit(payload)
    else:
        raise ValueError(f"Unhandled message type: 0x{msg_type:02x}")


# ========================================================================
#  Stratum V1 Conversion Helpers
# ========================================================================


def template_to_notify_params(tmpl: EhashTemplate) -> list:
    """Convert an EhashTemplate to Stratum V1 mining.notify params array.

    Returns: [job_id, prevhash_hex, coinbase1_hex, coinbase2_hex,
              merkle_branches_hex[], version_hex, nbits_hex, ntime_hex, clean_jobs]

    All hash/coinbase fields are hex-encoded raw bytes (internal byte order).
    version/nbits/ntime are formatted as big-endian hex (standard stratum convention).
    """
    # job_id is sent as a string in stratum
    job_id_str = str(tmpl.job_id)

    # Hashes: hex-encode raw bytes (internal byte order, as stored in binary)
    prevhash_hex = tmpl.prevhash.hex()
    coinbase1_hex = tmpl.coinbase1.hex()
    coinbase2_hex = tmpl.coinbase2.hex()

    # Merkle branches: hex-encode each branch
    merkle_hex = [b.hex() for b in tmpl.merkle_branches]

    # Integer fields: big-endian hex (standard stratum V1 convention)
    version_hex = f"{tmpl.btc_version:08x}"
    nbits_hex = f"{tmpl.nbits:08x}"
    ntime_hex = f"{tmpl.ntime:08x}"

    clean = bool(tmpl.clean_jobs)

    return [
        job_id_str,
        prevhash_hex,
        coinbase1_hex,
        coinbase2_hex,
        merkle_hex,
        version_hex,
        nbits_hex,
        ntime_hex,
        clean,
    ]


def submit_to_nonce(
    job_id_str: str,
    extranonce2_hex: str,
    ntime_hex: str,
    nonce_hex: str,
    worker_id: int = 0,
) -> EhashNonce:
    """Convert Stratum V1 mining.submit fields to an EhashNonce.

    Stratum hex values are big-endian representations of the integer values.
    Binary EHASH_NONCE stores them as little-endian uint32.
    """
    return EhashNonce(
        job_id=int(job_id_str),
        worker_id=worker_id,
        extranonce2=int(extranonce2_hex, 16),
        ntime=int(ntime_hex, 16),
        nonce=int(nonce_hex, 16),
    )


# ========================================================================
#  Difficulty / Share Validation Helpers
# ========================================================================


def sha256d(data: bytes) -> bytes:
    """Double SHA-256 (Bitcoin hash function)."""
    import hashlib

    return hashlib.sha256(hashlib.sha256(data).digest()).digest()


def decode_nbits(nbits: int) -> int:
    """Decode Bitcoin compact difficulty format (nbits) to a 256-bit target.

    Compact format: [exponent(1 byte)] [negative(1 bit)] [mantissa(23 bits)]
    Standard Bitcoin target encoding.
    """
    exponent = nbits >> 24
    mantissa = nbits & 0x007FFFFF
    if exponent <= 3:
        target = mantissa >> (8 * (3 - exponent))
    else:
        target = mantissa << (8 * (exponent - 3))
    return target


def compute_merkle_root(coinbase_hash: bytes, branches: List[bytes]) -> bytes:
    """Compute merkle root from coinbase hash and merkle branches.

    Standard stratum V1 merkle computation: coinbase hash is always left child.
    """
    merkle = coinbase_hash
    for branch in branches:
        merkle = sha256d(merkle + branch)
    return merkle


def build_block_header(
    btc_version: int,
    prevhash: bytes,
    merkle_root: bytes,
    ntime: int,
    nbits: int,
    nonce: int,
) -> bytes:
    """Build an 80-byte Bitcoin block header."""
    return (
        struct.pack("<I", btc_version)
        + prevhash
        + merkle_root
        + struct.pack("<III", ntime, nbits, nonce)
    )


def check_share(
    tmpl: EhashTemplate,
    extranonce1: bytes,
    extranonce2: int,
    ntime: int,
    nonce: int,
    difficulty_multiplier: float = 1.0,
) -> bool:
    """Check if a share meets the difficulty target.

    Reconstructs the block header, hashes it, and compares to the adjusted target.

    Returns True if the share hash is below the target (valid share).
    Returns False if the share doesn't meet the difficulty.
    """
    # Build coinbase transaction
    extranonce2_bytes = struct.pack("<I", extranonce2)
    coinbase_tx = tmpl.coinbase1 + extranonce1 + extranonce2_bytes + tmpl.coinbase2

    # Hash coinbase
    coinbase_hash = sha256d(coinbase_tx)

    # Compute merkle root
    merkle_root = compute_merkle_root(coinbase_hash, tmpl.merkle_branches)

    # Build block header (80 bytes)
    header = build_block_header(
        tmpl.btc_version, tmpl.prevhash, merkle_root, ntime, tmpl.nbits, nonce
    )

    # Double SHA-256 the header
    block_hash = sha256d(header)

    # Interpret as little-endian 256-bit integer (Bitcoin convention)
    hash_int = int.from_bytes(block_hash, "little")

    # Derive target from nbits
    target = decode_nbits(tmpl.nbits)

    # Apply difficulty multiplier (higher = harder = lower target)
    if difficulty_multiplier > 1.0:
        target = int(target / difficulty_multiplier)

    return hash_int < target
