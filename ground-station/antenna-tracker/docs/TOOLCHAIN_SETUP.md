# Toolchain Setup (Working Configuration)

## Required Versions
- ESP-IDF: v5.3
- esp-idf-sys: 0.36.x
- Rust toolchain: `esp` (Xtensa-enabled)
- GCC: esp-13.2.0_20240530 (from ESP-IDF)

## Critical Notes

### 1. Do NOT use ESP-IDF v6
`esp-idf-sys 0.36.x` only supports IDF 5.x.

### 2. Use Espressif Rust Toolchain
Stable Rust cannot compile Xtensa targets.

Install:
```
```

### 3. Remove Rust-bundled Xtensa GCC
Avoid GCC version conflicts:
```
rm -rf ~/.rustup/toolchains/esp/xtensa-esp-elf
```

Use ESP-IDF’s GCC instead.

### 4. Environment Order (Important)
Before building:
```
source ~/esp/esp-idf/export.sh
source ~/export-esp.sh
```

### 5. Build / Flash
```
make build
make flash
make monitor
```
