import os, subprocess
WT = os.path.expanduser("~/worktrees/bf-consolidate")


def sh(c):
    r = subprocess.run(c, shell=True, capture_output=True, text=True, cwd=WT)
    return (r.stdout or "").strip()


print("=== C2: is firmware/e80-stm32-bench live on the trunk? ===")
print("last 8 commits touching it:")
print(sh("git log -8 --format='  %ad %h %s' --date=short -- firmware/e80-stm32-bench"))
print("commits touching it since 2026-09-01 :",
      sh("git log --since=2026-09-01 --oneline -- firmware/e80-stm32-bench | wc -l"))
print("commits touching it since 2026-10-01 :",
      sh("git log --since=2026-10-01 --oneline -- firmware/e80-stm32-bench | wc -l"))
print("HEAD has the suite? tests:", sh("ls firmware/e80-stm32-bench/tests/*.c 2>/dev/null | wc -l"),
      "src:", sh("ls firmware/e80-stm32-bench/src/*.c 2>/dev/null | wc -l"))
print("referenced by current plans:")
print(sh("grep -rln 'e80-stm32-bench' --include='*.md' . 2>/dev/null | grep -v '^./firmware/e80-stm32-bench' | head -8"))

print()
print("=== C3 sanity (RP2040 path) ===")
print("last 5 commits touching firmware/rp2040 + mesh-stack/flrc-bench-espidf:")
print(sh("git log -5 --format='  %ad %h %s' --date=short -- firmware/rp2040 mesh-stack/flrc-bench-espidf"))
print("commits since 2026-09-01:", sh("git log --since=2026-09-01 --oneline -- firmware/rp2040 mesh-stack/flrc-bench-espidf | wc -l"))

print()
print("=== C5: PCB artifacts ===")
print("last 6 commits touching tracker/hardware:")
print(sh("git log -6 --format='  %ad %h %s' --date=short -- tracker/hardware"))
print("commits since 2026-09-01:", sh("git log --since=2026-09-01 --oneline -- tracker/hardware | wc -l"))
print("balloon-circuit-design (2026-07-30) adds/changes:")
ref = "github/balloon-circuit-design"
base = sh('git merge-base HEAD "%s"' % ref)
print(sh('git diff --stat "%s" "%s" | tail -6' % (base, ref)))
print("hub_board_v1.kicad_pcb on trunk:", sh("git cat-file -s HEAD:tracker/hardware/hub_board_v1.kicad_pcb 2>/dev/null") or "(absent)",
      "bytes; on that branch:", sh('git cat-file -s "%s:tracker/hardware/hub_board_v1.kicad_pcb" 2>/dev/null' % ref) or "(absent)", "bytes")
