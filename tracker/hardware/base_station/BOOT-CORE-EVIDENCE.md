# Boot-core capture candidate — not a booted board or layout release

Extends RP2040-CAPTURE-EVIDENCE.md; supersedes its flash/crystal/LDO placeholder paragraphs only. Existing RP2040/portability edits preserved. No original netlist/PCB, RF routing, v10, push, merge or tag changed.

## Exact selection and independent pin oracle

| Reference | Exact selection / footprint | Tested physical pins |
|---|---|---|
| U_FLASH | Winbond **W25Q16JVSSIQ**, `Package_SO:SOIC-8_5.3x5.3mm_P1.27mm` (208mil SS, no EP) | 1 CSn, 2 SD1/DO, 3 SD2/WP, 4 GND, 5 SD0/DI, 6 SCLK, 7 SD3/HOLD, 8 3V3; no fictitious pad 9 |
| Y1 | Abracon **ABM8-272-T3**, `Crystal:Crystal_SMD_3225-4Pin_3.2x2.5mm` | 1 XIN, 2/4 GND, 3 XOUT_XTAL |
| U_LDO | TI **TLV75533PDBVR**, `Package_TO_SOT_SMD:SOT-23-5` (DBV, not DYD) | 1 IN=5V_PCBA, 2 GND, 3 EN=5V_PCBA, 4 NC left open, 5 OUT=3V3_MCU |

Flash: 2MiB, 2.7–3.6V. Corrects swapped IO0/IO1. 100nF local bypass; fitted 10k CS pull-up for startup. 10k SD2/SD3 pull-ups maintain inactive WP/HOLD if used in single SPI; IQ ordering option has QE factory fixed high (Winbond §8). Supports standard 03h read and quad EBh; use Pico SDK W25Q-compatible boot2 or conservative generic 03h boot2, with 2MiB flash size. Firmware image/boot2, QSPI clock divider and actual boot remain integration tests, not claimed by connectivity tests.

Crystal: 12MHz, CL=10pF, ESR <=50ohm, drive <=200uW. Raspberry Pi reference Figure 8 uses 1k between MCU XOUT and crystal; C_X2 belongs on **crystal side**, not MCU side. Both caps 15pF C0G (selected 1%, 50V). Reference calculation 15/2 + assumed 3pF stray = 10.5pF; parasitics are not measured. Abracon drawing visually verified: active 1/3, ground 2/4, chamfer location is not a reliable invariant. Exact passive MPNs and assembled startup/drive qualification remain open.

LDO: always enabled when regulated 5V is present, independently of switched LNA branch. 1.45–5.5V operating input; 500mA silicon limit is NOT a board thermal rating. At frozen 50mA MCU allowance dissipation is 85mW; at provisional 100mA controller+flash budget 170mW. Budget/load transients and copper/ambient thermal rise need validation. Input/output nominal 2.2uF X7R 10V 0805 with required effective >=1uF; TI requires effective >0.47uF. Exact capacitor derating/MPN remains a procurement gate. SWD pin1 is target-voltage reference only, **not an external supply input**. Do not back-power 3V3 with 5V absent (no reverse protection). USB VBUS not connected/selected.

## Primary sources actually downloaded

Local PDFs/text/renders: `tracker/hardware/base_station/output/readiness/boot-core/sources/` (ignored).

- Winbond W25Q16JV Rev J, §§3.1/3.3,8,11.2,12:
  https://www.winbond.com/resource-files/W25Q16JV%20SPI%20RevJ%2005202026%20Plus.pdf
  SHA256 `0a7d2859578bdf11ca5519d444c11cdc790fcbe6921989689b9c1ae4599780ef`
- Abracon drawing 456603 rev B (PDF mechanical page visually read):
  https://abracon.com/datasheets/ABM8-272-T3.pdf
  SHA256 `aead22b6bd9d6f8ad4472352f70fce3ade633e90b9772ba80fabe8fd0856ae91`
