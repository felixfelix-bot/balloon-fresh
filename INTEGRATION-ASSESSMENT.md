# Integration Assessment — Balloon Pre-Stretching

**Track:** balloon-pre-stretching (physical preparation only)
**Date:** 2026-07-21
**Scope:** Balloon materials, inflation procedures, pre-stretching protocols, leak testing, pressure holding validation. No firmware, no circuit design.

---

## What Works Now

| Item | Status | Evidence |
|------|--------|----------|
| DecoGlee 18" leak test data | **Complete** | 3 balloons, 25-day indoor test, 0.15 g/day leak rate. See `docs/balloon-test-results.md` |
| Pressure test plan | **Written** | 4-test methodology (short, long-term, multi-balloon, temperature). See `docs/balloon-pressure-test.md` |
| Community research | **Complete** | 80+ flights from 6+ practitioners analyzed. See `docs/balloon-flight-lessons.md` |
| Balloon options analysis | **Complete** | 7 balloon types compared with cost/duration data. See `docs/balloon-options-analysis.md` |
| Gas decision | **Decided** | He 4.6 (99.996%) per ADR-011. Party He = 0% circumnavigation (Ruthroff 0/9) |
| Balloon type decision | **Decided** | Yokohama 32" Crystal Clear for long-duration, DecoGlee 18" for shakedown |
| Sealing method | **Decided** | Heat seal + Kapton tape (proven by all successful community flights) |
| Free lift target | **Decided** | 5–7 g (Ruthroff + KI4MCW data) |
| Pre-stretching protocol | **Written (this commit)** | `docs/PRE-STRETCHING-PROTOCOL.md` — DecoGlee and Yokohama procedures |
| 30x DecoGlee 18" balloons | **Owned** | In inventory |
| Pressure sensor + pump | **Owned** | In inventory |

## What Exists But Is Untested/Incomplete

| Item | Status | Gap |
|------|--------|-----|
| Pressure test rig (BMP280 + XIAO ESP32C3) | **Designed, not built** | BMP280 breakout not yet purchased (~€1). Wiring documented in `docs/balloon-pressure-test.md` (SDA→GPIO8, SCL→GPIO9). No physical assembly done. |
| Pressure test firmware | **Specified, not implemented** | ESP-IDF mini-project at `tools/balloon_pressure_test/` — outside this track's scope (firmware track). Python evaluation script also specified but not written. |
| DecoGlee multi-balloon cluster concept | **Analyzed, not tested** | 6× DecoGlee gives ~28.8 g net lift with party He. Cut-down mechanism identified as essential (dead balloon = 10.5 g dead weight). No cluster assembly or test flight performed. |
| Temperature cycling test | **Planned, not executed** | Freezer −18 °C test described in protocol (§D.2 Test 4). Not yet performed on any balloon. |
| Leak rate acceptance thresholds | **Defined, not validated** | < 0.5 mbar/h = very good, > 5 mbar/h = reject (from `docs/balloon-pressure-test.md`). Thresholds are from community guidance, not yet validated with our own rig. |

## What Does NOT Exist Yet

| Item | Impact | Action Required |
|------|--------|----------------|
| Yokohama 32" balloons | **Blocking long-duration flights** | Purchase 10-pack (€105.95) from yokohamaballoon.com or US reseller |
| Industrial He 4.6 supply | **Blocking all serious flights** | Source Air Liquide ALbee Fly (or Linde/Messer equivalent). Price and availability TBD. |
| Pressure test rig (physical) | **Blocking electronic leak tests** | Buy BMP280 breakout, assemble with XIAO ESP32C3, wire per spec |
| Pre-stretching experience | **Blocking Yokohama flights** | No team member has physically pre-stretched a nylon/PE balloon. First attempt must follow protocol carefully — Ruthroff's JR01–JR06 overpressure mistake is documented as a cautionary example. |
| Heat sealer | **Possibly needed** | Not confirmed in inventory. Standard food-bag sealer required (setting "6", ~5 s). |
| Kapton/Kynar tape | **Possibly needed** | Not confirmed in inventory. Required for seal reinforcement. |
| Cut-down mechanism | **Blocking multi-balloon flights** | Essential for DecoGlee clusters. Not designed or built. |
| Non-magnetic calibrated weights | **Needed for free lift** | MS300 scale cannot weigh magnets. Need brass/steel/lead weights for accurate free lift measurement. |
| Launch coordination | **Blocking all flights** | Need launch date, location, weather window from orchestrator track |

