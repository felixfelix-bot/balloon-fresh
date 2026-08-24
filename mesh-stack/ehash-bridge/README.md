# E-Hash Stratum Bridge

Ground station stratum-bridge for relaying Bitcoin mining data between
the balloon LR2021 link and a local Bitaxe/ASIC miner.

## What It Does

```
Balloon (LR2021) → [ehash-bridge] → Bitaxe (TCP :3333)
                     ↕ :3334           ↑
                  Tollgate API      mining.notify / mining.submit
```

The bridge:
1. Receives binary EHASH_TEMPLATE messages (from balloon via LR2021)
2. Decrypts with per-session key (D8)
3. Reconstructs Stratum V1 JSON `mining.notify`
4. Serves on TCP localhost:3333 (Bitaxe connects here)
5. Receives `mining.submit` from Bitaxe
6. Applies local difficulty filter (D7)
7. Encodes as binary EHASH_NONCE (21 bytes)
8. Outputs for LR2021 uplink to balloon

## Files

| File | Purpose |
|------|---------|
| `ehash_codec.py` | Binary encode/decode for all 4 EHASH message types |
| `stratum_server.py` | TCP Stratum V1 server (JSON-RPC 2.0) |
| `mock_template.py` | Generates fake block templates for testing |
| `test_codec.py` | Unit tests for codec round-trip (35 tests) |

## Quick Start

### Run tests
```bash
python3 test_codec.py
```

### Start stratum server in mock mode
```bash
python3 stratum_server.py --mock --port 3333
```

### Point Bitaxe at it
Configure Bitaxe stratum URL to: `stratum+tcp://<ground-station-ip>:3333`

## Stratum V1 Protocol

The server implements standard Stratum V1 JSON-RPC:

- `mining.subscribe` → subscription ID + extranonce1 + extranonce2_size
- `mining.authorize` → accepts all workers (payment gate is upstream)
- `mining.notify` → pushes block template as job
- `mining.submit` → validates share, returns true/false

## Interface Boundary

See `mesh-stack/protocol/ehash-interface-boundary.md` for the split
between balloon-pow (this code) and tollgate (customer wallet layer).

- **Balloon-pow serves**: TCP stratum server on `:3333`
- **Tollgate serves**: HTTP API on `:3334` (balance, share-report)
- **No shared code** — communicate via localhost APIs

## Dependencies

Python 3.8+ stdlib only. No pip packages required.
