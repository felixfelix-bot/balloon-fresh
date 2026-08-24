# TASK DELEGATION — Orchestrator → Sub-Manager

Copy this prompt into a balloon sub-manager Signal group to PUSH a task downward.
This is the complement to STATUS-REQUEST-PROMPT.md (which PULLS status upward).

---

## TASK DELEGATION

This is a task from the orchestrator (balloon-hermes). You are receiving this
because the orchestrator has identified work that falls within your track's scope.

### BOUNDARIES

- This task is for YOUR track only. Do NOT forward to other balloon groups.
- If any part of this task is outside your scope, say so — do not silently expand.
- Route cross-track dependencies back to the orchestrator via ESCALATION.

### INSTRUCTIONS

1. Read the task, context, and deliverable below.
2. If anything is unclear, reply with QUESTIONS immediately — do not guess.
3. Execute the task within your worktree scope.
4. Report results using the RESPONSE FORMAT below.
5. If blocked, reply immediately with BLOCKERS — do not wait for a status pull.

### TASK TEMPLATE

```
### TASK: [verb] [what]
### CONTEXT: [why this is needed, what the orchestrator knows]
### DELIVERABLE: [concrete output expected]
### PRIORITY: [blocking / normal / background]
### DEADLINE: [if any, or "none"]
```

### RESPONSE FORMAT

Reply with this format. No intro/outro text.

```
### TASK RESULT: balloon-YOURTRACK
- Task: [echo the task title]
- Status: [done / in-progress / blocked / rejected-out-of-scope]
- Result: [what you did, found, or produced]
- Artifacts: [files changed, commits, hashes — or "none"]
- Blockers: [what stops you, or "none"]
- Questions: [for orchestrator, or "none"]
- Time Spent: [estimate]
```

### RULES

- If the task is outside your scope, REJECT it: status=rejected-out-of-scope.
- Do NOT expand your scope without orchestrator approval.
- Do NOT coordinate with other tracks to complete this task — escalate dependencies.
- If you need hardware that's locked, say so in BLOCKERS.
- Commit and push any code changes before reporting done.
