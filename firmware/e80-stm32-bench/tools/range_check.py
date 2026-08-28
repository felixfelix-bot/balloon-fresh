#!/usr/bin/env python3
"""range_check.py — post-stop gap check + selective re-send preset writer.

Run on the RX machine right after each stop:

    make range-check DIST=872m                      # latest session found
    make range-check DIST=872m SESSION=2608281225   # explicit session
    python3 tools/range_check.py --dist 872m \
        --configs ../../configs/per-stop/stop-872m.json

What it does:
  1. Finds the rx-log for the stop (logs/<session>/stop-<dist>/ new-style
     T0-tagged files first, then the legacy firmware/e80-stm32-bench/
     rx-log.csv cwd-quirk path).
  2. Filters harmonized PKT lines by session, counts received packets per
     config (best pass across replicates — matches the best-pass merge
     policy), and diffs against the preset.
  3. Prints one operator line, e.g.:
         872m: GAPS c4 MISS, c7 THIN 3/10
     or  872m: COMPLETE 9/9
  4. If there are gaps (MISS or THIN configs), writes a trimmed preset
     containing ONLY those configs (original idx values preserved) to
     configs/resend/resend-<dist>-<session>.json and prints paste-ready
     re-send commands with T0 = next 5-minute boundary.

Exit codes: 0 = complete, 1 = gaps found, 2 = usage/log errors.

The analysis layer never modifies raw logs.
"""
import argparse
import glob
import json
import os
import sys
import time

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)
import e80_bench_ctl as ctl  # noqa: E402  (reuse parse_pkt_line + preset loader)

DEFAULT_THIN_FRAC = 0.5


# ---------------------------------------------------------------------------
# Pure analysis functions (unit-tested in test_range_check.py)
# ---------------------------------------------------------------------------

def analyze_capture(cfgs, pkts, thin_frac=DEFAULT_THIN_FRAC):
    """Diff captured packets against the preset.

    pkts: list of parsed PKT dicts (harmonized, any session — filter first).

    Returns {config_idx: {"n_pkts": expected, "n_recv": best-pass count,
                          "per_replicate": {rep: count}, "status": ...}}
    where status is "OK" (n_recv >= thin_frac*n_pkts), "THIN"
    (0 < n_recv < thin_frac*n_pkts) or "MISS" (n_recv == 0 — config not in
    the capture at all, or fully lost). Best pass = max over replicates.
    """
    counts = {}
    for p in pkts:
        key = (int(p["config_id"]), int(p["replicate"]))
        counts[key] = counts.get(key, 0) + 1
    out = {}
    for c in cfgs:
        idx = int(c["idx"])
        per_rep = {rep: n for (ci, rep), n in counts.items() if ci == idx}
        n_recv = max(per_rep.values()) if per_rep else 0
        n_pkts = int(c["n_pkts"])
        if n_recv == 0:
            status = "MISS"
        elif n_recv < thin_frac * n_pkts:
            status = "THIN"
        else:
            status = "OK"
        out[idx] = {"n_pkts": n_pkts, "n_recv": n_recv,
                    "per_replicate": per_rep, "status": status}
    return out


def render_summary_line(dist, per_cfg):
    """One operator line: '<dist>: COMPLETE 9/9' or '<dist>: GAPS c4 MISS, c7 THIN 3/10'."""
    total = len(per_cfg)
    gaps = [i for i in sorted(per_cfg) if per_cfg[i]["status"] != "OK"]
    if not gaps:
        return "{}: COMPLETE {}/{}".format(dist, total, total)
    parts = []
    for i in gaps:
        s = per_cfg[i]
        if s["status"] == "MISS":
            parts.append("c{} MISS".format(i))
        else:
            parts.append("c{} THIN {}/{}".format(i, s["n_recv"], s["n_pkts"]))
    return "{}: GAPS {}".format(dist, ", ".join(parts))


def build_resend_preset(cfgs, per_cfg, dist, session):
    """Trimmed preset with ONLY the gap configs (idx preserved). None if complete."""
    gaps = [i for i in sorted(per_cfg) if per_cfg[i]["status"] != "OK"]
    if not gaps:
        return None
    keep = [c for c in cfgs if int(c["idx"]) in gaps]
    return {
        "name": "resend-{}-{}".format(dist, session),
        "description": ("Selective re-send for stop {} session {} — gap "
                        "configs only (MISS/THIN per range-check); idx values "
                        "match the original preset".format(dist, session)),
        "configs": keep,
    }


