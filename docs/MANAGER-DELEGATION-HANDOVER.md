# Manager Delegation Handover — 2026-07-25

## Purpose

This document explains what went wrong with the manager profile's context management during the balloon range test sessions, and proposes concrete changes to Hermes configuration to prevent recurrence.

## The Problem

The manager profile (balloon-hermes group) is configured as an **orchestrator** — its job is to coordinate, make design decisions, and delegate mechanical work to sub-managers.

In practice, the manager has been doing ALL mechanical work in its main thread:
- Reading firmware source files (each `read_file` = 500-2000 tokens)
- Patching firmware (each `patch` = tool call + diff output)
- Running builds (`pio run` = 2000+ tokens of output)
- Flashing boards (USB debugging, BOOTSEL, serial port scanning = 5000+ tokens)
- Reading serial output (capture logs = thousands of tokens)
- Git commit/push operations

Over a multi-hour session, this consumed 150K+ tokens of context on mechanical work. The result:
1. **Tool-call exhaustion** — manager hits the max tool-call iteration limit before completing tasks
2. **Context bloat** — each response takes longer as context grows, degrading quality
3. **Lost state** — when context gets compacted, important details from mechanical work are lost
4. **Slow responses** — 200K-token context means 2+ minute response times

## What Actually Works

The `delegate_task` tool gives sub-managers isolated contexts:
- Sub-manager gets fresh, small context (~5-20K tokens)
- ALL tool output stays in the sub-manager's context
- Only a summary (~200-500 tokens) returns to the manager
- The manager never sees the raw build output, serial data, or file contents

**Proven example**: A build task that would take the manager 10+ tool calls (read file, find error, patch, rebuild, repeat) was completed by a sub-manager in one dispatch. The sub-manager made 15 API calls, processed 183K input tokens, and returned a clean 200-word summary. The manager's context was untouched.

## What Needs to Change

### 1. SOUL.md — Add Hard Delegation Rule (ALREADY EXISTS but not enforced)

The SOUL.md already contains:
```
### HARD RULE: What MUST be delegated
| Action | Delegate TO | Tool |
|--------|-------------|------|
| Reading firmware source files > 20 lines | worker-balloon | kanban or delegate_task |
| Writing/patching code | worker-balloon | kanban or delegate_task |
| Running `pio run` builds | worker-balloon | kanban or delegate_task |
| Flashing boards (`pio upload`) | worker-balloon | kanban or delegate_task |
| Reading serial output > 5 lines | worker-balloon | kanban or delegate_task |
| Git commit + push | worker-balloon | kanban or delegate_task |
```

The rule EXISTS but the manager ignores it. This is a training problem — the LLM sees the task and does it directly instead of delegating.

### Proposed Fix: Self-Audit Trigger

Add to SOUL.md a self-audit checkpoint that the manager MUST run before every `terminal`, `patch`, or `read_file` call:

```
Before calling terminal/patch/read_file on firmware/code files:
  Ask: "Should a sub-manager be doing this?"
  If YES → delegate instead
  If you've made > 3 terminal/patch/read_file calls in a turn → STOP and delegate
```

The current rule says "> 5 calls" but that's too loose. By call 5, context is already polluted.

### 2. Kanban Board Setup for Range Tests

The range test project needs its own kanban board so tasks persist across sessions:

```bash
hermes kanban create --name "balloon-range-tests" \
  --worktree ~/worktrees/balloon-range-tests
```

Task categories:
- **Build**: compile firmware, fix errors
- **Flash**: BOOTSEL, UF2 copy, verify
- **Capture**: start serial capture, monitor, stop
- **Analyze**: parse logs, compute PER/BER/RSSI, generate plots
- **Review**: code review, sub-manager consensus
- **Document**: write handover docs, update wiki

Each task gets dispatched to a worker profile. The manager monitors the board and reviews results.

### 3. Worker Profile for Balloon Range Tests

Create `worker-balloon` profile:

