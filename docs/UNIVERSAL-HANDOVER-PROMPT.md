# Universal Handover Prompt — Balloon Project

**Purpose:** A single message to paste into ANY balloon-related Signal group.
Each group reads it, finds their track by name, and knows exactly what to do.

**How to use:** Copy everything below the `---CUT---` line and paste it into your Signal group.
The message is self-contained — it works for all 7 balloon tracks + the coordinator.

GitHub: https://github.com/c03rad0r/balloon-fresh/blob/master/docs/UNIVERSAL-HANDOVER-PROMPT.md

---

# CUT HERE ---

## BALLOON PROJECT — TRACK INITIALIZATION — READ THIS FIRST

You are part of the Balloon Project — solar-powered pico balloon nodes with ESP32-C3 + LR2021 LoRa radios that form a mesh internet transport network. Each track has its own Signal group, worktree, and source code. All tracks report to a top-level coordinator.

**STEP 1 — IDENTIFY YOUR TRACK**

Read your Signal group name and find it in the table below.

| Signal Group | Track | Your Job |
|---|---|---|
| balloon-hermes | — | **COORDINATOR.** You track all balloon tracks, resolve cross-track dependencies, plan integration. You also handle Track 1 (radio baseline). |
| balloon-nostr | Track 2 | Extract wisp-esp32 Nostr relay → port to ESP32-C3. NIP-01 WebSocket server, LittleFS storage, subscription manager, Schnorr validation. |
| balloon-tollgate | Track 3 | Extract captive portal + Cashu + DNS from tollgate-esp32 → port to ESP32-C3. WiFi AP, payment validation, firewall. |
| balloon-pow | Track 4 | Extract sw_miner + stratum_client from tollgate-esp32 → evaluate mining feasibility on ESP32-C3. SHA256 PoW, Stratum v1 protocol. |
| balloon-fips | Track 5 | Add LR2021 LoRa transport to microfips mesh protocol. Noise XK encryption, Wirehair erasure coding, balloon-to-balloon mesh. |
| balloon-blossom | Track 6 | Design + build Blossom media server (BUD-01/02) on ESP32. Greenfield — no existing code. Serves media over captive portal WiFi. |
| balloon-range-tests | Track 7 | Outdoor distance testing: 10m, 25m, 50m, 100m. FLRC + LoRa modes. Packet loss vs distance. Uses RP2040 + LR2021 hardware. |
| balloon-speed-tests | Track 8 | Throughput optimization: FLRC 2600 kbps target. SPI tuning, PIO/DMA, packet size sweeps. RP2040 + LR2021 hardware. |

If your group name is **balloon-hermes**: You are the coordinator. All other balloon tracks report to you. You sequence integration, resolve hardware conflicts (shared boards, shared SPI buses), and maintain the master plan to get balloons flying.

If your group name is **anything else**: You are an async sub-agent. You work independently in your assigned worktree, maintain your code, and report progress + blockers back to balloon-hermes.

**STEP 2 — READ YOUR HANDOVER DOC**

Each track has a detailed, self-contained handover document. A fresh LLM session with zero conversation history can bootstrap from it. Read yours:

