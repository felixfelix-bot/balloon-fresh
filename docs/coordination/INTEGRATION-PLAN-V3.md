# Integration Plan V3: First Unified Balloon Firmware Image

**Date:** 2026-08-05 (revised after consultant reviews V2-V4)
**Branch:** `autonomous/mesh-baseline`
**Predecessor:** INTEGRATION-PLAN-V2.md (superseded)
**Consultant reviews:** V2, V3, V4

---

## WHAT CHANGED FROM V2

Consultant V4 found 3 issues:
1. PCB order should be FIRST (2-week lead time is critical path)
2. FIPS atomics fix should be simpler (portable_atomic everywhere, no cfg)
3. CLI commands may not exist — need to verify before planning integration tests

V3 reorders: PCB first, FIPS second, CLI verification third, integration tests last.

---

## COMPLETED WORK (Phases 0-1)

### Phase 0: SMOKE — DONE
- GPIO10 collision fixed (LED→GPIO18, FEM_TX→GPIO19)
- secp256k1 smoke build passed (69KB flash, 0 DRAM)
- CI workflow created (433 tests, GitHub Actions)
- Cross-platform: C3 (301KB) + S3 (330KB) both build

### Phase 1: ARCHITECTURE — DONE
- FreeRTOS 3-task architecture implemented
- radio_task (100ms non-blocking poll, TX priority)
- app_task (nostr_store + secp256k1 linked)
- 12/12 host-side relay pipeline tests pass
- 5 consultant bugs fixed (deserialize, tollgate API, Kconfig, sig field, radio blocking)

---

## REVISED PHASES (V3)

### Phase 2: PCB FIX + ORDER (TODAY, 2h) — CRITICAL PATH

**Why first:** JLCPCB 2-week lead time. Every day delayed = 1 day later flying.

**2.1 — Find KiCad project** [15 min]
- `find ~/repos/balloon-fresh/ -name "*.kicad_pcb" -o -name "*.kicad_sch"`
- Check if kicad-cli installed: `which kicad-cli`

**2.2 — Fix GPIO assignments in schematic** [1h]
- LED: GPIO10 → GPIO18 (change net label + re-route if needed)
- FEM_TX: GPIO1 → GPIO19 (change net label + re-route if needed)
- NSS stays on GPIO10 (correct)
- GPS UART RX stays on GPIO1 (correct)

**2.3 — Regenerate gerbers** [30 min]
- If kicad-cli: `kicad-cli pcb export gerbers`
- If no CLI: open in KiCad GUI, Plot, export drill
- Run DRC (Design Rule Check) — must pass

**2.4 — Order from JLCPCB** [15 min]
- Upload gerber ZIP
- Upload BOM + CPL for PCBA (if doing assembly)
- Board specs: 2-layer, 1.6mm, HASL, (check existing spec)
- Express shipping (2-week standard, 5-day express)

**Pass criteria:** Order placed, confirmation email received.

### Phase 3: FIPS BUILD FIX (TODAY, 2h) — NO HARDWARE

**3.1 — Fix portable-atomic** [30 min]
- Add `portable-atomic = { version = "1", default-features = false }` to microfips-esp-common/Cargo.toml
- Replace `core::sync::atomic::AtomicU32` with `portable_atomic::AtomicU32` everywhere
- No cfg conditionals — portable_atomic works on all targets

**3.2 — Add esp32c3 cfg variants in config.rs** [45 min]
- Add `#[cfg(feature = "esp32c3")]` blocks for: DEVICE_NSEC, DEVICE_NAME, RESET_REGISTER, UART0_BASE, GPIO_FUNC_IN_SEL_BASE, UART_RX_GPIO_NUM
- Verify register addresses against ESP32-C3 Technical Reference Manual
- Use fixed dev key for DEVICE_NSEC

**3.3 — Fix logger** [30 min]
- Add `esp-println = { version = "0.10", features = ["log", "esp32c3"] }`
- Call `esp_println::logger::init_logger(log::LevelFilter::Info)` at startup

**3.4 — Build verification** [15 min]
```bash
cargo build -p microfips-esp32c3 --target riscv32imc-unknown-none-elf
cargo build -p microfips-esp32s3 --target xtensa-esp32s3-elf  # verify no regression
```

**3.5 — Add .cargo/config.toml entry** [5 min]
```toml
[target.riscv32imc-unknown-none-elf]
runner = "espflash flash --monitor"
rustflags = ["-C", "link-arg=-Tlinkall.x"]
```

**Pass criteria:** `cargo build -p microfips-esp32c3` exits 0.

### Phase 4: CLI COMMAND AUDIT (TODAY, 30 min) — NO HARDWARE

**4.1 — Verify existing CLI commands**
```bash
grep -r "radio_test\|radio_recv\|radio_send" ~/repos/balloon-fresh/tracker/firmware/main/
grep -r "nostr_dump\|relay_send\|tollgate_send" ~/repos/balloon-fresh/tracker/firmware/main/
```

**4.2 — Document what exists vs what's missing**
- If radio_test/radio_recv exist: Phase 5 (raw ping) unblocked
- If relay_send_nostr/nostr_dump/tollgate_send_pay missing: need Phase 5.5

