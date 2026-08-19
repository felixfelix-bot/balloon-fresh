"""TDD Gate 1 test for C3-3: Verify C3 PKT line has 23 fields in the common format.

This test validates that the C3 firmware's PKT printf format string produces
exactly 23 comma-separated fields matching the harmonized PKT line contract.

It uses a regex to extract the printf format string from range_test.cpp,
then counts the format specifiers. It also validates that sample PKT lines
generated from the firmware's format would parse correctly through the
standard 23-field parser.
"""

import re
import os
from tools.pkt_parser import parse_pkt_line, PKT_FIELDS

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
C3_SOURCE = os.path.join(REPO_ROOT, "mesh-stack", "flrc-bench-espidf", "main", "range_test.cpp")
C3_HEADER = os.path.join(REPO_ROOT, "mesh-stack", "flrc-bench-espidf", "main", "range_test.h")


def _extract_pkt_printf(source_text: str) -> str:
    """Extract the PKT printf format string from the source."""
    # Match printf("PKT,...  format strings
    match = re.search(r'printf\(\s*"PKT,([^"]*)"', source_text)
    if match:
        return "PKT," + match.group(1)
    return ""


def _count_format_specifiers(fmt: str) -> int:
    """Count printf-style format specifiers (excluding %%)."""
    # Match % followed by flags, width, precision, length, and a conversion char
    specs = re.findall(r'%(?:\.\d+)?[0-9]*[lh]*[diouxXeEfFgGs%]', fmt)
    # Filter out literal %%
    return sum(1 for s in specs if not s.endswith('%'))


class TestC3PktFormat:
    """Verify C3 firmware PKT line matches the 23-field common format."""

    def test_source_file_exists(self):
        assert os.path.isfile(C3_SOURCE), f"C3 source not found: {C3_SOURCE}"

    def test_pkt_printf_has_23_fields(self):
        """The PKT printf format string must produce exactly 23 fields."""
        with open(C3_SOURCE) as f:
            source = f.read()

        fmt = _extract_pkt_printf(source)
        assert fmt, "No PKT printf format found in range_test.cpp"

        # Count comma-separated format specifiers
        # The format string after "PKT," should have exactly 23 fields
        # Each field is separated by a comma
        # Count by splitting the format portion (after "PKT,") on commas
        # that are NOT inside format specifiers
        fmt_body = fmt[len("PKT,"):]
        # Count commas at the top level (not inside {...} or %... specifiers)
        # For printf, commas are literal field separators
        num_commas = fmt_body.count(',')
        num_fields = num_commas + 1  # n commas = n+1 fields
        assert num_fields == 23, (
            f"C3 PKT line has {num_fields} fields, expected 23. "
            f"Format: {fmt}"
        )

    def test_pkt_printf_format_specifier_count(self):
        """The number of % format specifiers must match 23 fields."""
        with open(C3_SOURCE) as f:
            source = f.read()

        fmt = _extract_pkt_printf(source)
        assert fmt, "No PKT printf format found in range_test.cpp"

        num_specs = _count_format_specifiers(fmt)
        assert num_specs == 23, (
            f"C3 PKT format has {num_specs} format specifiers, expected 23. "
            f"Format: {fmt}"
        )

    def test_pkt_line_parses_with_standard_parser(self):
        """A sample PKT line built from the C3 format must parse correctly."""
        # This is the canonical 23-field line that the C3 firmware should emit
        sample = (
            "PKT,test-session,F2600-868,1,42,12345,-87,5,1,0,0,"
            "868000000,FLRC,0,0,1,22,50,0,0,0,0,0,0"
        )
        result = parse_pkt_line(sample)
        assert result is not None, "23-field PKT line failed to parse"
        assert len(result) == 23
        assert result['session_id'] == "test-session"
        assert result['config_id'] == "F2600-868"
        assert result['replicate'] == 1
        assert result['seq'] == 42
        assert result['ts_ms'] == 12345
        assert result['rssi_dbm'] == -87
        assert result['snr_db'] == 5
        assert result['crc_ok'] == 1
        assert result['bit_err'] == 0
        assert result['bytes_bad'] == 0
        assert result['freq_hz'] == 868000000
        assert result['mod'] == "FLRC"
        assert result['pkt_size'] == 50

    def test_empty_session_config_parses(self):
        """When no SESSION/CONFIG command received, session_id and config_id are empty."""
        sample = (
            "PKT,,,0,1,100,-80,0,1,0,0,"
            "868000000,FLRC,0,0,1,22,50,0,0,0,0,0,0"
        )
        result = parse_pkt_line(sample)
        assert result is not None
        assert result['session_id'] == ""
        assert result['config_id'] == ""

    def test_config_start_marker_format(self):
        """CONFIG_START line must have 4 fields: config_id, replicate, ts_ms."""
        with open(C3_SOURCE) as f:
            source = f.read()

        # Look for CONFIG_START printf
        match = re.search(r'printf\(\s*"CONFIG_START,([^"]*)"', source)
        assert match, "No CONFIG_START printf found in range_test.cpp"
        fmt = "CONFIG_START," + match.group(1)
        # Count format specifiers (should be 3: config_id, replicate, ts_ms)
        num_specs = _count_format_specifiers(fmt)
        assert num_specs == 3, (
            f"CONFIG_START format has {num_specs} specifiers, expected 3. "
            f"Format: {fmt}"
        )

    def test_session_id_storage_in_header(self):
        """range_test.h must declare session_id, config_id, replicate storage."""
        with open(C3_HEADER) as f:
            header = f.read()

        assert "session_id" in header, "session_id not declared in range_test.h"
        assert "config_id" in header, "config_id not declared in range_test.h"
        assert "replicate" in header, "replicate not declared in range_test.h"

    def test_no_old_20_field_format_remains(self):
        """Ensure the old 20-field PKT format is gone from the source."""
        with open(C3_SOURCE) as f:
            source = f.read()

        # The old format had loopCount, curWinId, curWin.name as first 3 fields
        # after PKT — look for the old printf pattern with loopCount
        old_pattern = r'printf\(\s*"PKT,[^"]*loopCount'
        assert not re.search(old_pattern, source), (
            "Old 20-field PKT format with loopCount still present in range_test.cpp"
        )

    def test_old_pkt_field_count_not_20(self):
        """Ensure no PKT printf produces 20 fields (the old count)."""
        with open(C3_SOURCE) as f:
            source = f.read()

        # Find ALL PKT printf format strings
        all_pkt_fmts = re.findall(r'printf\(\s*"PKT,([^"]*)"', source)
        for fmt_body in all_pkt_fmts:
            num_commas = fmt_body.count(',')
            num_fields = num_commas + 1
            assert num_fields == 23, (
                f"Found PKT format with {num_fields} fields (expected 23): "
                f"PKT,{fmt_body[:80]}..."
            )