# FLASHING — E80 STM32F103C8T6 bench firmware

COMPILE-ONLY document. Do not flash until the bench plan's flash gate is
explicitly cleared. Nothing here has been executed against hardware yet.

## What gets flashed

- Target: onboard STM32F103C8T6 (64K flash / 20K RAM) of the E80-900MBL-02.
- Image: `build-fw/e80_bench.bin` (or `.hex`) from this directory.
- Console/flash path: USB Type-C -> CH340 -> USART1 (`/dev/ttyUSB3`, `/dev/ttyUSB4`).

## BOOT0 entry finding (verified against manual + demo sources)

> The manual confirms the USB Type-C->CH340 UART interface is the intended
> "burn firmware to the chip" path (STM32 ROM ISP on USART1). KEY1/KEY2 are
> plain GPIO user keys (PB15/PB14), NOT boot keys. NO documented CH340
> DTR/RTS->BOOT0/NRST auto-download circuit was found. Manual entry required:
> hold RESET, release as stm32flash syncs ('stm32flash -R', retry loop).
> **Needs live probe verification.**

## Procedure (stm32flash)

```bash
pip install stm32flash   # or: apt install stm32flash

# 0) Brownout hygiene: powered USB hub, disable USB autosuspend:
#    echo -1 | sudo tee /sys/module/usbcore/parameters/autosuspend

# 1) DUMP STOCK FIRST (mandatory, per-board, keep off-host copy):
stm32flash -r E80_stock_dump_ttyUSB3.bin /dev/ttyUSB3
stm32flash -r E80_stock_dump_ttyUSB4.bin /dev/ttyUSB4
# Verify dump size = 65536 bytes; store a second copy elsewhere.

# 2) Enter ROM ISP: hold RESET button, start flash, release RESET
#    as stm32flash begins syncing (retry loop if sync fails):
stm32flash -w build-fw/e80_bench.bin -v -g 0x08000000 /dev/ttyUSB3

# 3) Verify image CRC after write (stm32flash -v does read-back compare).
```

## Restore stock

- Preferred: reflash the dump: `stm32flash -w E80_stock_dump_<port>.bin -v /dev/ttyUSB<port>`
- Fallback: stock `E80.hex` from the EByte demo archive
  (`~/repos/lr2021-eval/pdfs/id4393-unpacked/E80_DEMO/stock E80/MDK-ARM/E80/E80.hex`).

## Notes

- 32-bit CRC verify: `stm32flash` read-back (`-v`) covers integrity; for an
  explicit CRC use `stm32flash -r` to read back and compare hashes with the dump.
- Antennas are attached to the SMA ports on both boards (confirmed). The bench
  firmware still boots TX-INHIBITED (radio asleep, TX requires ROLE TX + ARM TX).
- Flash wear is a non-issue (~10^5 rated cycles vs tens of bench cycles).
