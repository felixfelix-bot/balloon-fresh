# LR2021 local source inventory — what already exists on this host

**Task:** `t_5a6297cf` (Inventory LR2021 sources already present in the local repos)  
**Generated:** 2026-09-30 23:06 UTC on c03rad0r-DQ05proplus  
**Method:** read-only recon — `git ls-files` / `git ls-tree` / `find` / `grep -rI` / `md5sum` / `pdftotext`. No file outside this deliverable was written.  
**Scope rule:** sourcing only. The `plausible blocks` column records which register/command **token families occur in the file text** — it is *not* a statement about register behaviour.

Legend — blocks: **TXP** SetTxParams/power/ramp · **ARX** SetAutoRxTx/SetRxTxFallback/SetRx/SetTx · **FIFO** WriteTxFifo/ReadRxFifo/clear/level · **IRQ** IRQ status/clear/DIO mapping · **CALIB** calibration/PA config · **ERRATA** errata/workaround text.

Repos searched: `~/repos/*` (56 repos) and `~/worktrees/*` for filenames; content greps run per repo; full text greps of every repo exceeded the tool budget and were replaced by per-repo `grep -rI` + `git ls-tree` of the LR2021-bearing repos.

---

## 1. Published LR2021 corpus (already pushed) — balloon-fresh `docs/lr2021-research/`

Revision: **felixfelix-bot/balloon-fresh @ 55b6cf85 (origin/main)** (corpus landed by kanban task `t_dbcc7e9a`; all 33 files are git-tracked blobs at that commit).  
Local checkout used: `/home/c03rad0r/worktrees/t_5a6297cf-inv` (branch `pr/lr2021-local-inventory`, ff of origin/main).

| local path (repo-root-relative) | type | bytes | lines | md5(8) | revision | role | plausible blocks |
|---|---|---|---|---|---|---|---|
| `docs/lr2021-research/SOURCES.md` | md | 15045 | 112 | 5049a9e6 | 55b6cf85 | manifest | TXP, ARX, FIFO, IRQ, ERRATA (token-presence only) |
| `docs/lr2021-research/radiolib-master/LICENSE.txt` | txt | 1068 | 21 | ffcaa8d7 | 55b6cf85 | third-party-driver-support | none (no command/register tokens observed) |
| `docs/lr2021-research/radiolib-master/LR11x0_commands.h` | h | 54737 | 586 | 4af046e6 | 55b6cf85 | third-party-driver-support | TXP, ARX, IRQ, CALIB (token-presence only) |
| `docs/lr2021-research/radiolib-master/LR11x0_types.h` | h | 6350 | 230 | db826b65 | 55b6cf85 | third-party-driver-support | none (no command/register tokens observed) |
| `docs/lr2021-research/radiolib-master/LR2021-module/LR2021.cpp` | cpp | 39656 | 1201 | 94d7767d | 55b6cf85 | third-party-driver-source | ARX, FIFO, IRQ, CALIB (token-presence only) |
| `docs/lr2021-research/radiolib-master/LR2021-module/LR2021.h` | h | 49778 | 1080 | 468d5898 | 55b6cf85 | third-party-driver-source | TXP, ARX, FIFO, IRQ, CALIB, ERRATA (token-presence only) |
| `docs/lr2021-research/radiolib-master/LR2021-module/LR2021_cmds_chip_control.cpp` | cpp | 15930 | 399 | 8123d95f | 55b6cf85 | third-party-driver-source | ARX, FIFO, IRQ, CALIB, ERRATA (token-presence only) |
| `docs/lr2021-research/radiolib-master/LR2021-module/LR2021_cmds_flrc.cpp` | cpp | 2580 | 65 | 2ffdc666 | 55b6cf85 | third-party-driver-source | ERRATA (token-presence only) |
| `docs/lr2021-research/radiolib-master/LR2021-module/LR2021_cmds_gfsk.cpp` | cpp | 4542 | 100 | 4a02dff3 | 55b6cf85 | third-party-driver-source | ERRATA (token-presence only) |
| `docs/lr2021-research/radiolib-master/LR2021-module/LR2021_cmds_lora.cpp` | cpp | 6377 | 144 | 51aa6aef | 55b6cf85 | third-party-driver-source | ERRATA (token-presence only) |
| `docs/lr2021-research/radiolib-master/LR2021-module/LR2021_cmds_misc.cpp` | cpp | 1208 | 35 | 9d3a69a4 | 55b6cf85 | third-party-driver-source | ARX (token-presence only) |
| `docs/lr2021-research/radiolib-master/LR2021-module/LR2021_cmds_ook.cpp` | cpp | 4674 | 109 | 241f2816 | 55b6cf85 | third-party-driver-source | ERRATA (token-presence only) |
| `docs/lr2021-research/radiolib-master/LR2021-module/LR2021_cmds_oqpsk.cpp` | cpp | 2412 | 62 | ae71adc2 | 55b6cf85 | third-party-driver-source | none (no command/register tokens observed) |
| `docs/lr2021-research/radiolib-master/LR2021-module/LR2021_cmds_radio.cpp` | cpp | 4811 | 126 | 1c158141 | 55b6cf85 | third-party-driver-source | TXP, ARX, CALIB, ERRATA (token-presence only) |
| `docs/lr2021-research/radiolib-master/LR2021-module/LR2021_cmds_ranging.cpp` | cpp | 2644 | 64 | 31285cf4 | 55b6cf85 | third-party-driver-source | none (no command/register tokens observed) |
| `docs/lr2021-research/radiolib-master/LR2021-module/LR2021_commands.h` | h | 48984 | 534 | d92d1b27 | 55b6cf85 | third-party-driver-source | TXP, ARX, FIFO, IRQ, CALIB (token-presence only) |
| `docs/lr2021-research/radiolib-master/LR2021-module/LR2021_config.cpp` | cpp | 45527 | 1193 | 5de9bb7f | 55b6cf85 | third-party-driver-source | TXP, ARX, CALIB (token-presence only) |
| `docs/lr2021-research/radiolib-master/LR2021-module/LR2021_registers.h` | h | 1790 | 35 | b7c488ec | 55b6cf85 | third-party-driver-source | none (no command/register tokens observed) |
| `docs/lr2021-research/radiolib-master/LR2021-module/LR2021_types.h` | h | 1154 | 53 | 92dbf9cb | 55b6cf85 | third-party-driver-source | none (no command/register tokens observed) |
| `docs/lr2021-research/radiolib-master/PROVENANCE.md` | md | 1868 | 29 | 99500657 | 55b6cf85 | third-party-driver-support | TXP, ARX, FIFO, IRQ (token-presence only) |
| `docs/lr2021-research/semtech-official/AN1200.101_LR2021_FLRC_Improvements.pdf` | PDF | 915486 | binary | f7358eb9 | 55b6cf85 | vendor-datasheet/appnote | IRQ (pdf text token-presence only) |
| `docs/lr2021-research/semtech-official/AN1200.102_LR20xx_LoRaImprovements_Rev1.1.pdf` | PDF | 1397726 | binary | 6a6185e3 | 55b6cf85 | vendor-datasheet/appnote | TXP, ARX, IRQ, CALIB (pdf text token-presence only) |
| `docs/lr2021-research/semtech-official/AN1200.104_LR20xx_ModemInterface_v1.0.pdf` | PDF | 607936 | binary | 71f528d0 | 55b6cf85 | vendor-datasheet/appnote | TXP, FIFO, IRQ, CALIB (pdf text token-presence only) |
| `docs/lr2021-research/semtech-official/LR2021_LR2022_LR2012_Datasheet_v2.2.pdf` | PDF | 5980032 | binary | 18a392b7 | 55b6cf85 | vendor-datasheet/appnote | TXP, ARX, FIFO, IRQ, CALIB (pdf text token-presence only) |
| `docs/lr2021-research/vendor/balloon-lr2021-transport/lr2021_framing.cpp` | cpp | 1318 | 30 | ea5f14e0 | 55b6cf85 | first-party-driver-source | none (no command/register tokens observed) |
| `docs/lr2021-research/vendor/balloon-lr2021-transport/lr2021_framing.h` | h | 6709 | 207 | 806329a4 | 55b6cf85 | first-party-driver-source | none (no command/register tokens observed) |
| `docs/lr2021-research/vendor/balloon-lr2021-transport/lr2021_spi.cpp` | cpp | 17846 | 507 | 46c3be2c | 55b6cf85 | first-party-driver-source | TXP, ARX, FIFO, IRQ, CALIB (token-presence only) |
| `docs/lr2021-research/vendor/balloon-lr2021-transport/lr2021_spi.h` | h | 15156 | 373 | 8db7abde | 55b6cf85 | first-party-driver-source | TXP, ARX, FIFO, IRQ, CALIB (token-presence only) |
| `docs/lr2021-research/vendor/balloon-lr2021-transport/lr2021_transport.cpp` | cpp | 6055 | 184 | 747cb078 | 55b6cf85 | first-party-driver-source | ARX, IRQ (token-presence only) |
| `docs/lr2021-research/vendor/balloon-lr2021-transport/lr2021_transport.h` | h | 6938 | 181 | 551a4956 | 55b6cf85 | first-party-driver-source | none (no command/register tokens observed) |
| `docs/lr2021-research/vendor/meshcore-lr2021-patches/CustomLR2021.h` | h | 1327 | 46 | 8c64a0c9 | 55b6cf85 | first-party-integration-patch | ARX, IRQ (token-presence only) |
| `docs/lr2021-research/vendor/meshcore-lr2021-patches/CustomLR2021Wrapper.h` | h | 1645 | 63 | ee7d7e16 | 55b6cf85 | first-party-integration-patch | ARX, CALIB (token-presence only) |
| `docs/lr2021-research/vendor/meshcore-lr2021-patches/EspIdfHal.h` | h | 4842 | 162 | 2253faf1 | 55b6cf85 | first-party-integration-patch | none (no command/register tokens observed) |

