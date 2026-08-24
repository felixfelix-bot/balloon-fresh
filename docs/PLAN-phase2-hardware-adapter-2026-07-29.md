# Phase 2 Plan: ESP32-C3 Hardware Adapter + Cross-Track Finding Resolution

**Created:** 2026-07-29
**Author:** balloon-fips sub-manager
**Status:** AWAITING FELIX APPROVAL
**Branch:** `balloon-fips-extract` in `~/worktrees/balloon-fips-fresh/`
**Prerequisite:** DQ05 build server online (ESP-IDF cross-compile required)

---

## Critical Discoveries (MUST RESOLVE BEFORE CODING)

### Discovery 1: DUAL-MCU vs DIRECT-SPI ARCHITECTURE CONFLICT

The hub board schematic (`hub_schematic.py`, commit e5e2db6) uses a **dual-MCU architecture**:
- LR2021 SPI bus → RP2040 coprocessor (GP2-GP8)
- ESP32-C3 ↔ RP2040 via UART (GPIO0/GPIO1 ↔ GP21/GP20)

But the **proven working firmware** (`firmware/esp32-c3-flrc/main/main.cpp`) connects LR2021 **directly to ESP32-C3** via SPI (GPIO2/6/7/10/4/5/3). This achieved 1733 kbps, 1000/1000 packets.

**This is a DESIGN DECISION, not a bug.** Felix must decide:
- **Option A (Direct SPI):** ESP32-C3 drives LR2021 directly. Proven, faster (20 MHz true SPI). Requires different PCB than hub_schematic.py.
- **Option B (UART bridge):** ESP32-C3 sends commands to RP2040, RP2040 drives LR2021 SPI. Matches hub schematic. Adds latency. RP2040 SPI caps at 12 MHz.
- **Option C (Dual firmware):** Support both — direct SPI for dev boards, UART bridge for flight PCB.

### Discovery 2: GPIO PIN CONFLICT (if Option A — Direct SPI)

If ESP32-C3 drives LR2021 directly, hub-schematic pins conflict:

| GPIO | Hub Schematic Use | Proven SPI Firmware Use | CONFLICT |
|------|------------------|------------------------|----------|
| GPIO2 | GPS UART RX | SPI MISO | YES |
| GPIO4 | ADC (supercap voltage) | BUSY | YES |
| GPIO5 | (unused) | IRQ (DIO9) | No |
| GPIO8 | I2C SDA (MS5611) | LED | YES |
| GPIO10 | Status LED | SPI CS (NSS) | YES |

### Discovery 3: pio-flash.sh DOES NOT PROTECT ESP32-C3 BOARDS

The flash shim only resolves `tx`/`rx` (RP2040 serials F242D/8332). ESP32-C3 boards (MAC 96:DC at ttyACM0, MAC C6:98 at ttyACM1) fall through to "unknown board" → flash WITHOUT lock check. ADR-025 is bypassed.

### Discovery 4: lr2021_spi.h CONTAINS WRONG OPCODE NAMESPACES

The header has THREE opcode namespaces:
- `Lr2021Commands` — 1-byte SX1280-style opcodes (0x00-0x1B) — **WRONG**
- `Lr2021Registers` — 16-bit register addresses (0x903, 0x880) — **WRONG**
- `Lr2021Opcodes` — 2-byte opcodes (0x01xx, 0x02xx) — **CORRECT**

The wrong namespaces are dead code but could confuse future workers. Should be removed.

---

## DECISION POINT FOR FELIX (blocks Phase 2)

**Q: Which architecture for Phase 2?**

- **A) Direct SPI** — use proven ESP32-C3 pin mapping (GPIO 2/3/4/5/6/7/10). Requires flight PCB revision or dev-board-only testing. Hub schematic would need updating.
- **B) UART→RP2040 bridge** — matches current hub schematic. Adds RP2040 firmware dependency. SPI capped at 12 MHz. More complex but matches flight hardware.
- **C) Both** — write EspHalLr2021Radio (direct SPI) for dev/testing NOW. Add UartBridgeLr2021Radio later for flight PCB.

**MY RECOMMENDATION: Option C.** Build direct SPI adapter now (matches Phase 5 hardware test on breadboard). Add UART bridge adapter when flight PCB is manufactured. The Lr2021Radio interface abstracts this — both implementations satisfy the same abstract class.

---

## Plan: 5 Tasks

### Task F2-1: Fix pio-flash.sh to support ESP32-C3 boards (NO DQ05)

**Goal:** pio-flash.sh must enforce board locks for c3-a and c3-b, not just tx/rx.

