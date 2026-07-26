#!/usr/bin/env python3
"""
flash_board.py — Flash RP2040 board via USB reset + 1200 baud BOOTSEL + UF2 copy.

Usage:
  python3 flash_board.py --port /dev/ttyACM3 --uf2 path/to/firmware.uf2 [--label SERIAL_END]
"""
import argparse
import fcntl
import os
import shutil
import subprocess
import sys
import time

# USBDEVFS_RESET ioctl
USBDEVFS_RESET = 21780

RPI_LABEL = "RPI-RP2"
MOUNT_WAIT = 15  # seconds


def usb_reset(port: str) -> bool:
    """Issue USBDEVFS_RESET on the underlying usb device file."""
    # Walk sysfs to find the /dev/bus/usb path for this tty
    syspath = f"/sys/class/tty/{os.path.basename(port)}/device"
    try:
        real = os.path.realpath(syspath)
    except FileNotFoundError:
        print(f"  [reset] no sysfs for {port}", file=sys.stderr)
        return False

    # Find the usb device — walk up to the usb_device
    usb_dev = real
    for _ in range(20):
        if os.path.exists(os.path.join(usb_dev, "idVendor")):
            break
        usb_dev = os.path.dirname(usb_dev)
    else:
        print(f"  [reset] could not find usb_device for {port}", file=sys.stderr)
        return False

    # Read busnum/devnum
    try:
        with open(os.path.join(usb_dev, "busnum")) as f:
            busnum = int(f.read().strip())
        with open(os.path.join(usb_dev, "devnum")) as f:
            devnum = int(f.read().strip())
    except (FileNotFoundError, ValueError) as e:
        print(f"  [reset] cannot read bus/dev: {e}", file=sys.stderr)
        return False

    usb_file = f"/dev/bus/usb/{busnum:03d}/{devnum:03d}"
    print(f"  [reset] {port} -> {usb_file}", file=sys.stderr)
    try:
        fd = os.open(usb_file, os.O_WRONLY)
        fcntl.ioctl(fd, USBDEVFS_RESET, 0)
        os.close(fd)
        print(f"  [reset] OK", file=sys.stderr)
        return True
    except OSError as e:
        print(f"  [reset] ioctl failed: {e}", file=sys.stderr)
        return False


def baud1200_touch(port: str) -> bool:
    """Open serial at 1200 baud briefly to trigger BOOTSEL mode."""
    import serial
    try:
        s = serial.Serial(port, 1200, timeout=0.5)
        s.close()
        print(f"  [1200] touch sent to {port}", file=sys.stderr)
        return True
    except Exception as e:
        print(f"  [1200] failed: {e}", file=sys.stderr)
        return False


def find_rpi_rp2():
    """Find the RPI-RP2 block device by label."""
    by_label = "/dev/disk/by-label"
    link = os.path.join(by_label, RPI_LABEL)
    if os.path.exists(link):
        return os.path.realpath(link)
    return None


def wait_for_mount():
    """Wait for RPI-RP2 to appear, then ensure mounted."""
    print(f"  [mount] waiting for {RPI_LABEL}...", file=sys.stderr)
    deadline = time.time() + MOUNT_WAIT
    while time.time() < deadline:
        dev = find_rpi_rp2()
        if dev:
            return dev
        time.sleep(0.3)
    return None


