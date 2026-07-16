# HANDOVER: Range Testing Track (2026-07-17)

## For the next context window picking up range testing

This document gives a fresh agent everything needed to continue range
testing without reading the full session history.

---

## WHAT YOU'RE DOING

Characterizing the LR2021 FLRC radio link across distance, TX power,
packet size, modulation mode, antenna type, and frequency. The goal is
to find maximum reliable range and optimal flight configuration.

## WHAT'S ALREADY DONE

- Two RP2040+LR2021 boards with working firmware
- Proven radio link: 1377 kbps, 1000/1000 TX_DONE, 0% RX packet loss
- Radio config: 2440 MHz, FLRC 2600 kbps, 255-byte packets, +12 dBm
- Sync word: 0x12AD101B (both boards matched)
- Coordinated test harness: scripts/coordinated_tx_rx_test.py
- Commits: eee6147 (IRQ fix), a99b64c (TX baseline), dceb6e5 (coordinated test)

## WHAT YOU NEED TO DO

Follow: docs/range-test-comprehensive-plan-2026-07-17.md

Execution order:
1. Session 1: Distance sweep (10m, 25m, 50m, 100m outdoor LOS)
2. Session 2: TX power sweep (0→12.5 dBm) + packet size sweep (16→255 bytes)
3. Session 3: Modulation comparison (FLRC vs LoRa)
4. Session 4: Antenna + frequency sweep

## HARDWARE

| Item | Quantity | Notes |
|------|----------|-------|
| RP2040 + LR2021 TX board | 1 | Serial E663B035973B8332 |
| RP2040 + LR2021 RX board | 1 | Serial E663B035977F242D |
| Wire dipole antennas | 2 | λ/2 = 61mm at 2440 MHz |
| USB cables | 2+ | Micro-USB, bring spares |
| Laptop | 1 | Full battery for outdoor |
| Anti-static bags | 2 | For transport |

## FIRMWARE

Current working firmware (DO NOT CHANGE without reason):
- TX: `firmware/rp2040/src/flrc_raw_tx.cpp` — env `rp2040-flrc-tx-raw`
- RX: `firmware/rp2040/src/flrc_rx_raw.cpp` — env `rp2040-flrc-rx-raw`

Flash commands:
```
cd ~/repos/balloon-fresh/firmware
make rp2040-flash ENV=rp2040-flrc-tx-raw PORT=/dev/ttyACMX
make rp2040-flash ENV=rp2040-flrc-rx-raw PORT=/dev/ttyACMY
```

IMPORTANT: Port assignments SWAP after every BOOTSEL flash. Always
re-discover ports with: `for d in /dev/ttyACM*; do udevadm info -q property $d | grep SERIAL_SHORT; done`

## HIGHEST-VALUE NEXT STEP

Write a configurable TX firmware that accepts serial commands to change
power, packet size, and frequency at runtime. This avoids reflashing
between every test point. See "FIRMWARE NEEDED" in the range test plan.

Commands to implement:
- `POWER 12` — set TX power
- `PKTLEN 64` — set packet size
- `FREQ 2422` — set frequency
- `COUNT 500` — set packet count
- `RUN` — start transmission

## KEY FACTS

- LR2021 is a Semtech LR2021 Gen 4 (SX1281 derivative), NOT LR10xx
- FLRC = Fast LoRa, a modulation mode in the SX1281/LR2021 family
- RadioLib v7.6.0 is used for radio init (then raw SPI for hot loop)
- 1200 baud touch on /dev/ttyACMX triggers RP2040 BOOTSEL mode
- CDC DTR fix needed: use pyserial with dtr=True, or firmware delay(2000)
- LR2021 max SPI clock: ~18 MHz (SX1281 spec), RP2040 delivers ~12 MHz actual
- The EBYTE E28-2G4M27S (+27 dBm) boards are NOT integrated yet

## WHAT NOT TO DO

- Don't change radio init parameters without testing at 1m first
- Don't use 1200 baud unless you want to trigger BOOTSEL
- Don't assume port assignments are stable after flash
- Don't forget to match sync words between TX and RX
- Don't attempt throughput optimization — that's the OTHER track
  (see docs/speed-test-comprehensive-plan-2026-07-17.md)

## DATA FORMAT

Record every test result as:
```
RANGE_TEST,date=YYYY-MM-DD,distance_m=X,power_dbm=Y,pkt_size=Z,\
mode=FLRC2600,freq_mhz=2440,antenna=TYPE,orientation=ORIENT,\
packets_sent=N,packets_rx=M,loss_pct=P,throughput_kbps=K,notes=ENV
```

Save to: docs/range-test-results-2026-07-XX.md

## COMMIT EVERYTHING

After each test session:
```
cd ~/repos/balloon-fresh
git add docs/range-test-results-*.md
git commit -m "test: range test session N — distance/power/pktsize results"
git push github master && git push origin master
```

## LINKS

- Full plan: docs/range-test-comprehensive-plan-2026-07-17.md
- Master plan: docs/lr2021-dual-track-master-plan-2026-07-17.md
- Other track: docs/speed-test-comprehensive-plan-2026-07-17.md
- Repo: ~/repos/balloon-fresh
- Pin mapping: firmware/rp2040/src/flrc_raw_tx.cpp (header comment)
