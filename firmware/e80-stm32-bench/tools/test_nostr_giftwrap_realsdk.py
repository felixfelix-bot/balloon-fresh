#!/usr/bin/env python3
"""Real-``nostr_sdk`` end-to-end test for the NIP-59 gift-wrap layer.

Card t_88b2e58f (e80-bench). ``test_nostr_giftwrap.py`` pins the call shape
against a fake SDK, because the CI image has no Rust bindings. That fake hid a
real defect once (``event_view`` used ``list(tag)`` while the binding's ``Tag``
is not iterable), so this module runs the **actual** NIP-59 cryptography
whenever ``nostr_sdk`` is importable and is skipped otherwise.

It builds a real kind-1059 wrap for a real TX npub and checks the card's
acceptance criteria on the real emitted event:

  * outer kind == 1059
  * outer ``p`` tag == the TX npub (hex)
  * the ARMED payload is not visible in plaintext in tag/content
  * the intended recipient can unwrap it and read back the payload
  * publishing any non-1059 kind raises and nothing reaches the client

Run:  python3 -m unittest test_nostr_giftwrap_realsdk -v
(or:  python3 -m pytest test_nostr_giftwrap_realsdk.py -v)
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
import unittest

_TOOLS_DIR = os.path.dirname(os.path.abspath(__file__))
if _TOOLS_DIR not in sys.path:
    sys.path.insert(0, _TOOLS_DIR)

import nostr_giftwrap as gw  # noqa: E402

try:  # the whole module is a no-op without the Rust bindings
    import nostr_sdk  # type: ignore
except ImportError:  # pragma: no cover - exercised in the bare CI image
    nostr_sdk = None

ARMED_PAYLOAD = {
    "type": "ARMED",
    "session_id": "realsdk0000001",
    "stop": "stop-50m",
    "t_ready_utc": 1789000000,
    "preset_hash": "feedfacecafe0002",
    "seq": 11,
    "created_at": 1788999990,
}


class FakeClient:
    def __init__(self):
        self.sent = []

    async def send_event(self, event):
        self.sent.append(event)


@unittest.skipUnless(nostr_sdk is not None, "nostr_sdk not installed")
class TestRealNostrSdkGiftWrap(unittest.TestCase):

    def setUp(self):
        self.sender = nostr_sdk.Keys.generate()
        self.signer = nostr_sdk.NostrSigner.keys(self.sender)
        self.tx = nostr_sdk.Keys.generate()
        self.tx_npub = self.tx.public_key().to_bech32()
        self.tx_hex = self.tx.public_key().to_hex()
        self.payload = dict(ARMED_PAYLOAD,
                            author=self.sender.public_key().to_hex())

    def _wrap(self):
        return asyncio.run(gw.build_gift_wrap(
            self.payload, self.tx_npub, self.signer,
            author=self.sender.public_key().to_hex()))

    def test_outer_event_is_kind_1059(self):
        event = self._wrap()
        self.assertEqual(int(event.kind().as_u16()), gw.KIND_GIFT_WRAP)
        self.assertEqual(gw.event_view(event)["kind"], 1059)

    def test_outer_ptag_is_the_tx_npub(self):
        event = self._wrap()
        tags = [t.as_vec() for t in event.tags().to_vec()]
        self.assertEqual([t[1] for t in tags if t[0] == "p"], [self.tx_hex])
        self.assertEqual(gw.assert_recipient_tag(event, self.tx_npub),
                         self.tx_hex)

    def test_no_plaintext_fragment_in_tags_or_content(self):
        event = self._wrap()
        self.assertTrue(gw.assert_no_plaintext_leak(event, self.payload))
        haystack = event.content() + json.dumps(
            [t.as_vec() for t in event.tags().to_vec()])
        for fragment in ("realsdk0000001", "feedfacecafe0002", "stop-50m",
                         "ARMED", "session_id", "preset_hash"):
            self.assertNotIn(fragment, haystack)
        self.assertNotIn(json.dumps(self.payload), haystack)

    def test_recipient_unwraps_and_reads_the_payload(self):
        event = self._wrap()
        unwrapped = asyncio.run(nostr_sdk.UnwrappedGift.from_gift_wrap(
            nostr_sdk.NostrSigner.keys(self.tx), event))
        rumor = unwrapped.rumor()
        self.assertEqual(int(rumor.kind().as_u16()), gw.INNER_KIND)
        self.assertEqual(json.loads(rumor.content()), self.payload)
        self.assertEqual(unwrapped.sender().to_hex(),
                         self.sender.public_key().to_hex())

    def test_wrong_recipient_cannot_unwrap(self):
        event = self._wrap()
        other = nostr_sdk.Keys.generate()
        with self.assertRaises(Exception):
            asyncio.run(nostr_sdk.UnwrappedGift.from_gift_wrap(
                nostr_sdk.NostrSigner.keys(other), event))

    def test_publishing_the_wrap_sends_exactly_once(self):
        client = FakeClient()
        event = self._wrap()
        asyncio.run(gw.publish_gift_wrap(client, event, payload=self.payload,
                                        tx_npub=self.tx_npub))
        self.assertEqual(client.sent, [event])

    def test_real_signed_kind_30315_is_refused(self):
        client = FakeClient()
        builder = nostr_sdk.EventBuilder(kind=nostr_sdk.Kind(30315),
                                         content="plaintext tally")
        plaintext = builder.sign(self.signer)
        if asyncio.iscoroutine(plaintext):
            plaintext = asyncio.run(plaintext)
        with self.assertRaises(gw.PlaintextKindError) as ctx:
            asyncio.run(gw.publish_gift_wrap(client, plaintext))
        self.assertEqual(client.sent, [], "nothing may reach the relay")
        self.assertIn("30315", str(ctx.exception))
        self.assertIn("FORBIDDEN", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
