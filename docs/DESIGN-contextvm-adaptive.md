# CVM Adaptive Range Test Architecture

**Status:** implemented (2026-08-23)
**Branch:** `feat/2g4-sweep`
**Firmware:** `0561b29` (no flashing required)

## 1. Overview

The E80 bench has two boards (TX and RX) that today must be driven from a
single Python process because `arm_and_stream()` opens both serial ports in
the same interpreter. For outdoor range tests the TX and RX boards are on
**different machines behind different NATs** — a single-process controller is
not viable, and SSH tunnels between the machines are fragile.

This design replaces the in-process serial calls with **ContextVM (CVM)** —
MCP-over-Nostr tool calls. Each machine runs a small "CVM board server" that
owns its local serial port + SWD probe and exposes a fixed tool surface via
gift-wrapped JSON-RPC events on Nostr relays. A coordinator process (running
on either machine) calls both board servers over Nostr, runs the same SPRT
adaptive loop that `e80_campaign.py` already implements, and writes the same
CSV/Markdown reports.

```
                              Nostr relays
                       ┌──────────────────────┐
                       │  wss://relay.primal  │
                       │  wss://nostr.mom     │
                       │  wss://nos.lol       │
                       │  wss://relay2.cvm    │
                       │  wss://relay.nostr.b │
                       └───┬──────────────┬───┘
                           │              │
            gift-wrapped   │              │   gift-wrapped
            JSON-RPC 25910 │              │   JSON-RPC 25910
            in kind 1059   │              │   in kind 1059
                           ▼              ▼
        ┌─────────────────────┐    ┌─────────────────────┐
        │ TX machine          │    │ RX machine          │
        │ cvm_board_server    │    │ cvm_board_server    │
        │   ROLE=tx           │    │   ROLE=rx           │
        │ board_query/send/   │    │ board_query/capture/│
        │ start_burst/swd_    │    │ stat/swd_reset      │
        │ reset/stat          │    │                     │
        │   │                 │    │   │                 │
        │  CH340 ── E80 (TX)  │    │  CH340 ── E80 (RX)  │
        │  Pico ── SWD        │    │  Pico ── SWD        │
        └─────────────────────┘    └─────────────────────┘

                       ┌──────────────────────┐
                       │ Coordinator          │
                       │ cvm_campaign.py      │
                       │   - build_campaign_  │
                       │     configs()        │
                       │   - sprt_decide()    │
                       │   - branch() /        │
                       │     cliff_search()   │
                       │   - CSV/MD report    │
                       └──────────────────────┘
            (runs on either machine; just needs Nostr reachability)
```

## 2. Why Nostr (not TCP/SSH)?

| Property                | TCP board server | CVM (Nostr)             |
|-------------------------|------------------|-------------------------|
| NAT traversal           | ❌ needs port fwd | ✅ outbound-only        |
| SSH required            | yes              | no                      |
| Discoverability         | IP + port        | npub (anyone with key)  |
| Privacy                 | plaintext        | NIP-44 gift wrap        |
| Multi-relay failover    | no               | yes                     |
| Latency (warm)          | <1 ms            | ~0.7 s                  |
| Latency (cold)          | <1 ms            | ~5-10 s                 |

The 0.7 s warm latency is acceptable: a single SPRT burst takes 1-50 s
depending on modulation; the relay overhead is a fixed ~1 s fixed cost per
round trip (TX arm, RX capture, RX stop).

## 3. Protocol

Verified working pattern (see
`~/.hermes/profiles/manager/skills/devops/contextvm/references/direct-nostr-implementation.md`)
— here reproduced for Python `nostr_sdk`.

### 3.1 Wire flow

