#!/usr/bin/env python3
"""e80_detect_port.py — single source of truth for the E80 bench console port.

Why this exists (Funchal demo bug):
  laptop-tx-setup.sh used to re-grep /dev/ttyACM* for the SWD probe serial
  and could match the Pico debugprobe CDC UART (/dev/ttyACM0) — NOT the CH340
  console. The installer then generated per-stop commands with
  PORT=/dev/ttyACM0, which is a field failure (the E80 console never answers
  on the probe CDC).

The E80 console port is ALWAYS a CH340 USB-serial (/dev/ttyUSB* on Linux,
/dev/cu.usbserial-* on macOS). The authoritative answer lives in the `port:`
field of `python3 tools/e80_detect.py`. This module parses exactly that field
and refuses anything that isn't a CH340-style console port.

Ban rule: /dev/ttyACM* (and /dev/tty.usbmodem* on macOS) are Pico probe CDC
UARTs — never a valid E80 console port. If the resolved port matches one, we
abort rather than emit a broken command.

Usage (run from the e80-stm32-bench dir so relative `tools/e80_detect.py` works,
or from anywhere with --detect-cmd / --port-from-output):
    python3 tools/../scripts/e80_detect_port.py            # run e80_detect.py, print port
    python3 e80_detect_port.py --port-from-output '<text>' # parse already-captured output
    python3 e80_detect_port.py --detect-cmd 'cmd...'       # run a custom detect command

Exit codes: 0 = ok (port printed on stdout), non-zero = failure (message on stderr).
"""

from __future__ import annotations

import re
import subprocess
import sys

# Console ports for the E80 bench are CH340 USB-serial. These glob prefixes are
# the ONLY acceptable console ports.
CH340_CONSOLE_GLOBS = ("/dev/ttyUSB", "/dev/cu.usbserial", "/dev/tty.usbserial")

# Pico debugprobe CDC UARTs — never a valid E80 console port. If detection
# resolves to one of these, we abort (the operator plugged the probe cable into
# the serial port, or detection is broken).
PICO_PROBE_CDC = ("/dev/ttyACM", "/dev/tty.usbmodem")


def parse_detect_port(detect_output: str) -> str:
    """Extract the `port:` field from e80_detect.py output.

    Raises SystemExit with a clear message (non-zero code) if:
      - no `port:` field is present, or
      - the port is blank, or
      - the port resolves to a Pico debugprobe CDC UART (/dev/ttyACM*).
    Returns the console port path on success.
    """
    m = re.search(r"^\s*port:\s*(\S+)\s*$", detect_output, re.MULTILINE)
    if not m:
        sys.exit(
            "ERROR: e80_detect.py output has no 'port:' field — board may not be "
            "connected. Plug in the E80 board (CH340 serial + Pico probe cables) "
            "and re-run the installer."
        )
    port = m.group(1).strip()
    if not port:
        sys.exit("ERROR: e80_detect.py returned an empty port field.")

    for acm in PICO_PROBE_CDC:
        if port.startswith(acm):
            sys.exit(
                f"ERROR: resolved console port is {port} — that is the Pico "
                f"debugprobe CDC UART, NOT the E80 console. The E80 console is a "
                f"CH340 USB-serial ({CH340_CONSOLE_GLOBS[0]}*/{CH340_CONSOLE_GLOBS[1]}*). "
                f"Plug the CH340 cable into the serial port, not the probe port."
            )
    if not any(port.startswith(g) for g in CH340_CONSOLE_GLOBS):
        sys.exit(
            f"ERROR: port '{port}' is not a recognized CH340 console port. "
            f"Expected one of: {', '.join(CH340_CONSOLE_GLOBS) + '*'}."
        )
    return port


def _run_detect(detect_cmd: list[str]) -> str:
    """Run the detect command and return its stdout."""
    try:
        proc = subprocess.run(
            detect_cmd, capture_output=True, text=True, timeout=60
        )
    except FileNotFoundError as e:
        sys.exit(f"ERROR: could not run detect command: {e}")
    except subprocess.TimeoutExpired:
        sys.exit("ERROR: e80_detect.py timed out (board may be wedged).")
    if proc.returncode != 0:
        # Detection failed (board not connected / no CH340) — surface the
        # detect tool's own diagnostic, then exit non-zero.
        err = proc.stderr.strip() or proc.stdout.strip() or "unknown error"
        sys.exit(f"ERROR: e80_detect.py failed:\n{err}")
    return proc.stdout


def main() -> None:
    import argparse

    ap = argparse.ArgumentParser(
        description="Print the E80 bench CH340 console port (single source of truth)."
    )
    ap.add_argument(
        "--port-from-output",
        help="Parse the port from already-captured e80_detect.py output (for testing).",
    )
    ap.add_argument(
        "--detect-cmd",
        default=None,
        help="Custom detect command (default: run e80_detect.py from the bench dir).",
    )
    args = ap.parse_args()

    if args.port_from_output is not None:
        out = args.port_from_output
    else:
        detect_cmd: str = args.detect_cmd or "python3 tools/e80_detect.py"
        out = _run_detect(detect_cmd.split())

    print(parse_detect_port(out))


if __name__ == "__main__":
    main()
