#!/usr/bin/env python3
"""range_check.py — post-stop rx-log gap check + selective re-send preset.

Union of the two range-check implementations (superset — both feature sets):

v1 (main / worker-balloon/range-check):
  - STAT-row parsing with the bracket-safe ``per_ci_x1e6=[lo,hi]`` split
    (a comma inside brackets must not corrupt later fields).
  - LOGGING GAP verdict: zero STAT rows for the session means the rx
    LOGGER failed (STAT rows are emitted per config even when rx=0, so
    rx=0 STATs are DATA — RF death — never a logging gap; no resend file).
  - WARMUP_REPLICATES exclusion, per-config conditional: when a config's
    capture has more than WARMUP_REPLICATES distinct replicates, the
    first WARMUP_REPLICATES never count (multi-cycle warmup); a
    single-cycle (loop=1) or short capture (<= WARMUP_REPLICATES
    distinct replicates) counts ALL of its replicates.
  - Default per-stop preset lookup + VALID_DISTS error (exit 2).
  - v1-style renumbered resend ``configs/resend-<DIST>-s<SESSION>.json``
    + verbatim TX one-liner (``T0=+90`` relative form).

v2 (worker-balloon/range-check2):
  - Best-pass analysis across replicates (max, never pooled — matches the
    best-pass merge policy in merge_csvs.py) with a thin_frac threshold.
  - T0-tagged per-stop log discovery (logs/*/stop-<dist>/rx-log-*.csv,
    newest first) + legacy cwd-quirk fallback.
  - Session auto-detect (highest session id found in the log).
  - idx-preserved resend ``configs/resend/resend-<dist>-<session>.json``
    + paste-ready TX/RX re-send commands (T0 = next 5-minute boundary).

Usage (from firmware/e80-stm32-bench/, or via the root make proxy):

    make range-check DIST=50m                      # latest session found
    make range-check DIST=872m SESSION=2608281225  # explicit session

Exit codes: 0 = complete, 1 = gaps / logging gap, 2 = usage/log errors.
The analysis layer never modifies raw logs. No hardware, no serial.
"""

from __future__ import annotations

import argparse
import datetime
import glob
import json
import os
import re
import sys
import time

_TOOLS_DIR = os.path.dirname(os.path.abspath(__file__))
if _TOOLS_DIR not in sys.path:
    sys.path.insert(0, _TOOLS_DIR)

import e80_bench_ctl as ctl  # noqa: E402  (parse_pkt_line + preset loader)

# Multi-cycle warmup: when a config's capture has MORE than this many
# distinct replicates, the first this-many never count. Captures with
# this many or fewer (e.g. single-cycle loop=1 stops) count everything.
WARMUP_REPLICATES = 2

# Field TX board probe serial (TX laptop, walks with the operator).
TX_PROBE_SERIAL = "148757200D2D1425"

VALID_DISTS = ["50m", "100m", "218m", "436m", "872m", "1744m", "5km", "11km", "70km"]

DEFAULT_THIN_FRAC = 0.5


def default_repo_root():
    """Repo root three levels up from this file (.../firmware/e80-stm32-bench/tools/)."""
    return os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def normalize_dist(dist):
    """Bare numbers are meters: '100' -> '100m'; anything else passes through."""
    return dist + "m" if dist.isdigit() else dist


# ---------------------------------------------------------------------------
# rx-log parsing (harmonized PKT + STAT lines, no header; legacy CSV too)
# ---------------------------------------------------------------------------

_STAT_SPLIT_RE = re.compile(r",(?![^\[]*])")  # commas outside [...] brackets


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


