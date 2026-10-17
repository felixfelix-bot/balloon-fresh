# Astra visual review

Served model: gpt-6-astra
Images: docs/fab/jlc-query/edge-launch-cross-section.png

1. **OVERLAP: Fails.** In View A, the red dashed reference line crosses “interface edge (routed)”; the vertical extension line at the slot mouth crosses the end of “tab outside 2.0 mm.” In View B, callout bubble **7** covers the lower third land/fillet.

2. **CLIPPING: Passes;** no text or graphic is visibly cut off by the image boundary or hidden beneath another block.

3. **LEGIBILITY: Passes;** the labels are readable at the supplied image size, notwithstanding the overlaps identified above.

4. **CONSISTENCY: Fails.**
   - At the right of View B, **“slot 0.9 mm” measures between the tab faces**, while **“tab 0.6 mm” measures between the slot faces**. The dimension labels and measured features are reversed.
   - View B note **10** claims the tab is “1.2 mm clear of the slot's side walls,” but the drawing shows no lateral slot walls. The illustrated 1.2 mm margins are between the outer lands and the tab edges, not between the tab and slot walls.
   - The header and “Committed geometry” row present **±0.10 mm** as part of committed geometry, whereas “Slot width tolerance” explicitly calls it an **assumption** awaiting confirmation. Its application to width alone versus both width and depth is also unclear.

5. **COMPLETENESS: Fails.** The lateral slot walls named in View B note 10 are not drawn or located by dimensions. The hub thickness is explicitly **“TODO(unverified)”**, leaving the wall thicknesses and fabrication geometry undefined.

6. **ARROW / DIMENSION CONVENTION: Fails.** The two vertical dimensions at the right of View B attach to the wrong feature boundaries, as described in check 4. The other dimension arrowheads are opposed and point toward their extension lines.

7. **TECHNICAL CORRECTNESS: Fails.**
   - Views A and B depict broad copper lands extending **4.0 mm along the internal slot faces**. The fabrication notes instead describe ordinary F.Cu/B.Cu lands, copper exposed by routing, and **no edge plating or plated slot barrel**. Routing a conventional PCB exposes copper edges; it does not create the broad internal-face copper lands shown. No construction that produces those lands is specified.
   - View A note 4 calculates **0.15 mm solder per face** from slot width minus the **0.6 mm FR4** tab thickness, without accounting for the separately specified copper thickness. This does not establish the finished solder gap.
   - View A shows a square-ended routed slot acting as a full-depth insertion stop, with no cutter radius or matching tab-end treatment. A routed blind end requires tool-radius geometry that can affect seating.

8. **TYPOS: Passes;** no definite misspelled word or incorrect unit symbol is visible.

### Actionable defect list

1. Move the View A “interface edge (routed)” label or interrupt its dashed reference line so the line does not cross the text.
2. Move “tab outside 2.0 mm” below the slot-mouth extension line’s endpoint, or shorten that extension line to clear the label.
3. Move View B callout **7** off the lower third land/fillet and add a leader identifying the intended feature.
4. Correct the two right-hand View B dimensions: attach **slot 0.9 mm** to the slot faces and **tab 0.6 mm** to the tab faces.
5. Correct View B note **10** to distinguish land-to-tab-edge margins from tab-to-slot-wall clearance; draw and dimension the lateral slot walls if that clearance is intended.
6. Mark **±0.10 mm** consistently as proposed/unconfirmed until approved, and state separately whether it applies to slot width, slot depth, or both.
7. Replace **“TODO(unverified)”** with a verified hub thickness and specify the remaining wall thicknesses before fabrication release.
8. Specify a manufacturable copper construction for the internal slot-face lands, consistent with the plating restrictions, or redraw the joint to show the actual routed copper-edge contact geometry.
9. Define whether the tab’s **0.6 mm** dimension is finished thickness or FR4-only thickness, include copper and finish in the stack-up, and recalculate the solder gaps accordingly.
10. Show and dimension the routed slot’s end radius and any matching tab-end relief; define the seating-depth datum using the actual contact geometry.

VERDICT: DEFECTS_PRESENT 10
