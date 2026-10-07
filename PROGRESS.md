# PROGRESS — ADR-108 pin-plan revision (branch `adr/pin-plan-revision`)

Base: `github/main` tip `94c3c4dac97b1820bd1bf7b074424be8b528a769`
Worktree: `/home/c03rad0r/worktrees/bf-pinplan`

## Cluster 0 — recon (done)

* Baseline ERC on the committed sheet: **19 errors, all `pin_not_connected`, 0 warnings**
  (`kicad-cli sch erc --exit-code-violations -o /tmp/erc_before.rpt v9_flight.kicad_sch`,
  exit 5). The 19 are: U5.18, U5.15, U1.3, U1.20, U1.13, U1.14, U1.24, U1.25, U7.4,
  U3.6, U3.7, U3.9, U3.14, U3.15, U3.16, U3.17, U4.1, U4.2, U4.14.
* Register read: `grep -n 'OPEN-' build_flight_sch.py` → OPEN-1..OPEN-32 (`V9_TODO`), plus
  the `V9_NC` no-connect list. `check_sch_gates.py v9` GATE-3 floor `V9_GATE_TODO_MIN = 14`;
  it REPORTS ERC errors rather than failing on them (`gates pass` != `ERC clean`).
* Read (in-tree, not re-derived): ADR-108, ADR-029 D2b/D3/D5/D8, ADR-034 D1/D5, ADR-040,
  ADR-047 §2, ADR-060 §1.3/§4/§8, ADR-045 D1, ADR-009, `docs/V9-RADIO-SITE-MATRIX.md`
  §2/§3.1/§3.3, `docs/POWER-BUDGET-V9-D2BE.md` §2, `docs/F33-MODULE-PLAN.md`,
  `docs/LR2021-LESSONS-2026-09.md`, `docs/v9-BOM.md`, `docs/v9-system-diagram.svg`.
* Frozen-board precedent sweep (all committed boards, not just v8i): dumped pads→nets for
  `output/v8i_krt_gnss`, `output/v8j_krt_ms5611`, `output/v8b_krt_routed`,
  `output/v8c_krt_routed_margin`, `output/v8f_krt_margin_escaped`, `output/v8_krt_routed`
  and `hub_board_v1_clean`.
* **Datasheets obtained (not invented):**
  * **TI TPS7A02** `SBVS277C` (Rev C, Sept 2022), fetched to `/tmp/tps7a02.pdf`,
    text-extracted with `pdftotext -layout`. Table 5-1 / Figure 5-2: **DBV (SOT-23-5)
    pin 4 = NC**, "No connect pin. This pin is not internally connected. Connect to
    ground or leave floating." Pins: 1 IN / 2 GND / 3 EN / 4 NC / 5 OUT.
  * **u-blox MAX-M10S** `UBX-20035208-R08`, fetched to `/tmp/ublox.pdf`, `pdftotext -layout`.
    Table 10: **pin 15 VIO_SEL** "Connect to GND for 1.8 V supply, or leave open for 3.3 V
    supply"; **pin 18 SAFEBOOT_N** "Safeboot mode (active low). Leave open if not used."
  * **Espressif ESP32-S3-WROOM-1 & WROOM-1U** datasheet v1.8 (`esp32-s3-wroom-1_wroom-1u_
    datasheet_en.pdf`), §9 Peripheral Schematics p.41: "it is advised to add an RC delay
    circuit at the EN pin. The recommended setting ... is usually R = 10 kOhm and C = 1 uF."

## Cluster 1 — decisions taken (the pin plan)

| Pin | Assignment | Decided by |
|---|---|---|
| U4.1 / U4.2 | `+3V3` | ADR-047 §2.3 + POWER-BUDGET §2 (both SX1280 states on 3.3 V) |
| U4.14 RFIO | `ANT2_2G4_RANGE` (ANT2 re-pointed) | ADR-034 D1/D5 "the F33 carries TX only" vs ADR-029 D2b D3 four connectors |
| U2.10 F33 ANT-2G4 | no-connect | ADR-034 D5 |
| U3.6 / U3.7 / U3.14 / U3.15 | GPIO12 / GPIO47 / GPIO48 / GPIO11 | V9-RADIO-SITE-MATRIX §3.1 +4 GPIO budget |
| U3.9 bare sub-GHz ANT | no-connect | ADR-034 D1 (Site B is the 2.4 GHz RX site) |
| U3.16 / U3.17 DIO8/DIO7 | no-connect | bare module has no front end (LR2021-LESSONS; ADR-034 D1 item 2) |
| U5.15 VIO_SEL | no-connect | MAX-M10S DS Table 10 ("leave open for 3.3 V supply") |
| U5.18 SAFEBOOT_N | no-connect | MAX-M10S DS Table 10 ("Leave open if not used") |
| U7.4 TPS7A02 pin 4 | no-connect | TPS7A02 DS SBVS277C Table 5-1 (pin 4 = NC) |
| U1.20 / U1.24 / U1.25 | GPIO12 / GPIO47 / GPIO48 | same as U3 control lines |
| U1.11 (IO11) | re-spent on `U3_IRQ` | OPEN-6 freed it (no F33 DIO5 pad) |

Residual (still OPEN, named + owned): **U1.3 EN, U1.13 USB_D-, U1.14 USB_D+**
(OPEN-10) — needs a physical console/reset connector; the revision NAMES the
recommended connector part + reset-RC values (`R = 10 kOhm`, `C = 1 uF`,
ESP32-S3-WROOM-1 DS v1.8 §9) so a single later edit nets them.

## Cluster 2 — generator + artefacts

* `build_flight_sch.py` edited (v9 target) only; `v9_flight.kicad_sch` never hand-edited.
* Regenerate twice → byte-identical (sha256 recorded in REPORT.md).
* `docs/v9-BOM.md` regenerated from the netlist; `docs/v9-system-diagram.svg` ANT2 text
  updated and the PNG re-rendered with the repo's own render script + layout gate.
* ADR-108 revised in place with a dated "Revision R1" section.

RESULT: 19 → 3 ERC errors, all three the OPEN-10 console cluster. 0 warnings throughout.
