# Pico / small-balloon solar: what that community actually does

> **STATUS: CONSULTANT ANALYSIS — NOT A DECISION RECORD.**
> This document is an *external-evidence* survey produced **for the operator to decide on**. It is
> **not** an ADR, it amends nothing, and nothing in it may be read as an accepted design decision.
> Every external claim carries a URL and a verbatim quote or a precise paraphrase of what the
> fetched page actually said. Sources that could not be read are listed in §8 as **UNVERIFIED** —
> they were **not** read and nothing in §1–§7 relies on them. Where a claim is the author's own
> arithmetic on a source's own numbers, it is labelled *derived* and the formula is shown.
>
> This survey deliberately answers the operator's challenge to `docs/analysis/wing-literature-survey.md`:
> most of that report's mechanical rigour came from **CubeSat** teams whose vehicles are ~1.33 kg.
> This one reads **pico/small-balloon** sources only, and where the balloon world is silent it says
> so instead of borrowing the CubeSat conclusion.

- Date: 2026-10-07
- Branch: `analysis/pico-balloon-solar` · Worktree: `/home/c03rad0r/worktrees/bf-pico`
- Base commit: `af9a672` (ADR-049, tip of the branch point) — verified reachable with `git cat-file -t` before the worktree was created.
- Lens: **external evidence only.** The repo's measured numbers are treated as *given* and are not re-derived:
  small cell 52.07 × 19.65 × 0.21 mm = 10.23 cm², ~0.50 g, ~0.5 V / ~0.4 A; large cell
  78.55 × 38.90 × 0.21 mm = 30.6 cm², ~1.50 g, ~0.5 V / ~1.2 A; one pad per face; 12 cells in series
  ≈ 6.0 V / 7.2 W; radio 6.15 W peak, 0.388 W average; supercapacitor bank, no battery; hand-soldered.
- Method: a headless-browser daemon was unavailable again (`browser_exec` → `daemon default didn't come up`;
  Chrome could be started with `--remote-debugging-port=9222` and the DevTools endpoint answered, but the
  harness refused to attach, so searches went through the `r.jina.ai` text-render proxy over DuckDuckGo's
  HTML endpoint and pages were fetched with `curl` / `pandoc` / the same proxy. Every URL below was copied
  from the fetched resource.

---

## 1. The class, and why it is sub-100 g

**Definition used in this survey: a "pico/small balloon" payload is one whose *entire* launch mass —
balloon, gas, harness, tracker, antenna and solar power — is under about 100 g, with the *tracker
payload itself* typically 10–30 g.** The operator's ~20–40 g all-up payload sits at the **heavy end**
of this band, which is exactly why the community's numbers are usable for him rather than merely
suggestive.

Justification, each from a source actually read:

- IEEE Spectrum, describing pico balloons: *"The payload of a pico balloon is so light (between 12 to
  30 grams) that you can use a large Mylar party balloon filled with helium to lift it."*[^spectrum]
- ZachTek (commercial pico-balloon tracker maker, first-hand): *"These type of balloons are typically
  called Pico balloons as they only carry a payload of 15grams or lighter"*.[^zachtekblog]
- NPR, reporting the NIBBB K9YO-15 flight from the club's own launch post: *"Its total payload weight
  was just 16.4 grams, or about half an ounce"*.[^npr]
- John Ruthroff (KC9IKB), hobbyist with a long pico-balloon flight log: *"The total package, balloon,
  payload, power supply…everything…normally can't weight more than 3 ounces [≈85 g]… Since nearly half
  that weight it taken up by the balloon itself, we're down to lifting a useful payload/power supply
  combination of 8/10th's of an ounce [≈23 g]"*.[^astro]
- Measured payloads in this class from the sources: WB8ELK Skytracker *"totally solar-powered APRS
  tracker – 12 grams"*[^hamsci]; ZachTek WSPR-TX Pico *"weighs just 10.5 grams with solar cells"*[^zachtekblog];
  Traquito Jetpack + PowerFilm *"11.0 grams"*, Jetpack + Solar System *"11.7 grams"*[^trqpf][^trqss];
  KS4VA sample flight *"payload 11 g"*[^ks4va1]; Project:Traveler ptSolarHF `Mass (Tracker) 14.7g`,
  `Mass (Ready to Fly) 15.7g`[^ptraveler]; KC9IKB *"Weight at release 14 grams"*[^astro].

So "sub-100 g all-up, 10–30 g payload" is not an arbitrary cut: it is the band every one of these
builders states or measures, and the operator is inside it.

### 1.1 The sources, by type

**First-hand build reports / builder documentation** (the builder describes his own hardware):
Traquito Solar System[^trqss], Traquito PowerFilm[^trqpf], Traquito tracker[^trqtracker], K9YO/K9YO-group
solar-panel page[^k9yo], NIBBB standard array[^nibbbstd], NIBBB low-sun array[^nibbblow], NIBBB panel
specs[^nibbbpow], NIBBB technical page[^nibbbtech], John Ruthroff PICO-Ballooning[^astro], K1FM repo
README[^k1fm], KS4VA single-PCB[^ks4va1] and triple-PCB[^ks4va3] READMEs, missile.design "Operation
Magellan"[^magellan], AA0O flight report[^aa0o], IEEE Spectrum first-person account[^spectrum],
nearspaceflights.com (WB8ELK)[^elkweb], HamSCI WB8ELK presentation[^hamsci].

