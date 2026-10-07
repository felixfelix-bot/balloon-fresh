# On-board storage for the v9 balloon payload — what we already have, what adding more would take, and what size the buffer should actually be

**STATUS: this is an ANALYSIS, not a decision record.** It assembles evidence, does
arithmetic, and ranks options. The *decision* it feeds is recorded separately in
`docs/adr/059-onboard-storage.md`. Nothing here is a fabrication authority and **no
hardware is ordered by it** (design work only).

- Date: 2026-10-07
- Author: Hermes subagent, branch `adr/onboard-storage`
- Base: `github/main` @ `23a621c` (`merge(analysis): analysis/meshcore-lr2021-drift`)
- Operator's question (verbatim intent): *"what would it take to store stuff on the board?
  For instance a master relay or a blossom server can include a very lightweight, small,
  compact, cheap flash storage on the board?"*
- Provenance legend: **CITED** = a repo file or a datasheet read for this analysis (both
  named) · **COMPUTED** = arithmetic shown in-line · **ESTIMATE** = a labelled analogy or a
  dimensional calculation, *not* a datasheet figure · `TODO(unverified)` = no source
  carries it.

---

## 0. Answer first

1. **The board already carries the storage.** The `ESP32-S3-WROOM-1U-N8R8` is **8 MB of
   Quad SPI flash *plus* 8 MB of Octal SPI PSRAM on the module** (CITED, Espressif
   `ESP32-S3-WROOM-1 & WROOM-1U` datasheet v1.8, Tables 1-1/1-2). Roughly **4–6 MB of the
   flash is free for data after firmware**, and the repo's own blossom design already
   assumes ~4 MB of it is available on an S3. **The cheapest storage is the storage we
   already bought: no external part is required.**
2. **What is *not* true** is that PSRAM is where the flight log lives. PSRAM is **volatile
   RAM**. ADR-036 mandates a **night deep-sleep with a cold start at dawn** — anything held
   only in PSRAM does not survive the night. The persistent flight log must live in the
   module's **flash**, and PSRAM is only a volatile staging buffer. This refines ADR-036's
   "8 MB PSRAM / flash logging" wording and is the single most load-bearing correction in
   this analysis.
3. **Adding external storage buys nothing and breaks on cold.** Every candidate (SPI NOR,
   EEPROM, FRAM, microSD) is rated to **at best −40 °C**, against a −50…−56 °C ambient and
   a −60 °C design case. microSD is the worst: the *cards* are rated **−25 °C to +85 °C**
   (SanDisk Industrial; the industrial-temperature Kingston part only reaches −40 °C) and
   the *socket* is rated −25…+85 °C (Würth 693072010801). All of them cost grams and euros
   to add a capability the module already has.
4. **Storage is nearly free; transmission is not.** At the repo's own numbers —
   **6.15 W × 0.1 s = 0.615 J per sub-GHz TX slot** and **22 kbps achievable at 300 km** —
   the marginal cost of a transmitted byte is **≈ 2.24 mJ**. The entire usable bank
   (**33.264 J**) buys **≈ 15 KB** of downlink. Therefore the TX buffer is sized by
   **(contact window × achievable rate)**, never by flash capacity. Storing megabytes you
   can never afford to transmit is worthless.
5. **A Blossom server or relay cache on the balloon is not sensible. Write-mostly
   store-and-forward with opportunistic upload is.** Serving one 1 MB blob would cost
   **≈ 2.34 kJ = 70× the whole usable bank = 1.68 h of the entire array's output.**
6. **The one hard requirement already on the board** is the sibling record's per-unit
   temperature-calibration curve (`docs/adr/058-onboard-temp-compensation.md` D4, branch
   `adr/058-...`): a **129-byte `temp_comp_curve_t` blob**, written **once** at bench
   characterisation, read at boot. Internal NVS on the module's own flash serves it
   exactly, with no external part.

---

## 1. What storage we already have

### 1.1 The module's on-module flash and PSRAM — datasheet, not memory

The part is fixed by ADR-029 D1 (`docs/adr/029-dual-band-flight-board.md`, line 98):
the v9 MCU is **`ESP32-S3-WROOM-1U-N8R8`**.

> Espressif **`ESP32-S3-WROOM-1 & WROOM-1U` Datasheet v1.8**, Table 1-2
> ("ESP32-S3-WROOM-1U Series Comparison"), read for this analysis:
> **`ESP32-S3-WROOM-1U-N8R8` — Flash: 8 MB (Quad SPI); PSRAM: 8 MB (Octal SPI);
> Ambient Temp. −40 ~ 65 °C.**
> Datasheet text, §1: *"R8 and R16V series modules operate at −40 ~ 65 °C ambient
> temperature, and other module variants operate at −40 ~ 85 °C ambient temperature."*
> Table 1-2 note `b`: *"For modules with Octal SPI PSRAM, i.e., modules embedded with
> ESP32-S3R8 or ESP32-S3R16V, pins IO35, IO36, and IO37 are connected to the Octal SPI
> PSRAM and are not available for other uses."*

So the part number decodes exactly as the repo's own `docs/V9-RADIO-SITE-MATRIX.md` line 70
and `docs/SX1280-ARRAY-FEASIBILITY.md` line 75 already assume: **N8 = 8 MB flash, R8 = 8 MB
PSRAM**, and the `-1U` suffix is the U.FL antenna variant.

