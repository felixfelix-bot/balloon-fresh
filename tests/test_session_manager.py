"""Tests for session_manager create_session/persist_session — HOST-3.

Tests the create_session() and persist_session() functions, plus a
regression check on inject_session_id_into_pkt().
"""

import json

from tools.session_manager import (
    create_session,
    persist_session,
    inject_session_id_into_pkt,
)


class TestCreateSession:
    def test_session_creation(self):
        """create_session() returns a dict with session_id and start_time."""
        result = create_session()
        assert isinstance(result, dict)
        assert "session_id" in result
        assert isinstance(result["session_id"], str)
        assert len(result["session_id"]) > 0
        assert "start_time" in result
        assert isinstance(result["start_time"], str)
        # start_time should be an ISO8601 string (contains a 'T')
        assert "T" in result["start_time"]

    def test_session_creation_with_config(self):
        """create_session(config=...) stores the config dict."""
        cfg = {"config_id": "F2600", "replicate": 3}
        result = create_session(config=cfg)
        assert result["config"] == cfg

    def test_session_persistence(self, tmp_path):
        """create_session(output_dir=...) writes a JSON file with session_id and start_time."""
        result = create_session(output_dir=str(tmp_path))
        session_id = result["session_id"]
        expected_file = tmp_path / f"session_{session_id}.json"
        assert expected_file.exists()
        with open(expected_file) as f:
            data = json.load(f)
        assert data["session_id"] == session_id
        assert "start_time" in data


class TestPersistSession:
    def test_persist_session_writes_json(self, tmp_path):
        """persist_session() writes a pretty-printed JSON file."""
        metadata = {
            "session_id": "test-123",
            "start_time": "2026-08-20T14:30:00+00:00",
            "config": {"config_id": "F2600"},
        }
        filepath = tmp_path / "session_test-123.json"
        persist_session(metadata, str(filepath))
        assert filepath.exists()
        with open(filepath) as f:
            data = json.load(f)
        assert data == metadata
        # Verify pretty-printed (should contain newlines/indentation)
        raw = filepath.read_text()
        assert "\n" in raw  # pretty-printed JSON has newlines


class TestInjectSessionId:
    def test_session_id_injection(self):
        """inject_session_id_into_pkt replaces the session_id field in a PKT line."""
        line = "PKT,oldid,rest,of,line"
        result = inject_session_id_into_pkt(line, "newid")
        assert result == "PKT,newid,rest,of,line"

    def test_session_id_injection_longer_line(self):
        """inject works with a realistic 23-field PKT line."""
        line = (
            "PKT,oldsession,field2,field3,field4,field5,field6,field7,field8,"
            "field9,field10,field11,field12,field13,field14,field15,field16,"
            "field17,field18,field19,field20,field21,field22,field23"
        )
        result = inject_session_id_into_pkt(line, "newsession")
        assert result.startswith("PKT,newsession,")
        # The rest of the line should be preserved
        assert result.endswith(
            "field2,field3,field4,field5,field6,field7,field8,field9,field10,"
            "field11,field12,field13,field14,field15,field16,field17,field18,"
            "field19,field20,field21,field22,field23"
        )