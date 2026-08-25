#!/usr/bin/env python3
"""test_rf_experiment_design.py — TDD tests for the RF-EXPERIMENT-DESIGN-ANALYSIS.md update.

Task 12 of the guard-time/config/CVM plan: update the consultant's experiment
design analysis (docs/RF-EXPERIMENT-DESIGN-ANALYSIS.md) to reflect the user's
decisions:

1. FLRC-2600: KEEP (high data rate is the mission goal).
2. Packet count: KEEP 10 (reducing tries doesn't save much time).
3. Payload size: MAX (511B FLRC, 255B LoRa — worst-case sensitivity).
4. Guard time: REDUCE (both machines online = NTP within 1s).
5. CVM: INTEGRATE as an optional layer (fixed-schedule fallback).
6. 70 km extension (Madeira-Porto Santo inter-island mission range).

RED phase: these tests are written BEFORE the doc is updated. They should
FAIL against the current doc.

Run:  python3 -m pytest tools/test_rf_experiment_design.py -v
"""

from __future__ import annotations

import pathlib
import unittest

# Doc is four levels up from tools/ (tools/ -> e80-stm32-bench/ -> firmware/ -> repo root)
DOC = pathlib.Path(__file__).resolve().parent.parent.parent.parent / "docs" / "RF-EXPERIMENT-DESIGN-ANALYSIS.md"


def _read_doc() -> str:
    assert DOC.exists(), f"RF-EXPERIMENT-DESIGN-ANALYSIS.md not found at {DOC}"
    return DOC.read_text()


class TestUserDecisionsSection(unittest.TestCase):
    """The doc must have a User Decisions section recording the user's choices."""

    @classmethod
    def setUpClass(cls):
        cls.doc = _read_doc()

    def test_user_decisions_section_present(self):
        self.assertIn("User Decisions", self.doc,
                      "doc should have a User Decisions section")

    def test_flrc2600_keep(self):
        self.assertIn("FLRC-2600", self.doc)
        self.assertIn("KEEP", self.doc,
                      "doc should record FLRC-2600: KEEP")

    def test_packet_count_keep_10(self):
        self.assertIn("10", self.doc,
                      "doc should record packet count: KEEP 10")

    def test_max_payload(self):
        self.assertIn("511", self.doc,
                      "doc should record max payload (511B FLRC)")
        self.assertIn("255", self.doc,
                      "doc should record max payload (255B LoRa)")

    def test_guard_reduce(self):
        self.assertIn("guard", self.doc,
                      "doc should record guard time: REDUCE")

    def test_cvm_optional(self):
        self.assertIn("CVM", self.doc,
                      "doc should record CVM: INTEGRATE (optional layer)")

    def test_70km_extension(self):
        self.assertIn("70 km", self.doc,
                      "doc should record the 70 km extension")


if __name__ == "__main__":
    unittest.main(verbosity=2)
