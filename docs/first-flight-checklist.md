# First Flight Checklist

## Variant: Minimal (~9g) — Range/Throughput Characterization

## Pre-Flight Hardware

- [ ] ESP32-C3_Mini_V1 dev board flashed with `CONFIG_ENABLE_GPS=y`
- [ ] NiceRF LoRa2021 wired to ESP32-C3 per pin mapping
- [ ] u-blox MAX-M10S GPS on UART1 (GPIO0 TX, GPIO1 RX)
- [ ] Wire dipole antenna on Sub-GHz port (Pin 9, 868 MHz, ~8.6 cm each leg)
- [ ] Solar cells connected (52x19mm, 2S configuration for ~1.0V 400mA)
- [ ] Supercapacitor bank connected and charged
- [ ] BMP280 on I2C (GPIO8 SDA, GPIO9 SCL) — optional for first flight
- [ ] All connections soldered, no breadboard jumpers
- [ ] Weight verified: total payload < 9g (without balloon)
- [ ] Antenna SWR checked if possible (analyzer or indirect via RSSI)

## Pre-Flight Firmware

- [ ] `idf.py build` succeeds with no warnings
- [ ] Unit tests pass: `gcc -o /tmp/test test_telemetry_gps.c && /tmp/test` → 17/17
- [ ] GPS fix obtained outdoors (check NMEA output on serial)
- [ ] LoRa TX verified with SDR or second LoRa module (ground station)
- [ ] Telemetry decoded by ground station receiver (JSON output)
- [ ] Deep sleep current measured: should be < 50 uA
- [ ] TX interval configured (default: 120s)
- [ ] Callsign hash set in firmware

## Pre-Flight Ground Station

- [ ] Ground station receiver flashed and running
- [ ] Antenna connected (868 MHz, ideally directional Yagi)
- [ ] USB serial monitor running with JSON output logging
- [ ] Battery/power for ground station (laptop + receiver)
- [ ] Position logging to file enabled

## Balloon Preparation

- [ ] Yokohama 32" Crystal Clear inspected for defects
- [ ] Humidity environment: store balloon in humid area 24h before (manufacturer recommendation)
- [ ] Heat sealer tested on scrap balloon film
- [ ] Kapton tape cut and ready
- [ ] Scale calibrated (MS300, non-magnetic surface)

## Inflation (Outdoor or Well-Ventilated Area)

- [ ] Bauhaus Party Factory He canister ready
- [ ] Inflate to ~85% initially, wait 1-2 hours, top up to ~90-95%
- [ ] Do NOT overinflate — balloon should be soft, not taut
- [ ] Measure neck opening, heat seal closed
- [ ] Apply Kapton tape over heat seal (reinforcement)
- [ ] Measure net lift: balloon weight - payload weight should give 5-7g free lift
- [ ] If insufficient lift: reduce payload or use purer He

## Launch

- [ ] Weather check: no storms, jet stream direction favorable
- [ ] HYSPLIT trajectory run: verify no ocean crossing in first 48h
- [ ] Wind speed < 20 km/h at ground level
- [ ] GPS fix confirmed (LED or serial check)
- [ ] Final weight check: total system (balloon + payload) logged
- [ ] Release in open area, away from trees/power lines
- [ ] Note exact launch time and position
- [ ] Start ground station logging

## Post-Launch Monitoring

- [ ] First telemetry reception confirmed on ground station
- [ ] Log all received packets with timestamp, RSSI, SNR
- [ ] Monitor for at least 2 hours (ensure regular transmission)
- [ ] Upload position data to tracking service if available
- [ ] Note signal strength patterns (fading, directional effects)

## Emergency / Abort Criteria

- **No telemetry received within 30 min of launch** — likely hardware failure
- **Net lift < 3g** — balloon may not ascend, abort inflation and retry
- **GPS never gets fix after 15 min outdoors** — check wiring, firmware
- **Balloon leaks audibly after inflation** — discard, use new balloon

## Key Measurements to Record

| Measurement | Target | Actual |
|-------------|--------|--------|
| Payload weight | < 9g | ___g |
| Balloon weight | ~7-8g | ___g |
| Net free lift | 5-7g | ___g |
| First GPS fix time | < 5 min | ___min |
| First TX received RSSI | > -100 dBm | ___dBm |
| Time between packets | 120s ± 5s | ___s |
| Deep sleep current | < 50 uA | ___uA |
