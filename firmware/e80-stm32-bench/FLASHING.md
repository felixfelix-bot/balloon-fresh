# FLASHING — E80 STM32F103C8T6 bench firmware

COMPILE-ONLY document (procedures verified against RM0008 + the stm32flash
flow; no board access yet). Do not flash until the bench plan's flash gate is
explicitly cleared.

## What gets flashed

- Target: onboard STM32F103C8T6 (64K flash / 20K RAM) of the E80-900MBL-02.
- Image: `build-fw/e80_bench.bin` (or `.hex`) from this directory.
- Console/flash path: USB Type-C -> CH340 -> USART1 (`/dev/ttyUSB3`, `/dev/ttyUSB4`).

## BOOT0 entry finding (verified against manual + demo sources)

> The manual confirms the USB Type-C->CH340 UART interface is the intended
> "burn firmware to the chip" path (STM32 ROM ISP on USART1). KEY1/KEY2 are
> plain GPIO user keys (PB15/PB14), NOT boot keys. NO documented CH340
> DTR/RTS->BOOT0/NRST auto-download circuit was found. **Needs live probe
> verification.** Applies to STOCK firmware only — bench fw v1.2+ jumps to
> the ROM bootloader on its own `FLASH` command (below).

## Procedure (stm32flash)

### First flash on stock firmware (once per board — manual RESET cycling)

Stock firmware has no `FLASH` command, so ROM ISP entry is the manual
method (unchanged from the original finding):

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
```

### Every later re-flash (bench firmware >= v1.2): headless via `FLASH`

The bench firmware jumps itself into the ROM bootloader — no RESET button,
no operator at the bench:

```bash
# 1) Order the jump over the console (115200 8N1):
python3 -c "import serial,time; s=serial.Serial('/dev/ttyUSB3',115200,timeout=2); \
time.sleep(1); s.write(b'FLASH\r\n'); time.sleep(1); \
print(s.read(256).decode(errors='replace'))"
# Expect: OK JUMPING TO BOOTLOADER   (console then goes silent)

# 2) Run stm32flash immediately. The ROM waits for the 0x7F sync byte
#    indefinitely (no timeout), so there is no race:
stm32flash -w build-fw/e80_bench.bin -v -g 0x08000000 /dev/ttyUSB3
```

If a flash session is interrupted (USB hiccup, Ctrl-C), the ROM bootloader
is still resident and still waiting for sync — just re-run stm32flash; only
a reset/power glitch returns the board to the app.

## Watchdog rule (why FLASH can refuse)

The IWDG (TX-hang watchdog layer 3) starts at the FIRST `ARM TX` after
power-on and cannot be stopped; the ROM bootloader never feeds it — a WDG
reset mid-write can brick the app unrecoverably. Therefore:

- On a board that has EVER run `ARM TX` since power-on, `FLASH` replies
  `ERR POWER-CYCLE FIRST (WATCHDOG ACTIVE)` and does NOT jump.
- `ID?` shows the current verdict in its `boot=` field:
  `boot=jump-ok` (FLASH will jump now) or
  `boot=powercycle-first(wdg-active)` (refuses — cycle power first; the
  power cycle itself drops you into the stock/v1.2 state where FLASH works).
- Typical bench session: power-cycle at the bench anyway, so send `ID?`
  first and check `boot=` before heading into a headless flash.

## Restore stock

- Preferred: reflash the dump: `stm32flash -w E80_stock_dump_<port>.bin -v /dev/ttyUSB<port>`
  (enter via `FLASH` on bench fw, or manual RESET on stock/older fw).
- Fallback: stock `E80.hex` from the EByte demo archive
  (`~/repos/lr2021-eval/pdfs/id4393-unpacked/E80_DEMO/stock E80/MDK-ARM/E80/E80.hex`).

## Notes

- 32-bit CRC verify: `stm32flash` read-back (`-v`) covers integrity; for an
  explicit CRC use `stm32flash -r` to read back and compare hashes with the dump.
- Antennas are attached to the SMA ports on both boards (confirmed). The bench
  firmware still boots TX-INHIBITED (radio asleep, TX requires ROLE TX + ARM TX).
- Flash wear is a non-issue (~10^5 rated cycles vs tens of bench cycles).
