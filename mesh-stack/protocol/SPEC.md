# Pico Balloon Mesh Protocol Specification

Version: 0.1-draft  
Status: Implementation in progress  
Components: tracker/firmware/components/{fips_transport,pipeline,frag,erasure,tdma,nostr_store,mesh_adapter}

## 1. Overview

This document specifies the wire protocol for the pico balloon mesh network. The protocol stack is:

```
Application  Nostr events (kind 30023 telemetry, kind 1 chat)
Transport    FIPS Noise IK (secp256k1, ChaCha20-Poly1305)
Fragment     Erasure-coded fragmentation (PRBS23-XOR)
Link         TDMA dual-band scheduler (Sub-GHz + 2.4 GHz)
Physical     LR2021 (LoRa/FLRC, 868 MHz + 2.4 GHz)
```

## 2. Physical Layer (L1)

### 2.1 Sub-GHz Band (868 MHz)

| Parameter  | Value          | Notes                        |
|------------|----------------|------------------------------|
| Frequency  | 869.618 MHz    | EU ISM band                  |
| Modulation | LoRa SF8       | MeshCore EU/UK Narrow preset |
| Bandwidth  | 62.5 kHz       | EU duty cycle compliance     |
| Coding Rate| 4/8            | Maximum hardware FEC         |
| TX Power   | +22 dBm        | LR2021 direct output         |
| Antenna    | Pin 9          | Sub-GHz dedicated port       |

### 2.2 2.4 GHz Band

| Parameter     | Short Range    | Medium Range     | Long Range       |
|---------------|----------------|------------------|------------------|
| Modulation    | FLRC 1300 kbps | LoRa SF9/1625kHz | LoRa SF10/125kHz |
| Air Rate      | ~1300 kbps     | ~22 kbps         | ~1.0 kbps        |
| TX Power      | +12 dBm        | +22 dBm (FEM)    | +22 dBm (FEM)    |
| Antenna       | Pin 10         | Pin 10           | Pin 10           |

Modulation selected adaptively based on ground station distance from GPS.

## 3. TDMA Frame Structure (L2)

### 3.1 Frame Duration

- Default: 2,000,000 us (2 seconds)
- Configurable: 1-4 seconds
- Maximum slots: 8
- Guard band: 200 us between slots

### 3.2 Slot Types

| Type        | Value | Callback | Notes                      |
|-------------|-------|----------|----------------------------|
| SLEEP       | 0     | None     | Radio off, power saving    |
| TX          | 1     | TX cb    | Transmit in assigned band  |
| RX          | 2     | None     | Listen in assigned band    |
| BEACON      | 3     | TX cb    | TX beacon every frame      |
| CONTENTION  | 4     | None     | ALOHA-style shared slot    |

### 3.3 Band Assignment

Each slot is assigned to either `TDMA_SUBGHZ` (0) or `TDMA_2G4` (1).

### 3.4 Default 4-Slot Frame (Mesh V1)

```
Slot 0: BEACON   Sub-GHz   (MeshCore advert)
Slot 1: TX       Sub-GHz   (MeshCore forward)
Slot 2: TX       2.4 GHz   (FIPS encrypted data)
Slot 3: CONTENTION Sub-GHz  (MeshCore ALOHA)
```

### 3.5 Clock Discipline

GPS PPS from MAX-M10S resets frame timer at each pulse.
Expected accuracy: ±1 us.
Guard bands accommodate 300 km propagation delay (~1 ms) plus clock drift.

## 4. Fragmentation Layer (L3)

### 4.1 Fragment Header

```
Offset  Size  Field            Description
0       2     block_id         Block identifier (CRC-derived)
2       1     frag_index       Fragment index (0 = first)
3       1     original_count   Number of original (non-redundant) fragments
4       2     crc16            CRC-16/CCITT of header + payload
6       N     payload          Fragment payload data
```

Total header: 6 bytes (FRAG_HEADER_SIZE).

### 4.2 CRC-16

