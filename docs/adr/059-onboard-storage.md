# ADR-059 — On-board storage: the module's own 8 MB flash is sufficient; no external storage part is fitted; the TX buffer is sized to the link, not to the flash

- Status: **Proposed** — the *design direction* this record takes (the cheapest storage is the
  storage already bought; the buffer is sized by transmission energy, not flash capacity; no
  external part; no on-board Blossom server) is recorded here, but the **text has NOT been
  accepted by a human**, so it does not say Accepted. Until a human accepts it, no schematic,
  placement, BOM freeze or fabrication may treat it as frozen (ADR-first rule, ADR-029
  §Context).
- Date: 2026-10-07
- Decision owner: Felix (operator). The question is his (2026-10-07); the text is not accepted.
- Author: Hermes subagent, branch `adr/onboard-storage`, worktree `~/worktrees/bf-storage`.
- **No hardware is ordered by this record. It is design work only.** The decision is to add
  *nothing*, so it has no BOM line and no cost.
- Number allocation: `python3 scripts/adr_next_number.py` printed **`57`** in this checkout
  (base `23a621c`). **057 is not free** — a sibling worker claimed it
  (`docs/adr/057-flrc-drift-strategy.md` on branch `adr/flrc-drift-strategy`); checked across
  ALL refs, **057, 058 and 060 are taken (and 058 is claimed twice)** and **059 is free on
  every branch inspected**. The number is therefore **059**, taken from the allocator's
  range but not hard-coded to its raw output. No file is renamed.
- Related records:
  - **ADR-036** (`docs/adr/036-energy-policy-burst-storage-daylight-only-tx.md`) — burst-sized
    storage, daylight-only TX, **night deep-sleep mandatory**, the **100 µW night anchor**, and
    the statement that **the flight recorder becomes the primary evidence source**. This ADR
    refines (does not overturn) ADR-036's "8 MB PSRAM / flash logging" wording: **PSRAM is
    volatile and cannot survive the night; the log must be in flash.**
  - **ADR-029** (`docs/adr/029-dual-band-flight-board.md`) — D1 selects
    `ESP32-S3-WROOM-1U-N8R8` and D1 item 3 gives "8 MB PSRAM for on-board logging". Its
    *sdkconfig header comment* claim of "16 MB flash" (D1 item 5) is corrected here for this
    module.
  - **ADR-042** (`docs/adr/042-thermal-drift-strategy.md`) — the **`log-don't-tune`** philosophy
    (Addendum A6: the ESP32 die sensor is a free logging channel, not a control input).
  - **ADR-058** (`docs/adr/058-onboard-temp-compensation.md`, branch
    `adr/058-onboard-temp-compensation`, commit `39b3333`) — **D4 requires non-volatile
    storage for the per-unit calibration curve** and expressly defers the storage *part* to a
    sibling task. **This record answers that deferral.**
  - **ADR-051** (`docs/adr/051-hub-array-and-cut-topology.md`) §2.5.1 — the persistent **NVS
    fired-flag** per cut channel.
  - **ADR-047** (§3.2, the **33.264 J usable bank**) and **ADR-050 §3.6** (the `I_Q ≤ 5 µA`
    night bound).
  - **ADR-027** (`docs/adr/027-blossom-on-ip-layer.md`, Accepted) — Blossom stays on IP/HTTP.
  - **ADR-013** (`docs/adr/013-cluster-aware-stratorelay.md`) — the balloon as a *relay*, and
    its own airtime-saturation risk.
  - **ADR-043** (cold qualification) and **ADR-056 §D5** (the −60 °C rating gap is closed by
    part selection / accepted characterisation, **not by heating**).
- Evidence base: `docs/analysis/onboard-storage.md` (the analysis this record takes its
  decision from; every number there is cited or computed, with `TODO(unverified)` where no
  source carries it). Datasheets read for this record: Espressif
  `ESP32-S3-WROOM-1 & WROOM-1U` Datasheet **v1.8**; Winbond `W25Q128JV` rev F 2018/03/27;
  Microchip `24AA256/24LC256/24FC256` DS20001203; Infineon/Cypress `FM25W256`; Würth
  `693072010801`; Western Digital *Industrial Grade microSD / SD Card Portfolio* brochure;
  Kingston `SDCIT` datasheet + spec sheet.

