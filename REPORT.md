Task t_5a10f700 report

Implemented ADR-029 D3 amendment in docs/adr/029-dual-band-flight-board.md.
- Explicitly defines four external U.FL landing zones: GNSS L1, F33 sub-GHz ANT, F33 ANT-2G4, and SX1280.
- Clarifies the ESP32-S3 -1U Wi-Fi/BT U.FL is module-integrated and not counted in the four-zone amendment.
- Added a 55 x 45 mm monospace placement feasibility sketch with four non-overlapping 4x4 mm landing zones, 2 mm edge/keep-out envelope, 39x21 mm F33 envelope, and separate SX1280 island.
- Explicitly preserves the S3/Wi-Fi U.FL as the feed routed to the opposite end of the payload under §2(a); U4 SX1280 receives an independent feed.
- Updated §2(e) from three to four perimeter U.FL zones.

Verification: git diff --check passed; targeted content grep passed.
Commit: 2328635
Pushes observed: GitHub origin branch pr/v9-d3-four-ufl and ngit branch pr/v9-d3-four-ufl.
Caveat: the sketch is an envelope feasibility check, not a KiCad courtyard/edge DRC; ADR-030 deterministic placement gate remains required before routing.
