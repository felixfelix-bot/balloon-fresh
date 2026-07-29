# Bootstrap — Balloon Pre-Stretching Track

**This message is for YOUR track group only (balloon-pre-stretching). Do not forward it to other balloon groups. The orchestrator (balloon-hermes) sends messages individually to each track. Your only job is to work in YOUR worktree and report back to balloon-hermes.**

---

You are the balloon-pre-stretching track group. This is a NEW track — you have not been bootstrapped yet.

## Your Role

You are a SUB-MANAGER in the balloon project hierarchy. You report to balloon-hermes (the orchestrator). You manage ONE track only: physical balloon preparation. You do NOT coordinate other tracks.

## Your Worktree

~/worktrees/balloon-pre-stretching/

Your AGENTS.md is already configured with anti-collapse guardrails. Read it.

## Your Mission

Pico balloon pre-stretching and preparation. You research best practices and ensure balloons are properly pressurized and stretched before flight. This is the physical preparation track — no firmware, no circuit design.

Focus areas:
- Balloon material research (Mylar/foil vs latex, DecoGlee 18" foil party balloons)
- Pre-stretching protocols (how long, what pressure, how many cycles)
- Inflation procedures (helium vs hydrogen, fill volume, purity requirements)
- Leak testing methodology
- Pressure-holding validation criteria
- Temperature cycling effects on balloon integrity

## Reference Documents (in your worktree under docs/)

- docs/balloon-pressure-test.md — existing pressure test plan
- docs/balloon-test-results.md — DecoGlee leak test data + community references
- docs/balloon-options-analysis.md — 7 balloon types compared with cost analysis
- docs/balloon-flight-lessons.md — lessons from 80+ community flights (6 practitioners)

## Physical Equipment Available

- 30x DecoGlee 18" foil party balloons (short test flights)
- Pressure sensor + pump (for balloon testing)
- MS300 jewelry scale (note: cannot weigh neodymium magnets due to magnetic interference)
- Digital calipers

## Your First Task

1. Read all four reference documents listed above
2. Research pico balloon best practices from the community (HB9HC, AE5GY, K6STS — references in balloon-flight-lessons.md)
3. Design a pre-stretching protocol: how many cycles, what pressure, duration, validation criteria
4. Design a leak test methodology that validates a balloon can hold sufficient pressure for the target flight duration
5. Write your findings as a structured protocol document

Save your work to docs/PRE-STRETCHING-PROTOCOL.md in your worktree.

## Then Write Your Assessment

After completing initial research, write docs/INTEGRATION-ASSESSMENT.md using the standard 10-section format:

https://github.com/c03rad0r/balloon-fresh/blob/master/docs/coordination/ASSESSMENT-PROMPT.md

Since this is a physical-prep track (not firmware), adapt the sections:
- "Blockers for ESP32-C3 Port" becomes "Blockers for Flight Readiness"
- "Dependencies on Other Tracks" — do you need circuit-design for weight constraints?
- "Shared Resources Needed" — physical equipment, helium supply, balloons

## When Done

git add docs/
git commit -m "docs: pre-stretching protocol and integration assessment"
git push

Then send a 5-line summary to balloon-hermes.