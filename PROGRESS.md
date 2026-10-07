# PROGRESS — ADR-037 (v9 MCU = ESP32-S3; SKY66112 FEM omitted)

Branch: `adr/mcu-s3-no-fem` (worktree `/home/c03rad0r/worktrees/bf-adr-s3`)
Base: `8b46f6873f815425acb7203da1d22685e954d404` (observed tip of `adr/radioband-tdm`)

## Done
- [x] Verified next-free ADR number = 037 (034/035 on radioband-tdm; 036 on adr/energy-policy, other worker).
- [x] Ran link budget: RX power -102.6 dBm @ 300 km (EIRP 37 dBm, FSPL 149.6 dB).
      Margin +33.4 dB (LNA in, -136 dBm) / +21.4 dB (LNA out, -124 dBm). FEM not needed.
- [x] Wrote docs/adr/037-mcu-s3-no-fem.md.
- [x] Added pointers: ADR-001 (scope split), ADR-005 (superseded in part), ADR-006 (stale load list).
- [x] Re-verified SKY66112 evidence: v8h board of record 0 occurrences; v_c3_flight.kicad_sch has 2 "(opt)" placeholders; 19 docs mention it.

## Todo
- [ ] Commit + push github then ngit (sequential).
- [ ] Verify remote SHAs.
