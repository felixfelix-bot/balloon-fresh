# Balloon Blossom Server — Design Document

**Track:** 6 — Blossom Server
**Status:** Design (awaiting orchestrator approval)
**Date:** 2026-07-29
**Author:** balloon-blossom sub-manager

## 1. Purpose

Minimal Blossom (BUD-01/02/11) media server for ESP32 balloon nodes. Enables
balloon nodes to store and serve media files (telemetry snapshots, config files,
firmware update chunks) via the Nostr Blossom protocol over captive portal WiFi.

## 2. Scope — What We Build vs Skip

### Build (Minimal Viable Server)

| BUD | Endpoint | Method | Purpose |
|-----|----------|--------|---------|
| 01 (mandatory) | `GET /<sha256>` | GET | Download blob by hash |
| 01 (mandatory) | `HEAD /<sha256>` | HEAD | Check existence + size |
| 01 (mandatory) | `OPTIONS *` | OPTIONS | CORS preflight |
| 02 (optional) | `PUT /upload` | PUT | Upload blob (streaming) |
| 11 (auth) | — | — | Kind 24242 event verification |

### Skip (Rationale)

| BUD | Why Skip |
|-----|----------|
| 03 (server list) | Client-side only, no server endpoint |
| 04 (mirror) | Requires outbound HTTP client — marginal value on balloon node |
| 05 (media optimization) | Transcoding impractical on ESP32 (no FPU headroom) |
| 06 (upload preflight) | Only relevant if upload rate-limiting needed — add later |

### Future Phases
- BUD-04 mirror: if balloon-to-balloon blob sync becomes useful
- BUD-06 preflight: if flash wear management requires pre-upload checks
- DELETE endpoint: if storage cleanup needed (BUD-01 mentions DELETE in some drafts)

## 3. Architecture

```
┌─────────────────────────────────────────────────┐
│                  ESP32-C3 / S3                   │
│                                                  │
│  ┌──────────────────────────────────────────┐   │
│  │         esp_http_server (port 80)         │   │
│  │                                          │   │
│  │  GET /<sha256>  →  blob_download_handler │   │
│  │  HEAD /<sha256> →  blob_check_handler    │   │
│  │  PUT /upload    →  blob_upload_handler   │   │
│  │  OPTIONS *      →  cors_preflight_handler│   │
│  └──────────────┬───────────────────────────┘   │
│                 │                                │
│  ┌──────────────▼───────────────────────────┐   │
│  │           Blossom Auth Layer              │   │
│  │  • Parse Authorization: Nostr <base64url> │   │
│  │  • JSON parse kind 24242 event            │   │
│  │  • Schnorr sig verify (secp256k1)         │   │
│  │  • Check: kind, expiration, t-tag, x-tag  │   │
│  └──────────────┬───────────────────────────┘   │
│                 │                                │
│  ┌──────────────▼───────────────────────────┐   │
│  │         Blob Storage Layer                │   │
│  │  • LittleFS on flash partition            │   │
│  │  • Files stored as /<sha256-hex>          │   │
│  │  • Sidecar metadata: /<sha256>.meta (JSON)│   │
│  │    { "size": N, "type": "mime",           │   │
│  │      "uploaded": unix_ts }                 │   │
│  │  • SHA256 hash (mbedtls HW accelerated)   │   │
│  └──────────────────────────────────────────┘   │
│                                                  │
│  Flash Layout:                                   │
│  ┌──────────┬──────────────┬──────────────────┐ │
│  │ Firmware │  NVS (16KB)  │  Blossom (data)  │ │
│  │ (~1.8MB) │              │  (~1-2MB LittleFS)│ │
│  └──────────┴──────────────┴──────────────────┘ │
└─────────────────────────────────────────────────┘
```

## 4. Porting Strategy

~70% of foundation portable from `esp32-tollgate`. Source repos untouched.

### Port Directly (proven on ESP32, C3-compatible)

