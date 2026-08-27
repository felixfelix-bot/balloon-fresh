"""Tests for session_id injection — HOST-3.

Tests the session_manager module: session_id generation, SESSION command
formatting, and CONFIG command formatting.
"""

from tools.session_manager import (
    generate_session_id,
    format_session_command,
    format_config_command,
)


class TestGenerateSessionId:
    def test_generate_returns_uuid_string(self):
        """generate_session_id() returns a string of length >= 8."""
        result = generate_session_id()
        assert isinstance(result, str)
        assert len(result) >= 8

    def test_generate_unique(self):
        """Two calls to generate_session_id() return different values."""
        a = generate_session_id()
        b = generate_session_id()
        assert a != b

    def test_generate_format(self):
        """Session_id matches YYYYMMDDHHMMSS-<8hex> format."""
        import re
        result = generate_session_id()
        # Format: 14-digit timestamp, dash, 8 hex chars
        assert re.match(r'^\d{14}-[0-9a-f]{8}$', result), f"Bad format: {result}"


class TestFormatSessionCommand:
    def test_format_session_command(self):
        """format_session_command returns 'SESSION <id>\\r\\n'."""
        result = format_session_command("abc-123")
        assert result == "SESSION abc-123\r\n"


class TestFormatConfigCommand:
    def test_format_config_command(self):
        """format_config_command returns 'CONFIG <id> <replicate>\\r\\n'."""
        result = format_config_command("F2600", 3)
        assert result == "CONFIG F2600 3\r\n"