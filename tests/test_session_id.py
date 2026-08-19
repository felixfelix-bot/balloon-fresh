"""Tests for session_id injection — HOST-3.

Generates and injects a unique session_id into capture sessions.
The session_id appears in SESSION_START headers and PKT lines.
"""

import re
import uuid
from tools.session_manager import (
    generate_session_id,
    format_session_start,
    inject_session_id_into_pkt,
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
        """format_session_start() produces 'SESSION_START,<uuid>,<timestamp>\\n'."""
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