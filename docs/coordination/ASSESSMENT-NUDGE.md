# Assessment Nudge — Action Required

Your integration assessment has not been received at the correct location. The coordinator checks for exactly one file:

**docs/INTEGRATION-ASSESSMENT.md**

in your worktree. No other filename counts.

## If you already wrote an assessment

It may be saved with the wrong filename. Common mistakes:

- `ground-station-assessment.md` — rename it:
  `git mv docs/ground-station-assessment.md docs/INTEGRATION-ASSESSMENT.md`
- `ASSESSMENT.md` or `assessment.md` — rename it:
  `git mv docs/ASSESSMENT.md docs/INTEGRATION-ASSESSMENT.md`
- Written in a chat message but never saved to file — save it now to `docs/INTEGRATION-ASSESSMENT.md`

## If you haven't written it yet

The full format and instructions are at:

https://github.com/c03rad0r/balloon-fresh/blob/master/docs/coordination/ASSESSMENT-PROMPT.md

10 sections required:

1. What Works Right Now (note platform for each item)
2. What Exists But Is Untested
3. What Does NOT Exist Yet
4. Blockers for ESP32-C3 Port (4MB flash, 400KB RAM, single-core, no PSRAM — be specific)
5. Estimated Effort (hours / days / weeks)
6. Dependencies on Other Tracks
7. Shared Resources Needed
8. Integration Checklist (numbered)
9. Key Risks
10. Questions for the Coordinator

## Once your file is at docs/INTEGRATION-ASSESSMENT.md

```
git add docs/INTEGRATION-ASSESSMENT.md
git commit -m "docs: integration assessment for balloon coordinator"
git push
```

Then send a 5-line summary to balloon-hermes.

You are blocking the cross-track integration plan. All tracks must submit before the critical path analysis can begin.