**4.3 — Write missing CLI commands** (if needed, 2-3h)
- relay_send_nostr: serialize event → push to tx_queue
- nostr_dump: iterate store → print to serial
- tollgate_send_pay: encode PAY → push to tx_queue

**Pass criteria:** All CLI commands needed for Phases 5-6 exist or are written.

### Phase 5: TWO-BOARD RAW PING (WHEN BOARDS ARRIVE, 30 min)

**Prerequisites:** LR2021 modules wired to 2 S3 boards, board locks acquired.

**5.1 — Config**
- CONFIG_ENABLE_RELAY_MODE=n (use existing CLI commands)
- CONFIG_ENABLE_MESH=n (isolate radio)
- Build: `idf.py set-target esp32s3 && idf.py build`

**5.2 — Flash board A** (TX)
```bash
BALLOON_TRACK=balloon-hermes python3 ~/repos/balloon-fresh/tools/balloon-board-lock.py acquire board-a --purpose "raw ping test" --timeout 120
idf.py -p /dev/ttyACM0 flash monitor
# On serial console: radio_test 1 "hello"
```

**5.3 — Flash board B** (RX)
```bash
BALLOON_TRACK=balloon-hermes python3 ~/repos/balloon-fresh/tools/balloon-board-lock.py acquire board-b --purpose "raw ping test" --timeout 120
idf.py -p /dev/ttyACM1 flash monitor
# On serial console: radio_recv 30
```

**5.4 — Verify**
- Board B receives "hello" within 30s
- Swap roles, verify bidirectional
- Boards at 1-2m separation (NOT 30cm — receiver overload)

**5.5 — Release board locks**
```bash
python3 ~/repos/balloon-fresh/tools/balloon-board-lock.py release board-a
python3 ~/repos/balloon-fresh/tools/balloon-board-lock.py release board-b
```

**Pass criteria:** Raw bytes round-trip both directions.

### Phase 6: NOSTR ROUND-TRIP (WHEN BOARDS ARRIVE, 1h)

**Config:** CONFIG_ENABLE_RELAY_MODE=y, CONFIG_ENABLE_NOSTR_STORE=y

**6.1 — Board A sends Nostr event**
- Use relay_send_nostr CLI (or hardcoded test packet)
- radio_task TX → LR2021 → air

**6.2 — Board B receives and stores**
- radio_task RX → app_task → nostr_event_deserialize → nostr_store_add
- Verify via nostr_dump CLI or serial log

**Pass criteria:** Event stored on board B with correct pubkey/kind/content.

### Phase 7: TOLLGATE ROUND-TRIP (WHEN BOARDS ARRIVE, 1h)

**Config:** CONFIG_ENABLE_RELAY_MODE=y, CONFIG_ENABLE_TOLLGATE=y

**7.1 — Board A sends PAY**
- tollgate_send_pay CLI → encode → tx_queue → radio_task → LR2021

**7.2 — Board B decodes and ACKs**
- app_task: tollgate_proto_decode → TG_MSG_PAY → encode ACK → tx_queue → radio_task

**7.3 — Board A receives ACK**
- Verify seq matches, amount preserved

**Pass criteria:** PAY → ACK round-trip completes within 5s.

### Phase 8: POLISH (ONGOING)

- nostr_store index persistence (brownout survival)
- FIPS Noise handshake wrapping transport
- E-hash relay wiring to LR2021
- StratoRelay multi-hop (3+ boards)
- Outdoor range testing
- Power budget measurement
- Logic analyzer: C3 vs RP2040 SPI timing comparison

---

## ROLLBACK PLAN

| Phase fails | Rollback |
|-------------|----------|
| PCB fix | Use old gerbers, fly with GPIO10 collision (LED disabled in firmware) |
| FIPS build | Skip FIPS for V1 flight, use plaintext radio (acceptable for dev) |
| CLI commands | Test via hardcoded packets in app_main.cpp |
| Raw ping | Check wiring with multimeter, verify SPI with logic analyzer |
| Nostr round-trip | Run host-side relay test (12/12 pass) to isolate firmware vs hardware |
| TollGate round-trip | Run tollgate unit tests (119 pass) to isolate protocol vs radio |

---

## RESOURCE BUDGET (measured)

| Resource | C3 (flight) | S3 (bench) | Budget |
|----------|-------------|------------|--------|
| Flash | 301KB / 1024KB (71% free) | 330KB / 1024KB (69% free) | 2048KB total |
| DRAM | 63KB / 321KB (20% used) | 64KB / 321KB (20% used) | 321KB |
| secp256k1 | 69KB flash, 0 DRAM | same | measured |
| Components | 9 linked | 9 linked | all in one binary |

## SUMMARY

| Phase | Status | Hardware needed | Est time |
|-------|--------|-----------------|----------|
| 0 Smoke | DONE | No | 3h |
| 1 Architecture | DONE | No | 4h |
| 2 PCB fix + order | TODO | No (KiCad only) | 2h |
| 3 FIPS build fix | TODO | No | 2h |
| 4 CLI audit | TODO | No | 0.5h |
| 5 Raw ping | TODO | 2 boards + LR2021 | 0.5h |
| 6 Nostr round-trip | TODO | 2 boards + LR2021 | 1h |
| 7 TollGate round-trip | TODO | 2 boards + LR2021 | 1h |
| 8 Polish | ONGOING | Varies | TBD |