## Blockers For Flight Readiness

Adapted from "Blockers Before ESP32-C3 Integration" format.

### B1: Yokohama Balloons Not Purchased
- **Severity:** Blocks long-duration flights entirely
- **Cost:** €105.95 for 10-pack
- **Lead time:** Unknown (international shipping from Japan or US reseller)
- **Resolution:** User purchases Yokohama 32" Crystal Clear 10-pack

### B2: He 4.6 Supply Not Sourced
- **Severity:** Blocks all serious flights (party He = 0% circumnavigation)
- **Cost:** TBD (Air Liquide ALbee Fly cylinder + regulator)
- **Lead time:** Unknown (industrial gas supplier procurement)
- **Resolution:** User contacts Air Liquide / Linde / Messer for He 4.6 supply

### B3: Pressure Test Rig Not Built
- **Severity:** Blocks electronic leak testing (manual circumference method is fallback but less precise)
- **Cost:** ~€1 (BMP280 breakout) + XIAO ESP32C3 (owned) + wires
- **Lead time:** 1–2 days (order + assemble)
- **Resolution:** Purchase BMP280, wire to XIAO ESP32C3 per `docs/balloon-pressure-test.md`

### B4: Heat Sealer and Kapton Tape Not Confirmed
- **Severity:** Blocks reliable balloon sealing (all adhesives failed in community testing)
- **Cost:** ~€10–20 (standard food-bag heat sealer) + ~€5 (Kapton tape roll)
- **Resolution:** Confirm in inventory or purchase

### B5: No Physical Pre-Stretching Experience
- **Severity:** Risk of balloon damage during first Yokohama pre-stretch
- **Mitigation:** Protocol documented (§C.2) with Ruthroff's overpressure cautionary note. Follow circumference-based method, not pressure-based.
- **Resolution:** Perform first pre-stretch with strict protocol adherence

### B6: Payload Weight Not Finalized
- **Severity:** Cannot determine balloon count or gas volume for launch
- **Dependency:** Circuit-design track must finalize payload weight (Minimal ~9 g, Mittel ~13 g, Mesh V1 ~14 g)
- **Resolution:** Awaiting payload weight from circuit-design track

## Dependencies On Other Tracks

| Dependency | Track | What We Need | Impact |
|-----------|-------|-------------|--------|
| Payload weight | circuit-design | Final weight of flight-ready tracker (board + battery + solar + antenna) | Determines balloon count (DecoGlee) or gas volume (Yokohama) and free lift calculation |
| Launch coordination | orchestrator | Launch date, location, weather window, regulatory compliance | Cannot schedule pre-stretching (48 h lead time) or inflation without a launch date |
| Tracker readiness | firmware + circuit-design | Working, flight-ready tracker with confirmed weight | Pre-stretching can proceed without tracker, but final gas fill volume depends on payload weight |
| Pressure test firmware | firmware | BMP280 reading + serial logging on XIAO ESP32C3 | Electronic leak test rig needs this firmware to function. Manual circumference method is fallback. |
| Cut-down mechanism | mechanical (if separate track) | Design and build for multi-balloon clusters | Dead DecoGlee = 10.5 g dead weight. Essential for clusters. |

## Minimal Viable Integration

**6× DecoGlee 18" + party He = 3–5 day shakedown flight. No Yokohama needed.**

This is the fastest path to a first flight:

| Component | Status | Notes |
|-----------|--------|-------|
| 6× DecoGlee 18" balloons | **Owned** (30 in inventory) | 6 × 4.8 g = 28.8 g gross net lift |
| Party helium | **Available** (Amazon, party store) | 4.8 g/balloon net lift. 0% circumnavigation rate — shakedown only. |
| Heat sealer | **To confirm/purchase** | Setting "6", ~5 s per seal |
| Kapton tape | **To confirm/purchase** | For seal reinforcement |
| Pressure test rig | **Optional** | Manual circumference method is fallback for shakedown |
| Cut-down mechanism | **Needed** | Dead balloon = 10.5 g dead weight per balloon |
| Payload | **From circuit-design track** | Target: ≤ 14 g (Mesh V1) → 28.8 g − 14 g = 14.8 g free lift margin |

**Expected outcome:** 3–5 day flight, validates tracker + balloon + sealing + launch process. Does NOT validate long-duration capability (requires Yokohama + He 4.6).

**Path to long-duration:** Replace DecoGlee with 1× Yokohama 32" + He 4.6 → target 60+ days.

## Hardware Needed

### For Shakedown Flight (DecoGlee + Party He)

| Item | Qty | Cost | Status |
|------|-----|------|--------|
| DecoGlee 18" balloons | 6 (of 30 owned) | €0 | Owned |
| Party helium (Amazon) | 1 tank/cylinder | ~€20–30 | Purchase |
| Heat sealer | 1 | ~€10–15 | Confirm/purchase |
| Kapton tape | 1 roll | ~€5 | Confirm/purchase |
| Non-magnetic weights | Set (5–10 g) | ~€5 | Purchase |
| Cut-down mechanism | 1 | TBD | Design + build |

### For Long-Duration Flight (Yokohama + He 4.6)