---

## Context

The operator asked (verbatim intent):

> *"what would it take to store stuff on the board? For instance a master relay or a blossom
> server can include a very lightweight, small, compact, cheap flash storage on the board?"*

The implicit premise is that the board has no storage. **It does.** The v9 MCU is fixed by
ADR-029 D1 as **`ESP32-S3-WROOM-1U-N8R8`**, whose part number decodes to **8 MB flash + 8 MB
PSRAM on the module** (Espressif datasheet v1.8, Table 1-2: *Flash 8 MB (Quad SPI); PSRAM
8 MB (Octal SPI)*, ambient **−40 ~ 65 °C**). After firmware, **≈ 4 MB is free** (the repo's
own blossom design assumes ~4 MB of an S3).

Two things the premise gets wrong, and this record states both:

1. **"Storage" on this vehicle is already the storage you bought.** A "lightweight, small,
   compact, cheap flash" is what the module already is. Adding an external W25Q-class part
   adds a *second copy* of a resource whose real constraint is elsewhere.
2. **The real constraint is transmission energy, not flash capacity.** At the repo's own
   numbers — **6.15 W × 0.1 s = 0.615 J per sub-GHz TX slot** (`docs/analysis/mppt-charge-path-specification.md`
   §3.5) and **22 kbps achievable at ~300 km** (ADR-009) — a transmitted byte costs
   **≈ 2.24 mJ**. **The entire usable bank (33.264 J, ADR-047 §3.2) buys ≈ 15 KB of
   downlink.** So a store sized by "how much flash can I buy" is a store the link can never
   drain.

A second, harder premise check: the sibling record **ADR-058 D4 already requires
non-volatile storage** for the per-unit calibration curve and **deliberately leaves the part
to this task**. That requirement must be satisfied here.

---

## Decision

**The v9 flight board carries NO external storage part. Storage is served entirely by the
`ESP32-S3-WROOM-1U-N8R8`'s own 8 MB flash (≈ 4 MB free for data after firmware), and the
design work is partitioning, not procurement.**

Sub-parts, all recorded as decisions:

### D1 — Internal 8 MB flash is sufficient; no external part is fitted

**The cheapest storage is the storage already bought.** The module's on-module **8 MB Quad
SPI flash** (Espressif DS v1.8, Table 1-2) provides:

- **≈ 4 MB free for data** after a 2 MB app partition and the system partitions — the figure
  the repo's own `docs/blossom-design.md` §6 assumes for an S3, and consistent with
  `firmware/blossom-server/partitions.csv` (factory `0x200000` + data `0x180000` on a 4 MB C3).
- **≈ 270× the download capacity of one full bank discharge** (§D3): the flash is not the
  constraint and cannot be made to be.

**Correction to the repo:** `tracker/firmware/sdkconfig.defaults.esp32s3` line 2 and ADR-029
D1 item 5 state **16 MB flash** for this board. **That is wrong for the `-N8R8` part**, which
is 8 MB. (The 16 MB figure belongs to the TollGate boards, a different module in this repo's
other track.) **ADR-029 is not edited here**; the correction is stated so no partition table or
sizing claim inherits the stale number. Flagged for the manager.

**Rejected alternatives, with their reasons (not hidden):**

