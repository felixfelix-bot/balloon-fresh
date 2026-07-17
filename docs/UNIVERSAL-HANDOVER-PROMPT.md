# Universal Handover Prompt

**Purpose:** A single message you can paste into ANY Signal group in the project.
Each group reads it, finds their section by name, and knows exactly what to do.

**How to use:** Copy everything below the `---CUT---` line and paste it into your Signal group.
The message is self-contained — it works for all 10 workstreams + the coordinator.

---

# CUT HERE ---

## PROJECT WORKSTREAM INITIALIZATION — READ THIS FIRST

You are part of a multi-workstream engineering project. Each workstream has its own Signal group,
worktree, kanban board, and source repo. All workstreams report to a top-level coordinator.

**STEP 1 — IDENTIFY YOUR ROLE**

Read your Signal group name and find it in the table below. That is your workstream and role.

| Signal Group Name | WS # | Your Role |
|---|---|---|
| balloon-hermes | — | **TOP COORDINATOR.** You are NOT a single workstream. You coordinate ALL workstreams, resolve cross-workstream dependencies, and plan integration. You also manage WS3 (Balloon) radio link testing directly. |
| esp32-tollgate | WS1 | ESP32-S3 TollGate firmware — captive portal WiFi hotspot with Cashu, Nostr relay, mining |
| microfips | WS2 | microFIPS Mesh — Rust firmware for ESP32-C3, ESP-NOW mesh, Noise XK, Wirehair erasure coding |
| balloon | WS3 | Balloon/LR2021 — ESP32-C3 pico balloon tracker + mesh internet transport. Radio link baseline |
| balloon-nostr | WS3a | Balloon sub-track: Extract wisp-esp32 Nostr relay → port to ESP32-C3 |
| balloon-tollgate | WS3b | Balloon sub-track: Extract captive portal + Cashu → port to ESP32-C3 |
| balloon-pow | WS3c | Balloon sub-track: Extract sw_miner + stratum → evaluate C3 feasibility |
| balloon-fips | WS3d | Balloon sub-track: Add LR2021 LoRa transport to microfips protocol |
| balloon-blossom | WS3e | Balloon sub-track: Design + build ESP32 Blossom media server (BUD-01/02) |
| tollgate-module-basic-go | WS4 | TollGate Router/Backend — Go backend (:2121) + pytest router test automation |
| market | WS5 | Plebeian Market — Nostr-native marketplace, React + TanStack + Bun, Playwright e2e |
| continuum-agent | WS6a | Torii Continuum backend — Go agent, FIPS mesh, Noise handshake, Wirehair |
| continuum-ui | WS6b | Torii Continuum frontend — browser onboarding, KeyVault, Web Crypto + IndexedDB |
| tollgate-android | WS7 | TollGate Android — native Kotlin/Jetpack Compose + Rust core via UniFFI |
| configurationwizzard | WS8 | net4sats MVP — onboarding wizard (Go :8099), admin dashboard (Preact PWA) |
| devops-infra | WS9 | Infrastructure — z.ai proxy, burn prediction, rate limiting, monitoring, kanban |
| sovereign-shops | WS10 | Sovereign Shops — Nostr-native arbitrage business on Plebeian Market |

If your group name is **balloon-hermes**: You are the coordinator. All other groups report to you.
Integration decisions are yours. You sequence work across workstreams and resolve conflicts.

If your group name is **anything else**: You are an async sub-agent. You work independently in your
assigned worktree, maintain your kanban board, and report progress + blockers back to balloon-hermes.
When you complete a phase or hit a blocker, you write a handover doc and report to balloon-hermes
so they can plan integration.

**STEP 2 — READ THE MASTER INDEX**

This is the single source of truth for ALL repos, branches, remotes, worktrees, hardware, and
cross-workstream dependencies. Read it first:

```
https://raw.githubusercontent.com/c03rad0r/balloon-fresh/master/docs/WORKSTREAM-INDEX.md
```

GitHub view: `https://github.com/c03rad0r/balloon-fresh/blob/master/docs/WORKSTREAM-INDEX.md`

**STEP 3 — READ YOUR DETAILED HANDOVER DOC**

Each workstream has a self-contained handover document. A fresh LLM session can bootstrap from it
without any conversation history. Find yours:

| Your Workstream | Handover Doc Path |
|---|---|
| WS1 ESP32 TollGate | `~/coordination/handover-esp32-tollgate.md` |
| WS2 microFIPS | `~/coordination/handover-microfips.md` |
| WS3 Balloon/LR2021 | `~/coordination/handover-balloon.md` |
| WS4 TollGate Router | `~/coordination/handover-tollgate-router.md` |
| WS5 Plebeian Market | `~/coordination/handover-plebeian-market.md` |
| WS6 Torii Continuum | `~/coordination/handover-torii-continuum.md` |
| WS7 TollGate Android | `~/coordination/handover-tollgate-android.md` |
| WS8 net4sats | `~/coordination/handover-net4sats.md` |
| WS9 Infrastructure | `~/coordination/handover-infrastructure.md` |
| WS10 Sovereign Shops | `~/coordination/handover-sovereign-shops.md` |