```
1. Client builds JSON-RPC request:
   { "jsonrpc":"2.0", "method":"tools/call",
     "params":{ "name": "board_query", "arguments": { "line": "ID?" } },
     "id": 1 }

2. Client wraps as inner event (kind 25910), signed by client keys:
   { pubkey: <client_pk>, kind: 25910,
     tags: [["p", <server_pk>]],
     content: <JSON-RPC request>,
     created_at: <unix> }

3. Client gift-wraps (nostr_sdk.gift_wrap):
   - generates ephemeral wrap key
   - NIP-44 encrypts the signed inner event to server_pk
   - publishes kind 1059 with p tag = server_pk, signed by ephemeral key

4. Server (subscribed to broad kind 1059) receives wrap event.
   - Filters client-side: p tag must match server_pk
     (NIP-12 #p filter is unreliable for kind 1059 on some relays).

5. Server unwraps (nostr_sdk.UnwrappedGift.from_gift_wrap):
   - verifies NIP-44 conversation key (server_sk, wrap_event.author)
   - parses inner event, verifies inner signature
   - inner.author() = client_pk (used to address the reply)
   - parses JSON-RPC

6. Server executes tool, builds JSON-RPC response, sends back
   the same way (gift-wrapped to client_pk).

7. Client receives response, correlates by JSON-RPC id.
```

### 3.2 Python nostr-SDK primitives (verified)

| Concern              | nostr_sdk helper                              |
|----------------------|-----------------------------------------------|
| Key from hex         | `Keys.parse(hex_string)`                       |
| Signer from keys     | `NostrSigner.keys(keys)`                       |
| Build client w/signer| `ClientBuilder().signer(signer).build()`      |
| Add relay            | `client.add_relay(RelayUrl.parse(url))`        |
| Subscribe (broad)    | `client.subscribe(Filter().kinds([Kind(1059)]), None)` |
| Receive events       | `client.handle_notifications(HandleNotification instance)` |
| Build inner event   | `UnsignedEvent.from_json({...})` then `sign_with_keys(keys)` |
| Gift wrap + send     | `gift_wrap(signer, recipient_pk, unsigned)` + `client.send_event(gw)` |
| Unwrap received      | `UnwrappedGift.from_gift_wrap(signer, event)` |
| Get p tag            | `event.tags().to_vec()` → `tag.as_vec()`       |

### 3.3 Verified round-trip latency

End-to-end test on `wss://relay.primal.net` + `wss://nostr.mom`:
gift-wrapped `board_query` request → server processes → reply received by
client in **0.58 s**. Matches the "0.7 s warm" figure from the skill.

## 4. Key Management

### 4.1 Three keys, never reused

| Key            | Holder     | Used for                                    |
|----------------|------------|---------------------------------------------|
| `TX_SERVER_HEX`| TX machine | signs TX board server's inner events        |
| `RX_SERVER_HEX`| RX machine | signs RX board server's inner events        |
| `CLIENT_HEX`   | Coordinator| signs JSON-RPC requests (different from both servers) |

**MUST use different keys** — sharing a key causes the client to receive its
own requests and breaks correlation (verified gotcha in
direct-nostr-implementation.md).

### 4.2 Generation

```bash
nak key generate                 # prints nsec1... and npub1...
nak key convert <nsec1...> -t hex # gives the hex private key (32 bytes)
```

The CVM board server accepts:
- `--server-hex <64-char hex>` or `--nsec nsec1...`
- `CVM_SERVER_HEX` environment variable

The coordinator accepts:
- `--client-hex <64-char hex>` or `CVM_CLIENT_HEX` env
- `--tx-npub npub1...` and `--rx-npub npub1...` (recipient addresses)

### 4.3 Key separation rules

- **Never commit real keys to git.** Production keys live in
  `~/.config/e80-cvm/keys.env` (chmod 0600), sourced in Makefile via `include`.
- The test fixtures (`test_cvm_board_server.py`) generate ephemeral keys
  with `nostr_sdk.Keys.generate()` — no keys persist.
- For dev/demo, the Makefile `range-cvm-keys` target generates a 3-key set
  (tx server, rx server, coordinator) and writes them to a gitignored file.

## 5. Tools Exposed by the Board Server

Each tool is a single JSON-RPC `tools/call` with `name` + `arguments`.
Response is the standard MCP `result.content[0].text` JSON-encoded payload.

### 5.1 Common tools (both TX and RX)

