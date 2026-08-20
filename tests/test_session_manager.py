"""Tests for session_manager create_session/persist_session — HOST-3.

Tests the create_session() and persist_session() functions, plus a
regression check on inject_session_id_into_pkt().
Also tests the CLI / central-session-store functions: new_session,
set_session, current_session, and the _cli() entry point.
Also tests the session lifecycle functions: start_session,
get_session_status, end_session, and duplicate session handling.
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
    start_session,
    get_session_status,
    end_session,
    list_sessions,
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


class TestSessionLifecycle:
    """Tests for the session lifecycle: start_session, get_session_status,
    end_session, list_sessions, and duplicate session handling."""

    def test_start_session_creates_valid_id(self, tmp_path):
        """start_session() returns metadata with a valid session_id."""
        path = str(tmp_path / "sessions.json")
        meta = start_session(filepath=path)
        assert isinstance(meta, dict)
        assert "session_id" in meta
        assert isinstance(meta["session_id"], str)
        assert len(meta["session_id"]) > 0
        assert meta["status"] == "active"
        assert "start_time" in meta
        assert meta["end_time"] is None

    def test_start_session_with_config(self, tmp_path):
        """start_session(config=...) stores the config in metadata."""
        path = str(tmp_path / "sessions.json")
        cfg = {"config_id": "F2600", "replicate": 2}
        meta = start_session(config=cfg, filepath=path)
        assert meta["config"] == cfg

    def test_get_session_status(self, tmp_path):
        """get_session_status() retrieves the metadata for a started session."""
        path = str(tmp_path / "sessions.json")
        meta = start_session(filepath=path)
        sid = meta["session_id"]
        status = get_session_status(sid, filepath=path)
        assert status is not None
        assert status["session_id"] == sid
        assert status["status"] == "active"

    def test_get_session_status_not_found(self, tmp_path):
        """get_session_status() returns None for unknown session_id."""
        path = str(tmp_path / "sessions.json")
        assert get_session_status("nonexistent-id", filepath=path) is None

    def test_end_session(self, tmp_path):
        """end_session() sets status to 'ended' and records end_time."""
        path = str(tmp_path / "sessions.json")
        meta = start_session(filepath=path)
        sid = meta["session_id"]
        ended = end_session(sid, filepath=path)
        assert ended is not None
        assert ended["status"] == "ended"
        assert ended["end_time"] is not None
        # Verify persisted
        status = get_session_status(sid, filepath=path)
        assert status["status"] == "ended"

    def test_end_session_not_found(self, tmp_path):
        """end_session() returns None for unknown session_id."""
        path = str(tmp_path / "sessions.json")
        assert end_session("nonexistent-id", filepath=path) is None

    def test_duplicate_session_handling(self, tmp_path):
        """Multiple start_session() calls create unique sessions in the registry."""
        path = str(tmp_path / "sessions.json")
        meta1 = start_session(filepath=path)
        meta2 = start_session(filepath=path)
        assert meta1["session_id"] != meta2["session_id"]
        # Both should be retrievable
        assert get_session_status(meta1["session_id"], filepath=path) is not None
        assert get_session_status(meta2["session_id"], filepath=path) is not None
        # Registry should contain both
        sessions = list_sessions(filepath=path)
        assert len(sessions) == 2

    def test_end_only_affects_target_session(self, tmp_path):
        """Ending one session does not affect other active sessions."""
        path = str(tmp_path / "sessions.json")
        meta1 = start_session(filepath=path)
        meta2 = start_session(filepath=path)
        end_session(meta1["session_id"], filepath=path)
        # Session 1 ended, session 2 still active
        assert get_session_status(meta1["session_id"], filepath=path)["status"] == "ended"
        assert get_session_status(meta2["session_id"], filepath=path)["status"] == "active"

    def test_list_sessions_sorted(self, tmp_path):
        """list_sessions() returns sessions sorted by start_time descending."""
        path = str(tmp_path / "sessions.json")
        start_session(filepath=path)
        start_session(filepath=path)
        sessions = list_sessions(filepath=path)
        assert len(sessions) == 2
        # Most recent first
        assert sessions[0]["start_time"] >= sessions[1]["start_time"]

    def test_persistence_across_calls(self, tmp_path):
        """Sessions persist across separate _load_sessions calls."""
        path = str(tmp_path / "sessions.json")
        meta = start_session(filepath=path)
        # Simulate a "new process" by just calling get_session_status again
        status = get_session_status(meta["session_id"], filepath=path)
        assert status is not None
        assert status["session_id"] == meta["session_id"]


class TestCLILifecycle:
    """Tests for the CLI subcommands: start, status, end, list."""

    def test_cli_start(self, tmp_path, capsys, monkeypatch):
        """`start` subcommand prints a valid session_id."""
        path = str(tmp_path / "sessions.json")
        monkeypatch.setenv("BALLOON_SESSIONS_FILE", path)
        rc = _cli(["start"])
        assert rc == 0
        captured = capsys.readouterr()
        sid = captured.out.strip()
        assert len(sid) > 0
        # Should be persisted in the registry
        assert get_session_status(sid, filepath=path) is not None

    def test_cli_start_with_config(self, tmp_path, capsys, monkeypatch):
        """`start --config-id` stores the config."""
        path = str(tmp_path / "sessions.json")
        monkeypatch.setenv("BALLOON_SESSIONS_FILE", path)
        rc = _cli(["start", "--config-id", "F2600"])
        assert rc == 0
        captured = capsys.readouterr()
        sid = captured.out.strip()
        status = get_session_status(sid, filepath=path)
        assert status["config"] == {"config_id": "F2600"}

    def test_cli_status(self, tmp_path, capsys, monkeypatch):
        """`status <id>` prints the session metadata as JSON."""
        path = str(tmp_path / "sessions.json")
        monkeypatch.setenv("BALLOON_SESSIONS_FILE", path)
        meta = start_session(filepath=path)
        rc = _cli(["status", meta["session_id"]])
        assert rc == 0
        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert data["session_id"] == meta["session_id"]

    def test_cli_status_not_found(self, tmp_path, capsys, monkeypatch):
        """`status <id>` returns rc=1 for unknown session."""
        path = str(tmp_path / "sessions.json")
        monkeypatch.setenv("BALLOON_SESSIONS_FILE", path)
        rc = _cli(["status", "nonexistent"])
        assert rc == 1

    def test_cli_end(self, tmp_path, capsys, monkeypatch):
        """`end <id>` ends the session and prints updated metadata."""
        path = str(tmp_path / "sessions.json")
        monkeypatch.setenv("BALLOON_SESSIONS_FILE", path)
        meta = start_session(filepath=path)
        rc = _cli(["end", meta["session_id"]])
        assert rc == 0
        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert data["status"] == "ended"
        assert data["end_time"] is not None

    def test_cli_end_not_found(self, tmp_path, capsys, monkeypatch):
        """`end <id>` returns rc=1 for unknown session."""
        path = str(tmp_path / "sessions.json")
        monkeypatch.setenv("BALLOON_SESSIONS_FILE", path)
        rc = _cli(["end", "nonexistent"])
        assert rc == 1

    def test_cli_list_empty(self, tmp_path, capsys, monkeypatch):
        """`list` with no sessions prints '(no sessions)'."""
        path = str(tmp_path / "sessions.json")
        monkeypatch.setenv("BALLOON_SESSIONS_FILE", path)
        rc = _cli(["list"])
        assert rc == 0
        captured = capsys.readouterr()
        assert "(no sessions)" in captured.out

    def test_cli_list_with_sessions(self, tmp_path, capsys, monkeypatch):
        """`list` shows all sessions."""
        path = str(tmp_path / "sessions.json")
        monkeypatch.setenv("BALLOON_SESSIONS_FILE", path)
        start_session(filepath=path)
        start_session(filepath=path)
        rc = _cli(["list"])
        assert rc == 0
        captured = capsys.readouterr()
        # Should have 2 lines (plus possible newline)
        lines = [l for l in captured.out.strip().split("\n") if l.strip()]
        assert len(lines) == 2


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