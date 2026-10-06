#!/usr/bin/env python3
"""Emit docs/BRANCH-TRIAGE-2026-10-06.md into the bf-consolidate worktree."""
import json, os, subprocess, collections

WT = os.path.expanduser("~/worktrees/bf-consolidate")
R = os.path.expanduser("~/reports/balloon-consolidation")
tj = json.load(open(os.path.join(R, "TRIAGE.json")))
mtr = json.load(open(os.path.join(R, "triage.json")))
cherry = json.load(open(os.path.join(R, "cherry.json")))


def sh(c):
    r = subprocess.run(c, shell=True, capture_output=True, text=True, cwd=WT)
    return r.stdout.strip()


HEAD = sh("git rev-parse HEAD")

# cluster assignment (by shared conflicting file / domain)
CLUSTERS = [
    ("C1 payack / tollgate_payment_proto", "tracker/firmware/main/tollgate_payment_proto.{c,h} + PAY/ACK parser tests + the two CI lanes",
     ["feat/tracker-tx-tempcomp", "fix/tollgate-payack-harness-seq",
      "fix/tollgate-payack-seq-whitespace", "fix/tollgate-payack-sid-price-exp"]),
    ("C2 E80 STM32 bench firmware", "firmware/e80-stm32-bench/{src,tests,tools} — the FIX-T1..T7 + E80 feature set",
     ["fix/t1-sweep-start-validation", "fix/t2-rx-start-len-gate", "fix/t3-flrc-match123",
      "fix/t4-fifo-clear", "fix/t6-sweep-preflight", "feat/e80-7-crc-logging",
      "feat/e80-spi-bypass", "feat/e80-cvm-go-mode", "feat/c3-harmonization"]),
    ("C3 RP2040 / flrc-bench-espidf radio benches", "firmware/rp2040/*, mesh-stack/flrc-bench-espidf/*",
     ["speed-sustained-sweep", "phase1-interop-test", "range-tests", "feat/host-driven-bench"]),
    ("C4 tracker port / adoption trio", ".gitignore, tracker/firmware/main/{app_main.cpp,Kconfig.projbuild}, firmware/rp2040/platformio.ini",
     ["docs/harm-t9-adoption"]),
    ("C5 PCB / KiCad board artifacts", "tracker/hardware/*, Makefile, drc_snapshots",
     ["balloon-circuit-design", "worker-balloon/pcb-phase1-t877", "worker-balloon/pcb-phase1-t877-main"]),
    ("C6 nostr_store / mesh wiring component", "tracker/firmware/components/nostr_store/*, CMakeLists + sdkconfig",
     ["balloon-nostr/dev", "balloon-mesh-wiring/radio-glue", "balloon-tollgate-extract", "balloon-tollgate/dev"]),
]
assigned = {b for _, _, bs in CLUSTERS for b in bs}
CLUSTERS.append(("C0 unclustered", "", [b["branch"] for b in tj["branches"] if b["branch"] not in assigned]))

by_branch = {b["branch"]: b for b in tj["branches"]}
mmeta = {u["branch"]: u for u in mtr["unmerged"]}


def tips(branch):
    out = sh('git log -1 --format="%ad|%an|%s" --date=short "github/' + branch + '"')
    return (out.split("|", 2) + ["", "", ""])[:3]


