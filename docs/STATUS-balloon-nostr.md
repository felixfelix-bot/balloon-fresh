# STATUS — balloon-nostr (Nostr Relay Track)

**Last updated:** 2026-07-26
**Phase:** Assessment pending (not started)

## Track Goal
Port wisp-esp32 Nostr relay (ESP32-S3) to ESP32-C3 flight platform.
Source: `~/wisp-esp32/` — NIP-01 WebSocket relay, LittleFS, Schnorr validation, subscription manager.

## Current State
- [ ] Worktree not created (`~/worktrees/balloon-nostr/`)
- [ ] Integration assessment not done
- [ ] Phase 1 (understand + verify on S3) not started
- [ ] Phase 2 (C3 port) not started

## Cross-Track Discovery Ingest (2026-07-26)

Two findings from balloon-hermes received. Relevant to nostr relay because the
relay will consume radio telemetry and publish as Nostr events.

### Discovery 1: FLRC byte alignment + app-layer CRC-16 (commit 9b740aa)
**Tags:** RADIO, FIRMWARE

Radio layer now has reliable packet framing:

**Packet structure (verified on hardware):**
| Bytes   | Content                          |
|---------|----------------------------------|
| 0-3     | Sync header: `0xA5 0x5A 0x42 0x24` |
| 4-22    | GPS payload (lat, lon, sats, fix)  |
| 23-28   | Fill pattern                      |
| 29-30   | CRC-16 (CCITT, poly 0x1021)       |
| 31-254  | Fill (`i ^ 0xA5`)                  |

Key details:
- Sync header NOT at byte 0 in FIFO — LR2021 prepends framing bytes. RX does dynamic search.
- **Hardware CRC unreliable** — passes garbage. App-layer CRC-16 is source of truth.
- CRC computed over bytes 4-21, stored at bytes 29-30. RX verifies, logs `APP_CRC_FAIL`.
- RX FIFO cleared (opcode `0x01 0x20`) before every re-arm — prevents stale data.

**Nostr relevance:** When relay ingests radio payloads, trust ONLY post-CRC-verified data. Parse GPS from bytes 4-22. Ignore hardware CRC status.

### Discovery 2: GPS payload verified on LoRa (commit be354b0)
**Tags:** RADIO, FIRMWARE, TEST

GPS data confirmed working over LoRa phases:
- 5/6 LoRa phases decode correctly: lat=32.639, lon=-16.946, sats=6-9, fix=1
- FLRC phase 12 still has partial alignment issue (not all modes fixed yet)
- RSSI: -31 to -58 dBm (good signal at walk-test range)
- Phase sync via GPS UTC time (TX and RX cycle through same phase simultaneously)

**Nostr relevance:** GPS position data is available and verified. Relay can publish geo-tagged Nostr events (NIP-01 text notes or custom telemetry kind) with confidence in data integrity.

## Next Steps (when track starts)
1. Create worktree: `git worktree add ~/worktrees/balloon-nostr balloon-nostr-extraction`
2. Build wisp-esp32 on ESP32-S3, verify NIP-01 relay functionality
3. Benchmark: heap, flash, max WebSocket connections
4. Plan C3 port (4MB flash vs 16MB, 400KB RAM vs 8MB PSRAM)
5. Define telemetry-to-Nostr-event mapping using the radio payload format above