```bash
hermes profile create worker-balloon \
  --model glm-5.2 \
  --toolsets terminal,file \
  --worktree ~/worktrees/balloon-range-tests
```

This profile:
- Has its own context window (never pollutes manager)
- Can run builds, flash boards, read serial
- Has board lock access (balloon-board-lock.py)
- Reports results back via kanban

### 4. Sub-Manager Git Workflow

Sub-managers work on their OWN worktree + branch copies. The git dance:

1. Manager creates kanban task with clear scope
2. Worker creates feature branch in own worktree (e.g. `worker-balloon/channel-sweep`)
3. Worker commits + pushes to their branch
4. Worker returns: "PR #X ready" or "commit Y on branch Z"
5. Manager reviews the summary
6. Manager merges feature branch → main (or asks worker to rebase)
7. Manager pushes main

Key: Workers NEVER touch main directly. Manager handles merge/rebase.

### 5. Dispatch Patterns

**Simple tasks (file lookup, build, flash)**: Use `delegate_task` with `model='glm-4.5-flash'`. 2-5 min, returns summary.

**Complex tasks (firmware changes, analysis)**: Use `delegate_task` with `model='glm-5.2'`. 5-10 min, returns detailed summary.

**Long tasks (>5 min)**: Use `delegate_task` with `background=true`. Manager keeps working, result re-enters conversation when done.

**Recurring tasks**: Use kanban board. Worker picks up, executes, reports.

**Parallel independent work**: Use `delegate_task` with `tasks` array (up to 3 concurrent).

### 6. What Stays in Manager Thread

The manager ONLY does:
- Architecture/design decisions (which frequencies, what protocol, what trade-offs)
- Creating tasks and defining scope for sub-managers
- Reviewing sub-manager summaries (go/no-go decisions)
- Operator interface (Felix's messages, status reports)
- Cross-track coordination
- Git merge/rebase choreography (reviewing diffs, deciding merge order)
- Sub-manager consensus review

### 7. Context Budget Management

Manager context budget breakdown (target):
- System prompt + memory: ~10K tokens (fixed)
- Conversation history: ~20K tokens
- Sub-manager summaries: ~5K tokens (just results, not raw data)
- **Available for decisions**: ~165K tokens

vs what happened:
- System prompt + memory: ~10K tokens
- Conversation history: ~20K tokens
- **Raw tool output (builds, serial, files)**: ~120K tokens
- Available for decisions: ~50K tokens (DANGEROUSLY LOW)

## Immediate Action Items

1. **Create kanban board** for balloon-range-tests project
2. **Verify worker-balloon profile exists** or create it
3. **Add self-audit rule** to SOUL.md (reduce threshold from 5→3 calls)
4. **Set up kanban tasks** for: flash boards, capture data, analyze, plot
5. **Create SDR handover doc** (delegate to sub-manager with simpler scope)
6. **Document the delegation workflow** in AGENTS.md for the range test worktree

## Current State (as of 2026-07-25 18:00 UTC)

- Firmware v4 with channel sweep: BUILT + COMMITTED (899db5e)
- Both TX+RX have: FLRC CR=3/4, phase reorder, 13 WiFi channels + 8 EU 868MHz sub-bands, 30s GPS grace
- TX board: USB CDC was dead, needs physical replug
- RX board: running old firmware, needs reflash
- SDR handover doc: NOT YET WRITTEN (2 sub-manager attempts timed out)
- Kanban board: NOT YET SET UP for range tests

## For the Hermes Setup Context Window

The person/context managing Hermes infrastructure should:
1. Set up the kanban board + worker profile described above
2. Verify the SOUL.md delegation rules are actually being loaded into the manager's system prompt
3. Consider adding a programmatic guard: if the manager profile makes >3 consecutive `terminal`/`read_file`/`patch` calls, inject a warning
4. Review whether the kanban dispatch skill (`kanban-worker-management`) is working and workers are picking up tasks
5. Consider a cron job that audits the manager's context usage and alerts if it's doing mechanical work
