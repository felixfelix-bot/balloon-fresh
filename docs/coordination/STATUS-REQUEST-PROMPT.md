# STATUS REQUEST — Balloon Track Status Pull

Copy this prompt into each balloon Signal group. Tracks must write their status
to their worktree and reply with the filled template only.

---

## STATUS REQUEST

This is a status pull from the coordinator (balloon-hermes). You are receiving
this because the orchestrator needs your current track status to update the
master integration timeline.

### BOUNDARIES

- This message is for YOUR track only. Do NOT forward to other balloon groups.
- Do NOT message other tracks or ask them for their status.
- Do NOT offer opinions on the overall project timeline or integration order.
- Your only external duty is to fill this template and report back.

### INSTRUCTIONS

1. Check YOUR worktree: `git log --oneline -5` in `~/worktrees/balloon-YOURTRACK/`
2. Check YOUR kanban board if you have one (run `hermes kanban --board <slug> ls` if applicable)
3. Check YOUR current blockers — things that stop YOU from progressing
4. Fill the template below. Do NOT add intro/outro text. Do NOT add commentary.
5. Save the filled template to `docs/STATUS-balloon-YOURTRACK.md` in your worktree
6. Commit and push
7. Reply in THIS Signal group with the filled template only

### MANDATORY RESPONSE TEMPLATE

Copy and fill this exact template. Do not change the keys. Do not add fields.

```
### STATUS REPORT: balloon-YOURTRACK
- Current Phase: [assessment / execution / blocked / done]
- Kanban Telemetry: [X] tasks done / [Y] total (or "no board")
- Last Commit: [short hash + one-line message]
- Immediate Blockers: [List blockers or "None"]
- Dependencies Waiting On: [List track names or "None"]
- Next 3 Deliverables: [Item 1, Item 2, Item 3]
- Estimated Integration Readiness: [YYYY-MM-DD or "unknown"]
- Critical Output: [Core deliverable you will hand to the orchestrator]
- Shared Resources Needed: [Hardware/board names or "None"]
- Questions for Orchestrator: [List or "None"]
```

### RULES

- If data is missing, write "unknown" or leave the field empty. Do NOT invent data.
- Do NOT report on other tracks' progress. You do not have visibility into them.
- Do NOT suggest changes to the integration order. The orchestrator decides that.
- Do NOT add free-form text before or after the template.
- Keep it factual. The orchestrator ingests this as raw telemetry data.