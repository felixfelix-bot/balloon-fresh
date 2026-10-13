#!/usr/bin/env python3
"""
session_manager.py — Session ID manager for capture runs (HOST-3).

Generates and manages unique session IDs for data-capture runs so that every
CSV/raw artefact produced by ``rx_range_logger`` (or other host capture tools)
can be traced back to a single, well-identified session.

A session ID is a short, human-readable, lexicographically-sortable string of
the form::

    YYYYmmdd-HHMMSS-<6-hex>

The date/time prefix comes from the wall clock when the session is created;
the 6-hex suffix is random, guaranteeing uniqueness even when two sessions
start in the same second.

The manager can optionally persist the current session to a JSON state file
so that a crash/restart can recover the same session ID instead of silently
starting a new one.

Usage as a library::

    from session_manager import SessionManager

    sm = SessionManager()
    sid = sm.new_session()
    print(f"Capture session: {sid}")
    # ... later ...
    sm.end_session()

    # Recover a previous session from state file:
    sm2 = SessionManager(state_file="/tmp/capture_session.json")
    recovered = sm2.current_session()  # None if no prior session

Usage as a CLI::

    python3 session_manager.py                    # print a new session ID
    python3 session_manager.py --state /tmp/s.json # create + persist
    python3 session_manager.py --show /tmp/s.json  # show current
"""

import argparse
import json
import os
import random
import secrets
import string
import sys
import time
from datetime import datetime
from pathlib import Path

# Length of the random hex suffix.
SESSION_RAND_HEX_LEN = 6
# Default state-file location (can be overridden via constructor).
DEFAULT_STATE_FILE = ".capture_session.json"


