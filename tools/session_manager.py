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