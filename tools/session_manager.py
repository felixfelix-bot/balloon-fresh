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


def _cli(argv=None) -> int:
    """CLI entry point for session management.

    Usage:
        python -m tools.session_manager --new-session
        python -m tools.session_manager --current-session
        python -m tools.session_manager --set-session <id>
    """
    import argparse

    parser = argparse.ArgumentParser(
        prog="session_manager",
        description="Manage capture session IDs (HOST-3).",
    )
    grp = parser.add_mutually_exclusive_group(required=True)
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

    if args.new_session:
        sid = new_session()
        print(sid)
        return 0
    if args.current_session:
        sid = load_current_session()
        if sid is not None:
            print(sid)
            return 0
        print("(no current session)", file=__import__("sys").stderr)
        return 1
    if args.set_session is not None:
        set_session(args.set_session)
        print(args.set_session)
        return 0
    return 2


if __name__ == "__main__":
    import sys
    sys.exit(_cli())