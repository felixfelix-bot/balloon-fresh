# TollGate ESP32-C3 Build Size Report

**Date:** 2026-07-30
**Branch:** `balloon-tollgate-extract`
**Commit:** `3221d20` + unused-const fix
**Target:** ESP32-C3 (RISC-V, 4 MB flash, 400 KB SRAM)
**ESP-IDF:** v5.4.1
**Build artifact:** `tollgate-balloon-test.elf` / `.bin`

## TL;DR Verdict: ✅ FITS

Build PASSES on ESP32-C3. DRAM usage is **49.5 KB / 312 KB budget (15.8%)** — 84% headroom
remaining for the mesh stack. Flash app partition is **316 KB / 1 MB (30%)** — 70% free.
nucula C++ wallet compiles and links cleanly.

---

## 1. Flash Usage

| Region | Size (bytes) | Size (KB) | Notes |
|--------|-------------:|----------:|-------|
| **App binary (.bin)** | 316,560 | 309.1 | Flashed to 0x10000 |
| App partition free | 732,048 | 715.0 | 70% free (1 MB partition) |
| Bootloader | 20,832 | 20.3 | 36% free in bootloader region |
| Partition table | (3 KB) | — | Standard layout |

**Total image size: 309,138 bytes (~302 KB)**

---

## 2. Section Breakdown (.text / .rodata / .data / .bss)

### Flash Regions (code + read-only data)

| Section | Size (bytes) | Size (KB) | % of Flash |
|---------|-------------:|----------:|-----------:|
| `.text` (flash code) | 185,606 | 181.3 | 60.0% |
| `.rodata` | 65,128 | 63.6 | 21.1% |
| `.eh_frame` | 12,884 | 12.6 | 4.2% |
| `.appdesc` | 256 | 0.25 | 0.1% |
| **Flash total** | **263,874** | **257.7** | — |

### DRAM Regions (initialized + zero-init RAM)

| Section | Size (bytes) | Size (KB) | % of DRAM |
|---------|-------------:|----------:|----------:|
| `.text` (IRAM) | 40,648 | 39.7 | 12.6% |
| `.bss` (zero-init) | 5,448 | 5.3 | 1.7% |
| `.data` (init) | 4,588 | 4.5 | 1.4% |
| **DRAM total** | **50,684** | **49.5** | **15.8%** |

### RTC Slow Memory

| Section | Size (bytes) | Notes |
|---------|-------------:|-------|
| `.force_fast` | 28 | Deep-sleep retained |
| `.rtc_reserved` | 24 | ROM reserved |
| **Total** | **52** | 0.63% of 8 KB RTC slow |

---

## 3. DRAM Budget Analysis

**C3 DRAM budget:** 312 KB usable (321,296 bytes total minus ~9 KB reserved for ROM/handlers)

| Metric | Value |
|--------|-------|
| DRAM used | **49.5 KB (15.8%)** |
| DRAM remaining | **264.3 KB (84.2%)** |
| Threshold (leaves mesh room) | 280 KB |
| Status | ✅ **Massive headroom** — 5.3× margin |

Static BSS allocations (the critical figure for mesh stack):
- Total `.bss` = 5,448 bytes (5.3 KB)
- nucula_lib contributes 1,052 bytes BSS (wallet state)
- FreeRTOS contributes 2,240 bytes BSS (task stacks, queues)

---

## 4. Heaviest Modules (Top 10 by Flash)

