# REPORT — ADR-038 (Wi-Fi/BT disabled on v9 ESP32-S3)

## Authoring
- Branch: `adr/wifi-bt-disabled` on worktree `/home/c03rad0r/worktrees/bf-adr-wifi`.
- Base: observed tip of `adr/radioband-tdm` (github and ngit both returned `8b46f6873f815425acb7203da1d22685e954d404`).
- Files created/modified:
  - `docs/adr/038-wifi-bt-disabled.md` (new)
  - `docs/adr/029-dual-band-flight-board.md` (amended line 261 config row)
  - `PROGRESS.md` (new)
  - `REPORT.md` (new)
- Commit SHA (local, before push): **COMMIT_SHA_TBD** — this report will be updated after push.

## Datasheet verification (cited)
- ESP32-S3 Series Datasheet v2.2, §1: ESP32-S3 is an SoC *"with integrated 2.4 GHz Wi-Fi and Bluetooth® 5 (LE)"* — PHY is on-die.
- ESP32-S3-WROOM-1 & WROOM-1U Datasheet v1.8, §1.2: all variants are Wi-Fi+BT LE modules; no radio-free variant exists.
- Same datasheet §10.2: `-1U` connector is U.FL/MHF I/AMC first-gen compatible; module ships without antenna.
- Power figures (ESP32-S3 Series Datasheet v2.2, §5.6.2): Wi-Fi TX 802.11b@21dBm=340mA peak; RX=88-91mA; BLE TX@21dBm=335mA; modem-sleep=13.2-66.7mA; light-sleep=240µA; deep-sleep=7-8µA.

## Key verdicts
- Part/variant: **unchanged** — keep `ESP32-S3-WROOM-1U-N8R8`, leave U.FL unpopulated.
- Idle-power saving: small; real cost is +20 dBm TX bursts and 2.4 GHz activity.
- Mass saving: ~3–12 g (ESTIMATE) — single-digit to low-teens grams; not a mass lever.
- Coexistence: removes the S3 as a fourth 2.4 GHz self-jammer; ADR-029 §2(b) / `WIFI_2G4` slot gets simpler.
- Regulatory: all 2.4 GHz use now under operator's amateur licence; no mixed regime.
- ADR-034 separate 2.4 GHz receiver stands; parked question is closed.
- Config path: USB/serial (bench) + radio link (flight); ADR-029 row updated.
- MCU choice not reopened; v9 = S3 remains (ADR-037, in flight).

## UNVERIFIED
- Exact never-initialised quiescent current of the S3 RF subsystem; would be settled by a
  bench measurement with `CONFIG_ESP_WIFI_ENABLED=n` / `CONFIG_ESP_BT_ENABLED=n`.

## Push verification
- github SHA after push: **TBD**
- ngit SHA after push: **TBD**
