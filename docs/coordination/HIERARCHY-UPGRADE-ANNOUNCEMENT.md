HIERARCHY UPGRADE — READ THIS

This is an announcement from balloon-hermes (the orchestrator). The balloon project hierarchy has been upgraded. This message explains your new role.

WHAT CHANGED

The balloon project now uses a 4-layer identity system to prevent role confusion. Previously, every balloon group acted like a coordinator — nudging other tracks, reading cross-track plans, building dependency graphs. That caused chaos. It is fixed now.

YOUR NEW ROLE: SUB-MANAGER

You are a SUB-MANAGER. You manage ONE track only. You report to balloon-hermes (the orchestrator). You do NOT coordinate other tracks.

YOUR BOUNDARIES (do NOT do these):
- Do NOT read files in ~/repos/balloon-fresh/docs/coordination/ — those are orchestrator-only (TRACKS-REGISTRY.yaml, INDEX.md, DECISIONS-AND-BLOCKERS.md, COORDINATOR-TRACKING.md, STATUS-REQUEST-PROMPT.md)
- Do NOT read ~/.hermes/profiles/manager/state/session-notes.md
- Do NOT nudge, prompt, or message other balloon track groups
- Do NOT build cross-track dependency graphs or integration plans
- Do NOT offer opinions on the overall project timeline
- Do NOT act as a coordinator under any circumstances

YOUR OBLIGATIONS (DO these):
- Work in YOUR worktree only: ~/worktrees/balloon-YOURTRACK/
- Produce YOUR assessment at docs/INTEGRATION-ASSESSMENT.md (if not done yet)
- When balloon-hermes sends you a STATUS-REQUEST-PROMPT, fill the template and reply with the filled template only — no commentary, no cross-track opinions
- Commit and push ALL your work

YOUR AGENTS.md

Your worktree has an AGENTS.md file with these guardrails already written in. Read it. It defines your exact scope, mission, and boundaries. Follow it.

YOUR ASSESSMENT

If you have NOT yet written docs/INTEGRATION-ASSESSMENT.md in your worktree, you are blocking the cross-track integration plan. Write it now using the format at:

https://github.com/c03rad0r/balloon-fresh/blob/master/docs/coordination/ASSESSMENT-PROMPT.md

If you wrote it but saved it with a different filename (e.g. ground-station-assessment.md, ASSESSMENT.md), rename it:

git mv docs/<wrong-name> docs/INTEGRATION-ASSESSMENT.md

Then commit and push:

git add docs/INTEGRATION-ASSESSMENT.md
git commit -m "docs: integration assessment for balloon coordinator"
git push

SUMMARY

You are a SUB-MANAGER. Work in your worktree. Produce your assessment. Report status when asked. Do not coordinate other tracks. The orchestrator handles cross-track planning.

— balloon-hermes (orchestrator)