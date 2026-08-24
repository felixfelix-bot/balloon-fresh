# Consultant Plan Review V4 — Three Plans

## Plans Under Review
- A) FIPS-FIX-PLAN.md — ESP32-C3 Rust build fixes (3 bugs)
- B) INTEGRATION-TEST-PLAN.md — Two-board test phases 2-4
- C) V1-PCB-GPIO-FIX.md — PCB schematic GPIO collision fix

## Overall Assessment

All three plans are reasonable but have gaps. The ordering is wrong — PCB fix should be first (2-week lead time is the critical path), then FIPS (code work, no hardware), then integration tests (needs hardware).

## Plan A: FIPS C3 Build Fix

### Correct
- Per-member build approach is right
- portable-atomic for RISC-V atomics is the standard solution
- esp-println for logging is simplest option
- Order (atomics → config → logger) is correct dependency chain

### Concerns
1. **DEVICE_NSEC hardcoded?** Plan says "generate or hardcode." This is a cryptographic identity — hardcoding is fine for dev but needs proper key generation for production. Don't overthink it — use a fixed dev key and note it.

2. **Register addresses need verification.** The plan lists UART0_BASE=0x60043000 and RESET_REGISTER=0x60007000. These should be verified against the ESP32-C3 Technical Reference Manual, not guessed. Wrong addresses = silent hardware failure.

3. **Missing: .cargo/config.toml update.** Plan mentions it at the end but doesn't specify what goes in it. Need:
   ```toml
   [target.riscv32imc-unknown-none-elf]
   runner = "espflash flash --monitor"
   rustflags = ["-C", "link-arg=-Tlinkall.x"]
   ```

4. **Overcomplicated:** The cfg(target_arch = "riscv32") conditional import is unnecessary. Just use portable_atomic everywhere — it falls back to core::sync::atomic on platforms that support it natively. One import, no cfg.

### Verdict: Good plan, simplify the atomic fix.

## Plan B: Integration Test Plan

### Correct
- Phase 2 (raw ping) first is right — zero new code
- Config flags for each phase are correct
- Troubleshooting tables are useful
- Wiring checklist is comprehensive

### Concerns
1. **Missing CLI commands are a bigger problem than acknowledged.** The plan says "may not exist" but the reality is NONE of these commands exist: relay_send_nostr, nostr_dump, tollgate_send_pay. Without them, Phases 3-4 can't run at all. The plan should either:
   - Add a Phase 2.5: "Write missing CLI commands" with time estimate
   - Or specify how to test via serial input / hardcoded packets

2. **radio_recv 30 — does this command exist?** The plan assumes existing CLI commands work. Need to verify. If radio_test and radio_recv don't exist, Phase 2 is also blocked.

3. **No mention of SPI initialization.** The relay-mode firmware initializes the radio differently than the TX-sleep firmware. When CONFIG_ENABLE_RELAY_MODE=n, does the CLI radio_test command still work? The radio init path may differ.

4. **Board lock protocol not mentioned.** AGENTS.md requires balloon-board-lock.py acquire before flashing. The plan should include this.

5. **"30cm apart" is too close.** LR2021 at 22dBm at 30cm will overload the receiver. Start at 1-2 meters minimum, or add 20dB attenuators.

### Verdict: Decent plan, but needs CLI command gap analysis and board lock steps.

## Plan C: V1 PCB GPIO Fix

### Correct
- Net label changes are the right approach
- JLCPCB checklist is comprehensive
- Pin assignment table is clear

### Concerns
1. **This is the highest priority plan but listed last.** JLCPCB has 2-week lead time. This should be ordered TODAY. Even if the schematic fix takes 2 hours, the gerber regeneration and order should happen before anything else.

2. **No actual KiCad file investigation.** The plan says "find KiCad project files" but doesn't do it. Need to actually locate the .kicad_pcb file and check if kicad-cli is installed before estimating time.

3. **GPIO18 and GPIO19 may have existing traces.** Moving LED and FEM_TX isn't just changing net labels — it may require re-routing traces on the PCB layout. This could be a 4-hour job, not 30 minutes.

4. **Missing: DRC after changes.** Design Rule Check must pass before ordering. The checklist mentions it but no procedure.

### Verdict: Right approach, but needs actual file investigation and should be prioritized FIRST.

## Recommended Order

1. **PCB fix + order (TODAY)** — 2-week lead time is critical path. Find KiCad files, make changes, order.
2. **FIPS fix (TODAY, no hardware)** — 2h code work, unblocks FIPS integration later
3. **Verify CLI commands exist (TODAY)** — grep for radio_test, radio_recv in firmware. If missing, Phase 2 needs new code.
4. **Integration tests (when boards arrive)** — Phase 2 first, then write CLI commands for Phases 3-4

## What's Missing Across All Plans

1. **No unified firmware config for bench testing.** Need a single sdkconfig that enables relay mode + nostr_store + secp256k1 but disables mesh (isolate the relay pipeline). None of the plans specify this.

2. **No mention of the host-side relay test (12/12 passing).** This test already proves the pipeline works. Integration tests should build on this, not start from scratch.

3. **No rollback plan.** If any phase fails, what's the fallback? Each plan should have a "if this doesn't work, do X" section.

4. **ngit push is broken.** Multiple workers reported "account COMPROMISED not maintainer." This needs investigation — GitHub-only push is fine for now but ngit is part of the dual-push workflow.

## Bottom Line

Plans are solid foundations. Three actions:
1. Find and fix PCB schematic TODAY, order JLCPCB
2. Fix FIPS (2h, no hardware, well-specified)
3. Verify CLI commands exist before planning integration tests