# PROGRESS — analysis/wing-fab-cost

Branch: `analysis/wing-fab-cost` (worktree `/home/c03rad0r/worktrees/bf-wingfab`, base `76dd04d`)
Lens: manufacturability, hand-assembly effort, order cost.

## Done
- [x] Worktree created at `76dd04d` (tip of `github/main`; local `main` is `8fa2202` — noted in the doc).
- [x] Read ADR-046, ADR-048, `docs/hardware-design.md`, `docs/POWER-BUDGET-V9-D2BE.md`,
      `docs/component-guide.md`, the wing gate record and the wing gerber `.gbrjob`.
- [x] LIVE JLCPCB capabilities read (`jlcpcb.com/capabilities/pcb-capabilities`).
- [x] LIVE JLCPCB quote for the repo's real wing zip driven with Playwright:
      2-layer 25×184 mm qty5 = **$6.40**; 4-layer = **$28.00** (measured toggles).
- [x] Joint counts computed for (a) 3 large, (b) 3 small, (c9/c12) parallel smalls, (d) mixed.
- [x] Layout feasibility computed against the 176×25 mm outline.
- [x] Slot/thickness tolerance stack computed from LIVE tolerances → worst-case gap 0.00 mm.
- [x] `docs/analysis/wing-fab-cost.md` written (status line: CONSULTANT ANALYSIS, not a decision record).
- [x] `REPORT.md` written.

## Not done / remaining
- [ ] LIVE 250 mm-outline quote (no 250 mm gerber uploaded) — recorded as TODO(unverified)/ESTIMATE.
- [ ] LIVE isolated qty-scaling curve (clicking the qty widget was unreliable; states with a
      changed qty came back with un-isolated option sets and are labelled indicative only).
- [ ] Hub-side quote — impossible: no v9 hub PCB exists on this branch.
- [ ] No DRC was run by this session; the gate PASS cited is the committed record in the worktree.

## Honesty
- Every number in the deliverable is labelled LIVE / COMPUTED / ESTIMATE / TODO(unverified).
- No price is presented as verified that was not read off a live page this session.
- Push SHAs (local / github / ngit) are recorded in REPORT.md after the pushes are observed.
