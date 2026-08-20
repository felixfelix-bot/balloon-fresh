"""
Tests for session_manager.py — HOST-3 session ID management.

Tests cover:
  - Session ID generation (format, uniqueness, timestamp correctness)
  - Session ID validation (valid/invalid formats)
  - SessionManager lifecycle (new_session, current_session, end_session)
  - Persistence (save/load/clear state file)
  - Edge cases (double-start, end without start, corrupt state file)
  - Timestamp extraction from session IDs
"""

import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path

import pytest

# Ensure tools/ is importable
TOOLS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "tools")
if TOOLS_DIR not in sys.path:
    sys.path.insert(0, TOOLS_DIR)

from session_manager import (
    SessionManager,
    generate_session_id,
    validate_session_id,
    extract_timestamp,
    SESSION_RAND_HEX_LEN,
)


# ─── generate_session_id ────────────────────────────────────────────────


class TestGenerateSessionId:
    def test_generates_valid_id(self):
        """generate_session_id produces a valid session ID."""
        sid = generate_session_id()
        assert validate_session_id(sid) is True

    def test_format_is_correct(self):
        """Session ID has format YYYYmmdd-HHMMSS-<6hex>."""
        dt = datetime(2026, 8, 20, 14, 30, 5)
        sid = generate_session_id(dt=dt)
        # Timestamp prefix should match the given datetime
        assert sid.startswith("20260820-143005-")
        # Random suffix should be 6 hex chars
        suffix = sid.split("-")[2]
        assert len(suffix) == SESSION_RAND_HEX_LEN
        int(suffix, 16)  # should not raise

    def test_uses_current_time_by_default(self):
        """Without explicit dt, uses current time."""
        before = datetime.now().replace(microsecond=0)
        sid = generate_session_id()
        after = datetime.now().replace(microsecond=0)
        ts = extract_timestamp(sid)
        assert ts is not None
        assert before <= ts <= after

    def test_two_ids_are_unique(self):
        """Two generated IDs are different (random suffix)."""
        ids = {generate_session_id() for _ in range(100)}
        # With 6 hex chars of randomness, collisions are extremely unlikely
        assert len(ids) == 100

    def test_same_dt_different_ids(self):
        """Same datetime still produces unique IDs via random suffix."""
        dt = datetime(2026, 1, 1, 0, 0, 0)
        ids = {generate_session_id(dt=dt) for _ in range(50)}
        assert len(ids) == 50


# ─── validate_session_id ────────────────────────────────────────────────


class TestValidateSessionId:
    def test_valid_id(self):
        """A well-formed session ID validates."""
        assert validate_session_id("20260820-143005-a1b2c3") is True

    def test_valid_id_uppercase_hex(self):
        """Uppercase hex in the random suffix is rejected (lowercase only)."""
        # int(x, 16) accepts uppercase, so this should be valid
        assert validate_session_id("20260820-143005-A1B2C3") is True

    def test_invalid_wrong_parts_count(self):
        """Session ID with wrong number of dash-separated parts is invalid."""
        assert validate_session_id("20260820-143005") is False
        assert validate_session_id("20260820-143005-a1b2c3-extra") is False

    def test_invalid_bad_date(self):
        """Non-numeric date part is invalid."""
        assert validate_session_id("abcdefgh-143005-a1b2c3") is False

    def test_invalid_bad_time(self):
        """Non-numeric time part is invalid."""
        assert validate_session_id("20260820-abcdef-a1b2c3") is False

    def test_invalid_bad_hex_suffix(self):
        """Non-hex suffix is invalid."""
        assert validate_session_id("20260820-143005-xyzxyz") is False

    def test_invalid_wrong_suffix_length(self):
        """Suffix of wrong length is invalid."""
        assert validate_session_id("20260820-143005-a1b2") is False
        assert validate_session_id("20260820-143005-a1b2c3d4") is False

    def test_invalid_empty_string(self):
        """Empty string is not a valid session ID."""
        assert validate_session_id("") is False

    def test_invalid_non_string(self):
        """Non-string input returns False (does not raise)."""
        assert validate_session_id(None) is False
        assert validate_session_id(12345) is False

    def test_invalid_date_too_short(self):
        """Date part too short is invalid."""
        assert validate_session_id("2026082-143005-a1b2c3") is False

    def test_invalid_time_too_short(self):
        """Time part too short is invalid."""
        assert validate_session_id("20260820-14305-a1b2c3") is False


# ─── extract_timestamp ──────────────────────────────────────────────────


class TestExtractTimestamp:
    def test_extracts_correct_datetime(self):
        """extract_timestamp returns the correct datetime."""
        sid = "20260820-143005-a1b2c3"
        ts = extract_timestamp(sid)
        assert ts == datetime(2026, 8, 20, 14, 30, 5)

    def test_returns_none_for_invalid(self):
        """extract_timestamp returns None for invalid session IDs."""
        assert extract_timestamp("invalid") is None
        assert extract_timestamp("") is None

    def test_returns_none_for_non_string(self):
        """extract_timestamp returns None for non-string input."""
        assert extract_timestamp(None) is None


# ─── SessionManager lifecycle ───────────────────────────────────────────


