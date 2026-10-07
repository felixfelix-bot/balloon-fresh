# PROGRESS — ADR-038 (Wi-Fi/BT disabled on v9 ESP32-S3)

## Done
1. Read brief `ADR-BRIEF-9-wifi-bt-disabled.md` in full.
2. Created worktree `/home/c03rad0r/worktrees/bf-adr-wifi` off observed tip
   `8b46f6873f815425acb7203da1d22685e954d404` (verified via `git ls-remote` github + ngit).
3. Verified datasheet facts against Espressif PDFs downloaded to /tmp (not committed):
   - ESP32-S3 Series Datasheet v2.2 — on-die/integrated 2.4 GHz Wi-Fi + BT5(LE), §1.
   - ESP32-S3-WROOM-1 & WROOM-1U Datasheet v1.8 — all variants Wi-Fi+BT LE; -1U external
     connector (U.FL/MHF I/AMC); ships without antenna.
   - Power tables 5-7..5-10: TX 802.11b@21dBm=340mA, RX 88-91mA, BLE TX 335mA,
     modem-sleep 13.2-66.7mA, light-sleep 240µA, deep-sleep 7-8µA.
4. Wrote `docs/adr/038-wifi-bt-disabled.md`.
5. Added pointer in `docs/adr/029-dual-band-flight-board.md` line 261 (config row).

## Todo
- Stage explicit paths, commit, push github then ngit sequentially, verify ls-remote.