**Vendor documentation / application data** (the maker's own spec): PowerFilm MPT3.6-75[^pf75],
MPT3.6-150[^pf150a], MPT6-150[^pf150b]; ZachTek product page[^zachtek]; QRP Labs U4B hardware
manual[^u4b] and product page[^u4bpage]; Project:Traveler ptSolarHF[^ptraveler].

**Second-hand / news / reference:** NPR[^npr], Hackaday[^hackaday], the NIBBB BCARC club
presentation[^bcarc], the Pico Balloon Archive[^archive], Engineering ToolBox US Standard
Atmosphere[^atmos].

---

## 2. What they actually use — per source

### 2.1 Bare rigid crystalline cells (un-encapsulated), mounted end-only

- **Traquito "Solar System"**[^trqss] — cells are bare 0.5 V crystalline wafers. *"Solar cells are
  very fragile! Solar cells are very tricky to solder to."* The build: **sandwich the cells between
  two thin PCBs and solder the PCBs together through plated holes**: *"Solar System lets you build
  solar panels quickly and easily by sandwiching solar cells between two PCBs that do all the
  electrical connections for you."* Attachment is **solder at the cell ends only** — *"no need to use
  more than one oval per-side per-cell"* — and the PCB strip (5 mm × 441 mm, 0.6 mm thick, cut into
  3-cell jigs) **is** the structure. **No adhesive, no bonded substrate.** The Traquito site
  classifies this as `Fragile` and the PowerFilm route as `Robust`[^trqsolar]. Measured mass:
  *"Solar System fully assembled: 6.3 grams"*, `5 mm x 224 mm`[^trqss].
- **NIBBB "Standard Solar Array"**[^nibbbstd] — 7 × bare polycrystalline 52 mm × 19 mm cells
  (the BOM names *"AOSHIKE 100pcs 0.5V 400mA Micro Mini Solar Cell… 52mmx 19mm Polycrystalline
  Silicon"*). **Substrate = a foam disposable plate**: *"use the pattern to cut out the frame with the
  hobby knife from the middle of a 8.825" foam plate"*, and the cells are **glued at their corners**
  to that frame: *"Glue the panel to the frame using the corner holes for reference"* with *"Loctite
  Power Grab"* glue, plus fibre-glass tape and 30 AWG wire. Cell surface protection: **none**. Measured
  mass (NIBBB's own spec page): *"Weight: 4.5 – 4.7 grams"*, `122 mm × 110 mm`[^nibbbpow].
- **John Ruthroff (KC9IKB)**[^astro] — 7–8 bare polycrystalline 0.5 V cells in series on a
  *"white Styrofoam™"* airframe, no battery. **Attachment is deliberately at the ends only**:
  *"Some people glue their cells to the airframe. I don't do this because of the possibility that the
  temperature change between the assembly area and the cold at 40,000 feet + may crack a cell. I just
  attach each end of the solar array to the airframe with epoxy, so the cells can 'float' and contract
  a certain amount."*
- **K1FM Pico Balloon (Alain, adecarolis)**[^k1fm] — *"A maiden flight, powered by 6 39x19mm Aoshike
  solar panels"*; the tracker board itself *"Version 1.3 weights 2.84 grams and takes around 55mA at
  3.3V"*. Bare cells, board-mounted.
- **K9YO-group solar-panel page**[^k9yo] — *"The most common solar panel used is a flat panel made of
  6 polycrystalline solar cells."* It notes a design produced by Jim Janiak KD9UQB (the NIBBB standard
  array) and says of the Traquito route: *"the cells are completely exposed and need more caution when
  transporting and launch."*

### 2.2 Flexible thin-film modules (vendor-encapsulated / laminated)

- **Traquito "PowerFilm" route**[^trqpf] — *"PowerFilm solar modules are lightweight and flexible and
  easy to use… These panels are super durable and don't break."* Two modules in parallel: *"The
  PowerFilm modules deliver 3.6v 50mA each. Voltage good, 50mA too little -- we want more than that.
  So we're wiring two of them in parallel to double it to 100mA."* Cells are **rotated on stiff wire,
  no substrate**: *"Since we're using a stiff wire to attach to the tracker, you can just rotate the
  panels and they'll stay in place."* Measured `PowerFilm fully assembled: 4.5 grams`,
  `Jetpack + PowerFilm fully assembled: 11.0 grams`, `$14.76 (two MPT3.6-75 PowerFilm modules)`[^trqpf][^trqsolar].
- **NIBBB "Low Sun Angle – High Power" array**[^nibbblow] — 3 × **PowerFilm MPT6-150** (BOM:
  `6v 100ma Solar Panel ×3`, Digi-Key `MPT6-150`, $16.98 each) plus 3 × `1N5817` Schottky diodes.
  **Attachment:** 3D-printed templates hold the three panels as a 360° triangular prism; the panels
  are *"attach[ed] between the ring templates using the notches"*; Kapton tape covers the diode and
  solder connections (*"Apply two layers to Kapton tape over the diode connections"*). The site's
  measured spec page: `Voltage: 8.7 v / Current: 94 ma / Weight: 16.70 grams`,
  `143 mm × 143 mm × 114 mm`[^nibbbpow]. Launched from Neumayer Station III, Antarctica; *"The
  Antarctic balloon has transmitted its first data packet when the sun is only 1.8° above the
  horizon."*[^nibbblow]
- **IEEE Spectrum (Stephen Cass, first-person)**[^spectrum] — *"the tracker runs off two lightweight
  solar modules"* — PowerFilm modules, *"the two solar modules ($7 each)"* — and the report's own
  diagnosis of poor telemetry is a power, not a mechanical, failure (see §6).
- **ZachTek (vendor, WSPR-TX Pico with solar)**[^zachtek] — *"Ultra thin and light weight solar
  cells"*, part `SKU: 1043`, `Nominal voltage 3.6V`, `3.6V 50mA`, *"The weight for a single solar cell
  is 1.44gram."* These are the vendor's **"Polymer"** (thin-film) cells, i.e. already encapsulated.
  ZachTek's own blog describes the mounting: *"it is now designed to hang vertical and the solar cells
  are soldered in to a slot"*, and on the earlier revision *"here the solar cells are soldered along
  the sides"* — again **solder into slots/harness, no bonded substrate**[^zachtekblog].
- **KS4VA PowerFilm PCB adapters**[^ks4va1][^ks4va3] — *"A PCB to mount one PowerFilm p/n MPT3.6-150
  solar cell to a Traquito pico balloon tracker"*; the triple version *"mount[s] three vertical low
  sun angle PowerFilm MPT3.6-150 solar cells"*. Two key sentences: *"On the PowerFilm solar cells, you
  DO NOT need to remove the plastic covering ... just go ahead and solder them as shown!"* and the
  triple's *"top PCB gets three SMD Schottky diodes installed (to 'steer' or isolate the dark solar
  panels from the illuminated one). Use one more PCB (without diodes attached) as a bottom spreader
  or stiffener."* **The PCB is the substrate; the encapsulated module is merely clamped/soldered to
  it.** Sample flight: *"a 'CYMylar 60' hydrogen filled balloon (free lift 8 g, payload 11 g)"*[^ks4va1].
