"""TDD Gate 1 test for C3-3 and C3-4: Verify C3 PKT line has 23 fields in the common format.

This test validates that the C3 firmware's PKT printf format string produces
exactly 23 comma-separated fields matching the harmonized PKT line contract.

It uses a regex to extract the printf format string from range_test.cpp,
then counts the format specifiers. It also validates that sample PKT lines
generated from the firmware's format would parse correctly through the
standard 23-field parser.

C3-4 additions: Verify CRC-failed packets produce a PKT line with crc_ok=0
and RSSI value.
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
        """The number of % format specifiers must match 23 fields (CRC-ok line).

        The CRC-ok (successful) PKT printf must have exactly 23 format specifiers.
        The CRC-failed PKT printf may have fewer specifiers because some fields
        are hardcoded (e.g., seq=0, snr=0, crc_ok=0, bit_err=0, bytes_bad=0).
        """
        with open(C3_SOURCE) as f:
            source = f.read()

        # Find ALL PKT printf format strings
        all_pkt_fmts = re.findall(r'printf\(\s*"PKT,([^"]*)"', source)
        assert len(all_pkt_fmts) >= 2, (
            f"Expected at least 2 PKT printf format strings (CRC-ok and CRC-failed), "
            f"found {len(all_pkt_fmts)}"
        )

        # At least one PKT printf must have 23 format specifiers (the CRC-ok line)
        # The CRC-failed line will have fewer because it hardcodes some fields
        crc_ok_specs = None
        crc_failed_specs = None
        for fmt_body in all_pkt_fmts:
            num_specs = _count_format_specifiers("PKT," + fmt_body)
            # The CRC-ok line has 23 specifiers (all fields are format args)
            # The CRC-failed line has fewer because seq, snr, crc_ok, bit_err,
            # bytes_bad are hardcoded as 0
            if num_specs == 23:
                crc_ok_specs = num_specs
            elif num_specs < 23:
                crc_failed_specs = num_specs

        assert crc_ok_specs == 23, (
            f"No CRC-ok PKT format with 23 format specifiers found. "
            f"All formats: {all_pkt_fmts}"
        )
        assert crc_failed_specs is not None, (
            "No CRC-failed PKT format found (expected one with <23 specifiers)"
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


class TestC3CrcFailedPackets:
    """C3-4/M7: Verify CRC-failed packets produce a PKT line with crc_ok=0."""

    def test_crc_failed_pkt_printf_exists(self):
        """Source must contain a CRC-failed PKT printf in the error handler."""
        with open(C3_SOURCE) as f:
            source = f.read()

        # The CRC-failed handler should be in the `state != RADIOLIB_ERR_NONE` block
        # and should contain a PKT printf with hardcoded crc_ok=0
        # Look for the pattern: rxCrcErrors followed by a PKT printf
        # The CRC-failed PKT printf has hardcoded 0 for crc_ok (field 8)
        # In the format string, the 8th field is at a fixed position
        all_pkt_fmts = re.findall(r'printf\(\s*"PKT,([^"]*)"', source)
        # The CRC-failed format has literal 0s for seq, snr, crc_ok, bit_err, bytes_bad
        # Pattern: ...,%u,0,%lu,%d,0,0,0,0,...  (seq=0 hardcoded, snr=0, crc_ok=0, bit_err=0, bytes_bad=0)
        crc_failed_found = False
        for fmt_body in all_pkt_fmts:
            # CRC-failed format has literal "0" in the snr position (field 7)
            # and "0" for crc_ok (field 8), bit_err (field 9), bytes_bad (field 10)
            # Check if the format has at least 3 consecutive hardcoded 0s
            # in the snr/crc_ok/bit_err/bytes_bad positions
            num_specs = _count_format_specifiers("PKT," + fmt_body)
            if num_specs < 23:
                # This is the CRC-failed format (has hardcoded fields)
                crc_failed_found = True
                break

        assert crc_failed_found, (
            "No CRC-failed PKT printf found (expected a format with <23 specifiers "
            "where crc_ok and other fields are hardcoded as 0)"
        )

    def test_crc_failed_pkt_has_23_fields(self):
        """CRC-failed PKT printf format must still produce 23 fields."""
        with open(C3_SOURCE) as f:
            source = f.read()

        all_pkt_fmts = re.findall(r'printf\(\s*"PKT,([^"]*)"', source)
        for fmt_body in all_pkt_fmts:
            num_commas = fmt_body.count(',')
            num_fields = num_commas + 1
            assert num_fields == 23, (
                f"PKT format has {num_fields} fields, expected 23: "
                f"PKT,{fmt_body[:80]}..."
            )

    def test_crc_failed_pkt_has_rssi(self):
        """CRC-failed PKT printf must include RSSI (field 6) as a format specifier."""
        with open(C3_SOURCE) as f:
            source = f.read()

        all_pkt_fmts = re.findall(r'printf\(\s*"PKT,([^"]*)"', source)
        # Find the CRC-failed format (fewer than 23 specifiers)
        for fmt_body in all_pkt_fmts:
            num_specs = _count_format_specifiers("PKT," + fmt_body)
            if num_specs < 23:
                # This is the CRC-failed format
                # RSSI is field 6 (0-indexed field 5). The format should have
                # a %d or similar signed int specifier in the RSSI position.
                # Split the format on commas to find field 6
                fields = fmt_body.split(',')
                assert len(fields) == 23, (
                    f"CRC-failed PKT format has {len(fields)} fields, expected 23"
                )
                # Field 5 (0-indexed) is rssi_dbm — should be a format specifier, not hardcoded
                rssi_field = fields[5].strip()
                assert '%' in rssi_field, (
                    f"CRC-failed PKT RSSI field is hardcoded '{rssi_field}', "
                    f"expected a format specifier (e.g., %d)"
                )
                return

        assert False, "No CRC-failed PKT format found"

    def test_crc_failed_pkt_has_crc_ok_zero(self):
        """CRC-failed PKT printf must hardcode crc_ok=0 (field 8)."""
        with open(C3_SOURCE) as f:
            source = f.read()

        all_pkt_fmts = re.findall(r'printf\(\s*"PKT,([^"]*)"', source)
        for fmt_body in all_pkt_fmts:
            num_specs = _count_format_specifiers("PKT," + fmt_body)
            if num_specs < 23:
                # This is the CRC-failed format
                fields = fmt_body.split(',')
                assert len(fields) == 23
                # Field 7 (0-indexed) is crc_ok — should be hardcoded as "0"
                crc_ok_field = fields[7].strip()
                assert crc_ok_field == '0', (
                    f"CRC-failed PKT crc_ok field is '{crc_ok_field}', expected '0'"
                )
                return

        assert False, "No CRC-failed PKT format found"

    def test_crc_failed_pkt_sample_parses(self):
        """A sample CRC-failed PKT line must parse correctly through the standard parser."""
        # CRC-failed line: seq=0, snr=0, crc_ok=0, bit_err=0, bytes_bad=0
        # GPS fields all 0, gps_hdop=0.0
        sample = (
            "PKT,test-session,F2600-868,1,0,99999,-85,0,0,0,0,"
            "868000000,LORA,7,125,5,22,50,0,0,0,0,0,0.0"
        )
        result = parse_pkt_line(sample)
        assert result is not None, "CRC-failed PKT line failed to parse"
        assert result['crc_ok'] == 0, f"crc_ok should be 0, got {result['crc_ok']}"
        assert result['rssi_dbm'] == -85, f"rssi_dbm should be -85, got {result['rssi_dbm']}"
        assert result['seq'] == 0, f"seq should be 0 (corrupt), got {result['seq']}"
        assert result['snr_db'] == 0, f"snr_db should be 0, got {result['snr_db']}"
        assert result['bit_err'] == 0
        assert result['bytes_bad'] == 0

    def test_crc_failed_handler_in_error_block(self):
        """The CRC-failed PKT printf must be inside the state != ERR_NONE error handler."""
        with open(C3_SOURCE) as f:
            source = f.read()

        # Look for the pattern: state != RADIOLIB_ERR_NONE ... rxCrcErrors ... PKT
        # This verifies the PKT printf is in the CRC error handler, not elsewhere
        # Find the error handler block
        error_block_pattern = r'state != RADIOLIB_ERR_NONE.*?rxCrcErrors.*?printf\s*\(\s*"PKT'
        assert re.search(error_block_pattern, source, re.DOTALL), (
            "CRC-failed PKT printf not found in the state != RADIOLIB_ERR_NONE error handler"
        )

    def test_crc_failed_handler_reads_rssi(self):
        """The CRC-failed handler must call radio->getRSSI() for the RSSI value."""
        with open(C3_SOURCE) as f:
            source = f.read()

        # The CRC error handler in the RX path contains rxCrcErrors and getRSSI
        # Find the block that has rxCrcErrors followed by getRSSI
        rssi_in_crc_handler = re.search(
            r'rxCrcErrors\+\+.*?getRSSI',
            source, re.DOTALL
        )
        assert rssi_in_crc_handler, (
            "CRC error handler (rxCrcErrors block) does not call radio->getRSSI() "
            "for RSSI value"
        )