# DESIGN — CVM E28 Board Server (`e28_board_server.py`)

**Status:** Implemented (Phase 2 of the E28 ranging campaign)
**Date:** 2026-09-10
**Plan ref:** `~/.hermes/profiles/manager/state/plans/e28-ranging-campaign-plan.md` (Phase 2)

## Purpose

Wrap the E28 ranging serial console (LILYGO T3S3 ESP32-S3 + SX1282, firmware
`firmware/esp32-e28-range`) as CVM MCP tools over Nostr, mirroring
`cvm_board_server.py`. This lets a single coordinator drive the E28 distance
measurement over the same gift-wrapped kind 1059 transport as the E80 boards.

## Architecture

Each bundle (RX and TX) carries an E28 + E80 + a computer. Each machine runs
TWO servers:

```
TX machine:   cvm_board_server.py --role tx   (E80)
              e28_board_server.py  --role tx   (E28, master)
RX machine:   cvm_board_server.py --role rx   (E80)
              e28_board_server.py  --role rx   (E28, responder)
```

`e28_board_server.py` reuses ~75% of the `CVMBoardServer` transport from
`cvm_board_server.py`:

- **Gift-wrap kind 1059** (NIP-44/NIP-59), inner kind 25910 JSON-RPC.
- **`_NotificationHandler`** — the `handle_notifications` adapter.
- **`dispatch_rpc`** — the pure-Python JSON-RPC test seam.
- **`_extract_p_tag`, `_load_keys`, `DEFAULT_RELAYS`, `JSON_RPC_ERROR`.**

`E28BoardServer` subclasses `CVMBoardServer` and swaps in an `E28Tools` object
(the E28 line protocol differs from the E80 `BoardController` protocol, so we
reuse the *pattern* — a drain-thread serial wrapper — not the class).

## E28 serial wrapper (`E28Controller`)

A `BoardController`-style drain-thread wrapper with the E28 line protocol:

- Background drain thread reads serial output into an in-memory buffer.
- `query(line, prefixes)` sends a line and waits for a reply matching a prefix.
- `send(line)` is fire-and-forget — the E28 `FREQ`/`SF`/`BW`/`PA` commands
  emit no success reply.
- `id_query()` / `ensure_alive()` probe `ID?` for `E28-RANGE`.

## Tool surface (`E28Tools`)

| Tool | Args | Role | Behavior |
|------|------|------|----------|
| `e28_range` | `{freq?, sf?, bw?, pa?}` | **TX** | Initiate master ranging; returns `{ok, status}` |
| `e28_range_slave` | `{freq?, sf?, bw?, pa?}` | **RX** | Respond to ranging; returns `{ok, status}` |
| `e28_query` | `{}` | any | Last distance; returns `{ok, distance_m, status}` |
| `e28_config` | `{freq?, sf?, bw?, pa?}` | any | Best-effort radio config; returns `{ok, status, commands}` |

**Role enforcement:** `e28_range` requires `role=TX` (master initiates);
`e28_range_slave` requires `role=RX` (responder). A role mismatch returns
`{ok: false, error: "...requires role=TX..."}` and does NOT touch the serial
port.

**Power cap:** `PA` is clamped to the EU indoor cap **+10 dBm**
(`E28_TXPOW_CAP_INDOOR_DBM`, matching `E28_RANGE_TXPOW_CAP_INDOOR_DBM` in the
firmware). `e28_config` clamps via `_clamp_pa`.

**Known-good fallback:** `e28_config` with no args (or missing keys) falls
back to `E28_KNOWN_GOOD` = `{freq: 2440000000, sf: 7, bw: 812.5, pa: 10}`.
This is the sx1280-correlation-test lesson: the E28 vendor config protocol was
historically unreliable (26/26 "unverified"), so we default to a manual
known-good config rather than trusting the vendor protocol.

**Distance parsing:** `e28_query` parses `DIST=<m>m` via
`re.match(r"DIST=([0-9.]+)m", reply)`; `DIST=none` → `distance_m=None`.

## Usage

```bash
# TX machine (master):
CVM_SERVER_HEX=<hex> python3 e28_board_server.py --role tx

# RX machine (responder):
CVM_SERVER_HEX=<hex> python3 e28_board_server.py --role rx

# Explicit port + allow-list:
python3 e28_board_server.py --role tx --port /dev/ttyUSB4 \
    --relays wss://relay.primal.net,wss://nostr.mom \
    --server-hex <hex> --allowed-client-npubs npub1xxx,npub1yyy
```

`--port auto` (default) probes `/dev/ttyUSB*` and `/dev/ttyACM*` for a port
that answers `ID?` with `E28-RANGE`.

## Testing

`tools/test_e28_board_server.py` — 14 tests, no hardware or Nostr relays:

- `E28Tools` surface: `e28_range`, `e28_range_slave`, `e28_query`,
  `e28_config`, unknown-tool error.
- Role enforcement: TX cannot `e28_range_slave`, RX cannot `e28_range`.
- `e28_query` parses `DIST=<m>m` and `DIST=none`.
- `e28_config` sends FREQ/SF/BW/PA; empty args use known-good.
- JSON-RPC dispatch via `E28BoardServer.dispatch_rpc`.
- Mock-transport integration: client → server round-trip for TX and RX.

Run: `python3 -m pytest test_e28_board_server.py -v`

## Files

- `firmware/e80-stm32-bench/tools/e28_board_server.py` — server + tools.
- `firmware/e80-stm32-bench/tools/test_e28_board_server.py` — tests.
- `docs/plans/cvm-e28-integration-audit.md` — design audit (Phase 2 source).