| Tool              | Arguments                          | Returns                                       |
|-------------------|------------------------------------|-----------------------------------------------|
| `board_query`     | `{line: "...", prefixes: [...], timeout: float}`| `{ok, reply}` or `{ok:false, error}`     |
| `board_send`      | `{line: "...", timeout: float}`   | `{ok, reply}` (expects `OK`/`ERR` prefix)     |
| `board_stat`      | `{}`                               | `{ok, reply: "STAT n=N ...}"}`                |
| `board_swd_reset` | `{}`                               | `{ok}` or `{ok:false, error}`                |
| `board_info`      | `{}`                               | `{ok, role, port, probe_serial, fw, id_reply}` |

### 5.2 TX-side tools

| Tool                | Arguments                                  | Returns                                    |
|---------------------|--------------------------------------------|--------------------------------------------|
| `board_start_burst` | `{n: int, plen: int, gap_us: int, raw: bool}` | `{ok, reply: "OK ARMED"}` or error    |

`board_start_burst` writes `START N=.. LEN=.. GAP=..` to the TX serial port
and returns the start reply line. It does **not** wait for the burst to
complete (the coordinator will `board_stop`/`swd_reset` later). The `raw`
flag emits the unsanitized START line (useful for repeating phrases).

### 5.3 RX-side tools

| Tool            | Arguments                                             | Returns                                |
|-----------------|-------------------------------------------------------|----------------------------------------|
| `board_capture` | `{duration_s: float, config_idx: int, eager_stop: bool}` | `{ok, pkts: [PKT dict...], n, k, lines: [...]}` |

`board_capture` drains the RX serial for `duration_s` seconds (default 5),
parses PKT lines via `parse_pkt`, filters by `config_idx`, and returns the
aggregated list plus derived `n/k` counts. If `eager_stop` is set and the
coordinator has hit SPRT n_min, the server itself can decide CLEAN/DEAD
early (validation work in §8).

## 6. Distributed SPRT Loop

The coordinator runs the same loop as `e80_campaign.py` `main()`, except
each call that previously hit a local serial port is replaced by a CVM
tool call:

| Step                              | Local (`e80_campaign.py`)              | CVM (`cvm_campaign.py`)                              |
|-----------------------------------|-----------------------------------------|------------------------------------------------------|
| Configure TX                       | `sw.cmd(tx, "MOD LORA 7 125")`          | `tx.call("board_send", {line: "MOD LORA 7 125"})`    |
| Configure RX                      | `sw.cmd(rx, "MOD LORA 7 125")`          | `rx.call("board_send", {line: "MOD LORA 7 125"})`    |
| Role + session + config tags      | `sw.cmd(s, "ROLE TX")` etc.              | `tx.call("board_send", {line: "ROLE TX"})` etc.      |
| Band override                     | `sw.cmd(s, "BAND OVERRIDE 2026")`        | `tx.call("board_send", {line: "BAND OVERRIDE 2026"})`|
| Arm TX                            | `sw.cmd(tx, "ARM TX")`                   | `tx.call("board_query", {line: "ARM TX"})`           |
| Start burst                       | `tx.write(b"START N=.. LEN=.. GAP=..\r\n")` | `tx.call("board_start_burst", {n, plen, gap_us})` |
| Stream RX, early-stop via SPRT    | `while n < n_cap: line = readline(rx)`   | `rx.call("board_capture", {duration_s, config_idx, eager_stop})` |
| STOP TX                           | `sw.cmd(tx, "STOP")`                     | `tx.call("board_send", {line: "STOP"})`               |
| Reset between configs             | `swd_reset(PROBE_TX)` etc.                | `tx.call("board_swd_reset")` + `rx.call("board_swd_reset")` |

The actual SPRT decision logic (`sprt_decide(k, n)`, Wilson CI, branch,
cliff_search) is imported unchanged from `e80_campaign.py`. This preserves
test coverage and keeps the SPRT code single-sourced.

### 6.1 Latency budget per SPRT iteration

