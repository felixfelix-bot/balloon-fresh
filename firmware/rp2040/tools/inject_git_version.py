#!/usr/bin/env python3
"""
inject_git_version.py — PlatformIO extra_script for firmware self-identification.

Runs at build time (via platformio.ini: extra_scripts = pre:tools/inject_git_version.py).
Reads git state and injects three -D defines into the build:

    FW_GIT_HASH    — 7-char short git hash (e.g. "abc123d")
    FW_BUILD_TAG   — "TX0" or "RX0" (derived from PIO environment name)
    FW_BUILD_TIME  — ISO 8601 UTC timestamp (e.g. "2026-07-24T14:30Z")

In firmware, use:

    #ifndef FW_GIT_HASH
    #define FW_GIT_HASH "unknown"
    #endif
    #ifndef FW_BUILD_TAG
    #define FW_BUILD_TAG "UNK0"
    #endif
    #ifndef FW_BUILD_TIME
    #define FW_BUILD_TIME "1970-01-01T00:00Z"
    #endif

This allows the firmware to always compile (with fallback defines) even when
built outside PlatformIO or without the extra_script enabled.
"""

import subprocess
import sys
import os
from datetime import datetime, timezone


def _git_output(args, fallback="unknown"):
    """Run a git command, return stripped stdout or fallback on failure."""
    try:
        result = subprocess.run(
            args,
            stdout=subprocess.PIPE,
            text=True,
            timeout=5,
            stderr=subprocess.DEVNULL,
        )
        if result.returncode == 0:
            val = result.stdout.strip()
            if val:
                return val
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        pass
    return fallback


def _derive_build_tag(pioenv):
    """Derive TX0/RX0 from the PlatformIO environment name."""
    env_lower = pioenv.lower()
    if "tx" in env_lower:
        return "TX0"
    if "rx" in env_lower:
        return "RX0"
    return "UNK0"


def main():
    Import("env")  # noqa: F821 — provided by SCons/PlatformIO at import time

    # Determine current PIO environment name
    pioenv = str(env.get("PIOENV", ""))  # noqa: F821
    if not pioenv:
        # Fallback: scan argv for -e/--environment
        for i, arg in enumerate(sys.argv):
            if arg in ("-e", "--environment") and i + 1 < len(sys.argv):
                pioenv = sys.argv[i + 1]
                break

    # Gather git state
    git_hash = _git_output(
        ["git", "rev-parse", "--short=7", "HEAD"], fallback="0000000"
    )
    # Ensure exactly 7 chars
    git_hash = git_hash[:7].ljust(7, "0")

    git_dirty = _git_output(
        ["git", "describe", "--always", "--dirty"], fallback=git_hash
    )

    build_tag = _derive_build_tag(pioenv)
    build_time = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%MZ")

    # Inject as BUILD_FLAGS with proper string-literal escaping.
    # SCons passes these as: -DFW_GIT_HASH=\"abc123d\"
    # Compiler sees: -DFW_GIT_HASH="abc123d"
    # C++ sees: FW_GIT_HASH → "abc123d"
    env.Append(  # noqa: F821
        BUILD_FLAGS=[
            f'-DFW_GIT_HASH=\\"{git_hash}\\"',
            f'-DFW_BUILD_TAG=\\"{build_tag}\\"',
            f'-DFW_BUILD_TIME=\\"{build_time}\\"',
        ]
    )

    print(f"  inject_git_version: hash={git_hash} tag={build_tag} "
          f"time={build_time} env={pioenv}")


main()
