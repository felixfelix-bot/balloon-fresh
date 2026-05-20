# Development Workflow

This document describes the normal daily workflow for developing
the ESP32 antenna tracker firmware.

---

# 1. Open a New Terminal

Always activate both environments:

```bash
source ~/esp/esp-idf/export.sh
source ~/export-esp.sh
```

You can verify with:

```bash
rustup toolchain list
```

You must see the `esp` toolchain.

---

# 2. Build Firmware

```bash
cd antenna-firmware
cargo build
```

---

# 3. Flash Firmware

```bash
cargo run
```

Or explicitly:

```bash
cargo espflash /dev/ttyUSB0
```

---

# 4. Monitor Serial Output

```bash
cargo monitor
```

---

# 5. Git Workflow

From repo root:

```bash
git status
git add .
git commit -m "Describe change"
```

Avoid committing:

- `target/`
- `.venv/`
- build artifacts

---

# 6. Recommended Branching Model

- `main` → stable working firmware
- `feature/*` → experimental features
- `hardware/*` → hardware-related changes

---

# 7. Firmware Architecture Guidelines

Keep firmware modular:

- `motor.rs` → stepper abstraction
- `protocol.rs` → serial protocol parsing
- `control.rs` → motion control logic
- `main.rs` → system wiring

Avoid putting all logic in `main.rs` long term.