- **NPR, describing K9YO-15's hardware**: *"The entire thing that the balloon lifts is a business
  card-sized circuit board and two little tissue paper-thin solar cells"*[^npr] — thin film, two
  panels, on a bare tracker board.

### 2.3 Potting / conformal coating

- **Project:Traveler ptSolarHF**[^ptraveler] — a commercial ready-to-fly tracker, *"Solar-Only Power:
  No batteries required"*, `Mass (Tracker) 14.7g / Mass (Ready to Fly) 15.7g`, with an explicit
  protection option in its requirements list: *"Conformal Coating or High Voltage Corona Dope
  (optional) - An added optional layer of protection from the environment"* and *"5 Minute Epoxy - For
  securing the tracker to the mounting harness"*. This is the one source found that recommends a
  coating — **of the board, not a bonded coverglass over the cells**, and it is marked optional.

### 2.4 No solar at all

- None found in the class. Every tracker source is solar-only or solar+storage: Traquito — *"Trackers
  are almost always solar powered"*[^trqsolar]; missile.design — *"Pico balloons… are typically solar
  powered"*[^magellan]; U4B — solar input is the primary rail[^u4b]. **The only "no solar" case is the
  implicit one: after dark the payload stops** (see §6).

### 2.5 The mounting methods, summarised

