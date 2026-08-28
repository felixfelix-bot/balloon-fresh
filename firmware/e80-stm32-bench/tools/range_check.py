#!/usr/bin/env python3
"""range_check.py — post-stop rx-log coverage verdict + selective re-send preset.

Field tool for the Friday range sweep. After a stop's session completes, check
the RX log for coverage gaps and — if any config came in missing or thin —
write a re-send preset containing ONLY those configs, plus the copy-paste
TX command to run it.

Usage (from firmware/e80-stm32-bench/, or via the root make proxy):

    make range-check DIST=50m SESSION=2608281130 [RX_LOG=rx-log.csv]

Decision procedure (approved design):
  - Rows for cfg i = rx-log rows with session == SESSION and config == i.
  - counted = PKT rows with replicate >= WARMUP_REPLICATES + 1 (the first 2
    replicates are warmups and never count).
  - MISS  = no counted rows; THIN = counted < n_pkts; otherwise OK.
  - PASS iff every config is OK (exit 0). Any MISS/THIN = GAPS (exit 1).
  - Zero STAT rows for the session = LOGGING GAP verdict (the rx logger
    itself failed — no re-send file is written). STAT rows with rx=0 mean
    the radio heard nothing (RF death) — that is DATA, not a logging gap.

The rx-log format is the harmonized one written by e80_bench_ctl run_rx_mode
(HarmonizedRxLogWriter): ``PKT,<23 fields>`` and ``STAT,role=RX,...`` lines,
no header, ``#`` comments allowed. This tool parses exactly that format.

On GAPS it writes ``configs/resend-<DIST>-s<SESSION>.json`` (schema-compatible
with load_config_preset; configs are renumbered 0..N-1 for the new session,
labels preserved) and prints the TX-side one-liner:

    make range-tx CONFIGS=configs/resend-<DIST>-s<SESSION>.json T0=+90 \
        PROBE=148757200D2D1425 PORT=<from detect>

No hardware, no serial — safe to run any time.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys

_TOOLS_DIR = os.path.dirname(os.path.abspath(__file__))
if _TOOLS_DIR not in sys.path:
    sys.path.insert(0, _TOOLS_DIR)

from e80_bench_ctl import load_config_preset, parse_pkt_line  # noqa: E402

# First WARMUP_REPLICATES replicates never count toward coverage.
WARMUP_REPLICATES = 2

# Field TX board probe serial (TX laptop, walks with the operator).
TX_PROBE_SERIAL = "148757200D2D1425"

VALID_DISTS = ["50m", "100m", "218m", "436m", "872m", "1744m", "5km", "11km", "70km"]


def default_repo_root():
    """Repo root four levels up from this file (.../firmware/e80-stm32-bench/tools/)."""
    return os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def normalize_dist(dist):
    """Bare numbers are meters: '100' -> '100m'; anything else passes through."""
    return dist + "m" if dist.isdigit() else dist


# ---------------------------------------------------------------------------
# rx-log parsing (harmonized PKT + STAT lines, no header)
# ---------------------------------------------------------------------------

_STAT_SPLIT_RE = re.compile(r",(?![^\[]*\])")  # commas outside [...] brackets


def parse_stat_row(line):
    """Parse a ``STAT,role=RX,...,session=N,config=N,replicate=N,...`` line.

    The ``per_ci_x1e6=[lo,hi]`` field contains a comma inside brackets, so a
    naive split(',') would corrupt the fields after it — split on commas that
    are not inside a bracketed value instead.

    Returns a dict of key->string, or None if the line is not a STAT line.
    """
    if not line or not line.strip().startswith("STAT,"):
        return None
    parts = _STAT_SPLIT_RE.split(line.strip())
    fields = {}
    for tok in parts[1:]:
        if "=" in tok:
            k, v = tok.split("=", 1)
            fields[k.strip()] = v.strip()
    return fields


def parse_rx_log(path):
    """Parse an rx-log into ([pkt dicts], [stat dicts]).

    PKT rows are parsed with e80_bench_ctl.parse_pkt_line (the same parser
    the merge/stitch tools use). Comment lines and noise are ignored. A
    missing file parses as empty (=> LOGGING GAP verdict upstream).
    """
    pkts, stats = [], []
    if not path or not os.path.isfile(path):
        return pkts, stats
    with open(path, errors="replace") as f:
        for line in f:
            line = line.strip()
            if line.startswith("PKT,"):
                p = parse_pkt_line(line)
                if p is not None:
                    pkts.append(p)
            elif line.startswith("STAT,"):
                s = parse_stat_row(line)
                if s is not None:
                    stats.append(s)
    return pkts, stats


# ---------------------------------------------------------------------------
# Coverage analysis
# ---------------------------------------------------------------------------

def _session_matches(row_value, session):
    """Compare session ids as strings (int-normalized when numeric)."""
    return str(row_value).strip() == str(session).strip()


def analyze(cfgs, pkts, stats, session):
    """Return (per-config results, session STAT row count).

    Per config: counted = PKT rows with session==SESSION, config==idx and
    replicate > WARMUP_REPLICATES. Status: MISS / THIN / OK.
    """
    stat_rows = [s for s in stats
                 if _session_matches(s.get("session", ""), session)]
    results = []
    for c in cfgs:
        counted = sum(
            1 for p in pkts
            if _session_matches(p["session_id"], session)
            and p["config_id"] == c["idx"]
            and p["replicate"] > WARMUP_REPLICATES)
        n = c["n_pkts"]
        if counted == 0:
            status = "MISS"
        elif counted < n:
            status = "THIN"
        else:
            status = "OK"
        results.append({
            "idx": c["idx"], "label": c["label"],
            "n_pkts": n, "counted": counted, "status": status,
        })
    return results, len(stat_rows)


def verdict_line(dist, session, results, kind, stat_count=0):
    """One-line Signal verdict, e.g.
    ``50m s2608281130: GAPS c0:MISS c3:THIN 3/10 (8/10 clean)``."""
    if kind == "LOGGING_GAP":
        return ("{} s{}: LOGGING GAP (0 STAT rows for session — rx logger "
                "problem, not RF; no resend file)".format(dist, session))
    clean = sum(1 for r in results if r["status"] == "OK")
    total = len(results)
    if kind == "PASS":
        return "{} s{}: PASS ({}/{} clean)".format(dist, session, clean, total)
    parts = []
    for r in results:
        if r["status"] == "OK":
            continue
        if r["status"] == "THIN":
            parts.append("c{}:THIN {}/{}".format(r["idx"], r["counted"], r["n_pkts"]))
        else:
            parts.append("c{}:MISS".format(r["idx"]))
    return "{} s{}: GAPS {} ({}/{} clean)".format(
        dist, session, " ".join(parts), clean, total)


# ---------------------------------------------------------------------------
# Re-send preset
# ---------------------------------------------------------------------------

def write_resend_preset(raw_cfgs, results, dist, session, repo_root):
    """Write configs/resend-<DIST>-s<SESSION>.json with ONLY MISS+THIN cfgs.

    raw_cfgs is the ORIGINAL preset's configs list (verbatim dicts, labels
    preserved); the re-send renumbers them 0..N-1 via load_config_preset
    position semantics for the new session. Returns the path.
    """
    gapped = [raw_cfgs[r["idx"]] for r in results if r["status"] != "OK"]
    out = {
        "name": "resend-{}-s{}".format(dist, session),
        "description": ("Selective re-send for stop {} session {} — only "
                        "configs that came in MISS/THIN; renumbered 0..{} "
                        "in the new session, labels preserved.".format(
                            dist, session, len(gapped) - 1)),
        "configs": gapped,
    }
    out_dir = os.path.join(repo_root, "configs")
    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, "resend-{}-s{}.json".format(dist, session))
    with open(path, "w") as f:
        json.dump(out, f, indent=2)
        f.write("\n")
    return path


def tx_one_liner(dist, session):
    return ("make range-tx CONFIGS=configs/resend-{}-s{}.json T0=+90 "
            "PROBE={} PORT=<from detect>".format(dist, session, TX_PROBE_SERIAL))


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------

def main(argv=None):
    ap = argparse.ArgumentParser(
        description="Post-stop rx-log coverage verdict + selective re-send preset")
    ap.add_argument("--dist", required=True,
                    help="stop distance, e.g. 50m / 1744m / 70km (bare = meters)")
    ap.add_argument("--session", required=True,
                    help="session id from the stop's SESSION_ID banner")
    ap.add_argument("--rx-log", default="rx-log.csv",
                    help="rx log path (default: rx-log.csv, as written by make rx)")
    ap.add_argument("--configs", default=None,
                    help="preset path override (default: configs/per-stop/stop-<DIST>.json)")
    ap.add_argument("--repo-root", default=None,
                    help="repo root for preset lookup + resend output (default: derived)")
    args = ap.parse_args(argv)

    dist = normalize_dist(args.dist)
    repo_root = args.repo_root or default_repo_root()

    preset_path = args.configs or os.path.join(
        repo_root, "configs", "per-stop", "stop-{}.json".format(dist))
    if not os.path.isfile(preset_path):
        sys.stderr.write(
            "ERROR: preset not found: {}\nValid DIST values: {}\n".format(
                preset_path, ", ".join(VALID_DISTS)))
        return 2

    cfgs = load_config_preset(preset_path)
    with open(preset_path) as f:
        raw_preset = json.load(f)
    raw_cfgs = raw_preset["configs"]

    pkts, stats = parse_rx_log(args.rx_log)
    results, stat_count = analyze(cfgs, pkts, stats, args.session)

    if stat_count == 0:
        # Logger problem: the rx side wrote no STAT rows for this session at
        # all (STAT lines are emitted per config even when rx=0, so zero
        # means the logger/logger path failed, not the radio).
        print(verdict_line(dist, args.session, results, "LOGGING_GAP"))
        return 1

    if all(r["status"] == "OK" for r in results):
        print(verdict_line(dist, args.session, results, "PASS"))
        return 0

    print(verdict_line(dist, args.session, results, "GAPS"))
    path = write_resend_preset(raw_cfgs, results, dist, args.session, repo_root)
    labels = ", ".join(raw_cfgs[r["idx"]]["label"] for r in results
                       if r["status"] != "OK")
    print("resend: {} (cfgs renumbered 0..{} in the new session; labels: {})"
          .format(os.path.relpath(path, repo_root),
                  sum(1 for r in results if r["status"] != "OK") - 1, labels))
    print("TX: " + tx_one_liner(dist, args.session))
    return 1


if __name__ == "__main__":
    sys.exit(main())