def next_t0(boundary_s=300, now=None):
    """Next 5-minute epoch boundary (same rule as the Makefile)."""
    now = int(now if now is not None else time.time())
    return ((now // boundary_s) + 1) * boundary_s


def format_resend_commands(resend_path, t0, dist):
    """Paste-ready TX + RX commands for the selective re-send."""
    sid = time.strftime("%y%m%d%H%M", time.gmtime(t0))
    cfgs_arg = "CONFIGS={}".format(resend_path)
    common = "DIST={} {} T0={} SESSION_ID={}".format(dist, cfgs_arg, t0, sid)
    return (
        "TX: make range-tx {}   # run FIRST, banner prints instantly".format(common),
        "RX: make range-rx {}   # arm BEFORE T0 (or immediately — late join "
        "skips to the next future config)".format(common),
    )


# ---------------------------------------------------------------------------
# Log discovery + parsing
# ---------------------------------------------------------------------------

def parse_rx_log(path):
    """Parse an rx-log file → (pkts, sessions_seen).

    Harmonized format: PKT,<23 fields> lines (STAT,/comment lines ignored).
    Legacy format (16-col CSV with header) parsed via csv.DictReader.
    """
    pkts = []
    sessions = set()
    with open(path, "r") as f:
        lines = [ln.rstrip("\n") for ln in f]
    data = [ln for ln in lines if not ln.startswith("#")]
    for ln in data:
        p = ctl.parse_pkt_line(ln)
        if p is not None:
            pkts.append(p)
            sessions.add(int(p["session_id"]))
    if not pkts and data and data[0].startswith("session,"):
        import csv
        import io
        for row in csv.DictReader(io.StringIO("\n".join(data))):
            try:
                pkts.append({
                    "session_id": int(row["session"]),
                    "config_id": int(row["config"]),
                    "replicate": int(row.get("replicate", 1)),
                })
                sessions.add(int(row["session"]))
            except (ValueError, KeyError, TypeError):
                continue
    return pkts, sessions


def find_rx_logs(dist, session, search_roots):
    """Locate candidate rx-log files for a stop, best-first.

    Order: explicit T0-tagged file for the session → any T0-tagged file for
    the stop (newest first) → legacy cwd-quirk rx-log.csv in tool dir.
    """
    cands = []
    for root in search_roots:
        if session:
            cands.extend(glob.glob(os.path.join(
                root, "logs", str(session), "stop-" + dist, "rx-log-*.csv")))
        cands.extend(glob.glob(os.path.join(
            root, "logs", "*", "stop-" + dist, "rx-log-*.csv")))
    cands = sorted(set(cands), key=os.path.getmtime, reverse=True)
    legacy = os.path.join(_HERE, "rx-log.csv")
    if os.path.isfile(legacy):
        cands.append(legacy)
    seen = set()
    uniq = []
    for c in cands:
        r = os.path.realpath(c)
        if r not in seen:
            seen.add(r)
            uniq.append(c)
    return uniq


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser(
        description="Post-stop gap check: diff rx-log vs preset, write "
                    "selective re-send preset + paste-ready commands")
    ap.add_argument("--dist", required=True,
                    help="stop distance label, e.g. 872m (log-dir lookup + labels)")
    ap.add_argument("--configs", required=True,
                    help="per-stop preset JSON (the one the stop ran with)")
    ap.add_argument("--session", type=int, default=None,
                    help="session id to filter PKT lines (default: highest "
                         "session found in the log)")
    ap.add_argument("--rx-log", default=None,
                    help="explicit rx-log path (skips discovery)")
    ap.add_argument("--thin-frac", type=float, default=DEFAULT_THIN_FRAC,
                    help="configs with fewer than this fraction of n_pkts "
                         "received are THIN (default 0.5)")
    ap.add_argument("--out-dir", default=None,
                    help="where to write the resend preset (default: "
                         "<repo-root>/configs/resend)")
    args = ap.parse_args()

    repo_root = os.path.abspath(os.path.join(_HERE, "..", "..", ".."))
    cfgs = ctl.load_config_preset(args.configs)

    # Locate the log
    if args.rx_log:
        path = args.rx_log
        if not os.path.isfile(path):
            sys.exit("ERROR: rx-log not found: {}".format(path))
    else:
        roots = [os.getcwd(), repo_root, os.path.abspath(os.path.join(_HERE, ".."))]
        cands = find_rx_logs(args.dist, args.session, roots)
        if not cands:
            sys.exit("ERROR: no rx-log found for stop {} (looked in logs/*/"
                     "stop-{}/ and {}). Pass --rx-log explicitly.".format(
                         args.dist, args.dist, os.path.join(_HERE, "rx-log.csv")))
        path = cands[0]
        if len(cands) > 1:
            print("note: multiple candidate logs, using newest: {}".format(path))

    pkts, sessions = parse_rx_log(path)
    if not pkts:
        sys.exit("ERROR: no PKT lines parsed from {} (wrong session or "
                 "empty/failed run?)".format(path))

    session = args.session
    if session is None:
        session = max(sessions)
        print("session: {} (auto — highest in {})".format(session, path))
    else:
        print("session: {} (explicit)".format(session))
    pkts = [p for p in pkts if int(p["session_id"]) == session]
    if not pkts:
        sys.exit("ERROR: session {} has no PKT lines in {} (sessions present: "
                 "{})".format(session, path, sorted(sessions)))

    per_cfg = analyze_capture(cfgs, pkts, thin_frac=args.thin_frac)
    line = render_summary_line(args.dist, per_cfg)
    print("")
    print(line)
    reps = max((len(v["per_replicate"]) for v in per_cfg.values()), default=1)
    print("")
    print("per-config (best pass{}):".format(" across {} replicates".format(reps) if reps > 1 else ""))
    for i in sorted(per_cfg):
        s = per_cfg[i]
        label = next((c["label"] for c in cfgs if int(c["idx"]) == i), "?")
        print("  c{:<2} {:<22} {:>3}/{}  {}".format(
            i, label, s["n_recv"], s["n_pkts"], s["status"]))
    print("")
    print("log: {}".format(path))

    preset = build_resend_preset(cfgs, per_cfg, args.dist, session)
    if preset is None:
        print("result: COMPLETE — no re-send needed.")
        return 0

    out_dir = args.out_dir or os.path.join(repo_root, "configs", "resend")
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, "resend-{}-{}.json".format(args.dist, session))
    with open(out_path, "w") as f:
        json.dump(preset, f, indent=2)
        f.write("\n")
    print("result: GAPS — re-send preset written: {}".format(out_path))

    t0 = next_t0()
    sid = time.strftime("%y%m%d%H%M", time.gmtime(t0))
    print("")
    print("Paste-ready selective re-send (T0={} session={}):".format(t0, sid))
    for cmd in format_resend_commands(
            os.path.relpath(out_path, repo_root), t0, args.dist):
        print("  " + cmd)
    return 1


if __name__ == "__main__":
    sys.exit(main())
