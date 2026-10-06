#!/usr/bin/env python3
import subprocess, json, os, sys, tempfile, difflib

REPO = os.path.expanduser("~/worktrees/bf-consolidate")
HEAD = "f2a8629f81d85321fddf6255ce49066d53a227ea"  # pinned trunk (task-specified), NOT the moving worktree HEAD

BRANCHES = [
    ("feat/c3-harmonization", 2, 23),
    ("speed-sustained-sweep", 22, 10),
    ("balloon-nostr/dev", 5, 9),
    ("feat/e80-7-crc-logging", 1, 8),
    ("feat/e80-spi-bypass", 10, 8),
    ("feat/tracker-tx-tempcomp", 14, 8),
    ("fix/tollgate-payack-harness-seq", 5, 8),
    ("fix/tollgate-payack-sid-price-exp", 11, 8),
    ("docs/harm-t9-adoption", 16, 7),
    ("fix/tollgate-payack-seq-whitespace", 7, 7),
    ("phase1-interop-test", 8, 6),
    ("feat/host-driven-bench", 29, 5),
    ("range-tests", 15, 5),
    ("balloon-mesh-wiring/radio-glue", 7, 3),
    ("feat/e80-cvm-go-mode", 20, 3),
    ("fix/t1-sweep-start-validation", 2, 3),
    ("fix/t4-fifo-clear", 4, 3),
    ("worker-balloon/pcb-phase1-t877-main", 6, 3),
    ("balloon-tollgate-extract", 2, 2),
    ("fix/t3-flrc-match123", 2, 2),
    ("worker-balloon/pcb-phase1-t877", 3, 2),
    ("balloon-circuit-design", 3, 1),
    ("balloon-tollgate/dev", 11, 1),
    ("fix/t2-rx-start-len-gate", 2, 1),
    ("fix/t6-sweep-preflight", 4, 1),
]

BINARY_EXTS = {'.kicad_pcb', '.kicad_sch', '.kicad_pro', '.png', '.jpg', '.jpeg',
               '.pdf', '.bin', '.elf', '.zip', '.gz', '.lib', '.kicad_sym',
               '.kicad_mod', '.wav', '.mp3', '.ico', '.so', '.a', '.o'}

def sh(cmd):
    return subprocess.run(cmd, cwd=REPO, capture_output=True, text=True)

def git(*args):
    return sh(["git"] + list(args))

def get_conflicted_files(ref):
    r = git("merge-tree", "--write-tree", "--name-only", HEAD, ref)
    out = r.stdout
    lines = out.split("\n")
    files = []
    if not lines or not lines[0].strip():
        return files
    # line 0 = tree oid, then file names until blank line
    for ln in lines[1:]:
        if ln.strip() == "":
            break
        files.append(ln.rstrip())
    return files

def file_kind(path):
    p = path.lower()
    ext = os.path.splitext(p)[1]
    if ext in BINARY_EXTS:
        return "binary"
    if any(p.endswith(x) for x in ['.jsonl', '.db', '.sqlite', '.sqlite3']):
        # jsonl may be line-based; treat as binary-ish but check content later
        pass
    # config/build
    if any(x in p for x in ['CMakeLists', 'Makefile', 'platformio.ini', 'sdkconfig',
                             'Kconfig', 'CMake', '.json', '.yaml', '.yml', '.toml', '.cfg',
                             '.ini', 'requirements.txt', 'package.json', 'Cargo.toml',
                             'pyproject.toml']):
        return "build-config"
    if any(x in p for x in ['README', 'docs/', '.md', '.rst', 'CHANGELOG', 'LICENSE']):
        return "docs"
    if any(p.endswith(x) for x in ['.c', '.h', '.cpp', '.hpp', '.py', '.rs', '.go',
                                    '.js', '.ts', '.sh', '.cc', '.ino', '.s', '.S']):
        return "code"
    # default: treat jsonl as data/binary
    if p.endswith('.jsonl'):
        return "binary"
    return "code"

def get_blob(ref, path):
    r = git("rev-parse", "--verify", "-q", f"{ref}:{path}")
    if r.returncode != 0 or not r.stdout.strip():
        return None
    r2 = git("show", f"{ref}:{path}")
    if r2.returncode != 0:
        return None
    return r2.stdout

def classify(base_text, ours_text, theirs_text, path):
    # returns (class, already_present, evidence)
    if base_text is None and theirs_text is None:
        return ("COMPETING", "n/a", "both deleted")
    if base_text is None:
        # file added on both sides (base absent) -> likely competing unless identical
        if ours_text == theirs_text:
            return ("TRUNK-ONLY", "n/a", "identical add")
        return ("COMPETING", "n/a", "added on both sides, differ")
    if ours_text == theirs_text:
        return ("TRUNK-ONLY", "n/a", "identical content")
    if ours_text == base_text:
        return ("BRANCH-ONLY", "n/a", "trunk == base, take branch")
    if theirs_text == base_text:
        return ("TRUNK-ONLY", "n/a", "branch == base, keep trunk")
    # Both changed vs base. Now check disjoint insertions.
    ours_ins = inserted_regions(base_text, ours_text)
    theirs_ins = inserted_regions(base_text, theirs_text)
    # also detect deletions/modifications: any line in base missing from ours/theirs in changed hunks
    ours_del = deleted_lines(base_text, ours_text)
    theirs_del = deleted_lines(base_text, theirs_text)
    # For BOTH-ADD: both sides only insert (no deletions) AND inserted regions disjoint
    if ours_del == 0 and theirs_del == 0:
        if regions_disjoint(ours_ins, theirs_ins):
            return ("BOTH-ADD", "n/a", f"disjoint insertions ours={len(ours_ins)} theirs={len(theirs_ins)}")
        else:
            return ("COMPETING", "n/a", "insertions overlap")
    return ("COMPETING", "n/a", "modifications present")

