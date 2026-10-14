import os, subprocess, sys

WT = "/home/c08r4d0r/worktrees/v9-route"
GATE = os.path.join(WT, "tracker/hardware/verify_fab_package.py")

pairs = [
    ("tracker/hardware/wing_board/wing_board_v9.kicad_pcb",
     "tracker/hardware/output/gerbers_wing_v9"),
    ("tracker/hardware/wing_board/wing_board_v9.kicad_pcb",
     "tracker/hardware/output/gerbers_wing_v9_jlcpcb.zip"),
    ("tracker/hardware/output/v_c3_flight_v6.kicad_pcb",
     "tracker/hardware/output/gerbers_v_c3_final"),
    ("tracker/hardware/output/v2_adc_2layer.kicad_pcb",
     "tracker/hardware/output/gerbers_v2_2layer"),
]

for b, p in pairs:
    bp = os.path.join(WT, b)
    pp = os.path.join(WT, p)
    if not os.path.exists(bp):
        print(f"[SKIP: no board] {b}")
        continue
    if not os.path.exists(pp):
        print(f"[SKIP: no pkg  ] {p}")
        continue
    r = subprocess.run([sys.executable, GATE, bp, pp],
                       capture_output=True, text=True, timeout=300)
    v = "COHERENT" if r.returncode == 0 else "INCOHERENT"
    probs = [l.strip() for l in r.stdout.splitlines() if l.strip().startswith("- ")]
    print(f"[{v}] {p}")
    for x in probs:
        print("      ", x)