def generate_session_id(dt: datetime | None = None) -> str:
    """
    Generate a new session ID.

    Format: ``YYYYmmdd-HHMMSS-<6hex>``

    Args:
        dt: Optional datetime to use for the timestamp prefix. If None,
            uses the current local time.

    Returns:
        A session ID string, e.g. ``20260820-143005-a1b2c3``.
    """
    if dt is None:
        dt = datetime.now()
    ts = dt.strftime("%Y%m%d-%H%M%S")
    rand_hex = secrets.token_hex(SESSION_RAND_HEX_LEN // 2)
    # token_hex(N) returns 2*N hex chars; we want SESSION_RAND_HEX_LEN chars
    if len(rand_hex) > SESSION_RAND_HEX_LEN:
        rand_hex = rand_hex[:SESSION_RAND_HEX_LEN]
    elif len(rand_hex) < SESSION_RAND_HEX_LEN:
        # Pad in the unlikely case token_hex returned fewer chars
        rand_hex = rand_hex.ljust(SESSION_RAND_HEX_LEN, "0")
    return f"{ts}-{rand_hex}"


def validate_session_id(session_id: str) -> bool:
    """
    Validate that a string is a well-formed session ID.

    A valid session ID matches the pattern
    ``\\d{8}-\\d{6}-[0-9a-f]{6}``.

    Args:
        session_id: The string to validate.

    Returns:
        True if the session ID is well-formed, False otherwise.
    """
    if not isinstance(session_id, str):
        return False
    parts = session_id.split("-")
    if len(parts) != 3:
        return False
    date_part, time_part, rand_part = parts
    if len(date_part) != 8 or not date_part.isdigit():
        return False
    if len(time_part) != 6 or not time_part.isdigit():
        return False
    if len(rand_part) != SESSION_RAND_HEX_LEN:
        return False
    try:
        int(rand_part, 16)  # must be valid hex
    except ValueError:
        return False
    return True


def extract_timestamp(session_id: str) -> datetime | None:
    """
    Extract the datetime from a session ID's timestamp prefix.

    Args:
        session_id: A valid session ID string.

    Returns:
        A datetime object, or None if the session ID is invalid or the
        timestamp cannot be parsed.
    """
    if not validate_session_id(session_id):
        return None
    parts = session_id.split("-")
    date_str, time_str = parts[0], parts[1]
    try:
        return datetime.strptime(date_str + time_str, "%Y%m%d%H%M%S")
    except ValueError:
        return None


class SessionManager:
    """
    Manages session IDs for capture runs.

    Args:
        state_file: Optional path to a JSON state file. When provided (or
                    when ``persist=True``), the manager saves the current
                    session ID so it can be recovered after a restart.
        persist: If True, automatically save session state to
                 ``state_file`` whenever a session is created or ended.
    """

    def __init__(self, state_file: str | None = None, persist: bool = False):
        self.state_file = state_file
        self.persist = persist
        self._session: str | None = None
        self._session_start: float | None = None
        self._session_end: float | None = None

        # Try to load existing session from state file
        if self.state_file and os.path.exists(self.state_file):
            self._load_state()

    def new_session(self, session_id: str | None = None) -> str:
        """
        Start a new capture session.

        Args:
            session_id: Optional explicit session ID. If None, a new one
                        is generated automatically.

        Returns:
            The session ID string.

        Raises:
            ValueError: If a session is already active (call ``end_session``
                        first), or if an explicit session_id is provided
                        but is invalid.
        """
        if self._session is not None:
            raise ValueError(
                f"Session already active: {self._session}. "
                "Call end_session() before starting a new one."
            )

        if session_id is not None:
            if not validate_session_id(session_id):
                raise ValueError(f"Invalid session ID format: {session_id}")
            self._session = session_id
        else:
            self._session = generate_session_id()

        self._session_start = time.time()
        self._session_end = None

        if self.persist and self.state_file:
            self._save_state()

        return self._session

    def current_session(self) -> str | None:
        """
        Return the current active session ID, or None if no session is active.
        """
        return self._session

    def end_session(self) -> str | None:
        """
        End the current capture session.

        Returns:
            The session ID that was ended, or None if no session was active.
        """
        sid = self._session
        self._session = None
        self._session_end = time.time()

        if self.persist and self.state_file:
            self._clear_state()

        return sid

    def is_active(self) -> bool:
        """Return True if a session is currently active."""
        return self._session is not None

    def session_duration(self) -> float | None:
        """
        Return the duration of the current or most-recent session in seconds.

        If a session is active, returns elapsed time since start.
        If the last session has ended, returns total duration.
        If no session has been started, returns None.
        """
        if self._session_start is None:
            return None
        end = self._session_end if self._session_end is not None else time.time()
        return end - self._session_start

    def _save_state(self) -> None:
        """Save current session state to the state file."""
        if not self.state_file:
            return
        state = {
            "session_id": self._session,
            "start_time": self._session_start,
        }
        with open(self.state_file, "w") as f:
            json.dump(state, f, indent=2)

    def _load_state(self) -> None:
        """Load session state from the state file."""
        if not self.state_file or not os.path.exists(self.state_file):
            return
        try:
            with open(self.state_file, "r") as f:
                state = json.load(f)
            sid = state.get("session_id")
            if sid and validate_session_id(sid):
                self._session = sid
                self._session_start = state.get("start_time")
        except (json.JSONDecodeError, KeyError, OSError):
            # Corrupt state file — start fresh
            pass

    def _clear_state(self) -> None:
        """Remove the state file."""
        if self.state_file and os.path.exists(self.state_file):
            try:
                os.remove(self.state_file)
            except OSError:
                pass


def main():
    """CLI entry point for session management."""
    parser = argparse.ArgumentParser(
        description="Session ID manager for capture runs (HOST-3)"
    )
    parser.add_argument("--state", default=None,
                        help="Path to state file for persistence")
    parser.add_argument("--show", action="store_true",
                        help="Show current session from state file and exit")
    parser.add_argument("--validate", default=None,
                        help="Validate a session ID string and exit")
    args = parser.parse_args()

    if args.validate is not None:
        valid = validate_session_id(args.validate)
        print(f"{'VALID' if valid else 'INVALID'}: {args.validate}")
        sys.exit(0 if valid else 1)

    if args.show:
        if not args.state:
            print("ERROR: --show requires --state", file=sys.stderr)
            sys.exit(2)
        sm = SessionManager(state_file=args.state)
        sid = sm.current_session()
        if sid:
            print(f"Current session: {sid}")
        else:
            print("No active session.")
        sys.exit(0)

    sm = SessionManager(state_file=args.state, persist=bool(args.state))
    sid = sm.new_session()
    print(sid)


if __name__ == "__main__":
    main()