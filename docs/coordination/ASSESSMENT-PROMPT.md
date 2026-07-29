# ASSESSMENT REQUEST — Balloon Integration Readiness

Copy this prompt into each balloon Signal group. Ask them to write their assessment and save it to their worktree as docs/INTEGRATION-ASSESSMENT.md.

---

## ASSESSMENT REQUEST

You have now reviewed your codebase and understand what exists. Write a single markdown document called `docs/INTEGRATION-ASSESSMENT.md` in your worktree. Commit and push it. Then send a summary to balloon-hermes.

This assessment is for the coordinator (balloon-hermes) to build a high-level integration plan. Be specific and honest. Use this exact format:

```
# Integration Assessment — [TRACK NAME]

## Date
[Today's date]

## What Works Right Now
List what is tested and proven. Only include things you have actually verified or can see from code review are functional. For each item note the platform (ESP32-S3, ESP32-C3, host-only, etc).

## What Exists But Is Untested
Code that is present but has not been verified by you in this session.

## What Does NOT Exist Yet
Features or components that need to be written from scratch for balloon integration.

## Blockers for ESP32-C3 Port
Specific things that prevent this from running on ESP32-C3 (4MB flash, 400KB RAM, single-core, no PSRAM). Be precise: which component exceeds limits, by how much.

## Estimated Effort
For each remaining work item, estimate: hours / days / weeks. If uncertain, say so.

## Dependencies on Other Tracks
Does your track need output from another balloon track before it can proceed? List each dependency.

## Shared Resources Needed
Do you need physical hardware (ESP32-S3 boards, ESP32-C3 boards, LR2021 modules) that other tracks also need? Which ones.

## Integration Checklist
What must be true for your component to be ready for integration into the final balloon firmware? Number each item. This is what balloon-hermes will track.

## Key Risks
What could derail this track or force a redesign.

## Questions for the Coordinator
Anything you need balloon-hermes to decide or clarify.
```

Save this as `docs/INTEGRATION-ASSESSMENT.md` in your worktree. Commit and push. Then send a 5-line summary of your key findings to balloon-hermes.

balloon-hermes will read all assessments and produce a cross-track integration plan with critical path analysis and a prioritized roadmap to first flight.