Corpus totals: **33 files**; PDFs: 4 (datasheet Rev 2.2 + AN1200.101/102/104). The corpus manifest `SOURCES.md` records origin URLs, retrieval dates and version strings for each item (see that file; this inventory does not restate vendor URLs).

---

## 2. Working clone `~/repos/balloon-e80bench` (same repo, older main)

Revision: **felixfelix-bot/balloon-fresh @ 2e9d297e (~/repos/balloon-e80bench, main)**. `git status`: clean except one untracked scratch file (`firmware/e80-stm32-bench/rx-log.csv`, not LR2021 material).

### 2a. Vendored Semtech LR20xx driver + radio HAL (register/command defines present)

| local path (repo-root-relative) | type | bytes | lines | revision | plausible blocks |
|---|---|---|---|---|---|
| `firmware/e80-stm32-bench/third_party/Radio/lr20xx_driver/CHANGELOG.md` | md | 308 | 12 | tracked@2e9d297e last=c9748665 | none (no command/register tokens observed) |
| `firmware/e80-stm32-bench/third_party/Radio/lr20xx_driver/CMakeLists.txt` | txt | 2940 | 70 | tracked@2e9d297e last=c9748665 | none (no command/register tokens observed) |
| `firmware/e80-stm32-bench/third_party/Radio/lr20xx_driver/LICENSE.txt` | txt | 1807 | 30 | tracked@2e9d297e last=c9748665 | none (no command/register tokens observed) |
| `firmware/e80-stm32-bench/third_party/Radio/lr20xx_driver/README.md` | md | 10929 | 136 | tracked@2e9d297e last=c9748665 | ARX, FIFO, ERRATA (token-presence only) |
| `firmware/e80-stm32-bench/third_party/Radio/lr20xx_driver/inc/lr20xx_driver_version.h` | h | 3218 | 85 | tracked@2e9d297e last=c9748665 | none (no command/register tokens observed) |
| `firmware/e80-stm32-bench/third_party/Radio/lr20xx_driver/inc/lr20xx_hal.h` | h | 7542 | 179 | tracked@2e9d297e last=c9748665 | FIFO (token-presence only) |
| `firmware/e80-stm32-bench/third_party/Radio/lr20xx_driver/inc/lr20xx_radio_bluetooth_le.h` | h | 9895 | 212 | tracked@2e9d297e last=c9748665 | ARX, IRQ, ERRATA (token-presence only) |
| `firmware/e80-stm32-bench/third_party/Radio/lr20xx_driver/inc/lr20xx_radio_bluetooth_le_types.h` | h | 5870 | 135 | tracked@2e9d297e last=c9748665 | FIFO (token-presence only) |
| `firmware/e80-stm32-bench/third_party/Radio/lr20xx_driver/inc/lr20xx_radio_bpsk.h` | h | 3848 | 99 | tracked@2e9d297e last=c9748665 | none (no command/register tokens observed) |
| `firmware/e80-stm32-bench/third_party/Radio/lr20xx_driver/inc/lr20xx_radio_bpsk_types.h` | h | 7278 | 172 | tracked@2e9d297e last=c9748665 | FIFO (token-presence only) |
| `firmware/e80-stm32-bench/third_party/Radio/lr20xx_driver/inc/lr20xx_radio_common.h` | h | 28115 | 664 | tracked@2e9d297e last=c9748665 | TXP, ARX, CALIB, ERRATA (token-presence only) |
| `firmware/e80-stm32-bench/third_party/Radio/lr20xx_driver/inc/lr20xx_radio_common_types.h` | h | 18030 | 404 | tracked@2e9d297e last=c9748665 | ARX, CALIB (token-presence only) |
| `firmware/e80-stm32-bench/third_party/Radio/lr20xx_driver/inc/lr20xx_radio_fifo.h` | h | 8172 | 209 | tracked@2e9d297e last=c9748665 | FIFO, IRQ (token-presence only) |
| `firmware/e80-stm32-bench/third_party/Radio/lr20xx_driver/inc/lr20xx_radio_fifo_types.h` | h | 3566 | 96 | tracked@2e9d297e last=c9748665 | FIFO (token-presence only) |
| `firmware/e80-stm32-bench/third_party/Radio/lr20xx_driver/inc/lr20xx_radio_flrc.h` | h | 8072 | 206 | tracked@2e9d297e last=c9748665 | ARX, IRQ, ERRATA (token-presence only) |
| `firmware/e80-stm32-bench/third_party/Radio/lr20xx_driver/inc/lr20xx_radio_flrc_types.h` | h | 10099 | 251 | tracked@2e9d297e last=c9748665 | none (no command/register tokens observed) |
| `firmware/e80-stm32-bench/third_party/Radio/lr20xx_driver/inc/lr20xx_radio_fsk.h` | h | 10927 | 267 | tracked@2e9d297e last=c9748665 | ARX, IRQ, ERRATA (token-presence only) |
| `firmware/e80-stm32-bench/third_party/Radio/lr20xx_driver/inc/lr20xx_radio_fsk_common_types.h` | h | 10616 | 172 | tracked@2e9d297e last=c9748665 | none (no command/register tokens observed) |
| `firmware/e80-stm32-bench/third_party/Radio/lr20xx_driver/inc/lr20xx_radio_fsk_types.h` | h | 12889 | 274 | tracked@2e9d297e last=c9748665 | IRQ (token-presence only) |
| `firmware/e80-stm32-bench/third_party/Radio/lr20xx_driver/inc/lr20xx_radio_lora.h` | h | 22601 | 465 | tracked@2e9d297e last=c9748665 | ARX, ERRATA (token-presence only) |
| `firmware/e80-stm32-bench/third_party/Radio/lr20xx_driver/inc/lr20xx_radio_lora_types.h` | h | 17290 | 356 | tracked@2e9d297e last=c9748665 | ARX (token-presence only) |
| `firmware/e80-stm32-bench/third_party/Radio/lr20xx_driver/inc/lr20xx_radio_lr_fhss.h` | h | 6033 | 154 | tracked@2e9d297e last=c9748665 | none (no command/register tokens observed) |
| `firmware/e80-stm32-bench/third_party/Radio/lr20xx_driver/inc/lr20xx_radio_lr_fhss_types.h` | h | 3031 | 65 | tracked@2e9d297e last=c9748665 | none (no command/register tokens observed) |
| `firmware/e80-stm32-bench/third_party/Radio/lr20xx_driver/inc/lr20xx_radio_ook.h` | h | 9737 | 246 | tracked@2e9d297e last=c9748665 | ARX, IRQ, ERRATA (token-presence only) |
| `firmware/e80-stm32-bench/third_party/Radio/lr20xx_driver/inc/lr20xx_radio_ook_types.h` | h | 12026 | 284 | tracked@2e9d297e last=c9748665 | IRQ (token-presence only) |
| `firmware/e80-stm32-bench/third_party/Radio/lr20xx_driver/inc/lr20xx_radio_oqpsk_15_4.h` | h | 7968 | 188 | tracked@2e9d297e last=c9748665 | ARX, IRQ (token-presence only) |
| `firmware/e80-stm32-bench/third_party/Radio/lr20xx_driver/inc/lr20xx_radio_oqpsk_15_4_types.h` | h | 6638 | 151 | tracked@2e9d297e last=c9748665 | FIFO (token-presence only) |
| `firmware/e80-stm32-bench/third_party/Radio/lr20xx_driver/inc/lr20xx_radio_wi_sun.h` | h | 6043 | 153 | tracked@2e9d297e last=c9748665 | ARX, IRQ (token-presence only) |
| `firmware/e80-stm32-bench/third_party/Radio/lr20xx_driver/inc/lr20xx_radio_wi_sun_types.h` | h | 8530 | 186 | tracked@2e9d297e last=c9748665 | none (no command/register tokens observed) |
| `firmware/e80-stm32-bench/third_party/Radio/lr20xx_driver/inc/lr20xx_radio_wm_bus.h` | h | 5457 | 142 | tracked@2e9d297e last=c9748665 | ARX, IRQ (token-presence only) |
| `firmware/e80-stm32-bench/third_party/Radio/lr20xx_driver/inc/lr20xx_radio_wm_bus_types.h` | h | 7369 | 156 | tracked@2e9d297e last=c9748665 | none (no command/register tokens observed) |
| `firmware/e80-stm32-bench/third_party/Radio/lr20xx_driver/inc/lr20xx_radio_z_wave.h` | h | 7007 | 190 | tracked@2e9d297e last=c9748665 | ARX, IRQ, ERRATA (token-presence only) |
| `firmware/e80-stm32-bench/third_party/Radio/lr20xx_driver/inc/lr20xx_radio_z_wave_types.h` | h | 10873 | 229 | tracked@2e9d297e last=c9748665 | FIFO (token-presence only) |
| `firmware/e80-stm32-bench/third_party/Radio/lr20xx_driver/inc/lr20xx_regmem.h` | h | 5343 | 131 | tracked@2e9d297e last=c9748665 | none (no command/register tokens observed) |
| `firmware/e80-stm32-bench/third_party/Radio/lr20xx_driver/inc/lr20xx_rttof.h` | h | 8848 | 221 | tracked@2e9d297e last=c9748665 | ARX, CALIB, ERRATA (token-presence only) |
| `firmware/e80-stm32-bench/third_party/Radio/lr20xx_driver/inc/lr20xx_rttof_types.h` | h | 5494 | 158 | tracked@2e9d297e last=c9748665 | none (no command/register tokens observed) |
| `firmware/e80-stm32-bench/third_party/Radio/lr20xx_driver/inc/lr20xx_status.h` | h | 2993 | 74 | tracked@2e9d297e last=c9748665 | none (no command/register tokens observed) |
| `firmware/e80-stm32-bench/third_party/Radio/lr20xx_driver/inc/lr20xx_system.h` | h | 22647 | 546 | tracked@2e9d297e last=c9748665 | IRQ, CALIB (token-presence only) |
| `firmware/e80-stm32-bench/third_party/Radio/lr20xx_driver/inc/lr20xx_system_types.h` | h | 21523 | 486 | tracked@2e9d297e last=c9748665 | FIFO, IRQ, CALIB (token-presence only) |
| `firmware/e80-stm32-bench/third_party/Radio/lr20xx_driver/inc/lr20xx_workarounds.h` | h | 20570 | 467 | tracked@2e9d297e last=c9748665 | ARX, ERRATA (token-presence only) |
| `firmware/e80-stm32-bench/third_party/Radio/lr20xx_driver/inc/lr_fhss_v1_base_types.h` | h | 4414 | 127 | tracked@2e9d297e last=c9748665 | none (no command/register tokens observed) |
| `firmware/e80-stm32-bench/third_party/Radio/lr20xx_driver/src/CMakeLists.txt` | txt | 4255 | 89 | tracked@2e9d297e last=c9748665 | FIFO, ERRATA (token-presence only) |
| `firmware/e80-stm32-bench/third_party/Radio/lr20xx_driver/src/lr20xx_driver_version.c` | c | 3461 | 82 | tracked@2e9d297e last=c9748665 | none (no command/register tokens observed) |
| `firmware/e80-stm32-bench/third_party/Radio/lr20xx_driver/src/lr20xx_radio_bluetooth_le.c` | c | 11685 | 256 | tracked@2e9d297e last=c9748665 | ARX, FIFO, ERRATA (token-presence only) |
| `firmware/e80-stm32-bench/third_party/Radio/lr20xx_driver/src/lr20xx_radio_bpsk.c` | c | 5625 | 122 | tracked@2e9d297e last=c9748665 | none (no command/register tokens observed) |
| `firmware/e80-stm32-bench/third_party/Radio/lr20xx_driver/src/lr20xx_radio_common.c` | c | 38870 | 798 | tracked@2e9d297e last=35b95fe2 | TXP, ARX, CALIB, ERRATA (token-presence only) |
| `firmware/e80-stm32-bench/third_party/Radio/lr20xx_driver/src/lr20xx_radio_fifo.c` | c | 11036 | 265 | tracked@2e9d297e last=c9748665 | FIFO, IRQ (token-presence only) |
| `firmware/e80-stm32-bench/third_party/Radio/lr20xx_driver/src/lr20xx_radio_flrc.c` | c | 17680 | 489 | tracked@2e9d297e last=c9748665 | ERRATA (token-presence only) |
| `firmware/e80-stm32-bench/third_party/Radio/lr20xx_driver/src/lr20xx_radio_fsk.c` | c | 21746 | 447 | tracked@2e9d297e last=c9748665 | ERRATA (token-presence only) |
| `firmware/e80-stm32-bench/third_party/Radio/lr20xx_driver/src/lr20xx_radio_lora.c` | c | 26519 | 631 | tracked@2e9d297e last=c9748665 | ERRATA (token-presence only) |
| `firmware/e80-stm32-bench/third_party/Radio/lr20xx_driver/src/lr20xx_radio_lr_fhss.c` | c | 8604 | 203 | tracked@2e9d297e last=c9748665 | none (no command/register tokens observed) |
| `firmware/e80-stm32-bench/third_party/Radio/lr20xx_driver/src/lr20xx_radio_ook.c` | c | 16587 | 405 | tracked@2e9d297e last=c9748665 | ARX, ERRATA (token-presence only) |
| `firmware/e80-stm32-bench/third_party/Radio/lr20xx_driver/src/lr20xx_radio_oqpsk_15_4.c` | c | 9537 | 209 | tracked@2e9d297e last=c9748665 | none (no command/register tokens observed) |
| `firmware/e80-stm32-bench/third_party/Radio/lr20xx_driver/src/lr20xx_radio_wi_sun.c` | c | 9194 | 199 | tracked@2e9d297e last=c9748665 | ERRATA (token-presence only) |
| `firmware/e80-stm32-bench/third_party/Radio/lr20xx_driver/src/lr20xx_radio_wm_bus.c` | c | 8086 | 181 | tracked@2e9d297e last=c9748665 | none (no command/register tokens observed) |
| `firmware/e80-stm32-bench/third_party/Radio/lr20xx_driver/src/lr20xx_radio_z_wave.c` | c | 12713 | 271 | tracked@2e9d297e last=c9748665 | ERRATA (token-presence only) |
| `firmware/e80-stm32-bench/third_party/Radio/lr20xx_driver/src/lr20xx_regmem.c` | c | 10811 | 257 | tracked@2e9d297e last=c9748665 | none (no command/register tokens observed) |
| `firmware/e80-stm32-bench/third_party/Radio/lr20xx_driver/src/lr20xx_rttof.c` | c | 15995 | 373 | tracked@2e9d297e last=35b95fe2 | ARX, ERRATA (token-presence only) |
| `firmware/e80-stm32-bench/third_party/Radio/lr20xx_driver/src/lr20xx_system.c` | c | 26192 | 630 | tracked@2e9d297e last=35b95fe2 | IRQ, CALIB, ERRATA (token-presence only) |
| `firmware/e80-stm32-bench/third_party/Radio/lr20xx_driver/src/lr20xx_workarounds.c` | c | 29944 | 689 | tracked@2e9d297e last=c9748665 | ERRATA (token-presence only) |
| `firmware/e80-stm32-bench/third_party/Radio/radio_hal/lr11xx_hal.c` | c | 9720 | 305 | tracked@2e9d297e last=c9748665 | none (no command/register tokens observed) |
| `firmware/e80-stm32-bench/third_party/Radio/radio_hal/lr11xx_pa_pwr_cfg.h` | h | 35107 | 666 | tracked@2e9d297e last=c9748665 | CALIB (token-presence only) |
| `firmware/e80-stm32-bench/third_party/Radio/radio_hal/lr20xx_hal.c` | c | 9423 | 286 | tracked@2e9d297e last=c9748665 | FIFO (token-presence only) |
| `firmware/e80-stm32-bench/third_party/Radio/radio_hal/lr20xx_pa_pwr_cfg.h` | h | 23819 | 459 | tracked@2e9d297e last=c9748665 | CALIB (token-presence only) |
| `firmware/e80-stm32-bench/third_party/Radio/radio_hal/ral_lr11xx_bsp.c` | c | 27110 | 740 | tracked@2e9d297e last=c9748665 | CALIB (token-presence only) |
| `firmware/e80-stm32-bench/third_party/Radio/radio_hal/ral_lr20xx.h` | h | 21054 | 519 | tracked@2e9d297e last=c9748665 | ARX, FIFO, IRQ (token-presence only) |
| `firmware/e80-stm32-bench/third_party/Radio/radio_hal/ral_lr20xx_bsp.c` | c | 24643 | 711 | tracked@2e9d297e last=c9748665 | FIFO, IRQ, CALIB (token-presence only) |
| `firmware/e80-stm32-bench/third_party/Radio/radio_hal/ral_lr20xx_bsp.h` | h | 11087 | 265 | tracked@2e9d297e last=c9748665 | IRQ, CALIB (token-presence only) |

