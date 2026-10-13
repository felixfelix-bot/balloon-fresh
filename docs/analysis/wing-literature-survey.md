# Wing literature and open-source survey — what other people learned building solar wings

> **STATUS: CONSULTANT ANALYSIS — NOT A DECISION RECORD.**
> This document is an *external* literature and open-source survey produced for the operator to
> decide on. It is **not** an ADR, it amends nothing, and nothing in it may be read as an accepted
> design decision. Every external claim below carries a URL and a quote or a precise paraphrase of
> what the source actually says. Sources that could not be opened are listed as **UNVERIFIED** in
> §6 — they were **not** read and must not be relied on. Where a source is anecdotal (a hobbyist
> blog, a vendor marketing page, a forum post) that is stated at the point of use.

- Date: 2026-10-07
- Branch: `analysis/wing-literature` · Worktree: `/home/c03rad0r/worktrees/bf-winglit`
- Base commit: `af9a672` (tip of `main` = "docs(adr): ADR-049 wing architecture…"); verified with `git cat-file -t` before creating the worktree.
- Lens: **external evidence only.** The repo's own measured numbers and decisions were read first and
  are treated as *given*: 52.07 × 19.65 × 0.21 mm small cells, 78.55 × 38.90 × 0.21 mm large cells,
  one solder pad per face, 12 cells in series = 6.0 V nominal, load max 6.15 W DC, spine-and-ribs
  frame at **0.187 W/g** (`docs/analysis/wing-mass-shape.md:113`), hand-assembled by the operator.
  This survey does not re-derive any of that.

---

## 1. Method, and what this survey can and cannot say

Search: a headless-browser daemon was unavailable in this session (`browser_exec` returned
`daemon default didn't come up`), and the open DuckDuckGo/Bing/Startpage HTML endpoints either
blocked automated access or returned JS-gated pages. The working search path was **Brave Search
fetched with `curl` and parsed locally**, plus **GitHub's REST API** for repository discovery
(unauthenticated: 60 core requests/hour, 10 search requests/minute). Pages were converted to text
with `pandoc` / `html2text`; PDFs with `pdftotext`.

Consequences, stated honestly:

- Every source numbered §2.1–§4.6 below was **downloaded and read**. Quotes are verbatim from the
  fetched text.
- Brave rate-limited further queries after roughly 3–5 per window (a blocked query returns a fixed
  73 799-byte page). A few promising titles could therefore not be opened; they are in §6 as
  **UNVERIFIED** rather than summarised from a search-result snippet.
- The survey is **not** exhaustive. It is a deliberately-bounded sample biased towards *primary*
  sources with measured data (flight hardware documents, a qualification test plan, actual KiCad
  files) over secondary blog commentary.

---

## 2. Amateur and professional high-altitude balloon (HAB) solar builds

### 2.1 TT7 High Altitude Balloon — hobbyist flight log, **reports a failure** — ANECDOTAL but first-hand

- **URL:** http://tt7hab.blogspot.com/2017/09/
- **What it is:** the build/flight log of a solo amateur superpressure-balloon programme (28-day
  flights) using **52 × 38 mm solar cells** — almost exactly the class of our large cell
  (78.55 × 38.90 mm, same 38 mm axis).
- **Directly relevant failure:** *"I had to repair the first solar panel that consisted of six
  52x39mm solar cells in series at 0° angle to ground, because it output only about 15% of expected
  power when tested. I found out that it was caused by three cells that significantly
  underperformed."*
- **The builder's own summary of the task:** *"Working with solar cells was one of the more
  frustrating parts of the project."*
- **His soldering method, stated as the one that finally worked:** *"First, I measure all the cells
  to be used with a multimeter to ensure they output expected amount of current when illuminated. I
  then tap a small spot (on the white stripes) I want to solder to with a flux pen. For soldering, I
  use a hoof tip with the iron set to about 250 °C. I load the flat surface of the tip with solder
  and apply it for a few seconds to the end of the wire laid on the cell."* Followed by: *"After
  that I tape over the joints on the bottom of the cell with Kapton tape and at least fix the wires
  that are soldered to the top of the cell in place. When putting the whole panel together I try
  taping everything in place so it eases off any bending or pulling on the solder joints."*
- **He also abandoned a step:** *"I stopped doing the surface scratching I had mentioned in previous
  blogs, because with this approach it turned out to be unnecessary."*
- **A second, unresolved failure:** the solar-powered tracker TT7B3 — *"The signal reception was
  significantly worse than on the previous flights, and the last packet was received over Poland
  after just a couple of hours in flight while the balloon was still ascending. There was no further
  information about its fate."* (http://tt7hab.blogspot.com/ home page, "TT7 tracker" section.)

### 2.2 Global Aerospace / NASA SBIR — *HighPower™ Solar Array System for Balloons* — AIAA ATIO 6744 — PRIMARY, measured

- **URL:** https://www.gaerospace.com/projects/Modular_Solar/pdf/Aaron_AIAA_ATIO_6744.pdf
- **What it is:** the design paper for a deployable, sun-tracking balloon solar array (2.5 kW at
  35 km, 6 × 2 m × 2 m Solar Array Modules of 600 cells each). It is the closest published analogue
  to a *balloon* array (as opposed to a satellite array) and it is explicit about failure.
- **Failure mode #1 — landing, not flight:** *"In particular, solar array panels are quite fragile
  and they will often sustain irreparable damage."* and *"In the past, solar arrays have been
  sacrificed on landing, as there was no feasible means of protecting them."*
- **Failure mode #2 — mechanical, stated as a safety requirement:** *"It is a safety-related
  requirement that no part of the HighPower™ solar array subsystem detach, posing a hazard to people
  or property on the ground, during any reasonably anticipated event."*
- **Shading drove the cell layout:** *"Each SAM is a square panel about 2m x 2m covered with two
  strings of 300 solar cells each and attached at the corners… The unusual arrangement of the solar
  cells is intended to reduce the effects of shadowing along the sides and corners of the panels to
  balance the effects on each of the parallel SAMs."*
- **Mass-per-watt benchmark (this is the number to compare against):** the estimated operational
  system: SAMs 53 kg + SASS 56 kg + bottom plate 19 kg = **128 kg** for **2486 W** BOL, i.e.
  *"even still at 128 kg, the overall specific power of the estimated operational system is nearly
  19.4 W/kg versus the goal of 20 W/kg."* (Table 1, "System Mass Estimates".)
  Isolating the panel itself: "SAM substrate with cells" = 35 kg for six 2 m × 2 m modules, i.e.
  ≈ **1.46 kg/m² of panel** and ≈ **14.1 W/kg at SAM level** (2486 W ÷ (35+16) kg, taking the SAM
  substrate plus corner hardware as the panel).
- **Cell topology:** *"Each cell produces about 0.5V, so the total nominal output voltage from the
  array is about 150V"* — 300 series cells, matched to our 12-in-series/6.0 V scale by scaling only.

### 2.3 NASA JPL, *Results of the 1968 Balloon Flight Solar Cell Standardization Program* (TR 32-7426) — PRIMARY

- **URL:** https://ntrs.nasa.gov/api/citations/19700002654/downloads/19700002654.pdf
- **What it is:** four balloon flights that flew bare and cover-glass/filter-covered silicon cells as
  calibration standards, with flight-by-flight damage reporting. 1969, so the cells are old — but it
  is a rare *documented impact-damage* record on a balloon.
- **Damage observed:** *"Due to the shock of the lower payload release, the balloon apparently
  ruptured, and the upper payload, along with the balloon material, essentially free-fell, impacting
  in a cornfield and inflicting extensive damage on the tracker. Two solar cell modules were slightly
  damaged; on one, a load resistor was broken, and on the other, the solar cell cover glass was
  chipped."*
