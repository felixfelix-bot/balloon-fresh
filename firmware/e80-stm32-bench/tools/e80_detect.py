#!/usr/bin/env python3
"""e80_detect.py — auto-detect E80 bench board role + serial port.

Solves the #1 operator pain point: CH340 USB-serial ports (/dev/ttyUSB*)
SWAP on every reboot. This module figures out which port belongs to which
board (TX vs RX) so the operator never has to guess.

Two detection strategies, both openocd-free:

  1. SWD PROBE SERIAL (primary, most reliable):
     Each board has a CMSIS-DAP SWD probe (Raspberry Pi Pico Debugprobe)
     with a unique USB serial number. We read this directly from sysfs
     (/sys/bus/usb/devices/*/serial) — no openocd, no lsusb -v, just a
     file read. The serial uniquely and permanently identifies the board
     as TX or RX.

  2. FIRMWARE ID? (verification + fallback):
     The firmware console responds to "ID?" with a line including
     role=TX or role=RX. This is a RUNTIME setting (set by ROLE TX/RX
     commands), so it reflects the last session, not the board identity.
     Used to verify the board is alive and confirm the role.

Detection modes:

  • SINGLE-BOARD (distributed range test — one board per machine):
    Exactly one CH340 port + one known SWD probe → role from probe serial.

  • DUAL-BOARD (both boards on one machine, e.g. bench testing):
    Two CH340 ports + two SWD probes. We match each CH340 to its probe
    via the USB device tree (shared parent hub), then role from probe
    serial. Falls back to the radio handshake if tree matching is
    ambiguous.

Usage:
    python3 e80_detect.py              # auto-detect and print result
    python3 e80_detect.py --check-deps # verify openocd + pyserial
    python3 e80_detect.py --json       # machine-readable output

Exit codes: 0=ok, 1=error, 2=deps missing.
"""

from __future__ import annotations

import glob
import json
import os
import re
import subprocess
import sys
import time

# -----------------------------------------------------------------------
# Static config — SWD probe serial → board role
# -----------------------------------------------------------------------
PROBE_TX = "148757200D2D1425"
PROBE_RX = "203584200D2D0D42"
PROBE_TO_ROLE = {PROBE_TX: "TX", PROBE_RX: "RX"}

BAUD = 2000000  # firmware console baud (fw 0561b29+)

# Vendor/product IDs
CH340_VENDOR_ID = "1a86"
CH340_PRODUCT_ID = "7523"
CMSIS_DAP_VENDOR_ID = "2e8a"  # Raspberry Pi Debugprobe on Pico


# -----------------------------------------------------------------------
# Dependency check
# -----------------------------------------------------------------------

def find_openocd() -> str | None:
    """Return path to openocd or None."""
    # Check common locations
    for candidate in (
        os.environ.get("OPENOCD", ""),
        os.path.expanduser("~/.local/bin/openocd"),
        "/usr/bin/openocd",
        "/usr/local/bin/openocd",
    ):
        if candidate and os.path.isfile(candidate) and os.access(candidate, os.X_OK):
            return candidate
    # Fall back to PATH search
    try:
        r = subprocess.run(["which", "openocd"], capture_output=True, text=True, timeout=5)
        p = r.stdout.strip()
        if p and os.path.isfile(p):
            return p
    except Exception:
        pass
    return None


def find_pyserial() -> bool:
    try:
        import serial  # noqa: F401
        return True
    except ImportError:
        return False


def check_deps() -> dict:
    """Check dependencies and return a status dict with install hints."""
    openocd = find_openocd()
    pyserial = find_pyserial()
    issues = []
    if not openocd:
        issues.append(
            "openocd not found. Install for SWD reset (board recovery):\n"
            "    sudo apt install openocd\n"
            "  or (user-local, no sudo):\n"
            "    pip install meson ninja\n"
            "    git clone https://git.code.sf.net/p/openocd/code openocd\n"
            "    cd openocd && ./bootstrap && ./configure --prefix=$HOME/.local && make -j$(nproc) && make install"
        )
    if not pyserial:
        issues.append(
            "pyserial not found. Install:\n"
            "    pip install pyserial"
        )
    return {
        "openocd": openocd or None,
        "pyserial": pyserial,
        "all_ok": openocd is not None and pyserial,
        "issues": issues,
    }


# -----------------------------------------------------------------------
# CH340 port discovery
# -----------------------------------------------------------------------

