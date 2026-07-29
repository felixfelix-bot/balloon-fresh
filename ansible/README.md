# Logic Analyzer Debugging — Ansible Playbook

## What it installs

This playbook (`setup-debug-env.yml`) installs all tools needed for the
RP2040 + LR2021 logic analyzer debugging workflow on a local Ubuntu/Debian
laptop:

| Tool | Purpose |
|------|---------|
| **sigrok-cli** + libsigrok | Command-line logic analyzer capture (fx2lafw driver) |
| **pulseview** (optional) | GUI viewer for `.sr` capture files |
| **picotool** | Flash RP2040 via USB BOOTSEL mode |
| **PlatformIO CLI** | Build RP2040 firmware (pio run -e <env>) |
| **libsigrokdecode** | Protocol decoders (SPI, I2C, etc.) |
| **udev rules** | USB access permissions for logic analyzer + RP2040 |

## Prerequisites

- Ubuntu/Debian-based Linux laptop
- `ansible` installed (`pip install ansible` or `apt install ansible`)
- Sudo password (the playbook uses `become: true` for system packages)

## Running

```bash
# From repo root
ansible-playbook ansible/setup-debug-env.yml -K
```

The `-K` flag prompts for your sudo password, which is needed for apt
installs and udev rule deployment.

Alternatively, use the Makefile shortcut:

```bash
make setup
```

## What the playbook does

1. **Apt packages**: installs build tools, libsigrok, sigrok-cli, pulseview
2. **picotool**: clones + builds from source if not already installed
3. **PlatformIO**: installed in a virtualenv under `~/.platformio/penv`,
   symlinked to `/usr/local/bin/pio`
4. **udev rules**: deploys rules for the fx2lafw-compatible logic analyzer
   (Cellulologic/Saleae) and RP2040 BOOTSEL/app mode USB IDs
5. **Verification**: runs each tool with `--version` and prints a summary

## After installation

```bash
# Verify tools
sigrok-cli --version
picotool version
pio --version

# Build and flash firmware
make build ENV=rp2040-raw-tx
make flash ENV=rp2040-raw-tx

# Capture SPI signals
make capture DURATION=2 OUTPUT=captures/byte-transfer.sr
```