- **Cell construction used for flight:** cells *"covered with optical bandpass filters"* deposited on
  *"water-free quartz material"* — i.e. a rigid cover medium, with the weight cost that implies
  (the report's flight payloads are quantified in kg). Use it as evidence that *covered* cells chip
  and *bare* handling is what breaks cells, not the other way round.

### 2.4 PowerFilm Solar — *Lightweight Solar for High-Altitude Balloons* case study — VENDOR MARKETING, ANECDOTAL, NO NUMBERS

- **URL:** https://www.powerfilmsolar.com/case-studies/high-altitude-balloon
- **What it is:** a thin-film PV vendor's HAB case-study page. **Read it; there are no measurements
  in it.** It states the requirements qualitatively: *"Minimal mass contribution. Mechanical
  integrity at altitude. Stable voltage and current output. Reliable performance in extreme
  environmental conditions."* and the approach as *"Lightweight substrate and encapsulation
  materials. Secure attachment compatible with balloon envelope structures."*
- **Why it is still listed:** it is the only commercial HAB solar product page found, and it confirms
  two design pressures exist in industry (substrate/encapsulation mass, and *attachment*), but it
  carries **no numbers and no failure data**. Treat it as a pointer, not evidence.

---

## 3. CubeSat / PocketQube deployable panels, their design files and their failure modes

### 3.1 Sorensen, Halliwell et al., *Open-Source CubeSat Solar Panels: Design, Assembly, Testing, and On-Orbit Demonstration* (SSC24-WP2-33, arXiv:2407.19356) — PRIMARY, measured, flown

- **URL:** https://arxiv.org/abs/2407.19356 · full text read at https://arxiv.org/html/2407.19356v1
- **What it is:** the University of Alberta (AlbertaSat) solar-panel paper for the Northern SPIRIT
  constellation (Ex-Alta 2, YukonSat, AuroraSat; deployed from the ISS 2023-04-24) and the
  Ex-Alta 3 mission. Licensing stated as **Apache 2.0**, design files published.
- **The single most transferable failure mechanism in this whole survey — trapped voids crack cells
  in vacuum:** *"to attach the cells to the substrate, Keller et al., used a conductive epoxy,
  whereas Vanhille and Karuza et al. used two layers of Kapton tape. Each method had several
  drawbacks. Keller's approach is used widely by student CubeSat projects to assemble solar panels;
  however, it can cause the formation of air pockets or voids between the solar cells and the
  substrates. When exposed to vacuum, these air pockets can crack the solar cells, reducing their
  potential to generate power."*
- **Their fix, in two parts:** (i) *"we use a single piece of double-sided Kapton tape, adhered first
  to the solar cells. This method is more repeatable than using conductive epoxy, and it reduces the
  risk of forming voids."*; (ii) *"we add via stitching to the solar panel PCB substrates. This via
  stitching, if sufficiently dense (>~5/cm²), nearly eliminates the possibility of air pockets
  forming between the tape and the substrate."* They also *"place venting holes in the PCB substrate"*.
- **Materials, named:** *"The solar cells are attached to the PCB using a double-sided polyimide
  (Kapton) tape, which uses a silicone adhesive, and the electrodes are connected using a silver
  epoxy. Specifically, we used the CAPLINQ PIT2SD, 5 mil-thick tape, and EPO-TEK H20E silver epoxy."*
  They note the tape *"had higher total mass loss and collected volatile condensable material than
  specified by the mission requirements"* but they deviated because of its small exposed area.
- **Epoxy must be minimal and is cured in vacuum:** *"A small amount of the epoxy (~0.25 mL) is
  applied… if too much epoxy is used, it will degas and expand as it cures, which can cause
  significant stress on the solar cells. Then, the epoxy is cured at 120 °C for two hours in a
  partial vacuum (−10 mmHg), pausing halfway to allow for electrical short testing… Epoxy is then
  added to the negative terminals on the top of the panel, again using only a small amount, before
  curing at 100 °C for two more hours in the same partial vacuum."*
- **Order of operations (recommended pattern we can copy):** *"All component-level testing is done
  before adhering the solar cells to the substrates, which reduces the likelihood of cell damage."*
  and *"The panels are assembled after all other electronic components have been added and fully tested."*
- **Fragility of thin silicon, demonstrated:** testing the procedure on silicon first, *"The silicon
  cells, which initially measured 80 mm × 80 mm, were mechanically scoured with a scalpel and snapped
  along the growth direction crystal axis to be the same dimensions as the Ex-Alta 2 XTJ prime solar
  cells — 69 mm × 40 mm."*
- **Bypass diodes and what failure looks like when they act:** *"we achieved partial illumination by
  covering half of the solar panel, and this was done to verify bypass diode functionality"*; a
  damaged cell showed *"their damage results in the stepping seen in Figure 4c, caused by activation
  of the bypass diodes. Stepping can also signify uneven illumination of the panels, which reduces
  the total power generation."* They also used *"reverse bias testing to identify any points of damage."*
- **Test regime, measured:** *"The satellite assemblies were held at high vacuum (<10⁻⁶ Torr) for six
  hours in a TVAC chamber, followed by full functional tests"*; earlier panels were *"inspected for
  voids using a thermal camera both before and after vibration testing"* at CSA's David Florida Lab.
- **Deployment-failure consequence, quantified:** with both deployable panels failed, average
  generation fell from *"9.6 W ± 17%"* to *"2.9 W"*, which *"was less than the standby mode power
  requirement"* — the satellite survives on the critical power requirement but loses functionality.
- **Mass, measured:** body-mounted panel **82 g typical** (72–92), deployable panel **76 g typical**
  (66–86), for 6 × XTJ-Prime cells, 6S1P at 14.4 V / 0.48 A, MPP 6.2 W typical.
- **Cell size / thickness:** cells are *"69 mm × 40 mm"* XTJ-Prime; the companion design document
  (below) gives 225 µm.
- **Deployment mechanisms:** aluminium hinges with springs, actuated by burnwires (*"5 V to the
  10 Ω… burnwire resistors. The resistors heated up to approximately 200 °C, melting the twice-wrapped
  Dyneema thread"*), with SPDT deployment-state switches and *"Several 3D-printed PEEK parts"*.

### 3.2 AlbertaSat *Hyperion* detailed design + qualification test plan — PRIMARY, measured (Apache-2.0)

- **URL (repo):** https://github.com/AlbertaSat/ex2_hyperion_solar_panel_hardware
- **URL (detailed design PDF, read):** https://raw.githubusercontent.com/AlbertaSat/ex2_hyperion_solar_panel_hardware/master/Documentation/TX2-PW-387-Ver.%200.12%20Hyperion%20Detailed%20Design.pdf
- **URL (test plan PDF, read):** https://raw.githubusercontent.com/AlbertaSat/ex2_hyperion_solar_panel_hardware/master/Documentation/TX2-PW-435%20Ver.%201.00%20Hyperion%20Testing%20Plan.pdf
- **Licence:** Apache-2.0 (`LICENSE` fetched, "Apache License / Version 2.0, January 2004").
- **Cell mechanical data (Table 4):** Spectrolab XTJ-Prime, **thickness 225 µm**, width 6.91 cm,
  length 3.97 cm, **area 26.62 cm², mass 2.24 g** → **84.1 mg/cm²**.
- **Cell temperature coefficients (Table 5) — usable directly in our cold-Voc arithmetic:**
  `ΔVMP/ΔT = −6.2 mV/°C`, `ΔVOC/ΔT = −5.6 mV/°C`, `ΔIMP/ΔT = +217.76 µA/°C`,
  `ΔISC/ΔT = +299.42 µA/°C`. The design doc also gives EOL (10-year LEO) coefficients
  (`ΔVOC/ΔT = −5.8 mV/°C`, `ΔJSC/ΔT = +10.0 µA/(cm²·°C)`).
- **Thermal environment stated:** *"Thermal analysis has determined that the solar cells would reach
  70 °C if exposed to irradiance equaling the solar constant (1.361 kW/m²) at steady state."*
  Operating temperature spec: **−40 °C min to +125 °C max**; storage −40 °C to +125 °C.
- **Panel-level mass and power (Table 8):** single body-mounted panel 82 g typ, single deployable
  panel 76 g typ; per-panel output 14.4 V × 0.48 A ≈ **6.9 W**, so the deployable panel is
  ≈ **91 W/kg at panel level** (6.9 W ÷ 0.076 kg) — with the panel carrying 6 × 26.62 cm² = 159.7 cm²
  of cell, i.e. **≈ 476 mg/cm² of panel** against **84 mg/cm² of cell**. *The substrate and panel
  hardware are ~5.7× the mass of the silicon they carry.*
- **Bypass diodes are inside the cell, not a board part:** the test plan's scope is *"testing, visual
  inspections, and verification of the pre-installed bypass diode on the XTJ-Prime solar cells"*, and
  §2 tests *"bypass diode characterisation"*. **This is the commercial-space answer to our bypass
  question: per-cell diodes are integrated into the cell by the cell maker.**
- **Acceptance criteria for incoming bare/CIC cells (very reusable):** edge chips ≤ 12 mm, corner
  chips ≤ 1.1 mm, surface nicks ≤ 5 mm; *"The sum of all the areas of the defects found in step 2 must
  not exceed 1.33 cm²"*; inspect *"the contact weld area as these could weaken interconnections
  between cells"*; cover-glass criteria — must *"cover 100% of the bare solar cell"*, *"should not
  contain any bubbles larger than 0.02 mm²"*, and *"cannot have cracks with a visible separation"*.
- **Test order and environment:** cell-level → PCB-component-level → PVA (assembled) level; ambient
  *"101.325 ± 3.3 kPa, 23 ± 5 °C, 40–60% RH"*; test-plan chapters include *"Vacuum Thermal Cycling
  Test"*, *"Humidity Test"*, *"Electrical continuity check"*, *"Capacitance test"*, *"Temperature
  Coefficients Check"*; the thermal-test tolerance table references gradients such as *"-40 to -30"*
  and notes *"the temperature can vary from -50 to -40 when conducting thermal cycling at -40 °C"*.
  It also bans *"pure Tin, Cadmium, or Zinc"* in the finished panel and references
  **ECSS-Q-ST-70-02C** for thermal-vacuum outgassing and **ECSS-E-ST-20-08C** as its parent standard.

### 3.3 Craig Clark & Steven Kirk (Clyde Space Ltd), *Off-the-Shelf, Deployable Solar Panels for CubeSats* — PRIMARY (industry), 2012

- **URL:** http://mstl.atl.calpoly.edu/~workshop/archive/2012/Spring/33-Clark-Solar_Panels.pdf
- **What it is:** a CubeSat workshop presentation by a commercial panel vendor (Ukube-1 flight
  hardware, NASA GEVS qualification).
- **The headline system-level failure mode:** *"The most common failure of CubeSats is negative power
  budget."* — i.e. in practice arrays under-deliver rather than break.
- **Deployable panel qualification:** the double-deployable variant is *"Up to 4 faces of solar cells
  (front and back)"*, has *"Integrated MTQ, TKD and thermal knifes"*, is *"Tested at −40 °C and
  +80 °C"*, and is *"Designed for P-POD specification and clearance (fits within 6.5 mm envelope)"*.
- **Redundancy in the release mechanism:** *"Integrated Thermal Knives and thermal knife drivers
  (dual redundant)."* Also *"All deployed panels are double sided"* and 90°/135° deployment options.
- **Power effect of deployment, quantified:** a 3U with body-mounted panels gives *"Orbit average
  power of 4.9 W"*; the same bus with deployed panels gives *"Orbit average power of 20.8 W"* and
  *"Peak power is 40W"* — the deployable is worth ~4×, which is the real reason wings exist.

### 3.4 OreSat (Portland State Aerospace Society) solar modules — REAL, LICENSED, KiCad + test plan

- **URL:** https://github.com/oresat/oresat-solar-hardware
- **Licence:** *"This source describes Open Hardware that is licensed under CERN-OHL-S v2, or any later
  version… Copyright the Portland State Aerospace Society, 2025."* (`README.md`). This is a genuinely
  open, reusable licence (and the best-licensed hardware found in this survey).
- **What it actually contains (verified from the git tree):** KiCad projects for several 1U solar
  modules — GaAs + Si cell variants, STM32 and MCXN processor variants — plus `1u_panel/test-plan.md`,
  LTSpice MPPT-boost simulations, `kapton-tape-outline/solar-module-tape-outline.gbr`, and a
  `1u_panel.pretty` footprint library. Board: *"4 layer board / Bounding box is 83.0 x 100.0 mm /
  Board thickness is 1.59 mm"*, ENIG or immersion silver.
- **They fly with a per-module true MPPT:** *"each 1u panel has its own true maximum power point
  tracker, with a software-defined MPPT algorithm"*, boosting *"the cell voltage up to 8.2 V in order
  to directly charge the batteries"*.
- **Assembly requirements worth copying verbatim:** *"Solder paste MUST be leaded. Aqueous flux and
  wash strongly preferred. Clean to NASA Standard 'Visibly Clean (VC)'… No conformal coating."*
  Cells are *"hand placed"* using a separate PSA SOP: *"PSAS SOP - Solar Cell mounting with PSA"*.
- **`test-plan.md`, read — a reusable bring-up order:** power the input at *"5V @ 50 mA max"* and
  check the draw (13.5 mA +3/−1) before anything else; verify rails at named test points; *"do not
  continue to test if a test fails. Instead, debug the PCB then continue to test. If you don't fix
  these problems in order, you may end up destroying other circuits."*; then program the MCU; then an
  MPPT functional test using *"Two solar cell test panel with halogen bulb (or solar simulator)"*;
  then a temperature functional test using *"Temperature controlled hot air gun"* at ~100 °C against
  the on-board TMP101A sensors.

### 3.5 NanoSat Lab (UPC) 3CatNXT PocketQube — REAL, PocketQube-scale, KiCad + SolidWorks

- **URL:** https://github.com/nanosatlab/pocat-hw
- **Licence:** **no licence file and no `license` field found via the GitHub API** — i.e. all rights
  reserved by default. *Read it for method; do not copy files from it.*
- **What it contains:** the complete KiCad electrical design of a 1U-class PocketQube — `pq_eps/`,
  `pq_latboard/` (the lateral solar face), `pq_topboard/`, `pq_botboard/`, `pq_latboard_deploy/`,
  `pq_adcs/` — plus the SolidWorks/STEP mechanical assembly, including
  `assembly/bottom/Solar_Cell_Azur.SLDPRT` and `assembly/lateral/solar-cells/`.
- **The one-pad-per-face solution, read out of the board file
  `pq_latboard/PQ_Lat_Board/PQ_Lat_Board.kicad_pcb`:** the solar cell is a single footprint
  `power-nsl:Lighttricity_S3040_CIC` (a 30 × 40 mm CIC cell, outline 40.64 × 30.734 mm) carrying
  **three pads**: two `7 × 4 mm` rounded-rect pads on net **GND** (the cell's back/body contact, one
  at each end of the long axis) and a `5 × 5 mm` pad on net **/SOLAR** (the front-face tab contact),
  plus one deliberately `unconnected-(SC1-Pad2)` pad. The cell sits on **B.Cu** (bottom side).
- **Bypass diodes: none on this board.** A search for any diode footprint (`D_*`, `BAT*`, `MBR*`,
  `SS*`) in both `PQ_Lat_Board.kicad_pcb` and `PQ_EPS.kicad_pcb` returned **nothing**. This is a real
  data point that a flown-class PocketQube lateral solar board carries **no bypass diode at all**.

### 3.6 Spacecraft Design Lab 2019 solar panel library — REAL KiCad footprint library for *bare* cells and a *Schottky*

- **URL:** https://github.com/spacecraft-design-lab-2019/Solar-Panel-Z
- **Licence:** **no licence file found** (GitHub API `license: None`). Read for method; do not copy.
- **What it contains (verified):** `Libraries/SolarCellParts.pretty/` with
  `SB Diode.kicad_mod`, `SM111K04L.kicad_mod`, `SM141K04LV.kicad_mod`, `KXOB25-05X3F.kicad_mod`,
  `Burn Wire.kicad_mod`, `Burn-Wire-Rotated.kicad_mod`; plus `SolarCellZ_v1.kicad_pcb`.
- **Read out of `SB Diode.kicad_mod`:** a two-pad SMD Schottky bypass-diode land —
  `pad 1 smd rect (at -1.2 0) (size 2.7 1.4)` and `pad 2 smd rect (at 1.85 0) (size 1.4 1.4)`.
- **Read out of `SM141K04LV.kicad_mod`:** the bare-cell land for a 45 × 15 mm package with **two
  circular 4 mm pads at opposite ends of the same face** (`pad 1 … (at 5.5 0) (size 4 4)`,
  `pad 2 … (at 39.5 0) (size 4 4)`) — i.e. the designer assumes the two terminals are brought out to
  the cell's two *ends*, which is exactly our cell's geometry (one pad per face, at opposite ends).
- **Read out of `SolarCellZ_v1.kicad_pcb`:** the board contains **8 × `KXOB25-05X3F` cell footprints
  (SC1…SC8) and exactly 2 × `"SB Diode"` footprints (D4, D5)** — i.e. **bypass diodes are fitted
  per *group*, not per cell** (2 diodes for 8 cells), with the cells wired as two 4-cell groups.

### 3.7 UWCubeSat deployable-panel — EMPTY, listed to prevent a false hit

- **URL:** https://github.com/UWCubeSat/deployable-panel — description *"Deployable solar array PCB
  files"*, but the repository contains only `.gitignore` and `README.md` (**2 files, 0 KB of design
  data**). There are **no design files to reuse**. Noted so nobody else wastes a lookup.

---

## 4. Tabbing, soldering, the one-pad-per-face problem, and encapsulation

### 4.1 Sinovoltaics — *Tabbing ribbons: design and purpose* — INDUSTRY PRIMER, concrete numbers

- **URL:** https://sinovoltaics.com/learning-center/materials/tabbing-ribbons-design-and-purpose/
- **Ribbon spec:** *"Flatt copper conductors about 2mm wide (suitable for most panels) with
  pre-soldered surfaces"*; *"made from 'oxygen-free high conductivity' (OFHC) copper"*;
  *"The solder layer (often 0.025 mm thick) also provides the solder mass which melts to make the
  connection"*; *"The copper used is 'dead soft' so that it can be easily bent for soldering to the
  cells and after the connection, does not stress the cell."*
- **Bond temperature:** *"Automatic tabbing machinery utilizes various methods including hot air jets
  radiative heat to raise the temperature to 150 °C or more to make a quick melt of the solder on the
  two joining surfaces. This is called reflow soldering where additional solder is not applied but
  existing solder on one or both mating surfaces melts and makes the joint."*
- **The failure mode that matters for us — thermal cycling microcracks:** *"The soldering process has
  to be carefully controlled to prevent chances of microcracks in the cell due to thermal or physical
  stress. These cracks are difficult to detect but can cause a premature failure. PV modules operating
  at a higher temperature may often fail due to deterioration of the solder joint. During soldering,
  the cells and the copper ribbons get heated, which expands them, and then allowed to cool after the
  solidification of solder. Differing coefficients of thermal expansion of the substrate and the
  ribbon as well as a non-uniform temperature gradient across the cells caused during the soldering
  process are generally responsible for buildup of thermal stresses in the components."*
- **Shading loss of the ribbon itself:** the ribbon shades the cell; *"The top surface is made highly
  reflective so that it reflects light back up rather than absorbing"*, recovering a fraction.

### 4.2 Sinovoltaics — *Solar cell soldering: what is it?* — INDUSTRY PRIMER

- **URL:** https://sinovoltaics.com/learning-center/manufacturing/solar-cell-soldering-what-is-it/
- **Iron temperature:** *"The temperature is important and can vary from 300 to 450 degrees Celsius.
  As mentioned above, it depends on the melting temperature of the solder on the tab ribbons."*
- **The overheat failure:** *"it is important not to overheat the solar cells, which will make the
  cells brittle and will definitely damage the cell… The risk is that the solar cell will crack
  during the lamination process."*
- **Why a hot iron is required (the cell is a heatsink):** *"the solar cells will function as a heat
  sink… The solder should melt before the cells takes out all the heat from the iron. The bigger the
  solar cell, the more heat you need to melt the solder. Manufacturers usually have a heating pad
  underneath the solar cells during soldering."*
- **Flux:** *"In order to solder the tab ribbons to the solar cell, PV manufacturers apply soldering
  flux to the tab ribbon… The soldering flux is used to remove the oxide from the tab ribbons or bus
  ribbons."* — i.e. flux the **ribbon**, and it is oxide removal, not wetting magic.

### 4.3 Indium Corporation — *Hand Soldering Recommendations for Solar Module Assembly* — INDUSTRY, PRACTICAL

- **URL:** https://www.indium.com/blog/hand-soldering-recommendations-for-solar-module-assembly/
- **Tip geometry:** *"using cone point soldering tips when they were working with 2mm wide solder
  coated tabbing ribbon. Simply changing the tip to a 2mm wide chisel point made all the
  difference… The chisel tip allows heat to flow across the ribbon, instead of only heating a single
  point."*
- **Pre-tin the iron:** *"melt a small amount of solder onto the tip of your iron before soldering,
  and be sure it's the same alloy you are soldering with."*
- **Alloy matters; low-temperature alloys can be destroyed by too much heat:** *"In some cases with
  low-temperature alloys (like bismuth or indium alloys), excessive soldering temperature can de-wet
  the alloy and char low temperature fluxes."*
- **Heat from below:** *"Silicon is known to pull heat away – that c-Si solar cell that needs to be
  soldered is a heatsink! Some solder equipment vendors also provide underside heating pads to help
  prevent excessive heat loss."*
- **Flux selection and a clean tip:** *"Use the correct flux… There are fluxes for high temperatures
  or low temperatures, cleaning with water or not cleaning at all."*; *"Those oxides and charred flux
  residues can easily be removed by wiping the hot iron across the wet sponge."*

### 4.4 SolarPanelsTalk — *Tabbing hints for solar cells* and *Issues when soldering back of solar cells* — PRACTITIONER FORUM, ANECDOTAL but specific

- **URLs:** https://www.solarpaneltalk.com/forum/diy-solar-panels/assembly-and-connection/9890-tabbing-hints-for-solar-cells
  and https://www.solarpaneltalk.com/forum/diy-solar-panels/diy-solar-panels-aa/16109-issues-when-soldering-back-of-solar-cells
- **The front/back pad problem, named:** *"When tabbing the back of the cells, the (I'll call it
  'solder pad') sometimes kind of 'evaporates'."* The explanation offered: *"The metal layer on
  cells, is only a few atoms thick, and it dissolves in solder."*