def ensure_mounted(dev: str):
    """Ensure the device is mounted; return mount point or None."""
    # Check if already mounted
    try:
        out = subprocess.run(["findmnt", "-n", "-o", "TARGET", "--source", dev],
                             capture_output=True, text=True, timeout=5)
        mp = out.stdout.strip()
        if mp:
            return mp
    except Exception:
        pass

    # Try udisksctl (user-space mount, no sudo needed)
    try:
        subprocess.run(["udisksctl", "mount", "-b", dev],
                       capture_output=True, text=True, timeout=10)
        out = subprocess.run(["findmnt", "-n", "-o", "TARGET", "--source", dev],
                             capture_output=True, text=True, timeout=5)
        mp = out.stdout.strip()
        if mp:
            return mp
    except Exception:
        pass

    # Fallback: sudo mount
    mp = "/mnt/RPI-RP2"
    try:
        subprocess.run(["sudo", "mkdir", "-p", mp], timeout=5)
        r = subprocess.run(["sudo", "mount", dev, mp],
                           capture_output=True, text=True, timeout=10)
        if r.returncode == 0:
            return mp
    except Exception:
        pass
    return None


def copy_uf2(mount_point: str, uf2_path: str) -> bool:
    """Copy UF2 file to mount point (sudo-aware for /mnt mounts)."""
    dest = os.path.join(mount_point, os.path.basename(uf2_path))
    print(f"  [copy] {uf2_path} -> {dest}", file=sys.stderr)
    try:
        # Try direct copy first; if permission denied, use sudo
        try:
            shutil.copy2(uf2_path, dest)
        except PermissionError:
            r = subprocess.run(["sudo", "cp", uf2_path, dest],
                               capture_output=True, text=True, timeout=30)
            if r.returncode != 0:
                raise RuntimeError(f"sudo cp failed: {r.stderr}")
        os.sync()
        size = os.path.getsize(dest)
        print(f"  [copy] OK ({size} bytes)", file=sys.stderr)
        return True
    except Exception as e:
        print(f"  [copy] failed: {e}", file=sys.stderr)
        return False


def unmount(dev: str):
    """Unmount and eject."""
    for cmd in [
        ["sudo", "umount", dev],
        ["udisksctl", "power-off", "-b", dev],
    ]:
        try:
            subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        except Exception:
            pass


def flash_one(port: str, uf2: str, label: str = "", attempt: int = 1):
    print(f"\n=== FLASH attempt {attempt}: {port} [{label}] ===", file=sys.stderr)

    # Step 1: USB reset
    usb_reset(port)
    time.sleep(1.0)

    # Step 2: 1200 baud touch
    if not baud1200_touch(port):
        print(f"  1200 baud failed on attempt {attempt}, retrying after reset", file=sys.stderr)
        usb_reset(port)
        time.sleep(1.0)
        if not baud1200_touch(port):
            return False

    # Step 3: Wait for RPI-RP2
    dev = wait_for_mount()
    if not dev:
        print(f"  RPI-RP2 did not appear", file=sys.stderr)
        return False
    print(f"  [mount] found {dev}", file=sys.stderr)

    # Step 4: Mount
    mp = ensure_mounted(dev)
    if not mp:
        print(f"  could not mount {dev}", file=sys.stderr)
        return False
    print(f"  [mount] mounted at {mp}", file=sys.stderr)

    # Step 5: Copy UF2
    ok = copy_uf2(mp, uf2)

    # Step 6: Unmount (RP2040 auto-reboots)
    unmount(dev)
    time.sleep(2.0)

    return ok


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", required=True)
    ap.add_argument("--uf2", required=True)
    ap.add_argument("--label", default="")
    ap.add_argument("--attempts", type=int, default=3)
    args = ap.parse_args()

    if not os.path.exists(args.uf2):
        print(f"UF2 not found: {args.uf2}", file=sys.stderr)
        sys.exit(2)

    for a in range(1, args.attempts + 1):
        if flash_one(args.port, args.uf2, args.label, a):
            print(f"\n✓ FLASH SUCCESS: {args.port} [{args.label}]", file=sys.stderr)
            sys.exit(0)
        print(f"  attempt {a} failed, retrying...", file=sys.stderr)
        time.sleep(2.0)

    print(f"\n✗ FLASH FAILED after {args.attempts} attempts: {args.port} [{args.label}]", file=sys.stderr)
    sys.exit(1)


if __name__ == "__main__":
    main()
