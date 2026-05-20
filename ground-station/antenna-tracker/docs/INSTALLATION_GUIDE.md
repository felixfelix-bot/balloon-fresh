# ESP32 Rust + ESP-IDF Installation Guide

This document records the full setup process for building ESP32 firmware
using Rust and ESP-IDF, including common pitfalls encountered during setup.

This project targets:

- **ESP32-WROOM-32**
- Target: `esp32`
- Rust toolchain: `xtensa-esp32-espidf`

---

# 1. Install ESP-IDF

## System Dependencies (Ubuntu/Debian)

```bash
sudo apt update
sudo apt install -y git wget flex bison gperf python3 python3-pip python3-venv \
cmake ninja-build ccache libffi-dev libssl-dev dfu-util libusb-1.0-0
```

## Clone ESP-IDF

```bash
mkdir -p ~/esp
cd ~/esp
git clone --recursive https://github.com/espressif/esp-idf.git
cd esp-idf
```

If submodules fail due to timeout:

```bash
git submodule update --init --recursive
```

## Install ESP-IDF Toolchain

```bash
./install.sh esp32
```

Activate environment:

```bash
source ~/esp/esp-idf/export.sh
```

---

# 2. Install Rust Properly

Install rustup:

```bash
curl https://sh.rustup.rs -sSf | sh
```

Reload shell:

```bash
source ~/.cargo/env
```

Verify:

```bash
cargo --version
rustc --version
```

---

# 3. Fix Cargo PATH Issues (Common Problem)

If `espup` or other cargo binaries are not found:

```bash
export PATH="$HOME/.cargo/bin:$PATH"
```

To fix permanently:

```bash
echo 'export PATH="$HOME/.cargo/bin:$PATH"' >> ~/.bashrc
source ~/.bashrc
```

Verify:

```bash
which cargo
which espup
```

---

# 4. Install ESP Rust Toolchain (Critical Step)

⚠ IMPORTANT:
If inside a directory containing `rust-toolchain.toml`, cargo may fail
because the custom `esp` toolchain does not yet exist.

Always install espup from outside the firmware directory:

```bash
cd ~
cargo +stable install espup
espup install
```

Activate:

```bash
source ~/export-esp.sh
```

Verify:

```bash
rustup toolchain list
```

You should see:

```
stable-x86_64-unknown-linux-gnu
esp
```

---

# 5. Critical: Remove Conflicting Rust GCC

The Espressif Rust toolchain installs its own Xtensa GCC (often newer than
ESP-IDF supports). ESP-IDF v5.3 strictly requires:

```
esp-13.2.0_20240530
```

If you see errors like:

```
Tool doesn't match supported version
```

Remove Rust’s bundled GCC only (NOT the whole toolchain):

```bash
rm -rf ~/.rustup/toolchains/esp/xtensa-esp-elf
```

This keeps the Rust Xtensa backend but forces ESP-IDF to use its own GCC.

---

# 6. Install ldproxy (Required for Linking)

If you see:

```
linker `ldproxy` not found
```

Install it explicitly:

```bash
cargo install ldproxy
```

Ensure Cargo bin is in PATH:

```bash
export PATH="$HOME/.cargo/bin:$PATH"
```

---

# 7. Install espflash (Required for Flashing)

If flashing fails with:

```
could not execute process `espflash`
```

Install:

```bash
cargo install espflash --locked
```

---

# 5. Common Errors and Their Fixes

## ❌ `espup: command not found`

Cause: `~/.cargo/bin` not in PATH.

Fix:

```bash
export PATH="$HOME/.cargo/bin:$PATH"
```

---

## ❌ `Toolchain esp ... is custom and not installed`

Cause: Project specifies `esp` toolchain before espup installed.

Fix:

```bash
cd ~
cargo +stable install espup
espup install
```

---

## ❌ `could not find Cargo.toml`

Cause: Not inside the firmware project directory.

Fix:

```bash
cd antenna-firmware
```

---

## ❌ `~/export-esp.sh: No such file or directory`

Cause: `espup install` did not complete successfully.

Fix:

```bash
espup install
```

---

# 6. Building Firmware

Every new shell must activate both environments:

```bash
source ~/esp/esp-idf/export.sh
source ~/export-esp.sh
```

Then build:

```bash
cd antenna-firmware
cargo build
```

Flash:

```bash
cargo run
```

---

# 7. Final Working Environment Checklist

Run these commands to verify full setup:

```bash
rustup toolchain list
which espup
which cargo
```

You must see:

- `esp` toolchain listed
- `espup` in `~/.cargo/bin`
- `cargo` working

---

# Lessons Learned

1. Cargo directory toolchain overrides can block bootstrapping.
2. PATH issues are the most common Rust setup failure.
3. `espup install` must be completed before building.
4. Always verify toolchains with `rustup toolchain list`.
5. Run toolchain installation outside firmware project directory.

---

This file documents all environment issues encountered during initial setup
of the antenna tracker firmware development environment.