The whole vendored tree is tracked (not a submodule): `firmware/e80-stm32-bench/third_party/Radio/lr20xx_driver/` = 41 files, driver version string **v1.3.1** (`inc/lr20xx_driver_version.h`), plus `radio_hal/` = 22 files (RAL for LR20xx and LR11xx).

### 2b. First-party LR2021 driver + firmware sources

| local path (repo-root-relative) | type | bytes | lines | revision | plausible blocks |
|---|---|---|---|---|---|
| `firmware/rp2040-sweep/src/LR2021Raw.h` | h | 16179 | 479 | tracked@2e9d297e last=0a56aa3a | TXP, ARX, FIFO, IRQ, CALIB (token-presence only) |
| `firmware/rp2040/src/pio_lr2021_rx.cpp` | cpp | 14382 | 316 | tracked@2e9d297e last=13374ac0 | FIFO (token-presence only) |
| `firmware/rp2040/src/pio_lr2021_rx.h` | h | 4599 | 114 | tracked@2e9d297e last=13374ac0 | FIFO (token-presence only) |
| `firmware/rp2040/src/pio_lr2021_rx.pio` | pio | 4640 | 85 | tracked@2e9d297e last=13374ac0 | FIFO (token-presence only) |
| `firmware/rp2040/src/pio_lr2021_rx.pio.h` | h | 2073 | 60 | tracked@2e9d297e last=13374ac0 | none (no command/register tokens observed) |
| `tracker/firmware/components/lr2021_transport/CMakeLists.txt` | txt | 228 | 9 | tracked@2e9d297e last=f4dddd06 | none (no command/register tokens observed) |
| `tracker/firmware/components/lr2021_transport/SPI-LAYOUT-CONSTRAINTS.md` | md | 2212 | 54 | tracked@2e9d297e last=b9712e51 | FIFO (token-presence only) |
| `tracker/firmware/components/lr2021_transport/include/esp_idf_lr2021_radio.h` | h | 6149 | 149 | tracked@2e9d297e last=c0a92a9c | FIFO, IRQ (token-presence only) |
| `tracker/firmware/components/lr2021_transport/include/lr2021_framing.h` | h | 6709 | 207 | tracked@2e9d297e last=75ffda3d | none (no command/register tokens observed) |
| `tracker/firmware/components/lr2021_transport/include/lr2021_spi.h` | h | 15156 | 373 | tracked@2e9d297e last=a59a758e | TXP, ARX, FIFO, IRQ, CALIB (token-presence only) |
| `tracker/firmware/components/lr2021_transport/include/lr2021_transport.h` | h | 6938 | 181 | tracked@2e9d297e last=4e7722c3 | none (no command/register tokens observed) |
| `tracker/firmware/components/lr2021_transport/src/esp_idf_lr2021_radio.cpp` | cpp | 18762 | 490 | tracked@2e9d297e last=9bcbf1a9 | ARX, FIFO, IRQ, CALIB (token-presence only) |
| `tracker/firmware/components/lr2021_transport/src/lr2021_framing.cpp` | cpp | 1318 | 30 | tracked@2e9d297e last=75ffda3d | none (no command/register tokens observed) |
| `tracker/firmware/components/lr2021_transport/src/lr2021_spi.cpp` | cpp | 17846 | 507 | tracked@2e9d297e last=f4dddd06 | TXP, ARX, FIFO, IRQ, CALIB (token-presence only) |
| `tracker/firmware/components/lr2021_transport/src/lr2021_transport.cpp` | cpp | 6055 | 184 | tracked@2e9d297e last=4e7722c3 | ARX, IRQ (token-presence only) |
| `tracker/firmware/components/lr2021_transport/test/Makefile` |  | 494 | 21 | tracked@2e9d297e last=75ffda3d | none (no command/register tokens observed) |
| `tracker/firmware/components/lr2021_transport/test/test_lr2021.cpp` | cpp | 25463 | 733 | tracked@2e9d297e last=75ffda3d | FIFO, IRQ (token-presence only) |