| Alternative | Rejected because |
|---|---|
| **`W25Q128JVSIQ` SPI NOR, SOIC-8 208-mil, 16 MB** (Winbond `W25Q128JV` rev F) | **Adds a duplicate of the on-module part.** Same class (Quad SPI NOR). Rated **−40…+85 °C** (Ind.) / **−40…+105 °C** (Ind.+), i.e. still short of the −50…−56 °C flight ambient. Costs an SPI device, a CS/GPIO on a board whose *pin budget* is the stated reason for the S3 (ADR-029 D1 item 1), ~0.10 g (ESTIMATE) and euros — for capacity the link cannot drain. |
| **`24LC256-I/SN` I²C EEPROM, 32 KB** (Microchip DS20001203) | Only 32 KB; 5 ms write cycle; rated −40…+85 °C (I) / −40…+125 °C (E). Its entire use case (small rarely-written config/calibration) is already served by internal NVS at 0 g. |
| **`FM25W256-G` SPI FRAM, 32 KB** (Infineon/Cypress) | Its headline advantage — **10¹⁴ read/write cycles** — is **unexercised** on this board (§D2.3). Rated −40…+85 °C. Same 0 g-is-available objection. |
| **microSD socket (`693072010801`) + card** | **Disqualified on temperature before mass is considered:** the **socket** is rated **−25…+85 °C** and mainstream cards **−25…+85 °C** (SanDisk Industrial I) — **25–31 K outside the flight ambient**; even an industrial-temperature card (Kingston **−40…+85 °C**, SanDisk XI) is 10–16 K short. It also adds a **mechanically intermittent connector** (~1 g+ socket+card) to a vehicle that deliberately avoids them. |
| **Bonding more PSRAM/SPI on the second SPI master** | The 8 MB octal PSRAM is already fitted and IO35/36/37 are consumed by it (Espressif DS v1.8 Table 1-2 note b; ADR-029 D1.1). The second master exists for the **logging/peripheral bus** (ADR-029 D1 item 2) — that is a bus for peripherals, not a reason to buy a storage chip. |

### D2 — PSRAM is a volatile staging buffer; the persistent log lives in flash

**This is the correction the operator's premise needs most.**

- ADR-036 makes **night deep-sleep mandatory** and **accepts a cold start at dawn** (its
  decision sub-parts 3 and 4). ADR-029 D1 item 3 gives "8 MB PSRAM for on-board logging".
  **PSRAM is volatile RAM.** Anything held only in PSRAM does not survive the night, let alone
  a cold start.
- **Decision:** the persistent flight log lives in the module's **flash** (NVS and/or a
  wear-levelled filesystem partition — the project already builds both: `nvs_flash` and
  `esp_littlefs`). **PSRAM is only a volatile staging/working buffer** for the burst log
  ADR-029 describes. A log design that assumes PSRAM persistence across the night is a bug.