| Component | Source Path | What It Provides |
|-----------|------------|------------------|
| Schnorr verify | `esp32-tollgate/components/wisp_relay/relay_validator.c` | BIP-340 sig verify + event ID hashing. Self-contained. |
| Schnorr sign | `esp32-tollgate/main/nostr_event.c` | For server to sign own events (NIP-94 metadata) |
| libsecp256k1 | `esp32-tollgate/nucula_src/components/secp256k1/` | Lean build (schnorrsig + extrakeys only). Drop WINDOW_SIZE 8→4 for C3 RAM. |
| LittleFS | `esp32-tollgate/components/esp_littlefs/` | Full vendored component, C3-native |
| Nostr JSON parsing | `esp32-tollgate/components/wisp_relay/handlers.c` + `relay_types.c` | cJSON-based event parsing, hex helpers |
| HTTP server patterns | `esp32-tollgate/main/captive_portal.c` | esp_http_server URI handler registration patterns |

### Adapt (needs modification for blossom)

| Capability | Source | Work Needed |
|-----------|--------|-------------|
| Blob storage | tollgate `storage_engine.c` (event store) | Simplify: store raw files as `/<sha256>` instead of JSON events. No index needed. |
| BUD-11 auth | tollgate `relay_validator.c` + `handlers.c` | ~80% reusable: extract kind 24242 from base64 header, verify sig (existing), check expiration + t-tag + x-tag (~30 new lines) |

### Build New (no existing code)

| Capability | Why |
|-----------|-----|
| Blossom endpoints | No blossom server code exists. New esp_http_server URI handlers. |
| Upload streaming | Streaming body receive → LittleFS file write via `httpd_req_recv` chunks. |
| Blob descriptor JSON | Response format for PUT /upload. |

## 5. Protocol Details

### Auth (BUD-11)

Authorization header format:
```
Authorization: Nostr <base64url(json_event_without_padding)>
```

Server verification steps:
1. Strip `"Nostr "` prefix
2. Re-add `=` padding
3. `base64.urlsafe_b64decode`
4. `json.loads` → Nostr event
5. Verify Schnorr signature over canonical event serialization (event ID = SHA256)
6. Check: `kind == 24242`
7. Check: `created_at` in past, `expiration` tag in future
8. Check: `t` tag matches endpoint action (`upload` for PUT /upload, `get` for GET)
9. Check (upload only): `x` tag == SHA256 hex of uploaded body

### Endpoints

**GET /<sha256>** — Download blob
- Parse 64-char hex from path, ignore trailing `.ext`
- Read from LittleFS, stream to client
- Headers: `Content-Type`, `Content-Length`, `Access-Control-Allow-Origin: *`
- Status: 200 / 404 / 401

**HEAD /<sha256>** — Check existence
- Same as GET but no body
- Returns `Content-Type` + `Content-Length`

**PUT /upload** — Upload blob
- Read `Authorization` header → verify BUD-11 auth
- Stream body to LittleFS temp file
- Compute SHA256 of received bytes (mbedtls HW accelerated)
- Verify hash matches `x` tag from auth event
- Rename temp file to `/<sha256>`
- Write sidecar `/<sha256>.meta` JSON
- Return Blob Descriptor JSON:
  ```json
  {"url":"http://<ip>/<sha256>","sha256":"<64hex>","size":N,"type":"<mime>","uploaded":<ts>}
  ```
- Status: 201 (new) / 200 (exists) / 401 / 413 (too large) / 409 (hash mismatch)

**OPTIONS *** — CORS preflight
- Headers: `Access-Control-Allow-Origin: *`, `Access-Control-Allow-Headers: Authorization, *`, `Access-Control-Allow-Methods: GET, HEAD, PUT, DELETE`

## 6. Storage Design

### File Layout
```
/blossom/          ← LittleFS mount point
  ├── <sha256>         ← raw blob bytes
  ├── <sha256>.meta    ← JSON: {"size":N,"type":"mime","uploaded":ts}
  └── ...
```

### Metadata Sidecar
Each blob gets a `.meta` JSON file storing MIME type, size, upload timestamp.
Keeps blob files pure binary (no header parsing needed for GET).

### Storage Limits (ESP32-C3)
- Total flash: 4MB
- Firmware: ~1.8MB
- NVS: 16KB
- **Blossom partition: ~1.5MB** (adjustable via partitions.csv)
- **Max single blob: ~128KB** (limited by available heap for streaming buffer)
- **Max blobs: ~10-12** (assuming ~128KB average)