**Three consequences the analysis must state plainly:**

- **A repo contradiction to correct.** `tracker/firmware/sdkconfig.defaults.esp32s3` line 2
  says *"S3 boards: 16MB flash, 8MB PSRAM (octal)"*, and ADR-029 D1 item 5 repeats
  *"16 MB flash / 8 MB octal PSRAM per its own header comment."* **That header comment is
  wrong for the `-N8R8` module** — the N8R8 part is **8 MB flash**, not 16 MB. The 16 MB
  figure belongs to the *TollGate* boards (a different module in this repo's other track),
  not to the flight module. Design, partition tables and any "how much flash" claim must
  use **8 MB**, i.e. half the number the stale comment implies. (Flagged for the manager;
  this analysis does not edit ADR-029.)
- **Cold: the module itself is out of spec.** The R8 variants are rated only to
  **−40 °C ambient**; the flight ambient is **−50 to −56 °C** and the design case is
  **−60 °C** (ADR-036/ADR-042/ADR-054). This is not a storage failure — it is the same
  pattern the array work already found (ADR-054 open item 2: "−55 °C diodes / −40 °C
  converters against a −60 °C case", `docs/analysis/array-topology-fault-tolerance.md`
  §9.5). The cold end is an **accepted, characterised risk** (ADR-043 decision 2 /
  ADR-056 §D5), not a part-selection win. **Nothing on this board — internal or external —
  is rated for −50 °C.**
- **IO35/36/37 are consumed** by the octal PSRAM. This is already recorded in ADR-029 D1.1
  and `docs/V9-RADIO-SITE-MATRIX.md`; repeating it here only to confirm the datasheet
  agrees with the repo.

### 1.2 How much of the 8 MB is realistically available for data

| Item | Value | Source |
|---|---|---|
| Module flash total | **8 MB (8,388,608 B)** | **CITED** Espressif DS v1.8 Table 1-2 |
| App partition (repo's own blossom precedent) | **2 MB** (`0x200000`) | **CITED** `firmware/blossom-server/partitions.csv` line 5 |
| NVS (repo's own blossom precedent) | **16 KB** (`0x4000`) | **CITED** same file line 2 |
| otadata + phy_init | 0x2000 + 0x1000 ≈ 12 KB | **CITED** same file, lines 3–4 |
| Data partition in the repo's own S3 blossom assumption | **~4 MB** | **CITED** `docs/blossom-design.md` §6 ("Storage Limits (ESP32-S3) · Total flash: 8MB typically · Blossom partition: ~4MB") |
| **Realistically free for data after firmware** | **≈ 4 MB (repo's own figure); up to ≈ 6 MB with a lean app** | **COMPUTED** 8 MB − 2 MB app − ~30 KB system partitions = 5.97 MB; the repo's conservative own assumption is 4 MB |

**Even the conservative figure — 4 MB — is 270× more than the ~15 KB the link can carry in
one bank discharge (§3).** The storage question is not "can we afford flash", it is "what
will we ever be able to transmit".

### 1.3 Mass of what we already have

| Item | Mass | Source |
|---|---|---|
| `ESP32-S3-WROOM-1U-N8R8` module (incl. its 8 MB flash + 8 MB PSRAM) | **2.5 g** | **ESTIMATE** by analogy to the repo's `ESP32-C3-Mini-1` line (2.5 g) in `docs/analysis/two-variant-mass-budget.md` §3.1 A2; `TODO(unverified)` — **no S3 module mass exists anywhere in this repo**, and `docs/POWER-BUDGET-V9-D2BE.md` §4 line 178 lists the S3 as `TODO(unverified)` |
| External storage on v9 today | **0 g** | by definition — there is none |

**The mass the operator's question is really about is already paid.** Any external part is
*additive* grams on a vehicle whose binding constraint is mass (Variant B target < 20 g).

---

## 2. What adding more would take — real parts, real packages, real ratings

The candidates, with the datasheets read for this analysis. **Mass for every SOIC-8 part is
an ESTIMATE**, because no vendor publishes per-package mass in these datasheets; the
estimate is a dimensional calculation from the datasheet's own package table with an epoxy
density of ~1.9 g/cm³. It is labelled as such and never presented as a datasheet figure.

### (a) SPI NOR flash in SOIC-8 — e.g. Winbond `W25Q128JVSIQ`

| Attribute | Value | Provenance |
|---|---|---|
| Part | **`W25Q128JVSIQ`** (Winbond `W25Q128JV`, package code **S**) | **CITED** Winbond datasheet *"W25Q128JV — 3V 128M-BIT SERIAL FLASH MEMORY WITH DUAL/QUAD SPI For Industrial & Industrial Plus Grade"*, rev F 2018/03/27 |
| Capacity | **128 Mbit = 16 MB** | **CITED** title page |
| Package | **8-pin SOIC 208-mil** | **CITED** §3.1, §10.1 ("8-Pin SOIC 208-mil (Package Code S)") |
| Geometry | 256 B page · **4 KB sector** · 64 KB block | **CITED** §8 ("65,536 programmable pages of 256-bytes each … 4,096 erasable sectors") |
| Endurance | **"Min. 100K Program-Erase cycles per sector"** | **CITED** Feature list |
| **Operating temperature** | **Industrial −40 → +85 °C**; **Industrial Plus −40 → +105 °C** | **CITED** §"Absolute Maximum / Operating", table lines: `Ambient Temperature, Operating — Industrial –40 … +85 °C; Industrial Plus –40 … +105 °C` |
| Pocket/package size | 5.23 × 5.23 × ~1.95 mm body (D1 × E1 × A, nominal) | **CITED** §10.1 dimension table |
| Mass | **≈ 0.10 g (ESTIMATE)** | **COMPUTED** 0.523 × 0.523 × 0.195 cm = 0.0533 cm³ × 1.9 g/cm³ = 0.101 g. `TODO(unverified)` — no datasheet mass |
| Price | `TODO(unverified)` — no price source read for this analysis; class-typical low single-digit EUR | — |
| Hand-solderability | **Easy** — 1.27 mm lead pitch, drag-solderable by hand | CITED geometry |

**The decisive point:** the module's own on-module memory is *the same class of part*. The
W25Q128JV is a **Quad SPI NOR** device; the module carries **8 MB of Quad SPI flash** of
exactly that kind. **Adding a W25Q128JV adds a second, colder-unqualified copy of the thing
we already have** — 16 MB more of a resource the link cannot drain, at the cost of grams,
euros, a second SPI device, and an extra GPIO/CS on a board whose pin budget is already the
stated reason for the S3 (ADR-029 D1 item 1).

### (b) I²C/SPI EEPROM — e.g. Microchip `24LC256-I/SN`

| Attribute | Value | Provenance |
|---|---|---|
| Part | **`24LC256-I/SN`** (`24AA256/24LC256/24FC256`) | **CITED** Microchip datasheet DS20001203 |
| Capacity | **256 Kbit = 32 KB** (32K × 8) | **CITED** Device Selection Table / Description |
| Package | **8-lead SOIC (3.90 mm)** | **CITED** package list + §"8-Lead SOIC (3.90 mm)" |
| Interface | I²C, 400 kHz (24LC256) / 1 MHz (24FC256), write-page 64 B | **CITED** front page |
| Endurance | **> 1,000,000 erase/write cycles** | **CITED** Feature list + DC table row 18 (`Endurance 1,000,000 cycles, Page mode, 25 °C, 5.5 V`) |
| Retention | **> 200 years** | **CITED** Feature list |
| **Operating temperature** | **Industrial (I): −40 → +85 °C**; **Automotive (E): −40 → +125 °C** | **CITED** Device Selection Table + DC/AC characteristics headers |
| Mass | **≈ 0.06 g (ESTIMATE)** | **COMPUTED** 0.39 × 0.49 × 0.155 cm = 0.0296 cm³ × 1.9 = 0.056 g. `TODO(unverified)` |
| Price | `TODO(unverified)` | — |
| Hand-solderability | **Easy** (SOIC-8 1.27 mm) but **slow writes**: 5 ms byte/page write cycle | **CITED** AC table row 17 (`TWC 5 ms`) |

32 KB total, and the write-cycle time is 5 ms — fine for configuration and a calibration
blob, wrong for a flight log.

### (c) FRAM — e.g. Infineon (ex-Cypress) `FM25W256-G`

| Attribute | Value | Provenance |
|---|---|---|
| Part | **`FM25W256-G`** | **CITED** FM25W256 datasheet (Infineon/Cypress, distrelec copy `fm25w256_eng_ds.pdf`) |
| Capacity | **256 Kbit = 32 KB** | **CITED** title / ordering info |
| Package | **8-pin "Green"/RoHS SOIC** (JEDEC MS-012 variation AA) | **CITED** Feature list + §8-pin SOIC (JEDEC MS-012 variation AA) |
| Interface | SPI, up to 20 MHz | **CITED** Feature list |
| **Endurance** | **100 trillion (10¹⁴) read/write cycles** — *"or 100 million times more write cycles than EEPROM"* | **CITED** Feature list + §"Endurance" (`least 10¹⁴ read or write cycles`) |
| Retention / cold storage | storage temp **−55 → +125 °C** | **CITED** Absolute Maximum Ratings (`TSTG`) |
| **Operating temperature** | **Industrial −40 → +85 °C** | **CITED** Feature list: *"Industrial Temperature −40 °C to +85 °C"* |
| Mass | **≈ 0.06 g (ESTIMATE)** | **COMPUTED** as (b). `TODO(unverified)` |
| Price | `TODO(unverified)` | — |
| Hand-solderability | **Easy** (SOIC-8 1.27 mm) | CITED |

**FRAM's unlimited endurance is real and is the reason it appears on every "frequently
updated state" shortlist — but see §2.4 and §6.** Its endurance advantage only matters when
the *same* location is rewritten often. Our frequently-written state is the **flight log**,
and a log is append-mostly, which NOR flash already handles with wear levelling (§3.4).

### (d) microSD socket + card — and why it is disqualified before mass is considered

| Attribute | Value | Provenance |
|---|---|---|
| Socket part | **Würth Elektronik `693072010801`** (microSD push-push, SMT) | **CITED** Würth datasheet `693072010801.pdf`, read for this analysis |
| Socket **operating temperature** | **−25 °C up to +85 °C** | **CITED** Würth datasheet, "Operating Temperature" row |
| Socket durability | 10,000 mating cycles | **CITED** same sheet, "Durability" row |
| Socket dimensions | ≈ **14.5 × 12.3 × 1.75 mm** (overall, incl. shell) | **CITED** same sheet, dimensions block |
| Socket mass | **gram-class; `TODO(unverified)`** | **ESTIMATE** — no datasheet mass. Dimensional upper bound: 1.45 × 1.23 × 0.175 cm = 0.312 cm³; even a light 1.5 g/cm³ average mix gives ~0.47 g, and the real part is a plastic body + stainless-steel shell, so it is **milligram-to-gram class, not sub-0.1 g** |
| Card (industrial) | **SanDisk Industrial grade microSD** | **CITED** Western Digital "Industrial Grade microSD / SD Card Portfolio" brochure |
| Card **operating temperature** | **I: −25 °C to +85 °C; XI: −40 °C to +85 °C** | **CITED** same brochure, "Operating Temperature" row |
| Card (industrial-temp example) | **Kingston Industrial Temperature microSD UHS-I** — *"operating temperature rating of −40 °C to 85 °C"* | **CITED** Kingston `SDCIT_en.pdf` |
| Card mass | **0.5 g typ.** (L 15 × W 11 × T 1.0 mm) | **CITED** Kingston `SDCIT-specsheet-8gb-32gb_en.pdf`, Physical row: *"L: 15, W: 11, T: 1.0 (mm), Weight: 0.5g (typ.)"* |

**Be blunt about this one:**

- **The socket alone is a gram-class mechanical part** (14.5 × 12.3 × 1.75 mm of plastic
  and stainless steel) — not a "lightweight, small, compact, cheap" flash chip. On a vehicle
  where 3 g of supercaps is a headline item, a socket plus card is a **~1 g** addition for a
  capability that is already on the module.
- **Both the socket and the mainstream cards are rated to −25 °C.** The flight case is
  −50 to −56 °C. **That is 25–31 K outside the socket's rating and 25–31 K outside the
  card's rating, before any electrical derating.** Even the best industrial-temperature
  card (Kingston, SanDisk XI) reaches only **−40 °C** — still 10–16 K short.
- **A card is a connector, and a connector is an intermittent-contact failure mode** the
  rest of this vehicle (soldered, unsealed, vibration-and-rotation-exposed, ADR-052
  end-only cell mounting) deliberately avoids.

**microSD is disqualified on temperature and reliability.** It should not be selected, and
its disqualification does not depend on its mass at all.

### 2.4 Comparison table (all four externals vs. what we have)

| Option | Capacity | Package | Operating temp | Endurance (writes) | Mass | Verdict for THIS mission |
|---|---|---|---|---|---|---|
| **On-module flash (already fitted)** | **8 MB** | on-module Quad SPI NOR | **−40…+65 °C** (module) | ~100 K cycles/sector + wear levelling | **0 g added** (in the 2.5 g module already counted) | **SELECT** |
| (a) `W25Q128JVSIQ` | 16 MB | SOIC-8 208-mil | −40…+85 (Ind.) / −40…+105 (Ind.+) | 100 K cycles/sector | ~0.10 g (ESTIMATE) | Reject — adds a duplicate of what we have, still not cold-rated |
| (b) `24LC256-I/SN` | 32 KB | SOIC-8 3.9 mm | −40…+85 (I) / −40…+125 (E) | 1 M cycles | ~0.06 g (ESTIMATE) | Reject as *storage*; internal NVS already covers its use case |
| (c) `FM25W256-G` | 32 KB | SOIC-8 | −40…+85 | **10¹⁴ cycles** | ~0.06 g (ESTIMATE) | Reject — endurance advantage is unused (§3.4, §6) |
| (d) Würth `693072010801` + microSD | GB | socket + card | **−25…+85 (socket) / −25…+85 or −40…+85 (card)** | card-grade | ~1 g+ (ESTIMATE) | **Reject — fails cold by 25–31 K and adds a connector** |

---

## 3. The cold and endurance constraints

### 3.1 Temperature: nothing here meets −60 °C, and that is already an accepted risk

| Part | Rated operating min | vs. −50 °C flight ambient | vs. −60 °C design case |
|---|---|---|---|
| `ESP32-S3-WROOM-1U-N8R8` (R8 variant) | **−40 °C** | **10 K short** | **20 K short** |
| `W25Q128JV` (Ind. / Ind.+) | **−40 °C** | 10 K short | 20 K short |
| `24LC256` (I / E) | **−40 °C** | 10 K short | 20 K short |
| `FM25W256` | **−40 °C** | 10 K short | 20 K short |
| Würth microSD socket | **−25 °C** | **25 K short** | **35 K short** |
| SanDisk microSD (I / XI) | **−25 °C / −40 °C** | 10–25 K short | 20–35 K short |
| Kingston Industrial microSD | **−40 °C** | 10 K short | 20 K short |

**This is the same finding the array work already produced and accepted** (ADR-054 open item
2, citing `docs/analysis/array-topology-fault-tolerance.md` §9.5: "−55 °C diodes / −40 °C
converters against a −60 °C case"). ADR-043 decision 2 and ADR-056 §D5 close the gap by
**part selection or explicit accepted-and-characterised behaviour — not by heating**
(heating costs 0.160 W = 41 % of the daylight average and 173× the bank over a 10 h night).

**Therefore: cold is not a reason to *choose* one of these parts.** It is a reason to
**not add a part that makes the cold exposure worse** (microSD's connector, an extra SPI
device to characterise), and to spend the cold-qualification effort on the parts that are
already on the critical path (ADR-043).

### 3.2 NOR flash endurance and wear levelling

- **Endurance:** the class figure is **"Min. 100K Program-Erase cycles per sector"**
  (`W25Q128JV` datasheet, feature list). The on-module flash is the same class.
- **Geometry that makes wear levelling tractable:** 4 KB sectors, 64 KB blocks
  (`W25Q128JV` §8). Erases happen per sector, not per byte.
- **Why it matters here:** a flash *log* is append-mostly, so a naive "rewrite the head
  sector every second" is exactly the pattern that burns a sector out. Worn levelling is
  mandatory, not optional.
- **Scale check (COMPUTED):** a 4 KB log sector rewritten once a minute for a 30-day
  flight = 43,200 erase cycles — **43 % of the 100 K budget for that sector in one flight**.
  Spread across, say, 16 log sectors by a ring allocator, the same traffic is 2,700
  cycles/sector = **2.7 %** of budget. This is what wear levelling buys, and it is why the
  headline "NOR has only 100 K cycles" is not the limitation people assume — provided the
  firmware does the ring/wear-levelling work.
- **What ESP-IDF already provides:** the repo's TollGate side uses `nvs_flash` (ESP-IDF NVS,
  `tracker/firmware/sdkconfig` line 1895ff) and `littlefs` (`firmware/blossom-server/partitions.csv`).
  NVS is a wear-levelled key-value store; LittleFS is a wear-levelled filesystem. **Both are
  already in this project's toolchain**, so the wear-levelling work is *configuration*, not
  new development.

### 3.3 Does FRAM's unlimited endurance change the choice? For *this* board's state, no.

FRAM's 10¹⁴ cycles (100 million × EEPROM) is decisive when one location is rewritten
continuously — e.g. a per-second high-score counter, or a state machine whose single
"progress" word is updated thousands of times a second.

**Our frequently-written state is the flight log, and a log is append-mostly.** Even the
worst realistic log pattern (a 4 KB sector per minute) fits the internal flash's 100 K-cycle
budget across a whole flight with a modest ring allocator (§3.2). Meanwhile the
*rarely-written* state we actually must protect is:

- the sibling record's **per-unit calibration curve** (`temp_comp_curve_t`, **129 bytes**,
  written once at bench time, read at boot — ADR-058 D4), and
- configuration (**bytes**, written rarely).

**Both are write-once/write-rarely, so endurance is irrelevant to them.** Internal NVS
covers both. **FRAM would be bought at gram + euro + a second SPI device cost to solve a
problem this vehicle does not have.** Recorded as a rejected alternative, not as a
recommendation.

### 3.4 The one place endurance *would* matter, and why it still doesn't change the answer

`docs/adr/051-hub-array-and-cut-topology.md` §2.5.1 (and the v9 schematic notes generated by
`tracker/hardware/schematics/flight_board/build_flight_sch.py` line 1611, 1805) mandate a
**"latched one-shot with a persistent NVS fired flag per channel"** for the irreversible wing
cuts, because a re-fire costs ~2.59 J of the bank's 16.63 J usable energy. That flag is
**4 bits of state**, written at most 4 times per flight. NVS holds it; FRAM's endurance is
still irrelevant. Recorded so the reader sees the endurance question was actually asked of
every store on this board and not skipped.

---

## 4. Size the buffer properly — the point of the whole exercise

**On this vehicle storage is nearly free and TRANSMISSION is expensive.** The buffer must be
sized by what the link can carry, not by what flash can hold.

### 4.1 Energy per transmitted byte, from the repo's own numbers

| Input | Value | Source |
|---|---|---|
| Sub-GHz TX DC power at the flight power point | **6.15 W** | **CITED** `docs/analysis/mppt-charge-path-specification.md` §3.5: *"6.15 W × 0.1 s = 0.615 J per slot"* |
| Achievable air rate at ~300 km | **22 kbps** | **CITED** ADR-009 `docs/adr/009-antenna-strategy-v1-v2.md`: *"22 kbps at 300 km with just a wire dipole and ground station gain"* (SF9/1625); 38 kbps with a 7 dBi Yagi; ~88 kbps with 4× multi-WAN bonding. `TODO(unverified)` under the **licence-exempt** regime: ADR-041 gives *margins* (+24.3/+30.3 dB on the 433 downlink at 10 mW ERP) but no *rate*; a rate at 10 mW ERP is a computed/bench measurement. This analysis uses the repo's only rate figure, 22 kbps. |
| Usable bank energy | **33.264 J** | **CITED** ADR-047 §3.2 via `docs/analysis/mppt-charge-path-specification.md` §3.5 (`E_usable = 33.264 J`) |
| Array average | **0.388 W** | **CITED** `docs/POWER-BUDGET-V9-D2BE.md` §2 (the representative average load) |

**COMPUTED — energy per byte:**

```
E per bit  = P_TX_DC / R_air = 6.15 W / 22 000 bit/s = 2.795e-4 J/bit
E per byte = 8 × 2.795e-4 = 2.236e-3 J/byte ≈ 2.24 mJ per byte

Cross-check against the repo's own slot unit:
  0.615 J per 0.1 s slot ÷ (22 000 bit/s × 0.1 s) = 0.615 / 2200 bit = 2.795e-4 J/bit  ✓ same
  0.615 J ÷ 275 bytes = 2.236 mJ/byte                                                 ✓ same
```

**COMPUTED — what the whole bank buys:**

```
bytes per full bank discharge = 33.264 J / 2.236e-3 J/byte = 14 876 bytes ≈ 14.9 KB ≈ 15 KB
```

**One entire usable bank ≈ 15 KB of downlink.** That single number is the whole sizing
argument. It does not matter that flash is 8 MB.

### 4.2 The buffer = (contact window × achievable rate), with the window energy-bounded

The "pass" is the interval in which the link is up and the vehicle has the energy to use it.
Energy available in a window of `W` seconds:

```
E_window = E_bank + P_array_avg × W          (bank + harvest during the window)
bytes    = E_window / (2.236e-3 J/byte)
```

| Contact window `W` | `E_window = 33.264 + 0.388·W` | Bytes sendable | × headroom for a store |
|---:|---:|---:|---:|
| 60 s | 56.6 J | **25.3 KB** | 32 KB |
| 300 s (5 min) | 149.7 J | **67 KB** | 128 KB |
| **600 s (10 min)** | **266.1 J** | **119 KB** | **128–256 KB** |
| 3600 s (1 h) | 1 430 J | 639 KB | 1 MB |

**And the ceiling imposed by the day, not by flash** (COMPUTED): the array's average is
**0.388 W**, so at 6.15 W TX DC the sustainable duty cycle is `0.388 / 6.15 = 6.3 %`. Over a
10 h daylight window (ADR-036's daylight-only policy) that is `0.063 × 36 000 s = 2 270 s`
of TX = `22 000 × 2 270 / 8 = 6.2 MB/day`. **6.2 MB/day is the most this vehicle can ever
transmit, and it assumes the entire array harvest goes to the downlink.**
`TODO(unverified)`: under the licence-exempt 10 mW ERP throttle the PA's DC draw is far
below 6.15 W, so this bound rises — but the *rate* at 10 mW ERP (ADR-041's open question)
then becomes the binding term. The bench measurement that settles both is a rate-vs-power
sweep at 10 mW ERP.

### 4.3 The recommended buffer, and the honest upper bound

**Recommended: a 128 KB store-and-forward buffer** — one 10-minute contact window with
~2× headroom (119 KB measured). Arithmetic:

```
10-minute window  → 119 KB measured  → 128 KB allocation (2^17 B)
```

**Recommended upper bound: do not allocate more than ~1 MB to the TX store**, because
`1 MB / 2.236e-3 = 2 344 J = 70× the usable bank` — a single megabyte is more than the
vehicle can transmit in a day's worth of bank discharges, let alone one window.

**And state plainly what the buffer is *not*:** it is not the flight log. The log is a
separate, write-mostly, **never-transmitted** partition whose size is set by flash
(4–6 MB is free) and whose recovery path is *physical* (cut-down + bench read), not radio.
Conflating the two is the mistake the flash-capacity framing invites.

**Storage is nearly free; transmission is not. Size the buffer to the link, size the log to
the flash, and never design a store you cannot drain.**

---

## 5. Is a Blossom server or relay caching sensible on a balloon?

### 5.1 Straight answer: **no — not as a server. Yes — as a client.**

**A Blossom server is a content-addressed HTTP blob store (BUD-01/02/11). It is a
SERVE-mostly pattern**, and that is the wrong direction of the link for this vehicle.

**What serving costs, in the vehicle's own units (COMPUTED):**

```
serve 1 MB = 1 048 576 bytes × 2.236e-3 J/byte = 2 344 J
  vs usable bank 33.264 J          → 70×  the ENTIRE usable bank
  vs array average 0.388 W         → 2 344 / 0.388 = 6 041 s = 1.68 h of the WHOLE array
serve 15 KB (one bank discharge)   → 33.5 J ≈ the entire bank, for one small blob
```

**At night the answer is absolute:** the night anchor is **100 µW** (ADR-036, restated in
ADR-051 §1.6 and ADR-050 §3.6). Serving *anything* at night is off the table by policy — the
vehicle is in deep sleep. During daylight the link "opens for minutes at a time", and a
serve-mostly node must be *listening and answering on demand* — i.e. **awake and radiating
for a client's benefit, on a schedule the vehicle does not control, drawing on a bank sized
to one burst.** The ground station (mains power, a 12–15 dBi Yagi, a 100 mW-EIRP licence-exempt
budget) is the correct end of the link to *serve* from.

**Repo precedent already points this way:**

- **ADR-027** (`docs/adr/027-blossom-on-ip-layer.md`, **Accepted**) keeps Blossom **on the
  IP layer** as an HTTP server and rejects a bespoke mesh-datagram transport, and its
  dependency chain (`FIPS mesh → IP → esp_http_server → Blossom BUD-01/02/11`) shows the
  balloon as one *potential* host, **blocked on FIPS providing IP**. Nothing in that chain
  addresses the **energy** of serving, which is the binding objection here.
- **ADR-013** (cluster-aware stratorelay) puts the balloon in a **relay/aggregator** role —
  but for other people's mesh traffic, filtered to cluster heads, and its own risk table
  names the failure mode precisely: *"Channel saturation: LoRa SF8/BW62.5 at 869.618 MHz has
  limited airtime. A dumb repeater seeing hundreds of nodes would exceed the 10 % EU duty
  cycle."* That is the serve-mostly risk stated by the repo itself.
- `docs/blossom-design.md` §6 sizes an **S3 Blossom partition at ~4 MB** — the same figure
  §1.2 shows is free. But *capacity* was never the constraint; §4 is.

### 5.2 The defensible pattern: write-mostly store-and-forward with opportunistic upload

**This vehicle can support a delay-tolerant store-and-forward node** — a node that:

1. **writes** telemetry and radio events into flash continuously (the flight log, §7.1),
2. **buffers** the subset destined for the ground in a small (128 KB) store-and-forward
   queue,
3. **transmits when the link and the energy policy allow** (ADR-036's energy-gated,
   daylight-only TX; ADR-035's TDM slot), draining the queue, and
4. **never serves on demand.**

That is the opposite traffic profile: **write-mostly, vehicle-initiated, time-shifted,
bounded by what the vehicle can afford to send.** In DTN terms it is a store-and-forward
node, and it is exactly what ADR-036 already describes ("telemetry gaps overnight and in
shadow … the ground segment must expect long periods with no downlink").

**Where Blossom fits:** as the **upload target and protocol on the ground side** — the
balloon acts as a **Blossom client**, pushing experiment/telemetry blobs to a ground Blossom
server during an opportunistic window. That keeps ADR-027's layer separation (Blossom is
L7 over HTTP/IP) while putting the *serving* cost where the energy is. **Blossom on the
balloon as a server: rejected. Blossom as a client to a ground server: kept open.**

---

## 6. The tie-in that already exists: the calibration blob

A sibling task has recorded the requirement, and this analysis must serve it.

> **`docs/adr/058-onboard-temp-compensation.md`, D4 — "NON-VOLATILE STORAGE IS REQUIRED for
> the per-unit calibration curve"** (branch `adr/058-onboard-temp-compensation`, commit
> `39b3333`; the record states it "deliberately does NOT pick a storage part. A sibling task
> is deciding the board storage; this ADR references that decision and states only the
> requirement: *persistent, per-unit, written at bench-characterisation time, read at boot,
> and validated on load (the curve must be range- and order-checked …)*").

**What the requirement actually needs:**

| Requirement | Value | Provenance |
|---|---|---|
| Type | `temp_comp_curve_t` — `pts[16]` of `{float temp_c; float ppm;}` + `uint8_t n` | **CITED** `firmware/rp2040/src/temp_comp.h` (`TEMP_COMP_CURVE_MAX_POINTS 16u`, struct definition) |
| **Blob size** | **129 bytes** (16 × 8 B + 1 B) | **COMPUTED** from the struct |
| Write frequency | **once per unit**, at bench characterisation | **CITED** ADR-058 D4 |
| Read frequency | **at boot** (~once per cold start, i.e. a few per flight) | **CITED** ADR-058 D4 |
| Validation on load | range + order (ascending `temp_c`) check by the loader | **CITED** `firmware/rp2040/src/temp_comp.cpp` `temp_comp_curve_load()` (rejects `TEMP_COMP_ERR_CURVE_NOT_SORTED`) |
| Failure mode if lost | identity (0.0 ppm) — the curve is empty/identity until the bench fills it | **CITED** `temp_comp_curve_is_identity()` + ADR-058 D2(b) |

**Which store serves it best?**

| Store | Fits 129 B? | Endurance need | Verdict |
|---|---|---|---|
| **Internal NVS on the module's 8 MB flash** | trivially (16 KB NVS partition holds it ~127×) | 1 write/unit + a few reads/flight — nothing | **RECOMMENDED** |
| `24LC256` EEPROM (32 KB) | yes | 1 M cycles — vast overkill | Rejected: adds a part, a bus, grams |
| `FM25W256` FRAM (32 KB) | yes | 10¹⁴ cycles — unused | Rejected: same, plus unused endurance |
| LittleFS on a data partition | yes | wear-levelled | Viable alternative if the same store also persists cut-fired flags |

**Answer:** the calibration blob needs **a small, rarely-written, validated, persistent
record** — and the module's **internal NVS** serves it exactly, at **0 g and 0 €**, with the
project's existing `nvs_flash` component. **EEPROM/FRAM are not needed for it**; FRAM's
endurance advantage is unexercised because the write count is one per unit. The
cut-fired-flag requirement (ADR-051 §2.5.1) has the same profile and is served the same way.

---

## 7. Use cases, ranked by value for THIS mission

| Rank | Use case | Store | Size | Written | Transmitted? | Why this rank |
|---:|---|---|---|---|---|---|
| **1** | **Flight log that survives link outages** (`log-don't-tune`, ADR-042 A6; ADR-036 consequence 2) | **Internal flash**, wear-levelled partition (LittleFS/NVS) | **≥ 1 MB; up to ~4 MB free** | continuously | **never** — recovered physically | ADR-036 makes the log **the primary evidence source** because there is no night/shadow downlink. It must survive the mandatory night deep-sleep and cold start, so it must be **flash, not PSRAM** (§1.1). Highest value, and it is the thing "storage on the board" is really for. |
| **2** | **Per-unit radio calibration curve** (ADR-058 D4) | **Internal NVS** | **129 B** | **once/unit** | no | It is an explicit **requirement** from a sibling record, and it is the cheapest thing on this list: NVS covers it with no new part. Ranks second only because it is tiny. |
| **3** | **Store-and-forward RX buffer** (delay-tolerant relay) | Internal flash, ring | **128 KB** (§4.3) | per event | **yes** | Real value, but bounded hard by §4: 15 KB per bank discharge, ~6 MB/day ceiling. Anything larger is un-transmittable. |
| **4** | **Configuration** (identity, schedule, policy) | Internal NVS | bytes | rarely | no | Served by the same NVS partition; already in the repo's toolchain. |
| **5** | **Post-flight reconstruction** | *not a separate store* | — | — | no | It is a **consumer** of rank 1, not a second storage system. Recovering the log requires the cut-down path and a USB-Serial-JTAG read; that is a **recovery-plan** item, not a storage part. |

**Two things not on the list, deliberately:** no external storage part (rank 1–2 need none),
and no on-board Blossom server (rejected in §5).

---

## 8. Every open item, gathered

1. **S3 module mass — `TODO(unverified)`.** No `ESP32-S3-WROOM-1U-N8R8` mass exists anywhere
   in this repo (`docs/POWER-BUDGET-V9-D2BE.md` §4 line 178; `docs/analysis/two-variant-mass-budget.md`
   §0 caveat 2). Settled by weighing one module on the repo's 0.01 g scale
   (`docs/inventory.md` line 68, "MS300 Waage"). **This is the single most valuable
   15-minute measurement for any mass decision here.**
2. **Achievable rate at 10 mW ERP — `TODO(unverified)`.** §4 uses ADR-009's 22 kbps (which
   was derived at +22 dBm with an FEM). ADR-041 settles the *margin* under licence-exempt
   but not the *rate*. A rate-vs-power sweep at 10 mW ERP is the measurement that pins the
   buffer arithmetic.
3. **The PA's actual DC draw at ≤ 10 mW ERP — `TODO(unverified)`.** §4's 6.15 W is the
   full-power figure from the MPPT analysis. At 10 mW ERP the DC draw is far lower, which
   would *raise* the 6.2 MB/day ceiling — but only if the rate holds (§8.2).
4. **Cold behaviour of the on-module flash and the MCU at −50/−60 °C — `TODO(unverified)`.**
   The datasheet stops at −40 °C. This is ADR-043's cold-qualification scope, not a new
   question, but the storage uses depend on it (log integrity across a cold night).
5. **Whether the flight log must survive a full cold start at dawn.** ADR-036 accepts "cold
   start at dawn"; if the supercap deep-discharges to zero, flash retention is unaffected
   (it is non-volatile and rated to −55…+125 °C *storage* on the NOR class), but the **log's
   filesystem integrity across brown-out** depends on the filesystem's power-fail design
   (LittleFS is designed for this; raw NOR requires the firmware to be). `TODO(unverified)`
   until the chosen filesystem's power-fail path is verified on the bench.
6. **Prices for every external candidate — `TODO(unverified)`.** No price source was read
   for this analysis. Not load-bearing: the recommendation is to add nothing.
7. **Wear-levelling budget for the chosen log allocator — `TODO(unverified)`.** §3.2's
   arithmetic is illustrative; the real figure needs the log rate and the ring design.

---

## 9. What would falsify this analysis

- **A measured achievable rate far below 22 kbps** (e.g. 1.7 kbps at 868 MHz, the figure
  ADR-009 rejects) would cut the buffer arithmetic by ~13× — to ~9 KB per 10-minute window.
  **It would not change the conclusion** (the internal flash still suffices), but it would
  change the recommended buffer size.
- **A measured deep-sleep current in the mA range** would mean the night LOG cannot survive
  on firmware alone (ADR-036 open item) — a bigger night store would then need to be
  *energy*-sized, not flash-sized, and would reopen the bank sizing, not the flash choice.
- **A demonstrated need to serve blobs to third parties** (e.g. the operator decides the
  balloon must be a Blossom *server* for the mesh) would reopen §5 — but the arithmetic
  (70× the bank per megabyte) would have to be answered first, and the answer would be a
  ground-side server.
- **A datasheet showing a cold-rated (−55 °C or better) SOIC-8 NOR/FRAM part** would make
  an external part *cold-viable*, though still unnecessary given 4–6 MB of free internal
  flash. No such part was found for this analysis.