### 2c. MeshCore LR2021 variant / patch set (in-repo copy)

| local path (repo-root-relative) | type | bytes | lines | revision | plausible blocks |
|---|---|---|---|---|---|
| `mesh-stack/meshcore-lr2021/.gitignore` |  | 16 | 2 | tracked@2e9d297e last=690ea9bc | none (no command/register tokens observed) |
| `mesh-stack/meshcore-lr2021/Makefile` |  | 3562 | 96 | tracked@2e9d297e last=5982e298 | none (no command/register tokens observed) |
| `mesh-stack/meshcore-lr2021/README.md` | md | 20497 | 378 | tracked@2e9d297e last=96c4338c | ARX, IRQ, CALIB (token-presence only) |
| `mesh-stack/meshcore-lr2021/monitor.py` | py | 2392 | 69 | tracked@2e9d297e last=690ea9bc | none (no command/register tokens observed) |
| `mesh-stack/meshcore-lr2021/outdoor-test.sh` | sh | 3297 | 120 | tracked@2e9d297e last=67c9e3f6 | none (no command/register tokens observed) |
| `mesh-stack/meshcore-lr2021/patches/CustomLR2021.h` | h | 1327 | 46 | tracked@2e9d297e last=5982e298 | ARX, IRQ (token-presence only) |
| `mesh-stack/meshcore-lr2021/patches/CustomLR2021Wrapper.h` | h | 1645 | 63 | tracked@2e9d297e last=530fab9d | ARX, CALIB (token-presence only) |
| `mesh-stack/meshcore-lr2021/patches/EspIdfHal.h` | h | 4842 | 162 | tracked@2e9d297e last=5982e298 | none (no command/register tokens observed) |
| `mesh-stack/meshcore-lr2021/patches/apply-patches.sh` | sh | 1984 | 42 | tracked@2e9d297e last=5982e298 | none (no command/register tokens observed) |
| `mesh-stack/meshcore-lr2021/patches/boards/esp32c3_supermini.json` | json | 877 | 44 | tracked@2e9d297e last=5982e298 | none (no command/register tokens observed) |
| `mesh-stack/meshcore-lr2021/patches/variant/NiceRFLR2021Board.h` | h | 1595 | 66 | tracked@2e9d297e last=4a589e7e | none (no command/register tokens observed) |
| `mesh-stack/meshcore-lr2021/patches/variant/esp32c3_supermini/pins_arduino.h` | h | 1015 | 42 | tracked@2e9d297e last=5982e298 | none (no command/register tokens observed) |
| `mesh-stack/meshcore-lr2021/patches/variant/platformio.ini` | ini | 3861 | 150 | tracked@2e9d297e last=5982e298 | none (no command/register tokens observed) |
| `mesh-stack/meshcore-lr2021/patches/variant/target.cpp` | cpp | 1203 | 48 | tracked@2e9d297e last=5982e298 | ARX (token-presence only) |
| `mesh-stack/meshcore-lr2021/patches/variant/target.h` | h | 638 | 20 | tracked@2e9d297e last=4a589e7e | ARX (token-presence only) |