### Storage Limits (ESP32-S3)
- Total flash: 8MB typically
- **Blossom partition: ~4MB**
- **Max single blob: ~512KB** (more heap available)
- **Max blobs: ~30-40**

### LRU Eviction (future)
If partition full and upload requested, delete oldest blob by `.meta` timestamp.
Not in Phase 2 — add when needed.

## 7. C3 Constraints & Mitigations

| Constraint | Impact | Mitigation |
|-----------|--------|------------|
| 400KB RAM | Limited heap for buffers | Stream upload in 512-byte chunks. No full-body buffering. |
| No PSRAM | Can't cache large blobs | Direct flash read → HTTP send, no intermediate buffer >4KB |
| 4MB flash | Limited storage | ~1.5MB blossom partition. Document as constraint. |
| RISC-V single-core | Lower throughput | mbedtls HW SHA256 offloads crypto. Schnorr verify ~50ms acceptable. |
| No FPU | Slow float ops | No float operations in blossom server code. |

## 8. Dependencies

### Port from esp32-tollgate (extract, do NOT modify source)
- `components/wisp_relay/relay_validator.c` + `.h`
- `components/wisp_relay/relay_types.c` + `.h`
- `nucula_src/components/secp256k1/` (full component)
- `components/esp_littlefs/` (full component)

### ESP-IDF Built-in
- `esp_http_server` — HTTP server
- `mbedtls` — SHA256 (hardware accelerated on C3)
- `nvs_flash` — NVS for config
- `cjson` — JSON parsing (via `esp_idf_component_manager` or vendored)

## 9. Project Structure

```
balloon-blossom/
├── docs/
│   └── design.md          ← this file
├── CMakeLists.txt          ← top-level
├── partitions.csv          ← flash partition table
├── main/
│   ├── CMakeLists.txt
│   ├── blossom_server.c    ← main entry, WiFi + HTTP init
│   ├── blossom_handlers.c  ← BUD-01/02 endpoint handlers
│   ├── blossom_handlers.h
│   ├── blossom_auth.c      ← BUD-11 auth verification
│   ├── blossom_auth.h
│   ├── blossom_storage.c   ← LittleFS blob storage
│   ├── blossom_storage.h
│   └── blossom_config.h    ← compile-time settings
└── components/
    ├── secp256k1/          ← ported from tollgate nucula_src
    ├── esp_littlefs/       ← ported from tollgate
    ├── relay_validator/    ← ported from tollgate wisp_relay
    └── relay_types/        ← ported from tollgate wisp_relay
```

## 10. Implementation Phases

### Phase 2A — Foundation (port components)
1. Copy + adapt secp256k1, esp_littlefs, relay_validator, relay_types into components/
2. Create partitions.csv with blossom data partition
3. Create CMakeLists.txt structure
4. Verify builds clean (S3 first)

### Phase 2B — Storage Layer
5. Implement `blossom_storage.c`: init LittleFS, store/retrieve/delete blobs
6. Unit test: write blob, read back, verify hash

### Phase 2C — HTTP Endpoints
7. Implement `blossom_handlers.c`: GET, HEAD, OPTIONS handlers
8. Test GET/HEAD with pre-seeded blob

### Phase 2D — Upload + Auth
9. Implement `blossom_auth.c`: parse + verify BUD-11 auth
10. Implement PUT /upload handler with streaming
11. Test full upload flow with curl

### Phase 3 — Test on Hardware
12. Flash to S3 board, curl test
13. Flash to C3 board, verify constraints
14. Benchmark: upload/download speed, max blob size

## 11. Open Questions for Orchestrator

1. **WiFi mode:** Should blossom server run in AP mode (balloon broadcasts WiFi) or STA mode (balloon joins existing network)? AP mode is natural for captive portal.
2. **Auth policy:** Require BUD-11 auth for all endpoints, or allow anonymous GET/HEAD (download without auth)?
3. **NIP-94 events:** Should server publish NIP-94 file metadata events to the Nostr relay (Track 2) after upload? Cross-track dependency.
4. **Flash partition size:** Confirm 1.5MB acceptable on C3, or does firmware need more?
5. **GitHub remote:** Create `felixfelix-bot/balloon-blossom` or fold into existing balloon-fresh repo?
