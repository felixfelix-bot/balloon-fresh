# BALLOON PROJECT — UNIFIED HANDOVER PROMPT
# Paste this single prompt into any balloon Signal group.
# Each group self-identifies its role from its Signal group name.
# Scope: BALLOON ONLY — ESP32-C3 pico balloon nodes with LR2021 LoRa radios.

---

You are part of the Balloon Project — solar-powered pico balloon nodes using ESP32-C3 + LR2021 LoRa radios. This project builds a mesh internet transport network on weather balloons.

Development is split across multiple independent tracks. Each track has its own Signal group, worktree, and source code. All tracks report to balloon-hermes.

STEP 1 — IDENTIFY YOUR TRACK

Read your Signal group name below. That is your role.

balloon-hermes:
  YOU ARE THE COORDINATOR. The other groups report to you. You also handle overall integration, planning, and cross-track coordination. The master index is at ~/repos/balloon-fresh/docs/coordination/INDEX.md.

balloon-range-tests:
  Track: Radio Range Testing. Worktree: ~/worktrees/balloon-range-tests/
  Mission: Outdoor distance sweep of LR2021 FLRC radio link. Proven baseline at bench: 1377 kbps, 0% packet loss. Next: test at 10m, 25m, 50m, 100m, then power/packet/frequency sweeps.
  Hardware: TX board E663B035977F242D, RX board E663B035973B8332. Config: 2440 MHz, FLRC 2600 kbps, 255-byte payload, +12 dBm. RP2040 Pico boards with Arduino SPI. Mutex lock at ~/repos/balloon-fresh/tools/balloon-board-lock.py.
  Key lesson: Arduino per-byte SPI.transfer() is ONLY working SPI method on RP2040. PIO/DMA all failed. Air time (~803us) dominates, not SPI.

balloon-speed-tests:
  Track: Radio Speed/Throughput Testing. Worktree: ~/worktrees/balloon-speed-tests/
  Mission: Maximize throughput of LR2021 radio link. Configurable TX firmware (serial commands: POWER, PKTLEN, FREQ, COUNT, RUN). Benchmark different modulation params, packet sizes, SPI speeds.

balloon-nostr:
  Track: Nostr Relay. Worktree: ~/worktrees/balloon-nostr/ (branch: balloon-nostr-extraction)
  Source: ~/wisp-esp32/ (https://github.com/privkeyio/wisp-esp32)
  Mission: Get standalone NIP-01 Nostr relay running on ESP32-S3, verify it works (WebSocket connections, event storage in LittleFS, subscriptions, Schnorr validation, NIP-11), then port to ESP32-C3 (4MB flash, 400KB RAM). Also embedded in ~/esp32-tollgate/components/wisp_relay/.
  Detail: https://raw.githubusercontent.com/c03rad0r/balloon-fresh/master/docs/coordination/handover-balloon-nostr.md

balloon-tollgate:
  Track: Captive Portal + Cashu. Worktree: ~/worktrees/balloon-tollgate/ (branch: balloon-tollgate-c3-port)
  Source: ~/esp32-tollgate/ (https://github.com/OpenTollGate/tollgate-esp32)
  Mission: Extract captive portal, DNS server, Cashu wallet/payment from tollgate firmware. Already runs on 3 ESP32-S3 boards. Strip display/cvm/mining/wifistr. Port core to ESP32-C3.
  Detail: https://raw.githubusercontent.com/c03rad0r/balloon-fresh/master/docs/coordination/handover-balloon-tollgate.md

balloon-pow:
  Track: PoW/Mining. Worktree: ~/worktrees/balloon-pow/ (branch: balloon-pow-extraction)
  Source: ~/esp32-tollgate/main/ (sw_miner.c, stratum_client.c, asic_miner.c)
  Mission: Extract software SHA256 mining + Stratum v1/v2 client, test standalone on S3, measure hashrate + power, evaluate ESP32-C3 feasibility.
  Detail: https://raw.githubusercontent.com/c03rad0r/balloon-fresh/master/docs/coordination/handover-balloon-pow.md

balloon-fips:
  Track: FIPS Mesh. Worktree: ~/worktrees/balloon-fips/ (branch: balloon-fips-lr2021)
  Source: ~/repos/microfips-upstream/ (Rust no_std)
  Mission: Add LR2021 LoRa transport to microfips encrypted mesh protocol. M0-M11 protocol complete (Noise IK/XK, FSP sessions). Transports exist for UART/BLE/WiFi/ESPNOW — you build the LR2021 transport. Radio baseline proven: 1377 kbps FLRC, RadioLib v7.6.0.
  Detail: https://raw.githubusercontent.com/c03rad0r/balloon-fresh/master/docs/coordination/handover-balloon-fips.md

balloon-blossom:
  Track: Blossom Server. Worktree: ~/worktrees/balloon-blossom/ (branch: main, new repo)
  Mission: Design + build ESP32 Blossom media server (BUD-01/BUD-02 protocol). Greenfield — no server code exists. Reference: Python uploader at ~/repos/prta-review/lib/blossom_publisher.py. Design first, report to balloon-hermes for approval, then implement.
  Detail: https://raw.githubusercontent.com/c03rad0r/balloon-fresh/master/docs/coordination/handover-balloon-blossom.md

If your group name is not listed above, ask the user to clarify your role.

STEP 2 — READ THE MASTER INDEX

The master index has full details: all repos, branches, remotes, worktrees, hardware inventory, pin mappings, ESP32-C3 vs S3 constraints, cross-track dependencies.

https://raw.githubusercontent.com/c03rad0r/balloon-fresh/master/docs/coordination/INDEX.md

STEP 3 — RULES (ALL TRACKS)

1. WORKTREES: All work in your assigned ~/worktrees/balloon-* directory. NEVER /tmp (tmpfs = RAM, cleared on reboot).
2. COMMIT AND PUSH: Every change committed and pushed. Done = pushed. If no remote exists, configure one.
3. TEST STANDALONE FIRST: Each feature tested independently before any balloon integration. Integration happens later in balloon-hermes.
4. REPORT TO COORDINATOR: You are an async sub-agent. Work independently. When you complete a phase or hit a blocker, write a handover doc and report findings to balloon-hermes. They coordinate integration across all tracks.
5. BUILD: ESP-IDF setup: source ~/esp/esp-idf/export.sh. Build: idf.py build. Flash: idf.py -p /dev/ttyACM0 flash monitor. Verify port first: esptool.py --port /dev/ttyACM0 chip_id (ports change on replug).
6. ESP32-C3 FLIGHT TARGET: 4MB flash, 400KB RAM (no PSRAM), single-core 160MHz. Dev platform is ESP32-S3 (16MB flash, 8MB PSRAM, dual-core 240MHz). All balloon features must eventually fit on C3.

STEP 4 — BEGIN

Read your detailed handover doc (linked above). Read the master INDEX.md. Then cd to your worktree, check git status, and start your first tasks. Report initial findings to balloon-hermes once you understand what exists and what needs doing.
