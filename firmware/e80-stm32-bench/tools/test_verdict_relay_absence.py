#!/usr/bin/env python3
"""test_verdict_relay_absence.py — the relay set must never contain the DEAD
unnumbered ``contextvm`` host.

Regression guard for the verdict transport's relay failover set
(``firmware/e80-stm32-bench/tools/verdict_transport.py``, NIP-59 kind 1059
publisher). The canonical list lives once, in ``verdict_relay_constants``.

Two independent angles, both required:

(a) **Runtime** — no member of ``FAILOVER_RELAYS`` equals the forbidden host,
    compared as a bare host and ignoring an optional ``:port`` suffix, so a
    URL form (``wss://…``), a port-bearing form (``…:443``) or a trailing dot
    cannot smuggle it past a naive string compare.

(b) **Source** — the *defining* source file (the module that actually holds the
    literal list, ``verdict_relay_constants.py``) contains no occurrence of the
    hostname at a hostname boundary, via the regex::

        (?<![a-z0-9.-])relay\\.contextvm\\.org(?![a-z0-9.-])

    The two lookarounds are the point: the legitimate, ALIVE
    ``relay2.contextvm.org`` must NOT false-positive (the ``2`` sits where the
    forbidden host has its ``.``), while ``relay.contextvm.org`` — bare, as a
    URL, with a port, or embedded in a longer label — is caught.

Run::

    python3 -m pytest -q firmware/e80-stm32-bench/tools/test_verdict_relay_absence.py
"""

from __future__ import annotations

import os
import re
import sys
import unittest

_TOOLS_DIR = os.path.dirname(os.path.abspath(__file__))
if _TOOLS_DIR not in sys.path:
    sys.path.insert(0, _TOOLS_DIR)

import verdict_relay_constants as vrc  # noqa: E402
import verdict_transport as vt  # noqa: E402

#: The forbidden host — the DEAD unnumbered member of the contextvm family.
FORBIDDEN_HOST = "relay.contextvm.org"

#: The ALIVE numbered sibling that must keep passing this scan.
ALIVE_HOST = "relay2.contextvm.org"

#: The exact boundary regex required by the acceptance criteria.
FORBIDDEN_HOST_RE = re.compile(
    r"(?<![a-z0-9.-])relay\.contextvm\.org(?![a-z0-9.-])"
)


def _bare_host(value) -> str:
    """Bare lowercase host of a relay entry or URL (port/path stripped)."""
    text = str(value).strip()
    if "://" in text:
        text = text.split("://", 1)[1]
    text = text.split("/", 1)[0]      # drop any path
    text = text.split("@", 1)[-1]     # drop any userinfo
    # IPv6 literals keep their brackets; a lone ':' separates a port.
    if text.count(":") == 1:
        text = text.split(":", 1)[0]
    return text.rstrip(".").lower()


class TestForbiddenRelayAbsenceRuntime(unittest.TestCase):
    """(a) No runtime entry in the failover set is the dead host."""

    def test_forbidden_relay_host_is_not_a_member_of_failover_relays(self):
        hosts = [str(entry) for entry in vt.FAILOVER_RELAYS]
        self.assertNotIn(FORBIDDEN_HOST, hosts)
        for entry in hosts:
            self.assertNotEqual(_bare_host(entry), FORBIDDEN_HOST,
                                "%r resolves to the DEAD relay host" % entry)

    def test_forbidden_relay_host_is_not_a_member_of_derived_urls(self):
        for url in vt.FAILOVER_RELAY_URLS:
            self.assertNotEqual(_bare_host(url), FORBIDDEN_HOST,
                                "%r resolves to the DEAD relay host" % url)

    def test_forbidden_relay_host_boundary_compare_ignores_port_and_scheme(self):
        """Even a port/scheme-bearing form must not sneak the host in."""
        for entry in list(vt.FAILOVER_RELAYS) + list(vt.FAILOVER_RELAY_URLS):
            text = str(entry)
            for decoration in ("", ":443", ":9735", "/", "."):
                self.assertNotEqual(_bare_host(text + decoration),
                                    FORBIDDEN_HOST)

    def test_alive_numbered_contextvm_host_is_still_present(self):
        """Non-vacuity: the live sibling is in the set at its pinned index."""
        hosts = [str(entry) for entry in vt.FAILOVER_RELAYS]
        self.assertIn(ALIVE_HOST, hosts)
        self.assertEqual(hosts.index(ALIVE_HOST), 3)


class TestForbiddenRelayAbsenceInSource(unittest.TestCase):
    """(b) The DEFINING source file names no forbidden host at a boundary."""

    def _defining_source_path(self):
        """The file that actually defines the relay list literal."""
        return os.path.abspath(vrc.__file__)

    def test_defining_source_file_has_no_forbidden_host_literal(self):
        path = self._defining_source_path()
        with open(path, "r", encoding="utf-8") as handle:
            source = handle.read()
        hits = FORBIDDEN_HOST_RE.findall(source)
        self.assertEqual(
            hits, [],
            "%s names the DEAD relay host at a hostname boundary: %r"
            % (os.path.basename(path), hits))

    def test_source_scan_regex_does_not_false_positive_on_the_alive_host(self):
        """Non-vacuity: the regex is inert for ``relay2`` but live for the bare
        host, in every decoration a leak could take."""
        dead_forms = [
            "relay.contextvm.org",
            "wss://relay.contextvm.org",
            "wss://relay.contextvm.org:443",
            "relay.contextvm.org/",
            '"relay.contextvm.org"',
        ]
        for form in dead_forms:
            self.assertTrue(FORBIDDEN_HOST_RE.search(form),
                            "regex failed to catch %r" % form)
        alive_forms = [
            "relay2.contextvm.org",
            "wss://relay2.contextvm.org",
            "relay12.contextvm.org",
        ]
        for form in alive_forms:
            self.assertIsNone(FORBIDDEN_HOST_RE.search(form),
                              "regex false-positived on %r" % form)

    def test_defining_source_file_holds_the_alive_host(self):
        """The defining file is genuinely the relay-list source (has relay2)."""
        with open(self._defining_source_path(), "r", encoding="utf-8") as fh:
            source = fh.read()
        self.assertIn(ALIVE_HOST, source)

    def test_canonical_constant_is_defined_in_the_scanned_file(self):
        """``FAILOVER_RELAYS`` really originates in the scanned module."""
        self.assertIs(vt.FAILOVER_RELAYS, vrc.FAILOVER_RELAYS)
        self.assertEqual([str(h) for h in vrc.FAILOVER_RELAYS],
                         [str(h) for h in vt.FAILOVER_RELAYS])


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