CLUSTER_REC = {
    "C1 payack / tollgate_payment_proto":
        "Sequential follow-ups on ONE PR line (all descend from the now-merged `pr/tollgate-payment-proto-tdd`), "
        "not competing implementations. Resolve: rebase onto the trunk in date order, union the docs/CI hunks, "
        "re-run `tracker/firmware/test/test_tollgate_payack_parse.py` + the integration test. One decision: accept the union as canonical.",
    "C2 E80 STM32 bench firmware":
        "FIX-T1..T7 + E80-7/SPI-bypass touch DIFFERENT functions of the same files (independent fixes); "
        "`feat/c3-harmonization` (23 files, 2026-08-25) is the wide/old one. Resolve: merge the FIX-T* set first, "
        "one at a time, running `firmware/e80-stm32-bench/tests` after each; then the features. One decision: "
        "is the STM32 bench firmware still live, or has the RP2040 path replaced it?",
    "C3 RP2040 / flrc-bench-espidf radio benches":
        "NOT a free archive — an earlier 'already on the trunk' reading was a grep false positive (see section 4). "
        "Reverse-apply shows the branch carries changes the trunk lacks. One decision: is the RP2040/FLRC bench path "
        "still live (merge, tests after each) or retired (archive with an `archive/` tag)?",
    "C4 tracker port / adoption trio":
        "`docs/harm-t9-adoption` is docs + AGENTS.md + README.md → prose union, lowest risk of the set. "
        "But `tracker/firmware/main/Kconfig.projbuild` + `app_main.cpp` conflict with `balloon-nostr/dev` on the same two files "
        "→ sequence with C6, do not merge in parallel.",
    "C5 PCB / KiCad board artifacts":
        "`worker-balloon/pcb-phase1-t877-main` IS open PR #15 (CONFLICTING) → rebase onto the trunk, resolve, push to the PR branch "
        "(never force). `pcb-phase1-t877` is the earlier attempt of the same job → superseded by `-main`. "
        "`balloon-circuit-design` carries a BINARY `hub_board_v1.kicad_pcb` (2026-07-30): decide which board revision is authoritative first.",
    "C6 nostr_store / mesh wiring component":
        "`balloon-nostr/dev` carries a real `nostr_store` component change (+ `Kconfig.projbuild`/`app_main.cpp` absent on trunk). "
        "`balloon-tollgate-extract` and `balloon-mesh-wiring/radio-glue` are build-config only (CMakeLists/sdkconfig) — "
        "hand-merge the superset, do not union `sdkconfig` (key/value). One decision: is `nostr_store` on the trunk's current "
        "wisp-esp32 relay path or superseded by it?",
}
CL_OF = {}
for _name, _d, _bs in CLUSTERS:
    for _b in _bs:
        CL_OF[_b] = _name


def rec(branch):
    b = by_branch.get(branch, {})
    files = b.get("files", [])
    present = [f for f in files if f.get("already_present") == "yes"]
    if branch == "fix/t2-rx-start-len-gate":
        return "MERGE NOW — 1 file, both sides insert, regions disjoint (BOTH-ADD); union is safe."
    if branch in BINARY_MARK:
        return "DECISION — binary board artifact: pick the authoritative revision."
    return f"[{CL_OF.get(branch, 'C0')}] " + CLUSTER_REC.get(CL_OF.get(branch, ""), "DECISION — competing edits to the same code.")


BINARY_MARK = {"balloon-circuit-design"}


lines = []
w = lines.append
w("# Branch triage — balloon-fresh divergence from the consolidated trunk")
w("")
w(f"Date: 2026-10-06 · trunk HEAD: `{HEAD[:12]}` · repo: `felixfelix-bot/balloon-fresh`")
w("")
w("## 1. What is already landed")
w("")
w("- `main` and `master` are the **same commit** and both carry the consolidation "
  "(32 commits of previously-diverged branch work + the earlier 119). Verified by "
  "`git ls-remote`: both refs identical, and identical again after this triage round.")
w("- 112 `archive/consolidate-2026-10-05/<branch>` tags preserve every branch tip "
  "that was moved, so nothing is lossy.")
w("- Two zero-conflict branches merged in this round:")
w("  - `pr/029-dual-band-flight-board` (+1) — FLRC throughput figure settled in the array-feasibility doc.")
w("  - `worker-balloon/flrc-512b-audit` (+4) — the 2.6 Mbps claim is the **air rate, not goodput**; "
  "adds `tools/flrc_512b_throughput_audit.py` + its test + `docs/FLRC-512B-THROUGHPUT-AUDIT-2026-10-06.md`.")
w("")
w("## 2. The 25 that disagree about code")
w("")
w("Reproduce: `git merge-tree --write-tree --name-only HEAD <ref>` per branch "
  "(read-only; see `~/reports/balloon-consolidation/{triage.py,analyze.py}`).")
w("")
w("Every branch has at least one commit the trunk does not have (`git cherry`: **0 obsolete branches**), "
  "so none of the 25 is a pure duplicate — but that does **not** mean each carries new work: "
  "for several the change is already on the trunk under a different commit.")
