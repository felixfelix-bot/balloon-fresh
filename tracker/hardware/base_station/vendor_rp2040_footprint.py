#!/usr/bin/env python3
"""The RP2040 footprint lives ONLY in KiCad's tiny_tapeout DEMO library, not in the main
footprint set. Vendor it into the repo so the board builds from a library we control, rather
than depending on a demo directory that a KiCad upgrade can remove.

Measured 2026-10-14:
  /usr/share/kicad/footprints/MCU_RaspberryPi_and_Boards.pretty   -> DOES NOT EXIST
  /usr/share/kicad/demos/tiny_tapeout/tinytapeout-kicad-libs/footprints/
      MCU_RaspberryPi_and_Boards.pretty/RP2040-QFN-56.kicad_mod   -> EXISTS
"""
import os
import shutil
import subprocess

WT = "/home/c08r4d0r/worktrees/v9-route"
SRC = ("/usr/share/kicad/demos/tiny_tapeout/tinytapeout-kicad-libs/footprints/"
       "MCU_RaspberryPi_and_Boards.pretty/RP2040-QFN-56.kicad_mod")
DEST_DIR = f"{WT}/tracker/hardware/base_station/library.pretty"
DEST = os.path.join(DEST_DIR, "RP2040-QFN-56.kicad_mod")

os.makedirs(DEST_DIR, exist_ok=True)

if not os.path.exists(SRC):
    raise SystemExit(f"source footprint vanished: {SRC}")

# record provenance IN the file so the vendored copy is auditable
src_bytes = open(SRC, encoding="utf-8").read()
sha = subprocess.run(["sha256sum", SRC], capture_output=True, text=True).stdout.split()[0]

banner = (f"# VENDORED from a KiCad DEMO library, not the main footprint set.\n"
          f"# source : {SRC}\n"
          f"# sha256 : {sha}\n"
          f"# why    : /usr/share/kicad/footprints/MCU_RaspberryPi_and_Boards.pretty does NOT exist;\n"
          f"#          the RP2040 QFN-56 footprint ships only in the tiny_tapeout demo, which a\n"
          f"#          KiCad upgrade may remove. Vendoring makes the build reproducible.\n"
          f"# date   : 2026-10-14\n")

with open(DEST, "w", encoding="utf-8") as f:
    f.write(banner + src_bytes)

print(f"vendored -> {DEST}")
print(f"  sha256 of source: {sha}")
print(f"  bytes: {len(src_bytes)}")
print()
print("library.pretty contents:")
for fn in sorted(os.listdir(DEST_DIR)):
    print(f"  {fn}")