**Worker profile:** glm-4.5-flash (mechanical file edit, clear pattern to follow)

**Tasks:**
1. Read `~/repos/balloon-fresh/tools/pio-flash.sh`
2. Add MAC-based device resolution for ESP32-C3 boards:
   - MAC contains `96:DC` → resource = `c3-a`
   - MAC contains `C6:98` → resource = `c3-b`
3. Update fallback mapping to not conflict: `ttyACM0` is now `c3-a`, not `rx`
4. Also add ESP-IDF flash support (current shim only wraps `pio run -t upload`; add `idf.py flash` wrapper mode)
5. Test: `BALLOON_TRACK=balloon-fips python3 pio-flash.sh --upload-port /dev/ttyACM0` should refuse without lock, succeed with lock

**Quality Gates:**
- [ ] Gate 1: Test exists — verify shim refuses flash when lock NOT held
- [ ] Gate 2: Test passes — verify shim allows flash when lock IS held
- [ ] Gate 3: Docs updated — ADR-025 enforcement section notes the fix
- [ ] Gate 4: Atomic commit — `fix: pio-flash.sh enforces c3-a/c3-b locks per ADR-025`
- [ ] Gate 5: PUSHED to github/master

**Estimated time:** 1-2 hours
**Needs DQ05:** NO
**Needs hardware:** NO (dry-run test with mock lock state)

---

### Task F2-2: Remove dead opcode namespaces from lr2021_spi.h (NO DQ05)

**Goal:** Eliminate confusion. Keep only `Lr2021Opcodes` (correct 2-byte). Remove `Lr2021Commands` (wrong SX1280) and `Lr2021Registers` (wrong 16-bit).

**Worker profile:** glm-4.5-flash (simple deletion + verify nothing references removed namespaces)

**Tasks:**
1. Read `~/worktrees/balloon-fips-fresh/tracker/firmware/components/lr2021_transport/include/lr2021_spi.h`
2. Search all source files for references to `Lr2021Commands::` and `Lr2021Registers::`
3. Remove the wrong namespaces and any references
4. Rebuild all host tests: `cd test && make clean && make build && make test`
5. All 9 tests must still pass (Phase 1 + Phase 3)

**Quality Gates:**
- [ ] Gate 1: Test exists — existing 9 host tests serve as regression
- [ ] Gate 2: Tests pass — `make test` shows 9/9
- [ ] Gate 3: No references to removed namespaces remain
- [ ] Gate 4: Atomic commit — `refactor: remove dead SX1280-style opcode namespaces from lr2021_spi.h`
- [ ] Gate 5: PUSHED

**Estimated time:** 30 min
**Needs DQ05:** NO
**Needs hardware:** NO

---

### Task F2-3: Write EspHalLr2021Radio — ESP-IDF hardware adapter (NEEDS DQ05)

**Goal:** Implement the `Lr2021Radio` abstract interface using ESP-IDF SPI/GPIO APIs. This is the real hardware driver that replaces RadioLib.

**Worker profile:** glm-5.2 (complex embedded systems code, multi-file, SPI timing critical)

**DEPENDS ON:** Felix answering Discovery 1 (architecture choice). If Option C, use proven direct-SPI pin mapping.

**Tasks:**
1. Create `~/worktrees/balloon-fips-fresh/tracker/firmware/components/lr2021_transport/include/esp_idf_lr2021_radio.h`
2. Create `~/worktrees/balloon-fips-fresh/tracker/firmware/components/lr2021_transport/src/esp_idf_lr2021_radio.cpp`
3. Implement all 9 `Lr2021Radio` virtual methods:
   - `init(const Lr2021Config&)` — SPI bus init + GPIO config + full LR2021 init sequence (17 steps from proven firmware)
   - `start_rx()` — SET_RX command + IRQ config for RX_DONE
   - `send_packet(const uint8_t*, size_t)` — wait BUSY → write TX FIFO → SET_TX → wait TX_DONE
   - `read_packet(uint8_t*, size_t, PacketStatus&)` — read RX FIFO → parse status (RSSI, CRC)
   - `get_irq_status(uint32_t&)` — read 32-bit IRQ register (opcode 0x0117)
   - `clear_irq()` — write 0xFFFFFFFF to IRQ clear (opcode 0x0116)
   - `check_irq(bool&)` — poll GPIO IRQ pin (DIO9)
   - `standby()` — SET_STANDBY (opcode 0x0128)
   - `sleep()` — SET_SLEEP (if supported) or SET_STANDBY