| # | Archive | Flash (bytes) | DRAM (bytes) | Notes |
|---|---------|--------------:|-------------:|-------|
| 1 | `libc.a` | 78,999 | 732 | newlib (printf, malloc, string) |
| 2 | `libsecp256k1.a` | 49,703 | 0 | secp256k1 crypto (nucula dep) |
| 3 | `libesp_app_format.a` | 28,951 | 10 | app description, versioning |
| 4 | `libgcc.a` | 14,428 | 88 | RISC-V soft-float, div helpers |
| 5 | `libnvs_flash.a` | 12,826 | 28 | NVS key-value storage |
| 6 | `libnucula_lib.a` | 12,445 | 1,052 | **Cashu wallet** (C++) |
| 7 | `libesp_hw_support.a` | 11,144 | 4,332 | CPU init, ADC, watchdog |
| 8 | `libheap.a` | 10,720 | 7,034 | Multi-heap allocator |
| 9 | `libfreertos.a` | 10,171 | 11,292 | RTOS kernel (IRAM-heavy) |
| 10 | `libstdc++.a` | 10,038 | 77 | C++ runtime (for nucula) |

**Top DRAM hogs:**
1. `libfreertos.a` — 11,292 bytes (task stacks, scheduler — IRAM-resident)
2. `libheap.a` — 7,034 bytes (heap metadata)
3. `libhal.a` — 8,358 bytes (register access primitives)
4. `libspi_flash.a` — 8,224 bytes (flash cache, MMU)

**TollGate components:**
| Component | Flash | DRAM |
|-----------|------:|-----:|
| `libtollgate_balloon.a` | 490 B | 262 B |
| `libtollgate_core.a` | (in tollgate_balloon above) | — |
| `libtollgate_esp.a` | (minimal) | — |

---

## 5. Component Composition Verified

✅ **nucula_lib** (C++ Cashu wallet) — compiles + links cleanly
✅ **secp256k1** — links as static dependency
✅ **tollgate_balloon** — mesh adapter scaffold compiles
✅ **tollgate_core** — payment protocol + core logic compiles
✅ **tollgate_esp** — ESP platform layer compiles

---

## 6. What's NOT Yet Linked (Future Growth)

The current build is the **skeleton + scaffolding** only. Still to be added:

| Component | Est. Flash | Est. DRAM | Status |
|-----------|----------:|----------:|--------|
| MeshCore ESP-IDF component | ~330 KB | ~6.5 KB | Available (B.7.x complete) |
| FIPS mesh transport | ~50-80 KB | ~10-20 KB | Not yet integrated |
| wisp-esp32 local relay | ~40 KB | ~8 KB | Source exists |
| WiFi captive portal | ~80 KB | ~30 KB | Source exists |
| Full tollgate_core runtime | ~20 KB | ~5 KB | Partial (mocked init) |
| **Estimated total addition** | **~520-550 KB** | **~60-70 KB** | — |

**Projected final image:**
- Flash: ~830-870 KB (of 1 MB partition → **fits, ~17% headroom**)
- DRAM: ~110-120 KB (of 312 KB budget → **fits, ~62% headroom**)

---

## 7. Recommendations

1. **No stripping needed** — current image is well within budget.
2. **Partition table** may need expansion from 1 MB to 1.5-2 MB once all
   components are integrated (flash has 4 MB total). Current partition
   is conservative.
3. **`-Os` already enabled** — compiler is optimizing for size.
4. **`.eh_frame` (12.6 KB)** could be stripped if exceptions are disabled
   (`-fno-exceptions` already set via CXXFLAGS, but libstdc++ pulls it in).
   Not worth the complexity at current headroom.
5. **libc (79 KB)** is the single largest contributor. Consider
   `CONFIG_NEWLIB_NANO_FORMAT=y` (already likely set) and
   `-ffunction-sections -fdata-sections` (already set) with
   `--gc-sections` linker flag (already set) to maximize dead-code removal.
6. **nucula C++** adds 22 KB combined (libnucula_lib + libstdc++). If DRAM
   becomes tight later, evaluate replacing libstdc++ with a minimal C++
   runtime or rewriting wallet in C.

---

## 8. Build Reproduction

```bash
source ~/esp/esp-idf/export.sh
cd mesh-stack/tollgate/
idf.py set-target esp32c3   # already configured
idf.py build
idf.py size
idf.py size --archives      # per-module breakdown
```

**Build log:** committed at `mesh-stack/tollgate/build/log/` (gitignored)
**Map file:** `build/tollgate-balloon-test.map`
