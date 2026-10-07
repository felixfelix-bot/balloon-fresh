# F33 land-pattern verification — repo footprint vs vendor pad file + datasheet drawing

**Card:** kanban `balloon:t_751620cb` (PCB-F33) · **Tier:** recon / measurement (read-only verification)
**Module:** NiceRF LoRa2021F33-2G4 (LR2021 + 2 W PA + TCXO, 39 × 21 mm, 18-pin castellated)
**Verdict: FAIL — the repo land pattern is NOT the manufacturer's land pattern. 0 of 18 pads coincide.**

---

## 1. Answer

The vendor pad file and the datasheet drawing agree with each other to better than 0.03 %.
The KiCad footprint used by the F33 boards agrees with **neither**:

| parameter | vendor pad file | datasheet p.8 | repo `LoRa2021F33_2G4.kicad_mod` | verdict |
|---|---|---|---|---|
| package L × W | 39.0 × 21.0 mm (derived, see §3.2) | 39.00 ± 0.5 / 21.00 ± 0.5 | 39 × 21 | MATCH |
| pads | 18, named 1…18 | 18 pins | 18 | MATCH |
| pads per side | 9 | 9 | 9 | MATCH |
| **pad pitch** | **3.9289 mm** (max dev 0.0000) | **3.93 ± 0.1** | **2.0 mm** | **MISMATCH 1.93 mm** |
| **pad rows sit on** | the two **39 mm edges** (row separation 21.0000 mm = module width) | 21.00 = module width | the two **21 mm ends** (pad `x = ±19.5`, rows 39 mm apart) | **MISMATCH — pattern rotated 90°** |
| **pad centre → module end** | **3.7844 mm** | **3.78 ± 0.1** | **0.0 mm** (pad centre sits exactly on the 39 mm end) | **MISMATCH 3.78 mm** |
| pad land size | not encoded in the pad records (see §7) | 3.00 / 3.30 / 0.80 callouts unattributed in this run | 2.0 × 1.0 mm | **UNVERIFIED** |

Quantified against the shipped board instance (`tracker/hardware/hub_board_f33.kicad_pcb`,
`custom:LoRa2021F33_2G4` @ line 89):

* pads coincident with a vendor pad (≤ 0.05 mm): **0 of 18**
* best case (nearest) misalignment: **4.071 mm** — worst: **10.226 mm**

So every one of the 18 module castellations lands off-metal, in the worst case 10 mm away.

## 2. Impact

* `hub_board_f33.kicad_pcb`, `tracker/hardware/gerbers_f33/*` and
  `tracker/hardware/hub_board_f33_jlcpcb.zip` were all generated from the wrong land pattern and
  are **not assemblable** with the F33 module as drawn.
* Any JLC/assembly quote built from that CPL (`tracker/hardware/gerbers_f33/pos_f33.csv`) is
  quoting an invalid design.
* The error is not a DRC-detectable one: the footprint is self-consistent (correct body outline,
  correct pad count, correct `U2` reference), so ERC/DRC/net-parity all pass. It can only be
  caught by comparing against the vendor land data — which is what this card did.
* Root cause: the footprint was authored from an *assumption*, not from the vendor material.
  `tracker/hardware/footprints/nicerf-lora2021f33-2g4.json` records
  `"pin_pitch_mm": 2.0`, `"pin_offset_from_edge_mm": 1.5`,
  `"pin1_marker": "none visible — orientation by pad position"`.
  The vendor's own land file has been in-tree the whole time at
  `docs/f33-module/materials/LORA2021F33-2G4 footprint_pads.pcb` and was never used as the source
  of truth.

## 3. Source A — the vendor pad file (authoritative)

`docs/f33-module/materials/LORA2021F33-2G4 footprint_pads.pcb`, 90 821 bytes.
It is an **Altium-format binary PCB document**, not KiCad and not text: OLE-ish header, the
string `<Romansim Stroke Font>`, layer names `Mechanical 1` / `Silkscreen Top`, object/style names
`STANDARDVIA` / `STDPROVIA`, and the module string `LORA2021F33-2G4`.

### 3.1 Record layout (byte-exact, derived in this run)

