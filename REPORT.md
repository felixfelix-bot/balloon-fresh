# REPORT — ADR-043 Cold Qualification + BOM Temperature Gate

Branch: `adr/cold-qualification-bom-gate` · Repo: `/home/c03rad0r/repos/balloon-fresh` (remotes github, ngit, origin)
Worktree: `/home/c03rad0r/worktrees/adr-cold-qualification-bom-gate`

## Outcome

Both deliverables created, tested, and pushed. The negative heating result is
recorded with arithmetic; the real finding (parts used below their rated
minimum, nothing gating it) is closed with a deterministic fail-closed gate.

## Deliverables

| Deliverable | Path |
|---|---|
| ADR-043 | `docs/adr/043-cold-qualification-heating.md` |
| Gate (deterministic, no LLM) | `tracker/hardware/tools/bom_temp_gate.py` |
| Gate test | `tracker/hardware/tools/test_bom_temp_gate.py` |
| Seed ratings DB | `tracker/hardware/tools/bom_ratings.csv` |
| Seed BOM (from real PCB) | `tracker/hardware/tools/bom_v8i_gnss.csv` |
| Progress log | `PROGRESS.md` |

## BOM source

Parsed footprints + values from the real PCBs (28 footprints each, confirming
the task's count):
`.../v8j-ms5611-reroute/tracker/hardware/output/v8i_krt_gnss.kicad_pcb` and
`v8j_krt_ms5611.kicad_pcb`. The legacy single-component
`tracker/hardware/schematics/v_c3_flight.kicad_sch` was ignored.

## ADR-043 content

* **Mission minimum: -60 °C** — `docs/RANGE-THROUGHPUT-PLAN.md:122` (cold soak at altitude).
* **Two identified out-of-range parts** (both 20 K below rating, both with in-repo documentary evidence):
  * Supercapacitor bank — `-40 °C` — `docs/adr/006-supercapacitor-power.md:63`; agrees `docs/component-guide.md:84`.
  * LR2021 radio — `-40 °C` — `docs/assets/lr2021/README.md:137` (path absent in worktree; marked TODO(unverified)).
  * Supercap suitability was already open: `docs/FLIGHT-TEST-READINESS-2026-07-29.md:70`.
* **Energy arithmetic** (every estimate marked): P = ΔT/R_th; R_th ≈ 100 K/W (ESTIMATE); 55 K → ~0.5 W; usable bank = 14 J (ADR-006) → **~28 s**. Storage thermal mass 3 g × ~1 J/(g·K) (ESTIMATE) = 3 J/K → +20 K = **60 J ≈ 4× the whole budget**.
* **Per-component verdict**: supercap HURT; LR2021 HURT/unnecessary (cold lowers RF noise); solar array HURT/unnecessary (efficiency + Voc rise when cold, so 2.4 W is conservative); MS5611/BMP280 HURT — it senses AMBIENT pressure and self-heats its compensation sensor, so heating corrupts telemetered altitude; night deep-sleep draws µA so insulation buys almost nothing (insulation not recommended).
* **Decision**: heating rejected; remedy is part selection or accepted-and-characterised behaviour, never heating; nothing passes silently.
* **Per-part rated-minimum table** inline, source per row, `TODO(unverified)` where unsourced.

## Gate behaviour

Deterministic, stdlib only, no LLM. Exit **0 PASS / 1 FAIL / 2 CANNOT-VERIFY**.
A part with no temperature data → CANNOT-VERIFY **naming that part**, never a
silent pass; a FAIL outranks CANNOT-VERIFY. Input is a BOM CSV or a
`.kicad_pcb` (footprints+values looked up in the ratings DB). `--strict-provenance`
fails TODO/UNVERIFIED-sourced ratings closed. The two known offenders are named
when present.

Real run observed: `python3 bom_temp_gate.py --pcb <v8i_krt_gnss.kicad_pcb> --ratings bom_ratings.csv`
→ exit 1, `KNOWN OFFENDERS present (ADR-043): LR2021 radio (U2); Supercapacitor bank (C_CAP / 2x3.3F)`, and `CANNOT-VERIFY` naming the 2 DNP parts.

## Test evidence (real output)

```
python3 -m pytest tracker/hardware/tools/test_bom_temp_gate.py -q
11 passed in 1.47s
```
Standalone runner: `11 passed, 0 failed` (exit 0).
Covers: PASS, FAIL, CANNOT-VERIFY-not-silent-pass, FAIL-outranks-cannot-verify,
ratings lookup by value, empty BOM → CANNOT-VERIFY, missing file → CANNOT-VERIFY,
strict provenance, seed ratings flag both offenders, real-PCB gate = FAIL,
PCB parser finds 28 footprints.

## Push verification

github / ngit / origin refs verified with `git ls-remote` after sequential push
(ngit helper has no --atomic). All three observed at the SAME commit:

```
LOCAL  fcaf84d938a577038c8ad85298c983c991cd611f
github fcaf84d938a577038c8ad85298c983c991cd611f  refs/heads/adr/cold-qualification-bom-gate
ngit   fcaf84d938a577038c8ad85298c983c991cd611f  refs/heads/adr/cold-qualification-bom-gate
origin fcaf84d938a577038c8ad85298c983c991cd611f  refs/heads/adr/cold-qualification-bom-gate
```

ngit note: `Published 1 state event to 1/2 relays (failed: nos.lol)` — the
`relay.ngit.dev` relay accepted the branch; `nos.lol` was unreachable. The ref
reads back correct from the ngit remote, so the push is verifiably landed.
No force-push was used.