### 2d. Remaining LR2021-named artifacts in this clone (docs, ADRs, PDFs, PIO)

| local path (repo-root-relative) | type | bytes | lines | revision | role | plausible blocks |
|---|---|---|---|---|---|---|
| `docs/LR2021-THROUGHPUT-OPTIMIZATION-ANALYSIS.md` | md | 30100 | 609 | tracked@2e9d297e last=106f6fd9 | first-party-analysis-secondary | TXP, ARX (token-presence only) |
| `docs/LR2021_LR2022_LR2012_Datasheet_Rev2.1.pdf` | PDF | 5809234 | binary | tracked@2e9d297e last=e03e7cb8 | vendor-document | TXP, ARX, FIFO, IRQ, CALIB (pdf text token-presence only) |
| `docs/PLAN-E80-LR2021-EVAL-2026-08-15.md` | md | 8256 | 140 | tracked@2e9d297e last=445d1992 | first-party-analysis-secondary | none (no command/register tokens observed) |
| `docs/RP2040-LR2021-BASELINE-v1.0.0.md` | md | 3384 | 89 | tracked@2e9d297e last=90549678 | first-party-analysis-secondary | none (no command/register tokens observed) |
| `docs/adr/002-lr2021-as-rf-chip.md` | md | 2451 | 50 | tracked@2e9d297e last=a69212e4 | first-party-analysis-secondary | none (no command/register tokens observed) |
| `docs/adr/101-lr2021-only-ban-sx1280.md` | md | 1621 | 35 | tracked@2e9d297e last=811a156b | first-party-analysis-secondary | none (no command/register tokens observed) |
| `docs/adr/020-deprecate-radiolib-adopt-raw-lr2021-spi.md` | md | 5036 | 117 | tracked@2e9d297e last=811a156b | first-party-analysis-secondary | ARX, FIFO, IRQ, CALIB (token-presence only) |
| `docs/adr/110-tollgate-over-lr2021.md` | md | 4860 | 91 | tracked@2e9d297e last=cc04e7cf | first-party-analysis-secondary | none (no command/register tokens observed) |
| `docs/coordination/LR2021-FULL-CHARACTERIZATION-PLAN.md` | md | 27584 | 597 | tracked@2e9d297e last=44f50d2b | first-party-analysis-secondary | TXP, ARX, FIFO, IRQ, CALIB, ERRATA (token-presence only) |
| `docs/e80-900mbl-02-eval/lr2021-datasheet-id4393.pdf` | PDF | 21870805 | binary | tracked@2e9d297e last=19524138 | vendor-document | n/a (pdf text not extracted) |
| `docs/lr2021-bottleneck-analysis-2026-07-29.md` | md | 15089 | 302 | tracked@2e9d297e last=0658ff3b | first-party-analysis-secondary | ARX, FIFO (token-presence only) |
| `docs/lr2021-complete-learnings-2026-07-23.md` | md | 7148 | 188 | tracked@2e9d297e last=c84b412b | first-party-analysis-secondary | TXP, ARX, FIFO, IRQ, CALIB (token-presence only) |
| `docs/lr2021-dual-track-master-plan-2026-07-17.md` | md | 3451 | 96 | tracked@2e9d297e last=f18fbcb2 | first-party-analysis-secondary | none (no command/register tokens observed) |
| `docs/lr2021-flrc-24ghz-datasheet-audit-2026-07-26.md` | md | 22280 | 322 | tracked@2e9d297e last=9550c2d2 | first-party-analysis-secondary | TXP, ARX, FIFO, IRQ, CALIB, ERRATA (token-presence only) |
| `docs/lr2021-flrc-complete-learnings-2026-07-16.md` | md | 9684 | 164 | tracked@2e9d297e last=df099239 | first-party-analysis-secondary | ARX, FIFO (token-presence only) |
| `docs/lr2021-lora-modulation-params-encoding.md` | md | 7434 | 218 | tracked@2e9d297e last=7b6c9fe6 | first-party-analysis-secondary | none (no command/register tokens observed) |
| `docs/lr2021-reference-2026-07-16.md` | md | 3064 | 68 | tracked@2e9d297e last=0bbd179e | first-party-analysis-secondary | none (no command/register tokens observed) |
| `docs/lr2021-research-2026-07-16.md` | md | 1723 | 39 | tracked@2e9d297e last=b59c8f9e | first-party-analysis-secondary | none (no command/register tokens observed) |
| `docs/lr2021-root-cause-analysis.md` | md | 4736 | 137 | tracked@2e9d297e last=5b108b4d | first-party-analysis-secondary | ARX, IRQ, CALIB (token-presence only) |
| `docs/lr2021-spi-bottleneck-analysis-2026-07-16.md` | md | 9578 | 228 | tracked@2e9d297e last=19d44333 | first-party-analysis-secondary | FIFO (token-presence only) |
| `docs/lr2021-spi-command-reference.md` | md | 8496 | 227 | tracked@2e9d297e last=7052eed2 | first-party-analysis-secondary | TXP, ARX, FIFO, IRQ, CALIB (token-presence only) |
| `docs/lr2021-spi-protocol-reference.md` | md | 6881 | 163 | tracked@2e9d297e last=7052eed2 | first-party-analysis-secondary | ARX, FIFO, IRQ, CALIB (token-presence only) |
| `docs/lr2021-throughput-fix-plan-2026-07-29.md` | md | 23028 | 504 | tracked@2e9d297e last=0658ff3b | first-party-analysis-secondary | ARX, FIFO (token-presence only) |
| `docs/lr2021-throughput-optimization-plan-2026-07-16.md` | md | 9861 | 253 | tracked@2e9d297e last=6db6fb6a | first-party-analysis-secondary | ARX, FIFO, IRQ (token-presence only) |
| `docs/lr2021-tx-params-verification.md` | md | 4820 | 156 | tracked@2e9d297e last=7b6c9fe6 | first-party-analysis-secondary | TXP, ARX (token-presence only) |