```
offset  size  field
0       4     int32 object tag      0x08435AD8 for every pad record
4       16    pad-name field        ASCII "1".."18" + NUL padding
20      16    x1,y1,x2,y2 int32     pad centre; both pairs equal (centres only)
=> 36 bytes per record, 18 records contiguous, first tag at byte 7290 (last byte 7937)
```

> Earlier attempts on this card assumed a 32-byte name field (stride 36 from byte 7294). That is
> off by one record: the decode then loses the 9th pad of the lower row and invents a phantom pad
> at the origin. The layout above was found by scanning for the `0x08435AD8` tag followed by 18
> consecutive name fields reading exactly `1 … 18`, and is reproducible in one command (§8).

### 3.2 Scale (1 500 000 units/mm) — justified without assuming it

The vendor file does **not** encode the body outline: an exact-value scan for the ±19.5 / ±10.5 mm
corner values returns 0 hits. The scale is therefore pinned by two *independent* agreements with
the drawing, one of which is scale-free:

* the file's pad pitch reads **3.9289 mm** ↔ drawing callout **3.93 ± 0.1 mm**;
* the file's pad-row separation reads **21.0000 mm**, which is exactly the module width
  (castellated pads are centred on the module edge), ↔ drawing callout **21.00 mm**;
* scale-free ratio test — file pitch/row-separation = **0.18709** vs drawing 3.93/21.00 =
  **0.18714** → the assumed mm/unit is consistent to **0.028 %**.

### 3.3 Decoded pads

| row | pads stored | x centres (mm) |
|---|---|---|
| y = −10.5000 | 8 | −11.7867, −7.8578, −3.9289, 0.0000, +3.9289, +7.8578, +11.7867, +15.7156 |
| y = +10.5000 | 9 | −15.7156, −11.7867, −7.8578, −3.9289, −0.0000, +3.9289, +7.8578, +11.7867, +15.7156 |
| pad 18 | 1 | coordinate field stored as (0, 0) |

Pad 18 is the only record whose coordinate field is zeroed in the file. It is placed by ring
closure: the pad naming runs around the perimeter (lower row left→right = 18, 1…8; upper row
right→left = 9…17), so the single unoccupied slot is (−15.7156, −10.5000) — which also puts
pin 18 (IRQ) next to pin 1 (VCC), and puts the two RF pins 9 (ANT) / 10 (ANT-2G4) adjacent at the
same end, consistent with the p.7 pin table. Ring closure is independently forced by the
arithmetic below.

### 3.4 Internal arithmetic

```
2 × 3.7844 mm (edge → first pad)  +  8 × 3.9289 mm (pitch)  =  39.0000 mm  =  module length
```

The pad array closes exactly on the 39.00 mm module edge. No other reading of the file does.

## 4. Source B — datasheet §9 "Mechanism Dimension (Unit: mm)", page 8

Re-OCR'd in this run (`tesseract --psm 11` on a 9× render). Callouts found, with position:

| callout | position on the drawing | attribution |
|---|---|---|
| 3.78 +0.1 | top-left of the pad view | module edge → first pad centre ✔ matches vendor file (3.7844) |
| 3.93 +0.1 | top of the pad view | pad-to-pad pitch ✔ matches vendor file (3.9289) |
| 0.80 +0.1 | top-right of the pad view | pad protrusion beyond the module outline |
| 39.00 ±0.5 | below the pad view | module length ✔ |
| 21.00 ±0.5 | beside the pad view | module width ✔ (see limits, §7) |
| 6.09 +0.1 | centre of the pad view | not attributed — raster drawing, no image read (§7) |
| 3.00 +0.1 (×2) | pad-view centre and top-right view | not attributed — candidate: land length along the row |
| 4.32 +0.1 | lower centre of the pad view | cannot be the pitch (4.32 > 3.93) |
| 5.00 +0.1 (×2) | bottom of the right view | not attributed |
| 3.30 +0.1 | bottom-right of the right view | not attributed — candidate: land width |

