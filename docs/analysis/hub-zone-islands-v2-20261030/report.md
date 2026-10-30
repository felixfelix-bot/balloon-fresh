# Hub zone islands v2 — INCOMPLETE DRAFT

Recovery savepoint. The inventory and validation JSON in this commit are historical,
unverified intermediate outputs, NOT legal-stitch evidence. In particular the old
candidate search used 0.20 mm instead of 0.50 mm for copper-to-edge clearance,
accepted any different component rather than the designated main component, and
ranked incomplete clearance measurements. Validation compared counts rather than
violation identities. These claims must not be used for fabrication or routing.

Source board remains read-only: `tracker/hardware/hub_board_v10_lora1280_7of9.kicad_pcb`,
SHA256 `732bfe889020b3c957fb778f1c30f2a84a3e96171cec37c1fa51dae58a9c6561`.
No board change is part of this work. Recovery found no running inventory or
KiCad process. Existing scratch evidence is preserved outside the deliverable.

Pending: correctness fixes, refreshed native DRC identity comparisons, tests and
coverage, final report. No island is waived as intentionally floating.
