# REPORT — radio_core (L0): device-agnostic radio HAL

**Branch:** `feat/lib-radio-core`
**Worktree:** `cobrador:/home/c03rad0r/worktrees/lib-radio-core` (repo `balloon-fresh`)
**Date:** 2026-10-14
**Subject:** `firmware/lib/radio_core/radio_core.cpp` + an SX1280 register-map
descriptor, implemented against the FROZEN `radio_hal.h` contract.

> **NO HARDWARE WAS USED OR CLAIMED.** No radio is attached to the build host.
> Every result below comes from a host fixture (`FakeSpi`: a register file plus a
> BUSY flag). A fixture is not silicon. Nothing here proves the SX1280 or LR2021
> responds on real SPI; that test has not been run and is not claimed.

---

## 1. What was delivered

| File | Role |
|---|---|
| `firmware/lib/radio_core/radio_core.cpp` | The HAL implementation (register layer, ownership, configure/read-back, data path) |
| `firmware/lib/radio_core/radio_core_internal.h` | Private header: `DeviceDescriptor`, `Device`, config-image codec, the `RadioCore` class |
| `firmware/lib/radio_core/sx1280_map.h` | SX1280 register map **as data** (constexpr descriptor) |
| `firmware/lib/radio_core/test_radio_core.cpp` | Host test: 160 checks, incl. every counter-test |

`radio_hal.h` was **not touched** (three siblings code against it). The `Makefile`
was **not touched** (auto-discovery picked the module up with no edit). The test
defines **no** `make_radio_hal`.

## 2. TDD: the observed RED

The test was written and committed **before** `radio_core.cpp` existed
(`efe7cb6b`). Real output of `make -C firmware/lib test`:

```
== radio_core ==
.../test_radio_core.cpp:181: undefined reference to
    `balloon::radio::RadioCore::RadioCore(balloon::radio::SpiBus*, balloon::radio::Device)'
...: undefined reference to `balloon::radio::descriptorFor(balloon::radio::Device)'
...: undefined reference to `RadioCore::bus_read_reg(unsigned short, unsigned char*) const'
...: undefined reference to `RadioCore::bus_write_reg(unsigned short, unsigned char) const'
...: undefined reference to `RadioCore::bus_write_burst(...)` / `bus_read_burst(...)`
collect2: error: ld returned 1 exit status
RESULT: FAILURES
make: *** [Makefile:16: test] Error 1
```

A link failure was the expected RED shape: the module did not exist, so it could
not run. It is a real, observed failure, not a described one.

Then GREEN (`853165f9`), then the counter-test hole was closed (`f870564b`) —
see §4, which is the part worth reading.

## 3. Behaviour implemented

1. **Register layer** — `bus_read_reg` / `bus_write_reg` / `bus_read_burst` /
   `bus_write_burst`, each asserting chip-select around the transfer (and a CS-at-rest
   assertion in the test), and a BUSY/readiness poll that returns
   `Result::Timeout`. SX1280 framing `0x18/0x19/0x1A/0x1B` is taken from the
   datasheet §11 via RadioLib, mirrored in-repo in
   `docs/lr2021-spi-command-reference.md`.
2. **Ownership** — the uncontended `acquire()` takes the radio without touching
   the clock at all; `acquire(timeout_ms=0)` while held returns `Busy`
   immediately; `release()` without `acquire()` returns `NotAcquired`; every
   guarded op returns `NotAcquired` before `acquire()`.
3. **configure / read-back** — `configure()` encodes an 18-byte image
   (magic, version, modulation, freq LE32, bw LE32, sf, cr, tx power, preamble
   LE16, crc, XOR checksum), writes it, then **reads it back off the bus and
   decodes it**, and fails if it does not match. `read_config()` reads the bus;
   **there is no RAM shadow of the last write**.
4. **Register map as data** — `sx1280_map.h` holds a constexpr descriptor;
   adding LR2021 support means adding a table, not editing driver logic.
5. **Error propagation** — a failed SPI transfer is `BusError` and is never
   reported as `Ok`.

**Two bounds on every device wait.** The primary bound is the elapsed-time
budget; the second is a 64-iteration cap. This is not belt-and-braces: the first
"green" attempt **hung for real** on a frozen clock (see §5).

## 4. Sabotage / counter-test results (actual observations)

Four sabotages were applied to the real implementation, the suite re-run, and
the implementation restored. Actual output:

| # | Sabotage | Result | Verdict |
|---|---|---|---|
| A | `read_config` returns a RAM shadow instead of reading the bus | 5 of 155 failed | **caught** |
| B | No-op the BUSY check (`busy = false`) | 4 of 155 failed | **caught** |
| C | Drop `cs_select()` from `transact` | 1 of 155 failed | **caught** |
| D | Swallow the failed transfer (`if (!ok) {}`) | **155/155 passed** | **NOT caught — hole** |

Sabotage D is the finding that matters. Error propagation could be deleted and
the suite still went green, because the readiness probe that runs **before**
every transfer was the first thing to see the dead bus: the probe failed first
and the tests accepted that failure. A green suite that survives a deleted error
path is not evidence.

**Fix:** the fixture gained `fail_data_transfers`, where the status no-op still
answers but real commands fail — isolating error propagation in the access layer
from the probe. Against the sabotaged build:

```
FAIL test_radio_core.cpp:473 [COUNTER-TEST: an SPI transfer failure is BusError, never Ok]
    r->bus_read_reg(0x0024, &v) == Result::BusError
FAIL test_radio_core.cpp:474 [COUNTER-TEST: an SPI transfer failure is BusError, never Ok]
    r->bus_write_reg(0x0024, 0x11) == Result::BusError
```

Sabotage D is now caught. Suite: **160/160 checks green** with the real
implementation, `-Wall -Wextra -Werror` clean, all other modules still green:

```
== radio_core ==
  ok   160 checks passed
RESULT: all module tests green
```

Counter-tests in the suite:
- `read_config` follows the **bus**, not RAM: a byte on the device is changed and
  the trailing checksum then repaired, so an integrity check alone cannot see it —
  only a genuine read-back can.
- a checksum-broken image is rejected (`BadArgument`), never returned as `Ok`.
- a BUSY-forever device yields `Timeout`, bounded, and never `Ok`.
- a BUSY-forever device with a **frozen clock** still terminates.
- a failed SPI transfer (command path) is `BusError`, never `Ok`, and recovers.

## 5. Two real bugs the tests caught (both in the test/fixture, both instructive)

1. **The suite hung.** The burst test wrote 32 bytes at 0x0000, clobbering the
   fixture's status register at 0x0010, so the fixture became BUSY **for ever** —
   and with `millis()` frozen, an elapsed-time-only bound never trips. That is a
   genuine violation of "never an infinite loop". Fixed in two places: the burst
   test now uses a clear region (0x0020..0x003F), and the driver gained the
   iteration cap so a frozen clock cannot spin. A frozen-clock counter-test was
   added with it.
2. **`acquire(0)` read the clock.** The test asserts `acquire(0)` does not
   advance the clock; the first implementation read `millis()` on entry. The
   uncontended fast path now touches nothing.

## 6. Honesty notes / open items

- **No silicon.** No radio was present. `FakeSpi` is a fixture.
- **Unverified register addresses.** `0x001A` (RSSI) and `0x001B` (SNR) are
  recorded in the descriptor as the map's current belief and explicitly
  **marked UNVERIFIED** in `sx1280_map.h`, with the reason: they sit plausibly in
  the 0x0018..0x001D statistics bank but I could not confirm the exact addresses
  against a datasheet and no SX1280 register table exists in this repo to
  cross-check. Nothing on the flight path depends on them yet (`get_rssi_dbm` /
  `get_snr_db` are bench-console reads); a wrong value surfaces with real
  silicon. The config image region 0x0040..0x0051 is a radio_core-owned scratch
  region, not a chip register.
- **The LR2021 map is deliberately absent.** The LR2021 shares no opcode with the
  SX1280 and its SPI status is 16-bit while its IRQ status is 32-bit
  (`docs/lr2021-spi-command-reference.md`). Inventing a map would be worse than
  not having one, so `Device::Lr2021` falls back to the SX1280 descriptor and
  says so. Filling it in is the natural next task, from the vendored
  `lr20xx_driver` sources rather than guesswork.
- **`send()` / `receive()` are not radio implementations.** This HAL has no
  silicon behind it; `receive()` reports `Ok + 0` ("nothing pending", the
  contract's own wording) and `send()` reports readiness/`Timeout`. Neither
  pretends a packet moved. A real radio path (FIFO, TX/RX state machine, IRQ
  status) is separate work and is not claimed here.
- **Factory ownership.** `radio_core.cpp` provides a host stub for the contract's
  `make_radio_hal(SpiBus*)` (returns `nullptr`; it refuses to fabricate a
  device). A device build must compile with
  `-DBALLOON_RADIO_CORE_DEVICE_FACTORY` so its real factory is the only
  definition. This is documented in `radio_core_internal.h`.

## 7. Commits

| Commit | What |
|---|---|
| `efe7cb6b` | `test(radio_core)`: RED — test first, link failure observed |
| `853165f9` | `feat(radio_core)`: GREEN — the HAL implementation |
| `f870564b` | `test(radio_core)`: counter-test the command path (closes the sabotage-D hole) |

Reproduce: `make -C firmware/lib test` (plain `g++`, no PlatformIO).

## 8. Push verification (both remotes)

```
local  c9ebba4f1214510720a356ad5e2668299c8b3c79
github c9ebba4f1214510720a356ad5e2668299c8b3c79
ngit   c9ebba4f1214510720a356ad5e2668299c8b3c79
```

- `git push github feat/lib-radio-core` -> `* [new branch] feat/lib-radio-core -> feat/lib-radio-core`
- `git push ngit feat/lib-radio-core` -> `* [new branch] feat/lib-radio-core -> feat/lib-radio-core`
  (`Published 1 state event to 1/2 relays (failed: nos.lol)`; ngit needed
  `~/.local/bin` on PATH for `git-remote-nostr`.) No force-push was used or
  needed. (The SHAs above are the code+report tip taken immediately after the
  first push; a later docs-only commit moves the tip forward without touching
  any code.)

Reproduce the whole thing from a clean tree:

```sh
make -C firmware/lib test        # -> radio_core: ok 160 checks passed
```

### Verdict

The HAL is implemented against the frozen contract and is host-green, with the
read-back-verification property carried by a counter-test that survives having
the implementation sabotaged underneath it. **It has never spoken to a radio.**
The next honest step is a bench run with real SX1280 silicon, which would also
confirm or refute the two UNVERIFIED register addresses in `sx1280_map.h`.