Group labels for 2d: `docs/*.md` + `docs/adr/*` + `docs/coordination/*` = **first-party analysis (secondary; not primary evidence)**; `docs/*.pdf` = **vendor documents**; `firmware/rp2040/*` = build/bench config.

### 2e. Vendor module documents for LR2021-bearing modules (names do not match `*lr2021*`)

These are module-level (Ebyte E80 / NiceRF LoRa2021F33) documents — they describe the *module and its RF front end*, not LR2021 register semantics. Listed because the task asks for datasheet/spec/app-note material.

| local path (repo-root-relative) | type | bytes | revision | plausible blocks |
|---|---|---|---|---|
| `docs/f33-module/LoRa2021F33-2G4-datasheet-v1.1.pdf` | PDF | 622568 | tracked@2e9d297e | TXP, IRQ (pdf text token-presence only) |
| `docs/e80-900mbl-02-eval/e80-900mbl-02-spec-id4397.pdf` | PDF | 110582 | tracked@2e9d297e | none (no command/register tokens observed) |
| `docs/e80-900mbl-02-eval/e80-900mbl-02-manual-id4396.pdf` | PDF | 1135507 | tracked@2e9d297e | FIFO, IRQ (pdf text token-presence only) |
| `docs/e80-900mbl-02-eval/e80_mbl02_usermanual.pdf` | PDF | 1135507 | tracked@2e9d297e | FIFO, IRQ (pdf text token-presence only) |
| `docs/e80-900mbl-02-eval/e80_mbl02_schematic.pdf` | PDF | 110582 | tracked@2e9d297e | none (no command/register tokens observed) |
| `docs/e80-900mbl-02-eval/e80_m2212s_manual.pdf` | PDF | 1899401 | tracked@2e9d297e | IRQ (pdf text token-presence only) |
| `docs/e80-900mbl-02-eval/mbl01_manual.pdf` | PDF | 1287723 | tracked@2e9d297e | FIFO, IRQ (pdf text token-presence only) |
| `docs/e80-900mbl-02-eval/cn_manual.pdf` | PDF | 1443640 | tracked@2e9d297e | FIFO, IRQ (pdf text token-presence only) |
| `docs/e80-900mbl-02-eval/ebyte-doc-id1373.pdf` | PDF | 2279224 | tracked@2e9d297e | none (no command/register tokens observed) |

