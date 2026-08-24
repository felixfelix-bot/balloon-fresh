# CONSULTANT STRATEGIC REVIEW — Balloon Project

**Reviewer:** Senior systems consultant (subagent)
**Date:** 2026-08-05
**Branch reviewed:** `autonomous/mesh-baseline` @ `c97752f`
**Method:** Read PROJECT-STATUS-SUMMARY.md, PCB-TASK-PIPELINE.md, CONSULTANT-FINAL-BOARD-REVIEW.md, FLIGHT-BOARD-PLAN.md. Independently verified claims against actual files: ran DRC on `v2_2LAYER_FINAL.kicad_pcb`, counted components/nets/unconnected, cross-checked firmware target vs board footprint, inventoried 33 board variants and ~20 routing scripts, audited commit history.

---

## TL;DR — THE BRUTALLY HONEST VERSION

**You are not on the critical path. You are on a side-quest.**

The team has spent the last week generating **33 PCB file variants, ~20 Python routing scripts, and 163 commits** to automate the layout of a **17-component, 18-net board** — a board a competent KiCad user routes by hand in a single evening. Meanwhile the firmware (22,000+ lines, 22 components, builds clean, 119 tests passing) is in far better shape than the status doc admits, and **the actual blocker to a first flight is not PCB routing at all — it's that the firmware and the board target different microcontrollers.**

Three findings below are show-stoppers that the status summary either buries, misstates, or misses entirely. Read them before you do anything else.

---

## THE THREE SHOW-STOPPERS

### 🚨 #1 — FIRMWARE AND BOARD TARGET DIFFERENT CHIPS

This is the single most important finding in this review and it is **not mentioned anywhere** in the status summary.

```
tracker/firmware/sdkconfig:   CONFIG_IDF_TARGET="esp32s3"
v2_2LAYER_FINAL.kicad_pcb:    footprint "ESP32-C3"  (U1)
```

- The firmware you have built (22,465 LOC, builds to `balloon-tracker.bin`, 332 KB) is for **ESP32-S3**.
- The PCB you have spent a week routing is for **ESP32-C3**.
- The 3 physical dev boards you own are **ESP32-S3** (per `AGENTS.md`).
- The original `FLIGHT-BOARD-PLAN.md` specified ESP32-C3 as the flight MCU.

**Implication:** Even if `v2_2LAYER_FINAL` were perfectly routed and you ordered it today, **the firmware would not run on it.** GPIO mappings differ (C3 has fewer pins, no GPIO9-as-LED in the same way, different SPI/UART routing), the radio transport layer would need porting, and at minimum a new sdkconfig + pin map + recompile. This is days of work, not hours, and it's not on anyone's radar.

**You must pick one MCU and align everything to it before doing any more PCB or firmware work.** See Q6 below for my recommendation.

### 🚨 #2 — THE "16 UNCONNECTED = ALL POWER NETS" CLAIM IS FALSE

The status summary (§5, lowest-hanging fruit) says: *"Order 2-layer board NOW (v2_adc_fixed2, 16 unconnected power pads). Felix finishes power routing in KiCad GUI (15 min)."*

I ran DRC on the actual candidate board (`v2_2LAYER_FINAL.kicad_pcb`). The 16 unconnected nets are:

| Category | Nets | Count |
|----------|------|-------|
| Power | `3V3`, `GND`, `VCAP` | 3 |
| **Critical signal** | **`SPI_SCK`, `LR2021_BUSY`, `LR2021_DIO9`, `STATUS_LED`** | **4** |
| RF / analog | `RF_SUB_868`, `RF_2G4_2400`, `SOLAR_IN`, `VDIV_MID` | 4+ |

**8 of the 16 unconnected nets are signal/RF, not power.** Three of them — `SPI_SCK`, `LR2021_BUSY`, `LR2021_DIO9` — are the SPI clock and the LR2021's busy + interrupt lines. **Without these the radio will not initialize, will not respond to a single SPI transaction, and will not generate a single packet.** This is not "15 minutes of power routing in the GUI." It is "the radio doesn't work."

Additionally: the board has **1 DRC violation — "Board outline self-intersecting"** — which JLCPCB may reject outright or fab as a malformed panel.

**Do not order this board.** It will not produce a working radio.

### 🚨 #3 — "FEM REMOVED FOR V1" IS ALSO FALSE FOR THIS BOARD