**D2.1 — Endurance:** flash is erased per **4 KB sector** and rated **≥ 100 K program-erase
cycles per sector** (W25Q-class feature figure). An append-mostly log with a ring/wear-levelling
allocator stays inside budget by a wide margin (the analysis §3.2 shows a 4 KB-per-minute log
burning 43 % of one sector's budget over 30 days, or **2.7 %** spread over 16 sectors).
**Wear levelling is mandatory, not optional** — and it is configuration, not new development,
because ESP-IDF NVS and LittleFS already provide it.

**D2.2 — Cold is an accepted risk, not a selection criterion.** The module (R8 variant) is
rated to **−40 °C ambient**; the flight case is **−50…−56 °C**, design **−60 °C**. This is the
*same* finding the array work already recorded and accepted (ADR-054 open item 2;
`docs/analysis/array-topology-fault-tolerance.md` §9.5: "−55 °C diodes / −40 °C converters
against a −60 °C case"), and the gap is closed per **ADR-043 decision 2 / ADR-056 §D5 — by
part selection or explicit accepted-and-characterised behaviour, never by heating.**
**No storage part, internal or external, is rated for −50 °C.** The cold-qualification effort
belongs to the parts already on the critical path (ADR-043), not to a storage chip.

**D2.3 — FRAM's unlimited endurance is not needed here, and this is recorded so the question
is visibly answered for every store on the board.** Endurance matters when *one location* is
rewritten continuously. On this board:

- the **flight log** is append-mostly → NOR flash + wear levelling suffices;
- the **calibration curve** is written **once per unit** (ADR-058 D4) → endurance irrelevant;
- the **cut-fired flags** are 4 bits written at most **4 times per flight** (ADR-051 §2.5.1)
  → endurance irrelevant;
- **configuration** is written rarely → endurance irrelevant.

**So FRAM is rejected on the grounds that its advantage is unused, not on price.**

### D3 — The TX store-and-forward buffer is sized by (contact window × achievable rate), and is 128 KB

**Storage is nearly free on this vehicle; transmission is not. The buffer is sized to what
the link can carry, never to flash capacity.**

**The arithmetic (COMPUTED; every input CITED — full working in the analysis §4):**

```
E per byte = P_TX_DC / R_air × 8
           = 6.15 W / 22 000 bit/s × 8
           = 2.236e-3 J/byte  ≈ 2.24 mJ per transmitted byte
  [6.15 W from docs/analysis/mppt-charge-path-specification.md §3.5 ("0.615 J per slot");
   22 kbps from ADR-009; cross-checked: 0.615 J ÷ 275 bytes = 2.236 mJ/byte]

bytes per full usable bank = 33.264 J / 2.236e-3 J/byte = 14 876 B ≈ 15 KB
  [33.264 J = ADR-047 §3.2 via mppt-charge-path-specification §3.5]

contact window W :  bytes = (33.264 J + 0.388 W · W) / 2.236e-3 J/byte
  [0.388 W = array average, POWER-BUDGET-V9-D2BE.md §2]
  W = 60 s   →  56.6 J  →   25.3 KB
  W = 300 s  → 149.7 J  →   67.0 KB
  W = 600 s  → 266.1 J  → 119.0 KB   ← the recommended sizing basis
```

**Decision: a 128 KB store-and-forward buffer** (2¹⁷ B) — one **10-minute contact window**
with ~2× headroom over the 119 KB measured figure — held in internal flash as a ring.

**And the honest upper bound, decided too:** **do not allocate more than ~1 MB to the TX
store.** `1 MB / 2.236e-3 = 2 344 J = 70× the usable bank`; a megabyte is more than a day's
worth of bank discharges. **Storing megabytes you can never afford to transmit is worthless.**

**Day ceiling (COMPUTED):** 0.388 W average ÷ 6.15 W TX DC = **6.3 % duty cycle** →
`0.063 × 36 000 s × 22 000 bit/s / 8 = 6.2 MB/day` in a 10 h daylight window, if *all*
harvest went to the downlink. `TODO(unverified)`: the licence-exempt 10 mW ERP throttle lowers
the PA's DC draw, which would raise this bound — but then the *rate at 10 mW ERP* (ADR-041's
open item) becomes binding. The bench measurement that settles both is a rate-vs-power sweep
at 10 mW ERP.

**Two stores, not one, and the record says so plainly:**

| Store | Size | Written | Transmitted | Sized by |
|---|---|---|---|---|
| **Flight log** (the primary evidence source, ADR-036) | **≥ 1 MB, up to ~4 MB free** | continuously | **never — recovered physically** | **flash** |
| **TX store-and-forward buffer** | **128 KB** (upper bound ~1 MB) | per event | **yes** | **the link (§D3 above)** |

Conflating them is the error the flash-capacity framing invites.

### D4 — No Blossom server and no relay cache on the balloon; Blossom as a *client* is kept open

**A Blossom server (BUD-01/02/11) is a content-addressed HTTP blob store: a SERVE-mostly
pattern.** That is the wrong direction of the link for this vehicle, and the record says why
with numbers:

```
serve 1 MB = 1 048 576 B × 2.236e-3 J/B = 2 344 J
  vs the 33.264 J usable bank        → 70×  the ENTIRE usable bank
  vs the 0.388 W array average       → 6 041 s = 1.68 h of the WHOLE array's output
serve one 15 KB blob (one bank)      → 33.5 J ≈ the entire bank, for one small blob
```

At night the answer is absolute: the **night anchor is 100 µW** (ADR-036; restated in ADR-051
§1.6 and ADR-050 §3.6) and the vehicle is in **mandatory deep sleep**. During daylight the link
"opens for minutes at a time"; a serve-mostly node must be awake and radiating **on a client's
schedule**, drawing on a bank sized to one burst. The repo's own relay risk table states the
same failure mode (ADR-013: *"Channel saturation … A dumb repeater seeing hundreds of nodes
would exceed the 10 % EU duty cycle"*), and ADR-027 (Accepted) already fixes Blossom on the
IP/HTTP layer.

**Decision:**

- **A Blossom server or a relay cache running ON the balloon is NOT sensible and is not
  adopted.** Rejected on energy, not on storage.
- **The defensible pattern IS adopted: write-mostly store-and-forward with opportunistic
  upload** — a delay-tolerant node that logs continuously, queues a 128 KB subset, and
  transmits **when the link and ADR-036's energy policy allow**, draining the queue. Vehicle-
  initiated, time-shifted, bounded by what it can afford to send.
- **Blossom is kept open as a *client* to a ground-side server** — the balloon pushing blobs
  during an opportunistic window, with the *serving* cost on the mains-powered, 12–15 dBi-Yagi
  ground side. That preserves ADR-027's layer separation and puts the energy where it is.

### D5 — Internal NVS is the store for the calibration blob and the cut-fired flags (answering ADR-058 D4)

**ADR-058 D4 requires** a **persistent, per-unit, written-once-at-bench, read-at-boot,
validated-on-load** record for the per-unit temperature-calibration curve, and defers the
*part* to this task.

| Requirement | Value | Source |
|---|---|---|
| Type | `temp_comp_curve_t` = `pts[16]` of `{float temp_c; float ppm;}` + `uint8_t n` | `firmware/rp2040/src/temp_comp.h` |
| **Blob size** | **129 bytes** | COMPUTED (16 × 8 B + 1 B) |
| Write frequency | **once per unit** | ADR-058 D4 |
| Read frequency | at boot | ADR-058 D4 |
| Validation | range + ascending-order check by the loader | `temp_comp.cpp` `temp_comp_curve_load()` |
| Failure mode if lost | identity (0.0 ppm) — empty/identity until the bench fills it | ADR-058 D2(b) |

**Decision: internal NVS** (16 KB partition; holds the 129 B record ~127× over). **EEPROM and
FRAM are NOT needed** — the write count is one per unit, so FRAM's endurance advantage is
unexercised, and the EEPROM's 5 ms write cycle buys nothing for a single bench write. The
**cut-fired flag** per channel (ADR-051 §2.5.1) has the same profile and uses the same store.

**This record therefore closes ADR-058 D4's deferral with: "internal NVS on the module's own
8 MB flash; no external part."**

### D6 — Use-case ranking (the tail of this decision)

Ranked by value for this mission (full ranking and rationale in the analysis §7):

1. **Flight log surviving link outages** (`log-don't-tune`, ADR-042 A6) — **internal flash**,
   ≥ 1 MB, write-mostly, never transmitted. Highest value: ADR-036 makes it the primary
   evidence source.
2. **Per-unit calibration curve** (ADR-058 D4) — **internal NVS**, 129 B, write-once.
3. **Store-and-forward RX buffer** — internal flash, **128 KB**.
4. **Configuration** — internal NVS, bytes.
5. **Post-flight reconstruction** — *not a separate store*; it is a **consumer** of (1) and a
   **recovery-plan** item (cut-down + USB-Serial-JTAG read), not a storage part.

---

## Consequences

- **No BOM line, no mass, no cost, no new GPIO, no new schematic change.** The decision is
  satisfied by partition tables and firmware. Mass consequence: **0 g added**; the storage
  mass is the module's own (2.5 g ESTIMATE, `TODO(unverified)` — see open items).
- **A partition-table task exists** and is the real deliverable: a 2 MB-class app partition, a
  16 KB NVS partition, a ≥ 1 MB wear-levelled log partition, and a 128 KB TX store — all
  inside 8 MB. That is a *partition* decision, not a *procurement* decision.
- **The night-log question is now a firmware question, not a storage question.**
  ADR-036's open item ("the payload's deep-sleep current in µA") is unaffected; this ADR only
  removes the false comfort of "PSRAM holds the log".
- **Cold stays an accepted, characterised risk** (ADR-043 / ADR-056 §D5). This ADR adds
  **no new cold exposure**, because it adds no part.
- **A repo correction is carried:** the 16 MB flash claim in
  `tracker/firmware/sdkconfig.defaults.esp32s3` and ADR-029 D1 item 5 is wrong for
  `-N8R8`. ADR-029 is **not** edited here.
- **Blossom's on-balloon server role is closed** for this vehicle; its ground-side client
  role stays open, consistent with ADR-027.

---

## What is NOT decided (stated explicitly)

1. **The partition table itself** — sizes, offsets, filesystem choice (LittleFS vs raw ring vs
   NVS blobs), and the log record format. This record fixes *that there is enough flash and
   how the stores must behave*, not *the exact layout*. That is a follow-up card.
2. **The log rate, retention policy and eviction rule** — what is logged, at what rate, and
   what is overwritten first when the ring fills. `log-don't-tune` (ADR-042 A6) mandates
   logging the ESP32 die temperature rather than tuning on it; the wider log-content policy is
   **not** decided here.
3. **Whether the PSRAM is used at all for log staging, and its size** — this ADR forbids
   *relying* on PSRAM for persistence; it does not forbid using it as a working buffer.
4. **The licence-exempt achievable rate at ≤ 10 mW ERP**, and therefore the final buffer-size
   confirmation — see Open items. The 128 KB recommendation rests on ADR-009's 22 kbps, which
   was derived at +22 dBm with an FEM.
5. **The exact NVS blob layout** for the calibration curve and the cut-fired flags (key names,
   versioning, CRC) — ADR-058 D4 fixes the *validation* requirement, not the encoding.
6. **Any external part whatsoever.** None is fitted; if a future variant needs one, it needs a
   new record, and the analysis §2 gives the data to write it.
7. **Blossom's ground-side protocol details** (which server, BUD versions, auth) — ADR-027
   owns the layer decision; this record only keeps the client role open.

---

## Open items

1. **`ESP32-S3-WROOM-1U-N8R8` mass — `TODO(unverified)`.** No mass figure exists anywhere in
   this repo (`docs/POWER-BUDGET-V9-D2BE.md` §4 line 178; `docs/analysis/two-variant-mass-budget.md`
   §0 caveat 2). Settled by weighing one module on the repo's 0.01 g scale
   (`docs/inventory.md` line 68, "MS300 Waage"). Carried from the mass-budget analysis,
   repeated here because this ADR's "0 g added" claim is relative to that mass.
2. **Achievable rate at ≤ 10 mW ERP — `TODO(unverified)`.** ADR-009's 22 kbps was derived at
   +22 dBm with an FEM. ADR-041 fixes the *margin* under licence-exempt but not the *rate*.
   The buffer sizing (D3) is gated on this. **The measurement is a rate-vs-power sweep at
   10 mW ERP.**
3. **The PA's DC draw at ≤ 10 mW ERP — `TODO(unverified)`.** D3 uses the 6.15 W full-power
   figure; the day ceiling (§D3) would rise if the throttled draw is much lower.
4. **Cold behaviour of the on-module flash and MCU at −50/−60 °C — `TODO(unverified)`.**
   Datasheet stops at −40 °C. Belongs to ADR-043's cold-qualification scope.
5. **Log filesystem power-fail integrity across a cold start at dawn — `TODO(unverified)`.**
   ADR-036 accepts a cold start; the log's integrity across brown-out depends on the chosen
   store's power-fail design (LittleFS is designed for it; a raw ring is not, unless firmware
   makes it so). Bench-verify the chosen path.
6. **Wear-levelling budget for the chosen log allocator — `TODO(unverified)`.** The analysis
   §3.2 arithmetic is illustrative; the real figure needs the log rate and the ring design.
7. **Prices for the rejected externals — `TODO(unverified)`.** No price source was read;
   not load-bearing, since the decision is to add nothing.

---

## What would falsify this

- **A measured achievable rate far below 22 kbps** (e.g. the 1.7 kbps that ADR-009 rejects for
  868 MHz) would shrink the buffer arithmetic ~13× (to ~9 KB per 10-minute window). It would
  **not** overturn D1 (internal flash still suffices) but would change D3's recommended size.
- **A measured deep-sleep current in the mA range** would mean the night LOG cannot survive on
  firmware alone (ADR-036 open item). That reopens the **bank** sizing, not this record's
  flash decision — the log still lives in flash; whether the vehicle can keep the log running
  at night becomes an energy question.
- **A requirement for the balloon to *serve* blobs to third parties** would reopen D4. The
  arithmetic (70× the bank per megabyte served) would have to be answered first, and the
  answer would be a ground-side server.
- **A datasheet showing a cold-rated (−55 °C or better) SOIC-8 NOR/FRAM part** would make an
  external part *cold-viable* — but still unnecessary given ≈ 4 MB of free internal flash. No
  such part was found for this record.