def inserted_regions(base, new):
    """Return list of (start_line, added_lines) regions in 'new' vs 'base' using diff."""
    import difflib
    base_lines = base.splitlines()
    new_lines = new.splitlines()
    sm = difflib.SequenceMatcher(None, base_lines, new_lines)
    regions = []
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == "insert":
            regions.append((j1, j2, new_lines[j1:j2]))
        elif tag == "replace":
            # treat replace as deletion+insertion -> not pure insertion
            regions.append((j1, j2, new_lines[j1:j2]))
    return regions

def deleted_lines(base, new):
    import difflib
    base_lines = base.splitlines()
    new_lines = new.splitlines()
    sm = difflib.SequenceMatcher(None, base_lines, new_lines)
    d = 0
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == "delete" or tag == "replace":
            d += (i2 - i1)
    return d

def regions_disjoint(r1, r2):
    # r1/r2 = list of (j1, j2, lines). Disjoint if line ranges don't overlap.
    def spans(r):
        return [(a, b) for a, b, _ in r]
    for a1, a2 in spans(r1):
        for b1, b2 in spans(r2):
            if not (a2 <= b1 or b2 <= a1):
                return False
    return True

def already_present(base_text, ours_text, theirs_text):
    """For COMPETING code files: are the branch's added/changed lines already in trunk?"""
    if ours_text is None or theirs_text is None or base_text is None:
        return ("n/a", "")
    base_lines = base_text.splitlines()
    theirs_lines = theirs_text.splitlines()
    ours_lines = ours_text.splitlines()
    sm = difflib.SequenceMatcher(None, base_lines, theirs_lines)
    added = []
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag in ("insert", "replace"):
            added.extend(theirs_lines[j1:j2])
    added = [l for l in added if l.strip()]
    if not added:
        return ("n/a", "")
    ours_set = set(ours_lines)
    matched = []
    for l in added:
        # exact match
        if l in ours_set:
            matched.append(l)
        else:
            # token match: strip whitespace
            tok = l.strip()
            for o in ours_lines:
                if o.strip() == tok:
                    matched.append(l)
                    break
    if len(matched) == 0:
        return ("no", "")
    if len(matched) >= len(added):
        return ("yes", matched[0][:80] if matched else "")
    return ("partial", matched[0][:80] if matched else "")

def main():
    results = []
    clusters = {}
    expected_total = 0
    actual_total = 0
    for name, ahead, exp_conf in BRANCHES:
        ref = f"refs/remotes/github/{name}"
        files = get_conflicted_files(ref)
        actual_total += len(files)
        expected_total += exp_conf
        base = git("merge-base", HEAD, ref).stdout.strip()
        entries = []
        decisive = []
        for f in files:
            kind = file_kind(f)
            base_text = get_blob(base, f)
            ours_text = get_blob(HEAD, f)
            theirs_text = get_blob(ref, f)
            # binary check
            if kind == "binary":
                # binary: if one side == base, safe; else needs decision
                if ours_text == base_text:
                    cls = "BRANCH-ONLY"
                elif theirs_text == base_text:
                    cls = "TRUNK-ONLY"
                elif ours_text == theirs_text:
                    cls = "TRUNK-ONLY"
                else:
                    cls = "BINARY"
                entries.append({"path": f, "kind": kind, "class": cls,
                                "already_present": "n/a", "evidence": ""})
                clusters.setdefault(f, []).append(name)
                continue
            cls, ap, ev = classify(base_text, ours_text, theirs_text, f)
            # already_present only for COMPETING code files
            ap_val = "n/a"
            ev2 = ev
            if cls == "COMPETING" and kind == "code":
                ap_val, ev3 = already_present(base_text, ours_text, theirs_text)
                if ev3:
                    ev2 = ev3
            entries.append({"path": f, "kind": kind, "class": cls,
                            "already_present": ap_val, "evidence": ev2})
            clusters.setdefault(f, []).append(name)
            if cls in ("COMPETING", "BINARY"):
                decisive.append(f)
        # verdict
        classes = {e["class"] for e in entries}
        if classes <= {"TRUNK-ONLY", "BRANCH-ONLY", "BOTH-ADD"}:
            verdict = "MECHANICAL"
        elif classes <= {"TRUNK-ONLY", "BRANCH-ONLY", "BOTH-ADD", "COMPETING", "BINARY"} and any(c in ("COMPETING","BINARY") for c in classes):
            verdict = "DECISION" if not any(c in ("TRUNK-ONLY","BRANCH-ONLY","BOTH-ADD") for c in classes) else "MIXED"
        else:
            verdict = "MIXED"
        # refine: MIXED = has at least one mechanical and one decision
        has_mech = any(c in ("TRUNK-ONLY","BRANCH-ONLY","BOTH-ADD") for c in classes)
        has_dec = any(c in ("COMPETING","BINARY") for c in classes)
        if has_mech and has_dec:
            verdict = "MIXED"
        elif has_dec:
            verdict = "DECISION"
        else:
            verdict = "MECHANICAL"
        results.append({"branch": name, "ahead": ahead, "conflicts_total": len(files),
                        "files": entries, "verdict": verdict, "decisive_files": decisive})

    # clusters sorted by branch count desc
    clusters_sorted = {k: v for k, v in sorted(clusters.items(), key=lambda kv: -len(set(kv[1])))}

    out = {"branches": results, "clusters": clusters_sorted}
    with open(os.path.expanduser("~/reports/balloon-consolidation/TRIAGE.json"), "w") as fh:
        json.dump(out, fh, indent=2)
    print(f"branches={len(results)} files_total(actual)={actual_total} files_total(expected)={expected_total}")

if __name__ == "__main__":
    main()
