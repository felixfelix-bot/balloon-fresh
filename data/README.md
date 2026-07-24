# Data Directory Structure

All walk test data follows this convention:

```
data/
  walk-YYYY-MM-DD/
    capture-rx.txt          # raw RX capture with metadata header
    capture-rx_packets.txt  # per-packet CSV with metadata header
    capture-rx.meta         # TX firmware sidecar (written when first PKT tx_fw seen)
    phone-gps.csv           # phone GPS ground truth
    metadata.json           # structured metadata (from template)
    plots/                  # generated plots (6 standard)
    analysis.md             # post-walk analysis
```

## Capture File Format

Each capture file starts with a metadata header (lines starting with `#`), then CSV data:

```
# CAPTURE START 2026-07-24T19:00:00+00:00
# RX_FIRMWARE FW_BOOT hash=abc1234 tag=RX0 built=2026-07-24T12:00:00Z
# TX_FIRMWARE (pending — will appear in first PKT tx_fw field)
# OPERATOR: alice
# ENV: outdoor
# DISTANCE_START: 0
# CYCLES: 999
# PORT: /dev/balloon-rx
# NOTES: balcony walk test
timestamp_iso,cycle,phase,name,...
```

## TX Firmware

TX firmware cannot be queried directly (TX is in the rucksack, not connected to the laptop).
Instead:

1. The capture header says "TX_FIRMWARE (pending)"
2. When the first PKT line with `tx_fw=<hash>` arrives, a sidecar `.meta` file is written
3. After capture, copy the TX hash into `metadata.json`

## metadata.json

Created from `data/metadata-template.json` by `tools/pre-walk-check.sh`.
Fill in operator name, firmware hashes, and notes after the walk.

Fields:
- `firmware_match`: true if TX and RX firmware hashes match
- `verified_before_walk`: true if pre-walk-check.sh ran successfully
- `walk_distance_km`: total distance walked (from phone GPS)
- `duration_min`: capture duration in minutes
