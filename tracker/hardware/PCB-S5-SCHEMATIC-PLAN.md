# PCB-S5 — a real schematic for the C3 flight board (ADR-028), plan + v0

**Task:** t_6543830b (PCB-S5a: PLAN + first draft; the full build is PCB-S5b, gated behind this)
**Date:** 2026-09-17
**Board of record:** `tracker/hardware/output/v_c3_flight_4layer_placed.kicad_pcb`
**Frozen PCB sha256:** `f3cf0143e7deff991e9650643f1322945388fd135efbf5191f51520dcd6edaa6`
(placement verified: 0 pad overlaps, 0 courtyard overlaps, `placement_guard` exit 0)
**Status:** PLAN + a **v0 schematic that loads with 0 ERC errors**. Awaiting operator approval
before the full build (PCB-S5b). Supersedes `tracker/hardware/SCHEMATIC-PLAN.md` (2026-08-05,
"PLANNING ONLY — no .kicad_sch files yet"), which planned three variants and shipped none.

---

## 0. What exists after this card (v0, verified)

Everything below is regenerated deterministically from the frozen PCB by one script; nothing is
hand-typed. Re-running is idempotent for a given PCB sha256 — the files are **byte-identical**
across runs, which GATE 6 now proves (dispatch 4 fixed a `uuid4()` in the generator: before the
fix every re-run produced a different schematic, so the published sha256 was not provenance).
Determinism is gated on the `.kicad_sch`; the exported `v_c3_flight.net` carries a KiCad
generation timestamp, so it is expected to show a one-line diff after any gate run.

| artifact | path | sha256 | notes |
|---|---|---|---|
| schematic (v0) | `tracker/hardware/schematics/flight_board/v_c3_flight.kicad_sch` | `c15d00df…446d` | 140 756 B, 20 symbols, 22 nets |
| generator | `tracker/hardware/schematics/flight_board/build_flight_sch.py` | `30f39753…f73a` | PCB → schematic; exits 2 on pad-coverage failure, 3 on PCB sha mismatch. Dead locals removed; 19 pre-existing cosmetic E127/E128 continuation-indent findings remain (no behaviour change — the schematic sha is unchanged) |
| gate suite | `tracker/hardware/schematics/flight_board/check_sch_gates.py` | `02134fce…e13b` | 7 gates, exit 0 = all pass |
| custom symbol lib | `balloon_flight.kicad_sym` | `dfeb5c7b…d3e2` | the LR2021F33 symbol (only part absent from KiCad v9 libs) |
| footprint lib | `balloon_flight.pretty/` (15 `.kicad_mod`) | — | the PCB's own footprints, exported verbatim |
| lib tables | `sym-lib-table`, `fp-lib-table` | `1823b99b…a05b`, `f5e0002f…3a55` | make ERC resolve both link classes |
| ERC report | `v_c3_flight-erc.rpt` | — | 0 errors, 1 warning (`pin_to_pin`, see §4) |

Gate evidence for v0 (re-runnable, `python3 check_sch_gates.py`, exit 0):

```
GATE 6  determinism regenerate twice: sha256 run1 == run2      c15d00df…446d
GATE 0  load        kicad-cli sch erc v_c3_flight.kicad_sch           exit=0
GATE 1  severity    kicad-cli sch erc --exit-code-violations          0 errors, 1 warning
GATE 2  net parity  schematic=22  pcb=22   only-in-schematic=none  only-in-pcb=none
GATE 3  node parity nodes: schematic=84  pcb=84  nets-with-differing-nodes=0
GATE 4  netless     total=27  unnamed-mechanical=9  INTENTIONAL=7  DECLARED_GAP=11  unclassified=0
GATE 5  pad coverage build_flight_sch.py exit=0 (2 = a pad has no symbol pin)
ALL GATES PASS
```

