"""Session manager — HOST-3.

Generates and injects a unique session_id into capture sessions.

The session_id format is ``YYYYMMDDHHMMSS-<8hex>`` — a timestamp followed by
8 hex characters derived from a UUID4.  This makes it human-readable while
still being globally unique.

Usage:
    from tools.session_manager import (
        generate_session_id,
        format_session_command,
        format_config_command,
    )

    session_id = generate_session_id()
    # Send "SESSION <id>\\r\\n" to firmware before capture
    ser.write(format_session_command(session_id).encode())
    # Print "# SESSION <id>" header to output
    print(f"# SESSION {session_id}")
"""

import json
import os
import uuid
from datetime import datetime, timezone


def generate_session_id() -> str:
    """Generate a unique session_id.

    Returns:
        A string in the format ``YYYYMMDDHHMMSS-<8hex>``, e.g.
        ``"20260820143022-a1b2c3d4"``.
    """
    ts = datetime.now().strftime("%Y%m%d%H%M%S")
    short_hex = uuid.uuid4().hex[:8]
    return f"{ts}-{short_hex}"


def format_session_command(session_id: str) -> str:
    """Format the SESSION command to send to firmware.

    Args:
        session_id: The session_id string from generate_session_id().

    Returns:
        A command string ``"SESSION {session_id}\\r\\n"``.
    """
    return f"SESSION {session_id}\r\n"


def format_config_command(config_id: str, replicate: int) -> str:
    """Format the CONFIG command to send to firmware.

    Args:
        config_id: The configuration identifier (e.g. "F2600").
        replicate: The replicate number.

    Returns:
        A command string ``"CONFIG {config_id} {replicate}\\r\\n"``.
    """
    return f"CONFIG {config_id} {replicate}\r\n"


def format_session_start(session_id: str) -> str:
    """Format the SESSION_START header line for CSV output.

    Args:
        session_id: The session_id string from generate_session_id().

    Returns:
        A line in the format ``SESSION_START,<id>,<iso-timestamp>\\n``.
    """
    from datetime import timezone
    ts = datetime.now(timezone.utc).isoformat()
    return f"SESSION_START,{session_id},{ts}\n"


def inject_session_id_into_pkt(line: str, session_id: str) -> str:
    """Inject a session_id into a PKT line's session_id field.

    The PKT format has 23 comma-separated fields after the ``PKT,`` prefix.
    Field 0 (the first field) is ``session_id``.  This function replaces
    that field with the given session_id.

    Args:
        line: A raw serial output line.  If it starts with ``PKT,``,
              the session_id field is replaced.  Other lines are
              returned unchanged.
        session_id: The session_id to inject.

    Returns:
        The modified line with the session_id injected, or the
        original line if it is not a PKT line.
    """
    if not line or not line.startswith("PKT,"):
        return line

    parts = line[4:].split(",", 1)  # Split after first comma (session_id field)
    if len(parts) < 2:
        # Malformed PKT line — return as-is
        return line

    # Reconstruct: PKT,<session_id>,<rest>
    return f"PKT,{session_id},{parts[1]}"


def create_session(config=None, output_dir=None) -> dict:
    """Create a new capture session with metadata.

    Generates a unique session_id, builds a metadata dict, and optionally
    persists it to a JSON file.

    Args:
        config: Optional configuration dict to store in the session metadata.
        output_dir: Optional directory path. If provided, the metadata is
                    written to ``<output_dir>/session_<session_id>.json``.

    Returns:
        A metadata dict with keys: ``session_id``, ``start_time``, ``config``.
    """
    session_id = generate_session_id()
    metadata = {
        "session_id": session_id,
        "start_time": datetime.now(timezone.utc).isoformat(),
        "config": config,
    }
    if output_dir is not None:
        filepath = os.path.join(output_dir, f"session_{session_id}.json")
        persist_session(metadata, filepath)
    return metadata


def persist_session(metadata: dict, filepath: str) -> None:
    """Write session metadata to a JSON file (pretty-printed).

    Args:
        metadata: The session metadata dict to persist.
        filepath: The full path to the output JSON file.
    """
    with open(filepath, "w") as f:
        json.dump(metadata, f, indent=2, sort_keys=True)


# ── Central session store ────────────────────────────────────────────────
# The "current" session is persisted to a central JSON file so that multiple
# capture tools can share the same session_id without re-generating it.

DEFAULT_SESSION_FILE = os.path.expanduser("~/.balloon/session.json")


