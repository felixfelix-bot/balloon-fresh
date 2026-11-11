#!/usr/bin/env python3
"""Run isolated, one-fault-at-a-time controls; never modify the source spec."""
from pathlib import Path
import subprocess
import sys

if __name__ == "__main__":
    test = Path(__file__).resolve().with_name("test_verifier_portability.py")
    raise SystemExit(subprocess.call([sys.executable, str(test), "-v"]))