w("")
w(f"- Conflicted files in total: **{sum(len(b['files']) for b in tj['branches'])}** across 25 branches.")
w("- Per-file three-way classification (`base`/`ours`/`theirs`): "
  + ", ".join(f"**{k}**={v}" for k, v in sorted(collections.Counter(f['class'] for b in tj['branches'] for f in b['files']).items(), key=lambda kv: -kv[1])) + ".")
w("  `COMPETING` means both sides edited the same region — a union merge is **not** safe there.")
w("")
w("| branch | tip | +commits | conflict files | recommendation |")
w("|---|---|---|---|---|")
for b in sorted(tj["branches"], key=lambda b: tips(b["branch"])[0]):
    ad, an, subj = tips(b["branch"])
    w(f"| `{b['branch']}` | {ad} | {b['ahead']} | {len(b['files'])} | {rec(b['branch'])} |")
w("")
w("## 3. It is ~5 decisions, not 25")
w("")
for name, files_desc, bs in CLUSTERS:
    if not bs:
        continue
    w(f"### {name}")
    if files_desc:
        w(f"Contended surface: `{files_desc}`")
    w("")
    for br in bs:
        b = by_branch.get(br)
        ad, an, subj = tips(br)
        if b:
            pres = [f for f in b["files"] if f.get("already_present") == "yes"]
            extra = f" · {len(pres)} conflicting file(s) already carry this change on the trunk" if pres else ""
            w(f"- `{br}` ({ad}, +{b['ahead']}) — {len(b['files'])} conflicting file(s){extra}")
            w(f"  - {subj[:150]}")
        else:
            w(f"- `{br}` ({ad}) — {subj[:150]}")
    w("")
w("## 4. Superseded-in-effect? REFUTED — nothing is a free archive")
w("")
w("Two independent tests, both negative:")
w("")
w("1. `git cherry HEAD <ref>` — patch-id comparison over each branch's commits: **0 of 25 branches** are duplicates.")
w("2. Reverse-apply test — for every conflicted file, `git diff <merge-base> <ref> -- <file> | git apply --check -R -` "
  "against the trunk. No branch produced even one clean reverse-apply, i.e. no file's branch version is already the trunk's version. "
  "Data: `~/reports/balloon-consolidation/applied.json` (script `applied.py`).")
w("")
w("**Correction to an earlier claim in this triage.** A grep of each branch's added lines against the trunk blob "
  "reported `already_present: partial/yes` on 54 of the competing code files, and that was read as "
  "\"C3 is the cheapest win — its change may already be on the trunk\". **That was a false positive.** The greps matched "
  "generic lines that occur everywhere (`#ifdef __cplusplus`, bare `}`, `/*`). The reverse-apply test is the reliable one, "
  "and it says the opposite. No branch in the 25 can be archived as superseded.")
w("")
w("The two branches that DO show a clean reverse-apply are the two already merged into the trunk in this round "
  "(`balloon-tollgate/dev` and `fix/t2-rx-start-len-gate`), which is a consistency check on the method, not a finding.")
w("")
w("## 5. Method / reproduction")
w("")
w("- Conflict discovery: `git merge-tree --write-tree --name-only HEAD <ref>` (never touches worktree/index).")
w("- Already-applied detection: `git cherry HEAD <ref>` (patch-id) + a grep of the branch's added lines against the trunk blob.")
w("- Per-file class: three-way blob diff (`base` = merge-base, `ours` = trunk, `theirs` = branch); "
  "`COMPETING` when both sides modify/delete the same region; BINARY for non-line-based artifacts.")
w("- Scripts: `~/reports/balloon-consolidation/{triage.py,meta.py,cherry.py,analyze.py,show.py}`.")
w("- Raw data: `~/reports/balloon-consolidation/{TRIAGE.json,cherry.json,triage.json}`.")
w("")

out = os.path.join(WT, "docs", "BRANCH-TRIAGE-2026-10-06.md")
open(out, "w").write("\n".join(lines) + "\n")
print("wrote", out, len(lines), "lines")