**Trap found (recorded, not fixed here):** `docs/e80-900mbl-02-eval/lr2021-datasheet-id4393.pdf` is **not a PDF** — `file(1)` reports *Zip archive data*, md5 `ff894418263cce9f475bda25d2446e77`, 21870805 bytes. Do not cite it as a datasheet.

---

## 3. Remote-branch-only material (objects in local git DBs, no worktree checkout)

| local path | type | bytes | revision | plausible blocks |
|---|---|---|---|---|
| `~/repos/meshcore` :: `src/helpers/radiolib/CustomLR2021.h` | h | 4368 | meshcore-dev/MeshCore @ 1ed56aac (origin/feature/nicerf-lr2021-variant) | not scanned (git object; remote-tracking branch only) |
| `~/repos/meshcore` :: `src/helpers/radiolib/CustomLR2021Wrapper.h` | h | 3668 | meshcore-dev/MeshCore @ 1ed56aac (origin/feature/nicerf-lr2021-variant) | not scanned (git object; remote-tracking branch only) |
| `~/repos/meshcore` :: `src/helpers/radiolib/CustomLR1110.h` | h | 3471 | meshcore-dev/MeshCore @ 1ed56aac (origin/feature/nicerf-lr2021-variant) | not scanned (git object; remote-tracking branch only) |
| `~/repos/meshcore` :: `src/helpers/radiolib/CustomLR1110Wrapper.h` | h | 2061 | meshcore-dev/MeshCore @ 1ed56aac (origin/feature/nicerf-lr2021-variant) | not scanned (git object; remote-tracking branch only) |
| `~/repos/meshcore` :: `src/helpers/radiolib/LR11x0Reset.h` | h | 766 | meshcore-dev/MeshCore @ 1ed56aac (origin/feature/nicerf-lr2021-variant) | not scanned (git object; remote-tracking branch only) |
| `~/repos/meshcore` :: `variants/nicerf_lr2021/NiceRFLR2021Board.h` | h | 1646 | meshcore-dev/MeshCore @ 1ed56aac (origin/feature/nicerf-lr2021-variant) | not scanned (git object; remote-tracking branch only) |
| `~/repos/meshcore` :: `variants/nicerf_lr2021/platformio.ini` | ini | 4410 | meshcore-dev/MeshCore @ 1ed56aac (origin/feature/nicerf-lr2021-variant) | not scanned (git object; remote-tracking branch only) |
| `~/repos/meshcore` :: `variants/nicerf_lr2021/target.cpp` | cpp | 1609 | meshcore-dev/MeshCore @ 1ed56aac (origin/feature/nicerf-lr2021-variant) | not scanned (git object; remote-tracking branch only) |
| `~/repos/meshcore` :: `variants/nicerf_lr2021/target.h` | h | 501 | meshcore-dev/MeshCore @ 1ed56aac (origin/feature/nicerf-lr2021-variant) | not scanned (git object; remote-tracking branch only) |
| `~/repos/microfips` :: `crates/microfips-esp-transport/src/lr2021_spi.rs` | rs | 13369 | Amperstrand/microfips @ origin/feat/lr2021-transport | not scanned (git object; remote-tracking branch only) |
| `~/repos/microfips` :: `crates/microfips-esp-transport/src/lr2021_framing.rs` | rs | 14502 | Amperstrand/microfips @ origin/feat/lr2021-transport | not scanned (git object; remote-tracking branch only) |
| `~/repos/microfips` :: `crates/microfips-esp-transport/src/lr2021_transport.rs` | rs | 10129 | Amperstrand/microfips @ origin/feat/lr2021-transport | not scanned (git object; remote-tracking branch only) |
| `~/repos/microfips` :: `crates/microfips-esp-transport/src/lib.rs` | rs | 1580 | Amperstrand/microfips @ origin/feat/lr2021-transport | not scanned (git object; remote-tracking branch only) |
| `~/repos/microfips` :: `crates/microfips-lr2021-test/src/lib.rs` | rs | 13327 | Amperstrand/microfips @ origin/feat/lr2021-transport | not scanned (git object; remote-tracking branch only) |
| `~/repos/microfips` :: `crates/microfips-lr2021-test/Cargo.toml` | toml | 604 | Amperstrand/microfips @ origin/feat/lr2021-transport | not scanned (git object; remote-tracking branch only) |

The microfips branch also drives the balloon first-party driver: `docs/lr2021-research/vendor/balloon-lr2021-transport/` is the C++ port of those Rust crates (per `SOURCES.md`).

---

## 4. Submodule / dependency state

| artifact | state | revision |
|---|---|---|
| `~/repos/balloon-e80bench` :: `tracker/firmware/components/RadioLib` | **not initialized** — gitlink only, directory exists but is empty; `git submodule status` reports `-f403b9c3...` | gitlink `f403b9c3d735bbd467ee92c1baf8ea216b608125` (`.gitmodules` url `https://github.com/jgromes/RadioLib.git`) |
| PlatformIO package cache (`~/.platformio/`) | **absent** on this host | n/a |
| MeshCore LR2021 variant's RadioLib pin | declared in git object only (`variants/nicerf_lr2021/platformio.ini`: `https://github.com/jgromes/RadioLib.git#6d8934836678d8894e3d556550475b37dce3e2b6`) | RadioLib `6d893483` (not checked out locally) |
| RadioLib LR2021 driver *source* | present only as the corpus snapshot (section 1) | master @ `75e486a573bbaad443ffcafa23f9e3e3d2499914`, 7.7.1-dev |

