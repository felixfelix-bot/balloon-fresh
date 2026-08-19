"""Tests for session_id injection — HOST-3.

Generates and injects a unique session_id into capture sessions.
The session_id appears in SESSION_START headers, PKT lines, and is
sent to firmware via a SESSION command.
"""

import os
import uuid
from unittest.mock import MagicMock, patch

from tools.session_manager import (
    generate_session_id,
    format_session_start,
    inject_session_id_into_pkt,
    send_session_command,
)


class TestGenerateSessionId:
    def test_generates_uuid(self):
        """generate_session_id() returns a non-empty UUID string."""
        sid = generate_session_id()
        assert sid is not None
        assert len(sid) > 0
        # Must be a valid UUID4 string
        parsed = uuid.UUID(sid)
        assert parsed.version == 4

    def test_unique(self):
        """Two calls return different IDs."""
        sid1 = generate_session_id()
        sid2 = generate_session_id()
        assert sid1 != sid2


class TestFormatSessionStart:
    def test_session_start_header(self):
        """format_session_start() produces 'SESSION_START,<uuid>,<timestamp>\n'."""
        sid = generate_session_id()
        header = format_session_start(sid)
        assert header.startswith("SESSION_START,")
        assert header.endswith("\n")
        # Should contain the session_id
        assert sid in header
        # Should match: SESSION_START,<uuid>,<iso-timestamp>
        # Strip the trailing newline for parsing
        parts = header.rstrip("\n").split(",")
        assert parts[0] == "SESSION_START"
        assert parts[1] == sid
        # The third field should be an ISO timestamp
        assert len(parts) >= 3
        timestamp_str = ",".join(parts[2:])
        # Should look like an ISO timestamp (contains 'T' and timezone info)
        assert "T" in timestamp_str


class TestInjectSessionIdIntoPkt:
    def test_injection_into_logger(self):
        """session_id appears in PKT lines written by rx_range_logger.

        inject_session_id_into_pkt() replaces the session_id field (field 1
        after 'PKT,') in a PKT line with the generated session_id.
        """
        sid = generate_session_id()
        # A PKT line with an empty session_id (field 1)
        original_line = "PKT,,F2600-868,1,42,12345,-87,5,1,0,0,868000000,FLRC,0,0,1,10,64,0,0,0,0,0,0"
        injected = inject_session_id_into_pkt(original_line, sid)
        # The injected line should contain the session_id
        assert sid in injected
        # The injected line should still start with PKT,
        assert injected.startswith("PKT,")
        # The session_id should be in position 1 (after PKT,)
        parts = injected[4:].split(",")
        assert parts[0] == sid

    def test_injection_replaces_existing_session_id(self):
        """If the PKT line already has a session_id, it gets replaced."""
        sid = generate_session_id()
        original_line = "PKT,old-session,F2600-868,1,42,12345,-87,5,1,0,0,868000000,FLRC,0,0,1,10,64,0,0,0,0,0,0"
        injected = inject_session_id_into_pkt(original_line, sid)
        parts = injected[4:].split(",")
        assert parts[0] == sid
        assert parts[0] != "old-session"

    def test_non_pkt_line_unchanged(self):
        """Non-PKT lines should be returned unchanged."""
        sid = generate_session_id()
        line = "RANGE_RESULT_RX,rx=100,unique=95,per=5"
        result = inject_session_id_into_pkt(line, sid)
        assert result == line


class TestSendSessionCommand:
    """Test that send_session_command sends 'SESSION <id>' to firmware."""

    def test_sends_session_command_to_serial(self):
        """send_session_command writes 'SESSION <id>\\r\\n' to the serial port."""
        mock_serial = MagicMock()
        sid = "550e8400-e29b-41d4-a716-446655440000"
        send_session_command(mock_serial, sid)
        # Verify that write was called with the SESSION command
        mock_serial.write.assert_called_once()
        written_bytes = mock_serial.write.call_args[0][0]
        assert b"SESSION " in written_bytes
        assert sid.encode() in written_bytes
        # Should end with \r\n
        assert written_bytes.endswith(b"\r\n")

    def test_returns_true_on_success(self):
        """send_session_command returns True when write succeeds."""
        mock_serial = MagicMock()
        sid = generate_session_id()
        result = send_session_command(mock_serial, sid)
        assert result is True

    def test_returns_false_on_write_error(self):
        """send_session_command returns False when write fails."""
        mock_serial = MagicMock()
        mock_serial.write.side_effect = Exception("Port closed")
        sid = generate_session_id()
        result = send_session_command(mock_serial, sid)
        assert result is False

    def test_command_format_matches_firmware_parser(self):
        """The SESSION command format must match firmware's strncmp(cmd, 'SESSION ', 8) parser."""
        mock_serial = MagicMock()
        sid = "test-session-123"
        send_session_command(mock_serial, sid)
        written_bytes = mock_serial.write.call_args[0][0]
        # Firmware expects: "SESSION <id>\r\n"
        # strncmp checks first 8 chars = "SESSION "
        decoded = written_bytes.decode('utf-8', errors='replace')
        assert decoded.startswith("SESSION ")
        assert decoded.rstrip("\r\n") == f"SESSION {sid}"


class TestCaptureSweepSessionId:
    """Test that capture_sweep.py integrates session_id into its output."""

    def test_capture_sweep_imports_session_manager(self):
        """capture_sweep.py should import from session_manager."""
        import importlib
        import importlib.util
        import sys
        # Ensure tools dir is in path
        tools_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "tools")
        if tools_dir not in sys.path:
            sys.path.insert(0, tools_dir)
        # Import capture_sweep module
        spec = importlib.util.spec_from_file_location(
            "capture_sweep",
            os.path.join(tools_dir, "capture_sweep.py"),
        )
        mod = importlib.util.module_from_spec(spec)
        # capture_sweep has a __main__ guard so importing won't run main()
        spec.loader.exec_module(mod)
        # Check that session_manager functions are available
        assert hasattr(mod, 'generate_session_id') or hasattr(mod, 'session_manager')

    def test_capture_sweep_writes_session_header(self):
        """capture_sweep should write a SESSION_START header to its CSV output."""
        # Verify by checking the source code contains session_id integration
        sweep_path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            "tools", "capture_sweep.py",
        )
        with open(sweep_path, 'r') as f:
            source = f.read()
        assert "session_id" in source, "capture_sweep.py must reference session_id"
        assert "SESSION_START" in source or "format_session_start" in source, \
            "capture_sweep.py must write a SESSION_START header"
        assert "send_session_command" in source, \
            "capture_sweep.py must send SESSION command to firmware"

    def test_rx_range_logger_sends_session_command(self):
        """rx_range_logger should send SESSION command to firmware."""
        logger_path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            "tools", "rx_range_logger.py",
        )
        with open(logger_path, 'r') as f:
            source = f.read()
        assert "send_session_command" in source, \
            "rx_range_logger.py must call send_session_command"