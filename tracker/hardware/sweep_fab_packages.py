#!/usr/bin/env python3
"""Sweep every fab package in the repo for the stale-artifact drift class.

Finds each gerber dir / zip, pairs it with its board (by name), runs
verify_fab_package.py, and reports which packages are INCOHERENT.
"""
import os, re, subprocess, sys

WT = "/home/c08r4d0r/worktrees/v9-route"
HW = f"{WT}/tracker/hardware"
GATE = f"{HW}/verify_fab_package.py"
sys.path.insert(0, "/usr/lib/python3/dist-packages")

# 1. every gerber dir + zip
pkgs = []
for root, dirs, files in os.walk(f"{HW}/output"):
    if ".git" in root:
        continue
    base = os.path.basename(root)
    if base.startswith("gerbers"):
        pkgs.append(root)
    for f in files:
        if f.endswith(".zip") and "gerber" in f.lower():
            pkgs.append(os.path.join(root, f))
pkgs = sorted(set(pkgs))

# 2. every board, for pairing
boards = {}
for root, dirs, files in os.walk(f"{HW}"):
    if ".git" in root:
        continue
    for f in files:
        if f.endswith(".kicad_pcb"):
            boards[f[:-10]] = os.path.join(root, f)

print(f"found {len(pkgs)} package(s), {len(boards)} board file(s)\n")

def pick_board(pkgname):
    """Best-effort pairing: strip gerbers_/prefix and match a board stem."""
    n = os.path.basename(pkgname)
    n = re.sub(r"^gerbers_", "", n)
    n = re.sub(r"_jlcpcb\.zip$", "", n)
    n = re.sub(r"\.zip$", "", n)
    # exact
    if n in boards:
        return n, boards[n]
    # prefix / substring match, longest stem first so wing_board_v9 beats v9
    cands = sorted(boards.items(), key=lambda kv: -len(kv[0]))
    for stem, path in cands:
        if n.startswith(stem) or stem.startswith(n) or stem in n or n in stem:
            return stem, path
        if n.replace("_", "") == stem.replace("_", ""):
            return stem, path
    return None, None

results = []
for pkg in pkgs:
    stem, board = pick_board(pkg)
    rel = os.path.relpath(pkg, WT)
    if not board:
        results.append(("NO-BOARD", rel, "", ""))
        continue
    try:
        p = subprocess.run([sys.executable, GATE, board, pkg],
                           capture_output=True, text=True, timeout=300)
        out = p.stdout
        verdict = "COHERENT" if p.returncode == 0 else "INCOHERENT"
        probs = [l.strip() for l in out.splitlines() if l.strip().startswith("- ")]
        results.append((verdict, rel, os.path.relpath(board, WT), "; ".join(probs)))
    except Exception as e:
        results.append(("ERROR", rel, os.path.relpath(board, WT), str(e)[:80]))

print("=" * 78)
for v, pkg, board, probs in results:
    print(f"[{v:10}] {pkg}")
    if board:
        print(f"             board: {board}")
    if probs:
        print(f"             {probs}")
print("=" * 78)
from collections import Counter
c = Counter(v for v, *_ in results)
print("summary:", dict(c))