```
   ┌────────────────────────────────────────────────────────────┐
   │ CVM round trip   │ ~0.7 s warm │ × ~6 board_send calls   │
   │                 ~4.2 s overhead per config (acceptable)    │
   ├────────────────────────────────────────────────────────────┤
   │ Arm + start     │ ~0.7 s │ ×2 (TX arm, TX start)         │
   │ RX capture      │ duration_s (1-50 s, depends on n_cap)    │
   │ STOP + reset    │ ~3-5 s (SWD reset ~2 s/board ×2)        │
   └────────────────────────────────────────────────────────────┘
   Total per config: ~10 s minimum (n_cap=20 LoRa SF12 path) up to
   ~60 s (n_cap=20 FLRC-2600 capture). Compare with single-process:
   ~5-55 s — Nostr overhead is ~5 s, well within reason.
```

### 6.2 Relay latency handling

Each CVM call has a default `timeout=30` seconds with one auto-retry on
timeout. Cold latency (5-10 s on first connect) is absorbed by:

1. Server starts subscribing first (run `make range-cvm-server` on TX/RX
   before `make range-adaptive`).
2. Coordinator waits for `board_info` from both servers before starting
   (warmup handshake).
3. Persistent connections keep pings warm between configs.

## 7. Relay Selection

Verified working relays (2026-08-23):

| Relay                          | Status  | Notes                                  |
|--------------------------------|---------|----------------------------------------|
| `wss://relay.primal.net`       | ✅      | Fastest in round-trip test (~0.3 s)   |
| `wss://nostr.mom`              | ✅      | Solid secondary, 0.5 s round trip     |
| `wss://nos.lol`                | ✅      | Public, no auth required               |
| `wss://relay2.contextvm.org`   | ✅      | CVM-specific, recommended             |
| `wss://relay.nostr.band`       | ✅      | Broad coverage                         |
| `wss://relay.contextvm.org`    | ❌      | Unreachable — do NOT use              |
| `wss://relay.damus.io`         | ❌      | Errors — do NOT use                    |

The board server and coordinator publish to **all configured relays**
simultaneously; subscriptions are also broad. This gives automatic failover
— if one relay hiccups, the event still arrives via another.

The Makefile `range-cvm-test` target runs `cvm_relay_test.py` to measure
round-trip latency across all working relays and reports the fastest.

## 8. Test Strategy

### 8.1 Unit tests (TDD-first)

`firmware/e80-stm32-bench/tools/test_cvm_board_server.py`:

- **MockBoardController**: stubs `BoardController` with synthetic replies,
  canned PKT lines, no real serial port.
- **MockCVMTransport**: in-memory bus that simulates the relay pool —
  captures gift-wrapped events and reroutes them to a registered handler,
  skipping the real WebSocket.
- Tests:
  - `test_tool_dispatch_unknown_tool` — unknown tool name → JSON-RPC error
  - `test_tool_board_query_ok_reply` — `board_query` returns OK reply
  - `test_tool_board_query_timeout` — query timeout returns error
  - `test_tool_board_send_err_reply` — firmware `.ERR` → exception in result
  - `test_tool_board_start_burst_args` — burst tool validates n/plen/gap_us
  - `test_tool_board_capture_parses_pkt` — PKT line → parse_pkt dict, k counts bit_err>0
  - `test_tool_board_capture_filters_config_idx` — non-matching config_idx is dropped
  - `test_tool_board_swd_reset_calls_openocd` — verify subprocess.run invoked
  - `test_ptag_filter_rejects_others` — wrap events with wrong p tag ignored
  - `test_gift_wrap_round_trip_local` — full wrap+unwrap without network

### 8.2 Integration tests (manual, on real network)

1. `make range-cvm-test` — relay latency + auth test
2. `make range-cvm-server ROLE=tx` started on T470
3. `make range-cvm-server ROLE=rx` started on DQ05 (over Netbird)
4. `make range-adaptive TX_NPUB=... RX_NPUB=... CONFIGS=outdoor-10 --dry-run`
   — verify the coordinator builds configs without hammering the network

### 8.3 Live hardware

```
# On T470 (TX server):
export CVM_SERVER_HEX=<tx_server_secret_hex>
make range-cvm-server ROLE=tx

# On DQ05 (RX server):
export CVM_SERVER_HEX=<rx_server_secret_hex>
make range-cvm-server ROLE=rx

# On either machine (coordinator):
export CVM_CLIENT_HEX=<coordinator_secret_hex>
make range-adaptive \
    TX_NPUB=npub1... \
    RX_NPUB=npub1... \
    CONFIGS=outdoor-10
```

