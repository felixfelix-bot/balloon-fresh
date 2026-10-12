"""Bind-safety guards for the unauthenticated E80 board TCP server (E80-2026-01).

These assert the safe default and the exposure warning, so the channel cannot
silently revert to binding all interfaces without an explicit opt-in and a
warning. See `docs/SECURITY-FINDINGS.md` and issue #21.
"""
import io
from contextlib import redirect_stderr

import e80_board_server as srv


def test_default_bind_is_loopback():
    # host is the first default of BoardTCPServer.__init__(controller, host=...)
    assert srv.BoardTCPServer.__init__.__defaults__[0] == "127.0.0.1"


def test_run_server_default_host_is_loopback():
    assert srv.run_server.__defaults__[-1] == "127.0.0.1"


def test_is_loopback_host():
    for host in ("127.0.0.1", "localhost", "::1", "", "  127.0.0.1  "):
        assert srv.is_loopback_host(host), host
    for host in ("0.0.0.0", "192.168.1.10", "10.0.0.5", "::"):
        assert not srv.is_loopback_host(host), host


def test_non_loopback_emits_warning():
    buf = io.StringIO()
    with redirect_stderr(buf):
        warned = srv.warn_if_unauthenticated_exposure("0.0.0.0", 7780)
    assert warned is True
    out = buf.getvalue()
    assert "UNAUTHENTICATED" in out
    assert "0.0.0.0:7780" in out


def test_loopback_emits_no_warning():
    buf = io.StringIO()
    with redirect_stderr(buf):
        warned = srv.warn_if_unauthenticated_exposure("127.0.0.1", 7780)
    assert warned is False
    assert buf.getvalue() == ""