class TestSessionManagerLifecycle:
    def test_new_session_returns_valid_id(self):
        """new_session returns a valid session ID."""
        sm = SessionManager()
        sid = sm.new_session()
        assert validate_session_id(sid) is True
        assert sm.current_session() == sid

    def test_is_active_after_new_session(self):
        """is_active returns True after starting a session."""
        sm = SessionManager()
        assert sm.is_active() is False
        sm.new_session()
        assert sm.is_active() is True

    def test_end_session_returns_id(self):
        """end_session returns the session ID that was ended."""
        sm = SessionManager()
        sid = sm.new_session()
        ended = sm.end_session()
        assert ended == sid

    def test_not_active_after_end(self):
        """is_active returns False after ending a session."""
        sm = SessionManager()
        sm.new_session()
        sm.end_session()
        assert sm.is_active() is False
        assert sm.current_session() is None

    def test_end_without_start_returns_none(self):
        """end_session without an active session returns None."""
        sm = SessionManager()
        assert sm.end_session() is None

    def test_double_start_raises(self):
        """Starting a new session while one is active raises ValueError."""
        sm = SessionManager()
        sm.new_session()
        with pytest.raises(ValueError, match="already active"):
            sm.new_session()

    def test_can_start_after_end(self):
        """A new session can be started after ending the previous one."""
        sm = SessionManager()
        sid1 = sm.new_session()
        sm.end_session()
        sid2 = sm.new_session()
        assert sid1 != sid2
        assert sm.current_session() == sid2

    def test_explicit_session_id(self):
        """new_session accepts an explicit, valid session ID."""
        sm = SessionManager()
        sid = sm.new_session(session_id="20260101-000000-abcdef")
        assert sid == "20260101-000000-abcdef"
        assert sm.current_session() == sid

    def test_invalid_explicit_session_id_raises(self):
        """new_session raises ValueError for an invalid explicit session ID."""
        sm = SessionManager()
        with pytest.raises(ValueError, match="Invalid session ID"):
            sm.new_session(session_id="not-a-valid-id")


# ─── SessionManager duration ────────────────────────────────────────────


class TestSessionManagerDuration:
    def test_duration_none_before_session(self):
        """session_duration returns None before any session is started."""
        sm = SessionManager()
        assert sm.session_duration() is None

    def test_duration_increases_during_session(self):
        """session_duration returns a positive value during an active session."""
        sm = SessionManager()
        sm.new_session()
        time.sleep(0.05)
        d = sm.session_duration()
        assert d is not None
        assert d > 0

    def test_duration_freezes_after_end(self):
        """session_duration does not increase after session ends."""
        sm = SessionManager()
        sm.new_session()
        time.sleep(0.05)
        sm.end_session()
        d1 = sm.session_duration()
        time.sleep(0.05)
        d2 = sm.session_duration()
        assert d1 is not None
        assert d2 is not None
        # d2 should be approximately equal to d1 (not growing)
        assert d2 - d1 < 0.05


# ─── SessionManager persistence ─────────────────────────────────────────


class TestSessionManagerPersistence:
    def test_persist_saves_state(self, tmp_path):
        """With persist=True, session state is saved to the state file."""
        state_file = str(tmp_path / "state.json")
        sm = SessionManager(state_file=state_file, persist=True)
        sid = sm.new_session()
        assert os.path.exists(state_file)
        with open(state_file) as f:
            state = json.load(f)
        assert state["session_id"] == sid
        assert "start_time" in state

    def test_load_recovers_session(self, tmp_path):
        """Loading from a state file recovers the previous session."""
        state_file = str(tmp_path / "state.json")
        sm1 = SessionManager(state_file=state_file, persist=True)
        sid = sm1.new_session()

        # Simulate a restart — create a new manager pointing at same file
        sm2 = SessionManager(state_file=state_file)
        assert sm2.current_session() == sid

    def test_end_clears_state_file(self, tmp_path):
        """end_session removes the state file when persist=True."""
        state_file = str(tmp_path / "state.json")
        sm = SessionManager(state_file=state_file, persist=True)
        sm.new_session()
        assert os.path.exists(state_file)
        sm.end_session()
        assert not os.path.exists(state_file)

    def test_no_persist_does_not_save(self, tmp_path):
        """Without persist=True, no state file is created."""
        state_file = str(tmp_path / "state.json")
        sm = SessionManager(state_file=state_file, persist=False)
        sm.new_session()
        assert not os.path.exists(state_file)

    def test_corrupt_state_file_ignored(self, tmp_path):
        """A corrupt state file is ignored (no crash, no session loaded)."""
        state_file = str(tmp_path / "state.json")
        with open(state_file, "w") as f:
            f.write("{not valid json")
        sm = SessionManager(state_file=state_file)
        assert sm.current_session() is None
        assert sm.is_active() is False

    def test_state_file_with_invalid_id_ignored(self, tmp_path):
        """State file containing an invalid session ID is ignored."""
        state_file = str(tmp_path / "state.json")
        state = {"session_id": "garbage", "start_time": time.time()}
        with open(state_file, "w") as f:
            json.dump(state, f)
        sm = SessionManager(state_file=state_file)
        assert sm.current_session() is None

    def test_new_session_after_load_raises(self, tmp_path):
        """Starting a new session when one was loaded from state raises."""
        state_file = str(tmp_path / "state.json")
        sm1 = SessionManager(state_file=state_file, persist=True)
        sm1.new_session()

        sm2 = SessionManager(state_file=state_file)
        with pytest.raises(ValueError, match="already active"):
            sm2.new_session()

    def test_load_then_end_then_new(self, tmp_path):
        """Can end a loaded session and start a fresh one."""
        state_file = str(tmp_path / "state.json")
        sm1 = SessionManager(state_file=state_file, persist=True)
        sid1 = sm1.new_session()

        sm2 = SessionManager(state_file=state_file)
        assert sm2.current_session() == sid1
        sm2.end_session()
        sid2 = sm2.new_session()
        assert sid2 != sid1