## 9. Failure Modes & Recovery

| Failure                         | Detection                          | Recovery                                  |
|---------------------------------|------------------------------------|-------------------------------------------|
| Relay disconnect mid-call       | timeout=30 s                       | Auto-retry on 2nd relay, then propagate as JSON-RPC error |
| Board hung (no ID? response)    | `board_info` returns `alive:false` | Coordinator auto-invokes `board_swd_reset` then retries once |
| Wrong p tag (not for us)        | filter in handler                  | Skip silently (log debug)                 |
| Decryption fail (bad wrap)      | `UnwrappedGift.from_gift_wrap` raises | Log + skip                                |
| JSON-RPC parse fail             | JSON parser raises                 | Reply with `error.code=-32700`            |
| Coordinator shutdown (Ctrl-C)   | SIGINT → graceful drain           | Final CSV/MD flush + state.commit()       |

## 10. Differences From Local e80_campaign.py

`cvm_campaign.py` `main()` mirrors `e80_campaign.py` `main()` almost exactly.
Differences:

1. `sw.open_boards()` is replaced by `cvm_open_clients(tx_npub, rx_npub)` —
   returns TX/RX CVMClient objects instead of serial handles.
2. `sprt_run(cfg, tx, rx, ...)` is replaced by `cvm_sprt_run(cfg, tx_client,
   rx_client, ...)` which dispatches the same sequence of board commands
   via the CVM tool surface, and uses `board_capture(duration_s=...)`
   instead of the streaming `readline(rx, timeout=3.0)` loop.
3. `stop_fn` remains compatible — `cvm_sprt_run` accepts a callable for
   early STOP if SPRT short-circuits.
4. CSV/MD output (`write_csv_row`, `write_md_report`) is reused unchanged.
5. `CampaignState` (carry-forward DB) is reused unchanged.

## 11. Ansible (`ansible/range-setup.yml`)

Adds (idempotent):

```yaml
- pip:
    name:
      - nostr-sdk
      - websocket-client
      - pyserial
    executable: pip3

- command: python3 -c "import nostr_sdk; print(nostr_sdk.Keys.generate().public_key().to_bech32())"
  register: nostr_check
  changed_when: false
```

The CVM stack is pure Python (no Node.js / bun required). `nak` is not
strictly required for the server or coordinator — only for key generation,
which is a one-time setup step documented in §4.2.

## 12. Files

| Path                                            | Purpose                                  |
|-------------------------------------------------|------------------------------------------|
| `firmware/e80-stm32-bench/tools/cvm_board_server.py` | CVM board server (TX or RX)         |
| `firmware/e80-stm32-bench/tools/cvm_campaign.py`     | Distributed coordinator            |
| `firmware/e80-stm32-bench/tools/test_cvm_board_server.py` | Unit tests                    |
| `firmware/e80-stm32-bench/tools/cvm_relay_test.py`   | Relay connectivity / latency probe      |
| `firmware/e80-stm32-bench/Makefile`                  | `range-cvm-*` targets               |
| `ansible/range-setup.yml`                       | Provisioning (adds nostr-sdk)           |
| `docs/DESIGN-contextvm-adaptive.md`             | This document                           |

## 13. Open Questions (deferred to runtime)

1. Should `board_capture` (RX) implement eager SPRT early-stop server-side?
   Pros: short-circuits LoRa SF12 captures that obviously fail at n=2-3.
   Cons: pushes SPRT logic to the server, splitting it from
   `e80_campaign.sprt_decide`. Decision: **deferred** — first version
   returns full capture; coordinator applies SPRT post-hoc. Can add
   `eager_stop=true` later without breaking the interface.
2. Gift-wrap spam filter — broad kind-1059 subscription may receive many
   unrelated events from the public relays. Already mitigated by client-side
   p-tag filter (O(1) per event). No further action needed unless throughput
   becomes a bottleneck (unlikely at ~1 event/s).
3. Multiple concurrent coordinators on the same npub pair — out of scope.
   The current design assumes one coordinator at a time per (TX, RX) pair.
   A second coordinator would just produce conflicting `START` commands on
   the TX board.
