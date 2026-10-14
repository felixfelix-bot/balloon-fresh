# Telco (4G/5G) backhaul for the balloon base station — gap analysis & options paper

**Date:** 2026-10-14
**Author:** Hermes subagent (delegated consult)
**Inputs (design of record — cited, not re-derived):** `/home/c08r4d0r/CONSULT-BRIEF-telco-backhaul.md`;
`docs/adr/071-ground-station-gateway-design-basis.md`; `docs/adr/072-band-split-duplex-two-antennas-no-circulator.md`;
`docs/adr/100-tollgate-over-fips-mesh-udp.md`; `docs/BASE-STATION-PCBA-D14-FREEZE.md`;
`docs/BASE-STATION-BOARD-CHECKLIST.md`; plus `docs/LINK-BUDGET-LICENCE-EXEMPT.md`,
`docs/licence-exempt-design-point.md`, `docs/analysis/PROGRAM-GAP-ANALYSIS-ROUND2.md`,
`docs/adr/012-mesh-networking-strategy.md`, `docs/adr/016-fips-implementation-keep-cpp-microfips.md`,
`docs/adr/111-canonical-board-production-order.md`

**Evidence tags used throughout:** **MEASURED** (read directly from a source I fetched this session, or from the repo's own frozen document)
· **MODELLED** (arithmetic over MEASURED inputs, shown)
· **GUESSED** (engineering estimate, no source — derivation shown)
· **UNVERIFIED** (could not confirm; the source that would settle it is named).

---

## 0. Verdict first (the five sub-questions, answered in one page)

| # | Question | Answer |
|---|---|---|
| 1 | Fit with existing plans? | Cellular backhaul **extends ADR-071, it does not contradict it.** It is orthogonal: a *third* antenna outside the duplex path, and a transport *below* L4 in the ADR-100 stack. But it **creates a commercial tension** with ADR-071 that must be decided, not ignored (§3.2). |
| 2 | Too big for the current base station? | **Yes — categorically.** The v1 PCBA has no host CPU, no OS, no networking, no USB/PCIe host, and a 5 V budget of 316 mA design / 0.5 A continuous. Every cellular option in the market is a *host-attached peripheral*. Cellular cannot be "added to" this board; it can only be an **adjacent box** or a **v2 architecture that adds a host** (§4). |
| 3 | Sunk cost of introducing it now? | **≈ €0 of fabricated hardware — nothing is ordered** (BS-01: no schematic, netlist or gerber exists; D14 is explicitly "not a KiCad layout and not a purchasing authorization"; ADR-111 states the base-station board "does not yet exist"). The real exposure is **scope creep in a gate-chained pipeline** plus four irreversible commitments. Adding telco *as an external box* re-spins **nothing**. Adding it *to the PCBA* forces a new freeze, a new ADR, and a board-class change (§4.3). |
| 4 | Options, cost, tradeoffs? | Six ranked options, §5. **Rank 1: an industrial LTE router as a separate station box — Teltonika RUT-class, or better for a mast, a MikroTik LHG LTE kit (Cat 4, 17 dBi, PoE-in, 6 W max, $179 suggested).** |
| 5 | Is 5G worth it? | **No.** A 5G router's *idle* draw (RUTX50: 4.61–4.81 W MEASURED) is **3× the entire current ground-station budget at idle**; peak 5G NSA is 15.7–17.5 W = **~11×**. And 5G's 2.4 Gbps is ~1000× the balloon link's legal/capability ceiling. **LTE Cat-4 is the usable ceiling; Cat-1 bis is sufficient for control-plane.** |

---

## 1. What the design of record actually fixes (so this paper does not re-derive it)

- **ADR-071 D1** — the ground station is "a full-duplex **INTERNET GATEWAY** through the balloon as a bent pipe"; users reach the internet *through* the balloon.
- **ADR-071 D2 / ADR-072 D1** — the duplex path is **two band antennas, no circulator, no T/R switch**; station RX = 433 MHz, station TX = 2.45 GHz, both live simultaneously (INV-1 forbids anything time-shared in that path).
- **ADR-071 §Costs/risks** — *"The uplink is EIRP/PSD-capped under licence-exempt rules, which caps the service radius; 'Internet gateway' is therefore a **local** service on the ISM footing, not a long-range one."*
- **ADR-071 §Open items** — *"A service definition (number of users, duty cycle, availability) is **not recorded anywhere** in this set."* ← **this is the hole cellular backhaul walks into** (§3.2).
- **ADR-100 / ADR-012** — the balloon (and the ground station) carry: L1 LR2021 → L2 TDMA dual-band → L3 erasure-coded fragmentation → **L4 UDP/IP tunnel → L5 FIPS mesh routing → L6 FIPS Noise XK → L7 TollGate + Nostr**. ADR-100 D1: *"TollGate communicates via UDP over the FIPS mesh transport layer, not via direct LR2021 radio access."*
- **D14 freeze** — board-own parts are the RP2040 (QFN-56), AD8318, ADL5240, ZFBT-4R2GW+ bias tee, TPS62162 5 V buck. Rail budget **316 mA design total, ≥ 0.5 A continuous / 1 A peak**; TPS62162 rated 3–17 V in / 1 A out; the note itself flags that the 18 V system input "is therefore a system-level limit … and must be enforced by the upstream protection/entry specification".
- **ADR-111** — the board pipeline is a **strict sequential gate chain** (logical definition → form factor → deterministic placement → **BLOCKING** human+Astra placement gate → routing → **BLOCKING** DRC gate). Changing what the board *is* mid-chain is the single most expensive thing that can happen to it.
- **Repo-wide telco search: nothing.** No LTE/SIM/Quectel/cellular row in any BOM, ADR or analysis (brief §"Repo state for cellular"). The only cellular object in the fleet is an LTE modem in a laptop — a host device, not a station part.

---

## 2. The two distinct services hidden in the operator's one sentence

The operator wrote: *"so that they can function anywhere without needing to have a separate internet gateway. Ideally the balloon / bent pipe is able to relay internet from a base station that has good cellphone reception to a base station that doesn't."*

That sentence contains **three** different things. Naming them is the core of the answer to question (c).

| | **G1 — Access Gateway** | **G2 — Backhaul Relay (WAN sharing)** | **G3 — Egress Election** |
|---|---|---|---|
| **Who is the user?** | a **third party** (a person/device at the station) | the **operator's own** remote station | the **mesh** as a whole |
| **Path** | user → station RF → balloon → station RF → internet | station B (no uplink) → balloon → station A (has uplink) → internet | which station is A, and when it changes |
| **Where does it live in the stack?** | L7 (TollGate) over L4/L5/L6 | L4 (UDP/IP tunnel) + L5 (FIPS routing) + a NAT/egress at A | L5 routing metric / policy |
| **Exists in the repo?** | **Yes** — ADR-071, ADR-100, ADR-012 L7 row | **No.** No design, no ADR, no metric | **No** |
| **Legal face** | *offering a telecom service to third parties* | *self-provisioning / extending your own network* | of the two, whichever applies at A |
| **Does cellular change it?** | It competes with it (see §3.2) | **It is what makes it possible** | It is what makes it *useful* |

**Plainly: the operator is asking for G2 but described it as if it were G1.** They are not the same service, they have different legal faces, and **G2 is the one worth building first**: it is the low-risk, high-value half, and it is what actually makes *"stations work anywhere"* true. Note also that **G3 is not hardware** — it is a routing metric, and it is the piece that decides whether "relay from a good-reception station to a bad one" happens *by design* or *by accident*. See §6.2.

### 2.1 Is the answer to "SSH into a remote station" the same layer? Yes — and it is already designed

`docs/adr/012-mesh-networking-strategy.md` lists the ground station as: *"Minimal: ESP32-C3 + LR2021 [or] Full: Raspberry Pi / SBC + LR2021 — Full FIPS daemon + strfry relay + tollgate-module-basic-go on OpenWRT + WiFi AP"*. So **the repo already anticipates an SBC at the station for the "full" option.** That SBC is the host a cellular modem needs — and it is *already* a documented option. This matters for option ranking (§5, option 2).

**Honest contradiction found in the repo, relevant here.** ADR-016 says *"**microfips** (`github.com/Amperstrand/microfips`) — **C++** implementation using mbedtls + micro_ecc"* and decides to keep C++. But ADR-012 lists the same component as **Rust**, and the GitHub API reports `Amperstrand/microfips` as **language: Rust, 2 stars, MIT, description "Minimal FIPS leaf node on STM32F469"** (MEASURED, `https://api.github.com/repos/Amperstrand/microfips`). Two records in the same tree disagree about the *language of the ground segment's mesh overlay*. Per the repo's own rule (a contradiction that names no winner is a **DEFECT**), this is flagged here and not resolved. It matters because a cellular backhaul adds a **second transport underneath the same overlay**, and you cannot design that without knowing what the overlay actually is.

Also MEASURED: `jmcorgan/fips` — "The Free Internetworking Peering System", **Rust, MIT, 270 stars** (`https://api.github.com/repos/jmcorgan/fips`). Note ADR-012 says FIPS = "Free Internetworking Peering System" while ADR-016 glosses it as "Federated Identity and Privacy Session" — a second, smaller naming inconsistency.

---

## 3. (a) Does cellular backhaul contradict or extend ADR-071?

### 3.1 Technically: it extends. Provably.

ADR-071's invariants are about **the duplex path** (INV-1: nothing in the duplex path is time-shared; INV-2: RX 433 / TX 2.45 GHz; INV-3: the balloon is a bent pipe; INV-4: one positioner carries both band antennas).

A cellular WAN:
- puts **nothing** in the duplex path → INV-1, INV-2 untouched;
- does not touch the balloon relay → INV-3 untouched;
- needs a **third antenna, which must NOT be a positioner load** (the cell tower is fixed while the balloon moves — see §5.7) → INV-4 is satisfied by *not* using the positioner, and ADR-071 D3 is not violated. **I recommend an explicit note be added to ADR-071/072 rather than a new ADR, because no invariant changes.**

### 3.2 Commercially: it collides, and the collision is the real decision

ADR-071's whole justification is *"ground users reach the Internet **through the balloon**"*. If a station has its own cellular internet, then for any local user **the shortest, cheapest, lowest-latency path to the internet is the cell modem — not the balloon.** The balloon becomes a detour. That is not a technical contradiction; it is a **business-model contradiction**, and ADR-071 already has the hole that exposes it: *"A service definition (number of users, duty cycle, availability) is not recorded anywhere in this set."* With no service definition, there is nothing to say whether the balloon's service and a cell modem's service compete or complement.

**Therefore the framing I recommend, and it is the paper's most important qualification:**

> **Cellular backhaul should back the *station* (control plane, telemetry, mesh egress), not the *user*.** The station's cellular WAN is a service-vehicle for G2/G3 and for SSH/management — it is not a second user-facing gateway competing with G1. If it is used to serve users directly, ADR-071's economic rationale must be re-argued, and TollGate's reason to exist at that station disappears.

This is also the honest answer to "does it contradict": **ADR-071's *text* survives; ADR-071's *unstated business case* does not survive in places where a cell tower exists, unless the "station-only" framing is adopted explicitly.**

### 3.3 Where the backhaul attaches — the layer, precisely

In the ADR-100/012 stack, cellular is **a second L1/L2 under the same L4 UDP/IP tunnel**:

```
L7  TollGate + Nostr                       <- unchanged
L6  FIPS Noise XK                          <- unchanged (this is what keeps the relay private)
L5  FIPS mesh routing                       <- NEEDS A COST/METRIC (G3 gap, §6.2)
L4  UDP/IP tunnel                           <- UNCHANGED INTERFACE (this is the key finding)
---- transports under L4 ----
      (a) LR2021 dual-band TDMA   (existing, ADR-100)
      (b) cellular IP (this proposal)  <- NEW, and it is *only* a transport
```

There is no L7 change, no TollGate change, and no FIPS-crypto change. **The clean integration point is the L4 UDP socket**, exactly as ADR-100 D1 already frames TollGate. That is why this is a *small* change architecturally and a *large* change electrically (§4).

---

## 4. (b) Is it too big for the current v1 PCBA? And what is the sunk cost?

### 4.1 Yes. Categorically, and here is the mechanical reason

The v1 PCBA owns: AD8318 log detector, ADL5240 VGA, RP2040 QFN-56 (SPI + one ADC), ZFBT-4R2GW+ bias tee, TPS62162 5 V buck. Its *own* freeze note says the board "does not add a 2.4 GHz PA, and it does not attempt to put the masthead LNA on the PCBA" — i.e. **the board is deliberately scoped to control/bias/telemetry only.**

Every cellular option in the market is one of: (i) a USB device, (ii) an M.2/PCIe device, (iii) an Ethernet device with its own OS. Category (i) and (ii) require a **host** (which the board does not have and its MCU cannot be — an RP2040 cannot enumerate a USB LTE modem and drive a NAT/firewall/tunnel stack, and it has no PCIe). Category (iii) requires **only an Ethernet or nothing at all** — this is why the router option wins (§5.1).

So the question "does it fit on v1?" has a flat answer: **no option fits on the PCBA.** The real question is "adjacent box or new architecture", and that is §4.3.

### 4.2 The power number, which is the second flat answer

The station's 5 V rail (MEASURED, D14 freeze): **316 mA design total = 1.58 W**, budgeted for **≥ 0.5 A continuous (2.5 W) / 1 A peak (5 W)**.

| Load | MEASURED draw | As 5 V-bus current (MODELLED, excl. converter loss) | Effect on the frozen budget |
|---|---|---|---|
| Teltonika RUT241, idle + mobile data, 12 V | **1.31 W** (109.3 mA @ 12 V) | ≈ 262 mA | **+83 % on the design total** |
| Teltonika RUT241, max (2 LAN + max-speed LTE + WiFi), 12 V | **3.28 W** (273.3 mA @ 12 V) | ≈ 656 mA | **exceeds the 0.5 A continuous allocation**; 66 % of the 1 A peak |
| Teltonika TRB140, idle no SIM / max, 12 V | 0.72 W / 3.89 W | ≈ 144 mA / 778 mA | same class of problem |
| MikroTik LHG LTE kit (outdoor CPE) | **"Max power consumption 6 W"** | ≈ 1200 mA | **exceeds the board's continuous *and* leaves nothing of the peak** |
| Teltonika RUTX50 (5G), **idle**, 12 V | **4.73 W** | ≈ 946 mA | **3× the entire station budget, at idle** |
| Teltonika RUTX50 (5G), **max 5G NSA**, 12 V | **16.21 W** (1351 mA @ 12 V) | ≈ 3242 mA | **~11× the design total; ~3× the 1 A peak** |

Sources (all MEASURED this session, vendor wiki tables):
`https://wiki.teltonika-networks.com/view/RUT241_Power_Consumption` ·
`https://wiki.teltonika-networks.com/view/TRB140_Power_Consumption` ·
`https://wiki.teltonika-networks.com/view/RUT956_Power_Consumption` ·
`https://wiki.teltonika-networks.com/view/RUTX50_Power_Consumption` ·
`https://mikrotik.com/product/lhg_lte_kit`

**Conclusion (MODELLED from MEASURED): any cellular option more than doubles the station's power budget, and every option except a low-power Cat-1 modem exceeds the board's 0.5 A continuous allocation on its own.**

### 4.3 The right topology — and it costs the frozen board exactly nothing

**Feed the modem from `VIN_GS` (9–18 V nominal), not from the 5 V rail.** Every candidate accepts that range directly:

- Teltonika RUT241 / TRB140: 9–30 V class (the vendor's own consumption table is measured at 9 / 12 / 24 V — MEASURED).
- MikroTik LHG LTE kit: **PoE-in 802.3af/at, 12–57 V** (MEASURED, MikroTik spec page) — one cable carries **data + power**, max 6 W.

Under this topology **nothing in the D14-frozen 5 V network changes**: TPS62162, the 316 mA budget, the ≥0.5 A/1 A copper budget, the bias tee, the AGC chain, the LNA branch — all untouched. What *is* added is **a second load on the protected entry** (`VIN_GS`), which the freeze note itself already frames as an upstream specification issue ("the 18 V upper system input … must be enforced by the upstream protection/entry specification"). So the required change is **an entry-spec addendum**, not a board re-spin.

### 4.4 Sunk cost, quantified: now vs after order

**MEASURED state of the program (from the repo, cited):**
- `docs/analysis/GAP-TRACKING-CHECKLIST.md` row **BS-01**: *"The base-station board does not exist. No schematic, netlist or gerber for the control/bias/telemetry board on any ref; the checklist is explicitly 'a document, NOT a KiCad layout'."* Status: **OPEN**.
- `docs/PROGRAM-BOARD-COMPLETION-PLAN.md`: base station = **"NO — no schematic, netlist or gerber on any ref"**, and the base-station card is in *triage*/ *todo*.
- `docs/adr/111`: *"Two required boards (base-station, bench-rig) **do not yet exist**."*
- `docs/BASE-STATION-PCBA-D14-FREEZE.md` header: *"**not** a KiCad layout and **not** an operator purchasing authorization."*

**⇒ No base-station hardware has been fabricated or ordered. The fabricated-hardware sunk cost of adding cellular today is €0.**

The genuine cost of "adding it now" is therefore **not a re-spin — it is a pipeline stall**, plus four *irreversible commitments* that get expensive later:

| # | Commitment | State today | Cost if decided NOW (adjacent-box route) | Cost if decided AFTER v1 order |
|---|---|---|---|---|
| 1 | **PCBA class** (2-layer control/bias board vs host-carrier board) | not designed; D14 freeze is a *part* freeze only | **€0** — keep telco off the board; D14 stands verbatim | **A new board.** A host (SBC or M.2 carrier) forces USB/PCIe routing, a second switching rail, thermal relief and almost certainly a layer-count change → **new freeze + new ADR + new placement gate (ADR-111 stage 4) + new DRC gate.** Cost: a full re-run of the ADR-111 chain, plus the design work already sunk on the current freeze premise |
| 2 | **Enclosure** | row 18 is **DNP / out-of-scope**; no mechanical BOM frozen (D14). A printed-enclosure line exists (`hardware/enclosure/balloon-field-case.scad`, `balloon-field-case-bigradio.scad`, `bottom.stl`, `lid.stl`) | **≈ €0 extra design** — add volume + penetrations + a DIN-rail/lid boss for a router and a small SBC while the STL is still being authored. **GUESSED** filament material cost of the extra volume ≤ €20 | **A re-print.** New STL, new gasket, new print, re-weatherproofing. **GUESSED** €20–60 material + 1–2 days print/assembly, and a *second* weatherproofing validation |
| 3 | **Mast / positioner** | ADR-076/077/078 unmerged; ADR-077 = printed structure + bought self-locking worm gearing + NEMA23; hierarchy already named the binding constraint: *"The positioner spec is therefore **stiffness and holding torque**, not speed"* (`PROGRAM-GAP-ANALYSIS-ROUND2.md` §6) | **≈ €0 extra** *if the LTE antenna goes on a separate, non-pointing stub* (§5.7). Add the stub to the mast spec now | **Expensive if got wrong.** Putting a 17 dBi LHG-class panel (391 mm dish, ~2 kg class — **UNVERIFIED**, vendor page states 17 dBi but I did not fetch mass) **on the positioner** changes the torque and wind-load budget → re-derive ADR-076/077/078 and possibly the whole positioner class |
| 4 | **Power entry spec** | `VIN_GS` 9–18 V, protected, upstream limit already flagged in D14 | **Free now** — write "second fused branch, 12 V @ 3 A" into the entry spec while it is still prose | Cheap to patch later (it is external wiring), but it will be discovered during bring-up, mid-campaign, with the field case already built |

**The one-line sunk-cost answer:** *because nothing is ordered, adding cellular as an external box today costs zero fabricated hardware and preserves every option; adding it **to the PCBA** would invalidate the D14 freeze and re-run the ADR-111 gate chain; and the changes that are genuinely cheap now and expensive later are (i) enclosure volume, (ii) the mast stub, (iii) the power-entry branch, (iv) the masthead-vs-shack split.*

### 4.5 The decision the telco requirement forces, that is already overdue

`PROGRAM-GAP-ANALYSIS-ROUND2.md` **MECH-01** (OPEN, critical): *"a masthead LNA, a DSA, a log detector, an ADC/MCU and a bias network all want to be at the masthead, while the control PC wants to be indoors … an argument for splitting the 'base-station board' into a MASTHEAD RF/bias/telemetry board plus a SHACK controller board — a decision … that must be made **before the board is designed**."*

**Cellular backhaul forces this decision, decisively**: a modem cannot go at the masthead (RF exposure, weather, cable loss, no need) and a host cannot go unenclosed in the weather. So the telco requirement is not merely compatible with MECH-01 — **it settles it: masthead = RF + bias + AGC; shack = host + modem + power.** And MECH-01 is free to decide today and expensive to decide after the board is laid out. **Recommendation: decide MECH-01 now (masthead/shack), and note that cellular backhaul is the second independent reason for it.**

---

## 5. (c) Telco options — ranked, with real numbers

Prices are **EUR where I fetched a German/EU price**, USD where the vendor quotes USD. Neither the operator's VAT status nor shipping is included. Where I could not fetch a price, it says so.

### 5.1 **RANK 1 — Industrial LTE router as a separate station box** ⭐ recommended

**What it is.** A self-contained, mains/DC-powered router with its own OS, firewall, NAT, VPN client, watchdog and remote management. Nothing is added to the PCBA; it consumes one Ethernet port and one DC branch.

| Candidate | Key specs (MEASURED) | Price | Power | Why / why not |
|---|---|---|---|---|
| **MikroTik LHG LTE kit** (RBLHGR&R11e-LTE) | LTE **Cat 4**, 150/50 Mbit/s; bands **1, 2, 3, 7, 8, 20, 38, 40**; **17 dBi** high-gain CPE; **outdoor** pole/mast mount; **PoE-in 802.3af/at, 12–57 V**; 1× Ethernet; →40…+50 °C tested ambient; 16 MB flash / 64 MB RAM | **$179.00 suggested price** (vendor spec page) | **max 6 W**, passive cooling | **Best fit for a mast station.** Outdoor-rated, integral 17 dBi gain (the whole point for rural), **single-cable PoE** (data+power), Cat 4 is already ≥50× the balloon link, 6 W is manageable. **Drawback:** 16 MB flash / 64 MB RAM limits on-box agents — plan on the *uplink being routed, not hosted*. Source: `https://mikrotik.com/product/lhg_lte_kit` |
| **Teltonika RUT241** | LTE Cat 4, industrial DIN-rail class, 2× Ethernet, Wi-Fi, RutOS, **RMS** remote management | **€169.90** (Amazon.de third-party listing, MEASURED; other marketplace offers €219.90 / €332.10 — the price spread is real and worth shopping) | **1.05 W** idle no-SIM @9 V; **1.31 W** idle+data @12 V; **3.24–3.31 W** max | **Best fit for the bench / first field build.** Quietest idle of the family, cheap, huge ecosystem, and Teltonika's own wiki publishes the consumption table (rare and useful). **Drawback:** indoor/industrial enclosure, not a masthead device. Sources: `https://teltonika-networks.com/products/routers/rut241`, `…/wiki/…/RUT241_Power_Consumption` |
| **Teltonika TRB140** | LTE **gateway** (not a router) — 1× Ethernet, DIN rail, no Wi-Fi | not fetched (UNVERIFIED) | **0.70 W** idle / **1.15 W** idle+data / **3.87 W** max (MEASURED) | The **lowest idle draw** of anything credible. If the job is "give the station one IP path", this is the minimal device. Sources: `…/wiki/…/TRB140_Power_Consumption` |
| Teltonika RUT956 | LTE + Wi-Fi + GNSS + serial + I/O | not fetched (UNVERIFIED) | 1.45 W idle / **10.26–11.30 W** max | **Ruled out** — the max case includes a 500 mA USB device; the idle is 1.4× RUT241 for features this use case does not need. `…/wiki/…/RUT956_Power_Consumption` |
| MikroTik Chateau LTE7 | indoor, mains, Cat 7 | **$119 suggested** (MEASURED) | **max 20 W** (14.1 W without attachments) | **Ruled out for this station** on power (20 W) — but the price datapoint is useful. `https://mikrotik.com/product/chateau_lte7` |

**Licencing:** none for the station (the MNO's licence covers the radio). Certification: a CE-marked router is already compliant; a *self-built* module carrier is not (see §5.4).
**Failure modes:** modem firmware regression (catastrophic in the field); CGNAT losing reachability (see §6.3); watchdog/reboot loop on a weak signal; PoE injector as a new single point of failure; SIM tray corrosion; **RutOS/RouterOS devices are actively attacked on the open internet — see §6.4.**
**Complexity:** **lowest of all options** — a known-good OS, a web/SSH UI, an update mechanism, and no host to maintain.

**Rank 1 verdict:** *an external router is the only option that changes nothing in the design of record, brings its own OS and update path, and can be unplugged and replaced in the field.* Between the two leaders: **MikroTik LHG for the deployed mast station (outdoor, PoE, 17 dBi); Teltonika RUT241 for the bench and the first build (cheap, quiet, documented).**

### 5.2 **RANK 2 — M.2 / NVMe LTE or 5G module + carrier board + SBC**

**What it is.** A bare module (M.2 or LCC) on a carrier, hosted by a Linux SBC. This is the route ADR-012 already contemplates for the "Full" station: *"Raspberry Pi / SBC + LR2021 — Full FIPS daemon + strfry relay + tollgate-module-basic-go."*

| Part | Specs (MEASURED) | Price | Note |
|---|---|---|---|
| **Quectel EC25** (LTE Cat 4, LCC) | Cat 4, **150/50 Mbit/s**, LCC **32.0 × 29.0 × 2.4 mm**, −40…+85 °C | not fetched (UNVERIFIED; distributor pages were bot-blocked) | The safest LTE workhorse if a custom board is ever made. `https://www.quectel.com/product/lte-ec25-series/` |
| **Quectel RM520N** (5G NR Sub-6, M.2) | M.2 **30 × 52 × 2.3 mm**; **SA 2.4 Gbps DL / 900 UL; NSA 3.4 / 550**; 3GPP Rel-16; −40…+85 °C | not fetched (UNVERIFIED) | The 5G reference module. `https://www.quectel.com/product/5g-rm520n-series/` |
| **Waveshare SIM7600E-H 4G DONGLE** | SIM7600 = LTE Cat 4, USB dongle, GNSS, **5 V DC input** | **$87.99** | See §5.3. `https://www.waveshare.com/sim7600e-h-4g-dongle.htm` |
| **Waveshare SIM8200EA-M2 5G HAT** (whole 5G stack for a Pi) | 5G Sub-6, Snapdragon X55, **6× IPEX-4** antennas, **5 V 3 A** supply | **$289.99 — listed DISCONTINUED** | Two findings: (a) 5 V/3 A = a 15 W provisioning requirement on a rail that is budgeted **0.5 A**; (b) **the hobbyist 5G path is being discontinued**, which is a supply-continuity risk for a long-lived station design. `https://www.waveshare.com/sim8200ea-m2-5g-hat.htm` |

**Host power, which is the disqualifier:** Raspberry Pi 4 requires a "5 V at 3 A" supply (MEASURED, `https://datasheets.raspberrypi.com/rpi4/raspberry-pi-4-datasheet.pdf`); Raspberry Pi 5 requires **5 V/5 A** via USB-C (MEASURED, `https://datasheets.raspberrypi.com/rpi5/raspberry-pi-5-product-brief.pdf`, list $45–$305 by RAM). **Both exceed the station's 1 A peak budget several times over.** Adding an SBC means adding a *second, much larger* power supply — i.e. a new architecture (§4.3), not an add-on.
**Licencing:** the module's own regulatory approval does **not** transfer to your carrier board. A self-integrated modem needs its own RED/CE conformity assessment — a real, named cost centre (UNVERIFIED magnitude).
**Failure modes:** USB/M.2 enumeration failures across thermal cycles; missing band-lock support (see §5.6); host OS updates breaking the modem stack; SD-card corruption (a classic unattended-site failure).
**Complexity:** **high** — a second OS, a second update path, a second failure domain, and a power architecture change.

**Rank 2 verdict:** *right only if the station needs an SBC anyway* (ADR-012's "Full" option, strfry/TollGate hosting). If the SBC is being bought *for the modem*, that is backwards — buy the router.

### 5.3 **RANK 3 — USB LTE dongle + SBC**

Cheapest capex (**$87.99** MEASURED for the Waveshare SIM7600E-H dongle, 5 V input). But: USB bus resets and dongle hangs are the **classic** unattended-site failure; thermal droop in a sealed case is worse for a bare dongle than for a router; there is no remote management of a dongle; and it needs the SBC (so it inherits all of §5.2's power/complexity). Also needs careful RF layout: a dongle's pigtail antenna next to the station's 2.4 GHz TX (§5.7).
**Rank 3 verdict:** *a legitimate cheap field experiment and a good signal-survey accessory. Not a station design.*

### 5.4 **RANK 4 — Integrated 5G module on a custom board (Quectel RM5xx / SIMCom)**

This is "put the modem on our board". By §4.1 it cannot be the v1 PCBA. It implies: a 4-layer mixed-signal board with an M.2/LCC footprint, USB 2.0/3.0 or PCIe routing, a 5 V/3 A switching rail, 4 antenna ports with IPEX→SMA pigtails, thermal relief, and a **new CE/RED conformity assessment**. It also locks the station to one module's band set. **Rank 4 / defer to v2 or never** — the router in Rank 1 delivers the same function with an off-the-shelf certified enclosure and OS.
*Named supply risk:* the closest hobbyist precedent (Waveshare's 5G HAT) is **DISCONTINUED** (MEASURED). *Pointer for the low-power direction:* Quectel's Cat 1 bis line (`https://www.quectel.com/lte-cat-1-bis-modules/` — linked from the fetched EC25 page) is the correct module class if a custom board is ever justified, because Cat 1 bis is ~20 Mbit/s down, single antenna, far lower burst current — *exactly* the class for a control-plane-only station. I did not fetch a Cat 1 bis datasheet or price: **UNVERIFIED**.

### 5.5 **RANK 5 — Phone-as-hotspot / tethered handset**

Not verified against any source (no price, no spec claims made here). Its real value is **not as a station design** but as: (a) a zero-cost **signal survey tool** — walk the site, measure RSRP/SINR before buying anything; (b) a fallback if a router fails in the field. **Rank 5 / tool, not architecture.** *(A handset also adds an obvious safety and security objection that a router does not.)*

### 5.6 **5G vs LTE — the explicit answer: LTE Cat-4 is the rational ceiling; Cat-1 bis is enough for control; 5G is not worth it here.**

Four independent reasons, in order of force:

1. **Power is decisive.** RUTX50 (5G) **idle** = 4.61–4.81 W (MEASURED). The entire current ground station is 1.58 W design. **A 5G router idles at 3× the station.** Peak 5G NSA = 15.68–17.45 W ≈ **11× the station design total** and ~3.5× its 1 A peak. By contrast RUT241 **idle + active mobile data = 1.31 W**. There is no engineering case for spending 3.6× the idle power.
2. **Bandwidth is 1000× oversubscribed.** 5G offers 2.4 Gbps DL (RM520N, MEASURED). The balloon link's own recorded ceiling is FLRC ~2.6 Mbps (ADR-081/082), and its *uplink* is legally EIRP/PSD-capped. Even the *aggregate* of every station the balloon can serve fits in **LTE Cat-1 bis (~10–20 Mbit/s)** with room to spare. Buying 5G is buying capacity that is discarded at the first hop.
3. **Air-interface complexity costs you antenna and band-lock control.** 5G front ends want more antennas (4×4 MIMO; the Waveshare 5G HAT carries **6× IPEX-4** — MEASURED) and the NSA path still requires an LTE anchor. More RF hardware on a mast whose binding constraint is already wind load and stiffness (`PROGRAM-GAP-ANALYSIS-ROUND2.md` §6).
4. **Rural coverage and price.** 5G NSA/SA coverage in rural Germany is materially thinner than LTE; a mast station in a field is exactly the deployment where LTE B20 (800 MHz) is the band that works, and the LHG explicitly targets it (bands 1,2,3,7,8,**20**,38,40 — MEASURED). 5G hardware costs 2–4× on the datapoints I could fetch (5G HAT $289.99 vs 4G dongle $87.99; Chateau LTE7 $119 vs RUTX50 price UNVERIFIED).

> **Answer: 5G is NOT worth it here. LTE Cat-4 (in a router) is the right class today; LTE Cat-1 bis is the right class if a custom board is ever built for a control-plane-only station. 5G should be re-considered only if a station is ever asked to carry *bulk third-party* traffic, which is precisely the G1 service ADR-071 does not yet define.**

### 5.7 Antenna coexistence — the honest engineering read

**The RF case is favourable, and for a specific reason worth writing down.** On the ground station the only *sensitive* receiver is at **433 MHz** (ADR-071 INV-2). The nearest LTE uplink allocations in Germany (B20 UL 832–862 MHz; B8 UL 880–915; B1 UL 1920–1980; B3 UL 1710–1785; B7 UL 2500–2570) are hundreds of MHz above it, and **ADR-072 INV-3 already requires a 433 MHz BPF before the LNA** with a checklist verification that it "reject **2.45 GHz by ≥ 40 dB**" (row 2, `BASE-STATION-BOARD-CHECKLIST.md`). A BPF that rejects 2450 MHz by 40 dB rejects 832–1980 MHz by *at least* as much. The station's own **2.4 GHz path is transmit-only**, so the classic self-desense problem (ADR-072's residual-hazard analysis) does not gain a new term from a cell modem.

**The real risks are mechanical, and they are named in the repo already:**
- Mast wind load and positioner stiffness are the *binding* constraints (ROUND2 §6). **Do not put the cellular antenna on the positioner** — the cell tower is fixed, the balloon moves; the antenna must be on a **separate fixed stub below the rotator**. This also keeps ADR-071 INV-4 (one positioner carries the two band antennas) literally true.
- Cable handling over the rotation range (ROUND2 §6 already flags loop vs slip ring). A third cable run must be routed to *not* cross the rotator.
- **Two things to check before buying:**
  - **450 MHz-class cellular (LTE B31 / NR n31) sits only ~15–66 MHz above the 433 MHz SRD band.** If any such network is deployed in the area, a 433 MHz BPF's stopband matters near-band, not just at 2.4 GHz. **UNVERIFIED for Germany** — the check is a 450 MHz deployment list plus, if any, a measured 433-BPF stopband sweep (the LiteVNA 62 in checklist row 13 already does this).
  - **B40 (2300–2400 MHz) / B7 UL (2500–2570) sit immediately around the 2.4 GHz ISM uplink.** Ground-side this is TX-only, so it is a *regulatory* and *balloon-side* coexistence question, not a station desense question. **UNVERIFIED magnitude**; the check is the same end-to-end desense test ADR-072 already mandates, plus looking at the *balloon's* 2.4 GHz RX when a cell modem is transmitting on the ground.
- **The 2.4 GHz BPF (checklist row 10, €17.79) now has a second reason to exist**: keeping LTE B7/B40 energy out of the uplink chain. That is a one-line justification to add to ADR-072, not a design change.

### 5.8 Non-cellular alternatives (one honest block each)

| Alternative | What it is | Cost | Verdict for this use case |
|---|---|---|---|
| **Starlink** | LEO satellite broadband, mains-powered dish, ~50–100 W class, monthly subscription | **UNVERIFIED.** `https://www.starlink.com/de/service-plans` is fully JS-rendered — every fetch I made returned a 34,721-byte shell with **zero** price content, and my search-engine fallbacks were captcha-blocked. I will not quote a number I could not fetch. | **Power rules it out of the pico-station class** (tens of watts vs 1.58 W) and it is a mains-class installation. **But it is the strongest *anchor* option for a single fixed "gateway station"** if G2 needs a backhaul where no cell tower exists. Compare as a *site class*, not a station part. |
| **Wi-Fi point-to-point (PtP)** | Directional 5 GHz link to a partner with internet | MikroTik class hardware is cheap (I fetched `https://mikrotik.com/product/wireless_wire` successfully but did **not** fetch a price → UNVERIFIED) | **Not a substitute for cellular — it is an alternative *mechanism for G2*.** Requires line-of-sight to a peer *that already has internet*. Useful where the geometry works; fails exactly where it is needed most (no partner in sight). |
| **Sat messaging** | LoRa-APRS (already in the fleet per the brief), Iridium SBD, Starlink direct-to-cell | UNVERIFIED | **Right for telemetry and "is it alive", wrong for backhaul.** Keep it as the out-of-band liveness channel — it is the only path that survives a cellular outage *and* a balloon outage, which is exactly when you need to reach the station. |
| **LoRa/FLRC *through the balloon* itself (no backhaul at all)** | The existing design | €0 incremental | **This already satisfies most of "reach it over SSH"** — provided one station in the group has an uplink. See G3 (§6.2). |

---

## 6. Data cost, remote access and security (the parts that decide whether it works unattended)

### 6.1 Data cost

**MEASURED:** 1NCE's IoT Lifetime Flat is **€12 for 10 years**, *"Die Gebühr von 12 € inkludiert bereits alle notwendigen Kosten und Features wie zum Beispiel **500 MB Datenvolumen**, SMS, APN oder **OpenVPN**"*; SIM form factor surcharges: Business **€1**, Industrial **€2** (`https://1nce.com/de-de/`).

**UNVERIFIED:** German consumer/IoT MNO data-plan pricing (my fetches of Telekom/T-Mobile tariff pages returned HTTP 202/empty; broker sites bot-blocked). I will not invent a €/month figure. What would settle it: the current price lists at the MNOs' IoT/business portals, plus a public-IPv4/static-IP add-on price if one exists.

**The arithmetic the operator actually needs — €12 is *not* a 10-year always-on plan (MODELLED, arithmetic shown):**
- 500 MB over 10 years = **137 kB/day** budget.
- A persistent tunnel with a 25 s keepalive = 3,456 keepalives/day. A ~32-byte payload in a ~100-byte on-the-wire packet (UDP/IP + cellular framing, GUESSED overhead) ≈ **345 kB/day**.
- **⇒ 500 MB lasts ≈ 1,450 days ≈ 4 years of keepalives alone**, before a single SSH session, log line or software update. With an SSH session and a modest telemetry stream, this is a **~1–3 year budget**, GUESSED.
- **Conclusion:** 1NCE at €12 is an excellent *control-plane* SIM (it is the cheapest credible answer to "the station must be reachable") but **it is not a data plan**. For a station that relays another station's traffic (G2), a volume-based plan is mandatory. **Design rule: budget the SIM per station-role** — G2 anchors get a real data plan; G2 leaves and pure-telemetry stations get the €12 lifetime flat.

Also MEASURED from Teltonika's RMS page: the **Management service has a 30-day trial per device; Connect/VPN get the first 5 GB free per company**, then data is bought as a **150 GB / 10-year per-device package** or as **2 GB credits per company** (`https://teltonika-networks.com/products/rms`) — the specific prices are not on that page (**UNVERIFIED**). This is a ready-made remote-management rail if a Teltonika router is chosen, and it is worth pricing against the SIM cost.

### 6.2 (c) The relay mechanism — and the routing gap that decides it

For "station A with reception relays to station B without", three mechanisms exist:

**(i) FIPS multi-transport (recommended direction).** Give every station a FIPS node. Station B's node has only the radio transport; station A's node has radio **+ cellular-UDP**. If FIPS forwards across transports, G2 comes for free and is *cryptographically* end-to-end (Noise XK at L6) — the relay station never sees plaintext. **Gap (named):** ADR-012 describes FIPS as *"spanning-tree routing + bloom-filter discovery"* and records **no cost/metric**; nothing in the repo says a radio hop and a cellular hop are comparable, so nothing stops the tree from routing *out* through the expensive/fragile path. **This is a routing-policy deliverable, not hardware: "G3 — Egress Election".**
**(ii) Explicit L3 tunnel.** WireGuard/IPsec from B to A over the balloon, A NATs. Works today on Rank-1 routers (MikroTik RouterOS documents WireGuard — `https://help.mikrotik.com/docs/spaces/ROS/pages/2031622/WireGuard`; RutOS supports WireGuard/IPsec). Simpler to reason about than (i) and needs no FIPS change, at the cost of losing the end-to-end property of (i) — inside the tunnel it is still Noise XK, but the *routing decision* becomes static configuration.
**(iii) "Just SSH to B through the balloon."** Once A has any uplink, an operator can reach B *over the balloon* with no cellular at B at all. **This is the cheapest correct answer to most of the operator's request** and it needs no new hardware on B.

**Ranking the mechanisms: (iii) + (i) together; (ii) as the fallback when FIPS forwarding is not yet available.** Note the ordering implication for procurement: **you do not need cellular on every station — you need it on the stations that will be anchors.**

### 6.3 Remote access over cellular — CGNAT is the deciding fact

**Answer plainly: you cannot reach a station by "dynamic DNS + port forward", because a mobile APN almost never gives you a routable public IPv4.** The standard German MNO data APN assigns a private address behind carrier NAT (CGNAT), so inbound connections are impossible and DDNS is useless — **UNVERIFIED for the specific APNs** (I did not fetch an MNO APN/address-plan document; that is exactly what would settle it).

What *does* work, in order of cost:
1. **An outbound, persistent overlay** — the station always initiates, so CGNAT is irrelevant. The fleet already runs a FIPS mesh (per the brief), FIPS is a UDP/IP overlay (ADR-100 D1), and RouterOS/RutOS both speak WireGuard. This is the recommended mechanism and it needs **no** carrier feature.
2. **IPv6** — many carriers delegate a global prefix with the default APN, which restores direct reachability *if* the operator's management side is IPv6-capable. **UNVERIFIED (carrier-specific).** The check is one APN test: dial up, look for a global (2000::/3) prefix.
3. **A business/M2M APN with a public or static IPv4** — these exist as commercial products. **Price UNVERIFIED**; I did not fetch a carrier product page with a price. Do not assume it is cheap.
4. **A relay/VPS rendezvous** — a small public server both ends dial out to. Works, but it is a new dependency and a new trust anchor.

**Therefore: "SSH-able anywhere" is a *software/overlay* requirement, not a cellular one.** Cellular buys the *bearer*; the overlay buys the *reachability*. Conflating them is the most common way this project would fail.

### 6.4 Security — what must be true before a station touches the internet

1. **The management plane must never be on the WAN.** Both RouterOS and RutOS are high-value targets with a long exploitation history; MikroTik maintains a dedicated security-advisory page (`https://mikrotik.com/supportsec`, MEASURED 200). *(I fetched `https://nvd.nist.gov/vuln/detail/CVE-2018-14847` but the page returned no usable content to this session, so I cite the vendor's advisory page rather than a CVE I could not read.)* Concretely: disable WAN-side management, no UPnP, no port forwards, change defaults, restrict the LAN side to the overlay.
2. **Tunnels outbound-only.** No inbound listeners except the overlay's authenticated peers.
3. **The station must not become an open relay.** This is the security consequence of G1 and G2 that the operator's sentence does not mention: *if* a station relays third-party internet traffic over licence-exempt ISM, the operator's callsign/identity is attached to whatever those users do. **Require authenticated peers (FIPS Noise XK does this) and refuse plaintext NAT.**
4. **An update cadence is a physical requirement, not a nice-to-have.** An unattended mast station with a known-vulnerable router is worse than no station. Budget a reboot/test window per site per quarter.
5. **FIPS at L6 already answers the confidentiality question** (ADR-012 L6 = Noise XK). Do not add a second, weaker crypto path at the cellular edge.

---

## 7. (d) Legal — is relaying internet over licence-exempt ISM to a third party legal? Does cellular change it?

Short answer: **the radio-legal position is unchanged by the traffic's *content* or its *destination*, and cellular backhaul does not change it. What changes is the *service* side — and there I found a hard, citable number that the repo has been treating as unknown.**

### 7.1 The radio limits — and a finding that closes one of the repo's open items

The repo repeatedly marks the exact ERC/REC 70-03 Annex 1 row as `TODO(unverified)` (ADR-071, ADR-072 §Open items, `LINK-BUDGET-LICENCE-EXEMPT.md` §5, `licence-exempt-design-point.md` §3). **I fetched the harmonised standard's own band table and it states the 433 MHz row.**

**MEASURED** — ETSI EN 300 220-2 V3.2.1 (2018-06), band table (`https://www.etsi.org/deliver/etsi_en/300200_300299/30022002/03.02.01_60/en_30022002v030201p.pdf`), verbatim columns *Operational Frequency Band / Maximum e.r.p. / Channel access and occupation rules / Maximum occupied bandwidth / Band number from EC Decision 2017/1483/EU*:

| Band | Frequency | Max e.r.p. | Duty cycle / access rule | Occupied BW | EC Decision band |
|---|---|---|---|---|---|
| **H** | **433,050 – 434,790 MHz** | **10 mW** | **10 %** | The whole band | **44b, 45b** |
| **I** | 433,050 – 434,790 MHz | 1 mW e.r.p. (−13 dBm/10 kHz PSD for modulation BW > 250 kHz) | **No requirement** | The whole band | 44a, 45a |
| **J** | 434,040 – 434,790 MHz | 10 mW | **No requirement** | **25 kHz** | 45c |

**Three consequences, all decision-grade:**

1. **The 433 MHz downlink carries a 10 % duty-cycle ceiling under the harmonised standard.** The repo's licence-exempt design assumed a **~1.7 %** beacon duty (`licence-exempt-design-point.md` §7) and called the allowance "part of the TODO(unverified) Annex-1 row". It is now readable: **10 %**. A beacon at 1.7 % is fine. **A user-facing gateway (G1) relaying third-party traffic wants far more than 10 %** — and the 10 % ceiling is therefore *the* quantity that limits Service G1's capacity, not the EIRP. **This is a substantive new limit on the ADR-071 service and it should be added to the design of record.** *(Caveat: EN 300 220-2 is a harmonised standard giving presumption of conformity; the legally binding German instrument is the BNetzA Allgemeinzuteilung. My attempt to fetch a BNetzA 433 MHz Allgemeinzuteilung PDF returned 404 → that exact row remains **UNVERIFIED**, and it is the one document that would close it.)*
2. **Band J is not a loophole for this design** — its "no duty requirement" comes with a **25 kHz** occupied bandwidth, which cannot carry the 2.666 MHz FLRC waveform ADR-072 measures against.
3. **Band I (1 mW e.i.r.p., no requirement) is the escape hatch for a *low-rate, high-duty* service** — but at 1 mW e.r.p. the link budget changes by ~10 dB against H, and `LINK-BUDGET-LICENCE-EXEMPT.md` §2 shows the 433 downlink was the *comfortable* direction (+24.3 dB). Trading 10 dB for the removal of the duty ceiling is a real, named option the operator now has — **but it needs its own link-budget re-run, not a guess from this paper.**

**And the repo's *other* named defect is closable too.** ADR-071/ADR-072 flag a ~6 dB disagreement: is the 2.4 GHz uplink capped at a flat **20 dBm EIRP** (`LINK-BUDGET-LICENCE-EXEMPT.md`, ADR-081's ladder) or at **14.26 dBm** under a 10 dBm/MHz PSD rule? **The standard says both limits apply, so the binding one is the lower.** MEASURED — ETSI EN 300 328 V2.2.2 (2019-07) (`https://www.etsi.org/deliver/etsi_en/300300_300399/300328/02.02.02_60/en_300328v020202p.pdf`):
- §**4.3.2.2.3** (Limit): *"The RF output power for non-FHSS equipment shall be equal to or less than **20 dBm**."*
- §**4.3.2.3.3** (Limit): *"The maximum Power Spectral Density for non-FHSS equipment is **10 dBm per MHz**."*

**MODELLED:** min(20 dBm, 10 + 10·log₁₀(2.666)) = min(20, 14.26) = **14.26 dBm EIRP** — i.e. **the PSD reading wins, exactly as `design/rf-shopping-list` computed.** The two readings were never alternatives; they are two simultaneous limits. **I recommend this be recorded as the resolution in ADR-072 §Open items (subject to the same German-Allgemeinzuteilung caveat), because it directly decides the uplink's range and the repo currently carries it as an unresolved DEFECT.**

### 7.2 The service side — does relaying to a third party change anything?

**What does *not* change (MEASURED/derived):** the ISM/SRD framework constrains the **transmitter's** power, PSD, duty cycle and non-interference behaviour. Those limits apply identically whether the payload is your own telemetry or a stranger's TCP stream. **Relaying third-party traffic over 433/2.4 GHz is therefore not a new radio-legal problem, and cellular backhaul does not change that either — the radio side and the WAN side are independent regimes.**

**What *does* change (and this is where the honesty contract bites):**

- **You may become a provider under the TKG.** **MEASURED** — TKG (2021) §5(1): *"Wer **gewerblich** öffentliche Telekommunikationsnetze betreibt oder **gewerblich** öffentlich zugängliche Telekommunikationsdienste erbringt … muss die beabsichtigte Aufnahme … bei der **Bundesnetzagentur** unverzüglich melden."* (`https://www.gesetze-im-internet.de/tkg_2021/__5.html`). **The trigger word is "gewerblich" (commercial).** A free community relay is arguably not *gewerblich*; a TollGate-gated relay that takes **Cashu payment** for internet access is much harder to argue is not. **UNVERIFIED as a legal conclusion — it needs a lawyer or a BNetzA enquiry, and I am not qualified to give it.** I state the test, not the verdict.
- **The cellular side adds a *contract* restriction that the ISM side does not have.** MNO and MVNO consumer/IoT tariffs normally forbid resale or providing the connection to third parties. **UNVERIFIED** — I did not fetch an authoritative German MNO/MVNO clause. What would settle it: the current *AGB/TKMV* of Telekom/Vodafone/O2 (and 1NCE's product terms) with the clauses on *Weiterverkauf*, *Nutzung durch Dritte* and *Ausstrahlung/Weiterleitung*. **This is the single most likely place for the relay idea to be contractually blocked, and it is not a radio question at all.**
- **Note the direction of the change:** the ISM relay is *radio*-constrained (10 % duty, EIRP/PSD caps → a local, thin service); the cellular relay is *contract*-constrained (T&Cs) and *coverage*-constrained. **Cellular backhaul therefore does not make the ISM relay more legal — it makes the WAN side of it legal-or-not on a completely different axis (the MNO contract).**
- **Pre-existing, upstream, and still the dominant legal risk:** the repo's own open item — *"Licence-exempt SRD **AIRBORNE** use is a grey area. The ERC/REC 70-03 framework is written for short-range ground use; airborne use is not clearly addressed. This needs a national-regulation check before flight."* (`licence-exempt-design-point.md` §9(a)). Nothing in this paper changes that, and no cellular decision should be taken as if it did.

### 7.3 One more legal/technical coupling worth stating

If the station's cellular WAN is used to **serve users directly** (the G1 reading), then the station is offering a *publicly available electronic communications service* using a commercial mobile subscription — which stacks the TKG question on top of the T&C question on top of the ISM duty-cycle ceiling. **The station-only framing (§3.2) avoids two of those three problems at once**, which is another independent argument for building G2 before G1.

---

## 8. Recommendation

**R1 — Do NOT put cellular on the v1 base-station PCBA. Keep the D14 freeze exactly as it is.** The board is control/bias/telemetry by design, it has no host, and every cellular option would change its class, its rail budget and its enclosure. Adding telco on-board is not an optimisation — it is a different product.

**R2 — Adopt the adjacent-box architecture: a Rank-1 industrial LTE router, powered from `VIN_GS` (9–18 V), not from the 5 V rail.** This changes **nothing** in the frozen 5 V network (TPS62162, 316 mA, 0.5 A/1 A, bias tee, AGC, LNA branch all stand), adds one fused 12 V branch to the entry spec, and delivers a known-good OS, firewall, WireGuard, watchdog and an update path. **Concretely: MikroTik LHG LTE kit ($179 suggested, Cat 4, 17 dBi, outdoor, PoE-in 12–57 V, max 6 W) for the deployed mast station; Teltonika RUT241 (€169.90 seen on Amazon.de, 1.31 W idle+data) for the bench and the first build.**

**R3 — Choose LTE Cat-4 now, Cat-1 bis later if you ever build a module carrier. Do not buy 5G.** Documented in §5.6 with four independent reasons; the power one alone is dispositive (a 5G router idles at 3× the entire station).

**R4 — Plan the WAN as *some* stations, not *all* stations.** The cheapest correct reading of the operator's request is: (a) every station is reachable **through the balloon** today; (b) cellular on the **anchor** station(s) makes the anchor independent of a fixed line; (c) the anchors relay (G2) to the rest. **Do not buy a SIM per station before measuring which sites actually have signal** — walk the sites with a handset and a band-lock readout first (§5.5).

**R5 — Treat reachability as an overlay problem, not a cellular problem.** CGNAT makes inbound-IP/DDNS useless (§6.3). The station must *initiate*: FIPS (already designed, ADR-100/012) or WireGuard outbound. **And before any of it: fix the ADR-012/ADR-016 contradiction about what microfips actually is**, because the overlay you are betting on is described one way in one ADR and another way in the next.

**R6 — Build the four cheap "preserve the option" items NOW, before the STL/board wiring is frozen** (they cost ≈ €0 today and are expensive later):
1. **Enclosure (row 18 is still DNP):** reserve volume, mounting bosses (DIN-rail or lid) and two cable penetrations for a router + a small SBC + antenna pigtails. *Free now; a re-print later (GUESSED €20–60 + 1–2 days).*
2. **Mast:** reserve a **fixed, non-pointing stub below the rotator** for a cellular MIMO antenna. *Free now; a torque/wind-load re-derivation of ADR-077/078 later.*
3. **Power entry:** write "second fused branch, 12 V @ 3 A, separate return" into the `VIN_GS` entry specification. *Free now; a bring-up surprise later.*
4. **Decide MECH-01 (masthead vs shack) now.** Cellular forces it, and it is already flagged OPEN/critical — masthead = RF + bias + AGC; shack = host + modem + power.

**R7 — Order the work G2/G3 before G1.** Station-to-station backhaul (G2) plus the egress-election routing metric (G3) is the half that makes *"stations work anywhere"* true, and it avoids the TKG/T&C exposure of selling internet to third parties (§7.2). G1 is not blocked forever — but it needs the ADR-071 service definition (users, duty cycle, availability) that the record itself says is missing, **and** the 10 % ISM duty ceiling now belongs in it.

**R8 — Two documentary actions for the design of record** (both are citations, not new engineering):
- **ADR-072 §Open items:** the 2.4 GHz ceiling defect is resolvable — EN 300 328 §4.3.2.2.3 and §4.3.2.3.3 apply *simultaneously*, so **14.26 dBm EIRP at 2.666 MHz is the binding figure** (§7.1). Record it, with the German Allgemeinzuteilung caveat.
- **ADR-071 / `licence-exempt-design-point.md`:** the 433 MHz SRD row is readable as **10 mW e.r.p. with a 10 % duty cycle** (EN 300 220-2 band H, EC Decision band 44b/45b), and **the 10 % duty ceiling — not the EIRP — is what limits a user-facing gateway** (§7.1).

### What I would buy first (a concrete, minimal first step)

1. One **Teltonika RUT241** (€169.90 seen) or **TRB140** — for the bench.
2. One **1NCE Lifetime Flat SIM** (€12, 500 MB/10 y) — from `https://1nce.com/de-de/`.
3. A handset + band-lock survey at 2–3 candidate sites **before** any mast hardware.
4. **Nothing else.** No PCBA change, no 5G, no SBC, no new board.

That step costs **≈ €185–190** and answers every open measurement question in this paper (idle/peak draw at the station, whether CGNAT bites, whether an outbound overlay is enough, whether the site has signal at all) without touching the D14 freeze or the ADR-111 pipeline.

---

## 9. Gap register (what is missing, where it goes in the existing records)

| ID | Gap | Owned by | Severity |
|---|---|---|---|
| **TELCO-01** | No ADR for a station WAN path. Cellular is a *transport under L4*; record it as extending ADR-071, not amending it. | new ADR (next free number per `scripts/adr_next_number.py`) | high |
| **TELCO-02** | **G2 "Backhaul Relay" and G3 "Egress Election" are undefined.** ADR-071 only defines G1. | new ADR + ADR-012/100 §L5 | **critical** (it is the operator's actual ask) |
| **TELCO-03** | **No FIPS routing cost/metric.** ADR-012 says "spanning-tree + bloom-filter discovery" and nothing about hop cost — so nothing steers traffic off the expensive/fragile cellular path, or onto it deliberately. | ADR-012 | high |
| **TELCO-04** | ADR-012 vs ADR-016 disagree on microfips' language (Rust vs C++) — and ADR-016 also mis-expands the FIPS acronym. Repo rule: a contradiction with no winner is a DEFECT. | ADR-012/016 | high |
| **TELCO-05** | ADR-071's missing service definition (users / duty cycle / availability) now also needs the **10 % ISM duty ceiling** as an input. | ADR-071 §Open items | high |
| **TELCO-06** | The 2.4 GHz EIRP/PSD "defect" is closable from the standard text (§7.1). | ADR-072 §Open items | medium |
| **TELCO-07** | Power entry spec must gain a second (12 V) branch, or the router cannot be added without breaking the entry limit D14 already flags. | `BASE-STATION-PCBA-D14-FREEZE.md` (entry spec, not the PCBA) | medium |
| **TELCO-08** | MECH-01 (masthead vs shack) is now **forced**, not merely advised. | ROUND2 MECH-01, pre-ADR-111 stage 1 | **critical / blocking for board design** |
| **TELCO-09** | No site-survey step exists in any plan: nothing currently measures signal, CGNAT or band availability before hardware is bought. | program plan | medium |
| **TELCO-10** | 450 MHz-class cellular proximity to the 433 MHz SRD band — unmeasured, unlisted. | `BASE-STATION-BOARD-CHECKLIST.md` row 2 verification (LiteVNA 62) | low/UNVERIFIED |
| **TELCO-11** | The 2.4 GHz BPF now has a second justification (LTE B7/B40 rejection). | ADR-072 / checklist row 10 | low |

---

## Appendix A — Every price and spec quoted in this paper, with its provenance

| Claim | Value | Status | Source (fetched this session unless noted) |
|---|---|---|---|
| Teltonika RUT241 power | 1.05 W idle (no SIM, 9 V); 1.31 W idle+data (12 V); 3.24–3.31 W max | MEASURED | https://wiki.teltonika-networks.com/view/RUT241_Power_Consumption |
| Teltonika TRB140 power | 0.70 / 1.15 / 3.87–3.89 W | MEASURED | https://wiki.teltonika-networks.com/view/TRB140_Power_Consumption |
| Teltonika RUT956 power | 1.45 / 1.75 / 10.26–11.30 W | MEASURED | https://wiki.teltonika-networks.com/view/RUT956_Power_Consumption |
| Teltonika RUTX50 (5G) power | 4.61–4.81 idle / 5.18–5.25 idle+data / 15.68–17.45 max 5G NSA | MEASURED | https://wiki.teltonika-networks.com/view/RUTX50_Power_Consumption |
| Teltonika RMS | 30-day Management trial; first 5 GB free; 150 GB/10 y package or 2 GB credits | MEASURED (prices NOT on page) | https://teltonika-networks.com/products/rms |
| MikroTik LHG LTE kit | Cat 4, 150/50 Mbit/s, bands 1/2/3/7/8/20/38/40, 17 dBi, **max power 6 W**, PoE-in 802.3af/at **12–57 V**, $**179.00** suggested, −40…+50 °C | MEASURED | https://mikrotik.com/product/lhg_lte_kit |
| MikroTik Chateau LTE7 | $119.00 suggested; max power **20 W** (14.1 W w/o attachments) | MEASURED | https://mikrotik.com/product/chateau_lte7 |
| MikroTik RouterOS WireGuard support | doc page exists | MEASURED | https://help.mikrotik.com/docs/spaces/ROS/pages/2031622/WireGuard |
| MikroTik security advisories | vendor advisory page | MEASURED (page reachable; no CVE detail asserted) | https://mikrotik.com/supportsec |
| Amazon.de RUT241 listings | **€169.90**; other offers €219.90 / €332.10 | MEASURED (marketplace, not list price) | amazon.de search results, fetched 2026-10-14 |
| Quectel EC25 | Cat 4, 150/50, LCC 32×29×2.4 mm, −40…+85 °C | MEASURED | https://www.quectel.com/product/lte-ec25-series/ |
| Quectel RM520N | M.2 30×52×2.3 mm, SA 2.4 Gbps/900, NSA 3.4/550, Rel-16, −40…+85 °C | MEASURED | https://www.quectel.com/product/5g-rm520n-series/ |
| Quectel Cat 1 bis line | exists (linked from EC25 page) | MEASURED (link); spec/price UNVERIFIED | https://www.quectel.com/lte-cat-1-bis-modules/ |
| Waveshare SIM7600E-H 4G dongle | **$87.99**, 5 V DC input | MEASURED | https://www.waveshare.com/sim7600e-h-4g-dongle.htm |
| Waveshare SIM8200EA-M2 5G HAT | **$289.99, DISCONTINUED**; 5 V 3 A; 6× IPEX-4 | MEASURED | https://www.waveshare.com/sim8200ea-m2-5g-hat.htm |
| Raspberry Pi 4 supply | 5 V / 3 A | MEASURED | https://datasheets.raspberrypi.com/rpi4/raspberry-pi-4-datasheet.pdf |
| Raspberry Pi 5 | 5 V / 5 A; $45 (1 GB) … $305 (16 GB); 0–70 °C | MEASURED | https://datasheets.raspberrypi.com/rpi5/raspberry-pi-5-product-brief.pdf |
| 1NCE Lifetime Flat | **€12 / 10 years, incl. 500 MB**, SMS/APN/OpenVPN; SIM Business €1, Industrial €2 | MEASURED | https://1nce.com/de-de/ |
| EN 300 220-2 band H (433.050–434.790) | **10 mW e.r.p., 10 % duty cycle**, whole band, EC Decision band **44b/45b** | MEASURED (quoted) | https://www.etsi.org/deliver/etsi_en/300200_300299/30022002/03.02.01_60/en_30022002v030201p.pdf |
| EN 300 220-2 bands I / J | I: 1 mW e.r.p., no requirement. J: 434.040–434.790, 10 mW, no requirement, **25 kHz** | MEASURED (quoted) | same |
| EN 300 328 §4.3.2.2.3 / §4.3.2.3.3 | ≤ **20 dBm** EIRP; max PSD **10 dBm per MHz** (both apply) | MEASURED (quoted) | https://www.etsi.org/deliver/etsi_en/300300_300399/300328/02.02.02_60/en_300328v020202p.pdf |
| TKG (2021) §5(1) Meldepflicht | commercial providers of public telecom networks/services must notify BNetzA | MEASURED (quoted) | https://www.gesetze-im-internet.de/tkg_2021/__5.html |
| jmcorgan/fips | Rust, MIT, 270 ★, "The Free Internetworking Peering System" | MEASURED | https://api.github.com/repos/jmcorgan/fips |
| Amperstrand/microfips | **Rust**, MIT, 2 ★, "Minimal FIPS leaf node on STM32F469" | MEASURED | https://api.github.com/repos/Amperstrand/microfips |
| MeshCore | C, MIT, 3,855 ★ | MEASURED | https://api.github.com/repos/meshcore-dev/MeshCore |
| Diamond A-430S15R (433 Yagi) | **74,50 €** | MEASURED | https://funktechnik-bielefeld.de/diamond-a-430s15r-uhf-15-element-richtantenne-70cm-band |
| Diamond A-430S10R | 69,00 € | MEASURED (same page) | same |
| Yaesu G-450CDC rotator | 359,00 € | MEASURED (same page; matches ADR-081) | same |

## Appendix B — Explicitly UNVERIFIED (do not treat as fact)

1. **Starlink German pricing and power.** `starlink.com/de/*` served a 34,721-byte JS shell with zero price content on every attempt (residential, roam, service-plans, /api/prices/de); search fallbacks were captcha-blocked. **No Starlink number is quoted anywhere in this paper.** Source that would settle it: the German Starlink price page rendered in a real browser, or Starlink's terms PDF.
2. **German MNO/MVNO tariff and T&C pricing/clauses for resale or third-party use.** Telekom/T-Mobile tariff pages returned HTTP 202 with empty bodies; broker/price-comparison sites bot-blocked. Source that would settle it: the MNOs' current AGB/TKMV and IoT product pages, plus 1NCE's product terms.
3. **Public/static IPv4 APN availability and price**, and **IPv6 prefix delegation** on German mobile APNs. Source that would settle it: one APN test per carrier, plus the carriers' business-M2M product pages.
4. **The German BNetzA Allgemeinzuteilung row for 433 MHz** (the legally binding instrument behind EN 300 220-2 band H). My fetch of a BNetzA 433 MHz Allgemeinzuteilung PDF returned HTTP 404. This is the one document that would close the 10 % duty-cycle finding at law (the standard's text is not in doubt).
5. **LTE B31 / NR n31 (450 MHz) deployment status in Germany** — relevant because it sits nearest the 433 MHz SRD band.
6. **MikroTik LHG LTE kit mass, and Teltonika product list prices** (both product pages are JS-rendered; I could read the spec tables but not a list price for the RUT family).
7. **Teltonika TRB140 / RUT956 / RUTX50 EUR retail prices** — not fetched.
8. **Quectel EC25 / RM520N / Cat 1 bis module prices** — distributor pages (Mouser/TME/Digi-Key/Conrad/Geizhals/idealo) returned HTTP 403 or stub pages.
9. **Any legal conclusion** about whether a station-to-station internet relay is lawful, whether the operator becomes a TKG-regulated provider, or whether a specific tariff permits it. This paper states the **tests** (TKG §5 "gewerblich"; MNO T&C resale clauses) and does not give a verdict. Obtain qualified advice.
10. **Self-integrated module CE/RED conformity assessment cost** — named as a cost centre, magnitude not researched.
11. **Enclosure re-print cost (€20–60, 1–2 days)** — GUESSED from the existence of the printed-enclosure line (`hardware/enclosure/*.scad`), not from a printed/measured job.

## Appendix C — Repo citations used (so nothing here re-derives them)

`docs/adr/071-ground-station-gateway-design-basis.md` (D1/D2/D3, INV-1…4, §Costs/risks EIRP caveat, §Open items service-definition hole) ·
`docs/adr/072-band-split-duplex-two-antennas-no-circulator.md` (D1/D3/D4/D5, INV-1…5, the 14.26 dBm reading, §Open items defect) ·
`docs/adr/100-tollgate-over-fips-mesh-udp.md` (D1, the L1–L7 stack, UDP socket interface) ·
`docs/adr/012-mesh-networking-strategy.md` (the stack table, ground-station Minimal/Full options, Phase ladder) ·
`docs/adr/016-fips-implementation-keep-cpp-microfips.md` (the C++ claim) ·
`docs/adr/111-canonical-board-production-order.md` ("base-station … does not exist"; the BLOCKING gates) ·
`docs/adr/081-ground-station-tier-ladder-and-option-b.md` (tier ladder, EIRP-inertness above ~8 dBi, ≈€735 option B) ·
`docs/BASE-STATION-PCBA-D14-FREEZE.md` (parts, 316 mA / 0.5 A cont / 1 A peak, 18 V entry limit, "not a purchasing authorization") ·
`docs/BASE-STATION-BOARD-CHECKLIST.md` (rows 2/10/13 verification criteria, prices, totals €274.58/€441.57) ·
`docs/LINK-BUDGET-LICENCE-EXEMPT.md` (§2/§3 margins, §5 TODOs) ·
`docs/licence-exempt-design-point.md` (§3 bands, §7 1.7 % duty, §8 what remains, §9(a) airborne grey area) ·
`docs/analysis/PROGRAM-GAP-ANALYSIS-ROUND2.md` (§1 the unmerged ground station, §6 wind-load-and-stiffness + MECH-01) ·
`docs/analysis/GAP-TRACKING-CHECKLIST.md` (BS-01…BS-07) ·
`docs/PROGRAM-BOARD-COMPLETION-PLAN.md` (board manifest: base station "NO").