def find_ch340_ports() -> list[str]:
    """Return /dev/ttyUSB* ports that are CH340 USB-serial converters.

    Uses udevadm to filter by vendor ID 1a86 (QinHeng CH340/CH341).
    """
    ports = []
    for dev in sorted(glob.glob("/dev/ttyUSB*")):
        try:
            r = subprocess.run(
                ["udevadm", "info", "-q", "property", "-n", dev],
                capture_output=True, text=True, timeout=5,
            )
            if CH340_VENDOR_ID in r.stdout and "ttyUSB" in dev:
                ports.append(dev)
        except Exception:
            pass
    return ports


# -----------------------------------------------------------------------
# SWD probe discovery (sysfs — no openocd needed!)
# -----------------------------------------------------------------------

def find_swd_probes() -> dict[str, dict]:
    """Find CMSIS-DAP SWD probes by scanning USB sysfs.

    Returns: {probe_serial: {"role": "TX"|"RX"|"?", "syspath": "...",
                            "product": "...", "vid": "..."}}
    Only returns probes with serials matching our known TX/RX boards.
    """
    found: dict[str, dict] = {}
    for dev_dir in sorted(glob.glob("/sys/bus/usb/devices/*")):
        serial_path = os.path.join(dev_dir, "serial")
        if not os.path.isfile(serial_path):
            continue
        try:
            with open(serial_path) as f:
                serial = f.read().strip()
        except (OSError, PermissionError):
            continue
        if serial in PROBE_TO_ROLE:
            prod = _read_sysattr(dev_dir, "product") or "?"
            vid = _read_sysattr(dev_dir, "idVendor") or "?"
            pid = _read_sysattr(dev_dir, "idProduct") or "?"
            found[serial] = {
                "role": PROBE_TO_ROLE[serial],
                "syspath": dev_dir,
                "product": prod,
                "vid": vid,
                "pid": pid,
            }
    return found


def _read_sysattr(dev_dir: str, attr: str) -> str | None:
    path = os.path.join(dev_dir, attr)
    try:
        with open(path) as f:
            return f.read().strip()
    except (OSError, PermissionError):
        return None


# -----------------------------------------------------------------------
# USB tree parent matching (for dual-board)
# -----------------------------------------------------------------------

def _usb_parent(devpath: str) -> str | None:
    """Walk one level up the USB tree. '3-1.2' → '3-1', '1-4' → '1'."""
    if not devpath or "-" not in devpath:
        return None
    bus, port_str = devpath.split("-", 1)
    ports = port_str.split(".")
    if len(ports) > 1:
        parent = bus + "-" + ".".join(ports[:-1])
    else:
        parent = bus  # root hub
    return parent


def _usb_ancestors(devpath: str) -> list[str]:
    """Full ancestor chain including self: ['3-1.2', '3-1', '3']."""
    chain = [devpath]
    p = _usb_parent(devpath)
    while p:
        chain.append(p)
        p = _usb_parent(p)
        if p and "-" not in p:
            chain.append(p)
            break
    return chain


def _tty_usb_syspath(tty_dev: str) -> str | None:
    """Get the USB device syspath (e.g. '1-4') for a /dev/ttyUSB* port."""
    try:
        r = subprocess.run(
            ["udevadm", "info", "-q", "path", "-n", tty_dev],
            capture_output=True, text=True, timeout=5,
        )
        path = r.stdout.strip()
        # path looks like /devices/.../usb1/1-4/1-4:1.0/ttyUSB3/tty/ttyUSB3
        # or: /devices/.../usb3/3-1/3-1.1/3-1.1:1.0/ttyUSB4/tty/ttyUSB4
        # We want the device path immediately before :1.0 (the leaf USB device)
        m = re.search(r"/((?:\d+)-[\d.]+):\d+\.\d+/", path)
        if m:
            return m.group(1)
    except Exception:
        pass
    return None


def _probe_devpath(probe_syspath: str) -> str | None:
    """Extract the USB device path (e.g. '3-1.2') from a full syspath."""
    return os.path.basename(probe_syspath.rstrip("/")) or None