The status summary (§1, What Worked) claims: *"GPIO fix: LED→GPIO9, FEM removed, ADC disabled for V1. Verified correct."*

The `v2_2LAYER_FINAL.kicad_pcb` still contains a `FEM` reference designator (5 matches for FEM/sky66112/SP4T). The FEM was removed from *one of the 33 variants*, not from the board being recommended for order. The team has lost track of which file is which — a direct consequence of having 33 board files with no schematic source of truth.

---

## WHAT THE STATUS DOC GETS RIGHT

To be fair, several things are genuinely in good shape:

1. **Firmware is the strong suit, not the weak suit.** 22K LOC, 22 components, builds to a 332 KB binary. `mesh_adapter`, `stratorelay`, `wirehair` (RaptorQ FEC), `erasure`, `tdma`, `frag`, `nostr_store`, `crypto`, `blossom_datagram`, `fips_radio_bridge` — this is a serious, layered mesh stack. The status doc undersells it.
2. **The radio task refactor (5s → 100ms poll) is real and matters.** That was a genuine latency bug. Good catch.
3. **Tollgate: 119 unit tests passing** on payment protocol — solid.
4. **FreeRTOS relay mode is implemented, not just designed.** `app_task.cpp` (164 LOC) and `radio_task.cpp` (82 LOC) exist with real queue-based dispatch. The status doc calls this "partial" — it's further along than that.
5. **The original `FLIGHT-BOARD-PLAN.md` is a clear, correct, sensible design.** 50×45 mm, 2-layer, bottom GND pour, ESP32-C3 + LoRa2021 + MAX-M10S, ~$16 from JLCPCB. This was the right plan. The team has drifted away from it.

---

## DIRECT ANSWERS TO FELIX'S QUESTIONS

### Q1. What are the lowest-hanging fruits?

In priority order:

1. **Stop generating board variants. Pick one MCU. Decide today.** (0 minutes of work, unblocks everything.)
2. **Wire an LR2021 module to an ESP32-S3 dev board on a breadboard.** You have 3 S3 boards and 4 LoRa2021 modules (per FLIGHT-BOARD-PLAN BOM). This takes 30 minutes with jumper wires and gives you a **bench-testable radio platform today** — no PCB, no JLCPCB, no 2-week wait. The firmware already targets S3. This is the single highest-leverage action available.
3. **Flash `balloon-tracker.bin` to an S3 board and verify the radio task actually initializes an LR2021 over SPI.** You have never confirmed this end-to-end on real hardware. Do it on a breadboard before you design a PCB around assumptions.
4. **Run `idf.py monitor` and confirm: chip ID read, SPI OK, TX/RX loopback between 2 boards.** This is the real "lowest-hanging fruit" — it converts 22K lines of firmware from "compiles" to "proven on hardware."

### Q2. What are the immediately actionable steps?

**This week (no PCB required):**

| Step | Owner | Time | Unblocks |
|------|-------|------|----------|
| 1. Breadboard: LR2021 ↔ ESP32-S3 (SPI + IRQ + BUSY + RST) | Felix | 30 min | All radio testing |
| 2. Flash tracker firmware, verify LR2021 chip ID over SPI | Felix | 1 hr | Confidence in firmware |
| 3. 2-board TX/RX range test (same room, then across house) | Felix | 2 hr | "Does the radio link work at all?" |
| 4. Decide: ESP32-S3 or ESP32-C3 for flight. Commit in writing. | Felix | 10 min | PCB design, firmware port |
| 5. Delete 30 of the 33 board variants. Keep 1 source of truth. | Felix | 5 min | Sanity |

**Next week (after breadboard validates the radio):**

| Step | Owner | Time |
|------|-------|------|
| 6. Route ONE board by hand in KiCad GUI (17 components!) | Felix | 1 evening |
| 7. Order from JLCPCB ($16) | Felix | 10 min |
| 8. While waiting (2 weeks): complete FreeRTOS relay testing on breadboard | Felix/agent | ongoing |

### Q3. How can we make progress more effectively toward the DIY Starlink goal?

**The goal is "pico balloon + tollgate + FIPS mesh." The critical path to a first flight is: working radio link on hardware → working relay firmware on hardware → one board that flies. Everything else is premature.**

Three process corrections:

**A. Stop automating things that are faster by hand.** A 17-component board does not need Freerouting, DSN/SES pipelines, 20 Python scripts, a `worker-layout` profile, or kimi-k3 spatial reasoning. Felix opening KiCad and routing it by hand is **at least 10× faster** than every automation attempt to date — and the automation has produced 33 broken variants as evidence. The "toolchain" was a yak-shave. The lesson learned ("kimi-k3 for ALL spatial work") is the wrong lesson. The right lesson is: **route trivial boards by hand; only automate when board complexity justifies it (50+ components, BGA, impedance-controlled).**

**B. Establish a single source of truth.** Right now: no schematic exists for any of the 33 board variants (only `hub_board_diy.kicad_sch` in the whole repo). Boards were generated by `gen_pcb.py` with hand-coded netlists. This means:
- No ERC was ever run.
- The netlist is whatever Python declared, not what a schematic verifies.
- This is why routing keeps "failing" — you're debugging a fabricated netlist with no ground truth for what should connect to what.
- It's also how the FEM-removed / not-removed confusion happened.

**Fix:** Draw the schematic first in KiCad. One schematic. Push netlist to PCB. Route. This is PCB design 101 and it was skipped.

**C. Reduce project sprawl.** The repo contains at least 6 firmware projects: `tracker/firmware/` (ESP32-S3), `firmware/rp2040/` (14 PIO environments!), `firmware/esp32-c3-flrc/`, `mesh-stack/firmware/`, `mesh-stack/esp-now-firmware/`, `firmware/esp32-uart-bridge/`. Pick the flight path. For V1 flight: **one MCU, one firmware, one board.** The RP2040 work and the ESP32-C3-FLRC work are interesting R&D but they are not the flight path and they are diluting focus.

### Q4. Is the 2-layer board orderable? Should we order it?

**No. Do not order `v2_2LAYER_FINAL.kicad_pcb` or `v2_adc_fixed2.kicad_pcb` as-is.**

