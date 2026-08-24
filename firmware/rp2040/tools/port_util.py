#!/usr/bin/env python3
"""
port_util.py — RP2040 (Pico) port detection + BOOTSEL flashing utility.

Implements ADR-020 invariant #4: port detection by serial ID, NOT /dev path.
Pico USB CDC ports shift on unplug/replug; the board's unique serial ID
(etched into the RP2040 OTP, exposed as ID_SERIAL_SHORT) is stable.

Three core operations:
  find_port(serial_suffix)        -> "/dev/ttyACM<n>"   (udevadm match)
  flash_bootsel(port)             -> puts board in BOOTSEL mode (1200 baud touch)
  mount_and_copy_uf2(uf2_path)    -> copies UF2 to RPI-RP2 mass storage, reboots

CLI subcommands:
  python3 tools/port_util.py find --serial 8332
  python3 tools/port_util.py find --serial 242D
  python3 tools/port_util.py list
  python3 tools/port_util.py flash --uf2 .pio/build/rp2040-sweep-rx-v4/firmware.uf2 --serial 8332
  python3 tools/port_util.py flash --uf2 <path> --port /dev/ttyACM1

Dependencies: pyserial (for the 1200 baud touch). Everything else shells out
to udevadm / lsblk / mount / udisksctl — no external Python libs required.

Board serial IDs (range-tests):
  TX = 242D   (full: E663B035977F242D)
  RX = 8332   (full: E663B035973B8332)
"""

import argparse
import shutil
import subprocess
import sys
import time
from pathlib import Path

# ─── try pyserial (only needed for the 1200 baud BOOTSEL touch) ────────────
try:
    import serial as pyserial  # noqa: F401
    _HAS_PYSERIAL = True
except ImportError:
    _HAS_PYSERIAL = False


# ─── Port detection ───────────────────────────────────────────────────────

def _udev_serial(dev_path: str) -> str:
    """Return ID_SERIAL_SHORT for a device, or '' if unavailable."""
    try:
        out = subprocess.run(
            ["udevadm", "info", "-q", "property", "-n", dev_path],
            capture_output=True, text=True, timeout=5,
        ).stdout
    except Exception:
        return ""
    for line in out.splitlines():
        if line.startswith("ID_SERIAL_SHORT="):
            return line.split("=", 1)[1].strip()
    return ""


def list_ports() -> list[dict]:
    """List all /dev/ttyACM* ports with their serial IDs.

    Returns a list of {'dev': '/dev/ttyACM0', 'serial': 'E663...'} dicts.
    """
    ports = []
    for i in range(8):
        dev = f"/dev/ttyACM{i}"
        if not Path(dev).exists():
            continue
        s = _udev_serial(dev)
        ports.append({"dev": dev, "serial": s})
    return ports


def find_port(serial_suffix: str, timeout: float = 0.0,
              poll_interval: float = 0.5) -> str | None:
    """Find the /dev/ttyACM* port whose ID_SERIAL_SHORT ends with the suffix.

    The suffix match handles the full RP2040 serial (e.g. 'E663B035977F242D')
    by matching its tail ('242D'), so a 4-char suffix is the common case.

    Args:
      serial_suffix: tail of ID_SERIAL_SHORT to match (e.g. '8332', '242D').
      timeout: seconds to poll waiting for the port to appear (0 = single try).
      poll_interval: re-scan cadence while polling.

    Returns the /dev/ttyACM* path, or None if not found within timeout.
    """
    suffix = serial_suffix.strip().upper()
    deadline = time.monotonic() + timeout
    while True:
        for p in list_ports():
            if p["serial"].upper().endswith(suffix):
                return p["dev"]
        if time.monotonic() >= deadline:
            return None
        time.sleep(poll_interval)


# ─── BOOTSEL mode ─────────────────────────────────────────────────────────

RP2_LABEL = "RPI-RP2"


def flash_bootsel(port: str, timeout: float = 15.0) -> bool:
    """Put an RP2040 board into BOOTSEL mode by opening its CDC port at 1200 baud.

    The 1200-baud touch is the standard Adafruit/Pico UF2 reset gesture: the
    Pico bootloader interprets a baud-rate change to 1200 as "reboot to BOOTSEL".
    On success the CDC port disappears and a RPI-RP2 mass-storage device appears.

    Returns True if the RPI-RP2 disk is visible within `timeout` seconds.
    """
    if not _HAS_PYSERIAL:
        print("ERROR: pyserial required for BOOTSEL touch. pip install pyserial",
              file=sys.stderr)
        return False
    if not Path(port).exists():
        print(f"ERROR: port {port} does not exist", file=sys.stderr)
        return False

    # Open at 1200 baud, set DTR=False then close. This triggers the reset.
    try:
        import serial as pyserial
        s = pyserial.Serial(port, 1200, timeout=0.2)
        s.dtr = False
        s.close()
    except Exception as e:
        # Some boards reset the instant the port opens at 1200; that's fine.
        print(f"  [bootsel] 1200-baud touch on {port}: {e}", file=sys.stderr)

    # Wait for the CDC port to vanish and RPI-RP2 disk to appear.
    return wait_for_bootsel_disk(timeout=timeout)


