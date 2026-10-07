# PROGRESS — Brief 5 re-dispatch (solar / pins / regulatory / cutdown)

Branch: `docs/solar-pin-regulatory` (off `adr/radioband-tdm` tip `8b46f68`).
Worktree: `/home/c03rad0r/worktrees/bf-solar-pin`.

- [x] Read brief + authority records (ADR-006, ADR-029, ADR-034, ADR-035, F33 pin plan,
      PINOUT_VERIFICATION.md, C3-SIGNOFF.md).
- [x] Established adr/radioband-tdm tip = `8b46f6873f815425acb7203da1d22685e954d404`
      (via `git ls-remote`, all three remotes agree).
- [x] Sourced solar constant 1361 W/m² (IAU B3 2015 / Kopp & Lean 2011).
- [x] Sourced ESP32-C3-WROOM-02 pinout + strapping (Espressif datasheet v1.7).
- [x] Sourced 433 MHz regulatory (ERC Rec 70-03 / LPD433, Germany 2008 cutoff).
- [x] Sourced cutdown mass (balloon-test-results.md, ~0.5 g/channel).
- [x] Computed all four number-sets; wrote docs/SOLAR-PIN-REGULATORY.md.
- [ ] Commit (explicit paths only) + push github then ngit sequentially + verify SHAs.
