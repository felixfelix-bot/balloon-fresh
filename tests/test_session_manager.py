"""Tests for session_manager create_session/persist_session — HOST-3.

Tests the create_session() and persist_session() functions, plus a
regression check on inject_session_id_into_pkt().
Also tests the CLI / central-session-store functions: new_session,
set_session, current_session, and the _cli() entry point.
"""

import json
import os

from tools.session_manager import (
    create_session,
    persist_session,
    inject_session_id_into_pkt,
    new_session,
    set_session,
    current_session,
    load_current_session,
    save_current_session,
    _cli,
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


class TestCentralSessionStore:
    """Tests for new_session / set_session / current_session with the
    central ~/.balloon/session.json store (using a temp-file override)."""

    def test_new_session_creates_and_persists(self, tmp_path):
        """new_session() generates an id and writes it to the session file."""
        path = str(tmp_path / "session.json")
        sid = new_session(filepath=path)
        assert isinstance(sid, str)
        assert len(sid) > 0
        # File should exist and contain the session_id
        assert os.path.exists(path)
        with open(path) as f:
            data = json.load(f)
        assert data["session_id"] == sid

    def test_current_session_retrieves(self, tmp_path):
        """current_session() returns the id written by new_session()."""
        path = str(tmp_path / "session.json")
        sid = new_session(filepath=path)
        assert current_session(filepath=path) == sid

    def test_current_session_none_when_no_file(self, tmp_path):
        """current_session() returns None when no session file exists."""
        path = str(tmp_path / "nonexistent.json")
        assert current_session(filepath=path) is None

    def test_set_session_explicit_id(self, tmp_path):
        """set_session() persists an explicit id and current_session retrieves it."""
        path = str(tmp_path / "session.json")
        set_session("my-explicit-id", filepath=path)
        assert current_session(filepath=path) == "my-explicit-id"

    def test_set_session_overwrites(self, tmp_path):
        """set_session() overwrites a previous session_id."""
        path = str(tmp_path / "session.json")
        set_session("first-id", filepath=path)
        set_session("second-id", filepath=path)
        assert current_session(filepath=path) == "second-id"

    def test_save_load_roundtrip(self, tmp_path):
        """save_current_session + load_current_session round-trip correctly."""
        path = str(tmp_path / "session.json")
        save_current_session("rt-id", filepath=path)
        assert load_current_session(filepath=path) == "rt-id"

    def test_new_session_uniqueness(self, tmp_path):
        """Two new_session() calls produce different ids."""
        path = str(tmp_path / "session.json")
        a = new_session(filepath=path)
        b = new_session(filepath=path)
        assert a != b
        # The file should hold the most recent one
        assert current_session(filepath=path) == b


class TestCLI:
    """Tests for the _cli() entry point (--new-session, --current-session, --set-session)."""

    def test_cli_new_session(self, tmp_path, capsys, monkeypatch):
        """--new-session prints a new session_id to stdout."""
        path = str(tmp_path / "session.json")
        monkeypatch.setenv("BALLOON_SESSION_FILE", path)
        rc = _cli(["--new-session"])
        assert rc == 0
        captured = capsys.readouterr()
        printed_id = captured.out.strip()
        assert len(printed_id) > 0
        # The printed id should match what's persisted
        assert load_current_session(filepath=path) == printed_id

    def test_cli_current_session(self, tmp_path, capsys, monkeypatch):
        """--current-session prints the persisted session_id."""
        path = str(tmp_path / "session.json")
        monkeypatch.setenv("BALLOON_SESSION_FILE", path)
        set_session("cli-test-id", filepath=path)
        rc = _cli(["--current-session"])
        assert rc == 0
        captured = capsys.readouterr()
        assert captured.out.strip() == "cli-test-id"

    def test_cli_current_session_none(self, tmp_path, capsys, monkeypatch):
        """--current-session returns rc=1 when no session exists."""
        path = str(tmp_path / "nonexistent.json")
        monkeypatch.setenv("BALLOON_SESSION_FILE", path)
        rc = _cli(["--current-session"])
        assert rc == 1

    def test_cli_set_session(self, tmp_path, capsys, monkeypatch):
        """--set-session <id> sets and prints the id."""
        path = str(tmp_path / "session.json")
        monkeypatch.setenv("BALLOON_SESSION_FILE", path)
        rc = _cli(["--set-session", "explicit-cli-id"])
        assert rc == 0
        captured = capsys.readouterr()
        assert captured.out.strip() == "explicit-cli-id"
        assert load_current_session(filepath=path) == "explicit-cli-id"