The drawing on p.8 is composed of two views (pad/land view + module view). Three of its callouts
(3.78, 3.93, 39.00) match the vendor file's decoded geometry to 0.004 mm / 0.001 mm / 0.000 mm.

## 5. Subject — the repo footprint

All three copies are byte-identical in their pad geometry, and the shipped board uses the same:

| file | pads | pad size | body | pad centres |
|---|---|---|---|---|
| `tracker/hardware/hub_board_f33_jlcpcb/custom.pretty/LoRa2021F33_2G4.kicad_mod` | 18 | 2.0 × 1.0 | 39 × 21 | x = ±19.5, y = 9.0…−7.0 step 2.0 |
| `tracker/hardware/hub_board_diy/custom.pretty/LoRa2021F33_2G4.kicad_mod` | 18 | 2.0 × 1.0 | 39 × 21 | identical |
| `tracker/hardware/output/pcb-handoff/custom.pretty/LoRa2021F33_2G4.kicad_mod` | 18 | 2.0 × 1.0 | 39 × 21 | identical |
| `tracker/hardware/hub_board_f33.kicad_pcb` (instance) | 18 | 2.0 × 1.0 | — | identical |

## 6. Corrected land pattern (taken from the vendor pad file)

Pad centres in the vendor's own coordinate frame (module centred on the origin, 39 mm along x):

| pad | x (mm) | y (mm) | | pad | x (mm) | y (mm) |
|---|---|---|---|---|---|---|
| 1 | −11.7867 | −10.5000 | | 10 | +11.7867 | +10.5000 |
| 2 | −7.8578 | −10.5000 | | 11 | +7.8578 | +10.5000 |
| 3 | −3.9289 | −10.5000 | | 12 | +3.9289 | +10.5000 |
| 4 | 0.0000 | −10.5000 | | 13 | −0.0000 | +10.5000 |
| 5 | +3.9289 | −10.5000 | | 14 | −3.9289 | +10.5000 |
| 6 | +7.8578 | −10.5000 | | 15 | −7.8578 | +10.5000 |
| 7 | +11.7867 | −10.5000 | | 16 | −11.7867 | +10.5000 |
| 8 | +15.7156 | −10.5000 | | 17 | −15.7156 | +10.5000 |
| 9 | +15.7156 | +10.5000 | | 18 | −15.7156 | −10.5000 |

Pitch 3.9289 mm on both rows; rows at y = ±10.5000 mm; outermost pad centre 3.7844 mm from the
39 mm ends. Pad land size still to be confirmed — see §7.

## 7. Limits of this verification (read before fixing)

1. **Pad land size is not in the file.** The pad records store centres only (`x1 == x2`,
   `y1 == y2`); the Altium pad-style/primitive table that carries each pad's length × width was not
   located within this run's budget. The drawing's own land callouts (3.00 ×2, 3.30, 5.00 ×2, 6.09,
   0.80) could not be attributed to features either, because page 8 is a **raster image** and the
   vision lane was unavailable in this run (`vision_analyze` → HTTP 503 "all providers exhausted",
   twice). The physical constraint bounds it: land length along the row must be < pitch − creepage,
   i.e. ≲ 3.4 mm at 3.93 mm pitch.
2. **Pin-1 orientation is not encoded in the file.** Pad *names* and *positions* are exact as
   tabulated, but the file carries no body outline and no pin-1 marker, so whether the file's
   +y row maps to the drawing's upper or lower row is not proven — a vertical mirror is possible.
   Orientation anchor for the fix: pins 9 (ANT) and 10 (ANT-2G4) are adjacent pads at the same end
   of the two rows; pin 18 (IRQ) sits next to pin 1 (VCC) at the other end.
3. **The 21.00 callout was not re-read by this run's OCR sweep** (a `d_21.png` crop from the
   earlier attempt exists in the scratch workspace). It is not load-bearing: the vendor file's own
   row separation (21.0000 mm) equals the module width, and the 39 × 21 mm package is recorded in
   the repo's own module metadata.
4. The bare-LoRa2021 footprint (`LoRa2021_Castellated.kicad_mod`, 19.81 × 14.98 mm, 1.29 mm pitch)
   is a **different module** and was not in scope here.

## 8. Reproduce