| Item | Qty | Cost | Status |
|------|-----|------|--------|
| Yokohama 32" Crystal Clear | 10-pack | €105.95 | Purchase |
| He 4.6 (99.996%) | 1 cylinder | TBD | Source (Air Liquide ALbee Fly) |
| 12V air pump | 1 | ~€15–25 | Confirm/purchase |
| BMP280 breakout | 1 | ~€1 | Purchase |
| XIAO ESP32C3 | 1 (of 20 owned) | €0 | Owned |
| Humidifier | 1 | ~€20–30 | Purchase/borrow |
| Measuring tape (100"+) | 1 | ~€3 | Purchase |
| Heat sealer | 1 | ~€10–15 | Shared with shakedown |
| Kapton tape | 1 roll | ~€5 | Shared with shakedown |

### Already Owned

- 30× DecoGlee 18" foil balloons
- 1× pressure sensor + pump (for balloon testing)
- 1× MS300 jewelry scale (cannot weigh magnets — use non-magnetic weights only)
- 1× digital calipers
- 20× ESP32-C3_Mini_V1 (for pressure test rig)
- ~43× neodymium magnets (NOT suitable as calibrated weights)

## Decisions Needed From The Human

| # | Decision | Options | Recommendation | Status |
|---|----------|---------|----------------|--------|
| D1 | He 4.6 vs H2 | He 4.6 (safe, indoor) vs H2 (55% circumnav, outdoor only) | **He 4.6** — already decided (ADR-011) | ✅ Decided |
| D2 | Yokohama vs SBS-13 | Yokohama (€10.60 each, proven) vs SBS-13 (~$165 each, purpose-built) | **Yokohama** — 10x cheaper, proven 528 days | ✅ Decided |
| D3 | Balloon count for first flight | 1× Yokohama (long-duration) vs 6× DecoGlee (shakedown) | **6× DecoGlee shakedown first**, then 1× Yokohama | ⬜ TBD — depends on payload weight |
| D4 | When to purchase Yokohama balloons | Now (long lead time) vs after shakedown validates tracker | **After shakedown** — don't waste €106 if tracker isn't ready | ⬜ Pending shakedown |
| D5 | He 4.6 supplier | Air Liquide ALbee Fly vs Linde vs Messer | **Air Liquide ALbee Fly** (Ruthroff's source, ADR-011) | ⬜ Pending sourcing |
| D6 | Heat sealer model | Any standard food-bag sealer with adjustable heat | Setting "6" per Ruthroff. Any brand works. | ⬜ Pending purchase |

## User Blockers

These require physical human action — cannot be resolved by this track's agent:

1. **Purchase Yokohama 32" Crystal Clear 10-pack** — €105.95 from yokohamaballoon.com or US reseller. International shipping may take weeks.
2. **Source industrial He 4.6** — Contact Air Liquide (ALbee Fly), Linde, or Messer. Need cylinder + regulator with appropriate fittings. Price and availability unknown.
3. **Purchase BMP280 breakout** — ~€1 from any electronics supplier (Amazon, AliExpress, DigiKey). Needed for electronic leak test rig.
4. **Build pressure test rig** — Wire BMP280 to XIAO ESP32C3 per `docs/balloon-pressure-test.md` (SDA→GPIO8, SCL→GPIO9, VCC→3.3V, GND→GND). Flash firmware (firmware track dependency).
5. **Purchase/confirm heat sealer** — Standard food-bag sealer with adjustable temperature. Setting "6" per Ruthroff.
6. **Purchase/confirm Kapton tape** — For seal reinforcement after heat sealing.
7. **Purchase non-magnetic calibrated weights** — Brass, steel, or lead. For free lift measurement. MS300 scale cannot handle magnets.
8. **Physically perform pre-stretching** — First Yokohama pre-stretch must be done by a human following the protocol (§C.2). 48 h lead time (humidification + stretching). Cannot be automated.
9. **Physically inflate and seal balloons** — Air inflation, He fill, heat sealing — all manual operations.
10. **Perform leak tests** — Set up rig, inflate, monitor, record data. Requires physical presence.

## Estimated Effort

### Shakedown Flight (DecoGlee + Party He)

| Task | Effort | Dependency |
|------|--------|------------|
| Confirm/purchase heat sealer + Kapton tape | 1 day | None |
| Purchase party He | 1 day | None |
| Purchase non-magnetic weights | 1 day | None |
| Design + build cut-down mechanism | 1–2 days | None |
| Inflate + leak test 6 balloons (4 h each) | 1 day | Heat sealer, weights |
| Heat seal + Kapton tape 6 balloons | 2 hours | Heat sealer, Kapton tape |
| Measure free lift | 1 hour | Weights, scale |
| **Total (after purchases arrive)** | **~3–4 days** | Payload weight from circuit-design |

### Long-Duration Flight (Yokohama + He 4.6)

| Task | Effort | Dependency |
|------|--------|------------|
| Order Yokohama balloons | 1 day (order) + shipping time | None |
| Source He 4.6 supply | 1–2 days (research + order) | None |
| Purchase BMP280 + build rig | 2–3 days | BMP280 in stock |
| Flash pressure test firmware | 1 day | Firmware track |
| Humidify workspace | 24–48 h (passive) | None |
| Pre-stretch Yokohama (Steps 1–4) | 2–3 days (48 h hold + inflate/deflate) | Yokohama received, He 4.6 received |
| Inspect + refill + seal (Steps 5–7) | 4 hours | Pre-stretch complete |
| Free lift measurement (Step 8) | 1 hour | He 4.6, weights |
| Leak test at launch pressure (Step 9) | 2–24 hours | Rig built |
| **Total (after all hardware received)** | **~5–7 days** | Yokohama + He 4.6 + rig |

### Critical Path

Shakedown: **purchases → leak test → seal → free lift → launch** (~1 week after purchases)
Long-duration: **Yokohama shipping → He 4.6 sourcing → pre-stretch (48 h) → fill/seal → leak test → launch** (~2–4 weeks, dominated by shipping and He sourcing)

## Flash/RAM Budget

**N/A — physical preparation track.**

This track deals exclusively with balloon materials, inflation procedures, leak testing, and pressure validation. No firmware is written, no microcontrollers are programmed (the pressure test firmware belongs to the firmware track), no Flash or RAM is consumed by this track's work.

---

*Assessment prepared by the balloon-pre-stretching track agent. All data sourced from project documentation (`docs/balloon-test-results.md`, `docs/balloon-pressure-test.md`, `docs/balloon-options-analysis.md`, `docs/balloon-flight-lessons.md`) and community references (Ruthroff/KC9IKB, KI4MCW, K9YO, Klofas/KF6ZEO, Yokohama manufacturer).*