def match_ports_to_probes(
    ports: list[str],
    probes: dict[str, dict],
) -> dict[str, str | None]:
    """Match each CH340 port to a probe serial via USB tree proximity.

    Returns {port: probe_serial | None}.
    Uses shared ancestor (shared USB hub) to match.
    """
    result: dict[str, str | None] = {p: None for p in ports}
    port_ancestors: dict[str, list[str]] = {}
    for p in ports:
        dp = _tty_usb_syspath(p)
        port_ancestors[p] = _usb_ancestors(dp) if dp else []

    for serial, info in probes.items():
        probe_dp = _probe_devpath(info["syspath"])
        probe_anc = set(_usb_ancestors(probe_dp)) if probe_dp else set()
        best_port = None
        best_depth = 999
        for p, anc_list in port_ancestors.items():
            if result[p] is not None:
                continue  # already matched
            for depth, ancestor in enumerate(anc_list):
                if ancestor in probe_anc:
                    # Prefer deeper match (closer hub) but skip root (depth too high)
                    if 0 < depth < best_depth:
                        best_depth = depth
                        best_port = p
                    break
        if best_port:
            result[best_port] = serial
    return result


# -----------------------------------------------------------------------
# Firmware ID? query (verification + alive check)
# -----------------------------------------------------------------------

def query_id(port: str, baud: int = BAUD, timeout: float = 3.0) -> str | None:
    """Send 'ID?' to a serial port and return the reply, or None."""
    try:
        import serial as pyserial
    except ImportError:
        return None
    try:
        s = pyserial.Serial(port, baud, timeout=0.1)
        s.reset_input_buffer()
        for _ in range(2):
            s.write(b"ID?\r\n")
            time.sleep(0.3)
            deadline = time.monotonic() + 2.0
            buf = bytearray()
            while time.monotonic() < deadline:
                chunk = s.read(512)
                if chunk:
                    buf += chunk
                    while b"\n" in buf:
                        line, buf = buf.split(b"\n", 1)
                        txt = line.rstrip(b"\r").decode(errors="replace").strip()
                        if txt and txt.startswith("ID "):
                            s.close()
                            return txt
        s.close()
    except Exception:
        return None
    return None


def parse_id_reply(reply: str) -> dict:
    """Parse an ID? reply line into a dict.

    Example: 'ID E80BENCH v1.2 fw=0561b29 role=TX armed=1 mod=lora ...'
    """
    d: dict = {}
    if not reply:
        return d
    tokens = reply.split()
    if tokens:
        d["board"] = tokens[1] if len(tokens) > 1 else "?"
    for tok in tokens:
        if "=" in tok:
            k, v = tok.split("=", 1)
            d[k] = v
    return d


# -----------------------------------------------------------------------
# Main detection logic
# -----------------------------------------------------------------------

def detect_board(target_role: str | None = None) -> dict:
    """Auto-detect the local board's role and serial port.

    Args:
        target_role: If "TX" or "RX", assert that the detected board
                     matches. If None, accept either role.

    Returns a dict with keys:
        role, port, probe_serial, id_reply, id_parsed, fw_hash, error

    Exit-worthy errors are returned as {"error": "..."}.
    """
    # Step 1: find SWD probes (determines role — NO openocd needed)
    probes = find_swd_probes()
    if not probes:
        return {
            "error": "no SWD probe found. Ensure the E80 board is plugged in "
                     "(USB cable to the CMSIS-DAP/Pico debugprobe port).",
        }

    if len(probes) == 1:
        # Single-board case (distributed): one probe → use it regardless
        # of label. Boards are identical hardware; role is set at runtime
        # by the host (ROLE TX/RX command), not by probe serial.
        serial, info = next(iter(probes.items()))
        role = target_role or info["role"]
    else:
        # Dual-board case: multiple probes. Use target_role to pick.
        if target_role:
            wanted_serial = PROBE_TX if target_role == "TX" else PROBE_RX
            if wanted_serial in probes:
                serial, info = wanted_serial, probes[wanted_serial]
                role = target_role
            else:
                return {
                    "error": f"no {target_role} probe ({wanted_serial}) found. "
                             f"Available probes: {list(probes.keys())}",
                    "probes_found": list(probes.keys()),
                }
        else:
            return {
                "error": "multiple SWD probes found. Specify --role TX or --role RX.",
                "probes_found": list(probes.keys()),
            }

    if target_role and role != target_role:
        return {
            "error": f"probe says role={role}, but target was {target_role}",
            "probe_serial": serial,
            "role": role,
        }

    # Step 2: find CH340 ports
    ports = find_ch340_ports()
    if not ports:
        return {
            "error": "no CH340 serial port found. Ensure the E80 board's "
                     "USB-serial cable is connected.",
            "probe_serial": serial,
            "role": role,
        }

    if len(ports) == 1:
        # Single board — the only port is ours
        port = ports[0]
    else:
        # Multiple CH340 ports — match via USB tree proximity
        mapping = match_ports_to_probes(ports, probes)
        matched = [p for p, s in mapping.items() if s == serial]
        if matched:
            port = matched[0]
        else:
            # Fallback: try ID? on each port and check role= field
            for p in ports:
                reply = query_id(p)
                if reply:
                    parsed = parse_id_reply(reply)
                    if parsed.get("role", "").upper() == role:
                        port = p
                        break
            else:
                return {
                    "error": f"could not determine which CH340 port is {role}. "
                             f"Found {ports}. Try --port to specify manually.",
                    "probe_serial": serial,
                    "role": role,
                    "ports": ports,
                }

    # Step 3: verify board is alive with ID?
    id_reply = query_id(port)
    id_parsed = parse_id_reply(id_reply) if id_reply else {}

    return {
        "role": role,
        "port": port,
        "probe_serial": serial,
        "id_reply": id_reply,
        "id_parsed": id_parsed,
        "fw_hash": id_parsed.get("fw"),
        "openocd": find_openocd(),
    }


