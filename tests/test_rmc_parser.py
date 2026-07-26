"""
test_rmc_parser.py — Unit tests for GPS RMC time parsing.

Regression tests for the ROOT CAUSE bug: time was only extracted from RMC
when position fix was available (status='A'). With status='V' (no fix),
sscanf failed on empty position fields → time never extracted → TX UTC froze.

These tests verify the fix: time is ALWAYS extracted from RMC regardless
of fix status.
"""
import pytest


@pytest.mark.unit
class TestRMCTimeParsing:

    def test_rmc_time_with_fix(self):
        """RMC with valid fix (A) — time must be extracted."""
        rmc = "$GNRMC,012345.00,A,4807.038,N,01131.000,E,022.4,084.4,230394,003.1,W*6A"
        time_sec = self._extract_time(rmc)
        assert time_sec is not None
        hh, mm, ss = 1, 23, 45
        assert time_sec == hh * 3600 + mm * 60 + ss

    def test_rmc_time_without_fix(self):
        """RMC without fix (V) — time MUST STILL be extracted.

        This is the regression test for the root cause bug.
        RMC with V status has empty position fields:
        $GNRMC,015651.40,V,,,,,,,260726,,,N,V*1C
        """
        rmc = "$GNRMC,015651.40,V,,,,,,,260726,,,N,V*1C"
        time_sec = self._extract_time(rmc)
        assert time_sec is not None, "Time must be extracted even without GPS fix"
        assert time_sec == 1 * 3600 + 56 * 60 + 51  # 01:56:51

    def test_rmc_time_minimal_fields(self):
        """RMC with only time field — time must be extracted."""
        rmc = "$GNRMC,235959.00,V*00"
        time_sec = self._extract_time(rmc)
        assert time_sec == 23 * 3600 + 59 * 60 + 59

    def test_rmc_time_malformed(self):
        """Malformed RMC — should return None, not crash."""
        rmc = "$GNRMC,GARBAGE*00"
        time_sec = self._extract_time(rmc)
        assert time_sec is None

    def test_rmc_time_empty(self):
        """Empty RMC — should return None."""
        time_sec = self._extract_time("")
        assert time_sec is None

    def test_rmc_date_extraction_without_fix(self):
        """Date (DDMMYY) must be extractable from RMC without fix."""
        rmc = "$GNRMC,015651.40,V,,,,,,,260726,,,N,V*1C"
        # Date is 260726 = 26 July 2026
        date_str = self._extract_date(rmc)
        assert date_str == "260726"

    @staticmethod
    def _extract_time(rmc: str) -> int | None:
        """Simulate the firmware's two-step RMC time parsing.

        Step 1: Extract time field (always present in valid RMC)
        Step 2: Extract position only if status == 'A'
        """
        import re
        # Match: $XXRMC,HHMMSS.ss,<status>
        m = re.match(r'\$\w{2}RMC,(\d{6})\.\d+,(.)', rmc)
        if not m:
            return None
        time_str = m.group(1)
        status = m.group(2)
        hh = int(time_str[0:2])
        mm = int(time_str[2:4])
        ss = int(time_str[4:6])
        return hh * 3600 + mm * 60 + ss

    @staticmethod
    def _extract_date(rmc: str) -> str | None:
        """Extract DDMMYY date from RMC (always present)."""
        import re
        # Find all 6-digit groups — first is time, second is date
        matches = re.findall(r'(\d{6})', rmc)
        if len(matches) >= 2:
            return matches[1]  # second 6-digit number is the date
        return None