- TI SBVS320D Figure 4-2/Table 4-1, capacitor and enable sections:
  https://www.ti.com/lit/ds/symlink/tlv755p.pdf
  SHA256 `43ff53fb1eca7df105c4b3c26017052aef20bf5eae154c45b175dbd9e71dca0c`
- Raspberry Pi Hardware design with RP2040 §§2.2/2.3, Figure 8 visually read:
  https://datasheets.raspberrypi.com/rp2040/hardware-design-with-rp2040.pdf
  SHA256 `51c4f430153fcdbf3209d9b3b41662c8527ff0150bc25777e3fcd6f5221a1c19`

Live vendor matching: fetched https://www.lcsc.com/product-detail/C131025.html and read embedded Product record: sku C131025, mpn W25Q16JVSSIQ, package SOIC-8-208mil. This is an exact vendor identity match, **not JLC assembly availability**. A preliminary guessed C11523 URL returned a soft 404 and was rejected. TI live https://www.ti.com/product/TLV755P/part-details/TLV75533PDBVR also returned exact MPN. DigiKey/eBee direct pages blocked; search indicated JV lifecycle/EOL notices, so lifecycle and assembly-stock confirmation remain procurement blockers. Do not silently substitute RV or an SN/USON package.

Installed KiCad footprints were loaded with `/usr/bin/python3` + pcbnew. SOIC pads 1–4 at x=-3.587mm, 5–8 at +3.587mm, 1.27mm pitch; only eight pads. Crystal pads 1(-1.1,+0.85),2(+1.1,+0.85),3(+1.1,-0.85),4(-1.1,-0.85) match Abracon top view. SOT23-5 has left pins 1/2/3 and right 4/5, matching TI. Land-pattern solder-process approval still required.

## RED/GREEN and reproduction

Each new feature test was run before its implementation:
- `test_flash`: FAIL on generic flash identity/package; then PASS after corrected eight-pin capture and support.
- `test_crystal`: FAIL on generic crystal; then PASS after exact crystal and damped network.
- `test_ldo`: FAIL on generic LDO; then PASS after exact identity/enable/NC capture.
Single-fault controls separately reintroduce SD1 swap, crystal bypass of damping and floating LDO EN into copied pad maps and require rejection.

From `tracker/hardware/base_station`:
```sh
python3 -m unittest test_boot_core test_rp2040_pinout test_verifier_portability -v
python3 test_spec_transcription.py
mkdir -p output/readiness/boot-core/candidate
cp gen_base_station_netlist.py spec.json test_netlist_implements_spec.py output/readiness/boot-core/candidate/
python3 output/readiness/boot-core/candidate/gen_base_station_netlist.py
python3 output/readiness/boot-core/candidate/test_netlist_implements_spec.py
sha256sum output/readiness/boot-core/candidate/base_station_v1.net
```

Candidate generated twice byte-identically: **61 components, 45 nets**.
SHA256 `5f5ae86eb05b7d7b0939edbaa2f6c523fc03924d555e9c0b3d2628b572b67beb`.
Transcription **34/34**; candidate structural invariants **25/25**. Final unittest run: **10 tests PASS = 4 boot-core + 3 RP2040 + 3 portability**; `git diff --check` clean. These legacy invariants do NOT prove real fault isolation or correctness of RF IC captures.

## Remaining release blockers

**9–18V input vs 17V TPS62162 remains unresolved.** Buck pins, feedback, startup (REG_EN pulled from its own output), input protection and transient margins are not validated. Thus whole-board power-up cannot be claimed; boot-core capture assumes a valid regulated 5V source. Do not power this whole board at 18V.

No physical prototype boot, firmware/boot2, SWD flashing, reset recovery, USB connector/ESD/BOOTSEL interface, QSPI signal integrity, oscillator startup/temperature/drive test, LDO thermal/transient/reverse-feed test, schematic ERC, placement or DRC has passed here. RF/analog placeholders and four frozen gates remain blocked. This is corrected concrete controller connectivity, not an order-ready board.
