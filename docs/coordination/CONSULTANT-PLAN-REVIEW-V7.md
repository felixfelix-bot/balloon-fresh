# Consultant Plan Review V7 — PCB Auto-Routing Execution Plan

**Reviewer:** Senior Hardware + Firmware Consultant
**Date:** 2026-08-05
**Plan:** `PCB-AUTOROUTE-EXECUTION-PLAN.md` (1,726 lines)
**Method:** Targeted section review (lines 1-100, 200-350, 600-700, 1400-1726) + firmware source verification

---

## 1. VERDICT

**APPROVE-WITH-CHANGES**

The PCB auto-routing pipeline (Phases 1-4, 6) is technically sound and ready to execute. The firmware phase (Phase 5) has one critical hardware/firmware conflict that must be resolved before flight. The plan is well-structured with good fallback strategies.

---

## 2. CRITICAL ISSUES

### C1: ADC Channel / GPIO8 Mismatch — HARD CONFLICT (BLOCKER)

**Finding:** `power_manager.c` line 9 defines `SUPERCAP_ADC_CHANNEL ADC_CHANNEL_0` with `ADC_UNIT_1`. On the ESP32-C3, `ADC1_CHANNEL_0` = **GPIO0**. GPIO0 is assigned to GPS UART TX (plan Appendix B, line 1676). This is a direct hardware conflict — the supercap ADC and GPS TX share the same physical pin.

The plan's Appendix B says "GPIO8 = ADC, ⚠️ Verify ADC channel mapping" but never resolves the warning. **GPIO8 is NOT an ADC-capable pin on the ESP32-C3** — ADC1 only supports GPIO0-GPIO4 (channels 0-4). The plan's claim to "Keep: ADC on GPIO8" is physically impossible.

**Fix:** The supercap voltage monitor must move to an ADC-capable pin. Options:
- Use `ADC1_CHANNEL_4` (GPIO4) — but GPIO4 is LR2021_BUSY (flight-critical). Cannot share.
- Use `ADC1_CHANNEL_3` (GPIO3) — but GPIO3 is LR2021_RST. Cannot share.
- **All ADC1 pins (GPIO0-4) are allocated to GPS or SPI.** There is no free ADC pin on the V1 pin map.
- **Recommendation:** Drop supercap voltage monitoring for V1 flight, or use an I2C ADC (e.g., ADS1115) on a future revision. For V1, set `SUPERCAP_ADC_CHANNEL` to an invalid/uninitialized state and skip ADC reads in firmware.

### C2: LED GPIO Change Not Yet Applied (Plan Phase 5 Unexecuted)

**Finding:** `app_main.cpp` line 85 still has `#define LED_GPIO 18`. Plan Phase 5 (line 1637) says change to GPIO9. This is expected since the plan hasn't been executed yet, but the verification is that the change is **defined** in the plan, not yet done. Confirmed the plan correctly identifies the current value (18) and target value (9). GPIO9 exists on ESP32-C3 and is currently unused per the pin map (was I2C SDA, now freed by BMP280 removal). **This is fine — just needs execution.**

### C3: FEM_TX_PIN Default Still 19 (Correctly Identified by Plan)

**Finding:** `Kconfig.projbuild` line 40: `default 19`. Plan says change to `-1`. ESP32-C3 SuperMini does not expose GPIO19. However, `FEM_TX_PIN` has `depends on ENABLE_FEM` and `ENABLE_FEM` defaults to `n`. So this only matters if someone enables FEM. The plan's change to `-1` is a reasonable defensive measure. **Confirmed the plan correctly identifies this.**

---

## 3. GAPS

### G1: No ADC Resolution for Flight
The plan acknowledges the ADC pin mapping needs verification (line 1642) but provides no solution. This is the most dangerous gap — if executed as-is, the firmware will attempt to read ADC on GPIO0, conflicting with GPS TX at runtime (not compile time). This will silently corrupt GPS communication or produce garbage ADC readings.

### G2: RF_SUB_868 Manual Routing Lacks Impedance Control Spec
Phase 3 (lines 1623-1627) specifies 0.8mm width for the RF trace but doesn't specify copper thickness, dielectric height, or target impedance. For 868MHz, trace width alone isn't sufficient — the trace geometry determines characteristic impedance. For a 2-layer 0.6mm board from JLCPCB, a 0.8mm trace on F.Cu gives roughly 50Ω only if the dielectric is ~0.3mm. This should be verified or the trace should be explicitly marked as "non-controlled impedance, short stub acceptable for V1."

### G3: Unconnected Items (68) Resolution Strategy Vague
Phase 2.5 (not in the sections read, but referenced) handles 68 unconnected items. The plan's fallback F2 says "manually add missing track segments" but 68 nets is a lot of manual routing. The plan should clarify whether 68 unconnected includes the 1 unrouted net (RF_SUB_868) or 68 individual connection points.

---

## 4. WORKER PROFILE RECOMMENDATIONS

| Phase | Worker Profile | Rationale |
|-------|---------------|-----------|
| Prereq + Phase 1 | **DevOps/Scripting** | Python script execution, DSN parsing, zero-length track filtering |
| Phase 2 | **PCB Layout** | DRC violation reduction, edge clearance, shorting investigation |
| Phase 3 | **RF/Hardware** | Manual antenna trace routing — needs RF awareness |
| Phase 4 | **DevOps/Scripting** | Gerber export, ZIP packaging |
| Phase 5 | **Firmware Engineer** | GPIO define changes, Kconfig updates, build verification. **Must resolve ADC conflict (C1) before execution** |
| Phase 6 | **DevOps** | Git staging, commit, push |

