# Discovery Sync — 2026-08-05

## Source: balloon-hermes (6 new findings)

### Assessment for balloon-fips

| # | Finding | Tags | FIPS Impact | Action |
|---|---------|------|-------------|--------|
| 1 | TransportError scope, API alignment (489123b) | FIRMWARE, PROTOCOL | NONE | nostr_store component, not lr2021_transport. Different TransportError enum. No conflict. |
| 2 | FreeRTOS relay task architecture — radio_task, app_task, queue-based RX (1f4fbef) | PROTOCOL | ALIGNMENT | balloon-hermes defines radio_task/app_task split. My fips_bridge.cpp already uses similar pattern (radioRxTask + uartToRadioTask + ISR notification). Review for task naming/priority alignment during integration. |
| 3 | secp256k1 component added to tracker firmware, smoke test (0829953) | FIRMWARE, TEST | INFORMATIONAL | FIPS meshcore uses ed25519 (not secp256k1). Relevant only if FIPS identity switches to secp256k1-based Nostr identity. |
| 4 | GPIO10 collision — LED vs LR2021 NSS + GPS/FEM GPIO1 collision (f926dc9) | RADIO | NO IMPACT | LED moved GPIO10→GPIO18 (LED side, not NSS). NSS stays GPIO10. My fips_bridge uses LED on GPIO8 — already safe. FEM_TX (GPIO1→GPIO19) only relevant if FIPS adds FEM support. |
| 5 | FLRC fixes, board lock tooling, coordination (0292aec) | RADIO | INFORMATIONAL | FLRC radio improvements. Board lock tooling already adopted (v3). |
| 6 | FreeRTOS task architecture design doc (ce75512) | GENERAL | REFERENCE | Review ARCHITECTURE-FREERTOS-TASKS.md when integrating unified firmware image. |

## Summary

**Zero blocking impacts.** My LR2021 SPI pin config (NSS=GPIO10, MOSI=7, MISO=2, SCK=6, RST=3, BUSY=4, IRQ=5) is confirmed correct and unaffected by the GPIO10 collision fix.

**One alignment opportunity:** FreeRTOS task architecture (radio_task/app_task/queue-RX) from balloon-hermes should be reviewed when building the unified firmware image. My fips_bridge.cpp already implements a similar pattern but may need renaming/priority alignment for consistency.

**No action required now.** All findings assessed as informational or already-compatible.
