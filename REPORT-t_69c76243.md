# REPORT — t_69c76243: fake relay transport double (ACCEPT/TIMEOUT/HARD_ERROR_RAISE/HARD_ERROR_REJECT)

**Card:** `t_69c76243` (board `e80-bench`)
**Branch:** `pr/fake-relay-transport-double` **Stacked base:** `pr/relay-scaffold-testkit` (tip `469c5b2e`)
**Repo:** `~/repos/balloon-e80bench` (github.com/felixfelix-bot/balloon-fresh)
**Worktree:** `~/worktrees/t_69c76243-fake-relay`

## Deliverable & import path

- **File (extended, not duplicated):** `firmware/e80-stm32-bench/tools/relay_testkit.py`
- **New pins:** `firmware/e80-stm32-bench/tools/test_fake_relay_transport.py`
- **Import path (verbatim):** `from relay_testkit import FakeRelayTransport, SyncFakeRelayTransport`
  (same package/tests tree as the sibling relay-failover tests: `tools/`; sibling
  suite `tools/test_relay_failover_publisher.py`, production `tools/relay_failover.py`.)

The card's suggested `<pkg>/_fake_relay.py` name was **not** used on purpose: an importable fake
relay double already exists in this tree (`relay_testkit.py`, card `t_588b1d1b`, branch
`pr/relay-scaffold-testkit`) as the single declared source of truth for the fan-out. Shipping a
second module would have duplicated it. Instead this card EXTENDS that module to the exact contract
requested, keeping one double.

## Step 1 — matched production signature

Read `relay_failover.py` (production fan-out) and `test_relay_failover_publisher.py` (sibling test).
The transport injection point is:

```
RelayFailoverPublisher(transport, timeout=5.0, relays=None, ...)
    _send_one: await asyncio.wait_for(self.transport.send(url, event), self.timeout)
```

- The double must expose `async def send(self, url: str, event: dict) -> list`
  (URL first, event dict second). **Async**, matching the production `await`.
- Relays are keyed by **full relay URL** (`wss://host`), default `ACCEPT`.
- A relay that *raises* → failure (reason `error: <Type>: <msg>`); `asyncio.TimeoutError` → `timeout`;
  a raised `RelayRejected` → `rejected: <msg>`; any non-raising return → accepted.
- A sync twin (`SyncFakeRelayTransport.send`) is provided for synchronous callers.