def _parse_rx_log_full(path):
    """Parse an rx-log into (pkts, stats, sessions).

    PKT rows are parsed with e80_bench_ctl.parse_pkt_line (the same parser
    the merge/stitch tools use), STAT rows with parse_stat_row above.
    Harmonized format first; a header-only legacy file (16-col CSV) is
    parsed via csv.DictReader. Comment lines and noise are ignored. A
    missing file parses as empty (=> LOGGING GAP verdict upstream).
    """
    pkts, stats, sessions = [], [], set()
    if not path or not os.path.isfile(path):
        return pkts, stats, sessions
    with open(path, errors="replace") as f:
        lines = [ln.rstrip("\n") for ln in f]
    data = [ln for ln in lines if not ln.startswith("#")]
    for ln in data:
        s = ln.strip()
        if s.startswith("PKT,"):
            p = ctl.parse_pkt_line(s)
            if p is not None:
                pkts.append(p)
                try:
                    sessions.add(int(p["session_id"]))
                except (TypeError, ValueError):
                    pass
        elif s.startswith("STAT,"):
            st = parse_stat_row(s)
            if st is not None:
                stats.append(st)
    if not pkts and not stats and data and data[0].startswith("session,"):
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
    return pkts, stats, sessions


def parse_rx_log(path):
    """Parse an rx-log file -> (pkts, sessions).

    Harmonized format: PKT,<23 fields> lines (STAT,/comment lines ignored).
    Legacy format (16-col CSV with header) parsed via csv.DictReader.
    """
    pkts, _stats, sessions = _parse_rx_log_full(path)
    return pkts, sessions


# ---------------------------------------------------------------------------
# t0 cross-check (2026-08-28 incident hardening): the rx-log and tx-log of
# one stop must belong to the SAME launch. t0 is read from BOTH the
# filename tag (-t0<epoch>, TZ-safe) and the log header (t0=<iso>); any
# disagreement is a loud exit-2, not a silent wrong-session analysis.
# ---------------------------------------------------------------------------

_T0_FN_RE = re.compile(r"(?:^|[-_/])t0(\d{8,})")
_T0_ISO_FMTS = ("%Y-%m-%dT%H:%M:%S.%f", "%Y-%m-%dT%H:%M:%S",
                "%Y-%m-%d %H:%M:%S")


def t0_from_filename(path):
    """Epoch int from a '-t0<epoch>' tag in the log's basename, else from
    its parent session dir (s<session>-t0<epoch>). None when untagged."""
    parent = os.path.basename(os.path.dirname(os.path.abspath(path or "")))
    for part in (os.path.basename(path or ""), parent):
        m = _T0_FN_RE.search(part)
        if m:
            return int(m.group(1))
    return None


def t0_from_header(path):
    """Epoch int from the DISTRIBUTED_*_MODE 't0=<iso-or-epoch>' comment.

    Only the first DISTRIBUTED header line is consulted (the launch-time
    banner). None when absent, unreadable, or unparseable.
    """
    if not path or not os.path.isfile(path):
        return None
    try:
        with open(path, errors="replace") as f:
            for ln in f:
                if "DISTRIBUTED" not in ln or "t0=" not in ln:
                    continue
                m = re.search(r"t0=(\S+)", ln)
                if not m:
                    return None
                tok = m.group(1)
                try:
                    return int(tok)
                except ValueError:
                    pass
                for fmt in _T0_ISO_FMTS:
                    try:
                        return int(datetime.datetime.strptime(
                            tok, fmt).timestamp())
                    except ValueError:
                        continue
                return None
    except OSError:
        return None
    return None


def t0_sources(path):
    """[(label, epoch)] for every t0 we can read from one log file."""
    srcs = []
    base = os.path.basename(path or "") or str(path)
    fn = t0_from_filename(path)
    if fn is not None:
        srcs.append(("{}: filename -t0{}".format(base, fn), fn))
    hdr = t0_from_header(path)
    if hdr is not None:
        srcs.append(("{}: header t0= -> {}".format(base, hdr), hdr))
    return srcs


