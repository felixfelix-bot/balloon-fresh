#!/usr/bin/env python3
"""test_failover_relays_constant.py — single-source relay-set contract (t_7c9268b7).

Pins the ONE authoritative, module-level relay-set constant consumed by the
Nostr NIP-59 kind-1059 gift-wrap publishing path (``cvm_armed_publisher`` /
``relay_failover``) and by every failover test:

  * ``FAILOVER_RELAYS`` is the canonical value: FIVE *bare* hostnames, in the
    exact contractual order — no scheme, no port, no trailing slash and no
    normalisation;
  * ``FAILOVER_RELAY_URLS`` is DERIVED from it (``wss://<host>``) so the host
    and URL views can never drift apart;
  * the publisher's own ``failover_relays()`` returns exactly that URL view.

The exact value AND order are pinned by a SHA-256 digest of the canonical list
so this test fails if the constant is ever silently edited *without* keeping a
second literal copy of the relay set in the tools tree.

Runs hermetically: no ``nostr_sdk``, no sockets.

Run:  python3 -m pytest tools/test_failover_relays_constant.py -v
"""

from __future__ import annotations

import hashlib
import json
import os
import sys
import unittest

_TOOLS_DIR = os.path.dirname(os.path.abspath(__file__))
if _TOOLS_DIR not in sys.path:
    sys.path.insert(0, _TOOLS_DIR)

from cvm_armed_publisher import (  # noqa: E402
    FAILOVER_RELAY_URLS,
    FAILOVER_RELAYS,
    failover_relays,
)

#: sha256 of the canonical host list serialised as ordered JSON. Pins value
#: AND order without restating a single hostname (see module docstring).
EXPECTED_HOSTS_SHA256 = (
    "109e156e41fb5d2b440e563faad9b7a98f4204ac93d965a16c41eb8559d48a48"
)
EXPECTED_URLS_SHA256 = (
    "56542e03b8c9d0becd390f311b446f2bbeafcb5073a2d5519ce077deae6c26f5"
)


def _digest(seq) -> str:
    return hashlib.sha256(
        json.dumps(list(seq), separators=(",", ":")).encode("utf-8")
    ).hexdigest()


class TestFailoverRelaysConstant(unittest.TestCase):
    """The canonical bare-host constant: value, order and shape."""

    def test_exactly_five_entries(self):
        self.assertEqual(len(FAILOVER_RELAYS), 5)

    def test_fourth_entry_is_relay2_contextvm_org(self):
        # the legitimate relay that must NOT be mistaken for the dead host
        self.assertEqual(FAILOVER_RELAYS[3], "relay2.contextvm.org")

    def test_every_entry_is_a_bare_hostname(self):
        for host in FAILOVER_RELAYS:
            self.assertIsInstance(host, str)
            self.assertTrue(host, "empty relay entry")
            self.assertNotIn("://", host, "scheme leaked into bare host")
            self.assertNotIn("/", host, "path/slash leaked into bare host")
            self.assertNotIn(":", host, "port leaked into bare host")
            self.assertEqual(host, host.strip())
            self.assertEqual(host, host.lower())

    def test_value_and_order_are_pinned(self):
        self.assertEqual(_digest(FAILOVER_RELAYS), EXPECTED_HOSTS_SHA256,
                         "FAILOVER_RELAYS was silently changed")

    def test_relay_urls_are_derived_from_the_hosts(self):
        self.assertEqual(FAILOVER_RELAY_URLS,
                         ["wss://" + host for host in FAILOVER_RELAYS])
        self.assertEqual(_digest(FAILOVER_RELAY_URLS), EXPECTED_URLS_SHA256)

    def test_publisher_returns_the_canonical_url_view(self):
        self.assertEqual(failover_relays(), FAILOVER_RELAY_URLS)


if __name__ == "__main__":
    unittest.main()