def detect_dual_board() -> dict:
    """Detect both TX and RX boards on the local machine (bench mode).

    Returns {"tx": {...}, "rx": {...}} where each sub-dict has
    port, probe_serial, id_reply. Uses USB tree matching, then
    falls back to ID? role= field, then radio handshake.
    """
    probes = find_swd_probes()
    ports = find_ch340_ports()
    result: dict = {"tx": None, "rx": None}

    if not ports or not probes:
        return {"error": "need 2 CH340 ports + 2 SWD probes for dual-board mode",
                "ports": ports, "probes": list(probes.keys())}

    # Try USB tree matching first
    mapping = match_ports_to_probes(ports, probes)
    for port, serial in mapping.items():
        if serial and serial in probes:
            role = probes[serial]["role"]
            reply = query_id(port)
            result["tx" if role == "TX" else "rx"] = {
                "port": port,
                "probe_serial": serial,
                "role": role,
                "id_reply": reply,
                "id_parsed": parse_id_reply(reply) if reply else {},
            }

    if result["tx"] and result["rx"]:
        return result

    # Fallback: ID? role= field
    for port in ports:
        if any(port == r["port"] for r in [result["tx"], result["rx"]] if r):
            continue
        reply = query_id(port)
        parsed = parse_id_reply(reply) if reply else {}
        role = parsed.get("role", "").upper()
        if role in ("TX", "RX") and not result[role.lower()]:
            result[role.lower()] = {
                "port": port,
                "probe_serial": None,
                "role": role,
                "id_reply": reply,
                "id_parsed": parsed,
            }

    if result["tx"] and result["rx"]:
        return result

    return {"error": "could not fully auto-detect dual boards",
            "partial": result, "ports": ports}


# -----------------------------------------------------------------------
# CLI
# -----------------------------------------------------------------------

def main():
    import argparse
    ap = argparse.ArgumentParser(description="E80 board auto-detection")
    ap.add_argument("--role", choices=["TX", "RX"], default=None,
                    help="assert the board is this role (for auto-role-detect, omit)")
    ap.add_argument("--port", default=None, help="skip detection, use this port")
    ap.add_argument("--json", action="store_true", help="output JSON")
    ap.add_argument("--check-deps", action="store_true", help="check dependencies and exit")
    ap.add_argument("--dual", action="store_true", help="detect both TX+RX on this machine")
    args = ap.parse_args()

    if args.check_deps:
        deps = check_deps()
        if args.json:
            print(json.dumps(deps, indent=2))
        else:
            for k, v in deps.items():
                if k == "issues":
                    for issue in v:
                        print(f"  ⚠ {issue}")
                else:
                    print(f"  {k}: {v}")
        sys.exit(0 if deps["all_ok"] else 2)

    if args.dual:
        result = detect_dual_board()
    else:
        result = detect_board(target_role=args.role)

    if args.json:
        print(json.dumps(result, indent=2, default=str))
    else:
        for k, v in result.items():
            print(f"  {k}: {v}")

    sys.exit(0 if "error" not in result else 1)


if __name__ == "__main__":
    main()