- Polynomial: 0x1021 (CRC-CCITT)
- Init: 0xFFFF
- Computed over header (with crc16=0) + payload
- Stored little-endian in header

### 4.3 Fragment Index

- `frag_index < original_count`: Original data fragment
- `frag_index >= original_count`: Redundant (erasure-coded) fragment

### 4.4 Reassembly

- Fragments may arrive out of order
- block_id mismatch → fragment rejected
- All original fragments received → complete
- Missing originals may be recovered via erasure decoding

## 5. Erasure Coding (L3)

### 5.1 Algorithm

Semtech PRBS23-XOR coding. Lightweight (~1 KB RAM for encoder+decoder).

### 5.2 Encoder

- Input: `k` original fragments, each `frag_size` bytes
- Output: `redundancy_count` additional fragments
- Parity matrix: PRBS23 pseudo-random, ~50% density
- Each redundant fragment = XOR of selected original fragments

### 5.3 Decoder

- Tracks missing fragment indices
- For each redundant fragment:
  - XOR out all received fragments referenced by parity row
  - If only 1 missing fragment in row → direct recovery
  - If >1 missing → add to matrix for Gaussian elimination
  - GE solve when enough redundant fragments collected

### 5.4 Recovery Guarantee

- Guaranteed recovery if `redundancy_count >= number_of_lost_originals`
- Subject to PRBS23 matrix rank (probabilistic for pathological cases)

## 6. Pipeline (L3 combined)

### 6.1 TX Path

```
Input: data (up to 190 bytes after FIPS encryption)
  1. Pad to multiple of frag_payload_size
  2. Encode: split into k original fragments
  3. Generate redundancy_count redundant fragments (erasure encode)
  4. Prepend fragment header to each
  5. Emit frames via callback
```

### 6.2 RX Path

```
Input: received LoRa frames
  1. Parse fragment header
  2. Feed to erasure decoder (all fragments, original and redundant)
  3. When decoder signals complete → extract original data
  4. Trim to actual data length
```

### 6.3 Constraints

| Parameter            | Value  |
|----------------------|--------|
| Max fragment payload | 242 B  |
| Max fragments/block  | 64     |
| Max redundancy       | 32     |
| Max data length      | ~15 KB |

## 7. FIPS Transport (L4-L6)

### 7.1 Noise Protocol Framework

- Pattern: **IK** (Immediate initiator static key, Known responder static key)
- DH: secp256k1 (via micro-ecc)
- AEAD: ChaCha20-Poly1305 (via mbedtls)
- Hash: SHA-256 (via mbedtls)
- Key derivation: HKDF Extract+Expand (via mbedtls)

### 7.2 Handshake Messages

**MSG1 (Initiator → Responder): 98 bytes**
```
Offset  Size  Field
0       33    Initiator ephemeral public key (compressed secp256k1)
33      33    Initiator static public key (compressed secp256k1)
66      16    AEAD tag for encrypted static key
82      16    AEAD tag for handshake hash
```

**MSG2 (Responder → Initiator): 49 bytes**
```
Offset  Size  Field
0       33    Responder ephemeral public key (compressed secp256k1)
33      16    AEAD tag for handshake hash
```

Total handshake overhead: 147 bytes.

### 7.3 Session State Machine

```
IDLE → WAIT_MSG2 (after MSG1 sent)
WAIT_MSG2 → ESTABLISHED (after MSG2 processed)
ESTABLISHED → (encrypt/decrypt FMP messages)
Any → ERROR (on protocol error)
```

### 7.4 FMP (FIPS Message Protocol)

Encrypted data frame format:

```
Offset  Size  Field
0       4     Length prefix (big-endian)
4       4     Reserved (zeros)
8       8     Counter (send/recv counter, big-endian)
16      N     Ciphertext
16+N    16    AEAD tag (Poly1305 MAC)
```

Overhead: 32 bytes (FIPS_FMP_OVERHEAD).

### 7.5 Node Address

