#!/usr/bin/env python3
"""Deterministic, fail-closed BOM cold-temperature gate (ADR-043).

WHY
---
ADR-043 records the *negative* result that heating board components to survive
stratospheric cold is not a viable remedy (see the energy arithmetic in the
ADR), and that the real risk is components used BELOW their rated minimum with
nothing gating it.  This script is that gate.  It is fully deterministic: no
LLM, no network, stdlib only.

WHAT IT CHECKS
--------------
Every part's rated MINIMUM operating temperature is compared against the
mission minimum (default -60 C, see --mission-min and ADR-043 for the source).
A part is acceptable only if `rated_min_c <= mission_min` (at least as cold as
the mission requires).

EXIT CODES (fail-closed -- a missing rating is never a silent pass)
-------------------------------------------------------------------
  0  PASS           every part is rated at or below the mission minimum
  1  FAIL           at least one part is rated ABOVE the mission minimum
  2  CANNOT-VERIFY  no FAIL, but at least one part has no temperature data
A definite FAIL outranks CANNOT-VERIFY (exit 1).  A part with no temperature
data ALWAYS yields at least exit 2 and is named in the output.

INPUTS
------
  --bom FILE.csv     BOM to check.  Headers:
                       ref,value[,mpn][,rated_min_c][,rated_max_c][,source]
                     If rated_min_c is absent/blank for a row, the ratings DB
                     is consulted by mpn then by value.
  --pcb FILE.kicad_pcb
                     Instead of a CSV, parse footprints + Reference + Value
                     from a KiCad PCB and look each part up in the ratings DB.
  --ratings FILE.csv Ratings DB.  Headers:
                       key,rated_min_c,rated_max_c,source
                     Default: bom_ratings.csv next to this script.
  --mission-min C    Mission minimum in degrees Celsius (default -60).
  --strict-provenance
                     Treat a row whose `source` starts with TODO/UNVERIFIED as
                     CANNOT-VERIFY (fail-closed on unprovenanced ratings).

PROVENANCE (ADR-043)
--------------------
Every rating in the ratings DB MUST cite a real document + line/table/page.
A rating that is unprovenanced, or that is an invented "typical range" class
guess rather than a document citation, MUST NOT silently produce a PASS or a
FAIL verdict -- it is CANNOT-VERIFY.  Therefore:

  * a row with `source` empty, or starting with TODO/UNVERIFIED, is
    unprovenanced                              -> CANNOT-VERIFY;
  * a `source` that reads as a class guess (contains "typical") is not a
    document citation                         -> CANNOT-VERIFY;
  * `--strict-provenance` is the HONEST mode and is the mode to use for a real
    qualification call.  Without it an unprovenanced rating is taken at face
    value -- and a guessed number that reads like a rating is worse than no
    number, because it drives a verdict off a fabrication.

A `source` is a claim about provenance, not proof of it: `--strict-provenance`
cannot detect a citation that is simply wrong.  What keeps the gate sound is
curation -- every retained rating cites a specific document+location, and rows
that cannot be sourced are DELETED (leaving the part at CANNOT-VERIFY), never
guessed.  See the ADR-043 addendum for the hardened per-part rating table.
"""

from __future__ import annotations

import argparse
import csv
import os
import re
import sys

# --- Exit codes -------------------------------------------------------------
EXIT_PASS = 0
EXIT_FAIL = 1
EXIT_CANNOT_VERIFY = 2

# Default mission minimum. Source: docs/RANGE-THROUGHPUT-PLAN.md line 122
# ("Cold soak (-60°C typical at altitude)") -- cited in ADR-043.
DEFAULT_MISSION_MIN_C = -60.0

# Known offenders ADR-043 identifies. If present in the BOM and genuinely
# out of range, they are reported in a dedicated section by name.
KNOWN_OFFENDERS = (
    ("LR2021 radio (U2)", re.compile(r"lora\s*2021|lr2021", re.I)),
    ("Supercapacitor bank (C_CAP / 2x3.3F)", re.compile(r"supercap|1f_5\.5v|1[.\s]?65f|3\.3f", re.I)),
)

