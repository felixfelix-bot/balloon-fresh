# HANDOVER: microFIPS Mesh Workstream

**Created:** 2026-07-17
**Coordinator:** balloon-hermes (top-level coordination hub)
**Authority:** This workstream reports to balloon-hermes. Cross-workstream dependencies are escalated there.

---

## WHAT THIS IS

Rust firmware for ESP32-C3 implementing a minimal FIPS (Free Internetworking
Peering System) mesh leaf node. Key technologies:

- **ESP-NOW** transport layer (connectionless WiFi-layer peer-to-peer)
- **Wirehair** erasure coding for fragmentation/reassembly
- **Noise XK** handshake (migrated from Noise IK/XX — see PR #132)
- **FMP link framing** and **FSP session protocol**
- **Embassy** async HAL, `no_std`

The project has proven end-to-end encrypted communication across USB CDC serial,
BLE GATT, BLE L2CAP, WiFi, and host-side UDP simulators. Current focus is
ESP-NOW mesh networking (Phase 0–4 roadmap).

---

## REPOSITORIES & WORKTREE

| Item | Path |
|------|------|
| Primary repo | `~/repos/microfips/` |
| Worktree | `~/worktrees/ws-microfips/` |
| Active branch | `feat/fips-v0-compat` (primary), `ws/microfips` (worktree) |
| Kanban board | `microfips` (`hermes kanban --board microfips`) |

**Remotes:**
- `fork` → https://github.com/c03rad0r/microfips.git (GitHub, primary push target)
- `origin` → nostr://...relay.ngit.dev/microfips
- `ngit` → nostr://...relay.ngit.dev/microfips

**Worktree status:** Clean, branch `ws/microfips` at commit `55b6cd7` ("fix(esp32c3):
resolve ESP-NOW binary compilation errors"). Primary repo is 1 commit behind
`fork/feat/fips-v0-compat` (commit `22360c9` — "Review fixes: drop unsafe
Peripherals::steal + add IK simultaneous-open test"). Can fast-forward.

---

## WORKSPACE STRUCTURE

Active workspace members (in `Cargo.toml`):
```
crates/microfips-build        — Build helpers
crates/microfips-core          — Core protocol types and traits
crates/microfips-protocol      — Node, Noise handshake, FMP/FSP framing
crates/microfips-esp-common    — Shared ESP32 abstractions
crates/microfips-esp-transport — Transport trait implementations (ESP-NOW)
crates/microfips-esp32c3       — ESP32-C3 binary target ("espnow")
```

Temporarily disabled crates (feature conflicts / std leak):
`microfips-esp32`, `microfips-esp32s3`, `microfips-link`, `microfips-sim`,
`microfips`, `microfips-service`, `microfips-http-demo`, `microfips-http-test`,
`fips-decrypt`, `microfips-l2cap-test`

**Toolchain:** Nightly Rust with `rust-src` and `thumbv7em-none-eabihf` target
(STM32). ESP32-C3 builds require `riscv32imc-unknown-none-elf` target.

---

## BUILD NOTES

- **Host `cargo check` fails** — this is expected. The `portable-atomic`
  `unsafe-assume-single-core` feature is only valid on the ESP32 target, not x86.
  Cross-compile with the appropriate target.
- **ESP32-C3:** `cargo build --target riscv32imc-unknown-none-elf`
- **ESP32-D0WD/S3:** Requires Xtensa LLVM toolchain (builds done on DQ05)
- Known as MFE-001 in the board: "Fix ESP-NOW binary linking — Critical"

---

## BOARD STATUS: `microfips`

**Summary:** done=15, todo=13, blocked=8, pending=8

### Critical Path (MFE-* tasks, pending/unassigned)
| ID | Task | Priority |
|----|------|----------|
| MFE-001 | Fix ESP-NOW binary linking | Critical (1 day) |
| MFE-002 | Flash and validate ESP-NOW binary | Critical (0.5 days) |
| MFE-003 | Port erasure coding from balloon-fresh | High (3-4 days) |
| MFE-004 | Implement pipeline layer | High (2 days) |
| MFE-005 | Merge MAC-to-node-address mapping | Medium (1 day) |
| MFE-006 | Implement FIPS STP + bloom filters | Medium (2-3 days) |
| MFE-007 | Two-node ESP-NOW demo | High (1 day) |
| MFE-008 | FIPS handshake over ESP-NOW | High (1 day) |

### Blocked (8 tasks)
- `t_1893bdd7` — P1.1: Port PRBS23-XOR erasure coding (blocked)
- `t_ffad7e2b` — P2.2: Spanning tree protocol for root election
- `t_00e727de` — Maintain interop test suite: microFIPS ↔ upstream FIPS VPS
- `t_d3eec3ff` — Set up ESP32 interop testing lab
- `t_0e404653` — Verify ESP32 WiFi firmware handshake against VPS1
- `t_20f1624a` — Review PR #133: ESP32-C3 WiFi Noise IK handshake (assigned to manager)
- `t_a142cf8b` — DQ05-BUILD-C3: Build ESP32-C3 binary on DQ05
- `t_76ba7adb` — VPS1-HEALTH: Check FIPS VPS1 (66.92.204.38:2121)

### Completed Milestones
- P0.1–P0.3: ESP-NOW FFI crate, transport trait, binary target ✅
- P2.1: MAC-to-FIPS-node-address mapping ✅
- P2.3: Bloom filter path tracking ✅
- PR #132: Noise IK → Noise XX migration ✅
- PR #133: ESP32-C3 WiFi firmware Noise IK handshake ✅
- DQ05 builds for ESP32-D0WD and S3 ✅

---

## PHASE ROADMAP

| Phase | Focus | Status |
|-------|-------|--------|
| P0 | ESP-NOW basics (FFI, transport trait, binary) | ✅ Done |
| P1 | Erasure coding pipeline (Wirehair/PRBS23-XOR) | ⏳ Blocked |
| P2 | Mesh routing (STP, bloom filters, MAC mapping) | 🔄 Partial |
| P3 | Reliability (peer table, MTU, retransmit, coexistence) | 📋 Todo |
| P4 | Multi-hop + Android exit node integration | 📋 Todo |

---

## KEY FILES

- `crates/microfips-esp-transport/` — ESP-NOW transport implementation
- `crates/microfips-esp32c3/` — ESP32-C3 binary with UART control CLI
- `crates/microfips-protocol/` — Node, Noise handshake, FMP/FSP
- `AGENTS.md` — Agent instructions (in repo root)
- `rust-toolchain.toml` — Nightly toolchain config

---

## INTEGRATION POINTS

1. **balloon-fresh** — Source of PRBS23-XOR erasure coding to port to Rust (P1.1)
2. **upstream FIPS VPS** — Interop testing target at 66.92.204.38:2121 (VPS1)
3. **DQ05 host** — Cross-compilation builds for Xtensa targets (ESP32-D0WD, S3)
4. **ESP32 hardware lab** — Multiple ESP32-C3 boards needed for mesh testing (blocked)
5. **TollGate Android** — P4.1 exit node integration (ESP-NOW mesh → WiFi → FIPS VPS)

---

## NEXT ACTIONS

1. **Fast-forward** primary repo to `fork/feat/fips-v0-compat` (1 commit ahead)
2. **MFE-001** (Critical): Fix ESP-NOW binary linking for `riscv32imc` target
3. **MFE-002** (Critical): Flash and validate ESP-NOW binary on hardware
4. **t_20f1624a** (Blocked/Manager): Review PR #133
5. **t_76ba7adb** (Blocked): Check VPS1 health and restart FIPS daemon if down
6. Assign pending MFE-* tasks to appropriate worker profiles

---

## COORDINATION PROTOCOL

- Report status + blockers to balloon-hermes Signal group
- Cross-workstream dependencies → escalate to balloon-hermes
- All work committed + pushed (fork remote for shared, ngit for mirror)
- Worktree at `~/worktrees/ws-microfips/` — never use `/tmp`
- Scrub PII from all public artifacts