```bash
cd <scratch>/work
python3 f33_landpattern_verify.py          # prints the full comparison, writes the JSON below
# machine-readable evidence:
#   f33_landpattern_decode_v2.json
```

(The script now resolves the repo root from its own location — run it from the
repo, optionally with `--repo <tree>`. See the addendum in §10.)

Raw one-liner for the decode (no dependencies beyond the stdlib):

```bash
python3 - <<'EOF'
import struct, os
p=os.path.expanduser('~/repos/balloon-fresh/docs/f33-module/materials/LORA2021F33-2G4 footprint_pads.pcb')
d=open(p,'rb').read()
for k in range(18):
    o=7290+36*k
    x,y=struct.unpack_from('<ii',d,o+20)
    print(d[o+4:o+20].rstrip(b'\0').decode(), round(x/1.5e6,4), round(y/1.5e6,4))
EOF
```

## 9. Provenance

* Vendor material: `docs/f33-module/LoRa2021F33-2G4-materials.zip` → `LORA2021F33-2G4 footprint_pads.pcb`,
  90 821 bytes, SHA-256 `c66ea27c4409a3af58f1bfd967cddec60214d446d4b15f620f2eef82e86ee7ac`.
  This is the same blob already committed at `docs/f33-module/materials/`.
* Datasheet: `docs/f33-module/LoRa2021F33-2G4-datasheet-v1.1.pdf` (SHA-256 `98b7c3aeb36ee0f1c8ed58497f560065dfaf07a572eb551b4bf03901dacc73f0`), rev V1.1, §9 p.8, §7 p.6.
* Decoder/verifier: `docs/f33-module/tools/f33_landpattern_verify.py` (stdlib only), evidence JSON
  alongside it as `f33_landpattern_decode_v2.json`.
* Verification performed read-only on `balloon-fresh` @ the commit named in the card handoff.

---

## 10. ADDENDUM — 2026-10-07: verdict re-checked, fix landed, what is still stale

**Branch:** `fix/f33-landpattern` (base `github/main` `94c3c4d`). Nothing above is
rewritten: §1–§9 are the original card record and their numbers are reproduced
below unchanged.

### 10.1 Was the FAIL correct? — YES, and it is a REAL geometry error (case i)

Re-decoded the vendor file independently (`scripts/gen_f33_landpattern.py`,
stdlib only, same 36-byte record layout, tag `0x08435AD8`, first record at byte
7290, 1.5e6 units/mm) with the scale pinned by the same three agreements:
pitch 3.9289 mm ↔ callout 3.93 ±0.1; row separation 21.0000 mm = module width;
closure `2 × 3.7844 + 8 × 3.9289 = 39.0000 mm` = module length 39.00 ±0.5.
All nine self-checks pass, including `pad18_zeroed_in_file` and
`outer_pad_3.7844_from_end`.

Measured coincidence of each artifact against the vendor pad centres
(nearest-pad distance, ≤0.05 mm = coincident), using the identity signature the
`pcb-fab-readiness-gating` skill requires (pad count, pad bbox, pad-size
histogram, pad-number string):

| artifact | pads | pad-centre bbox | pad sizes | numbers | coincident | nearest | worst |
|---|---|---|---|---|---|---|---|
| all four artifacts **BEFORE** (pre-fix tree `d5a2e47^`) | 18 | 39.0000 × 16.0000 mm | 2 × 1 | 1..18 | **0/18** | **4.071 mm** | **10.226 mm** |
| the three `custom.pretty` copies **AFTER** | 18 | 31.4312 × 21.0000 mm | 2 × 1 | 1..18 | **18/18** | 0.000 mm | 0.000 mm |
| `hub_board_f33.kicad_pcb` (still stale) | 18 | 39.0000 × 16.0000 mm | 2 × 1 | 1..18 | **0/18** | 4.071 mm | 10.226 mm |

The 4.071 / 10.226 mm figures reproduce §1 exactly, from a different
implementation — so the original verdict stands: the pattern was rotated 90°
(pads on the two 21 mm ends) with a wrong pitch (2.0 mm vs 3.9289 mm). Pad
count and pad-number string matched all along, which is why no DRC/ERC gate
could see it.

