"""TDD Gate 1 test for RP-1: Verify RP2040 firmware PKT line has 23 fields.

This test validates that the RP2040 firmware's PKT printf format string
produces exactly 23 comma-separated fields matching the harmonized PKT
line contract. It mirrors the C3 test (test_c3_pkt_format.py) but checks
the RP2040 source file.

RP-1 design: The RP2040 firmware uses a single emitPktLine() helper function
that contains the 23-field PKT printf format. Both CRC-ok and CRC-failed
packets call this same function with different arguments. This is cleaner
than having two separate format strings (as the C3 firmware does).

RP-1 additions: Verify:
  - M1: Boot banner contains FW_HASH=<sha>
  - M6: Non-resetting uint32 seq counter (seq counter not reset on phase change)
  - M3+M4+M5: 23-field PKT lines
  - M7: CRC-failed packets logged with RSSI
  - O4: CONFIG_START transition markers
"""

import re
import os
from tools.pkt_parser import parse_pkt_line, PKT_FIELDS

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RP2040_SOURCE = os.path.join(
    REPO_ROOT, "firmware", "rp2040", "src", "pkt_harmonized_rx.cpp"
)


def _extract_pkt_printf(source_text: str) -> str:
    """Extract the PKT printf format string from the source.

    The RP2040 firmware uses emitPktLine() which calls dualPrintf("PKT,...").
    We search for any function call containing a "PKT,..." string literal.
    """
    match = re.search(r'"PKT,([^"]*)"', source_text)
    if match:
        return "PKT," + match.group(1)
    return ""


def _count_format_specifiers(fmt: str) -> int:
    """Count printf-style format specifiers (excluding %%)."""
    specs = re.findall(r'%(?:\.\d+)?[0-9]*[lh]*[diouxXeEfFgGs]', fmt)
    return len(specs)


