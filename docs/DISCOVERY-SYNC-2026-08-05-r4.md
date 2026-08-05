# Discovery Sync — 2026-08-05 (Round 4)

## Source: balloon-hermes (7 new findings — PCB design + tooling)

### Assessment for balloon-fips

| # | Finding | Tags | FIPS Impact | Action |
|---|---------|------|-------------|--------|
| 1 | V2-ADC board — supercap ADC (bc8aa63) | POWER, FIRMWARE, HARDWARE | NONE | PCB variant for tracker hub board. FIPS runs on C3 SuperMini, separate hardware. |
| 2 | V1-FAST board — no ADC (8c46d99) | FIRMWARE, HARDWARE | NONE | Simplified PCB variant. Not FIPS hardware. |
| 3 | ESP32-C3 MINI-1 pinout verification (4b7203b) | FIRMWARE, HARDWARE | INFORMATIONAL | Confirms GPIO8 has NO ADC. Our fips_bridge uses LED on GPIO8 — fine, we don't need ADC. C3 SuperMini pinmap confirmed compatible with our LR2021 SPI pins (NSS=10, MOSI=7, MISO=2, SCK=6, RST=3, BUSY=4, IRQ=5). |
| 4 | LLM auto-routing pipeline (c542afb) | HARDWARE, PROTOCOL | NONE | PCB auto-routing tooling. Not FIPS scope. |
| 5 | Auto-routing feasibility verified (ee9b6ba) | HARDWARE, PROTOCOL | NONE | python3.14+pcbnew pipeline. Not FIPS scope. |
| 6 | V1 GPIO fix — LED off GPIO10, FEM_TX net (698a039) | HARDWARE, TEST | NONE | Same GPIO10 fix as earlier sync — LED removed from NSS pin. Already confirmed no FIPS impact. |
| 7 | Integration plan V3 — PCB first, FIPS second (f156ef7) | HARDWARE | INFORMATIONAL | Notes FIPS as second priority after PCB. Relevant for sequencing awareness. |

## Summary

Entirely PCB design + hardware tooling findings. Zero FIPS firmware/transport/protocol impact.

One useful confirmation: ESP32-C3 MINI-1 pinout verified — our LR2021 SPI pin assignments (from lr2021_spi.h) are all valid on the MINI-1 module. GPIO8 LED choice confirmed safe (no ADC needed for FIPS).

No action required.
## Addendum — 2 more findings (V2-ADC routing scripts)

| # | Finding | Tags | FIPS Impact |
|---|---------|------|-------------|
| 8 | V2-ADC board regenerate + routing scripts | HARDWARE, PROTOCOL | NONE — PCB tooling |
| 9 | V2-ADC routing WIP + finish_routing.py | HARDWARE, PROTOCOL | NONE — PCB tooling |

No action required.

## Addendum 2 — 4 more findings (PCB routing pipeline)

| # | Finding | Tags | FIPS Impact |
|---|---------|------|-------------|
| 10 | 4-layer scripts + DSN/SES files | HARDWARE, PROTOCOL | NONE — PCB tooling |
| 11 | kimi-k3 2-layer power routing scripts | HARDWARE, PROTOCOL | NONE — PCB tooling |
| 12 | V2-ADC 2-layer FINAL gerbers | HARDWARE, PROTOCOL | NONE — PCB tooling |
| 13 | finish_2layer.py one-shot routing | HARDWARE, PROTOCOL | NONE — PCB tooling |

No action required. PCB manufacturing pipeline. Zero FIPS scope.

## Addendum 3 — 2 more findings (C3 flight PCB)

| # | Finding | Tags | FIPS Impact |
|---|---------|------|-------------|
| 14 | C3 flight PCB routing — 80 tracks, 26 vias | HARDWARE, PROTOCOL | NONE — PCB manufacturing |
| 15 | C3 flight PCB WIP — 20 footprints, routing incomplete | HARDWARE, PROTOCOL | NONE — PCB manufacturing |

No action required.
