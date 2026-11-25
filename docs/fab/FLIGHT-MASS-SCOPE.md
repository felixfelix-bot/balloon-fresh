# Next-iteration minimum relay: area-first mass reduction

Status: operator-approved scope; SOON. Not a routed board or fabrication approval.

## Integration, not a competing revision

Extend [V11-DESIGN-SPEC.md](V11-DESIGN-SPEC.md) and reconcile with
[existing v11 layout PR #577](https://github.com/felixfelix-bot/balloon-fresh/pull/577)
before modifying hardware. Preserve the delivered v10 and full-feature variant.
The existing spec adds an MCP23017 for U_C. That requirement does not carry into
the minimum relay when U_C is removed: retain an expander only if other retained
functions need it. Do not copy the full-feature component additions blindly.
The spec's historical 'no v11 board exists' line is not current-state evidence;
inspect the open layout branch before selecting the implementation base.

## Measured baseline and unknowns

Builder measurements: partially populated hub 27.05 g; with F33 31.05 g.
Difference 4.00 g assumes nothing else changed. Neither is bare-PCB mass or
complete flight mass. Receiver, solar assembly, antennas, storage, tracking,
wiring and suspension must be itemized separately.
Delivered thickness and exact manufactured board source remain unverified.
72 x 80 x 1.6 mm versus 50 x 60 x 0.8 mm is an illustration, not a proven fit
or achieved saving. No new dimension or total mass is frozen by this brief.

## Keep, remove, investigate

- Keep F33 LR2021 TX, one low-power LR2021 RX, ESP32 and necessary power circuitry.
- Minimum variant: remove U_C and SX1280 footprints AND dedicated routing reservations.
  Full-feature variants and historical files remain preserved.
- Verify both module footprints against vendor drawings and physical samples;
  the reported small-module mismatch must close before placement sign-off.
- Replace flight-carried programming header with test pads and a reusable fixture;
  prove access to programming, boot/reset and ground before deleting the header.
- Evaluate soldered power leads with strain relief instead of a permanent header.
- Remove nonessential mounting/tooling margins only after assigning structural loads.
- Retain GNSS tracking and release hardware wherever flight requirements demand them.
- Size storage for TX bursts, cloud intervals and restart hysteresis BEFORE shrinking
  C_CAP1/C_CAP2 reservations. Do not equate an empty footprint with unnecessary circuitry.

## Candidate comparisons and hard gates

Four layers around 0.8 mm is the first candidate, NOT an accepted stackup.
Check F33 support, connector loads, suspension and wing socket/tab mating at each
candidate thickness; include any stiffeners, wires and strain relief in mass totals.
Compare single-sided and two-sided placement using actual module dimensions,
antenna keepouts, underside restrictions and through-hole exclusion areas.
Keep decoupling local and regulator current loops compact. Preserve RF ground
returns and check F33-to-receiver desensitization; area wins cannot waive these.
Compare two layers only against a measured compact four-layer candidate with the
same functions, design rules and mechanical requirements. Do not discard planes
merely because their trace count is low.

## Execution sequence / acceptance evidence

1. Pin source SHA and distinguish delivered assembly archive from next-iteration CAD.
2. Measure outline, thickness, per-layer track lengths/nets and filled copper areas;
   report unverified manufacturing inputs separately, not as measured facts.
3. Produce annotated keep/optional/remove layout plus netlist-derived removal list.
4. Correct and verify module lands; produce compact single-/double-sided candidates.
   Report area per side, reservations, mechanical envelope and estimated mass by item.
5. Independently review power/RF/mechanical trade-offs; operator placement sign-off
   BEFORE routing. No weakened clearance rules or hidden pin-map changes.
6. Route the accepted candidate, refill zones, run native KiCad DRC and connectivity
   checks, and verify firmware pin mapping and fabrication exports against that SHA.
7. Publish reviewed evidence and merge to default before claiming an iteration complete.

Open measurements: delivered PCB thickness; small receiver exact SKU/pad geometry;
complete solar-wing mass; connector masses; assembly load/support and mating tolerances.
Missing measurements block relevant qualification, not the read-only audit above.
This brief authorizes no purchase, flight, or modification of the arrived boards.
