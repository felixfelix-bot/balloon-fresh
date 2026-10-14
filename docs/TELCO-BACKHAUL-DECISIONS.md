# Telco (4G/5G) backhaul for the base station — gap analysis, options, decisions

**Date:** 2026-10-14 · **Status:** decision paper (proposals, not authorisation)
**Operator decision-owner:** Felix
**Evidence:** `docs/analysis/telco-backhaul-gap-analysis.md`,
`docs/analysis/telco-fleet-reality.md`, `docs/analysis/telco-g1-g2-g3-services.png`,
`docs/analysis/telco-topology-options.png`

---

## 0. Answer up front

1. **Nothing is fabricated or ordered.** The base-station board has **no schematic,
   no netlist, no placement and no gerbers** — ADR-111 records that it "does not
   yet exist", and D14 is explicitly *"not a KiCad layout and not a purchasing
   authorization"*. **The fabricated-hardware sunk cost of adding cellular today
   is €0.** (The one exception is the hub-v9 boards, which are unrelated to this
   board and are separately blocked — see §7.)
2. **Yes — we can still easily add a more powerful power section.** There is no
   routed base-station PCB to re-spin. Not a single trace exists to rip up.
3. **The right architecture keeps the D14 freeze intact**: put the modem in an
   **adjacent box fed from `VIN_GS` (9–18 V)**, *not* from the 5 V rail. Then the
   entire frozen 5 V network (TPS62162, 316 mA, bias tee, AGC, LNA branch) is
   **untouched**, and the only change is a **power-entry specification addendum**
   — a second fused 12 V branch. Prose, not copper.
4. **All three modes A/B/C are supported — but they are three different services,
   and they must be built in a specific order.** See §3.

## 1. Your power question, answered precisely

**Is the base station routed yet?** **No.** Verified: no base-station
`.kicad_pcb` exists anywhere in the repo; `docs/BASE-STATION-PCBA-D14-FREEZE.md`
is a *part/network freeze note* that says so itself, and ADR-111 records the
board as non-existent. There are **zero traces to re-route and zero copper to
rip up.**

So there is nothing to "undo", and a stronger power section costs **design time,
not salvage**.

**Where the power actually binds (the consultant measured it):**

| Load | Draw | vs. the frozen budget |
|---|---:|---|
| Teltonika RUT241, idle + data, 12 V | **1.31 W** (109 mA @ 12 V) | ≈ +83 % on the design total |
| Teltonika RUT241, max | **3.28 W** (273 mA @ 12 V) | **exceeds the 0.5 A continuous allocation** |
| MikroTik LHG LTE kit (mast, Cat 4) | **max 6 W** | outdoor-rated, PoE-in 12–57 V |
| Teltonika RUTX50 (**5G**), idle | **4.73 W** | **≈3× the entire station budget, at idle** |
| Teltonika RUTX50, max 5G NSA | **16.21 W** (1351 mA @ 12 V) | **≈11× design total, ~3× the 1 A peak** |

**That table is the whole argument for feeding the modem from `VIN_GS` and not
from the 5 V rail.** Every candidate accepts 9–18 V directly. The D14 note itself
already flags this as the right place to solve it:

> *"the 18 V upper system input is therefore a system-level limit for this
> regulator selection and must be enforced by the upstream protection/entry
> specification."*

**⇒ Required change: an entry-spec addendum ("second fused branch, 12 V @ 3 A"),
not a board re-spin.**

## 2. The gaps (what does not exist today)

| # | Gap | State |
|---|---|---|
| G-A | No cellular anything on the station | **nothing** — no schematic, no BOM row, no ADR |
| G-B | No host CPU / OS / USB / PCIe on the PCBA | by design; the freeze is control/bias only |
| G-C | No station-to-station WAN sharing | unbuilt |
| G-D | No routing metric in the mesh | ADR-012 records **no cost/metric** |
| G-E | No service definition for the gateway | ADR-071 says so: "not recorded anywhere" |
| G-F | No power-entry branch for a modem | prose gap only — cheap now |
| G-G | No egress/reachability story under CGNAT | cellular gives **no public IP**; inbound SSH unreachable |
| G-H | Base-station board itself | **no layout exists at all** |

## 3. The three services (A / B / C) — and why the order matters

The consultant drew a distinction I had not: you described **G2 but in the
language of G1**. They are different services with different legal faces.

| | **G1 Access Gateway** | **G2 Backhaul Relay** | **G3 Egress Election** |
|---|---|---|---|
| What it is | users reach the internet *through* the balloon | **our** WAN shared station-to-station | which station is the WAN anchor |
| Who is the user | **third parties** | **our own devices** — your hotspot analogy | n/a |
| Stack layer | L7 TollGate over L4–L6 | L4 UDP/IP + L5 FIPS routing + NAT at A | L5 routing metric / policy |
| Hardware | every station needs its own uplink | **only the anchor needs a SIM** | **none — policy, not hardware** |
| Legal load | ISM duty ceiling + TKG service question | **none of those** | none |
| Cost | highest | low | **€0** |

**Your clarification — "we relay it from our device to our other device, like a
phone hotspot" — removes the hardest legal problem.** G2 is genuinely low-risk:
it is our own traffic over our own link. That also matches the consultant's
recommendation to **build G2/G3 before G1**, and it is why the legal question I
flagged earlier (whose traffic is on the licence-exempt link) now has a clean
answer: **ours.**

## 4. The new constraint the research found (add to the design of record)

