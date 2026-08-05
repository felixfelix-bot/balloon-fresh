# PCB Model Selection Lessons Learned

**Date:** 2026-08-05
**Status:** ACTIVE — informs all future PCB work
**Related:** ADR-028, PCB-MASTER-EXECUTION-PLAN.md

---

## What Happened

We spent 8+ hours failing to produce a PCB. Root causes:

### 1. Model Was Down — Workers Ran Blind

- `kimi-k3:cloud` was quota-exhausted (503 error) for the entire session
- Every kanban task assigned to `worker-layout` (configured as kimi-k3:cloud) failed instantly
- Workers produced empty boards (0 footprints, 0 tracks) or fell back silently
- We reported "DRC clean, fabrication ready" on EMPTY boards because DRC finds 0 violations when there's nothing to check
- **We never verified the model was actually available before dispatching**

### 2. Wrong Model Assignment Assumption

- We assumed glm-5.2 "cannot do spatial work" after it produced 80+ PCB shorts
- We mandated kimi-k3:cloud for ALL PCB work
- Research shows: **GLM 5.2 is SUPERIOR to Kimi for PCB design tasks**
  - Schematics, netlists, pin mapping: GLM 5.2 wins
  - Mathematical coordinate calc, clearance enforcement: GLM 5.2 wins
  - Visual board inspection: Kimi wins (multimodal vision)
  - Raw gerber text output: Kimi wins

### 3. Wrong Approach, Not Wrong Model

- The 80+ shorts weren't because glm-5.2 "can't do spatial work"
- They happened because we asked it to route by raw spatial intuition
- GLM 5.2 is text/math-based, not visual — it needs mathematical constraints
- Without a DRC-protection system prompt, it generated code with overlapping coordinates
- **The fix is forcing mathematical coordinate calculation, not switching models**

### 4. No Model Health Check

- `curl -s http://localhost:9099/v1/models` lists kimi-k3:cloud as available even when it's 503
- Must actually TEST the model with a trivial request before dispatching workers
- `curl -s http://localhost:9099/v1/chat/completions -d '{"model":"kimi-k3:cloud",...}'`

---

## Correct Model Assignment

| Task | Best Model | Why |
|------|-----------|-----|
| Schematic design, netlists | GLM 5.2 | Mathematical rigor, complete pin mapping, 1M context for datasheets |
| PCB code generation (Python KiCad API) | GLM 5.2 | Constraint satisfaction, clearance math |
| DRC error prevention | GLM 5.2 | Thinks through constraints before writing code |
| Visual board inspection | Kimi K2.7 | Multimodal vision can "see" layout issues |
| Gerber text output validation | Kimi K2.7 | Better at large raw text consistency |

## Two-Stage Workflow (Optimal)

```
Stage 1: GLM 5.2 generates PCB code
  → DRC-protection system prompt forces mathematical coordinates
  → Complete pin mappings, clearance enforcement
  → Produces .kicad_pcb via Python API

Stage 2: Kimi K2.7 visually reviews (when available)
  → Render board layers as images
  → Upload for visual inspection
  → Catches layout issues GLM can't "see"
  → Cost: $4/M output (vs $15/M for K3)
```

## DRC-Protection System Prompt (MANDATORY)

Added to `worker-layout/SOUL.md`. Key rules:
1. 0.2mm minimum clearance between ALL nets — calculated mathematically
2. Same-layer traces never cross unless same net
3. Complete pin mappings — no abbreviations
4. Think-before-write: list critical nets + coordinates BEFORE generating code
5. Power planes (In1=GND, In2=3V3) instead of power traces

## Pre-Dispatch Checklist (MANDATORY)

Before dispatching ANY worker:

```bash
# 1. Test model is actually available
curl -s http://localhost:9099/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"model":"<model_name>","messages":[{"role":"user","content":"OK"}],"max_tokens":5}'
# Must return 200 with choices array, NOT {"error":"..."}

# 2. Verify task has quality gates
# 3. Verify worker SOUL.md has DRC-protection prompt
# 4. Verify expected API call count fits timeout budget
```

## Cost Comparison

| Model | Input $/M | Output $/M | PCB Suitability |
|-------|-----------|------------|-----------------|
| GLM 5.2 | $1.40 | $4.40 | Excellent (schematics, code, DRC) |
| Kimi K2.7 Code | $0.95 | $4.00 | Good (visual review, gerbers) |
| Kimi K3 | $3.00 | $15.00 | Best but 3.4× more expensive |
| DeepSeek V4 Pro | $0.44 | $0.87 | Budget alternative for code gen |
