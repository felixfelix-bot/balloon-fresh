# PER Stats Fix Verification — SF12 Hardware Test

**Date:** 2026-07-23
**Firmware:** rp2040-lora-rx-sf12 (with cumulativeRx fix, commit 9352337)
**Test:** 200-packet SF12 LoRa burst, 127-byte payload, 812 kHz BW, CR 4/5, 12 dBm

## Result: FIX VERIFIED ✅

The cumulativeRx PER stats fix works correctly on hardware.

### Window-by-Window Results

| Window | RX (this window) | Cumulative RX | Unique | Lost | Total (maxSeq+1) | PER |
|--------|-----------------|---------------|--------|------|-------------------|-----|
| 1 | 45 | 61 | 45 | 1 | 62 | 1.61% |
| 2 | 46 | 107 | 46 | 2 | 109 | 1.83% |
| 3 | 46 | 153 | 46 | 2 | 155 | 1.29% |
| 4 | 44 | 197 | 44 | 3 | 200 | **1.50%** |
| 5 | 0 | 197 | 0 | 0 | 1 | 0.00% (TX done) |
| 6 | 0 | 197 | 0 | 0 | 1 | 0.00% (TX done) |

### Final: 197/200 received, PER = 1.50%

### Bug vs Fix Comparison

| Metric | Old (buggy) | New (fixed) |
|--------|------------|-------------|
| PER per window | 78.50% | 1.50% |
| Cumulative tracking | No (reset each window) | Yes (preserved) |
| Root cause | received=0 after resetStats, maxSeq keeps climbing | cumulativeRx survives resetStats |

### RSSI/SNR (also fixed this session)

- RSSI: -8.0 dBm (correct for 1-2m indoor)
- SNR: 31.8 dB (correct for strong signal)
- Both confirmed stable across all windows