Independently re-verified on dispatch 4 (2026-09-17, this commit) **without the repo's gate
code**: a separate parser (`independent_parity_check.py`, kept in the task scratch dir, not in
this repo) reads the frozen PCB with its own S-expression scanner and compares it against the
netlist that `kicad-cli` exports from the committed `.kicad_sch` — 125 pads, 98 netted pads,
**22/22 nets and 84/84 nodes, zero differences, no orphans on either side** (parity therefore
does not depend on the generator's own view of the PCB). The same pass counted 18 `(no_connect)`
markers and 11 on-sheet `GAP <ref>.<pad>: …` annotations in the file — 18 numbered netless pads
+ 9 unnamed mechanical pads = the audit's 27, 1:1. Raw `kicad-cli sch erc` exit 0;
`--exit-code-violations` exit 5 with **0 errors, 1 warning**.

**84/84 nodes across 22/22 nets, both directions, with zero differences** — the schematic is a
provable mirror of the frozen PCB, which is exactly what ADR-028 needed and never had.

---

## 1. Direction of truth

**The frozen PCB netlist and the tested firmware are authoritative. The schematic is DERIVED to
match them.** The generator reads the PCB's S-expression directly (no retyping), so parity is
structural rather than a promise. This follows the SKiDL skill's own rule: *the firmware IS the
source of truth*; here the tested firmware and the frozen PCB are the same truth, and the
schematic is a certification instrument, not a design source.

What happens on a mismatch (in order):

1. **Schematic disagrees with the PCB** → the generator is wrong. Fix the generator, regenerate.
   The `.kicad_sch` is a **build product**: never hand-edit it, always regenerate. (Hand edits
   are silently lost on the next run and break the sha-based provenance.)
2. **The check reveals the PCB is wrong** (e.g. SPI MOSI/MISO swapped versus the tested
   firmware) → the fix goes to the **PCB and firmware first**: patch → re-run the placer/
   publisher → `placement_guard` → **re-freeze (new sha256)** → update `FROZEN_SHA256` in the
   generator → re-run the netlist audit and the gates. Any pad that adds or moves a part forces
   that re-freeze; netlist-only declarations do not.
3. **Firmware and PCB disagree** → **firmware wins** (it runs on real hardware today); treat as
   case 2.
4. **Schematic is never "made to match" a known-wrong PCB.** The gate exists to fail, not to be
   satisfied by editing the mirror.

Guard: `build_flight_sch.py` hard-fails (`exit 3`) when the PCB's sha256 differs from
`FROZEN_SHA256`, so a schematic can never silently describe a different board revision.

---

## 2. Tool path — decision and justification

**Decision: a deterministic in-repo generator that emits `.kicad_sch` S-expressions from the
frozen PCB** (`build_flight_sch.py`, ~570 lines, Python stdlib + `kicad-cli` for the gates).
**SKiDL is the right tool for the *author-first* variants (S3-Future, C3+RP2040), not for this
board.**

Evaluated, with evidence:

| option | evidence | verdict |
|---|---|---|
| **In-repo generator (chosen)** | reading the PCB is structural; re-run is idempotent for a given sha; v0 measures 22/22 nets and 84/84 nodes with 0 ERC errors | **chosen** — derivation, not transcription |
| **SKiDL 2.3.0** | *is* installable (`pip download skidl==2.3.0` succeeded) and **does** ship a KiCad 9 schematic writer — `skidl/tools/kicad9/gen_schematic.py` (853 lines) + `sexp_schematic.py` (1 595 lines), with placement, net terminals and a self-run ERC. So the usual "SKiDL can't draw schematics" claim is **false** for 2.3.0 | not chosen *for this board*: connectivity would be re-typed from the PCB into Python, adding a transcription step in exactly the place ADR-028 failed. Use it where the schematic **leads** |
| **Hand-authored `.kicad_sch`** | 20 symbols, 116 numbered pads, 22 nets by hand; no parity guarantee; the traps in §2.1 fail *silently or as load errors* | rejected |

Known KiCad 9 traps (each one observed in this repo; the fix is in the generator):

1. **`hierarchical_sheet_instances` is INVALID at top level in KiCad 9** → `kicad-cli sch erc`
   fails with "Failed to load schematic" (exit 3). Valid top-level fields: `sheet_instances`,
   `symbol_instances`. (Skill's own note: found at a cost of 8+ hours.)
2. Header must be `(version 20250114)`, `(generator "eeschema")`, `(generator_version "9.0")`.
3. **The `lib_symbols` cache cannot express `(extends …)`.** Derived library symbols
   (`Regulator_Linear:TPS7A0533PDBV` is one) carry no pins of their own — the parent's unit
   sub-symbols must be inlined, or the part silently has no pins and every pad of it shows as
   unconnected.
4. Embedded `lib_symbols` **still needs the library listed in `sym-lib-table`**, otherwise ERC
   emits `lib_symbol_issues` (v0 needed a real `balloon_flight.kicad_sym`).
5. **Footprint fields must carry a library nickname present in `fp-lib-table`**, otherwise ERC
   emits one `footprint_link_issues` warning per symbol (first pass: 20 of them). v0 exports the
   PCB's own footprints into `balloon_flight.pretty` so the link is real.
6. **A rail with no power-output pin on it → `power_pin_not_driven` ERROR.** Fix with
   `power:PWR_FLAG` (2 fitted here: GND and VCAP). Do **not** flag a rail that already has a
   real `power_out` pin — that yields a `power_out`/`power_out` `pin_to_pin` ERROR (cost one
   iteration on +3V3, driven by the LDO's OUT pin).
7. **`kicad-cli sch erc` exits 0 even when it reports violations.** A real gate must use
   `--exit-code-violations`; "exit 0" alone only proves the file *parsed*.
8. Netlist export prefixes local-label nets with the sheet path (`/EN` vs PCB `EN`) — normalise
   before comparing.
9. Every netless pad needs an explicit `(no_connect)` in the schematic, or ERC reports
   `pin_not_connected`.
10. KiCad notes "annotation errors" on netlist export because designators inherited verbatim
    from the PCB (`SOLAR`, `R_LED`, `C_CAP`, `R_PD`, `R_DIV1`) do not end in a digit. Cosmetic;
    refs are kept verbatim because the reference designators are part of the PCB truth.

---

## 3. Symbol strategy for the 20 footprints

20 footprints → **15 unique footprint patterns → 17 distinct symbols** (14 part symbols + 3
power symbols: `power:+3V3`, `power:GND`, `power:PWR_FLAG`). **One custom symbol is needed; the
connector-based module workaround from the skill is not needed for any part on this board**,
because KiCad v9 carries real module symbols for all three modules.

| ref | value | PCB footprint | schematic symbol | source |
|---|---|---|---|---|
| U1 | ESP32-C3-WROOM-02 | `ESP32-C3-WROOM-02` | `RF_Module:ESP32-C3-WROOM-02` | KiCad v9 lib (module-style symbol exists) |
| U2 | LR2021F33 | `HOPERF_RFM9XW_SMD` (16-pad) | **`balloon_flight:LR2021F33`** | **custom inline** — the only part absent from v9 libs |
| U3 | MAX-M10S | `ublox_MAX` (18-pad) | `RF_GPS:MAX-M10S` | KiCad v9 lib |
| U4 | TPS7A02 | `SOT-23-5` | `Regulator_Linear:TPS7A0533PDBV` | v9 lib, **derived symbol** (parent inlined; see trap 3) — part identity is question Q2 |
| U5 | BMP280 | `Bosch_LGA-8_2.5x2.5mm_P0.65mm_ClockwisePinNumbering` | `Sensor:BME280` | v9 lib, same LGA-8 pinout — naming question Q2 |
| C1, C2 | 10uF | `C_0603_1608Metric` | `Device:C` | v9 lib |
| C3, C4 | 100nF | `C_0402_1005Metric` | `Device:C` | v9 lib |
| C_CAP | 1F_5.5V | `CP_Radial_D10.0mm_P5.00mm` | `Device:C_Polarized` | v9 lib (the skill's `Device:CP` does not exist) |
| D1 | BAT54 | `D_SOD-123` | `Device:D_Schottky` | v9 lib (2-pin; `Diode:BAT54*` are 3-pin only) |
| LED1 | LED_RED | `LED_0603_1608Metric` | `Device:LED` | v9 lib |
| R_DIV1, R_DIV2 | 100k | `R_0402_1005Metric` | `Device:R` | v9 lib |
| R_LED | 330R | `R_0402_1005Metric` | `Device:R` | v9 lib |
| R_PD | 10k | `R_0402_1005Metric` | `Device:R` | v9 lib |
| J1 | Prog_Header | `PinHeader_1x06_P2.54mm_Vertical` | `Connector_Generic:Conn_01x06` | v9 lib |
| J2 | Debug_Header | `PinHeader_1x04_P2.54mm_Vertical` | `Connector_Generic:Conn_01x04` | v9 lib |
| SOLAR | Solar_In | `PinHeader_1x02_P2.54mm_Vertical` | `Connector_Generic:Conn_01x02` | v9 lib |
| ANT1 | U.FL | `U.FL_Molex_MCRF_73412-0110_Vertical` | `Connector:Conn_Coaxial` | v9 lib |

**Custom symbol (U2, the only one).** 16 pads, pin names taken from the RFM9xW reference pinout
cited in `PCB-S0-NETLIST-AUDIT.md` — **not** from the NiceRF 18-pin castellated map, which does
not line up with this footprint. Pads 7/11/15/16 are the unmodelled ones and are declared
no-connect with visible annotations. This mismatch is open question Q1.

---

## 4. Acceptance gates (all re-runnable, no prose)

| # | gate | command | pass condition | v0 result |
|---|---|---|---|---|
| 0 | **schematic LOADS** | `kicad-cli sch erc <sch>` | exit 0 (exit 3 = failed to load) | **exit 0** |
| 1 | **ERC clean** | `kicad-cli sch erc --exit-code-violations <sch>` | 0 errors; every warning classified | **0 errors, 1 warning** |
| 2 | **net parity, both ways** | `check_sch_gates.py` GATE 2 | schematic nets == PCB nets, no orphans either side | **22 = 22, none either way** |
| 3 | **node parity, both ways** | `check_sch_gates.py` GATE 3 | per net, `(ref,pin)` sets equal | **84 = 84, 0 nets differ** |
| 4 | **netless pads declared** | `check_sch_gates.py` GATE 4 | 27 netless, each INTENTIONAL / DECLARED_GAP / unnamed-mechanical, **0 unclassified** | **9 + 7 + 11 = 27, 0 unclassified** |
| 5 | **every pad has a pin** | `build_flight_sch.py` (+ GATE 5) | exit 0; exit 2 = a pad has no symbol pin | **exit 0** |
| 6 | **provenance** | `build_flight_sch.py` | PCB sha256 == `FROZEN_SHA256` (else exit 3) | **match** |
| 7 | **determinism** | `check_sch_gates.py` GATE 6 | regenerate twice → byte-identical `sha256` | **identical** |

One command runs the whole suite (exit 0 = all pass):

```bash
python3 tracker/hardware/schematics/flight_board/check_sch_gates.py
```

Classification of the single warning, for the record: `pin_to_pin` — "Pins of type
Bidirectional and Power output are connected", i.e. the `PWR_FLAG` that drives GND plus the
BME280's `SDO` address pin tied to GND. It is an unavoidable consequence of a correctly drawn
GND rail on this board (the SDO→GND tie is real PCB truth), not a schematic defect. Gate 1
therefore asserts **errors == 0** and requires each warning to be named; it does not assert a
vacuous "strict exit 0".

Netless / GAP traceability (GATE 4) reconciles 1:1 with `PCB-S0-NETLIST-AUDIT.md`: 9 unnamed
mechanical pads on U1, 7 INTENTIONAL rows, 11 GAP rows (4 HIGH, 1 LOW, 6 MEDIUM). The schematic
**declares** them (no-connect + on-sheet annotation); it does not resolve them — resolution is
PCB-S0b's, and any resolved row that adds or moves a part forces a re-freeze per §1.2.

---

## 5. Work breakdown and effort

### Already delivered by this card (v0)

Generator, library export, both filters, ERC to 0 errors, gate suite, plan: **≈5 worker-hours of
tool work** (three dispatches; the first two hit the 40-iteration cap). **$0 inference** — pure
script + `kicad-cli` work on the local host. Dispatch 4 added the deterministic-uuid fix, GATE 6
and the independent re-verification: **≈0.5 worker-hour** (one dispatch, same $0).

### Remaining for PCB-S5b

| step | work | estimate |
|---|---|---|
| B1 adjudicate the 11 GAP rows (datasheet rulings + operator answers) | script + operator | 2–3 h + operator |
| B2 if a GAP fix adds/moves a part → PCB re-freeze (placer → placement_guard → new sha256 → `FROZEN_SHA256` update) | script | 1–2 h |
| B3 confirm U2 16-pad pin map and U4/U5 part identity (Q1, Q2) | operator confirmation + edit | 1 h |
| B4 regenerate + re-run all 6 gates on the final board, attach evidence | script | 0.5–1 h |
| B5 mark ADR-028 Accepted; retire `SCHEMATIC-PLAN.md` (2026-08-05) | prose | 0.5 h |
| **total** | | **5–7.5 worker-hours** |

**Inference cost: $0** — every step above is deterministic tool work; no paid API call is
required (an LLM is needed only for the B5 prose, and B1's datasheet reading). **Operator time:
30–60 min**, answering the questions below. If B1's rulings turn out to require new parts, add
one more PCB re-freeze cycle (~2 h, plus component lead time).

### Human questions (max 5, each with a recommendation)

1. **U2 pin map (LR2021F33).** The board uses the 16-pad `HOPERF_RFM9xW_SMD` footprint; the
   NiceRF datasheet is an 18-pin castellated map that does not line up. The v0 symbol's pin names
   come from the RFM9xW reference pinout cited in the repo audit. Is pads 7/15 (unmodelled I/O)
   and 11/16 (probable GND tabs) correct? **Recommendation: treat 11 and 16 as GND tabs and tie
   them (EMC), declare 7/15 no-connect — this needs the fitted module's pin table page.**
2. **U4 / U5 identity.** U4's Value is `TPS7A02` while the v9 symbol used is
   `Regulator_Linear:TPS7A0533PDBV`; U5's Value is `BMP280` while the symbol is `Sensor:BME280`.
   Both are pin-compatible (the LDO's DBV order matches the nets the board already carries:
   IN=1←VCAP, GND=2, EN=3, NC=4, OUT=5→+3V3), but the *symbol* should name the fitted part.
   **Recommendation: fit and name TPS7A02 (BOM value) and BMP280 (or state BME280 if that is what
   is fitted); either is a one-line change, no re-freeze.**
3. **GPS antenna (U3.11 `RF_IN`, GAP HIGH).** The board has no GPS feed at all (only ANT1/U.FL
   for 2.4 GHz), so the receiver input is open. **Recommendation: add a U.FL or a patch feed and
   keep `RF_IN` as a real net; "accept no GPS reception" is the only $0 alternative, and it costs
   the flight its position source.**
4. **Floating logic inputs (U3.6 `V_BCKP`, U3.9 `RESET_N`, U3.15 `VIO_SEL`, U3.18 `SAFEBOOT_N`,
   U4.3 `EN`, U2.x).** The u-blox datasheet says tie `RESET_N` high, tie `V_BCKP` to +3V3, leave
   `VIO_SEL` open for 3.3 V I/O, leave `SAFEBOOT_N` open. **Recommendation: 10k pull-ups to +3V3
   for `RESET_N`, `EN`, `V_BCKP` in the board's existing 0402 pull-up style — this changes the
   PCB and therefore forces one re-freeze (B2).** Confirm the pull-up style/value.
5. **Reference designators.** KiCad flags `SOLAR`, `R_LED`, `C_CAP`, `R_PD`, `R_DIV1` as
   "annotation errors" because they do not end in a digit. **Recommendation: keep them verbatim**
   (they are the PCB's own designators, and the parity gates compare by ref); renaming would
   improve cosmetic KiCad hygiene at the cost of one more PCB/schematic divergence.

---

## 6. What this does NOT cover

- **Routing.** Out of scope; the routed board is a separate frozen artifact (`PCB-S1`).
- **Mechanical / enclosure.** None of the enclosure geometry, mounting or antenna keep-out is
  touched here.
- **Firmware pin changes.** The firmware is authoritative, not a deliverable; a firmware pin
  change is handled as a PCB mismatch (§1.3) and forces a re-freeze.
- **The other two ADR-028 variants** (S3-Future, C3+RP2040) — those are author-first and are the
  proper SKiDL use case; this plan covers only the C3 flight variant.
- **DRC / gerbers / JLCPCB ordering.** Untouched by the schematic work.
- **Resolving the 11 GAP rows.** The schematic declares them; PCB-S0b owns the rulings.
- **The GPS antenna hardware** (question 3) and any pull-up parts added by question 4.

## 7. What could NOT be verified in this card

- **U2's 16-pad pin map** against a vendor document — the custom symbol's pin *names* come from
  the repo's `PCB-S0-NETLIST-AUDIT.md` (an in-repo artifact), not from a NiceRF datasheet page.
- **U4 / U5 part identity** (question 2) — pin-compatibility was checked against the board's
  carried nets, not against a datasheet page for the specific orderable part.
- **The 11 GAP rows** remain open by design (PCB-S0b). v0 does not resolve them.
- **SKiDL's KiCad-9 writer was read, not run** — it is not installed in this environment. Its
  capability claim (§2) rests on the v2.3.0 source shipped in the pip tarball
  (`tools/kicad9/gen_schematic.py`, `sexp_schematic.py`), so the *comparison* is on feature
  surface, not on a head-to-head measurement.
- **The remaining `pin_to_pin` warning** is classified, not eliminated (§4); eliminating it would
  require misrepresenting the BME280's `SDO`→GND tie.
- **KiCad GUI rendering** was not inspected (headless environment): the gates prove the file
  parses, mirrors the netlist and passes ERC — they do not prove the sheet is *pretty*.
- **Push targets.** GitHub: `pr/adr-028-schematic-v0` pushed to
  `https://github.com/felixfelix-bot/balloon-fresh` (and the earlier
  `pr/pcb-s5a-schematic-plan` is up there too). **ngit: push FAILS** —
  `Error: no repo announcement event found at specified Nip19Coordinates. if you are the
  repository maintainer consider running 'ngit init' to create one`. Publishing this repo's
  branch to ngit therefore needs a maintainer-side `ngit init` (or an ngit-ready fork); it is
  not an artifact defect and cannot be fixed from inside this card.
- **Pad-coverage definition.** 125 PCB pads = 116 numbered + 9 unnamed mechanical pads (U1's
  library pads). Coverage is asserted over the 116 numbered pads; the 9 unnamed ones cannot be
  addressed by pin number and are declared + counted by GATE 4 (they are the case the audit
  itself marks "cannot be netted by construction"). No pad is silently dropped.