| Track | Handover Doc (local) | Handover Doc (GitHub) |
|---|---|---|
| All tracks | `~/repos/balloon-fresh/docs/WORKSTREAM-INDEX.md` | [WORKSTREAM-INDEX.md](https://github.com/c03rad0r/balloon-fresh/blob/master/docs/WORKSTREAM-INDEX.md) |
| Track 2 Nostr | `~/repos/balloon-fresh/docs/coordination/handover-balloon-nostr.md` | [handover-balloon-nostr.md](https://github.com/c03rad0r/balloon-fresh/blob/master/docs/coordination/handover-balloon-nostr.md) |
| Track 3 Tollgate | `~/repos/balloon-fresh/docs/coordination/handover-balloon-tollgate.md` | [handover-balloon-tollgate.md](https://github.com/c03rad0r/balloon-fresh/blob/master/docs/coordination/handover-balloon-tollgate.md) |
| Track 4 PoW | `~/repos/balloon-fresh/docs/coordination/handover-balloon-pow.md` | [handover-balloon-pow.md](https://github.com/c03rad0r/balloon-fresh/blob/master/docs/coordination/handover-balloon-pow.md) |
| Track 5 FIPS | `~/repos/balloon-fresh/docs/coordination/handover-balloon-fips.md` | [handover-balloon-fips.md](https://github.com/c03rad0r/balloon-fresh/blob/master/docs/coordination/handover-balloon-fips.md) |
| Track 6 Blossom | `~/repos/balloon-fresh/docs/coordination/handover-balloon-blossom.md` | [handover-balloon-blossom.md](https://github.com/c03rad0r/balloon-fresh/blob/master/docs/coordination/handover-balloon-blossom.md) |
| Track 7 Range | `~/repos/balloon-fresh/docs/handover-range-testing-2026-07-17.md` | [handover-range-testing.md](https://github.com/c03rad0r/balloon-fresh/blob/master/docs/handover-range-testing-2026-07-17.md) |
| Track 8 Speed | `~/repos/balloon-fresh/docs/handover-speed-testing-2026-07-17.md` | [handover-speed-testing.md](https://github.com/c03rad0r/balloon-fresh/blob/master/docs/handover-speed-testing-2026-07-17.md) |

**STEP 3 — YOUR WORKTREE**

| Track | Worktree | Branch | Source |
|---|---|---|---|
| Track 2 Nostr | `~/worktrees/balloon-nostr/` | `balloon-nostr-extraction` | from balloon-fresh master |
| Track 3 Tollgate | `~/worktrees/balloon-tollgate/` | `balloon-tollgate-c3-port` | from balloon-fresh master |
| Track 4 PoW | `~/worktrees/balloon-pow/` | `balloon-pow-extraction` | from balloon-fresh master |
| Track 5 FIPS | `~/worktrees/balloon-fips/` | `balloon-fips-lr2021` | from balloon-fresh master |
| Track 6 Blossom | `~/worktrees/balloon-blossom/` | `main` | from balloon-fresh master |
| Track 7 Range | `~/worktrees/balloon-range-tests/` | `range-tests` | from balloon-fresh master |
| Track 8 Speed | `~/worktrees/balloon-speed-tests/` | `speed-optimization` | from balloon-fresh master |
| Coordinator | `~/repos/balloon-fresh/` | `master` | primary repo |

**STEP 4 — COORDINATOR AUTHORITY**

**balloon-hermes is the top-level coordinator.** This means:

1. **Cross-track decisions** go through balloon-hermes. If your track depends on another track's output (e.g., FIPS needs the Nostr relay, Blossom needs the captive portal WiFi), escalate — do NOT negotiate directly with the other group.
2. **Hardware conflicts** are resolved by balloon-hermes. We have limited physical boards (20x ESP32-C3, 4x LR2021, 3x EBYTE E28, 2x RP2040). The coordinator decides who uses what.
3. **Integration sequencing** is determined by balloon-hermes. Do not integrate work from another track without coordinator approval.
4. **All tracks report to balloon-hermes.** Status, blockers, and handover docs go there.
5. **Goal: get balloons flying.** The coordinator tracks the critical path to first flight. If you're blocked, report immediately so the coordinator can reroute work.

**STEP 5 — WORKTREE DISCIPLINE (MANDATORY)**

1. **ALL git work in your worktree** — never work directly in `~/repos/balloon-fresh/` unless you ARE the coordinator.
2. **NEVER use `/tmp`** — tmpfs is RAM-backed. Work is destroyed on reboot.
3. **Done = pushed.** Commit AND push every change. Unpushed work = lost work.
4. **Verify hardware before flashing** — board ports change on every USB replug:
   ```bash
   esptool.py --port /dev/ttyACM0 chip_id  # verify BEFORE flashing
   ```
5. **Conventional commits.** Atomic commits — one concern per commit.
6. **No secrets in repos.** No nsec keys, passwords, Signal numbers, real names. Scrub everything.

**STEP 6 — HOW TO REPORT BACK**

Report to balloon-hermes when:
- You start: Post initial findings after reading the codebase.
- You complete a phase: Write a handover doc summarizing what you did.
- You hit a blocker: Post blocker + what you've tried + what you need.
- You need a cross-track dependency: Escalate to balloon-hermes.

Report format:
```
STATUS: [done | in-progress | blocked]
TRACK: [your track name]
TASK: [what you worked on]
RESULT: [what happened]
NEXT: [what's next, or what you need]
```

**STEP 7 — KEY REPOS (source code you'll work with)**

| Repo | Path | What's There |
|---|---|---|
| balloon-fresh (main) | `~/repos/balloon-fresh/` | Tracker firmware, mesh stack, hardware design, docs |
| tollgate-esp32 | `~/esp32-tollgate/` | Full ESP32-S3 TollGate: Nostr relay, Cashu, Stratum, portal |
| wisp-esp32 | `~/wisp-esp32/` | Standalone ESP32 Nostr relay (NIP-01) |
| microfips | `~/repos/microfips/` | Rust ESP32-C3 FIPS mesh firmware |
| LR2021 firmware | `~/repos/balloon-fresh/firmware/` | RP2040 + ESP32-C3 FLRC/LoRa firmware |

**STEP 8 — BEGIN**

1. Read your handover doc (from the table in Step 2)
2. `cd` to your worktree
3. Check state: `git status && git log --oneline -5`
4. Read AGENTS.md if present in your worktree
5. Start working on your next task
6. Report initial findings to balloon-hermes

--- END ---