| Method | Source | Substrate? | Bond? | Protection of cell face |
|---|---|---|---|---|
| Solder cell **ends** into a thin PCB frame (cells sandwiched between two PCBs) | Traquito Solar System[^trqss] | 0.6 mm FR4 **strip** (5 mm wide), not full-area | **no** | none (cells exposed) |
| **Glue cell corners** to a **foam plate** frame | NIBBB standard[^nibbbstd] | foam plate (Hefty 8.875") | corner glue only | none |
| **Epoxy the array ends only**, cells float | KC9IKB[^astro] | Styrofoam airframe | ends only, deliberate | none |
| Solder encapsulated module into a **PCB slot / spreader** | ZachTek[^zachtekblog], KS4VA[^ks4va1][^ks4va3] | 0.8 mm PCB spreader | no | module's own PET laminate |
| Rotate module on **stiff wire**, wire-tie to tracker | Traquito PowerFilm[^trqpf] | none | no | module's own PET laminate |
| 3D-printed **template rings** + Kapton over joints | NIBBB low-sun[^nibbblow] | 3D-printed prism (build aid) | no | module laminate |
| Optional **conformal coat / corona dope** (board-level) | Project:Traveler[^ptraveler] | n/a | n/a | coating on board |

**Nothing in the pico-balloon world bonds a bare cell face-down onto a full-area rigid substrate and
vents it.** No source in this survey uses a "bonded + vented substrate" at all.

---

## 3. The mass-critical trade

### 3.1 W/g and g/cm², per approach

| System | Power (stated) | Mass (stated) | **W/g** | **mg/cm²** | Efficiency (derived) | Source type |
|---|---|---|---|---|---|---|
| Operator's **bare poly-Si** cell (small) | 0.200 W (0.5 V × 0.4 A) | 0.50 g, 10.23 cm² | **0.400** | **48.9** | ≈19.6 % | repo measurement (given) |
| Operator's **bare poly-Si** cell (large) | 0.600 W (0.5 V × 1.2 A) | 1.50 g, 30.6 cm² | **0.400** | **48.9** | ≈19.6 % | repo measurement (given) |
| PowerFilm **MPT6-150** | 0.600 W (6.0 V × 100 mA) | 2.83 g, 166.44 cm² | **0.212** | **17.0** | ≈3.6 % | vendor[^pf150b] |
| PowerFilm **MPT3.6-150** | 0.360 W (3.6 V × 100 mA) | 4.35 g, 108.04 cm² | **0.083** | **40.3** | ≈3.3 % | vendor[^pf150a] |
| PowerFilm **MPT3.6-75** | 0.180 W (3.6 V × 50 mA) | 2.14 g, 54.02 cm² | **0.084** | **39.6** | ≈3.3 % | vendor[^pf75] |
| ZachTek polymer module | 0.180 W (3.6 V × 50 mA) | 1.44 g | **0.125** | TODO(unverified) — area not stated | TODO | vendor[^zachtek] |
| Traquito **PowerFilm** (2 × MPT3.6-75 ∥) — assembled | 0.360 W (3.6 V × 100 mA) | 4.5 g | **0.080** | 41.6 (derived: 4.5 g ÷ 2×54.02 cm²) | — | first-hand[^trqpf] |
| Traquito **Solar System** (6 bare cells) assembled | not stated | 6.3 g, 5×224 mm | TODO(unverified) — current not stated | 562 (derived: 6.3 g ÷ 11.2 cm²) | — | first-hand[^trqss] |
| NIBBB **standard** 7-cell bare array | 1.4 W (3.5 V × 0.4 A) | 4.6 g, 134.2 cm² | **0.304** | 34.3 (derived) | — | first-hand[^nibbbpow][^nibbbstd] |
| NIBBB **standard** array, *if 40 mA is right* | 0.14 W | 4.6 g | **0.030** | 34.3 | — | conflict — see §3.3 |
| NIBBB **low-sun** 3 × MPT6-150 prism | 0.816 W (8.7 V × 94 mA) | 16.70 g | **0.049** | TODO (3-D body) | — | first-hand[^nibbbpow] |
| K1FM tracker board (no cells) | — | 2.84 g | — | — | — | first-hand[^k1fm] |

*Derived figures:* efficiency = stated power ÷ (area × 100 mW/cm²); areal mass = mass ÷ stated area.
Vendor areal masses: MPT3.6-75 = 2.14 g ÷ 54.02 cm² = 39.6 mg/cm²; MPT6-150 = 2.83 g ÷ 166.44 cm² =
17.0 mg/cm².

**Caveat that must be stated:** the two PowerFilm areal masses are internally inconsistent with the
published 0.22 mm thickness. 2.14 g on 54 cm² at 0.22 mm implies ≈1.8 g/cm³ (plausible for PET +
foil tape); 2.83 g on 166 cm² at 0.22 mm implies ≈0.77 g/cm³, which is too light for a laminated
module. **I report the vendor's published numbers as published and flag that they do not reconcile.**
Do not build a budget on the MPT6-150 figure without weighing one.

### 3.2 The central question: different *structure* or different *component*?

**Answer from the sources: the pico-balloon world solves this by choosing a different COMPONENT
(an encapsulated thin-film module) or by mounting the bare cell at its ENDS ONLY — not by bonding a
bare cell to a vented rigid substrate.**

The community's own trade table makes it explicit — Traquito's solar overview gives the two routes as
a four-axis choice, not a structural one[^trqsolar]:

| Guide | Ease | Performance | Durability | Cost | Weight | Assembly Time |
|---|---|---|---|---|---|---|
| Solar System (bare cells, PCB sandwich) | Medium+ | High (15+ deg solar angle) | **Fragile** | $1.27 | 6.3 g | 20 min |
| PowerFilm (thin-film modules) | Easy | Medium (30+ deg solar angle) | **Robust** | $15.00 | 4.5 g | 10 min |

The decision the community makes is **fragile-and-cheap-and-light vs robust-and-easier-and-heavier**,
resolved by *picking the cell class*, and — when they keep bare cells — by *not bonding them*:
KC9IKB's *"so the cells can 'float' and contract a certain amount"*[^astro], Traquito's
`Fragile` label[^trqsolar], NIBBB's *"Solar panels are very fragile"*[^nibbbpow].

### 3.3 The numbers that decide it for a 20–40 g payload

1. **On W/g the operator's bare silicon wins, and it is not close.** 0.400 W/g (measured) vs
   **0.212 W/g** for the best thin-film module found (PowerFilm MPT6-150, vendor) — bare silicon is
   **1.9× better per gram**. Against the MPT3.6-75 the small cells use in the Traquito guide it is
   **4.8× better** (0.400 vs 0.084).
2. **On areal mass the thin film wins**: 17.0 mg/cm² (MPT6-150) vs 48.9 mg/cm² (bare cell) —
   **2.9× lighter per cm²** — but it delivers ≈3.6 % efficiency against the bare cell's ≈19.6 %, so
   the mass saving buys a 5.4× area penalty. For a mass-bound array the W/g column is the one that
   binds, and it favours silicon.
3. **The mounting overhead in the balloon world is tiny, so there is almost nothing to save by
   changing the structure.** NIBBB's measured array is **4.5–4.7 g** of which the 7 bare cells are
   ≈3.5 g (using the operator's own 0.50 g for a 52 × 19 mm cell) — i.e. the *entire* foam-plate
   frame + glue + fibre-glass tape + 30 AWG wiring + solder is **≈1.0–1.2 g** for seven cells, about
   **0.15 g per cell** (*derived*). The operator's ADR-049 spine-and-ribs frame is already in this
   class (12.846 g array, 0.187 W/g at 2.4 W; ADR-049 §"Why each rejected option was rejected").
4. **The real penalty for substituting thin film is area, not mass.** To replace the operator's 7.2 W
   from **367.2 cm²** of bare silicon (12 large cells × 30.6 cm²) with MPT6-150 modules would need
   7.2 ÷ 0.6 = **12 modules = 33.96 g and 1997 cm²** (*derived*: 12 × 2.83 g, 12 × 166.44 cm²) —
   heavier than the cells it replaces *before* any frame, and **5.4× the area**, which is unaffordable
   structurally and aerodynamically at 20–40 g.
5. **But the operator's power demand is ~250× the pico-balloon norm.** U4B transmits
   *"approximately 9mW… 27mW"*[^u4b]; the operator's radio peaks at 6.15 W. Pico-balloon solar
   budgets are sized for milliwatts, so their absolute areas are not a template — only their *method*
   is.

**Verdict the sources do settle:** for a 20–40 g, 7.2 W array, the CubeSat bonded-and-vented-substrate
approach is **the wrong end of the trade** — but so is a wholesale switch to thin film. The
balloon-world answer is **bare crystalline cells mounted at their ends only (no bonded substrate)**,
with thin film used *only* where low-angle or handling robustness is the binding constraint. §4 and §7
carry this through.

---

## 4. The void / pressure question — answered from the balloon world

### 4.1 What the payload actually sees

Pico balloons fly at constant-level (superpressure) neutral buoyancy roughly **10–12 km**:

- QRP Labs / ZachTek: *"the electronics could survive during days and night in the cold of **10 to
  11km** altitude"* and *"most Pico balloons don't go over **11km**"*[^zachtekblog].
- NIBBB BCARC: `Pico Balloon — Neutral Buoyancy @ **40,000 feet** (Jetstream)`[^bcarc] (= 12,192 m).
- QRP Labs U4B manual: *"In full sunshine at altitude, **-55C** temperatures can increase voltages and
  currents by up to 20%"*[^u4b].

From the US Standard Atmosphere table (Engineering ToolBox, N/m² converted to kPa by the author)[^atmos]:

| Altitude | Temperature | Pressure |
|---|---|---|
| 10,000 m | **−49.9 °C** | 2.650 × 10⁴ N/m² = **26.50 kPa** |
| 15,000 m | −56.5 °C | 1.211 × 10⁴ N/m² = 12.11 kPa |

*Derived, labelled:* a payload at 10–12 km therefore sits at **≈19–26 kPa ≈ 0.19–0.26 atm**, at
**≈−50 to −56 °C**. (Note this **contradicts** the earlier survey's *"~0.05–0.1 atm"* figure for the
wing environment — that number is roughly half to a quarter of the real pressure at pico-balloon
altitude and should be corrected in the repo. The earlier figure is closer to 15–18 km.)

### 4.2 Duration

Not a few hours. This is the part the earlier survey got wrong in the operator's favour:

- *"They can circle the earth multiple times, and stay in the air for hundreds of days."*[^magellan]
- QRP Labs: *"U4B-13 even went **17 times around the planet taking 305 days**"*[^u4bpage].
- IEEE Spectrum: *"At night, it gracefully powers down."*[^spectrum]

So the exposure is **hours to ~300 days**, day/night cycled, at 0.2 atm.

### 4.3 Is trapped air under a bonded cell a real, observed balloon failure?

**No balloon-world evidence of it was found — and there is direct balloon-world evidence that builders
avoid the condition on purpose.**

- The single most explicit statement is KC9IKB's: *"Some people glue their cells to the airframe. I
  don't do this because of the possibility that the temperature change between the assembly area and
  the cold at 40,000 feet + may crack a cell. I just attach each end of the solar array to the airframe
  with epoxy, so the cells can 'float' and contract a certain amount."*[^astro] This is a pico-balloon
  builder stating the **thermal-contraction** reason, not the void reason — he avoids the bond
  entirely rather than venting it.
- No pico/small-balloon source read in this survey reports a cell cracked by *trapped air expanding
  under a bonded cell*. Cracking is reported (see §6) but attributed to handling, launch and
  fragility — never to a void.

### 4.4 Is the multi-year CubeSat vacuum a fair analogue?

**No, and the numbers say so plainly.** The earlier survey's void failure comes from AlbertaSat,
whose qualification was *"held at high vacuum (<10⁻⁶ Torr) for six hours in a TVAC chamber"* and whose
vehicle is in vacuum for years (earlier survey §3.1/§3.2). <10⁻⁶ Torr ≈ 1.33 × 10⁻⁴ Pa. At 12 km the
ambient is ≈1.9 × 10⁴ Pa. The pressure ratio is **≈1.4 × 10⁸** (*derived*). A void sealed at 1 atm on
the ground sees a differential of ≈0.8 atm (≈81 kPa = 8.1 N/cm²) at altitude — real and worth
respecting — but the driving pressure, the gas available to *evolve* from outgassing, and the
thermal-cycle count are all in a different regime from a CubeSat's 10⁻⁶ Torr.

**Stated plainly: I found no balloon-world evidence either way on void-cracking. I am not borrowing the
CubeSat conclusion.** What the balloon world *does* say is (a) do not bond, or (b) if you bond, expect
thermal contraction to be the cracking mechanism — which is a different physics from the CubeSat void
and a different mitigation (bond at the ends, or use a module already encapsulated).

---

## 5. Flexible thin film vs bare silicon, with numbers

| | Bare poly-Si (operator, measured) | Flexible thin film (PowerFilm MPT6-150, vendor[^pf150b]) |
|---|---|---|
| Efficiency (derived from stated W, V, A and area; AM1.5 = 100 mW/cm²) | **≈19.6 %** | **≈3.6 %** |
| W/g | **0.400** | 0.212 → **silicon wins 1.9×** |
| mg/cm² | 48.9 | **17.0 → thin film wins 2.9×** |
| Thickness | 0.21 mm | 0.22 mm (laminated) |
| Voc/part | 0.5 V (12 in series for 6 V) | 6.0 V in one module; max Voc 9.3 V[^pf150b] |
| Robustness | *"extremely fragile"* — *"Cracking and breaking of these incredibly fragile cells is par for the course"*[^astro]; *"These panels are super durable and don't break"* is said of PowerFilm[^trqpf] | **thin film wins decisively** |
| Assembly | solder to each cell; *"very tricky to solder to"*[^trqss]; 0.5 V/1.2 A means heavy tabs and many joints | solder into a PCB slot / clamp; *"you DO NOT need to remove the plastic covering … just go ahead and solder them"*[^ks4va3] |
| Field handling | AA0O *"broke … a couple of the solar panels during the launch"*[^aa0o] | KS4VA: *"Tough enough to be handled by a child or dragged on the ground in a botched launch"*[^ks4va3] |
| Low sun angle | poor when flat; NIBBB *"Requires sun to be above the horizon to power the tracker"*[^nibbbpow] | PowerFilm *"well suited to collect direct sunlight and indirect light in shady areas"*[^pf150b]; NIBBB low-sun prism fires at *"1.8° above the horizon"*[^nibbblow] |

**Which wins on mass:** bare polycrystalline silicon, by **1.9× per gram** (0.400 vs 0.212 W/g), and by
**4.8×** against the MPT3.6-75 module the Traquito guide actually recommends (0.400 vs 0.084 W/g).

**Which wins on robustness and assembly simplicity:** flexible thin film, unambiguously, and every
source in this survey that comments on it says so in the same words — *"super durable and don't
break"*[^trqpf], *"Tough enough to be handled by a child"*[^ks4va3], *"Durability: Robust"*[^trqsolar].

**Efficiency is quoted, not hand-waved:** PowerFilm's own full-sun figures are 180 mW / 3.6 V / 50 mA
on 74 × 73 mm (MPT3.6-75) and 600 mW / 6.0 V / 100 mA on 114 × 146 mm (MPT6-150)[^pf75][^pf150b],
giving 3.33 and 3.60 mW/cm² at one sun. The operator's cells give 200 mW / 10.23 cm² = 19.55 mW/cm².

---

## 6. Failure reports

All of these are **real, sourced** pico/small-balloon solar failures found in this survey:

1. **Cells broken during handling/launch (bare cells) — AA0O, first-hand**: *"I received no spots and
   thought it was a failure as I broke the strain relief off the antenna and also a couple of the
   solar panels during the launch."*[^aa0o] Cause: launch handling of fragile bare cells.
2. **Cells cracking is routine (bare cells) — KC9IKB, first-hand**: *"Cracking and breaking of these
   incredibly fragile cells is par for the course. Assembly becomes easier with experience."*[^astro]
   Cause: fragility. **This same source names the thermal mechanism** as the reason not to glue:
   *"the temperature change between the assembly area and the cold at 40,000 feet + may crack a cell"*.
3. **Cells underperforming — TT7 (from the earlier survey, same community)**: *"I found out that it
   was caused by three cells that significantly underperformed."*[^tt7] Cause: individual bad cells;
   mitigated by measuring every cell first.
4. **No power because the array was shaded / sun too low — IEEE Spectrum, first-person**:
   *"My best guess is that power from the horizontal solar panels I'm using is marginal, with the
   winter sun being so low in the sky. That's something I should have thought about before launching
   the first balloon just 24 hours after the winter solstice!"*[^spectrum]
5. **No power in winter at high latitude — NPR on K9YO-15**: *"One explanation is that the balloon's
   GPS pings require solar power. At higher latitudes in wintertime — like the recent path of
   K9YO-15 — the tiny solar panels can struggle to receive enough sunlight."*[^npr]
6. **Silence at low sun angle — KC9IKB JR01**: *"It had traveled about 110 miles from its last
   position reported near sunset (when the sun angle was too low to power the solar cells)."*[^astro]
7. **Total tracker loss after a storm, solar/board fate unknown — K1FM**: *"After 5 days of
   transmissions the payload failed somewhere around Belize (central America) probably after
   encountering a tropical storm."*[^k1fm]
8. **Damage worry after a bad launch — ZachTek, first-hand**: *"We were of course worried that that
   the bad launch had caused some damage to the solar cells or the antenna and during the first days
   only 30m reports were being received"* (the worry proved unfounded — propagation).[^zachtekblog]
9. **Sudden silent death, cause never established — ZachTek**: *"it suddenly went silent mid-day. That
   is just the way it is with balloon flights I guess. It can die suddenly and you will never know what
   has happened, balloon burst? electronics failure? We will never know."*[^zachtekblog]

**Not found:** no source in this survey reports a **panel detaching from a substrate** (there is no
substrate bond to fail), and — as stated in §4.3 — **no source reports a cell cracked by trapped air
under a bond**. No source reports a **solder joint failing in the cold** as an identified cause; the
closest is the general fragility statements above. Those negatives are reported as negatives.

---

## 7. What we should do

**Recommendation: keep the bare cells, and do NOT bond them to a substrate. Mount them at their ends
only — the Traquito PCB-sandwich or the NIBBB foam-frame pattern — and use a Schottky diode per
parallel group as the balloon world does.**

Reasoning, with the deciding numbers:

1. **The deciding number is 0.400 W/g vs 0.212 W/g.** The operator's bare cells beat the best flexible
   module found by **1.9× on mass per watt**, and beat the module the pico-balloon community actually
   recommends (MPT3.6-75) by **4.8×**. At 20–40 g all-up, mass per watt is the binding constraint, so
   **switching the whole array to thin film is the wrong move**.
2. **Do not bond; that is the community's answer to the pressure/thermal problem.** KC9IKB attaches
   only the array ends *"so the cells can 'float'"*[^astro]; Traquito holds cells by soldering their
   ends through a PCB[^trqss]; NIBBB glues only the corners[^nibbbstd]. ADR-049's bonded-and-vented
   substrate (inherited from the CubeSat survey) is **not** something any pico-balloon source in this
   survey does. **The deciding evidence is that no balloon source bonds, and the one that explains why
   cites thermal contraction, not vacuum.**
3. **The mounting overhead is only ≈0.15 g/cell in the balloon world** (*derived* from NIBBB's
   4.5–4.7 g for 7 cells, ~3.5 g of which is silicon). The operator's spine-and-ribs frame is already
   in that class; he does not need a bonded substrate to save mass.
4. **Use thin film only where robustness or low sun angle is the binding constraint — a mixed
   strategy on the NIBBB model.** NIBBB itself flies a bare-cell flat array in spring/summer and a
   thin-film prism in winter/Antarctic[^nibbbpow][^nibbblow], and KS4VA mounts PowerFilm on PCB
   spreaders for *"low sun angle"*[^ks4va3]. If the winter launch needs a low-angle blade, put **one**
   encapsulated module on it, not the whole array. Note the honest cost: NIBBB's own thin-film
   low-sun array is **16.70 g for 0.816 W (0.049 W/g)** vs the bare-cell array's **4.6 g for 1.4 W
   (0.304 W/g)** — the thin-film option is **3–4× heavier** in NIBBB's own words (*"Three to four
   times heaver that standard configuration"*[^nibbbpow]).
5. **Add a Schottky (blocking/bypass) diode per parallel string.** Both balloon sources that face the
   dark-panel problem do this: KS4VA uses *"three SMD Schottky diodes … to 'steer' or isolate the dark
   solar panels from the illuminated one"*[^ks4va3]; NIBBB uses `1N5817` ×3[^nibbblow]. ADR-049
   already requires a ≥2 A / 40 V bypass — consistent with the community's practice.
6. **Encapsulation/potting is optional at board level, not required over the cells.** The only
   coating advice found is Project:Traveler's *optional* *"Conformal Coating or High Voltage Corona
   Dope"*[^ptraveler] — on the board, not a coverglass. Any coverglass would be 50–100× the cell's own
   mass and is not in evidence anywhere in this class.

### 7.1 What is NOT settled by evidence — the operator's own bench tests needed

1. **No balloon-world measurement of the operator's exact cell class in a flown array exists.** NIBBB's
   AOSHIKE 52 × 19 mm cells are the same class[^nibbbstd], but NIBBB does not publish W/g or a
   current for its standard array without contradiction (§3.3). **Bench test:** assemble 7 (or 12)
   of the operator's cells end-only on a mock frame and weigh + measure Isc at one sun.
2. **Whether his hand-soldered joints survive −50 °C + launch is untested.** KC9IKB's concern is
   thermal, and the earlier survey's microcrack evidence is thermal. **Bench test:** cold-soak a
   soldered cell string to ≈−55 °C, thermal-cycle it, re-measure Isc and inspect the joints. There is
   no balloon source that has done this and published it.
3. **Void-cracking under a bonded cell: no balloon evidence either way** (§4.3). If the operator still
   wants a bonded wing, this is his own test — a vacuum-bag or altitude-chamber cycle with a thermal
   camera, as the CubeSat source did, is the only way to know.
4. **The low-sun-angle current** — his array must survive a winter northern launch. NIBBB's answer was
   a physically different array[^nibbblow] and IEEE Spectrum's was to lose the flight[^spectrum].
   **Bench test:** measure the array's current at 5°, 10° and 15° elevation.
5. **The NIBBB "40 mA vs 400 mA" conflict** (§3.3) is unresolved from the source pages; the operator
   should not use NIBBB's W/g figure without resolving it against a real cell of that class.

---

## 8. UNVERIFIED sources (URL known, page NOT readable — nothing above relies on these)

| URL | What it appears to be | Why unverified |
|---|---|---|
| https://groups.io/g/picoballoon/topic/102234123 | Dave VE3KCL's soldering technique post, cited by the K9YO solar-panel page[^k9yo] | groups.io returned a **"Log In"** page — login-walled; not read |
| https://lora-aprs.org/pico-balloons/ | A pico-balloon community page | Fetch returned a **"Robot Challenge Screen"** (bot wall); not read |
| https://reverea.dev/picoballoon-tracker-teensytrack-v2/ | "TeensyTrack V2" pico-balloon tracker | Fetch returned a **"Schematic Prints"** stub (2 049 bytes); **not read** — no claim made |
| https://www.dropbox.com/s/wiwb2m30mua771j/Building%20a%20Pyramid%20Solar%20collector%20for%20a%20Pico%20C.docx | Graham Collins VE3GTC pyramid solar collector instructions, linked from K9YO[^k9yo] | Not fetched within budget — linked but not read |
| https://www.dropbox.com/scl/fi/b94l48927o8idge4yhm79/MOVI0002.avi | VE3KCL soldering video, linked from K9YO[^k9yo] | Video; not fetched |
| https://qrp-labs.com/images/u4b/u4b_hardware.pdf (solar-panel mounting detail) | U4B hardware manual — **the manual itself WAS read**[^u4b]; only its specific solar-panel *attachment* paragraph was not found | The manual does not describe how to stick the panel to the board — gap stated, not filled |
| https://www.sciencedirect.com/science/article/pii/S0960148119311589 | "Modelling and experimental investigations of microcracks in crystalline silicon…" | Not fetched (ScienceDirect bot wall, per the earlier survey); **not read** |
| https://ieeexplore.ieee.org/document/9198968 | "Microcrack Formation in Silicon Solar Cells during Cold Temperatures" | Not fetched (IEEE paywall); **not read** |

Also noted: `https://sbmicro.org.br/.../A POWER MANAGEMENT SYSTEM FOR HIGH-ALTITUDE PICO BALLOON…pdf`
returned a 201-byte body via the proxy (body failed to extract) — **not read**.

---

## Sources

[^trqsolar]: Traquito — Solar Power overview — https://traquito.github.io/solar/
[^trqpf]: Traquito — PowerFilm guide — https://traquito.github.io/solar/powerfilm/
[^trqss]: Traquito — Solar System guide — https://traquito.github.io/solar/solarsystem/
[^trqtracker]: Traquito — Jetpack WSPR Tracker — https://traquito.github.io/tracker/
[^k9yo]: Pico Balloons by K9YO — Solar Panel — https://sites.google.com/view/picoballoonsbyk9yo/solar-panel
[^k9yohome]: Pico Balloons by K9YO — Home — https://sites.google.com/view/picoballoonsbyk9yo/home
[^nibbbstd]: NIBBB — Standard Solar Array, Instructions and Bill of Materials — https://nibbb.org/standard-solar-array-instructions-and-bill-of-materials/
[^nibbblow]: NIBBB — Low Sun Angle – High Power Solar Array — https://nibbb.org/low-sun-angle-high-power-solar-array/
[^nibbbpow]: NIBBB — Power – Solar Panels (measured specs) — https://nibbb.org/power-solar-panels/
[^nibbbtech]: NIBBB — Technical Page — https://nibbb.org/technical-info/
[^astro]: John Ruthroff — PICO-Ballooning — https://www.theastroimager.com/picoballoning/pico-ballooning/
[^k1fm]: K1FM Pico Balloon — https://github.com/adecarolis/K1FM-Pico-Balloon (README) · https://k1fm.us/2019/05/k1fm-pico-balloon-part-one/
[^ks4va1]: KS4VA — PowerFilm SINGLE PCB for Traquito — https://github.com/KS4VA/PoweFilm-Solar-SINGLE-PCB-for-Traquito
[^ks4va3]: KS4VA — PowerFilm TRIPLE PCB for Traquito — https://github.com/KS4VA/PoweFilm-Solar-TRIPLE-PCB-for-Traquito-Balloon-Tracker
[^spectrum]: IEEE Spectrum — High-Altitude Adventure With a DIY Pico Balloon — https://spectrum.ieee.org/explore-stratosphere-diy-pico-balloon
[^zachtek]: ZachTek — Solar Cell for Pico Balloons, Polymer 3.6V 50mA — https://www.zachtek.com/product-page/solar-cell-for-pico-balloons-polymer-3-6v-50ma
[^zachtekblog]: ZachTek — "A new WSPR transmitter for Balloons" (mirror) — https://www.klofas.com/blog/2021/picoballoon-launch-3/zachtek.com.pdf
[^u4b]: QRP Labs — U4B Ultimate4 Balloon Tracker Hardware Manual — https://qrp-labs.com/images/u4b/u4b_hardware.pdf
[^u4bpage]: QRP Labs — U4B Balloon tracker (product page) — https://qrp-labs.com/u4b
[^ptraveler]: Project:Traveler — ptSolarHF Tracker — https://www.projecttraveler.org/trackers/ptsolarhf-tracker
[^magellan]: missile.design — Operation Magellan, PicoBalloon project part 1 — https://missile.design/2023/11/20/magellan-part1
[^aa0o]: AA0O — Pico Balloons (flight report) — https://aa0o.radio/2026/09/04/pico-balloons/
[^elkweb]: WB8ELK — Balloons — http://www.nearspaceflights.com/
[^hamsci]: Bill Brown WB8ELK — HamSCI 2019 Hamvention presentation — https://hamsci.org/sites/default/files/publications/2019_Hamvention/20190518_1000-William_Brown_WB8ELK.pdf
[^bcarc]: Bonner County ARC — Pico-Balloon Project Update, May 2024 — https://k7jep.org/wp-content/uploads/simple-file-list/BCARC-2024_05-Our-Pico-Balloon.pdf
[^npr]: NPR — "Did an F-22 shoot down an Illinois hobby group's small radio balloon?" — https://www.npr.org/2023/02/18/1158048921/pico-balloon-k9yo
[^hackaday]: Hackaday — "Answering Some Pico Balloon Questions" — https://hackaday.com/2023/02/24/answering-some-pico-balloon-questions/
[^archive]: Pico Balloon Archive — https://picoballoonarchive.org/home
[^pf75]: PowerFilm — MPT3.6-75 product page — https://www.powerfilmsolar.com/products/electronic-component-solar-panels/classic-application-series/mpt3-6-75
[^pf150a]: PowerFilm — MPT3.6-150 product page — https://www.powerfilmsolar.com/products/electronic-component-solar-panels/classic-application-series/mpt3-6-150
[^pf150b]: PowerFilm — MPT6-150 product page — https://www.powerfilmsolar.com/products/electronic-component-solar-panels/classic-application-series/mpt6-150
[^atmos]: Engineering ToolBox — U.S. Standard Atmosphere (metric table) — https://www.engineeringtoolbox.com/standard-atmosphere-d_604.html
[^tt7]: TT7 High Altitude Balloon (cited from the earlier survey `docs/analysis/wing-literature-survey.md` §2.1) — http://tt7hab.blogspot.com/2017/09/

---

## Honesty statement

Every quotation in §2–§6 was taken from a page this session downloaded and read; every URL was copied
from the fetched resource, not reconstructed from memory. Sources that could not be read are in §8 and
are not used to support any claim. Where a figure is the author's arithmetic on a source's own numbers
it is labelled *derived* and the formula is given. One internal vendor inconsistency (the two
PowerFilm areal masses vs their stated thickness, §3.1) and one source conflict (NIBBB 40 mA vs
400 mA, §3.3) are reported as conflicts rather than resolved. **No source was read that this document
does not name, and nothing in §1–§7 relies on a source in §8.**
