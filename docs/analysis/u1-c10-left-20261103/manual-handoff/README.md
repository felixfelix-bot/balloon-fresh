# Frozen editable baseline — unpromoted experiment
This is the exact recovered baseline, NOT trial-03. Do not replace it with routing search outputs.
SHA256 board.kicad_pcb: 7be7bb4f12473156b0ceba5c722c0b840b885fb3eff873ce66fde364d66a8ee9
Paired board.kicad_pro and board.kicad_dru are original and must accompany the board.
KiCad 9.0.9 refill on an isolated copy leaves identical board bytes: native DRC 42 opens, 24 warnings, zero non-connectivity errors. MISO endpoint→U1.9 connected; C10.1→U1.2 and C10.2→U7.2 disconnected. NOT fab-ready.
Local footprint libraries and fp-lib-table included for opening; embedded board footprints remain authoritative. Library mismatch warnings are not silently fixed. Optional 3D models may be absent; 2D editing does not require them.

Constraints: preserve external MISO endpoint (8.75,41.25) and U1.9 (11.05,44.05), move only A/B routing left as needed; jointly solve C10 power and GND, no via-in-pad, no rule relaxation, no unjustified component movement. Original rule file contains legacy conditionless edge exemptions; preserve for comparison, not approval. Refill before DRC. No canonical merge.

```bash
git clone --branch experiment/u1-c10-left-20261103 --single-branch https://github.com/felixfelix-bot/balloon-fresh.git balloon-c10-manual
cd balloon-c10-manual
git switch -c manual/u1-c10-routing
pcbnew docs/analysis/u1-c10-left-20261103/manual-handoff/board.kicad_pcb
```
Use KiCad 9.x. In GUI route with X, drag with D, keep DRC violations disabled, refill with B then save. Commit your own branch; do not overwrite the baseline branch.
