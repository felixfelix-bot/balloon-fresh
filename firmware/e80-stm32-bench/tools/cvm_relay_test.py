#!/usr/bin/env python3
"""cvm_relay_test.py — test relay connectivity + measure latency for CVM.

Pings each relay, sends a gift-wrapped kind 1059 to itself (round-trip),
reports working relays and average RTT. Writes a JSON summary.

Usage:
    python3 cvm_relay_test.py
    python3 cvm_relay_test.py --relays wss://relay.primal.net,wss://nostr.mom
    python3 cvm_relay_test.py --json   # machine-readable output
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import time
from datetime import timedelta

_TOOLS_DIR = os.path.dirname(os.path.abspath(__file__))
if _TOOLS_DIR not in sys.path:
    sys.path.insert(0, _TOOLS_DIR)

from cvm_board_server import DEFAULT_RELAYS, KIND_CVM_RPC, KIND_GIFT_WRAP


async def test_one_relay(url: str) -> dict:
    """Connect to a single relay, send a gift-wrap to self, measure RTT."""
    import nostr_sdk
    result = {"url": url, "ok": False, "rtt_s": None,
              "error": None, "connected": False}
    try:
        # Generate ephemeral keys for this test
        keys = nostr_sdk.Keys.generate()
        signer = nostr_sdk.NostrSigner.keys(keys)
        client = nostr_sdk.ClientBuilder().signer(signer).build()
        await client.add_relay(nostr_sdk.RelayUrl.parse(url))
        result["connect_t0"] = time.monotonic()
        await asyncio.wait_for(client.connect(), timeout=10)
        result["connect_dt"] = time.monotonic() - result["connect_t0"]
        result["connected"] = True

        # Subscribe to our own gift wraps (broad — filter p tag)
        f = nostr_sdk.Filter().kinds([nostr_sdk.Kind(KIND_GIFT_WRAP)])
        await client.subscribe(f, None)
        await asyncio.sleep(0.5)  # let subscription propagate

        # Send a gift-wrapped ping to OURSELVES
        recv_future: asyncio.Future = asyncio.get_event_loop().create_future()

        class SelfHandler(nostr_sdk.HandleNotification):
            async def handle(self, relay_url, subscription_id, event):
                p_tag = None
                for tag in event.tags().to_vec():
                    v = tag.as_vec()
                    if v and v[0] == "p" and len(v) >= 2:
                        p_tag = v[1]
                        break
                if p_tag != keys.public_key().to_hex():
                    return
                if not recv_future.done():
                    recv_future.set_result(event)

            async def handle_msg(self, relay_url, msg):
                return None

        handler = SelfHandler()
        notif_task = asyncio.create_task(client.handle_notifications(handler))

        # Build inner event (kind 25910)
        inner = nostr_sdk.UnsignedEvent.from_json(json.dumps({
            "pubkey": keys.public_key().to_hex(),
            "kind": KIND_CVM_RPC,
            "tags": [["p", keys.public_key().to_hex()]],
            "content": json.dumps({"ping": "cvm-relay-test", "ts": time.time()}),
            "created_at": nostr_sdk.Timestamp.now().as_secs(),
        }))
        t_send = time.monotonic()
        gw = await nostr_sdk.gift_wrap(signer, keys.public_key(), inner)
        await asyncio.wait_for(client.send_event(gw), timeout=10)

        # Wait for self-receipt (5s budget for round-trip via relay)
        await asyncio.wait_for(recv_future, timeout=5)
        result["rtt_s"] = time.monotonic() - t_send
        result["ok"] = True

        notif_task.cancel()
        try:
            await notif_task
        except asyncio.CancelledError:
            pass
        await client.shutdown()
    except asyncio.TimeoutError as e:
        result["error"] = f"timeout: {e}"
        if result["rtt_s"] is None:
            result["rtt_s"] = None
    except Exception as e:
        result["error"] = f"{type(e).__name__}: {e}"
    return result


async def main_async(relays: list[str], json_out: bool = False) -> int:
    print(f"CVM Relay Connectivity Test — {len(relays)} relay(s)",
          file=sys.stderr)
    results = []
    for url in relays:
        print(f"  Testing {url} ... ", end="", file=sys.stderr, flush=True)
        r = await asyncio.wait_for(test_one_relay(url), timeout=30)
        if r["ok"]:
            print(f"OK  rtt={r['rtt_s']:.2f}s", file=sys.stderr)
        else:
            err = r.get("error", "?")[:60]
            print(f"FAIL  ({err})", file=sys.stderr)
        results.append(r)
    # Summary
    ok = [r for r in results if r["ok"]]
    fail = [r for r in results if not r["ok"]]
    print(file=sys.stderr)
    print(f"=== Summary ===", file=sys.stderr)
    print(f"  Working:  {len(ok)}/{len(results)}", file=sys.stderr)
    if ok:
        fastest = min(ok, key=lambda r: r["rtt_s"])
        avg = sum(r["rtt_s"] for r in ok) / len(ok)
        print(f"  Avg RTT:  {avg:.2f}s", file=sys.stderr)
        print(f"  Fastest:  {fastest['url']} ({fastest['rtt_s']:.2f}s)",
              file=sys.stderr)
    if fail:
        print(f"  Failed:", file=sys.stderr)
        for r in fail:
            print(f"    {r['url']}: {r.get('error', 'unknown')}", file=sys.stderr)
    if json_out:
        print(json.dumps(results, indent=2))
    return 0 if ok else 1


def main():
    ap = argparse.ArgumentParser(
        description="CVM relay connectivity + latency test")
    ap.add_argument("--relays", default=",".join(DEFAULT_RELAYS),
                    help="Comma-separated relay URLs (default: all known working)")
    ap.add_argument("--json", action="store_true",
                    help="Emit machine-readable JSON to stdout")
    ap.add_argument("--relays-include-failures", action="store_true",
                    help="Also test the documented broken relays "
                         "(wss://relay.contextvm.org, wss://relay.damus.io)")
    args = ap.parse_args()
    relays = [r.strip() for r in args.relays.split(",") if r.strip()]
    if args.relays_include_failures:
        relays.extend(["wss://relay.contextvm.org", "wss://relay.damus.io"])
    return asyncio.run(main_async(relays, json_out=args.json))


if __name__ == "__main__":
    sys.exit(main())