def check_t0_match(rx_path, tx_path):
    """All readable t0 sources of BOTH logs must agree.

    Returns (ok, message). ok=True message summarizes the agreed epoch;
    ok=False message is a loud multi-line T0 MISMATCH report naming every
    source (rx filename, rx header, tx filename, tx header).
    """
    srcs = [("rx " + lbl, t) for lbl, t in t0_sources(rx_path)]
    srcs += [("tx " + lbl, t) for lbl, t in t0_sources(tx_path)]
    epochs = sorted({t for _lbl, t in srcs})
    if len(epochs) > 1:
        lines = ["T0 MISMATCH — rx-log and tx-log disagree on the launch:"]
        for lbl, t in srcs:
            lines.append("  {:<44} t0={}".format(lbl, t))
        lines.append(
            "The rx and tx logs are NOT from the same launch (stale "
            "T0/SESSION shell var? copied the wrong tx-log?). Re-check "
            "SESSION/T0, or pass --tx-log with the matching tx-log.")
        return False, "\n".join(lines)
    if not epochs:
        return True, "no t0 tags found (filename/header) — nothing to check"
    return True, "t0={} agreed by {}".format(
        epochs[0], ", ".join(lbl for lbl, _t in srcs))


def find_sibling_tx_log(rx_path):
    """Newest tx-log*.csv next to the rx-log, else in its parent session
    dir. None when no tx-log candidate exists."""
    if not rx_path:
        return None
    d = os.path.dirname(os.path.abspath(rx_path))
    for base in (d, os.path.dirname(d)):
        cands = glob.glob(os.path.join(base, "tx-log*.csv"))
        if cands:
            return max(cands, key=os.path.getmtime)
    return None


def find_rx_logs(dist, session, search_roots):
    """Locate candidate rx-log files for a stop, best-first.

    Order: explicit T0-tagged files for the session -> any T0-tagged file
    for the stop (newest first) -> legacy cwd-quirk rx-log.csv in tool dir.
    Handles both the s<session>-t0<epoch> repo-root layout and the bare
    <session> layout.
    """
    cands = []
    for root in search_roots:
        if session:
            cands.extend(glob.glob(os.path.join(
                root, "logs", "s{}-t0*".format(session), "stop-" + dist,
                "rx-log-*.csv")))
            cands.extend(glob.glob(os.path.join(
                root, "logs", str(session), "stop-" + dist, "rx-log-*.csv")))
        cands.extend(glob.glob(os.path.join(
            root, "logs", "*", "stop-" + dist, "rx-log-*.csv")))
    cands = sorted(set(cands), key=os.path.getmtime, reverse=True)
    legacy = os.path.join(_TOOLS_DIR, "rx-log.csv")
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
# Coverage analysis (best pass across replicates, warmup-aware)
# ---------------------------------------------------------------------------

def analyze_capture(cfgs, pkts, thin_frac=DEFAULT_THIN_FRAC,
                    warmup_replicates=0):
    """Diff captured packets against the preset (BEST pass per config).

    pkts: list of parsed PKT dicts (harmonized or legacy — filter to one
    session first). Counting is per replicate with a CONDITIONAL warmup
    rule: when a config's capture has more than warmup_replicates distinct
    replicates (a multi-cycle run), the first warmup_replicates are
    excluded (warmups never count); when it has warmup_replicates or
    fewer distinct replicates (single-cycle loop=1 or a short capture)
    ALL of them count — there is nothing to warm up against. The BEST
    surviving replicate is the result — matching the best-pass merge
    policy (never pooled).

    Returns {config_idx: {"n_pkts": expected, "n_recv": best-pass count,
                          "per_replicate": {rep: count}, "status": ...}}
    where status is "OK" (n_recv >= thin_frac*n_pkts), "THIN"
    (0 < n_recv < thin_frac*n_pkts) or "MISS" (n_recv == 0).
    """
    counts = {}
    for p in pkts:
        key = (int(p["config_id"]), int(p["replicate"]))
        counts[key] = counts.get(key, 0) + 1
    out = {}
    for c in cfgs:
        idx = int(c["idx"])
        distinct = {rep for (ci, rep) in counts if ci == idx}
        if len(distinct) > warmup_replicates:
            # Multi-cycle run: the first warmup_replicates never count.
            per_rep = {rep: n for (ci, rep), n in counts.items()
                       if ci == idx and rep > warmup_replicates}
        else:
            # Single-cycle (loop=1) / short capture: nothing to warm up
            # against — count ALL replicates.
            per_rep = {rep: n for (ci, rep), n in counts.items()
                       if ci == idx}
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


