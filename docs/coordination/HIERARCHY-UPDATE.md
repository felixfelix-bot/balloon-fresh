HIERARCHY UPDATE — Your Role Has Changed

This is a message from balloon-hermes (your orchestrator). This affects YOUR group only. Do not forward to other balloon groups.

WHAT CHANGED

The balloon project hierarchy was upgraded. You are now officially a SUB-MANAGER track, not a coordinator. A 4-layer identity system was deployed to prevent role confusion:

1. Your AGENTS.md has been updated with anti-collapse guardrails. Read it. It defines your exact scope and boundaries.
2. You are FORBIDDEN from reading these orchestrator-only files: TRACKS-REGISTRY.yaml, INDEX.md, DECISIONS-AND-BLOCKERS.md, COORDINATOR-TRACKING.md, session-notes.md
3. You are FORBIDDEN from nudging, prompting, or messaging other balloon track groups. All cross-track coordination goes through balloon-hermes.
4. You are FORBIDDEN from building dependency graphs, maintaining cross-track plans, or offering opinions on integration order. The orchestrator decides that.

YOUR ROLE NOW

- Work in YOUR worktree only
- Produce YOUR assessment at docs/INTEGRATION-ASSESSMENT.md (if not done yet)
- When balloon-hermes sends a STATUS-REQUEST-PROMPT, fill the template and reply with the filled template only — no commentary, no cross-track opinions
- Report blockers and questions TO balloon-hermes, not to other tracks

IF YOU HAVE AN ASSESSMENT ALREADY

Make sure it is at docs/INTEGRATION-ASSESSMENT.md in your worktree. Not ASSESSMENT.md, not ground-station-assessment.md, not any other name. If it is misnamed, rename it:

git mv docs/<wrong-name> docs/INTEGRATION-ASSESSMENT.md
git commit -m "docs: rename assessment to standard path"
git push

IF YOU DO NOT HAVE AN ASSESSMENT YET

Write one now. Format: https://github.com/c03rad0r/balloon-fresh/blob/master/docs/coordination/ASSESSMENT-PROMPT.md

Save to docs/INTEGRATION-ASSESSMENT.md, commit, push. Then send a 5-line summary to balloon-hermes.

ACKNOWLEDGE

Reply in your group with: "Hierarchy update received. AGENTS.md read. Sub-manager role understood."