---

## 5. Verification

Every path in sections 1–3 was checked with `test -f`: see the generator's `verify` pass recorded at the end of this file (section 7). Revision strings above come from `git ls-files`/`git ls-tree`/`git rev-parse`; no path is listed without one.

---

## 6. NOT FOUND LOCALLY

Of the three named in the task's acceptance criteria:

1. **LR2021 datasheet — FOUND LOCALLY.** Distinct local copies/editions:
   - Rev 2.1, 5809234 B, md5 `5773847a76352b0bfe3270897627fd7f` — `~/repos/balloon/docs/LR2021_LR2022_LR2012_Datasheet_Rev2.1.pdf` (git-tracked; `pdfinfo` title `LR20xxDatasheet_V2_1.pdf`, 2026-04-13). Sibling copies exist in `~/repos/balloon-e80bench` and other clones of the same tree.
   - Rev 2.2, 5980032 B, md5 `18a392b72ff448083e6f26b2dd6e3925` — `docs/lr2021-research/semtech-official/LR2021_LR2022_LR2012_Datasheet_v2.2.pdf` (corpus, section 1).
   - Semtech AN1200.104 "LR20xx Modem Interface" v1.0 PDF, and AN1200.101/AN1200.102 (corpus).
   - Also present but **not a datasheet**: `lr2021-datasheet-id4393.pdf` (ZIP archive) and the Ebyte module-level PDFs in `~/repos/balloon-e80bench/docs/e80-900mbl-02-eval/` (module wiring docs, not silicon docs).

2. **LR2021 errata sheet — NOT FOUND LOCALLY.** No file named `*errata*`/`*erratum*` exists anywhere under `~/repos` or `~/worktrees` (`find -iname '*errata*'` → 0 hits). Text search of every locally-held Semtech PDF for `errata|erratum` → **0 hits** in all four corpus PDFs (`pdftotext | grep -ic`, 2026-10-01). The closest local material is `lr20xx_driver/inc/lr20xx_workarounds.h` + `src/lr20xx_workarounds.c` (468 + 690 lines, vendor driver workaround code — **implementation**, not an errata document) and the two "Improvements" app notes (AN1200.101/102), which describe silicon changes but are not errata sheets. Any downstream "per errata…" claim about LR2021 must be marked **UNKNOWN — not sourced locally**.

3. **RadioLib LR2021 driver source — FOUND (as a snapshot), MISSING as a build dependency.**
   - Present: full `src/modules/LR2021/` snapshot (15 files) + `LR11x0_commands.h`/`LR11x0_types.h` under `docs/lr2021-research/radiolib-master/` — master @ `75e486a5`, 7.7.1-dev, 182 `RADIOLIB_LR2021_CMD_*` defines (section 1).
   - Absent: any checked-out RadioLib *tree/submodule* — no directory named `RadioLib` exists with content in any repo (`~/repos/balloon-e80bench/tracker/firmware/components/RadioLib` is an empty gitlink dir); `~/.platformio/` does not exist, so no PlatformIO-fetched RadioLib copy exists either. The exact RadioLib revision the balloon firmware builds against is therefore **UNKNOWN** (MeshCore's variant pins `6d893483`, which is *not* the snapshot revision).

Also not found locally (not requested, recorded for completeness):

- **No standalone LR2021 register-map document** (no spreadsheet/map file); registers are documented only inside the datasheet command reference and inside `LR2021_commands.h` / `lr20xx_*.h` sources.
- **No `feature/meshcore-lr2021-upstream-pr` branch and no `meshcore-lr2021` worktree** exist on this host. The nearest equivalents: `~/repos/balloon-e80bench` path `mesh-stack/meshcore-lr2021/` (in-repo patch set) and `~/repos/meshcore` branch `origin/feature/nicerf-lr2021-variant`. There is likewise **no repo named `esp32-balloon-integration`** — that string is the kanban board directory `~/hermes-kanban/boards/esp32-balloon-integration`; the code lives in the balloon-fresh clones.
- **No vendored RadioLib fork** of any kind.

---

## 7. Machine-check log

Commands that produced the tables above (run 2026-10-01 on this host):

```
git ls-files <path>                      # tracked file lists + revisions
git ls-tree -r -l <ref> -- <path>        # blob sha + byte size on a remote ref
git submodule status                     # RadioLib gitlink state
find ~/repos ~/worktrees -iname '*lr2021*' -o -iname '*lr11*'
find ~/repos ~/worktrees -iname '*errata*'
grep -rIl -iE 'lr2021|lr11x0|lr11xx' <repo>
md5sum / stat -c%s / wc -l <file>
pdftotext <pdf> - | grep -ic 'errata|erratum'
pdftotext <pdf> - | grep -ic '<token family>'
test -f <every listed path>              # section 7 verification pass
```

Generator: `~/.hermes/profiles/manager/scripts/lr2021_recon_{stat,md5,matrix,all,errata}.(sh|py)` (read-only helpers).

Verification pass output is appended below by the generator on each run.

### 7.1 test -f results

- paths tested: **167**
- paths missing: **0**

### 7.2 remote-branch-only entries (section 3) — `git cat-file -e <ref>:<path>`

- `meshcore` :: `src/helpers/radiolib/CustomLR2021.h` -> exists
- `meshcore` :: `src/helpers/radiolib/CustomLR2021Wrapper.h` -> exists
- `meshcore` :: `src/helpers/radiolib/CustomLR1110.h` -> exists
- `meshcore` :: `src/helpers/radiolib/CustomLR1110Wrapper.h` -> exists
- `meshcore` :: `src/helpers/radiolib/LR11x0Reset.h` -> exists
- `meshcore` :: `variants/nicerf_lr2021/NiceRFLR2021Board.h` -> exists
- `meshcore` :: `variants/nicerf_lr2021/platformio.ini` -> exists
- `meshcore` :: `variants/nicerf_lr2021/target.cpp` -> exists
- `meshcore` :: `variants/nicerf_lr2021/target.h` -> exists
- `microfips` :: `crates/microfips-esp-transport/src/lr2021_spi.rs` -> exists
- `microfips` :: `crates/microfips-esp-transport/src/lr2021_framing.rs` -> exists
- `microfips` :: `crates/microfips-esp-transport/src/lr2021_transport.rs` -> exists
- `microfips` :: `crates/microfips-esp-transport/src/lib.rs` -> exists
- `microfips` :: `crates/microfips-lr2021-test/src/lib.rs` -> exists
- `microfips` :: `crates/microfips-lr2021-test/Cargo.toml` -> exists