DEFAULT_RATINGS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "bom_ratings.csv")


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "").strip()).lower()


def _to_float(v):
    if v is None:
        return None
    v = str(v).strip()
    if v == "":
        return None
    try:
        return float(v)
    except ValueError:
        return None


def load_ratings(path: str) -> dict:
    """key(lower) -> (rated_min_c, rated_max_c, source)."""
    if not path or not os.path.exists(path):
        return {}
    db = {}
    with open(path, newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            if not row:
                continue
            key = _norm(row.get("key", ""))
            if not key:
                continue
            db[key] = (
                _to_float(row.get("rated_min_c")),
                _to_float(row.get("rated_max_c")),
                (row.get("source") or "").strip(),
            )
    return db


def lookup_rating(db: dict, value: str, mpn: str):
    """Look up by mpn first, then value. Returns (min, max, source) or None."""
    for cand in (_norm(mpn), _norm(value)):
        if cand and cand in db:
            return db[cand]
    return None


def parse_pcb(path: str):
    """Return [(ref, value, footprint)] from a KiCad .kicad_pcb.

    Supports both modern `(property "Reference" "R1")` and legacy
    `(fp_text reference R1 ...)` forms.
    """
    t = open(path, encoding="utf-8", errors="replace").read()
    rows = []
    for m in re.finditer(r"\(footprint\s+\"([^\"]+)\"", t):
        start = m.start()
        depth = 0
        i = start
        while i < len(t):
            if t[i] == "(":
                depth += 1
            elif t[i] == ")":
                depth -= 1
                if depth == 0:
                    break
            i += 1
        block = t[start:i + 1]

        def field(name, legacy):
            mm = re.search(r'\(property\s+"%s"\s+"([^"]*)"' % name, block)
            if mm:
                return mm.group(1).strip()
            mm = re.search(r"\(fp_text\s+%s\s+(\S+)" % legacy, block)
            if mm:
                return mm.group(1).strip().strip('"')
            return ""

        ref = field("Reference", "reference")
        val = field("Value", "value")
        if ref and not ref.startswith("#"):
            rows.append((ref, val, m.group(1)))
    return rows


def _provenance_unverified(source: str) -> bool:
    s = (source or "").strip().upper()
    if s.startswith("TODO") or s.startswith("UNVERIFIED") or s == "":
        return True
    # An invented class rating ("... typical range") is a guess, not a document
    # citation, and must not silently drive a PASS/FAIL verdict (ADR-043).
    return bool(re.search(r"\bTYPICAL\b", s))


def check(items, mission_min_c: float, strict_provenance: bool):
    """items: list of dicts with ref, value, mpn, rated_min_c, source.

    Returns (worst_exit, results) where results is a per-part list of
    (ref, value, status, detail).
    """
    results = []
    any_fail = False
    any_cannot = False

    for it in items:
        ref = it.get("ref", "") or "?"
        value = it.get("value", "") or ""
        mpn = it.get("mpn", "") or ""
        rmin = it.get("rated_min_c")
        source = it.get("source", "") or ""

        if rmin is None:
            results.append((ref, value, EXIT_CANNOT_VERIFY,
                            "no rated minimum temperature data (fail-closed)"))
            any_cannot = True
            continue

        if strict_provenance and _provenance_unverified(source):
            results.append((ref, value, EXIT_CANNOT_VERIFY,
                            "rating present but provenance unverified (%s)" % (source or "none")))
            any_cannot = True
            continue

        if rmin <= mission_min_c:
            results.append((ref, value, EXIT_PASS,
                            "rated_min %.0fC <= mission_min %.0fC%s" % (
                                rmin, mission_min_c,
                                (" [src: %s]" % source) if source else "")))
        else:
            results.append((ref, value, EXIT_FAIL,
                            "rated_min %.0fC ABOVE mission_min %.0fC by %.0f K%s" % (
                                rmin, mission_min_c, rmin - mission_min_c,
                                (" [src: %s]" % source) if source else "")))
            any_fail = True

    if any_fail:
        return EXIT_FAIL, results
    if any_cannot:
        return EXIT_CANNOT_VERIFY, results
    return EXIT_PASS, results


def build_items(args):
    items = []
    if args.pcb:
        db = load_ratings(args.ratings)
        for ref, value, _fp in parse_pcb(args.pcb):
            rating = lookup_rating(db, value, "")
            if rating is None:
                items.append({"ref": ref, "value": value, "mpn": "", "rated_min_c": None, "source": ""})
            else:
                rmin, _rmax, src = rating
                items.append({"ref": ref, "value": value, "mpn": "", "rated_min_c": rmin, "source": src})
        return items

    db = load_ratings(args.ratings)
    with open(args.bom, newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            if not row or not any((v or "").strip() for v in row.values()):
                continue
            ref = row.get("ref", "")
            value = row.get("value", "") or ""
            mpn = row.get("mpn", "") or ""
            rmin = _to_float(row.get("rated_min_c"))
            source = row.get("source", "") or ""
            if rmin is None:
                rating = lookup_rating(db, value, mpn)
                if rating is not None:
                    rmin, _rmax, src = rating
                    source = source or src
            items.append({"ref": ref, "value": value, "mpn": mpn,
                          "rated_min_c": rmin, "source": source})
    return items


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Deterministic fail-closed BOM cold-temperature gate (ADR-043).")
    src = ap.add_mutually_exclusive_group(required=True)
    src.add_argument("--bom", help="BOM CSV to check")
    src.add_argument("--pcb", help="KiCad .kicad_pcb to derive the BOM from")
    ap.add_argument("--ratings", default=DEFAULT_RATINGS, help="ratings DB CSV (default: bundled bom_ratings.csv)")
    ap.add_argument("--mission-min", type=float, default=DEFAULT_MISSION_MIN_C,
                    help="mission minimum temperature in C (default -60)")
    ap.add_argument("--strict-provenance", action="store_true",
                    help="treat TODO/UNVERIFIED-sourced ratings as CANNOT-VERIFY")
    args = ap.parse_args(argv)

    try:
        items = build_items(args)
    except (OSError, ValueError) as exc:
        print("CANNOT-VERIFY: could not read input: %s" % exc)
        return EXIT_CANNOT_VERIFY

    if not items:
        print("CANNOT-VERIFY: no parts found in input (fail-closed).")
        return EXIT_CANNOT_VERIFY

    worst, results = check(items, args.mission_min, args.strict_provenance)

    fails = [r for r in results if r[2] == EXIT_FAIL]
    cannots = [r for r in results if r[2] == EXIT_CANNOT_VERIFY]

    print("ADR-043 BOM cold-temperature gate")
    print("mission minimum: %.0f C" % args.mission_min)
    print("parts checked:   %d" % len(items))
    print("")

    if fails:
        print("FAIL -- parts used below their rated minimum:")
        for ref, value, _s, detail in fails:
            print("  %-10s %-24s %s" % (ref, value, detail))
        print("")

    if cannots:
        print("CANNOT-VERIFY -- no (provenanced) temperature data, named:")
        for ref, value, _s, detail in cannots:
            print("  %-10s %-24s %s" % (ref, value, detail))
        print("")

    # Name the two known offenders ADR-043 identifies, when present.
    hits = []
    for label, pat in KNOWN_OFFENDERS:
        if any(pat.search((it.get("value") or "")) for it in items):
            hits.append(label)
    if hits:
        print("KNOWN OFFENDERS present (ADR-043): %s" % "; ".join(hits))
        print("")

    if worst == EXIT_PASS:
        print("RESULT: PASS (%d parts, all rated at or below %.0f C)" % (len(items), args.mission_min))
    elif worst == EXIT_FAIL:
        print("RESULT: FAIL (%d part(s) above mission minimum; %d cannot-verify)"
              % (len(fails), len(cannots)))
    else:
        print("RESULT: CANNOT-VERIFY (%d part(s) without temperature data)" % len(cannots))

    return worst


if __name__ == "__main__":
    sys.exit(main())
