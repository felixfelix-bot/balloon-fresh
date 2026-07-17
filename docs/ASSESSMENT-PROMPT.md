# Track Assessment Prompt — Integration Readiness

**Purpose:** Paste this into each balloon Signal group. Each group writes a structured
assessment of what they need before their work integrates into a final ESP32-C3 pico balloon.
Commit the assessment to their worktree. The coordinator reads all assessments and builds
the master integration plan.

---

# CUT HERE ---

## INTEGRATION ASSESSMENT — WRITE AND COMMIT THIS NOW

You've been digging into your track's codebase. Now write a structured assessment so the coordinator (balloon-hermes) can build a master integration plan across all tracks.

**Write a file called `INTEGRATION-ASSESSMENT.md` in your worktree root** (the `~/worktrees/balloon-<your-track>/` directory). Commit and push it.

Use this exact structure:

```markdown
# Integration Assessment — [Track Name]

## What Works Now
List concrete, tested things that are proven to work. Be specific — file paths, test results, hardware verified. No vague claims.

- [thing that works, with evidence]

## What Exists But Is Untested/Incomplete
Code that's there but hasn't been verified or is known-broken.

- [thing that exists, what's wrong/missing]

## What Does NOT Exist Yet
Things that need to be built from scratch for this track.

- [thing that needs building]

## Blockers Before ESP32-C3 Integration
What prevents this track's output from running on a final ESP32-C3 balloon node RIGHT NOW. Be honest and specific.

- [blocker]: [why it blocks, what's needed to unblock]

## Dependencies On Other Tracks
What you need from other balloon tracks before you can integrate.

- [dependency]: [which track, what you need from them]

## Minimal Viable Integration
What is the ABSOLUTE MINIMUM from your track needed for a first working balloon? Strip it to the bone. What can you cut and still be useful?

- Minimum: [what's truly required]
- Can defer: [what can wait until v2]

## Hardware Needed
What physical hardware does your track need to test? Be specific about boards, modules, SPI buses, GPIO pins.

- [hardware requirements]

## Decisions Needed From The Human
Surface anything that requires a decision from the operator (the human behind balloon-hermes). Do NOT bury decisions in code — list them explicitly. The coordinator collects these and presents them in one batch.

- DECISION: [what needs deciding] — [options if known] — [impact if delayed]

## User Blockers
Things only the human can resolve. Purchasing hardware, physically soldering boards, registering services, regulatory questions. Be specific about what's needed and why a machine can't do it.

- BLOCKER: [what] — [why it blocks this track] — [what the human needs to do]

## Estimated Effort
Rough estimate to reach minimal viable integration.

- [hours/days] for [scope]

## Flash/RAM Budget
If your component were running on ESP32-C3 (512KB SRAM, 4MB flash), how much would it consume? Estimate if unsure.

- Flash: [estimate]
- RAM: [estimate]
- Notes: [constraints, conflicts with other components]
```

**Rules:**
1. Be HONEST. If something is broken, say so. If something is untested, say so. The coordinator needs ground truth, not optimism.
2. Be SPECIFIC. "Nostr relay works" is useless. "wisp_relay WebSocket server handles NIP-01 REQ/CLOSE on port 4869, tested with 50 concurrent subscriptions on ESP32-S3, LittleFS storage 4MB partition verified" is useful.
3. Be MINIMAL. The goal is getting a balloon flying. What's the smallest useful piece you can deliver?
4. Think about ESP32-C3 constraints: 512KB SRAM (not 8MB PSRAM like the S3), 4MB flash typically, RISC-V single core. Your component MUST fit.

**Commit it:**
```bash
cd ~/worktrees/balloon-<your-track>/
# Write INTEGRATION-ASSESSMENT.md
git add INTEGRATION-ASSESSMENT.md
git commit -m "docs: integration readiness assessment"
git push
```

**Report to balloon-hermes when done.** Post a one-line summary: "Assessment committed: [track name], [X] blockers, [Y] dependencies, minimal viable = [one sentence]."

--- END ---
