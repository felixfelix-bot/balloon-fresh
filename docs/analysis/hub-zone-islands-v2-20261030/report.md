# Hub zone islands v2 — INCOMPLETE DRAFT

## Outcome and boundary

The recovered inventory was rerun, not restarted from a new hypothesis. **35 filled
zone islands**, **29 provisionally outside their net's designated main component**.
The independent graph gives **Σ(components−1) = 86 over 22 affected nets**, matching
native connectivity's 86 unconnected items. Refill is byte-identical. These are
measured counts, not proof that every inferred graph edge is correct.

**Stitchability is NOT established.** All 29 isolated-island candidate sites were
individually inserted as a 0.50/0.30 mm through via on fresh copies, refilled and
checked by native KiCad DRC. **25/29 introduced no new violation identities**;
4 introduced new identities. Baseline: 40 violations, 86 unconnected items.
After insertion: 25 copies had 85 unconnected items, 3 had 86, one had 84.
Count reduction alone does not prove the candidate reaches the designated main
component. `connectivity_proven` remains false for every arm. No combined-via
layout was validated; independently passing sites are not a batch approval.

Source: `tracker/hardware/hub_board_v10_lora1280_7of9.kicad_pcb`.
SHA256 before and after:
`732bfe889020b3c957fb778f1c30f2a84a3e96171cec37c1fa51dae58a9c6561`.
No source copper, placement, silkscreen or routing was modified.

| Net | Layer | Filled islands |
|---|---|---:|
| GND | F.Cu | 12 |
| GND | B.Cu | 18 |
| GND | In1.Cu | 1 |
| +3V3 | B.Cu | 3 |
| VSCAP | B.Cu | 1 |

`islands.json` gives every island's zone UUID/index, area, bounds, centroid,
component/pad membership, same-layer nearest copper and provisional candidate.
Main means most pads in the independent graph, with deterministic tie order;
it is a convention, not an electrical intent waiver.

## Correctness repairs and retained refutations

- Edge check now uses **0.50 mm**, not the erroneous 0.20 mm copper spacing.
- Candidate score considers edge, hard-copper, conservative hole clearance and
  landing on the **designated main component**, not merely any different component.
- Exact distance minima over modeled polygon unions replace the incomplete
  search-window `1e9` sentinel. No-net tracks/graphics and footprint graphics are
  conservative obstacles. Native DRC, not this approximate geometry, tests legality.
- Nearest-feature search checks every per-layer node rather than only the first.
- Graph mismatch with 86/22/native 86 aborts **before classification**.
- Fresh work paths must not exist: earlier evidence is never recursively deleted.
- Native comparison uses a multiset of rule/type/severity/description and sorted
  item UUID/descriptions, not violation counts. Added and removed identities are
  both retained in `native_validation.json`.
- USB_DN graphic copper in `GetDrawings()` is included. Omitting it previously
  yielded the false graph total 87.
- Historical `stitch_validation.json` and `stitch_verification.json` are retained
  **refuted intermediate evidence**, not current proof. Their 27/29 prediction
  agreement and candidate-success counts must not be quoted as legal stitches.
  `verify_stitchable.py` is retired and fails closed.
- The earlier DRC-record-index attribution was invalid because equivalent DRC
  runs can choose different unconnected pairs. Polygon enumeration avoids that
  identity assumption; native violation identity comparison is separate from
  unconnected-record indexing. Related predecessor: PR #379.

A failed sampled site means **no legal candidate found in this sample**, never
proven non-stitchable. The 0.10 mm candidate grid is not exhaustive.

## Intent evidence: no floating-copper waiver

ADR-136, `docs/adr/136-flight-wing-interface-two-land-and-routing-sequence.md:47–48`:

> - **pad 2 (`GND`)** — the wing has no ground plane to reference (ADR-134 removed it), so on the
>   flight build this land carries nothing. It stays on the hub as an unused pad.

`docs/fab/HUB-V9-ORDER-READINESS.md:71–74`:

> ### 2. GND wing-pad stitching (5 of the 10 unconnected items)
>
> `Pad 2 [GND] of J_W1 / J_W2 / J_W3` is unconnected **F.Cu ↔ B.Cu** (its own two layers), and the
> F.Cu pad is not reached by `Zone 'GND_PLANE_F.Cu'`.

The latter is a historical v9 readiness finding, not a measurement of this v10
source. “Unused pad” is not a statement that attached floating copper is intended.
Neither passage authorizes waiving floating copper. This report makes no intent
classification and changes no ADR.

## Reproduction

Requires system Python with pcbnew and Shapely 2, plus `kicad-cli` (this run used
KiCad 9 bindings). From the repository root, use NEW work directories each time:

```sh
D=docs/analysis/hub-zone-islands-v2-20261030
/usr/bin/python3 "$D/run_island_inventory.py" --repo "$PWD" \
  --work "$PWD/.zi2scratch/reproduce-inventory" --out "$D/islands.json"
/usr/bin/python3 "$D/validate_stitching.py" --repo "$PWD" \
  --work "$PWD/.zi2scratch/reproduce-native" \
  --inventory "$D/islands.json" --out "$D/native_validation.json"
/usr/bin/python3 -m unittest discover -s "$D" -p 'test_*.py'
sha256sum tracker/hardware/hub_board_v10_lora1280_7of9.kicad_pcb
```

Executed recovery directories: `.zi2scratch/recovered-inventory-1` and
`.zi2scratch/recovered-native-1`. The original `.island_work`, `.stitch_work` and
`.zi2scratch` evidence remains local, outside the tracked deliverable.

## Verification and open gates

- Inventory execution: exit 0; 35/29/86/22, unchanged source, refill byte no-op.
- Native single-via execution: exit 0; all 29 arms completed and checkpointed.
- Four regression tests pass: identity order independence, equal-count replacement
  detection, multiset duplicates, and inventory/native evidence invariants.
- **Coverage gate blocked:** `/usr/bin/python3 -m coverage --version` fails with
  `No module named coverage`. No ≥80% coverage is claimed; four tests do not
  establish sufficient geometry coverage. Cross-family review also pending.
- Post-refill native endpoint-to-main-component proof remains missing. All
  stitchability classifications therefore remain unverified.
- Graph geometry retains approximations (curves, holes/slots, fallback pad shapes,
  4 µm contact tolerance); agreement of global counts is not full topology proof.
- KiCad emitted `PCB_VIA::GetWidth called without a layer argument` warnings in
  inventory execution. Results are provisional, not a fabrication gate.

## Decisions

Publish as an **incomplete draft**, rather than call 25 candidates stitchable.
Evidence supports inventory counts and 29 native single-site experiments; it does
not support the stronger endpoint-connectivity and coverage claims. Reject
silently accepting the older count-only results or inferring impossibility from
four failed samples. Promotion requires native landing proof, sufficient test
coverage and independent review. No merge or board edit is authorized here.
