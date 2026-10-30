# ADR-141 — Drill minimum is 0.20 mm, set by the fab, not by us

**Status:** Accepted (operator decision, 2026-10-30)
**Supersedes:** the 0.30 mm drill floor asserted in ADR-030 §"rules" and restated in ADR-126 §"via", to
the extent those records claim 0.30 mm is a *manufacturing* limit rather than a *self-imposed* one.

## Context

`kicad-cli pcb drc` on hub v10 reports **34 `drill_out_of_range` violations**, steady across every
routing attempt this session (unrouted, 4/9, 6/9, 7/9, 9/9 — the count never moved). They come from
existing footprints in the library, not from anything routed here: the board setup carries a 0.30 mm
minimum hole while the imported footprints contain 0.20 and 0.25 mm drills.

The operator was offered the choice directly:

> *"shrink holes to 0.30, or accept the fab's 0.20 and change our rule?"*
> **"accept the fabs 0.2 and change our rule"**

That is the right call, and the reason is the direction of the constraint. 0.30 mm was never a
fabricator requirement — it is a self-imposed floor that made our own library non-conforming and
generated 34 permanent violations that every subsequent DRC run has to be mentally subtracted. A
violation class that is permanently present and permanently benign teaches people to ignore DRC,
which is how a real violation gets missed.

## Decision

The board minimum hole is **0.20 mm**. It is a fabcapability, and JLCPCB's standard 4-layer process
supports it.

Consequences, stated so they cannot be quietly ignored later:

1. **0.20 mm and 0.25 mm drills are legal.** The 34 `drill_out_of_range` violations are a board-setup
   defect, not a copper defect, and disappear when `min_hole` is set to 0.20.
2. **This does not lower the copper rules.** Clearance stays 0.20 mm, track 0.20 mm, via diameter
   0.50 mm, hole-to-hole 0.25 mm, edge 0.50 mm. A drill hole being legal says nothing about the
   copper beside it.
3. **Via drill stays at 0.30 mm for anything routed by us.** Nothing we add needs to go below the
   process minimum just because it is now permitted. ADR-126's `0.50 / 0.25` via remains the routing
   default; the router's vias are 0.54 mm in this session precisely to keep the annular ring legal.
4. **The change lives in the `.kicad_pro`, not in this document.** A rule written only in an ADR is
   not a rule. `tracker/hardware/hub_board_v10_lora1280_7of9.kicad_pro` is now committed alongside the
   board so the design rules travel with it.

## Alternatives rejected

- **Shrink 34 holes to 0.30 mm.** Rejected: it edits library footprints to satisfy a rule we invented,
  and it risks the parts that actually want a 0.20 mm hole (fine-pitch connector pins, the LoRa1280's
  own castellations check out fine but others in the library are not this board's problem). Changing a
  hole is a mechanical change with a re-verification cost; changing a rule is one line.
- **Leave the rule and allow-list the class.** Rejected: the repo's own position on allow-lists (AGENTS
  §23) is that a class which is never legitimate must be fixed rather than excused — and the inverse
  applies here: a class that is always legitimate must not stay in the report.

## What would change the answer

A fabricator whose process minimum is above 0.20 mm. Then the *fab* becomes the constraint and the
holes are the thing to change — but that decision would be driven by a real process limit, quoted from
that fabricator, not by our own conservative default.

## How to verify

```
kicad-cli pcb drc --format json --severity-all --output /tmp/d.json <board>.kicad_pcb
python3 -c "import json,collections; d=json.load(open('/tmp/d.json')); \
print(collections.Counter(v['type'] for v in d['violations']))"
```
`drill_out_of_range` must reach 0 with the 0.20 mm minimum applied, and `clearance` /
`shorting_items` / `solder_mask_bridge` must not change.