- `node_addr = SHA-256(uncompressed_public_key)[:16]`
- 16-byte routing identifier derived from Nostr identity keypair

### 7.6 Size Limits

| Parameter          | Value |
|--------------------|-------|
| FIPS_MAX_PAYLOAD   | 222 B |
| Max plaintext      | 190 B (222 - 32 overhead) |
| MSG1 size          | 98 B  |
| MSG2 size          | 49 B  |

## 8. Nostr Event Store (L7)

### 8.1 Event Format

```
Field         Size       Description
id            32 B       SHA-256 of serialized event
pubkey        32 B       Author's secp256k1 public key
created_at    4 B        Unix timestamp
kind          2 B        Event kind (30023 = telemetry, 1 = text)
content       0-480 B    Event content (JSON for telemetry)
num_tags      1 B        Number of tags
tags          variable   Key-value pairs (max 8 tags, 64B each)
```

### 8.2 Bloom Filter Dedup

- 512-bit bloom filter (64 bytes)
- Event ID used as key
- Prevents processing duplicate events

### 8.3 Store Capacity

- FIFO ring buffer: 512 events
- Oldest events overwritten when full
- Bloom filter reset on overflow

### 8.4 Serialization

Binary format for LoRa transport (not JSON):
- Compact: ~50-200 bytes for typical events
- Used for store-and-forward relay between balloons

## 9. Mesh Adapter (Glue Layer)

### 9.1 TX Path

```
Application data → mesh_adapter_send()
  1. Pipeline fragment (with erasure redundancy)
  2. Queue frames in TX buffer
  3. Send callback for each frame (TDMA scheduler dispatches to radio)
```

### 9.2 RX Path

```
LoRa frame received → mesh_adapter_receive_frame()
  1. Pipeline reassemble (erasure decode if needed)
  2. When complete → return assembled data
  3. FIPS decrypt (handled by caller)
  4. Parse Nostr event and store
```

### 9.3 Configuration

```c
typedef struct {
    mesh_frame_send_fn send_fn;     // Called for each TX frame
    mesh_frame_queue_t *tx_queue;   // Optional TX frame buffer
} mesh_adapter_config_t;
```

## 10. Telemetry Packet (Application)

### 10.1 Binary Format (28 bytes)

```
Offset  Size  Type    Field
0       4     uint32  uptime_seconds
4       2     uint16  counter
6       4     int32   latitude (1e-7 degrees)
10      4     int32   longitude (1e-7 degrees)
14      2     uint16  altitude (meters)
16      2     int16   temperature (0.01 °C)
18      2     uint16  voltage (mV)
20      1     uint8   satellites
21      1     uint8   fix_quality
22      1     uint8   tx_power
23      1     uint8   mode
24      2     uint16  pressure (hPa * 10)
26      2     uint16  crc16
```

CRC-16 computed over bytes 0-25, stored little-endian at offset 26.
Total: 28 bytes. Fits in single LoRa frame (no fragmentation needed).

## 11. Test Coverage

| Component       | Host Tests | Integration Tests |
|-----------------|-----------|-------------------|
| erasure         | 5         | -                 |
| tdma            | 12        | -                 |
| nostr_store     | 7         | -                 |
| micro_ecc       | 5         | -                 |
| fips_transport  | 13        | 4 (FIPS+Pipeline) |
| pipeline        | 9         | -                 |
| frag            | 13        | -                 |
| telemetry       | 11        | -                 |
| gps             | 8         | -                 |
| bmp280          | 6         | -                 |
| antenna_switch  | 7         | -                 |
| sky66112        | 9         | -                 |
| cli             | 8         | -                 |
| power_manager   | 5         | -                 |
| mesh_adapter    | 8         | -                 |
| **Total C**     | **126**   | **4**             |

Python tests: 29 (link_budget) + 11 (nostr) + 14 (ground_station) = 54  
Grand total: 126 + 4 + 54 = **184 test assertions**  
Pytest items: **73** (14 C host wrappers + 54 Python + 4 integration)
