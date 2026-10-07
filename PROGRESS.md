# PROGRESS — adr/cold-qualification-bom-gate

Deliverable-first: ADR-043 + deterministic BOM temperature gate + passing test.

- [cluster A] recon: worktree reused at /home/c03rad0r/worktrees/adr-cold-qualification-bom-gate (repo balloon-fresh). Cited facts locked to exact lines.
- [cluster A] BOM source: parsed 28 footprints+values from real PCBs v8i_krt_gnss.kicad_pcb and v8j_krt_ms5611.kicad_pcb (read-only, sibling worktree v8j-ms5611-reroute). Ignored legacy v_c3_flight.kicad_sch.
- [cluster B] wrote docs/adr/043-cold-qualification-heating.md (negative heating result + arithmetic + per-part table + two offenders).
- [cluster C] wrote tracker/hardware/tools/bom_temp_gate.py + test_bom_temp_gate.py + bom_ratings.csv + bom_v8i_gnss.csv.
- [cluster C] test result: see REPORT.md.
- [cluster D] push github -> ngit -> origin, each verified with git ls-remote.
