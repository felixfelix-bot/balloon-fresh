# Hub Board v9 — Spatial Consult: unrouted-net decision (D1/D2/D3)

- **Date:** 2026-10-13
- **Model:** gpt-6-astra (openai_codex lane, internal-only)
- **Verdict:** CHANGES_REQUESTED
- **Artifacts reviewed:** /tmp/viz/FB.svg (F.Cu+B.Cu+Edge), /tmp/viz/In2.Cu.svg (+3V3 plane) — rasterized to PNG by visual_consult.py (fix 6b99ac77 / merge 197ccc06; Codex backend rejects image/svg+xml)
- **Board:** tracker/hardware/hub_board_v9_orderable.kicad_pcb @ 9f72e3f (branch feat/hub-routing-v9, worktree ~/worktrees/pcb-defects)

## Question put to the consultant

Two nets (/SX1280_DIO2, /SX1280_MISO, U4→U1, ~12 mm) are unroutable on the
current stackup — confirmed independently by FreeRouting (53 s, "cannot make
further progress") and agentee ("no path within the rules"). Candidates:
D1 (free a signal layer; D1-as-stated puts +3V3 between F.Cu and GND — unsound),
D1-corrected (In1.Cu stays GND, In2.Cu→signal, +3V3→B.Cu pours),
D2 (move U4 — illegal, RF geometry locked), D3 (accept unrouted).

## Consultant answer (verbatim excerpts)

1. **No hidden corridor:** "I do not see a credible legal corridor for both
   nets in the current F.Cu/B.Cu routing... A visually open region is not
   necessarily routable." Consistent with both routers' refusals.

2. **D1-corrected is sound:** "Spatially and electromagnetically much more
   defensible: F.Cu signal remains immediately referenced to a solid In1.Cu
   GND plane... avoids the major flaw in the original D1 proposal."
   **First verification: complete +3V3 connectivity after removing the In2.Cu
   plane** — all 14 F.Cu +3V3 pads on the B.Cu rail, every via/neck-down/branch
   checked, no isolated islands, zone refill + full DRC, then RF return-path
   inspection under F.Cu (In1.Cu must stay continuous under the RF routing),
   then fab stackup/impedance confirmation.

3. **D3 not defensible:** "An unrouted net is an open circuit, regardless of
   its length." Only acceptable as a temporary state followed by hand-routing
   + DRC verification.

4. **Recommendation:** D1-corrected, as a required re-layout, sequence:
   In2.Cu→signal; +3V3 to B.Cu pours/rails+vias; route the 2 nets on In2.Cu
   short+direct with ground-via support; refill zones; verify all 14 +3V3
   connections; connectivity/clearance/zone-isolation/unconnected checks;
   reinspect F.Cu RF vs In1.Cu; confirm stackup with fabricator.

**VERDICT: CHANGES_REQUESTED**

Full transcript: cobrador:/tmp/consult_final.txt (3598 bytes, 2026-10-13 13:31)