### 10.2 A checker defect found on the way (case ii, secondary)

`docs/f33-module/tools/f33_landpattern_verify.py` hard-coded
`REPO = ~/repos/balloon-fresh`. That shared checkout was on
`feat/tracker-tx-tempcomp` on 2026-10-07, i.e. a branch that still carried the
pre-fix pattern, so **re-running the checker did not grade the branch under
test**. Fixed: the repo root is derived from the script's own location, with a
`--repo` override; the evidence JSON now stores repo-relative paths. The script
also now prints the four-part identity signature and grades the footprints and
the shipped board **separately** (a fixed footprint set does not make the stale
board orderable).

Reproduce both states:

```bash
python3 docs/f33-module/tools/f33_landpattern_verify.py            # AFTER (this branch)
git worktree add /tmp/bf-prefix --detach d5a2e47^
python3 docs/f33-module/tools/f33_landpattern_verify.py --repo /tmp/bf-prefix   # BEFORE
```

### 10.3 The authoritative source, and the one thing that is still UNVERIFIED

* **Pad centres — VERIFIED.** The vendor's own land file is in-tree and
  machine-readable: `docs/f33-module/materials/LORA2021F33-2G4 footprint_pads.pcb`
  (sha256 `c66ea27c4409a3af58f1bfd967cddec60214d446d4b15f620f2eef82e86ee7ac`).
  Datasheet §7's pin table is also text-extractable (`pdftotext`) and agrees on
  the 18 pins.
* **Pad LAND SIZE — STILL UNVERIFIED, and not guessed.** §9 "Mechanism
  Dimension" (p.8) is two embedded JPEGs with **no text layer**:
  `pdftotext -raw -f 8 -l 8 <pdf>` prints only the page header, and
  `pdfimages -list -f 8 -l 8 <pdf>` shows the two images. OCR with tesseract (a
  text extractor, not `vision_analyze`) reproduces §4's callouts —
  `3.78 / 3.93 / 0.80 / 3.00 ×2 / 6.09 / 5.00 ×2 / 4.32 / 39.00 / 9.00 / 3.30`
  — but their positions cannot be attributed to a feature without reading the
  drawing, so the emitted land size stays 2.0 × 1.0 mm and is marked
  `TODO(unverified)` in the footprint, in the generator and in this doc. A
  guessed land is worse than a flagged one, because it looks verified.

### 10.4 What was fixed, and how it stays fixed

* `scripts/gen_f33_landpattern.py` — **new**, the reproducible generator: decodes
  the vendor land file, refuses to emit anything if the file drifts (pinned
  sha256) or fails its self-checks, and writes the footprint with its provenance
  in the header. `--check` / `--verify-all` grade any copy against the vendor
  centres; `--install` refreshes every registered copy.
* `tracker/hardware/schematics/flight_board/build_flight_sch.py` (v9) — now
  **derives** the F33 footprint from that generator at generation time instead of
  copying a `custom.pretty` file, and **fails the build** if the emitted pads are
  not all on the vendor land pattern. Regeneration is byte-identical across two
  consecutive runs.
* The four committed footprint copies are now generator output (identical
  geometry; header/comment text normalised with the provenance block).
* Pad-centre geometry is unchanged from the `d5a2e47` correction — this work
  makes it reproducible and closes the remaining stale artifacts, it does not
  move a pad.

### 10.5 What is left stale, on purpose

`hub_board_f33.kicad_pcb`, `tracker/hardware/gerbers_f33/*`,
`hub_board_f33_jlcpcb.zip`, `pcb_handoff.zip`, `output/pcb-handoff.zip` and the
`gen_pcb.py` `gen_v2` generator that produces them are **superseded, not
deleted** — they are history and `gen_pcb.py` still reproduces the board. They
must not be ordered, quoted to a fab, or assembled. Full register, with hashes
and the pre-order checklist: `docs/f33-module/F33-SUPERSEDED-ARTIFACTS.md`.
A replacement F33 board is a **re-route** (placement + routing) from the
corrected footprint, not a re-score.

