#!/usr/bin/env python3
"""Render meshcore.h from template_values.sh.

WHY: the mesh's sizing constants (header width, MTU, fragment limit, TTL bound)
must agree everywhere they appear or the firmware silently disagrees with the
host suite. template_values.sh is the single source of truth; this script renders
the C++ header from it, and the host test diffs the rendered values back against
the compiled constants in meshcodec.h / mesh.h / meshsim.h. Change a constant in
one place only and the host suite fails loudly.

Usage:
  scripts/gen_meshcore_header.py            # write firmware/lib/meshcore/meshcore.h
  scripts/gen_meshcore_header.py --check    # fail (exit 1) if the file is stale
"""
import argparse
import os
import re
import sys

NAMES = [
    "MESH_WIRE_VERSION",
    "MESH_HEADER_SIZE",
    "MESH_MAX_PAYLOAD",
    "MESH_MAX_DATAGRAM",
    "MESH_MAX_FRAGS",
    "MESH_MAX_NEIGHBORS",
    "MESH_NO_WAKE",
    "MESH_MAX_BACKOFF_MS",
    "MESH_MAX_QUEUE",
    "MESH_NODES",
]
# The rendered type is chosen from the value, so a constant that grows past one
# byte (an MTU, an id space) widens instead of silently wrapping.
U8_MAX = 255


def parse_values(path):
    values = {}
    with open(path, "r", encoding="utf-8") as fh:
        for lineno, raw in enumerate(fh, 1):
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            parts = line.split()
            if len(parts) != 2:
                raise SystemExit("%s:%d: expected 'NAME value'" % (path, lineno))
            name, value = parts
            if not re.fullmatch(r"\d+", value):
                raise SystemExit("%s:%d: value must be a decimal integer" % (path, lineno))
            values[name] = int(value)
    missing = [n for n in NAMES if n not in values]
    if missing:
        raise SystemExit("missing constants in %s: %s" % (path, ", ".join(missing)))
    return values


def render(values):
    out = []
    out.append("// Generated from template_values.sh by "
               "scripts/gen_meshcore_header.py.")
    out.append("// Do not edit by hand: change the constant's single source of "
               "truth instead.")
    out.append("#pragma once")
    out.append("")
    out.append("#include <cstdint>")
    out.append("")
    out.append("namespace balloon {")
    out.append("namespace mesh {")
    out.append("namespace tpl {")
    out.append("")
    width = max(len(n) for n in NAMES)
    for name in NAMES:
        ctype = "uint8_t" if values[name] <= U8_MAX else "uint32_t"
        out.append("constexpr %-8s %-*s = %uu;" % (ctype, width, name, values[name]))
    out.append("")
    out.append("}  // namespace tpl")
    out.append("}  // namespace mesh")
    out.append("}  // namespace balloon")
    out.append("")
    return "\n".join(out)


def main():
    # The script lives in <module>/scripts/, so the module directory is one level
    # up. Resolving both files from there keeps the script independent of the
    # repo root and of the caller's cwd.
    here = os.path.dirname(os.path.abspath(__file__))
    module_dir = os.path.dirname(here)
    values_file = os.path.join(module_dir, "template_values.sh")
    header_file = os.path.join(module_dir, "meshcore.h")
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true",
                    help="exit 1 if meshcore.h does not match template_values.sh")
    ap.add_argument("--values", default=values_file,
                    help="override the single-source-of-truth file")
    ap.add_argument("--header", default=header_file,
                    help="override the header to write / compare")
    args = ap.parse_args()
    values_file = args.values
    header_file = args.header

    want = render(parse_values(values_file))
    if args.check:
        try:
            with open(header_file, "r", encoding="utf-8") as fh:
                have = fh.read()
        except FileNotFoundError:
            print("STALE: %s is missing" % header_file)
            return 1
        if have != want:
            print("STALE: %s does not match template_values.sh" % header_file)
            print("       run scripts/gen_meshcore_header.py to regenerate")
            return 1
        print("OK: %s matches template_values.sh" % header_file)
        return 0

    os.makedirs(os.path.dirname(header_file), exist_ok=True)
    with open(header_file, "w", encoding="utf-8") as fh:
        fh.write(want)
    print("wrote %s" % header_file)
    return 0


if __name__ == "__main__":
    sys.exit(main())
