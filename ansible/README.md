# Balloon RF — Ansible Dev Setup

Idempotent playbook that installs **ALL** dependencies needed to run the
balloon-fresh Makefile targets on a fresh Ubuntu/Debian machine (Felix's
T470 ThinkPad, DQ05, etc.).

## What it installs

| Dependency     | Source      | Used by Make targets                      |
|----------------|-------------|-------------------------------------------|
| git, git-lfs   | apt         | cloning, version tracking                 |
| python3, pip   | apt         | all Python-based tools                    |
| usbutils       | apt         | `lsusb` → `make find-ports`               |
| udev           | apt         | `udevadm` → `make find-ports`, `flash-*`  |
| PlatformIO     | pip (user)  | `make build-*`, `flash-*`                 |
| pyserial       | pip (user)  | `make flash-*`, `sync-time`, `walk-test`  |
| pytest         | pip (user)  | `make test`, `test-unit`                  |
| picotool       | apt (opt.)  | UF2 BOOTSEL flashing                      |
| udev rules     | repo copy   | RP2040 board access without sudo          |

## Quick start

```bash
cd ~/repos/balloon-fresh
ansible-playbook ansible/setup-dev.yml --ask-become-pass
```

Enter your sudo password when prompted.

After it finishes:

1. **Log out and back in** (or run `source ~/.profile`) so that
   `~/.local/bin` is on your `PATH` for the `pio` command.
2. Verify boards are detected:
   ```bash
   make find-ports
   ```
3. Run unit tests (no hardware required):
   ```bash
   make test-unit
   ```
4. Build firmware:
   ```bash
   make build-all
   ```

## Running on a remote machine

```bash
ansible-playbook ansible/setup-dev.yml -i 192.168.1.50, -u felix --ask-become-pass
```

The trailing comma after the IP is required for a single-host ad-hoc inventory.

## udev rules

The playbook copies `tools/99-balloon-boards.rules` to
`/etc/udev/rules.d/` and reloads udev. This creates:

- `/dev/balloon-tx` — symlink to TX board (serial `E663B035977F242D`)
- `/dev/balloon-rx` — symlink to RX board (serial contains `8332`)
- `/dev/balloon-tx-boot`, `/dev/balloon-rx-boot` — BOOTSEL mode symlinks
- `MODE="0666"` — world-writable so no `sudo` needed for serial access

Verify after running:
```bash
ls -la /dev/balloon-tx /dev/balloon-rx
```

## Idempotency

Safe to run multiple times. Only genuinely changed items are reported as
`changed` — everything else stays `ok`.

## Troubleshooting

### `pio: command not found` after running

Run `source ~/.profile` or log out/in. PlatformIO installs to
`~/.local/bin/`, which the playbook adds to your `PATH` via `~/.profile`.

### `externally-managed-environment` pip error

This is the PEP 668 guard on Ubuntu 23.04+ / Debian 12+. The playbook sets
`PIP_BREAK_SYSTEM_PACKAGES=1` to bypass it for user installs. If you hit
this manually:

```bash
PIP_BREAK_SYSTEM_PACKAGES=1 pip install --user platformio pyserial pytest
```

### picotool not found

picotool is **optional** (only needed for UF2 BOOTSEL flashing). It's
available via apt on Ubuntu 23.04+. If your distro doesn't have it, build
from source:

```bash
sudo apt install build-essential cmake libusb-1.0-0-dev
git clone https://github.com/raspberrypi/picotool.git ~/picotool
cd ~/picotool && mkdir build && cd build
cmake .. && make -j$(nproc)
sudo make install
sudo ldconfig
```

### Boards not showing up in `make find-ports`

1. Check USB connection: `lsusb | grep 2e8a`
2. Check udev rules loaded: `cat /etc/udev/rules.d/99-balloon-boards.rules`
3. Reload manually:
   ```bash
   sudo udevadm control --reload-rules
   sudo udevadm trigger
   ```
4. Unplug and replug the board.

## Playbook structure

```
ansible/
├── setup-dev.yml    # Main playbook (run this)
└── README.md        # This file
```

The playbook references the existing udev rules at
`tools/99-balloon-boards.rules` (relative to repo root). If you move the
rules file, update the `src` path in the "Install RP2040 udev rules" task.
