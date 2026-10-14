# CONSULT BRIEF — Telco (4G/5G) backhaul for the balloon base station

## The operator's question (verbatim intent)

> "I think it would be great if [the base station] was to support simcards and
> Telco stack (ie. 4G and/or 5G) so that the base stations can be accessed
> remotely over ssh and/or fips and so that they can function anywhere without
> needing to have a separate internet gateway. Ideally the balloon / bent pipe is
> able to relay internet from a base station that has good cellphone reception to
> a base station that doesn't have good cellphone reception."

Sub-questions asked explicitly:
1. How does this fit with the plans and work already done?
2. Is this too big a change for the **current version** of the base station?
3. What is the **sunk cost** if introduced now?
4. What are the **options** for telco support, their **costs** and **tradeoffs**?
5. Recommendations?

## Established context — do not re-derive, cite where relevant

### What the base station IS (design of record)

- **ADR-071 (Accepted by operator, 2026-10-08):** the ground station is "a
  full-duplex **INTERNET GATEWAY** through the balloon as a bent pipe". Users
  reach the internet *through the balloon*. Two independent bands live
  simultaneously: 433 MHz downlink, 2.4 GHz uplink (ADR-034/072). Half-duplex
  T/R relays are ruled out because TCP/IP needs simultaneity.
  - **Key existing caveat (ADR-071 §Costs/risks):** *"The uplink is EIRP/PSD-capped
    under licence-exempt rules, which caps the service radius; 'Internet gateway'
    is therefore a **local** service on the ISM footing, not a long-range one."*
  - **Open item in the same record:** *"A service definition (number of users,
    duty cycle, availability) is not recorded anywhere in this set."*
- **ADR-072:** band-split duplex, **two antennas, NO circulator**, BPF before LNA.
- **ADR-084:** ground-station automatic level control (ADL5240 VGA + AD8318
  detector + RP2040).
- **Board reality today:** `docs/BASE-STATION-PCBA-D14-FREEZE.md` + `docs/BASE-STATION-BOARD-CHECKLIST.md`.
  The PCBA is **control/bias/telemetry only**: RP2040 (QFN-56), AD8318 log
  detector, ADL5240 VGA, ZFBT-4R2GW+ bias tee, TPS62162 5 V buck. **It has no
  host CPU, no networking, no OS, no PCIe/USB host, and no cellular anything.**
  5 V rail budget: **316 mA design total, ≥0.5 A continuous / 1 A peak**.
- **Antennas/feeds (checklist rows 1,2,3,9,12):** Diamond A-430S15R Yagi (433),
  Sirio SLP-17 log-periodic (2.4 GHz), 433 BPF, TQP3M9037 LNA, masthead feed.
  Not yet ordered/sign-off.

### The balloon's network stack (already designed)

From `docs/adr/100-tollgate-over-fips-mesh-udp.md` the balloon carries a full
stack: L1 LR2021 radio → L2 TDMA dual-band → L3 fragmentation/erasure coding →
**L4 UDP/IP tunnel → L5 FIPS mesh routing → L6 FIPS Noise XK → L7 TollGate +
Nostr**. So **IP-over-FIPS-over-the-balloon already exists as a design**; what is
missing is (a) a *backhaul* at the ground station and (b) the relay/scheduling
contract for internet traffic.

### Repo state for cellular

**Nothing.** A repo-wide search for LTE / SIM / Quectel / SIM7600 / BG95 /
cellular-modem terms returns no design, no card, no BOM row. The only cellular
object anywhere in the fleet is an **LTE modem in a laptop** (Sierra EM7455,
`/dev/ttyUSB0-2`), which is a *host* device, not a base-station part.

## What we need from you (the ask)

Produce a **decision-grade gap analysis + options paper**. Specifically:

### A. Fit with existing plans
- Does cellular backhaul *contradict* ADR-071, or extend it? Be precise: ADR-071
  says the gateway serves internet *through the balloon*; cellular backhaul adds
  a *separate* WAN path at the station. Are these the same function or two?
- Where does the backhaul attach in the stack above (which layer)?
- Does the operator's "relay internet from a station with good reception to one
  without" imply a **different** service than ADR-071's user-facing gateway
  (i.e. station-to-station backhaul WAN sharing)? Name the distinction.

### B. Is it too big for the current base station? Sunk cost?
- Given the PCBA is control/bias only with no host CPU: what has to be ADDED
  (compute, networking, modem, power, thermal, enclosure, antenna)?
- Quantify the sunk cost of introducing it **now** vs **after** the v1 PCBA is
  ordered: what would be re-spun (board, enclosure, mast, power budget)?
- Distinguish "add to v1" vs "adjacent box" vs "defer to v2".

### C. Telco options — ranked, with real numbers
For each option give: **what it is, hardware, typical cost (EUR), data cost,
power, complexity, licencing, and failure modes**:
1. USB LTE dongle + small Linux SBC (e.g. Raspberry Pi / CM4)
2. M.2/NVMe LTE or 5G module + carrier board + SBC
3. LTE/5G industrial router (Teltonika RUT-class, MikroTik, Cradlepoint)
4. Integrated 5G module on a custom board (e.g. Quectel RM5xx, SIMCom)
5. Phone-as-hotspot / tethered handset
6. Non-cellular backhaul alternatives worth comparing (Starlink, LoRa-APRS
   already present, Wi-Fi PtP, sat messaging) — at least one line each.
Include **5G vs LTE**: is 5G worth it for this use case (SSH + FIPS over a
kilometre-scale ISM link), or is LTE Cat-1/Cat-4 the rational choice?

### D. Hard constraints to check and state honestly
- **Licencing/legal:** is relaying internet over a licence-exempt ISM band
  (433/2.4 GHz) to a *third party* legal? Does that change with cellular
  backhaul? Flag anything UNVERIFIED.
- **Power:** the station's 5 V rail is 316 mA design / 0.5 A cont. What does an
  LTE modem add (idle vs TX burst)? Does it break the existing budget?
- **Data cost:** SIM/data-plan economics for an unattended remote site.
- **Antenna coexistence:** extra antenna on the mast vs the existing 433/2.4 GHz
  antennas and the ADR-072 isolation requirement.
- **Remote access:** SSH/FIPS over cellular — CGNAT, no public IP, dynamic DNS,
  VPN/mesh overlay (the fleet already runs a FIPS mesh + NetBird).
- **Security:** exposing a station to the internet; what must be true.

### E. Recommendation
A clear recommendation with the reasoning, and explicitly: **should this be in
the current base-station version, and if not, what is the minimal step now that
preserves the option** (e.g. reserve footprint, pin header, power headroom,
enclosure volume)?

### F. Honesty contract
- Cite sources with URLs for costs/specs. Mark anything unverified as
  `UNVERIFIED` and say why.
- Distinguish MEASURED from MODELLED from GUESSED.
- Do not invent part numbers, prices, or URLs.
- Where the repo already answers something, cite the file/ADR rather than
  re-deriving it.
- If you think the operator's premise is wrong, say so plainly with reasoning.