4. SPI configuration:
   - Bus: SPI2_HOST, DMA auto
   - Clock: **20 MHz** (proven on ESP32-C3, per Discovery 3 data)
   - Mode: 0
   - CS: manual GPIO (not SPI hardware CS)
   - Half-duplex flag
   - max_transfer_sz: 526 bytes (255 + opcode overhead)
5. GPIO configuration:
   - Use pin mapping from `firmware/esp32-c3-flrc/main/main.cpp` (proven):
     ```
     SCK=GPIO6, MOSI=GPIO7, MISO=GPIO2, CS=GPIO10,
     BUSY=GPIO4, IRQ=GPIO5, RST=GPIO3
     ```
   - Wrap all pin numbers in `#ifdef` for board-specific config
6. Private helper methods (port from proven firmware):
   - `spi_write(const uint8_t* cmd, size_t len)` — CS low → wait BUSY → transfer → CS high
   - `spi_read(const uint8_t* cmd, size_t cmd_len, uint8_t* buf, size_t buf_len)` — CS low → wait BUSY → send cmd → CS high → wait BUSY → CS low → read → CS high
   - `wait_busy(uint32_t timeout_us)` — poll GPIO BUSY pin
   - `hardware_reset()` — RST low 1ms → high → wait 50ms
   - `compute_frf(double freq_mhz)` — frequency register calculation
7. Compile on DQ05: `cd tracker/firmware && idf.py build` (with lr2021_transport in COMPONENT_REQUIRES)
8. Must compile WITHOUT errors. No runtime test yet (Phase 5).

