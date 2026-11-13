#!/usr/bin/env python3
"""Hide 3D models whose file does not resolve, by TEXT, because the API cannot do it.

WHY TEXT AND NOT THE API. `pcbnew` exposes `m_Show`, but `Models()` returns COPIES and there is
no `RemoveModel()`, so setting the flag in Python does not survive `SaveBoard`. Measured on this
repo previously; re-measured here: a flag-only attempt wrote a board whose models were all still
visible. The `(hide yes)` token must be written into the file.

WHY HIDE RATHER THAN SUBSTITUTE. `${KICAD9_3DMODEL_DIR}/Package_CSP.3dshapes/LFCSP-32-1EP_5x5mm_
P0.5mm_EP3.1x3.1mm.step` does not exist, and the installed library carries
`..._EP3.6x3.6mm.step` instead -- a DIFFERENT exposed-pad size. Pointing the footprint at it would
render a part the board does not have, and `kicad-cli pcb render` exits 0 either way, so the error
would be invisible. Excluding is honest; substituting is not. Same rule as the `-1U` suffix trap.

WHY THE COMMIT GATE CARES. `pad_audit.py` (invoked from the pre-commit hook) counts a model as a
defect only if it is BOTH unresolved and still shown, so hiding is the correct fix and it reports
which refs were affected rather than failing silently.

Usage: hide_unresolved_models.py BOARD.kicad_pcb [--json OUT.json]
Exit: 0 = every unresolved model hidden (or none present), 1 = something could not be hidden,
      2 = could not run.
"""
import argparse
import json
import os
import re
import sys

KNOWN_DIRS = [
    "/usr/share/kicad/3dmodels",
    os.path.expanduser("~/.local/share/kicad/9.0/3dmodels"),
]


def resolve(model_path):
    """Resolve a ${VAR}/rel/path model reference against the installed library."""
    p = model_path.strip()
    p = re.sub(r"^\$\{[A-Z0-9_]+\}/", "", p)
    for d in KNOWN_DIRS:
        cand = os.path.join(d, p)
        if os.path.exists(cand):
            return cand
    return None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("board")
    ap.add_argument("--json")
    a = ap.parse_args()

    if not os.path.exists(a.board):
        print(f"REFUSED: board not found: {a.board}")
        return 2

    text = open(a.board, encoding="utf-8").read()

    # a model block: (model "PATH" ... (hide yes|no)? ...) -- hide may be absent, and when absent
    # the model IS drawn. Track each block's span so the edit is positional, not regex-blind.
    unresolved = []
    hidden_now = 0
    already = 0
    edits = []

    for m in re.finditer(r'\n(\t+)\(model "([^"]*)"', text):
        start = m.start() + 1
        # find the matching close paren for this model block
        depth = 0
        end = None
        for j in range(start, len(text)):
            if text[j] == "(":
                depth += 1
            elif text[j] == ")":
                depth -= 1
                if depth == 0:
                    end = j + 1
                    break
        if end is None:
            print(f"REFUSED: unbalanced model block near offset {start}")
            return 2
        block = text[start:end]
        path = m.group(2)
        if resolve(path):
            continue
        unresolved.append(path)
        if re.search(r"\(hide yes\)", block):
            already += 1
            continue
        if re.search(r"\(hide no\)", block):
            newblock = block.replace("(hide no)", "(hide yes)", 1)
        else:
            # insert (hide yes) right after the path token, at the block's own indent
            indent = m.group(1) + "\t"
            insert_at = block.index('"', block.index('"') + 1) + 1
            newblock = block[:insert_at] + f"\n{indent}(hide yes)" + block[insert_at:]
        edits.append((start, end, newblock))
        hidden_now += 1

    for start, end, newblock in reversed(edits):     # back-to-front keeps offsets valid
        text = text[:start] + newblock + text[end:]

    if edits:
        open(a.board, "w", encoding="utf-8").write(text)

    print(f"board            : {a.board}")
    print(f"unresolved refs  : {len(unresolved)}")
    for p in sorted(set(unresolved)):
        print(f"   {p}")
    print(f"newly hidden     : {hidden_now}")
    print(f"already hidden   : {already}")

    # read-back: the edit must be on disk, not just in memory
    back = open(a.board, encoding="utf-8").read()
    still_shown = 0
    for m in re.finditer(r'\n(\t+)\(model "([^"]*)"', back):
        start = m.start() + 1
        depth = 0
        block = None
        for j in range(start, len(back)):
            if back[j] == "(":
                depth += 1
            elif back[j] == ")":
                depth -= 1
                if depth == 0:
                    block = back[start:j + 1]
                    break
        if block is None:
            print(f"REFUSED: unbalanced model block at offset {start}")
            return 2
        if not resolve(m.group(2)) and "(hide yes)" not in block:
            still_shown += 1
    print(f"read-back        : {still_shown} unresolved model(s) still shown")
    if a.json:
        json.dump({"board": a.board, "unresolved": sorted(set(unresolved)),
                   "hidden": hidden_now, "already_hidden": already,
                   "still_shown": still_shown}, open(a.json, "w"), indent=1)
    return 0 if still_shown == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