**The 433 MHz downlink carries a 10 % duty-cycle ceiling** under the harmonised
standard (EN 300 220-2). The repo's licence-exempt design assumed a **~1.7 %**
beacon duty and had marked the Annex-1 row `TODO(unverified)`.

- A 1.7 % beacon is **fine** — no change to the beacon design.
- **But Service G1 relaying third-party traffic wants far more than 10 %.** So
  **the duty ceiling, not the EIRP, is what limits G1's capacity.** This belongs
  in the ADR-071 service definition.
- Caveat, stated honestly: EN 300 220-2 gives presumption of conformity; the
  binding German instrument is the **BNetzA Allgemeinzuteilung**, and the fetch
  for that row **404'd → still `UNVERIFIED`**. That one document would close it.

## 5. Recommendation

**R1 — Do not put cellular on the v1 PCBA.** Keep the D14 freeze verbatim. The
board is control/bias/telemetry by design and every cellular option is a
host-attached peripheral. Putting a host on it would force USB/PCIe routing, a
second switching rail, thermal relief, and almost certainly a layer-count change
→ a new freeze + new ADR + full ADR-111 gate re-run.

**R2 — Adopt an adjacent-box architecture, fed from `VIN_GS`.**
- **Mast/deployed station:** MikroTik **LHG LTE kit** — Cat 4, 17 dBi, outdoor,
  PoE-in 12–57 V, max 6 W, ~$179. Integral 17 dBi is the whole point in a field.
  Note its 16 MB flash / 64 MB RAM means it should be a *routed uplink, not a host*.
- **Bench / first build:** Teltonika **RUT241** — ≈€169.90, quietest idle of the
  family (1.31 W idle+data), RutOS + RMS remote management.
- **Nothing on the frozen 5 V network changes.** Add a fused 12 V branch to the
  entry spec.

**R3 — LTE Cat-4 now. Do NOT buy 5G.** The RUTX50 is ~11× the station budget at
max and ~3× at idle. Rural coverage favours LTE B20 (800 MHz), which the LHG
targets explicitly. 5G only if a station is ever asked to carry bulk third-party
traffic — which is exactly the G1 service ADR-071 has not yet defined.
Cat 1 bis is the right class *if* a custom control-plane board is ever built.

**R4 — Cellular on ANCHOR stations only, not one SIM per station.** Survey sites
with a handset (RSRP/SINR, band-locked) **before buying anything**. The cheapest
correct reading: (a) every station is already reachable through the balloon;
(b) an anchor with cellular becomes independent of any fixed line; (c) anchors
relay (G2) to the rest.

**R5 — Treat reachability as an OVERLAY problem, not a cellular one.** CGNAT
defeats DDNS and inbound IP, so the **station must dial out**. The fleet already
runs FIPS over IPv6 as the primary transport (measured: `peer_count 8`,
spanning-tree depth 4, every node reachable) — use it. NetBird exists on 4 of 7
nodes but is *metered* and declared retired as primary.

**R6 — Buy the four "preserve the option" items now, while they cost ~€0:**
(i) enclosure volume for the DNP row-18 box, (ii) a **fixed non-pointing mast
stub** for the LTE antenna (never put a 17 dBi panel on the positioner — that
re-derives the whole torque/wind budget), (iii) the 12 V entry branch in prose,
(iv) the masthead-vs-shack decision.

**R7 — Order the work G2/G3 before G1.** G2 + G3 is the half that makes "stations
work anywhere" true, at low legal risk and with €0 of routing hardware.

## 6. Data cost — the arithmetic that matters

1NCE IoT Lifetime Flat is **€12 for 10 years incl. 500 MB** (MEASURED). But
**that is not an always-on data plan**: 500 MB per day for 10 years would be
137 kB/day, i.e. keepalives only. **Design rule: budget the SIM per station
role** — G2 anchors get a real volume plan; leaves and telemetry-only stations
get the €12 lifetime flat.

## 7. Separately blocked (not part of this gap)

The **hub-v9 flight board does not route** (43/49 nets, 43 → 816 DRC violations
against frozen rules; root cause: 2582 mm² of courtyard needed vs 2475 mm²
available → 104 %). It also has **5 netlist parts with no part selected**
(`U_CUT1–4`, `U_HUB_CVT` → `TODO(unverified)`). **v9 cannot be ordered.** See
`docs/fab/hub-v9/ROUTING-BLOCKER.md`. That is a geometric decision awaiting the
operator (enlarge outline / cut D8 nested dual / select-or-DNP those parts) and
is **independent** of the telco question.

## 8. Corrections made to this analysis (honesty log)

- My brief claimed **"the only LTE device in the fleet is a modem in a laptop."**
  **That was wrong.** The fleet-reality consultant measured **two** modems: the
  Sierra EM7455 (CobradorWave, `sim-missing`, no wwan0) **and a Fibocom
  L830-EB-00 on x280** with a registered `wwan0` and `/dev/cdc-wdm1`. Neither has
  a working data path or any cellular config, so the conclusion ("no
  station-ready cellular capability") stands — but the count was wrong.
- My earlier framing that OpenRouter needed a code change was wrong (it already
  reads the key from the OpenBao env); and I claimed the deepinfra lane needed
  two changes when the disable flag was already cleared.
- **UNVERIFIED items carried forward:** Starlink pricing (JS-only page, zero
  numbers fetchable), German MNO/MVNO tariffs and resale clauses, APN IPv4/IPv6
  allocation, BNetzA 433 MHz Allgemeinzuteilung row (404), LHG mass.