Three independent reasons:
1. **8 of 16 unconnected nets are signal/RF**, including the SPI clock and LR2021 control lines. The radio will not work.
2. **Board outline self-intersects** (DRC violation). JLCPCB may reject it.
3. **MCU mismatch** (show-stopper #1). The board is ESP32-C3; the firmware is ESP32-S3.

**Should you order a 2-layer board at all? Yes — after Felix routes it by hand in an evening.** 2-layer is correct for V1. The original FLIGHT-BOARD-PLAN had it right: top = signal, bottom = GND pour. You do not "route" GND on a 2-layer board — it's a copper pour. 3V3 is a single star-net from the LDO. This is trivial. The automation was trying to route GND as explicit tracks, which is the wrong mental model for 2-layer.

**Do not order until:** schematic exists → ERC clean → Felix routes by hand → DRC 0 violations / 0 unconnected → gerbers re-exported → Felix eyeballs the gerbers in a viewer.

### Q5. Should we prioritize 4-layer design or firmware?

**Neither. Prioritize breadboard validation.**

The 4-layer design is a solution to a problem you don't have. The 2-layer routing "failure" was a process failure (no schematic, automation-first, wrong GND model), not a layer-count failure. You do not need 4 layers for a 17-component board. JLCPCB charges more for 4-layer and the lead time is longer. **4-layer is premature optimization. Kill it.**

Firmware is in good shape and should be validated on hardware (breadboard) before more features are added. The next firmware priority is not "complete FreeRTOS relay tasks" — it's "prove the radio works on a real LR2021 over SPI on a real ESP32-S3." Once that's confirmed, the relay tasks have a testbed.

**Order of operations:** breadboard radio validation → hand-route 2-layer board → order → (2-week wait) → flesh out relay/mesh firmware on breadboard with real packets → receive PCB → assemble → fly.

### Q6. What's blocking us from a real flight test?

In order of severity:

1. **MCU decision unmade.** S3 firmware vs C3 board. This blocks everything downstream. **Decide today.** My recommendation: **ESP32-S3**, because (a) you have 3 S3 dev boards, (b) the firmware already targets S3 and builds, (c) the firmware is 22K lines of S3-targeted code that you do not want to port. Redesign the board for S3. The C3 was the original plan but the firmware investment has made S3 the pragmatic choice. The C3's only advantage (lower power, lighter) matters for flight — but you are months from flight, and an S3 dev-board-on-a-balloon proves the concept first. Optimize for weight in V2.

2. **No hardware validation of the radio link.** 22K lines of firmware, zero confirmed packets over a real LR2021. You are designing a PCB around an unvalidated radio integration. Breadboard it first.

3. **No ordered PCB.** 2-week JLCPCB lead time. Every day of delay = +1 day to flight. But: do not order until #1 and #2 are resolved, or you'll order the wrong board.

4. **No schematic.** Without a schematic there is no ERC, no netlist truth, and board variants multiply uncontrolled. This is why you have 33 of them.

5. **No GPS, solar, or supercap testing.** These are V1 flight essentials per FLIGHT-BOARD-PLAN but have had zero bench time. They're lower risk than the radio (well-trodden parts) but shouldn't be first-flighted cold.

Notably **NOT on the blocker list:** 4-layer PCB spec, FIPS firmware (dependency hell, park it), Cashu-on-balloon integration, secp256k1 on received packets, mesh relay protocol definition. These are all V2+ concerns. For a first flight you need: MCU + radio + GPS + power + antenna. That's it.

### Q7. What would a realistic timeline look like?

Assuming Felix acts on this review **today**:

| Week | Milestone | Deliverable |
|------|-----------|-------------|
| **1** (now) | Breadboard radio validation | LR2021 wired to S3, firmware flashed, SPI chip ID confirmed, 2-board TX/RX loopback working. **MCU decision committed.** Schematic drawn in KiCad. |
| **2** | Board designed + ordered | One (1) 2-layer board, hand-routed, DRC clean, gerbers verified, JLCPCB order placed (~$16). Breadboard relay-mode firmware testing continues. |
| **3–4** | JLCPCB lead time (parallel work) | On breadboard: GPS fix acquired, solar→supercap→LDO power chain tested, telemetry packet format finalized, range test (across neighborhood). |
| **4–5** | PCB arrives, assemble, bench test | Solder components. First powered-up on real PCB. Confirm radio + GPS + power on the flight board. |
| **5–6** | Integration + ground range test | Full system on flight board: GPS position → LoRa TX → ground station RX. Range test from ground (km-scale). Weight check (<9g flight config). |
| **6–8** | First flight | Balloon prep, leak test, He fill, launch. **First flight by ~week 7, realistically week 8–10 with slippage.** |

**This is 7–10 weeks to first flight if you pivot now.** If you continue the current path (4-layer spec, more board variants, automation scripts), you are looking at 4–6 months minimum, possibly longer, because you'll order a board that doesn't match your firmware and discover it after a 2-week lead time.

---

## PROCESS RECOMMENDATIONS

1. **Schematic-first, always.** No more `gen_pcb.py`. Draw it in KiCad. ERC before DRC.
2. **One board file.** Delete the other 32. Use git history if you ever need them.
3. **Hand-route small boards.** Reserve automation for >50-component designs.
4. **Breadboard before PCB.** Always. No exceptions for first-of-a-kind radio integration.
5. **One MCU. One firmware. One board.** For V1. Sprawl is for V2.
6. **Status doc accuracy.** The current PROJECT-STATUS-SUMMARY contains three materially false claims (16 unconnected = all power; FEM removed; implication that the board is orderable). These came from not verifying against the actual files. Always DRC the candidate board before writing "order this." The earlier CONSULTANT-FINAL-BOARD-REVIEW was correct ("DO NOT ORDER") and was apparently ignored or superseded by the rosier status summary. Trust the verification, not the narrative.

---

## THE BOTTOM LINE

The DIY Starlink goal is ambitious but **not blocked by anything fundamental** — the firmware is 80% there, the radio module is proven (NiceRF LoRa2021, "verified working" per FLIGHT-BOARD-PLAN), the board is simple, and JLCPCB is cheap and fast. **What's blocking you is process, not technology.** The team has been optimizing the wrong thing (PCB routing automation) on the wrong artifact (a board for the wrong MCU) via the wrong method (script-generated netlists with no schematic).

**Pivot to breadboard validation today. Route one board by hand this week. Order it. Fly in 7–10 weeks.**

The firmware work is good. The PCB work this past week was largely wasted — but that's fixable in a single evening with KiCad open and the FLIGHT-BOARD-PLAN.md as the guide. Get back to that plan. It was right.

---

*Review prepared by independent consultant subagent. All claims verified against repository contents at commit `c97752f` on 2026-08-05. DRC run live via `kicad-cli 9.0.8`. No claims in this document are derived from the status summary without independent verification.*