def _session_matches(row_value, session):
    """Compare session ids as strings (int-normalized when numeric)."""
    a, b = str(row_value).strip(), str(session).strip()
    if a.isdigit() and b.isdigit():
        return int(a) == int(b)
    return a == b


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
# Re-send presets (both output forms)
# ---------------------------------------------------------------------------

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


def write_resend_preset(raw_cfgs, results, dist, session, repo_root):
    """Write configs/resend-<DIST>-s<SESSION>.json with ONLY MISS+THIN cfgs.

    raw_cfgs is the ORIGINAL preset's configs list (verbatim dicts, labels
    preserved); position semantics of load_config_preset renumber them for
    the new session (presets with explicit idx values keep their idx).
    Returns the path.
    """
    gapped = [raw_cfgs[r["idx"]] for r in results if r["status"] != "OK"]
    out = {
        "name": "resend-{}-s{}".format(dist, session),
        "description": ("Selective re-send for stop {} session {} — only "
                        "configs that came in MISS/THIN; labels preserved."
                        .format(dist, session)),
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
# main
# ---------------------------------------------------------------------------

def main(argv=None):
    ap = argparse.ArgumentParser(
        description="Post-stop gap check: diff rx-log vs preset, write "
                    "selective re-send presets + paste-ready commands")
    ap.add_argument("--dist", required=True,
                    help="stop distance, e.g. 50m / 1744m / 70km (bare = meters)")
    ap.add_argument("--session", default=None,
                    help="session id from the stop's SESSION_ID banner "
                         "(default: highest session found in the log)")
    ap.add_argument("--rx-log", default=None,
                    help="explicit rx-log path (skips discovery; a missing "
                         "file is a LOGGING GAP, not an error)")
    ap.add_argument("--tx-log", default=None,
                    help="explicit tx-log path for the t0 cross-check "
                         "(default: newest tx-log*.csv sibling of the "
                         "rx-log)")
    ap.add_argument("--configs", default=None,
                    help="preset path override (default: "
                         "<repo-root>/configs/per-stop/stop-<DIST>.json)")
    ap.add_argument("--thin-frac", type=float, default=DEFAULT_THIN_FRAC,
                    help="configs with fewer than this fraction of n_pkts "
                         "received are THIN (default 0.5)")
    ap.add_argument("--out-dir", default=None,
                    help="where to write the idx-preserved resend preset "
                         "(default: <repo-root>/configs/resend)")
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

    cfgs = ctl.load_config_preset(preset_path)
    with open(preset_path) as f:
        raw_preset = json.load(f)
    raw_cfgs = raw_preset["configs"]

    # Locate the log: explicit path (missing => empty => LOGGING GAP), else
    # discovery over the per-stop T0-tagged layout with legacy fallback.
    if args.rx_log:
        path = args.rx_log
    else:
        roots = [os.getcwd(), repo_root, os.path.abspath(os.path.join(_TOOLS_DIR, ".."))]
        cands = find_rx_logs(dist, args.session, roots)
        if not cands:
            sys.stderr.write(
                "ERROR: no rx-log found for stop {} (looked in logs/*/"
                "stop-{}/ and {}). Pass --rx-log explicitly.\n".format(
                    dist, dist, os.path.join(_TOOLS_DIR, "rx-log.csv")))
            return 2
        path = cands[0]
        if len(cands) > 1:
            print("note: multiple candidate logs, using newest: {}".format(path))

    # t0 cross-check (fail fast): the rx-log and its sibling/explicit
    # tx-log must belong to the SAME launch — filename -t0<epoch> tags and
    # DISTRIBUTED_*_MODE t0=<iso> headers must all agree.
    tx_path = args.tx_log or find_sibling_tx_log(path)
    if tx_path:
        ok, msg = check_t0_match(path, tx_path)
        if not ok:
            sys.stderr.write("ERROR: {}\n".format(msg))
            return 2
        print("t0 cross-check: OK ({})".format(msg))
    else:
        print("note: no tx-log found (sibling of {}) — t0 cross-check "
              "skipped".format(path))

    pkts, stats, sessions = _parse_rx_log_full(path)

    session = args.session
    if session is None:
        if sessions:
            session = str(max(sessions))
            print("session: {} (auto — highest in {})".format(session, path))
        else:
            session = ""
    else:
        print("session: {} (explicit)".format(session))

    stat_count = sum(
        1 for s in stats
        if _session_matches(s.get("session", ""), session)) if session else 0

    if stat_count == 0:
        # Logger problem: the rx side wrote no STAT rows for this session at
        # all (STAT lines are emitted per config even when rx=0, so zero
        # means the logger/logger path failed, not the radio).
        print("log: {}".format(path))
        print(verdict_line(dist, session, [], "LOGGING_GAP"))
        return 1

    pkts = [p for p in pkts if _session_matches(p["session_id"], session)]
    per_cfg = analyze_capture(cfgs, pkts, thin_frac=args.thin_frac,
                              warmup_replicates=WARMUP_REPLICATES)
    results = [{"idx": int(c["idx"]), "label": c["label"],
                "n_pkts": per_cfg[int(c["idx"])]["n_pkts"],
                "counted": per_cfg[int(c["idx"])]["n_recv"],
                "status": per_cfg[int(c["idx"])]["status"]}
               for c in cfgs]

    # v2-style operator output: one line + per-config table.
    print("")
    print(render_summary_line(dist, per_cfg))
    reps = max((len(v["per_replicate"]) for v in per_cfg.values()), default=1)
    print("")
    print("per-config (best pass{}):".format(
        " across {} replicates".format(reps) if reps > 1 else ""))
    for i in sorted(per_cfg):
        s = per_cfg[i]
        label = next((c["label"] for c in cfgs if int(c["idx"]) == i), "?")
        print("  c{:<2} {:<22} {:>3}/{}  {}".format(
            i, label, s["n_recv"], s["n_pkts"], s["status"]))
    print("")
    print("log: {}".format(path))

    if all(r["status"] == "OK" for r in results):
        print("result: COMPLETE — no re-send needed.")
        print(verdict_line(dist, session, results, "PASS"))
        return 0

    print(verdict_line(dist, session, results, "GAPS"))

    # v1 output: renumbered resend + verbatim TX one-liner.
    v1_path = write_resend_preset(raw_cfgs, results, dist, session, repo_root)
    labels = ", ".join(raw_cfgs[r["idx"]]["label"] for r in results
                       if r["status"] != "OK")
    print("resend: {} (labels: {})".format(
        os.path.relpath(v1_path, repo_root), labels))
    print("TX: " + tx_one_liner(dist, session))

    # v2 output: idx-preserved resend + paste-ready TX/RX pair.
    preset = build_resend_preset(cfgs, per_cfg, dist, session)
    out_dir = args.out_dir or os.path.join(repo_root, "configs", "resend")
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, "resend-{}-{}.json".format(dist, session))
    with open(out_path, "w") as f:
        json.dump(preset, f, indent=2)
        f.write("\n")
    print("resend (idx preserved): {}".format(
        os.path.relpath(out_path, repo_root)))

    t0 = next_t0()
    sid = time.strftime("%y%m%d%H%M", time.gmtime(t0))
    print("")
    print("Paste-ready selective re-send (T0={} session={}):".format(t0, sid))
    for cmd in format_resend_commands(
            os.path.relpath(out_path, repo_root), t0, dist):
        print("  " + cmd)
    return 1


if __name__ == "__main__":
    sys.exit(main())
