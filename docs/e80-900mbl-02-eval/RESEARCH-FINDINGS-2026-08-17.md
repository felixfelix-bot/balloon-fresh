# EBYTE E80-900MBL-02 - Research Findings (Task B)
Date: 2026-08-17. Method: curl/python web scraping (DDG html, GitHub API, vendor sites) + downloaded and analyzed official files.

## 1. Product identity and official docs
- Board = EBYTE (Chengdu Ebyte Electronic Technology) E80-xxxMBL-02 eval kit; STM32F103C8T6 + module E80-900M2212S (Semtech LR2021, 22dBm).
- EN product page: https://www.cdebyte.com/products/E80-900MBL-02
- CN product page: https://www.ebyte.com/product/2924.html
- User Manual (EN): https://www.cdebyte.com/pdf-down.aspx?id=4396  (v1.00, 2026-3-6, 11pp) -> local copy e80_mbl02_usermanual.pdf
- User Manual (CN): https://www.ebyte.com/downpdf/2924.html -> cn_manual.pdf
- Schematic (EN): https://www.cdebyte.com/pdf-down.aspx?id=4397 (1 page, NO text layer - vector outlines; BOOT0 wiring NOT verifiable from text)
- Module manual (E80-xxxM2212S): https://www.cdebyte.com/pdf-down.aspx?id=4395 -> e80_m2212s_manual.pdf
- Demo source (Keil/CubeMX, 21.8MB): https://www.cdebyte.com/pdf-down.aspx?id=4393 -> id4393.bin (zip) -> mbl02demo/
- -01 kit (LR1121 variant) manual: id=3517; -01 demo: https://www.cdebyte.com/Uploadfiles/Files/2024-12-17/20241217104127777.zip
- id=4394 = Altium PcbLib of module footprint (not firmware related)
- ManualsLib mirror: https://www.manualslib.com/manual/4510083/Ebyte-E80-Mbl-02-Series.html

## 2. Official flashing procedure
- Manual: USB-C port "can ... burn firmware to the chip" (CN: ke shao lu gu jian zhi xin pian) BUT NO procedure given anywhere in EN or CN manual. No BOOT key documented; KEY1=PB15, KEY2=PB14 are plain GPIOs (per Zephyr dts). NRST is exposed on header J2-3.
- Demo firmware source inspected: UART parser only handles C1 00 (freq), C1 01 (power), C1 02 (CW), C1 03 (sleep), C1 C1 C1 (auto tx), C2 (12-byte param set). NO bootloader-jump / no IAP / no jump to 0x1FFFF000. => NO vendor UART/USB bootloader in stock firmware.
- Zephyr upstream board port e80_900mbl_01: "uses the SWD debug port that is broken out to a header for flashing" (openocd default runner). https://docs.zephyrproject.org/latest/boards/ebyte/e80_900mbl_01/doc/index.html
- SoftRF (flashes THIS exact board as "Retro Edition MkII"):
  https://github.com/lyusupov/SoftRF/wiki/Retro-Edition-MkII
  https://github.com/lyusupov/SoftRF/blob/master/software/firmware/binaries/README.md#e80-900mbl
  Procedure: CMSIS-DAP (DAPLink) or ST-LINK V2 adapter wired to the board SWD pads, then:
  openocd -f interface/cmsis-dap.cfg -f board/stm32f103c8_blue_pill.cfg -c "program fw.bin 0x08000000 verify reset exit"
- CONCLUSION: The easy official way = SWD via the 4 back pads (GND/3V3/SWCLK/SWDIO) + ST-LINK/DAPLink + OpenOCD or STM32CubeProgrammer. USB-C only powers the board + bridges to USART1 (PA9/PA10). UART ISP (stm32flash) would need BOOT0 raised - BOOT0 wiring unverified (schematic has no text layer; no BOOT button/pad documented; SoftRF author chose SWD, implying no easy BOOT0 path on production boards).

## 3. LR2021
- GENUINE SEMTECH chip: "LoRa Plus LR2021, Fourth-generation LoRa IP", first chip of the LoRa Plus series.
  Page: https://www.semtech.com/products/wireless-rf/lora-plus/lr2021
- Datasheet "LR2021/22/12 v2.1" (2026-04-16) + AN1200.102/103/104/106 app notes listed on that page (Salesforce-hosted PDFs; direct link needs a browser).
- Public datasheet mirror: https://github.com/RegginYag/LR20xx-datasheet-Rev.-2.1
- Compatibility (EBYTE module manual quote): "designed to be fully compatible with the SX126x, SX127x, SX128x, and LR11xx series chips"; sub-GHz PHY compatible with SX126x/SX127x, 2.4GHz compatible with SX128x (except FLRC); interface = SPI + NSS + BUSY + DIO10/11 (LR11xx-style, NOT SX127x SPI register style).
- SDKs: Semtech lr20xx_driver v1.3.1 bundled in EBYTE demo (mbl02demo/E80_DEMO/E80/Radio/lr20xx_driver/); Semtech USP: https://github.com/Lora-net/usp ; Zephyr uses semtech,lr1121 binding on the -01; RadioLib has src/modules/LR2021 (jgromes/RadioLib); mLRS lists LR2021 support; SoftRF Retro MkII firmware targets this exact board; ESP-IDF: Lierda-WSN/LiotLr2021 and lierda-iot/esp32_lora_driver.
- Note: LR20xx engineering samples (date code 2513, chip ver 0x0110) need driver workarounds (per lr20xx_driver README in the demo).

## 4. STM32F103 SWD questions (from knowledge of RM0008/AN2606; st.com was unreachable from this network so URLs not re-verified live)
- Running firmware CAN disable SWD by writing SWJ_CFG=100 in AFIO_MAPR (frees PA13/PA14). It is a peripheral (RAM) register: resets on any power-cycle/reset => NOT permanent. Only RDP (FLASH option bytes) level 2 permanently kills debug; level 1 removable via mass erase. Stock EBYTE demo touches neither (checked source).
- If user firmware ever locks SWD: connect-under-reset (ST-LINK "Under reset" mode / OpenOCD connect-under-srst; NRST conveniently on J2-3) then full chip erase. Standard recovery per ST docs (AN2606 ecosystem, RM0008 AFIO chapter).
- E80-900MBL-02 ships with an unlocked chip: SWD works out of the box (SoftRF/Zephyr depend on it).
