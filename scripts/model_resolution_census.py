#!/usr/bin/env python3
"""model_resolution_census.py -- does every 3D model reference a board makes resolve?

WHY THIS EXISTS
---------------
A `kicad-cli pcb render` of a board whose footprints reference missing 3D models
**succeeds silently**.  It prints "Successfully created 3D render image" and the
missing parts are simply absent from the picture.  Nothing in the output says so.

That matters because the operator's review gate is a *spatial* review of the
render: a reviewer cannot judge the placement, orientation or clearance of a part
it cannot see.  So "the render worked" is not evidence that the render is
complete, and this script is the thing that turns "complete" into a number.

Measured on the v9 hub before this check existed: 32 of the board's model
references resolved 25, and the seven that did not included **the two LoRa2021
radios and the ESP32-S3 MCU** -- the largest and most RF-critical bodies on the
board.  The render looked populated; the parts that matter were invisible.

HOW MODELS RESOLVE
------------------
A footprint's `(model "<path>")` may contain `${VAR}` references:

  ${KIPRJMOD}              -> the directory holding the board file
  ${KICAD9_3DMODEL_DIR}    -> the KiCad 3D-model package dir
  ${KICAD8_3DMODEL_DIR}    -> the previous-major version of the same

KiCad substitutes the `KICAD*_3DMODEL_DIR` variables from its own built-in
default table.  On this machine `~/.config/kicad/9.0/kicad_common.json` has
`{"vars": null}`, i.e. the built-in default wins, which is
`/usr/share/kicad/3dmodels` (the `kicad-packages3d` package).  A stale in-repo
claim that the package is "not installed, so the hub renders bare" is FALSE on
this machine -- see AGENTS.md.  Resolving against the built-in default is what
makes this check agree with the renderer; resolving against the shell environment
would not, because `KICAD9_3DMODEL_DIR` is unset in the shell and the renderer
does not read it from there.

RUN
---
    /usr/bin/python3.14 scripts/model_resolution_census.py <board.kicad_pcb> ...
    /usr/bin/python3.14 scripts/model_resolution_census.py --check <board> ...   # exit 1 if any ref is unresolved

No `pcbnew` import: this is a text parse of the board file, so it runs under the
3.11 test interpreter too.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys

# KiCad's built-in default for KICAD<n>_3DMODEL_DIR.  See the module docstring:
# the renderer uses the built-in table, not the shell environment.
KICAD_3DMODEL_DIR = "/usr/share/kicad/3dmodels"

_MODEL_RE = re.compile(r'\(model\s+"([^"]+)"')


def _iter_statements(text: str, token: str):
    """Yield each balanced `(token ...)` statement in `text`."""
    i = 0
    while True:
        start = text.find(token, i)
        if start < 0:
            return
        depth, p = 0, start
        while p < len(text):
            if text[p] == "(":
                depth += 1
            elif text[p] == ")":
                depth -= 1
                if depth == 0:
                    p += 1
                    break
            p += 1
        yield text[start:p]
        i = p


def _hidden_models(block: str) -> list[str]:
    """Model references inside `block` that carry `(hide yes)`.

    A hidden model is a THIRD way to be invisible, distinct from both a missing
    `(model ...)` block and an unresolvable path: the file may exist and resolve
    perfectly and the renderer will still draw nothing. Measured on the v9 hub:
    U3's reference to `NiceRF_LoRa2021.wrl` carried `(hide yes)` (it came in with
    the library footprint), so even with the file installed that radio would
    have stayed out of the render -- and a resolution-only check would have
    called it resolved and waved it through.
    """
    out = []
    for stmt in _iter_statements(block, "(model "):
        m = _MODEL_RE.search(stmt)
        if m and re.search(r"\(\s*hide\s+yes\s*\)", stmt):
            out.append(m.group(1))
    return out


def _expand(ref: str, project_dir: str) -> str:
    """Substitute the ${VAR} forms a KiCad board file may use."""
    out = ref
    out = out.replace("${KIPRJMOD}", project_dir)
    # Any major version: the board may still name a previous release's variable.
    out = re.sub(r"\$\{KICAD\d+_3DMODEL_DIR\}", KICAD_3DMODEL_DIR, out)
    out = os.path.expanduser(out)
    return out


_REF_RE = re.compile(r'\(property "Reference" "([^"]+)"')


def _iter_footprint_blocks(text: str):
    """Yield each top-level `(footprint ...)` block, paren-balanced.

    A regex cannot do this: footprint bodies nest arbitrarily deep (pads, models,
    graphics), so the block must be walked with a depth counter.
    """
    i = 0
    token = "(footprint "
    while True:
        start = text.find(token, i)
        if start < 0:
            return
        depth, p = 0, start
        while p < len(text):
            if text[p] == "(":
                depth += 1
            elif text[p] == ")":
                depth -= 1
                if depth == 0:
                    p += 1
                    break
            p += 1
        yield text[start:p]
        i = p


def census(board_path: str) -> dict:
    """Per-board model-reference resolution report."""
    board_path = os.path.abspath(board_path)
    project_dir = os.path.dirname(board_path)
    with open(board_path) as fh:
        text = fh.read()

    refs_by_fp: dict[str, list[str]] = {}
    hidden_by_fp: dict[str, list[str]] = {}
    for block in _iter_footprint_blocks(text):
        m = _REF_RE.search(block)
        ref = m.group(1) if m else "?"
        refs_by_fp.setdefault(ref, []).extend(_MODEL_RE.findall(block))
        hid = _hidden_models(block)
        if hid:
            hidden_by_fp.setdefault(ref, []).extend(hid)

    all_refs = [r for rs in refs_by_fp.values() for r in rs]
    resolved, unresolved = [], []
    for ref in all_refs:
        path = _expand(ref, project_dir)
        (resolved if os.path.isfile(path) else unresolved).append(ref)

    # A footprint with no model block is a DIFFERENT defect from one whose model
    # points at a file that is not there: the first is an omission in the
    # generator, the second a missing dependency.  Neither is proof of a problem
    # on its own -- a 3.2 mm mounting hole legitimately carries no model, while a
    # 39 x 21 mm radio that carries none is invisible to the spatial reviewer --
    # so the designators are reported and a caller can name the ones that must
    # have a model via --require-refs.
    without_model = sorted(r for r in refs_by_fp if not refs_by_fp[r])
    n_footprints = len(refs_by_fp)
    return {
        "board": os.path.relpath(board_path),
        "footprints": n_footprints,
        "model_refs": len(all_refs),
        "resolved": len(resolved),
        "unresolved": len(unresolved),
        "footprints_without_model": without_model,
        "without_model_set": without_model,
        "unresolved_refs": sorted(set(unresolved)),
        "hidden_refs": sorted({r for rs in hidden_by_fp.values() for r in rs}),
        "hidden_by_footprint": {k: v for k, v in sorted(hidden_by_fp.items())},
        "refs_by_footprint": {k: v for k, v in sorted(refs_by_fp.items())},
    }


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    ap.add_argument("boards", nargs="+", help=".kicad_pcb files to census")
    ap.add_argument("--check", action="store_true",
                    help="exit 1 if any model reference is unresolved, or any --require-refs part has no model")
    ap.add_argument("--require-refs", default="",
                    help="comma-separated designators that MUST carry a model, e.g. U1,U2,U3")
    ap.add_argument("--json", metavar="OUT", help="also write the report as JSON")
    args = ap.parse_args(argv)

    required = [r for r in (s.strip() for s in args.require_refs.split(",")) if r]
    reports = [census(b) for b in args.boards]
    failures = 0

    for r in reports:
        ok = not r["unresolved_refs"] and not r["hidden_refs"]
        missing_required = [x for x in required if x in r["without_model_set"]]
        if missing_required:
            ok = False
        print(f"{'OK  ' if ok else 'FAIL'}  {r['board']}")
        print(f"    footprints {r['footprints']}  model refs {r['model_refs']}  "
              f"resolved {r['resolved']}  unresolved {r['unresolved']}")
        if r["footprints_without_model"]:
            print(f"    no model block: {', '.join(r['footprints_without_model'])}")
        for ref in r["unresolved_refs"]:
            print(f"    MISSING {ref}")
        for ref in r["hidden_refs"]:
            print(f"    HIDDEN  {ref}   (resolves, but (hide yes) keeps it out of the render)")
        if missing_required:
            print(f"    REQUIRED but has no model: {', '.join(missing_required)}")
        if not ok:
            failures += 1

    if args.json:
        with open(args.json, "w") as fh:
            json.dump(reports, fh, indent=2)
        print(f"\nwrote {args.json}")

    if failures:
        print(f"\n{failures} of {len(reports)} board(s) NOT ready for a spatial review", file=sys.stderr)
        return 1 if args.check else 0
    print(f"\nall {len(reports)} board(s) OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