**Recommended:** Phases 1-4 by a single PCB-focused worker. Phase 5 by a firmware engineer who understands the ESP32-C3 ADC limitation. Phase 5 must NOT proceed until C1 is resolved.

---

## 5. ADC PIN CONFLICT VERIFICATION

| Item | Value | Source |
|------|-------|--------|
| Firmware ADC channel | `ADC_CHANNEL_0` | `power_manager.c:9` |
| Firmware ADC unit | `ADC_UNIT_1` (ADC1) | `power_manager.c:10` |
| ESP32-C3 ADC1_CH0 → GPIO | GPIO0 | ESP32-C3 datasheet |
| GPIO0 plan assignment | GPS UART TX | Plan Appendix B, line 1676 |
| Plan claims ADC on | GPIO8 | Plan Appendix B, line 1684 |
| ESP32-C3 ADC1 channels | CH0=GPIO0, CH1=GPIO1, CH2=GPIO2, CH3=GPIO3, CH4=GPIO4 | ESP32-C3 TRM |
| GPIO8 ADC capability | **NONE** | GPIO8-10 are not ADC pins on ESP32-C3 |

**Verdict: CONFIRMED CONFLICT.** The firmware uses ADC1_CH0 (GPIO0), which collides with GPS TX. The plan's assumption that ADC is on GPIO8 is incorrect — GPIO8 has no ADC peripheral on ESP32-C3. All ADC1-capable pins (GPIO0-4) are allocated to GPS or LR2021 SPI. **There is no available ADC pin in the current V1 pin map.**

---

## 6. QUALITY GATE ASSESSMENT

| Gate | Status | Notes |
|------|--------|-------|
| Prerequisites checklist (lines 1601-1607) | ✅ Adequate | Toolchain + input file verification |
| Phase 1 gate (lines 1609-1614) | ✅ Good | Zero-length filter + DRC threshold <230 |
| Phase 2 gate (lines 1616-1621) | ✅ Good | Specific violation type targets |
| Phase 3 gate (lines 1623-1627) | ⚠️ Missing impedance spec | Width specified, impedance not |
| Phase 4 gate (lines 1629-1634) | ✅ Good | Gerber completeness + final DRC |
| Phase 5 gate (lines 1636-1642) | ⚠️ Insufficient | "ADC pin mapping verified or flagged" is too vague — must be RESOLVED, not flagged |
| Phase 6 gate (lines 1644-1647) | ✅ Adequate | Git workflow |

**Overall:** Quality gates are good for PCB phases, insufficient for firmware phase. Phase 5 gate must require ADC conflict resolution before sign-off.

---

## 7. SPECIFIC CHANGES NEEDED

1. **[BLOCKER] Resolve ADC pin conflict before Phase 5 execution.** Either (a) disable supercap monitoring in firmware for V1 (set `SUPERCAP_ADC_CHANNEL` to unused, guard ADC reads with `#ifdef`), or (b) redesign the pin map to free an ADC-capable pin (GPIO0-4). Option (a) is recommended for V1 timeline.

2. **[BLOCKER] Update Phase 5 verification checklist (line 1642):** Change "ADC pin mapping verified or flagged for consultant review" to "ADC conflict resolved: supercap monitoring disabled OR pin remapped. Firmware compiles and GPS TX verified unaffected."

3. **[MEDIUM] Add impedance note to Phase 3:** Specify "0.8mm trace on 0.6mm 2-layer board ≈ 50Ω microstrip (0.3mm dielectric). Verify with JLCPCB stackup or mark as non-controlled impedance stub for V1."

4. **[MEDIUM] Clarify unconnected items count (68):** Specify whether this is 68 nets or 68 individual pad-to-pad connections. Update Phase 2.5 strategy accordingly.

5. **[LOW] Add explicit GPIO8 ADC impossibility note:** Appendix B should state "GPIO8 is NOT ADC-capable on ESP32-C3. Supercap monitoring requires ADC1 (GPIO0-4), all allocated. V1 flies without supercap voltage telemetry."

6. **[LOW] FEM_RX_PIN default 0 (line 45):** GPIO0 is GPS TX. If someone enables FEM, FEM_RX_PIN=0 would conflict with GPS. Change default to `-1` alongside FEM_TX_PIN for consistency.

---

## 8. BOTTOM LINE

The PCB auto-routing plan is solid engineering work. Phases 1-4 and 6 are ready to execute as written. The DSN parser correctly handles the zero-length track bug, the fallback strategies are practical, and the DRC targets are achievable.

**The one thing that will kill this flight is the ADC channel conflict.** The firmware reads supercap voltage on GPIO0 (ADC1_CH0), which is GPS TX. This won't cause a compile error — it will cause silent runtime corruption of GPS data. The plan identified "⚠️ Verify ADC channel mapping" but treated it as a TODO rather than a blocker. It is a blocker.

**Execute Phases 1-4 and 6 now.** Hold Phase 5 until the ADC conflict is resolved (disable supercap monitoring for V1). Then fly.

---

*Review completed: 2026-08-05 | Method: targeted section read + firmware source verification | Duration: <5 min*