# Troubleshooting Guide

This document focuses purely on diagnosing and resolving common issues.

---

# Environment Issues

## Problem: `espup: command not found`

Fix:

```bash
export PATH="$HOME/.cargo/bin:$PATH"
```

Add permanently:

```bash
echo 'export PATH="$HOME/.cargo/bin:$PATH"' >> ~/.bashrc
```

---

## Problem: `Toolchain esp is custom and not installed`

Cause: Running cargo inside firmware directory before espup install.

Fix:

```bash
cd ~
cargo +stable install espup
espup install
```

---

## Problem: `~/export-esp.sh not found`

Cause: espup install failed or was never run.

Fix:

```bash
espup install
```

---

# Build Issues

## Problem: `could not find Cargo.toml`

Fix:

```bash
cd antenna-firmware
```

---

# Flash Issues

## Problem: Device not found

Check:

```bash
ls /dev/ttyUSB*
```

If needed:

```bash
sudo usermod -a -G dialout $USER
```

Log out and back in.

---

# Motor Issues

## Motor Vibrates But Does Not Rotate

- Incorrect coil wiring
- Insufficient 5V supply
- Missing common ground

---

# Sanity Checklist

```bash
rustup toolchain list
which espup
which cargo
```

Everything must resolve correctly before building.