Balloon sub-tracks also have handovers in the repo at `docs/coordination/handover-balloon-*.md`.

**STEP 4 — COORDINATOR AUTHORITY STATEMENT**

**balloon-hermes is the top-level coordination authority.** This means:

1. **Cross-workstream decisions** are made by balloon-hermes. If your work depends on another
   workstream's output, do NOT negotiate directly — escalate to balloon-hermes.
2. **Integration sequencing** is determined by balloon-hermes. Do not integrate work from other
   workstreams into yours without coordinator approval.
3. **balloon-hermes resolves conflicts** when two workstreams need the same resource (hardware board,
   API key, deploy target, shared component).
4. **All workstreams report to balloon-hermes.** Status, blockers, and handover docs go there.
5. **If balloon-hermes gives you an instruction, follow it.** If you disagree, state your reasoning
   once and defer. The coordinator has the full cross-workstream picture.

**STEP 5 — WORKTREE DISCIPLINE (MANDATORY, NO EXCEPTIONS)**

1. **ALL git work goes in `~/worktrees/ws-<name>/`** — your dedicated worktree with your dedicated branch.
   | Workstream | Worktree | Branch |
   |---|---|---|
   | WS1 ESP32 TollGate | `~/worktrees/ws-esp32-tollgate/` | `ws-esp32-tollgate` |
   | WS2 microFIPS | `~/worktrees/ws-microfips/` | `ws/microfips` |
   | WS3 Balloon | `~/worktrees/ws-balloon/` | `ws/balloon-lr2021` |
   | WS4 Router/Backend | `~/worktrees/ws-tollgate-router/` | `ws/tollgate-router` |
   | WS5 Market | `~/worktrees/ws-plebeian-market/` | `ws/plebeian-market` |
   | WS6 Torii | `~/worktrees/ws-torii-continuum/` | `ws/torii-continuum` |
   | WS7 Android | `~/worktrees/ws-tollgate-android/` | `ws/tollgate-android` |
   | WS8 net4sats | `~/worktrees/ws-net4sats/` | `ws-net4sats/mvp` |
   | WS9 Infrastructure | `~/worktrees/ws-infrastructure/` | `ws/infrastructure` |
   | WS10 Shops | `~/worktrees/ws-sovereign-shops/` | `ws/sovereign-shops` |

2. **NEVER use `/tmp`** — it is tmpfs (RAM-backed). Your work will be silently destroyed on reboot.
3. **NEVER work directly in the primary repo** (e.g., `~/repos/balloon-fresh/`) unless you ARE
   the coordinator doing integration work. Always use your worktree.
4. **Done = pushed.** Commit AND push every change before ending your session. Unpushed work does
   not exist. Shared/org repos → branch + PR. Your own repos → push to main/master.
5. **Conventional commits.** Atomic commits — one concern per commit.
6. **Verify hardware before flashing** — board ports change on every USB replug:
   ```bash
   esptool.py --port /dev/ttyACM0 chip_id  # verify BEFORE flashing
   ```

**STEP 6 — HOW TO REPORT BACK**

You are an async sub-agent. Report to balloon-hermes when:

- ✅ **You start:** Post your initial findings after reading the codebase.
- ✅ **You complete a phase:** Write a handover doc summarizing what you did, what works, what's next.
- ✅ **You hit a blocker:** Post the blocker + what you've tried + what you need.
- ✅ **You need a cross-workstream dependency:** Escalate — do NOT negotiate directly with another group.

**Report format (keep it concise):**
```
STATUS: [done | in-progress | blocked]
WORKSTREAM: [your WS name]
TASK: [what you worked on]
RESULT: [what happened]
NEXT: [what's next, or what you need]
KANBAN: [board slug + task ID if applicable]
```

**Handover doc format:** Self-contained markdown. A fresh LLM session with zero conversation history
should be able to pick up your work by reading ONLY the handover doc. Include:
- What the workstream is
- Current state (done / in-progress / blocked)
- Key files, repos, and branches
- Integration points with other workstreams
- Next steps

Write handover docs to `~/coordination/handover-<name>.md`.

**STEP 7 — SECURITY & PII RULES**

- **No secrets in public repos.** No nsec keys, no passwords, no API tokens, no Signal numbers,
  no real names of individuals. Use generic descriptors (e.g., "the upstream maintainer").
- **Secret-detection hooks** are installed on repos that have them. Do NOT bypass with
  `--no-verify` unless explicitly authorized.
- **Commit hygiene:** Review your diff before committing. If you see anything that looks like a
  credential, stop and scrub it.

**STEP 8 — BEGIN**

1. Read the master index: `https://raw.githubusercontent.com/c03rad0r/balloon-fresh/master/docs/WORKSTREAM-INDEX.md`
2. Read your handover doc: `~/coordination/handover-<name>.md`
3. `cd` to your worktree: `~/worktrees/ws-<name>/`
4. Check state: `git status && git log --oneline -5`
5. Check your kanban board: `hermes kanban --board <slug> list`
6. Start working on your next task.
7. Report your initial findings to balloon-hermes once you understand the codebase.

--- END ---