**Quality Gates:**
- [ ] Gate 1: Test exists — host-side MockLr2021Radio tests (9 existing) + new host test for EspHalLr2021Radio pin/SPI config validation (compile-time #ifdef checks)
- [ ] Gate 2: Tests pass — host tests 9/9; DQ05 ESP-IDF build compiles with 0 errors
- [ ] Gate 3: Docs updated — SPI speed constraints + pin mapping documented in component README
- [ ] Gate 4: Atomic commit — `feat: EspHalLr2021Radio — ESP-IDF raw SPI adapter for LR2021 (20MHz, direct GPIO)`
- [ ] Gate 5: PUSHED

**Estimated time:** 4-6 hours
**Needs DQ05:** YES (ESP-IDF cross-compile)
**Needs hardware:** NO (compile only)
**Inputs:** Felix decision on architecture (Discovery 1)

---

### Task F2-4: Replace RadioLib in app_main.cpp (NEEDS DQ05)

**Goal:** Migrate `app_main.cpp` from broken RadioLib LR2021 to EspHalLr2021Radio + Lr2021Transport. ADR-020 compliance.

**Worker profile:** glm-5.2 (multi-file refactor, build system changes)

**DEPENDS ON:** Task F2-3 complete (EspHalLr2021Radio exists)

**Tasks:**
1. Add `lr2021_transport` to `tracker/firmware/main/CMakeLists.txt` COMPONENT_REQUIRES
2. Remove `RadioLib` from COMPONENT_REQUIRES (if no other component uses it)
3. In `app_main.cpp`:
   - Remove `#include <RadioLib.h>` and `#include "EspHalC3.h"`
   - Remove `LR2021* radio = nullptr` and all RadioLib API calls
   - Add `#include "esp_idf_lr2021_radio.h"` and `#include "lr2021_transport.h"`
   - Instantiate `EspHalLr2021Radio hw_radio;` then `Lr2021Transport transport(&hw_radio);`
   - Replace `radio->begin(...)` / `radio->startTransmit(...)` with `transport.init(config)` / `transport.send(data, len)`
   - Replace RadioLib IRQ handler with `transport.poll_irq()` + `transport.recv()`
4. Handle MeshCore integration:
   - MeshCore expects a `mesh::Radio&` reference
   - Create `Lr2021MeshCoreRadio` adapter OR investigate if the existing `EspIdfInterfaces.h` can wrap EspHalLr2021Radio
   - This is the boundary between FIPS transport and MeshCore (Phase 4 scope — may defer)
5. Build on DQ05: `cd tracker/firmware && idf.py build`
6. Must compile WITHOUT errors. No runtime test yet.

**Quality Gates:**
- [ ] Gate 1: Test exists — `idf.py build` compiles (build is the test for firmware)
- [ ] Gate 2: Build passes — 0 errors, 0 warnings (except existing RadioLib removal warnings)
- [ ] Gate 3: Docs updated — AGENTS.md updated to remove RadioLib references, note lr2021_transport as radio driver
- [ ] Gate 4: Atomic commit — `refactor: replace RadioLib with lr2021_transport in app_main (ADR-020 compliance)`
- [ ] Gate 5: PUSHED

**Estimated time:** 3-4 hours
**Needs DQ05:** YES
**Needs hardware:** NO
**RISK:** MeshCore may depend on RadioLib types. If so, MeshCore migration (Phase 4) must happen first or simultaneously.

---

### Task F2-5: SPI Speed Constraints Documentation (NO DQ05)

**Goal:** Document the 20MHz SPI layout rules from Discovery data into the balloon-fips component docs. Ensure Phase 5 hardware test respects these constraints.

**Worker profile:** glm-4.5-flash (documentation task)

**Tasks:**
1. Create `~/worktrees/balloon-fips-fresh/tracker/firmware/components/lr2021_transport/SPI-LAYOUT-CONSTRAINTS.md`
2. Document:
   - 20 MHz SPI confirmed working on ESP32-C3 (1733 kbps, 1000/1000)
   - PCB layout rules: <30mm traces, length-matched within 5mm, no sharp corners, ground plane, decoupling caps
   - RP2040 caps at 12 MHz actual → 77% RX packet loss at "20 MHz"
   - 40 MHz corrupts FIFO writes — hard ceiling
   - ESP32-C3 achieves TRUE 20 MHz (not SDK-capped)
   - Breadboard/test setup notes: use short jumpers (<10cm), single ground return
3. Cross-reference: `docs/INTEGRATION-ASSESSMENT.md` (SPI section), `docs/lr2021-spi-protocol-reference.md`
4. Add "Phase 5 Test Setup" section with breadboard wiring diagram (text-based pin connection list)

**Quality Gates:**
- [ ] Gate 1: Review — document covers all 5 SPI constraint areas
- [ ] Gate 2: Accuracy — values match proven firmware data (20 MHz, 1733 kbps)
- [ ] Gate 3: Commit — `docs: SPI layout constraints for LR2021 at 20MHz (Phase 5 test reference)`
- [ ] Gate 4: PUSHED

**Estimated time:** 1 hour
**Needs DQ05:** NO
**Needs hardware:** NO

---

## Dependency Graph

```
F2-5 (docs, host) ──────────────────────────────── independent, start now
F2-1 (pio-flash fix, host) ─────────────────────── independent, start now
F2-2 (dead code cleanup, host) ─────────────────── independent, start now
                                                    │
Felix answers Discovery 1 (architecture choice) ───┤
                                                    ▼
                                          F2-3 (EspHalLr2021Radio, DQ05)
                                                    │
                                                    ▼
                                          F2-4 (app_main migration, DQ05)
```

**Parallelizable:** F2-1, F2-2, F2-5 can ALL start immediately and run in parallel.
F2-3 is blocked on Felix's architecture decision.
F2-4 is blocked on F2-3.

## Execution Schedule

| Order | Task | DQ05? | Duration | Blocks |
|-------|------|-------|----------|--------|
| 1 (now) | F2-2: Dead opcode cleanup | NO | 30 min | — |
| 2 (now) | F2-5: SPI constraints doc | NO | 1 hour | — |
| 3 (now) | F2-1: pio-flash.sh fix | NO | 1-2 hours | — |
| 4 (DQ05) | F2-3: EspHalLr2021Radio | YES | 4-6 hours | Needs Felix answer |
| 5 (DQ05) | F2-4: app_main migration | YES | 3-4 hours | Blocked by F2-3 |

**Tasks 1-3 can be dispatched immediately via kanban.** Tasks 4-5 wait for DQ05.

---

## Worker Profile Assignments

| Task | Model | Rationale |
|------|-------|-----------|
| F2-1 (pio-flash fix) | glm-4.5-flash | Mechanical file edit, clear pattern |
| F2-2 (dead code cleanup) | glm-4.5-flash | Simple deletion + grep verification |
| F2-3 (EspHalLr2021Radio) | glm-5.2 | Complex embedded, SPI timing, multi-file |
| F2-4 (app_main migration) | glm-5.2 | Multi-file refactor, build system |
| F2-5 (SPI constraints doc) | glm-4.5-flash | Documentation from existing data |

## Escalation to Felix

**BLOCKING QUESTION:** Discovery 1 — which architecture?
- A) Direct SPI (proven, dev boards)
- B) UART→RP2040 bridge (matches hub schematic, flight PCB)
- C) Both (recommended — direct SPI now, UART bridge later)

This blocks Task F2-3. Tasks F2-1, F2-2, F2-5 proceed regardless.