- **The fix offered, and it is a single-pass rule:** *"add a little (just a little) more solder to
  the tab wire. Then flux the cell backside. Lay the flat tab wire on the backside, and gently drag
  your hot iron down the tab wire, allowing the heat to flow thru the tab wire, and reflow onto the
  cell."* — and explicitly: *"i don't advise tinning the cell, then adding the tab wire, that's 2
  heat cycles, and you loose more metalization than just one pass would."*
- **Cell cupping and why it matters:** *"The difference in temperature from the top surface of the
  cell to the bottom can make it curve. This will not, by itself, cause problems unless the solder
  hardens while the the space between two solder points on the tabbing wire is different from what it
  will be when the cell cools."* Heat-sinking the underside is the standard mitigation people use
  (*"He uses the tempered glass under the cells to take some of the heat so that the cells don't warp
  from the heat"*; another uses *"a sheet of metal that was actually the side panel of an old PC
  under the cells"*).
- **Alloys quoted by the posters:** *"63/37 melts at 183 °C"*; *"Sn96Ag4 with a melting point of
  221 °C and bismuth containing Bi58Sn42 with a melting point of 138 °C are recommended for tabbing
  solar cells"*; *"I found that using a small 40 Watt iron is hot enough."*
- **Warning about the electrode peeling:** *"The absolute temperature can damage the semiconductor
  and the coatings, and can even make the electrode separate from the surface of the cell."*

### 4.5 DIY Solar Homes — *Tabbing Solar Cells – The Right Way* — ANECDOTAL

- **URL:** http://diysolarhomes.com/blog/solar-cells/tabbing-solar-cells-the-right-way/
- **Iron setting:** *"The soldering iron should be of a good quality with a 65 to 75 Watt adjustable
  unit with the temperature set at about 700 F. You must find the temperature that is perfect for
  your specific solder. If you run the soldering iron too cold, the solder will not run properly, too
  hot and you risk damaging the solar cell"* (700 °F ≈ 371 °C, consistent with §4.2's 300–450 °C band).
- **Ribbon coating, a second number:** *"Solar tabbing ribbon typically consists of 10 -15 micrometers
  of solder alloy, commonly SN60 (60% tin and 40% lead) coated on copper strip"* — note this is
  thinner than Sinovoltaics' "often 0.025 mm" and both are pre-solder, not the joint filler.
- **Polarity convention:** *"In general, the solar cells are negative on the front and positive on
  the back"* — **opposite** to the convention implied by our repo's "one pad front, one pad back";
  polarity must be confirmed on the actual cell, not assumed.

### 4.6 DSNEG — *How To Use Tab And Solder PV Solar Cells Manually* — VENDOR GUIDE, ANECDOTAL

- **URL:** https://www.dsneg.com/info/how-to-use-tab-and-solder-pv-solar-cells-manua-40452362.html
- **The over-hang solution to the front/back problem:** *"This picture shows soldering the tab wire
  to the cells in the back (positive) side with enough hanging over to cover the next cell on the
  front (negative) side."*
- **Tab vs bus wire, and the width range for bus:** *"Bus wire or Connecting wire looks like tab wire
  but is much wider. Bus wire is used to carry the current across each row. It can range from 2.5mm
  to 5mm depending on the power of the panel and size of the solar cells."*

### 4.7 PV Lighthouse / pv-education — *Bypass Diodes* (the per-cell vs per-string question) — AUTHORITATIVE TEXTBOOK

- **URL:** https://www.pveducation.org/pvcdrom/modules-and-arrays/bypass-diodes
- **Hot-spot physics:** *"if a solar cell is reverse biased due to a mismatch in short-circuit
  current between several series connected cells, then the bypass diode conducts… The maximum reverse
  bias across the poor cell is reduced to about a single diode drop, thus limiting the current and
  preventing hot-spot heating."*
- **What happens when it is omitted:** *"The maximum power dissipation in the shaded cell is
  approximately equal to the generating capability of all cells in the group."* — the shaded cell
  must absorb the whole group's output as heat.
- **Per cell or per string, in practice — the direct answer:** *"In practice, however, one bypass
  diode per solar cell is generally too expensive and instead bypass diodes are usually placed across
  groups of solar cells… The maximum group size per diode, without causing damage, is about 15
  cells/bypass diode, for silicon cells. For a normal 36 cell module, therefore, 2 bypass diodes are
  used to ensure the module will not be vulnerable to 'hot-spot' damage."*
- **Relevance to us:** our array is **12 cells in series across four wings**. Under this textbook
  rule, **one bypass diode for the whole 12-cell string is inside the "safe" group size** (≤15) for
  *hot-spot damage* — but that rule contemplates *terrestrial* irradiance and a *2-string/36-cell*
  module; it says nothing about a **12:1** irradiance collapse on one wing (§2.2, §3.6) where whole
  wings, not single cells, are the mismatched element.

### 4.8 UVA BIG Idea 2018 proposal, *Photovoltaic…* (Mars balloon concept) — ENCAPSULATION MASS FIGURES, design-study grade

- **URL:** https://bigidea.nianet.org/wp-content/uploads/2018/03/2018-BIG-Idea-Final-Paper_UVA-1.pdf
- **CAVEAT: this is a Mars balloon concept study, not a HAB flight and not a flown array.** It is used
  here only because it is one of the few open sources that names encapsulation materials *with
  thicknesses*.
- **Encapsulation stack:** *"With a density of 1420 kg/m³ and a thickness of 10 microns for solar
  panels and 50 microns for Kevlar structural support mesh, the total mass required for the fabric is
  529 kg per balloon. The layer of Kevlar-29, in a mesh of 55 denier, will provide extra strength and
  support to the balloon and will contribute to support the solar cells. The whole material will be
  encapsulated with a 25-micron optically transparent polyimide film (LaRC-CP1)…"*
- **Usable number:** a **25 µm polyimide** cover film; at ~1.42 g/cm³ that is ≈ **3.6 mg/cm²** of
  film per unit cell area — i.e. an *encapsulation* you can add for a few percent of the silicon mass
  (our 0.21 mm cell = 48.9 mg/cm²), **not** a coverglass. Any rigid coverglass is 50–100× thicker.

---

## 5. Transferable lessons

Legend: **APPLIES HERE** — act on it. **DOES NOT APPLY** — with the reason. **NEEDS A TEST** — the
evidence is absent or inconclusive; do not decide without measuring.

1. **Do not leave voids under the cell: in vacuum they crack the silicon.** *(APPLIES HERE — our most
   likely field failure.)* AlbertaSat: conductive-epoxy and double-Kapton-tape assemblies both *"can
   cause the formation of air pockets or voids between the solar cells and the substrates. When
   exposed to vacuum, these air pockets can crack the solar cells"*; the fix is a single piece of
   double-sided Kapton and **via stitching denser than ~5/cm² plus venting holes** in the substrate
   (https://arxiv.org/html/2407.19356v1). Our wing is bare cells on a spine/ribs frame at ~0.05–0.1 atm
   for hours and −60 °C (§ADR-049) — **any bonded area must be void-free and vented**. Watch test:
   the same source used a **thermal camera before and after vibration** to see voids.

2. **Bond the cell, but bond it sparingly and thin — and vent the bond line.** *(APPLIES HERE.)*
   Same source: *"if too much epoxy is used, it will degas and expand as it cures, which can cause
   significant stress on the solar cells"*; ~0.25 mL of silver epoxy for a 69 × 40 mm cell, cured at
   120 °C then 100 °C in **partial vacuum** to pull volatiles out
   (https://arxiv.org/html/2407.19356v1).

3. **Cells floating on a frame with no bond is the untested option here.** *(NEEDS A TEST — no source
   found either way.)* Every flight design read in this survey either **tapes or epoxies the cell to
   the substrate** (AlbertaSat, OreSat *"hand placed"* with PSA) or **laminates it into a panel**
   (Global Aerospace honeycomb). No source in this survey describes a bare 0.2 mm silicon cell
   carried only by its tabs on a spine-and-ribs frame. Our §ADR-049 open item — *"whether
   spine-and-ribs leaves unsupported silicon spans that crack"* — is **not answered by the
   literature**; it must be measured.

4. **Smallest safe unsupported span for a 0.21 mm cell: UNKNOWN — NEEDS A TEST.** No source found
   states a span limit. The nearest evidence is that these cells are *extremely* fragile and are
   normally supported: AlbertaSat **scribed and snapped** 80 × 80 mm silicon to size, *"the cells are
   extremely fragile and can break easily"* (https://arxiv.org/html/2407.19356v1); the Hyperion test
   plan has an explicit chip/defect budget for cells (§3.2, https://raw.githubusercontent.com/AlbertaSat/ex2_hyperion_solar_panel_hardware/master/Documentation/TX2-PW-435%20Ver.%201.00%20Hyperion%20Testing%20Plan.pdf).
   A defensible test: dead-load or vacuum-bag a spare cell on candidate rib pitches and measure the
   deflection/failure load, rather than trusting a rule of thumb.

5. **Bypass diodes are per-cell only inside commercial space cells; terrestrial practice is per
   *group* of ~15 cells; a whole-array (12-cell) bypass is at the edge of the textbook rule.**
   *(APPLIES HERE — but the reasoning must be stated.)* pv-education: *"one bypass diode per solar
   cell is generally too expensive and instead bypass diodes are usually placed across groups of solar
   cells… The maximum group size per diode, without causing damage, is about 15 cells/bypass diode,
   for silicon cells"* (https://www.pveducation.org/pvcdrom/modules-and-arrays/bypass-diodes).
   Space cells solve it in the die: Hyperion's plan is *"verification of the pre-installed bypass
   diode on the XTJ-Prime solar cells"* (§3.2). Two real small-sat designs in this survey carry
   **no** per-cell bypass (PocketQube lateral board: zero diode footprints; see §3.5) and **two
   diodes for eight cells** (Spacecraft Design Lab `SolarCellZ_v1.kicad_pcb`, §3.6).

6. **What failure looks like with the bypass omitted (the shading cascade): a stepped I–V curve and
   a cell absorbing the whole group's output.** *(APPLIES HERE for test interpretation.)*
   pv-education: *"The maximum power dissipation in the shaded cell is approximately equal to the
   generating capability of all cells in the group"* (https://www.pveducation.org/pvcdrom/modules-and-arrays/bypass-diodes).
   AlbertaSat saw the signature and used it as a diagnostic: partial illumination produced
   *"stepping… caused by activation of the bypass diodes… Stepping can also signify uneven
   illumination of the panels"*, and they ran *"reverse bias testing to identify any points of
   damage"* (https://arxiv.org/html/2407.19356v1). **Copy that test** — half-cover a wing and look
   for a step.

7. **The front/back pad problem is solved three different ways in the wild; only one is a
   board-side fix.** *(APPLIES HERE — this is the core mechanical question.)*
   - **(i) Over-hanging tab ribbon** — the tab soldered to the back contact "with enough hanging over
     to cover the next cell on the front (negative) side" (https://www.dsneg.com/info/how-to-use-tab-and-solder-pv-solar-cells-manua-40452362.html). Cheapest, but every joint is hand-made and the
     ribbon carries the current *and* the mechanical load.
   - **(ii) Edge-access cell land** — OreSat's published `SPECTROLAB-XTE-SF.kicad_mod` places **all
     six cell pads along one edge of the 69.5 × 40 mm cell** (`POS1`, `POS2` at ±12 mm; `NEG1`…`NEG4`
     at −22.75, −0.5, +4.2, +21.75 mm; pads 3 × 5 mm and 5 × 5 mm, `F.Cu`/`F.Mask` only) so that
     *both* faces of the cell are contacted from a single edge (https://raw.githubusercontent.com/oresat/oresat-solar-hardware/master/1u_panel/kicad/1u_panel.pretty/SPECTROLAB-XTE-SF.kicad_mod).
   - **(iii) Two lands per cell end** — the PocketQube lateral board lands the **back/body contact on
     GND with two 7 × 4 mm pads** and the **front tab on /SOLAR with one 5 × 5 mm pad** (§3.5).
   **What none of them does** is put one small pad per face and rely on a via — the far pad is on the
   cell, not the board (confirmed by `docs/analysis/wing-fab-cost.md` §1.1 in-repo).

8. **After thermal cycling, cell-tab solder failures look like de-metallisation and microcracks, not
   like an obvious break.** *(APPLIES HERE.)* Practitioner observation of the back contact:
   *"the 'solder pad' sometimes kind of 'evaporates'"* because *"The metal layer on cells, is only a
   few atoms thick, and it dissolves in solder"* (https://www.solarpaneltalk.com/forum/diy-solar-panels/diy-solar-panels-aa/16109-issues-when-soldering-back-of-solar-cells).
   Industry: *"microcracks in the cell due to thermal or physical stress… are difficult to detect but
   can cause a premature failure"* and *"PV modules operating at a higher temperature may often fail
   due to deterioration of the solder joint"*, driven by *"Differing coefficients of thermal
   expansion of the substrate and the ribbon"* (https://sinovoltaics.com/learning-center/materials/tabbing-ribbons-design-and-purpose/).
   **Practical consequence: a single-pass joint and a lower-melting alloy**, per the same forum
   thread (*"i don't advise tinning the cell, then adding the tab wire, that's 2 heat cycles, and you
   loose more metalization than just one pass would"*).

9. **Solder hot and fast, from a chisel tip, with a bottom-side heat source, or you crack the cell.**
   *(APPLIES HERE.)* Iron **300–450 °C** and the cell is a *"heat sink"*
   (https://sinovoltaics.com/learning-center/manufacturing/solar-cell-soldering-what-is-it/);
   a **2 mm chisel tip** for 2 mm ribbon, pre-tinned tip, correct flux, and *"Use a bottom side
   heater"* (https://www.indium.com/blog/hand-soldering-recommendations-for-solar-module-assembly/);
   a real HAB builder converged on **250 °C hoof tip, flux pen, load the tip with solder, a few
   seconds** (http://tt7hab.blogspot.com/2017/09/). Overheating makes the cell *"brittle"* and it
   *"will definitely damage the cell"*.

10. **Do not switch the iron temperature on a whim; temperature *gradient* across the cell is itself
    the warping mechanism.** *(APPLIES HERE.)* *"The difference in temperature from the top surface
    of the cell to the bottom can make it curve. This will not, by itself, cause problems unless the
    solder hardens while the space between two solder points… is different from what it will be when
    the cell cools"* (https://www.solarpaneltalk.com/forum/diy-solar-panels/assembly-and-connection/9890-tabbing-hints-for-solar-cells).
    A flat cold backing (tempered glass, a metal plate) under the cell is the folk mitigation.

11. **Measure every cell before it goes on the wing.** *(APPLIES HERE — cheap and high-value.)*
    TT7 found his panel at *"only about 15% of expected power"* because *"three cells…
    significantly underperformed"*, and his first action is now *"I measure all the cells to be used
    with a multimeter to ensure they output expected amount of current when illuminated"*
    (http://tt7hab.blogspot.com/2017/09/). AlbertaSat likewise *"tested all solar cells individually…
    visually inspected for abnormalities, weighed, and dimensioned"* and ran reverse-bias tests
    (https://arxiv.org/html/2407.19356v1).

12. **Test every cell against a chip/defect budget before assembly — and record the rejects.**
    *(APPLIES HERE, and it is free.)* Hyperion's acceptance limits: edge chips ≤ 12 mm, corner chips
    ≤ 1.1 mm, surface nicks ≤ 5 mm, total defect area ≤ 1.33 cm², and specific attention to
    *"defects in the contact weld area as these could weaken interconnections between cells"*
    (https://raw.githubusercontent.com/AlbertaSat/ex2_hyperion_solar_panel_hardware/master/Documentation/TX2-PW-435%20Ver.%201.00%20Hyperion%20Testing%20Plan.pdf).
    Our cells are scrap-grade eBay-class silicon; this budget is the cheapest possible screening.

13. **Assemble the frame and all electronics first, then attach cells last.** *(APPLIES HERE.)*
    *"All component-level testing is done before adhering the solar cells to the substrates, which
    reduces the likelihood of cell damage"* and *"The panels are assembled after all other electronic
    components have been added and fully tested"* (https://arxiv.org/html/2407.19356v1); OreSat's flow
    is the same (assemble → test rails → program MCU → then cell functional test)
    (https://raw.githubusercontent.com/oresat/oresat-solar-hardware/master/1u_panel/test-plan.md).

14. **The structure, not the silicon, dominates panel mass — which is the whole argument for our
    spine.** *(APPLIES HERE — supports ADR-049.)* Hyperion: 84 mg/cm² of cell inside a panel that
    weighs **476 mg/cm²** — substrate + hardware are **~5.7× the cell mass**. Global Aerospace's
    2 m × 2 m SAMs are ≈ **1.46 kg/m²** of aluminium-honeycomb panel
    (https://www.gaerospace.com/projects/Modular_Solar/pdf/Aaron_AIAA_ATIO_6744.pdf). Our
    spine+ribs frame at 0.187 W/g exists precisely because the repo already beat this (ADR-049 rejects
    the full-area FR4 carrier at 2.61× the cell's areal mass).

15. **Published mass-per-watt benchmarks to compare 0.187 W/g against:**
    *(APPLIES HERE — use with the caveats below.)*
    - **19.4 W/kg (≈ 0.019 W/g)** — Global Aerospace HighPower, *whole HAB system* (SASS + bottom plate
      + 6 SAMs + mechanisms), 2486 W / 128 kg, "versus the goal of 20 W/kg"
      (https://www.gaerospace.com/projects/Modular_Solar/pdf/Aaron_AIAA_ATIO_6744.pdf). Its *panel-only*
      figure is ≈ **14.1 W/kg**.
    - **≈ 91 W/kg (≈ 0.091 W/g)** — AlbertaSat Hyperion *deployable panel*, 6.9 W ÷ 76 g, including
      sensors, harness and the aluminium hinge interface (§3.2, derived from the design doc's
      Table 8 + "14.4 V at 0.48 A").
    - **0.527 W/g** at *cell* level for XTJ-Prime (1.18 W ÷ 2.24 g) versus **0.400 W/g** for our cells
      (`docs/analysis/wing-mass-shape.md:425`). **Our silicon is ~1.3× worse per gram than a
      space-grade GaAs cell**, which is the price of using 0.5 V / 19.5 mW·cm⁻² polycrystalline cells.
    - **CAVEAT, stated honestly:** our 0.187 W/g is a *bare, uncertified, unencapsulated* array figure.
      The two benchmarks above include encapsulation, deployment mechanism, harness and qualification
      margins. Comparing 0.187 W/g directly to 91 W/kg overstates our advantage by exactly the amount
      we have not yet paid for (bonding, protection, attachment, qualification).

16. **A shading collapse on one of four series wings is a *power* problem in every flight design read;
    it is a *safety* problem only at landing.** *(APPLIES HERE for the budget; the landing caveat does
    NOT apply.)* AlbertaSat's deployment-failure analysis is purely energetic (9.6 W → 2.9 W);
    Global Aerospace's only *detachment* requirement is about ground hazard: *"no part of the
    HighPower™ solar array subsystem detach, posing a hazard to people or property on the ground"*
    (https://www.gaerospace.com/projects/Modular_Solar/pdf/Aaron_AIAA_ATIO_6744.pdf). **DOES NOT
    APPLY HERE (detach-as-ground-hazard):** our payload is small and our launch/landing regime is not
    a public-safety case — but the *in-flight* detach case **does** apply and must be load-tested.

17. **Landing, not flight, destroys balloon solar panels.** *(APPLIES HERE if the wing is to be
    recovered/reused; otherwise a note.)* *"solar array panels are quite fragile and they will often
    sustain irreparable damage"* on impact and drag; *"In the past, solar arrays have been sacrificed
    on landing"* (https://www.gaerospace.com/projects/Modular_Solar/pdf/Aaron_AIAA_ATIO_6744.pdf);
    the JPL 1968 flights confirm it — a free-falling tracker's *"solar cell cover glass was chipped"*
    (https://ntrs.nasa.gov/api/citations/19700002654/downloads/19700002654.pdf).

18. **Double-sided wings are standard practice — and useless for an opaque cell.** *(APPLIES HERE as a
    confirmation of ADR-049's rejection.)* Clyde Space: *"All deployed panels are double sided"*, the
    double-deployable carrying *"Up to 4 faces of solar cells (front and back)"*
    (http://mstl.atl.calpoly.edu/~workshop/archive/2012/Spring/33-Clark-Solar_Panels.pdf). They use
    **CIC cells that are single-sided by construction and mounted on both sides of a substrate** —
    not one cell used from both faces. Our cells are opaque; the back face produces nothing. ADR-049's
    rejection of the double-sided carrier is consistent with this.

19. **A true MPPT per sub-array beats a series string; the industry answer to mismatch is power
    electronics, not geometry.** *(DOES NOT APPLY HERE — for now, and here is the reason.)* OreSat
    gives *"each 1u panel… its own true maximum power point tracker"*
    (https://github.com/oresat/oresat-solar-hardware). Hyperion likewise runs the whole array at MPPT
    and sets the EPS MPPT voltage *"0.3 V per cell less than at max power point"* (§3.2). We have a
    supercapacitor + LDO architecture (ADR-006/044); adopting per-wing MPPT is a new converter per
    wing (mass, parts, failure points) and is out of scope for this build. **Revisit only if the
    measured per-wing mismatch justifies it.**

20. **Keep the wings structurally identical and keep the frame a real load path; hand-aligning four
    long arms is the known failure mode.** *(APPLIES HERE.)* Clyde Space ships *"single deployed"* and
    *"double deployed"* variants but with *"standard structures and standard mechanical/electrical
    interfaces"*, and a *"CubeSat assembly jig allows deployment tests"*
    (http://mstl.atl.calpoly.edu/~workshop/archive/2012/Spring/33-Clark-Solar_Panels.pdf). Our
    ADR-046 already picks a milled slot precisely to key the 90° angle — this survey supports that
    choice: **the jig/key is not optional when four 176 mm arms must be hand-soldered at 90°.**

21. **Bake out / vacuum-cure anything that outgasses, and keep the joint metals clean.** *(APPLIES
    HERE, lightweight version.)* AlbertaSat cures in partial vacuum and measured *"total mass loss and
    collected volatile condensable material"* of their Kapton tape
    (https://arxiv.org/html/2407.19356v1); Hyperion references **ECSS-Q-ST-70-02C** for thermal-vacuum
    outgassing, requires an aqueous wash cleaned to *"Visibly Clean (VC)"*, and **bans pure tin,
    cadmium and zinc** in the finished panel (§3.2). For a single flight we do not need the full
    standard, but **no-conformal-coating + clean + no pure-tin** is free and worth adopting.

---

## 6. UNVERIFIED sources (URL known, page was NOT readable)

Listed so they are not silently dropped, and so no one quotes them as if read. **Nothing in §5 relies
on these.**

| URL | What it appears to be | Why unverified |
|---|---|---|
| https://www.sciencedirect.com/science/article/abs/pii/S0960148118315301 | "Thermal performance of high-altitude solar powered scientific balloon", *Renewable Energy* (2018) | ScienceDirect returned an access-error page to automated fetch |
| https://www.sciencedirect.com/science/article/abs/pii/S0038092X2300868X | "Impact of cracks in solar array…" (Solar Energy) | same |
| https://www.researchgate.net/publication/366361749_In_situ_performance_and_stability_tests_of_large-area_flexible_polymer_solar_cells_in_the_35-km_stratospheric_environment | In-situ tests of flexible polymer solar cells in the 35 km stratosphere | ResearchGate returned "Access restricted… unusual activity from your network" |
| https://www.researchgate.net/publication/369262123_Testing_flexible_polymer_solar_cells_in_near-space | Testing flexible polymer solar cells in near-space | same |
| https://esmats.eu/amspapers/pastpapers/pdfs/2018/guzik.pdf | "Design and Development of CubeSat Solar Array…" (ESMATS 2018) | Server returned HTTP 403 Forbidden |
| https://dspace.mit.edu/bitstream/handle/1721.1/93800/900610426-MIT.pdf | "Dynamic Instabilities Imparted…" MIT thesis on deployable arrays | not fetched within budget |
| https://www.mdpi.com/2226-4310/8/3/64 | "Development of a Novel Deployable Solar Panel…" (Aerospace, MDPI) | fetch returned a 394-byte stub |
| https://arc.aiaa.org/doi/10.2514/6.2024-0728 | "Evaluating High Altitude Impacts of Solar Cell Performance…" | AIAA paywall; not attempted as it is known paywalled |
| https://www.caplinq.com/double-sided-polyimide-tape-pit2sd.html | CAPLINQ PIT2SD tape (AlbertaSat's tape) — datasheet would give the areal mass | fetch returned 0 bytes |

Also noted as **not usable**: https://github.com/UWCubeSat/deployable-panel (empty repository, §3.7).

---

## 7. What we should copy — specific artefacts, verbatim or adapted

| # | Artefact | Source URL | Verbatim or adapt | Licence |
|---|---|---|---|---|
| A1 | **Cell defect-acceptance limits** — edge chip ≤ 12 mm, corner chip ≤ 1.1 mm, nick ≤ 5 mm, total defect area ≤ 1.33 cm², inspect the contact-weld area | https://raw.githubusercontent.com/AlbertaSat/ex2_hyperion_solar_panel_hardware/master/Documentation/TX2-PW-435%20Ver.%201.00%20Hyperion%20Testing%20Plan.pdf | **Adopt verbatim** as our incoming-cell screening rule | Apache-2.0 |
| A2 | **Test order** — SCA (cell) → PCB components → PVA; all electronics tested before cells are attached | same PDF + https://arxiv.org/html/2407.19356v1 | **Adopt verbatim** as our build sequence | Apache-2.0 |
| A3 | **Void/venting control** — single-piece double-sided Kapton (CAPLINQ PIT2SD, 5 mil) + via stitching > 5/cm² + vent holes; thermal-camera void inspection before and after vibration | https://arxiv.org/html/2407.19356v1 | **Adapt**: we have a spine, not a full substrate, so use it wherever we *do* bond | CC BY 4.0 (paper) |
| A4 | **Partial-illumination bypass test** — half-cover a wing, look for a step in the I–V curve, then reverse-bias the suspect cell | https://arxiv.org/html/2407.19356v1 | **Adopt verbatim** as the wing acceptance test | CC BY 4.0 |
| A5 | **KiCad land pattern for a bare/CIC cell, edge-access, both polarities on one edge** — `SPECTROLAB-XTE-SF.kicad_mod` (`POS1`/`POS2`, `NEG1`…`NEG4`) | https://raw.githubusercontent.com/oresat/oresat-solar-hardware/master/1u_panel/kicad/1u_panel.pretty/SPECTROLAB-XTE-SF.kicad_mod | **Adapt** (scale to 52.07 × 19.65 and 78.55 × 38.90 mm) — this is the pattern to imitate for our one-pad-per-face cells | CERN-OHL-S v2 |
| A6 | **SMD Schottky bypass-diode footprint** — `SOD123.kicad_mod` (OreSat) and `SB Diode.kicad_mod` (2.7 × 1.4 mm pad 1 / 1.4 × 1.4 mm pad 2) | https://raw.githubusercontent.com/oresat/oresat-solar-hardware/master/1u_panel/kicad/1u_panel.pretty/SOD123.kicad_mod · https://raw.githubusercontent.com/spacecraft-design-lab-2019/Solar-Panel-Z/master/Libraries/SolarCellParts.pretty/SB%20Diode.kicad_mod | **Adapt** — pick the land that fits the ≥2 A / 40 V part ADR-049 requires | CERN-OHL-S v2 (OreSat) / **no licence** (SDL — check before reuse) |
| A7 | **Bare-cell land with two end pads** — `SM141K04LV.kicad_mod` (two 4 mm round pads at opposite ends) | https://raw.githubusercontent.com/spacecraft-design-lab-2019/Solar-Panel-Z/master/Libraries/SolarCellParts.pretty/SM141K04LV.kicad_mod | **Adapt** — the closest existing analogue to our cell's terminal geometry | **no licence** (check) |
| A8 | **PocketQube one-pad-per-face land, read from a real board** — back/body contact on GND via two 7 × 4 mm pads, front tab on /SOLAR via one 5 × 5 mm pad | https://github.com/nanosatlab/pocat-hw (`pq_latboard/PQ_Lat_Board/PQ_Lat_Board.kicad_pcb`) | **Adapt the idea only** — do not copy files | **no licence** (see only) |
| A9 | **Bypass-diode placement evidence** — 2 Schottky footprints for 8 cells on a real board | https://github.com/spacecraft-design-lab-2019/Solar-Panel-Z (`SolarCellZ_v1.kicad_pcb`) | **Compare** — a real counter-example to per-cell | **no licence** (see only) |
| A10 | **Board bring-up test plan with an ordered "stop on first failure" rule** — `1u_panel/test-plan.md` | https://raw.githubusercontent.com/oresat/oresat-solar-hardware/master/1u_panel/test-plan.md | **Adapt verbatim** (our board, our rails) | CERN-OHL-S v2 |
| A11 | **Panel-level qualification environment** — TVAC < 10⁻⁶ Torr / 6 h functional; thermal cycling with a −50…−40 °C gradient window; vibration with pre/post inspection; humidity; the parent standard ECSS-E-ST-20-08C | §3.1 https://arxiv.org/html/2407.19356v1 and §3.2 (Hyperion test plan PDF above) | **Adapt** to the extent a one-off HAB flight can honestly justify — record what we skip | CC BY 4.0 / Apache-2.0 |
| A12 | **Cell temperature coefficients** to sanity-check our −60 °C Voc estimate — ΔVOC/ΔT = −5.6 mV/°C, ΔVMP/ΔT = −6.2 mV/°C | https://raw.githubusercontent.com/AlbertaSat/ex2_hyperion_solar_panel_hardware/master/Documentation/TX2-PW-387-Ver.%200.12%20Hyperion%20Detailed%20Design.pdf | **Adapt** — ours are poly-Si, so use the *sign and order of magnitude*, not the exact slope | Apache-2.0 |
| A13 | **Assembly materials SOPs** — "PSAS SOP - Solar Cell mounting with PSA" and the TMP101 mounting SOP (Google Docs, linked from the OreSat README) | https://github.com/oresat/oresat-solar-hardware (`solar-module-1u-gaas-MCXN/README.md`) | **Read before writing our own SOP** — the SOPs themselves are external Google Docs (unverified) | CERN-OHL-S v2 (repo) |

---

## 8. What this survey does **not** establish

- It does **not** establish a safe unsupported span for a 0.21 mm cell (lesson 4) — no source found.
- It does **not** establish whether our cells' front and back contacts are both at the cell *ends*
  (the assumption the SM141K04LV land makes) — that is our own `TODO(unverified)` pad measurement.
- It does **not** establish a mass-per-watt benchmark for a *bare, unencapsulated, hand-built* array —
  both benchmarks in lesson 15 include structure the operator has not yet built, so the comparison is
  directional, not like-for-like.
- It does **not** cover RF/Yagi wing work, or the ADR-045 antenna solder-access question.

**Honesty statement.** Every quotation in §2–§4 was taken from a page or PDF this session downloaded
and read; every URL was copied from the fetched resource, not reconstructed from memory. Sources that
could not be read are listed in §6 as UNVERIFIED and are not used to support any lesson. Where a claim
is the author's arithmetic on a source's own numbers, it is labelled *derived* and the formula is
shown. No source was read that this document does not name.