def _default_session_file() -> str:
    """Return the default central session file path (~/.balloon/session.json).

    Honors the BALLOON_SESSION_FILE environment variable if set, to support
    tests and isolated environments.
    """
    return os.environ.get("BALLOON_SESSION_FILE", DEFAULT_SESSION_FILE)


def save_current_session(session_id: str, filepath: str | None = None) -> str:
    """Persist the current session_id to the central session file.

    Creates the parent directory if it does not exist.

    Args:
        session_id: The session_id to save as current.
        filepath: Optional override for the session file path. If None, uses
                  the default (~/.balloon/session.json or $BALLOON_SESSION_FILE).

    Returns:
        The path the session was written to.
    """
    path = filepath or _default_session_file()
    directory = os.path.dirname(path)
    if directory:
        os.makedirs(directory, exist_ok=True)
    data = {
        "session_id": session_id,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    with open(path, "w") as f:
        json.dump(data, f, indent=2, sort_keys=True)
    return path


def load_current_session(filepath: str | None = None) -> str | None:
    """Read the current session_id from the central session file.

    Args:
        filepath: Optional override for the session file path. If None, uses
                  the default (~/.balloon/session.json or $BALLOON_SESSION_FILE).

    Returns:
        The current session_id string, or None if no session file exists.
    """
    path = filepath or _default_session_file()
    if not os.path.exists(path):
        return None
    try:
        with open(path) as f:
            data = json.load(f)
        return data.get("session_id")
    except (json.JSONDecodeError, OSError):
        return None


def new_session(filepath: str | None = None) -> str:
    """Generate a new session_id and save it as the current session.

    Args:
        filepath: Optional override for the session file path.

    Returns:
        The newly generated session_id.
    """
    session_id = generate_session_id()
    save_current_session(session_id, filepath)
    return session_id


def set_session(session_id: str, filepath: str | None = None) -> str:
    """Set the current session_id to an explicit value.

    Args:
        session_id: The session_id to set as current.
        filepath: Optional override for the session file path.

    Returns:
        The session_id that was set.
    """
    save_current_session(session_id, filepath)
    return session_id


def current_session(filepath: str | None = None) -> str | None:
    """Return the current session_id (alias for load_current_session)."""
    return load_current_session(filepath)


# ── Session lifecycle store ──────────────────────────────────────────────
# A multi-session registry that tracks session lifecycle (start/end/status).
# Stored as a JSON dict keyed by session_id at ~/.balloon/sessions.json.

DEFAULT_SESSIONS_FILE = os.path.expanduser("~/.balloon/sessions.json")


def _default_sessions_file() -> str:
    """Return the default multi-session registry path.

    Honors the BALLOON_SESSIONS_FILE environment variable if set, to support
    tests and isolated environments.
    """
    return os.environ.get("BALLOON_SESSIONS_FILE", DEFAULT_SESSIONS_FILE)


def _load_sessions(filepath: str | None = None) -> dict:
    """Load the full sessions registry from the JSON file.

    Returns an empty dict if the file does not exist or is unreadable.
    """
    path = filepath or _default_sessions_file()
    if not os.path.exists(path):
        return {}
    try:
        with open(path) as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return {}


def _save_sessions(sessions: dict, filepath: str | None = None) -> None:
    """Write the full sessions registry to the JSON file."""
    path = filepath or _default_sessions_file()
    directory = os.path.dirname(path)
    if directory:
        os.makedirs(directory, exist_ok=True)
    with open(path, "w") as f:
        json.dump(sessions, f, indent=2, sort_keys=True)


def start_session(config=None, filepath: str | None = None) -> dict:
    """Start a new capture session.

    Generates a unique session_id, records it in the multi-session registry
    with status ``"active"`` and a UTC start_time, and also saves it as the
    current session in the central session file.

    Args:
        config: Optional configuration dict stored in the session metadata.
        filepath: Optional override for the sessions registry file path.

    Returns:
        A metadata dict with keys: ``session_id``, ``status``, ``start_time``,
        ``end_time`` (None), ``config``.
    """
    session_id = generate_session_id()
    now = datetime.now(timezone.utc).isoformat()
    metadata = {
        "session_id": session_id,
        "status": "active",
        "start_time": now,
        "end_time": None,
        "config": config,
    }
    sessions = _load_sessions(filepath)
    sessions[session_id] = metadata
    _save_sessions(sessions, filepath)
    # Also update the simple current-session pointer for backward compat
    save_current_session(session_id)
    return metadata


def get_session_status(session_id: str, filepath: str | None = None) -> dict | None:
    """Retrieve the status of a session by ID.

    Args:
        session_id: The session ID to look up.
        filepath: Optional override for the sessions registry file path.

    Returns:
        The session metadata dict, or None if the session ID is not found.
    """
    sessions = _load_sessions(filepath)
    return sessions.get(session_id)


def end_session(session_id: str, filepath: str | None = None) -> dict | None:
    """End an active session.

    Sets the session's status to ``"ended"`` and records the end_time.

    Args:
        session_id: The session ID to end.
        filepath: Optional override for the sessions registry file path.

    Returns:
        The updated metadata dict, or None if the session ID is not found.
    """
    sessions = _load_sessions(filepath)
    if session_id not in sessions:
        return None
    sessions[session_id]["status"] = "ended"
    sessions[session_id]["end_time"] = datetime.now(timezone.utc).isoformat()
    _save_sessions(sessions, filepath)
    return sessions[session_id]


def list_sessions(filepath: str | None = None) -> list[dict]:
    """List all sessions in the registry.

    Args:
        filepath: Optional override for the sessions registry file path.

    Returns:
        A list of session metadata dicts, sorted by start_time descending.
    """
    sessions = _load_sessions(filepath)
    result = list(sessions.values())
    result.sort(key=lambda s: s.get("start_time", ""), reverse=True)
    return result


def _cli(argv=None) -> int:
    """CLI entry point for session management.

    Subcommands (lifecycle):
        python3 tools/session_manager.py start
        python3 tools/session_manager.py status <session_id>
        python3 tools/session_manager.py end <session_id>
        python3 tools/session_manager.py list

    Legacy flag-style:
        python3 tools/session_manager.py --new-session
        python3 tools/session_manager.py --current-session
        python3 tools/session_manager.py --set-session <id>
    """
    import argparse
    import sys

    parser = argparse.ArgumentParser(
        prog="session_manager",
        description="Manage capture session IDs (HOST-3).",
    )

    # Subcommands for lifecycle management
    sub = parser.add_subparsers(dest="command")
    sub_start = sub.add_parser("start", help="Start a new capture session.")
    sub_start.add_argument("--config-id", default=None, help="Optional config identifier.")
    sub_status = sub.add_parser("status", help="Get session status.")
    sub_status.add_argument("session_id", help="The session ID to look up.")
    sub_end = sub.add_parser("end", help="End an active session.")
    sub_end.add_argument("session_id", help="The session ID to end.")
    sub.add_parser("list", help="List all sessions.")

    # Legacy flag-style args (mutually exclusive with subcommands)
    grp = parser.add_mutually_exclusive_group(required=False)
    grp.add_argument(
        "--new-session",
        action="store_true",
        help="Generate a new session_id and set it as current.",
    )
    grp.add_argument(
        "--current-session",
        action="store_true",
        help="Print the current session_id (from ~/.balloon/session.json).",
    )
    grp.add_argument(
        "--set-session",
        metavar="ID",
        help="Set the current session_id to the given value.",
    )

    args = parser.parse_args(argv)

    # Handle subcommands first
    if args.command == "start":
        config = {"config_id": args.config_id} if args.config_id else None
        metadata = start_session(config=config)
        print(metadata["session_id"])
        return 0

    if args.command == "status":
        metadata = get_session_status(args.session_id)
        if metadata is None:
            print(f"Session not found: {args.session_id}", file=sys.stderr)
            return 1
        print(json.dumps(metadata, indent=2))
        return 0

    if args.command == "end":
        metadata = end_session(args.session_id)
        if metadata is None:
            print(f"Session not found: {args.session_id}", file=sys.stderr)
            return 1
        print(json.dumps(metadata, indent=2))
        return 0

    if args.command == "list":
        sessions = list_sessions()
        if not sessions:
            print("(no sessions)")
            return 0
        for s in sessions:
            print(f"  {s['session_id']}  {s['status']:8s}  "
                  f"start={s.get('start_time', '?')}")
        return 0

    # Legacy flag-style commands
    if args.new_session:
        sid = new_session()
        print(sid)
        return 0
    if args.current_session:
        sid = load_current_session()
        if sid is not None:
            print(sid)
            return 0
        print("(no current session)", file=sys.stderr)
        return 1
    if args.set_session is not None:
        set_session(args.set_session)
        print(args.set_session)
        return 0

    parser.print_help(sys.stderr)
    return 2


if __name__ == "__main__":
    import sys
    sys.exit(_cli())