class TestRP2040PktFormat:
    """Verify RP2040 firmware PKT line matches the 23-field common format."""

    def test_source_file_exists(self):
        assert os.path.isfile(RP2040_SOURCE), f"RP2040 source not found: {RP2040_SOURCE}"

    def test_pkt_printf_has_23_fields(self):
        """The PKT printf format string must produce exactly 23 fields."""
        with open(RP2040_SOURCE) as f:
            source = f.read()

        fmt = _extract_pkt_printf(source)
        assert fmt, "No PKT printf format found in pkt_harmonized_rx.cpp"

        fmt_body = fmt[len("PKT,"):]
        num_commas = fmt_body.count(',')
        num_fields = num_commas + 1
        assert num_fields == 23, (
            f"RP2040 PKT line has {num_fields} fields, expected 23. "
            f"Format: {fmt}"
        )

    def test_pkt_printf_format_specifier_count(self):
        """The PKT printf format string must have 23 format specifiers.

        The RP2040 firmware uses a single emitPktLine() helper for all PKT
        lines (both CRC-ok and CRC-failed). The format string must have
        exactly 23 format specifiers.
        """
        with open(RP2040_SOURCE) as f:
            source = f.read()

        fmt = _extract_pkt_printf(source)
        assert fmt, "No PKT printf format found"

        num_specs = _count_format_specifiers(fmt)
        assert num_specs == 23, (
            f"PKT format has {num_specs} format specifiers, expected 23. "
            f"Format: {fmt}"
        )

    def test_pkt_line_parses_with_standard_parser(self):
        """A sample PKT line built from the RP2040 format must parse correctly."""
        sample = (
            "PKT,test-session,F2600-868,1,42,12345,-87,5,1,0,0,"
            "2440000000,FLRC,0,0,1,12,255,0,0,0,0,0,0"
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
        assert result['freq_hz'] == 2440000000
        assert result['mod'] == "FLRC"
        assert result['pkt_size'] == 255

    def test_empty_session_config_parses(self):
        """When no SESSION/CONFIG command received, session_id and config_id are empty."""
        sample = (
            "PKT,,,0,1,100,-80,0,1,0,0,"
            "2440000000,FLRC,0,0,1,12,255,0,0,0,0,0,0"
        )
        result = parse_pkt_line(sample)
        assert result is not None
        assert result['session_id'] == ""
        assert result['config_id'] == ""

    def test_config_start_marker_format(self):
        """CONFIG_START line must have 3 format specifiers: config_id, replicate, ts_ms."""
        with open(RP2040_SOURCE) as f:
            source = f.read()

        match = re.search(r'"CONFIG_START,([^"]*)"', source)
        assert match, "No CONFIG_START printf found in pkt_harmonized_rx.cpp"
        fmt = "CONFIG_START," + match.group(1)
        num_specs = _count_format_specifiers(fmt)
        assert num_specs == 3, (
            f"CONFIG_START format has {num_specs} specifiers, expected 3. "
            f"Format: {fmt}"
        )

    def test_fw_hash_in_boot_banner(self):
        """M1: Boot banner must contain FW_HASH=<sha>."""
        with open(RP2040_SOURCE) as f:
            source = f.read()

        assert "FW_HASH=" in source, (
            "Boot banner does not contain 'FW_HASH=' — M1 requirement not met"
        )

    def test_non_resetting_uint32_seq_counter(self):
        """M6: seq counter must be uint32 and NOT reset on phase change.

        The seq counter should:
        1. Be declared as uint32_t (not uint16_t)
        2. NOT be reset to 0 in the phase change handler (resetRxPhaseState or similar)
        3. Persist across phase transitions
        """
        with open(RP2040_SOURCE) as f:
            source = f.read()

        # Check that seq is declared as uint32_t
        seq_decl = re.search(r'(?:static\s+)?uint32_t\s+(?:pktSeq|seq|txSeq|rxSeq)\b', source)
        assert seq_decl, (
            "No uint32_t seq counter declaration found — M6 requires uint32 seq"
        )

        # Check that the seq counter is NOT reset in the phase reset function
        reset_func = re.search(
            r'(?:static\s+)?void\s+(?:resetRxPhaseState|resetPhaseState|resetState)\s*\([^)]*\)\s*\{([^}]*)\}',
            source, re.DOTALL
        )
        if reset_func:
            reset_body = reset_func.group(1)
            seq_var = seq_decl.group(0).split()[-1].rstrip(';')
            seq_reset = re.search(
                rf'\b{re.escape(seq_var)}\s*=\s*0\b', reset_body
            )
            assert not seq_reset, (
                f"Persistent seq counter '{seq_var}' is reset to 0 in "
                f"resetRxPhaseState — M6 requires non-resetting seq"
            )

    def test_pkt_all_fields_have_23_fields(self):
        """All PKT format strings (if multiple) must produce 23 fields."""
        with open(RP2040_SOURCE) as f:
            source = f.read()

        all_pkt_fmts = re.findall(r'"PKT,([^"]*)"', source)
        for fmt_body in all_pkt_fmts:
            num_commas = fmt_body.count(',')
            num_fields = num_commas + 1
            assert num_fields == 23, (
                f"PKT format has {num_fields} fields, expected 23: "
                f"PKT,{fmt_body[:80]}..."
            )

    def test_crc_failed_pkt_handler_exists(self):
        """M7: CRC-failed packet handler must exist and call emitPktLine.

        The RP2040 firmware uses a single emitPktLine() function for all PKT
        output. The CRC error handler must call emitPktLine with crc_ok=0
        and a RSSI value (not hardcoded to 0).
        """
        with open(RP2040_SOURCE) as f:
            source = f.read()

        # Find CRC error handler blocks — look for rxCrcErrors followed by emitPktLine
        # There should be at least one CRC error handler that calls emitPktLine
        crc_handler_pattern = r'rxCrcErrors\+\+.*?emitPktLine'
        assert re.search(crc_handler_pattern, source, re.DOTALL), (
            "CRC error handler (rxCrcErrors++) does not call emitPktLine — "
            "M7 requires CRC-failed packets to be logged as PKT lines"
        )

    def test_crc_failed_pkt_has_rssi(self):
        """M7: CRC-failed PKT must include RSSI (not hardcoded to 0).

        The CRC error handler should read RSSI before calling emitPktLine.
        Look for rfGetLoraRssi or rfGetFlrcRssi call before emitPktLine in
        the CRC error handler.
        """
        with open(RP2040_SOURCE) as f:
            source = f.read()

        # Find CRC error handler blocks that have RSSI reading before emitPktLine
        rssi_in_crc = re.search(
            r'rxCrcErrors\+\+.*?(?:rfGetLoraRssi|rfGetFlrcRssi).*?emitPktLine',
            source, re.DOTALL
        )
        assert rssi_in_crc, (
            "CRC error handler does not read RSSI before calling emitPktLine — "
            "M7 requires RSSI on CRC-failed packets"
        )

    def test_crc_failed_pkt_has_crc_ok_zero(self):
        """M7: CRC-failed PKT must pass crc_ok=0 to emitPktLine.

        The emitPktLine call in the CRC error handler must have 0 as the
        crc_ok argument (the 5th positional argument, after seq, ts_ms,
        rssi_dbm, snr_db). Look for `// crc_ok=0` comments in the source
        to identify CRC-failed calls.
        """
        with open(RP2040_SOURCE) as f:
            source = f.read()

        # The CRC-failed emitPktLine calls have `// crc_ok=0` comment
        crc_ok_zero_markers = re.findall(r'//\s*crc_ok=0', source)
        assert len(crc_ok_zero_markers) >= 2, (
            f"Expected at least 2 emitPktLine calls with crc_ok=0 comment "
            f"(hardware CRC fail + app CRC fail), found {len(crc_ok_zero_markers)}"
        )

    def test_crc_failed_pkt_sample_parses(self):
        """A sample CRC-failed PKT line must parse correctly."""
        sample = (
            "PKT,test-session,F2600-868,1,0,99999,-85,0,0,0,0,"
            "2440000000,LORA,7,812,5,12,255,0,0,0,0,0,0.0"
        )
        result = parse_pkt_line(sample)
        assert result is not None, "CRC-failed PKT line failed to parse"
        assert result['crc_ok'] == 0
        assert result['rssi_dbm'] == -85
        assert result['seq'] == 0

    def test_session_and_config_commands(self):
        """Verify SESSION and CONFIG command handlers exist in source."""
        with open(RP2040_SOURCE) as f:
            source = f.read()

        # SESSION command handler
        assert re.search(r'"SESSION\s', source) or re.search(r'strncmp.*"SESSION', source), (
            "No SESSION command handler found"
        )
        # CONFIG command handler
        assert re.search(r'"CONFIG\s', source) or re.search(r'strncmp.*"CONFIG', source), (
            "No CONFIG command handler found"
        )

    def test_session_id_config_id_replicate_storage(self):
        """Verify session_id, config_id, replicate variables are declared."""
        with open(RP2040_SOURCE) as f:
            source = f.read()

        assert "session_id" in source, "session_id not declared in source"
        assert "config_id" in source, "config_id not declared in source"
        assert "replicate" in source, "replicate not declared in source"