**Honest seam finding:** the publisher does NOT consume the returned NIP-01 frame — `_send_one`
treats any non-raising return as accepted. Refusal on the publisher seam is signalled by *raising*
`relay_failover.RelayRejected` (that is what the sibling test's transport does). The double still
returns the required rejection envelope (`HARD_ERROR_REJECT`) because that is the wire shape the card
demands and what a transport-layer caller sees; both shapes are pinned in
`test_fake_relay_transport.py::TestSeamNuance`. Consequence for a caller: to exercise the
publisher's reject-aggregation path, raise `RelayRejected`; to assert the wire envelope, call the
double directly.

## Behaviours implemented (per-relay injectable, default ACCEPT)

| Behaviour | Result |
|---|---|
| `ACCEPT` | `["OK", <event_id>, True, ""]` — `<event_id>` parsed from `event["id"]` (real 64-char lowercase hex), never hardcoded |
| `TIMEOUT` | awaits a never-set `asyncio.Event`; caller's `wait_for` deadline cancels it; `CancelledError` propagates, no task spawned (sync twin raises `TimeoutError`) |
| `HARD_ERROR_RAISE` | raises `ConnectionRefusedError` (an `OSError`) |
| `HARD_ERROR_REJECT` | `["OK", <event_id>, False, "blocked: ..."]`, reason prefixed exactly `"blocked: "` |

Back-compat aliases kept so the pre-existing sibling pins and older behaviour maps still work:
`HARD_ERROR = HARD_ERROR_RAISE`, `BLOCKED = HARD_ERROR_REJECT`, and string aliases
`"hard_error"`/`"blocked"` normalised on lookup.

Call log: `.calls = [(url, event_id), ...]` (ordered, 2-tuple, back-compat) and
`.attempts = [(url, event_id, seq), ...]` (3-tuple, `seq` = deterministic 0-based counter — a
reproducible timestamp substitute). `.reset()` / `.clear()` empties both and restarts `seq`.

Determinism: no sockets, no DNS, no randomness, no sleeps except the intentional never-resolving
TIMEOUT wait. **Hard no-network guarantee** stated in the module docstring and pinned by an AST scan
(`TestNoNetworkGuarantee`) that rejects imports of `socket/ssl/aiohttp/httpx/urllib3/urllib/http/...`
and calls to `open_connection/create_connection/getaddrinfo/gethostbyname`. The docstring documents
the injection-map format, each behaviour, the call-log shape, and a copy-pasteable example.

## Acceptance evidence

Import (exit status 0):

```
$ cd firmware/e80-stm32-bench/tools
$ python3 -c "from relay_testkit import FakeRelayTransport, SyncFakeRelayTransport"
import exit=0
```

All four behaviours (real 64-char event id `0011...eeff`):

```
event id in: 00112233445566778899aabbccddeeff00112233445566778899aabbccddeeff len 64
ACCEPT           -> ['OK', '00112233445566778899aabbccddeeff00112233445566778899aabbccddeeff', True, '']
HARD_ERROR_RAISE -> ConnectionRefusedError: relay unreachable: wss://nostr.mom
HARD_ERROR_REJECT-> ['OK', '00112233445566778899aabbccddeeff00112233445566778899aabbccddeeff', False, 'blocked: relay policy for wss://relay.nostr.band']
TIMEOUT          -> task.done() after 1 tick: False
TIMEOUT          -> cancelled cleanly (CancelledError propagated)
TIMEOUT          -> pending tasks after cancel: []
calls    : [('wss://nos.lol', '0011...eeff'), ('wss://nostr.mom', '...'), ('wss://relay.nostr.band', '...'), ('wss://relay.primal.net', '...')]
attempts : [('wss://nos.lol', '...', 0), ('wss://nostr.mom', '...', 1), ('wss://relay.nostr.band', '...', 2), ('wss://relay.primal.net', '...', 3)]
after reset calls: [] attempts: []
```

Tests:

```
$ python3 -m pytest test_fake_relay_transport.py test_relay_testkit.py test_relay_failover_publisher.py -q
45 passed
$ python3 -m pytest . -q          # whole tools/ suite
885 passed, 1 skipped in 13.21s
```

RED→GREEN: `test_fake_relay_transport.py` first run = **8 failed, 3 passed** (AttributeError on
`HARD_ERROR_RAISE`/`HARD_ERROR_REJECT`, missing `reset`); after extending `relay_testkit.py` =
**13 passed**; sibling `test_relay_testkit.py` 13 passed unchanged.

## Commands run (verbatim, in order)

```
git worktree add ~/worktrees/t_69c76243-fake-relay -b pr/fake-relay-transport-double origin/pr/relay-scaffold-testkit
python3 -m pytest test_fake_relay_transport.py -q                       # RED: 8 failed, 3 passed
python3 -m pytest test_fake_relay_transport.py test_relay_testkit.py -q # GREEN after impl
python3 -m pytest test_fake_relay_transport.py test_relay_testkit.py test_relay_failover_publisher.py -q
python3 -m pytest . -q
python3 -c "from relay_testkit import FakeRelayTransport, SyncFakeRelayTransport"
python3 -c "<four-behaviour transcript above>"
```

## Remaining / follow-up

- The publisher-ignores-frame nuance (above) is a production-side gap owned by the relay-failover
  publisher card; this card deliberately did not edit `relay_failover.py` (its deliverable, and a
  parallel PR).
