"""Session manager — HOST-3.

Generates and injects a unique session_id into capture sessions.

The session_id is a UUID4 string that identifies a single capture run.
It is written to the output file as a ``SESSION_START`` header line and
injected into every PKT line's ``session_id`` field (field 1 after
``PKT,``).

Usage:
    from tools.session_manager import generate_session_id, format_session_start

    session_id = generate_session_id()
    header = format_session_start(session_id)
    # write header to CSV, then inject session_id into each PKT line
"""

import uuid
from datetime import datetime, timezone


def generate_session_id() -> str:
    """Generate a unique session_id (UUID4 string).

    Returns:
        A string like ``"550e8400-e29b-41d4-a716-446655440000"``.
    """
    return str(uuid.uuid4())


def format_session_start(session_id: str) -> str:
    """Format the SESSION_START header line.

    Args:
        session_id: The session UUID string from generate_session_id().

    Returns:
        A line in the format ``SESSION_START,<uuid>,<iso-timestamp>\\n``
        where the timestamp is a UTC ISO-8601 string.
    """
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
        session_id: The session UUID to inject.

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