def find_bootsel_device() -> str | None:
    """Find the block device path for the RPI-RP2 mass storage, or None.

    Tries (in order): /dev/disk/by-label/RPI-RP2, then lsblk label scan.
    Returns e.g. '/dev/sda' or '/dev/disk/by-label/RPI-RP2'.
    """
    by_label = Path("/dev/disk/by-label") / RP2_LABEL
    if by_label.exists():
        return str(by_label.resolve())
    # lsblk fallback — scan all block devices for the label.
    try:
        out = subprocess.run(
            ["lsblk", "-rno", "NAME,LABEL"],
            capture_output=True, text=True, timeout=5,
        ).stdout
    except Exception:
        return None
    for line in out.splitlines():
        parts = line.split()
        if len(parts) >= 2 and parts[1] == RP2_LABEL:
            return "/dev/" + parts[0]
    return None


def wait_for_bootsel_disk(timeout: float = 15.0,
                          poll_interval: float = 0.3) -> bool:
    """Poll until the RPI-RP2 mass-storage device appears."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if find_bootsel_device():
            return True
        time.sleep(poll_interval)
    return False


# ─── Mount + copy UF2 ─────────────────────────────────────────────────────

def _find_mountpoint(device: str) -> str | None:
    """Return the current mountpoint of `device` if mounted, else None."""
    try:
        out = subprocess.run(
            ["findmnt", "-n", "-o", "TARGET", "--source", device],
            capture_output=True, text=True, timeout=5,
        ).stdout.strip()
        return out or None
    except Exception:
        return None


def mount_and_copy_uf2(uf2_path: str, unmount: bool = True,
                       timeout: float = 15.0) -> bool:
    """Mount the RPI-RP2 disk, copy the UF2, sync, unmount.

    Strategy:
      1. Locate RPI-RP2 block device.
      2. If already mounted (auto-mount), use that mountpoint.
      3. Else try udisksctl mount (no sudo needed on most desktops).
      4. Else try direct mount (may need root; will report if it fails).
      5. Copy UF2 file -> mountpoint, fsync, then unmount (which reboots board).

    Copying a .uf2 onto the RPI-RP2 drive causes the Pico to flash it and
    reboot into the new firmware automatically.
    """
    uf2 = Path(uf2_path)
    if not uf2.is_file():
        print(f"ERROR: UF2 not found: {uf2_path}", file=sys.stderr)
        return False

    device = find_bootsel_device()
    if not device:
        if not wait_for_bootsel_disk(timeout=timeout):
            print(f"ERROR: {RP2_LABEL} disk did not appear within {timeout}s",
                  file=sys.stderr)
            return False
        device = find_bootsel_device()
    assert device is not None  # narrowed: guaranteed set after wait

    print(f"  [flash] RPI-RP2 device: {device}", file=sys.stderr)

    # Already mounted?
    mountpoint = _find_mountpoint(device)

    owned_mount = False
    if not mountpoint:
        # Try udisksctl (desktop, no sudo).
        if shutil.which("udisksctl"):
            try:
                out = subprocess.run(
                    ["udisksctl", "mount", "-b", device],
                    capture_output=True, text=True, timeout=10,
                ).stdout
                # Output: "Mounted /dev/sda at /run/media/user/RPI-RP2."
                if " at " in out:
                    mountpoint = out.split(" at ", 1)[1].strip().rstrip(".")
                    owned_mount = True
            except Exception as e:
                print(f"  [flash] udisksctl mount failed: {e}", file=sys.stderr)

    if not mountpoint:
        # Direct mount fallback (needs root or fstab user option).
        import tempfile
        mountpoint = tempfile.mkdtemp(prefix="rp2_")
        rc = subprocess.run(["mount", device, mountpoint],
                            capture_output=True, text=True).returncode
        if rc != 0:
            print(f"ERROR: cannot mount {device} (need sudo?). "
                  f"Try: sudo mount {device} {mountpoint}", file=sys.stderr)
            try:
                Path(mountpoint).rmdir()
            except Exception:
                pass
            return False
        owned_mount = True

    print(f"  [flash] mountpoint: {mountpoint}", file=sys.stderr)

    # Copy the UF2. The Pico flashes on file-close.
    dest = Path(mountpoint) / uf2.name
    try:
        shutil.copy2(str(uf2), str(dest))
    except Exception as e:
        print(f"ERROR: copy UF2 failed: {e}", file=sys.stderr)
        if owned_mount:
            subprocess.run(["sync"])
            subprocess.run(["umount", mountpoint], capture_output=True)
        return False

    # Force the FS to flush so the board sees the complete file.
    subprocess.run(["sync"], capture_output=True)
    time.sleep(0.8)  # let the bootloader commit the flash write

    if unmount:
        subprocess.run(["sync"], capture_output=True)
        rc = subprocess.run(["umount", mountpoint],
                            capture_output=True, text=True).returncode
        if rc != 0 and shutil.which("udisksctl"):
            subprocess.run(["udisksctl", "unmount", "-b", device],
                           capture_output=True)
        print(f"  [flash] unmounted; board rebooting into new firmware",
              file=sys.stderr)

    print(f"  [flash] OK — {uf2.name} flashed", file=sys.stderr)
    return True


# ─── Full flash flow ──────────────────────────────────────────────────────

def flash_uf2(uf2_path: str, port: str | None = None,
              serial_suffix: str | None = None) -> bool:
    """End-to-end: locate board, BOOTSEL it, copy UF2.

    Provide either `port` (a /dev path) or `serial_suffix` (e.g. '8332').
    If serial_suffix is given and port is None, the port is auto-detected.
    """
    if not port and not serial_suffix:
        print("ERROR: provide --port or --serial", file=sys.stderr)
        return False
    assert serial_suffix is not None or port is not None  # checked above

    if not port:
        print(f"  [flash] detecting board serial suffix {serial_suffix}...",
              file=sys.stderr)
        found = find_port(serial_suffix, timeout=10.0)
        if not found:
            print(f"ERROR: no board with serial suffix {serial_suffix} found",
                  file=sys.stderr)
            return False
        port = found
    assert port is not None  # narrowed: set above or by caller

    print(f"  [flash] board at {port} -> BOOTSEL", file=sys.stderr)
    if not flash_bootsel(port):
        print(f"ERROR: could not enter BOOTSEL on {port}", file=sys.stderr)
        return False

    return mount_and_copy_uf2(uf2_path)


# ─── CLI ──────────────────────────────────────────────────────────────────

def _cli():
    p = argparse.ArgumentParser(
        description="RP2040 port detection + BOOTSEL UF2 flashing (ADR-020).")
    sub = p.add_subparsers(dest="cmd", required=True)

    pf = sub.add_parser("find", help="find a port by serial suffix")
    pf.add_argument("--serial", required=True, help="serial ID suffix (e.g. 8332)")
    pf.add_argument("--wait", type=float, default=0,
                    help="seconds to poll for the port to appear (default 0)")

    sub.add_parser("list", help="list all ttyACM ports + serials")

    fl = sub.add_parser("flash", help="flash a UF2 via BOOTSEL")
    fl.add_argument("--uf2", required=True, help="path to firmware.uf2")
    g = fl.add_mutually_exclusive_group(required=True)
    g.add_argument("--port", help="/dev/ttyACM* path")
    g.add_argument("--serial", help="serial ID suffix (e.g. 8332)")

    sub.add_parser("bootsel-disk", help="print the RPI-RP2 block device if present")

    args = p.parse_args()

    if args.cmd == "list":
        ports = list_ports()
        if not ports:
            print("(no /dev/ttyACM* ports found)")
        for pp in ports:
            print(f"{pp['dev']}  serial={pp['serial'] or '(none)'}")
        return 0

    if args.cmd == "find":
        port = find_port(args.serial, timeout=args.wait)
        if port:
            print(port)
            return 0
        print(f"(no port matching serial suffix {args.serial})", file=sys.stderr)
        return 1

    if args.cmd == "bootsel-disk":
        dev = find_bootsel_device()
        print(dev if dev else "(no RPI-RP2 disk)")
        return 0 if dev else 1

    if args.cmd == "flash":
        ok = flash_uf2(args.uf2, port=args.port, serial_suffix=args.serial)
        return 0 if ok else 1

    return 2


if __name__ == "__main__":
    sys.exit(_cli())
