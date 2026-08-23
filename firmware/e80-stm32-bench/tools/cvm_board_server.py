#!/usr/bin/env python3
"""cvm_board_server.py — ContextVM (Nostr MCP) board server for E80 bench.

Wraps the local E80 serial port as a set of JSON-RPC tools exposed over
Nostr relays using gift-wrapped kind 1059 events (NIP-44/NIP-59).
Replaces the TCP-only e80_board_server.py for NAT-traversing deployments.

Tools (JSON-RPC tools/call with name+arguments):

    board_query      {line, prefixes?, timeout?}   → {ok, reply}
    board_send        {line, timeout?}              → {ok, reply}
    board_stat        {}                            → {ok, reply}
    board_info        {}                            → {ok, role, port, probe_serial, fw, alive, id_reply}
    board_start_burst {n, plen, gap_us?}            → {ok, reply}   (TX only)
    board_capture     {duration_s, config_idx, eager_stop?}     → {ok, pkts, n, k, lines} (RX only)
    board_swd_reset   {}                            → {ok}

Wire protocol: see docs/DESIGN-contextvm-adaptive.md §3.
- Client → server: kind 25910 inner event (JSON-RPC request), gift-wrapped
  to kind 1059 by ephemeral key, with `p` tag = server pubkey.
- Server → client: same pattern, addressed to client pubkey.
- NIP-12 #p filter is unreliable for kind 1059 on some relays → subscribe
  broadly to kind 1059, filter p tag client-side.

Usage:
    # TX machine:
    CVM_SERVER_HEX=<hex_secret> python3 cvm_board_server.py --role tx

    # RX machine:
    CVM_SERVER_HEX=<hex_secret> python3 cvm_board_server.py --role rx

    # All flags:
    python3 cvm_board_server.py --role tx --port /dev/ttyUSB3 \\
        --relays wss://relay.primal.net,wss://nostr.mom \\
        --server-hex <hex> \\
        --allowed-client-npubs npub1xxx,npub1yyy
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import signal
import sys
import time
import traceback
from datetime import timedelta
from typing import Any, Awaitable, Callable, Optional

# Sibling imports (e80_board_server, e80_detect, e80_sweep_full)
_TOOLS_DIR = os.path.dirname(os.path.abspath(__file__))
if _TOOLS_DIR not in sys.path:
    sys.path.insert(0, _TOOLS_DIR)

# We piggy-back on e80_board_server's detection logic + BoardController.
import e80_board_server as bs  # noqa: E402
import e80_sweep_full as sw    # noqa: E402  (parse_pkt, lora_airtime_s, flrc_airtime_s)

# Default working relays (verified 2026-08-23).
DEFAULT_RELAYS = [
    "wss://relay.primal.net",
    "wss://nostr.mom",
    "wss://nos.lol",
    "wss://relay2.contextvm.org",
    "wss://relay.nostr.band",
]

# Nostr event kind for CVM JSON-RPC payloads (inner gift-wrapped event).
KIND_CVM_RPC = 25910
# Gift-wrap kind (NIP-59 outer wrap).
KIND_GIFT_WRAP = 1059

# JSON-RPC error codes (standard + custom —32000 range).
JSON_RPC_ERROR = {
    "PARSE_ERROR":       -32700,
    "INVALID_REQUEST":   -32600,
    "METHOD_NOT_FOUND":  -32601,
    "INVALID_PARAMS":   -32602,
    "INTERNAL_ERROR":    -32603,
    # Custom CVM errors
    "TOOL_ERROR":        -32000,  # Tool ran but returned ok=False
    "TOOL_TIMEOUT":      -32001,  # Relay timeout
    "SERVER_SHUTDOWN":   -32002,  # Server is shutting down
}


# ===========================================================================
# Board tools — pure-Python wrapper around BoardController, no Nostr
# ===========================================================================

class BoardTools:
    """Exposes BoardController methods as discoverable tools.

    Each method returns a dict that the CVM server will JSON-encode into the
    JSON-RPC result.content[0].text field. Hardware exceptions (TimeoutError,
    RuntimeError) propagate; the CVM layer catches and wraps them.
    """

    def __init__(self, ctrl: bs.BoardController, role: str):
        self.ctrl = ctrl
        self.role = role.upper()

    # --- tool dispatch ---

    def dispatch_tool(self, name: str, args: dict) -> dict:
        """Dispatch a tool call to the controller. Returns a result dict.

        Hardware/argument errors raised by the underlying tool implementation
        (TimeoutError, RuntimeError, ValueError) are caught and returned as
        ``{"ok": False, "error": str(e)}`` dicts so the JSON-RPC layer can
        simply embed them in ``result.content[0].text``.

        The only exception that propagates is ``ValueError`` for an unknown
        tool name, which ``dispatch_rpc`` maps to ``METHOD_NOT_FOUND``.
        """
        fn = getattr(self, f"tool_{name}", None)
        if fn is None:
            raise ValueError(f"unknown tool: {name} (role={self.role})")
        try:
            return fn(args)
        except (TimeoutError, RuntimeError, ValueError) as e:
            return {"ok": False, "error": str(e)}

    # --- tool implementations ---

    def tool_board_query(self, args: dict) -> dict:
        line = args.get("line")
        if not line:
            raise ValueError("board_query: 'line' is required")
        prefixes = tuple(args.get("prefixes", ("OK", "ERR", "STAT", "ID")))
        timeout = float(args.get("timeout", 15.0))
        reply = self.ctrl.query(line, prefixes=prefixes, timeout=timeout)
        return {"ok": True, "reply": reply}

    def tool_board_send(self, args: dict) -> dict:
        line = args.get("line")
        if not line:
            raise ValueError("board_send: 'line' is required")
        timeout = float(args.get("timeout", 15.0))
        reply = self.ctrl.cmd(line, timeout=timeout)
        return {"ok": True, "reply": reply}

    def tool_board_stat(self, args: dict) -> dict:
        reply = self.ctrl.stat()
        return {"ok": True, "reply": reply}

    def tool_board_info(self, args: dict) -> dict:
        id_reply = self.ctrl.id_query()
        fw = None
        role = self.role
        if id_reply:
            for tok in id_reply.split():
                if tok.startswith("fw="):
                    fw = tok.split("=", 1)[1]
                if tok.startswith("role="):
                    role = tok.split("=", 1)[1].upper()
        alive = self.ctrl.ensure_alive()
        return {
            "ok": True,
            "role": role,
            "port": self.ctrl.port,
            "probe_serial": self.ctrl.probe_serial,
            "fw": fw,
            "alive": alive,
            "id_reply": id_reply,
        }

    def tool_board_start_burst(self, args: dict) -> dict:
        """TX-side: arm and start a burst (does NOT wait for completion)."""
        if self.role != "TX":
            raise RuntimeError(f"board_start_burst: requires role=TX, got role={self.role}")
        n = int(args.get("n", 0))
        plen = int(args.get("plen", 0))
        gap_us = int(args.get("gap_us", 10000))
        if n < 1 or plen < 1:
            raise ValueError("board_start_burst: 'n' and 'plen' must be > 0")
        # ARM TX first — board replies "OK ARMED" (older firmware: "OK ARM TX")
        arm_reply = self.ctrl.query("ARM TX",
                                     prefixes=("OK", "ERR"), timeout=10.0)
        if not arm_reply.startswith("OK ARM"):
            raise RuntimeError(f"ARM TX rejected: {arm_reply}")
        # Emit START line via the controller so the write is recorded (mock
        # controllers track `written[]`) and the reply is read back cleanly.
        # Going through ctrl.query() instead of raw ser.write+readline keeps
        # this usable by both real BoardController and the test mocks (which
        # lack a `ser` attribute entirely).
        start_line = f"START N={n} LEN={plen} GAP={gap_us}"
        reply = self.ctrl.query(start_line,
                                prefixes=("OK", "ERR"), timeout=10.0)
        return {"ok": True, "reply": reply or "OK"}

    def tool_board_capture(self, args: dict) -> dict:
        """RX-side: capture PKT lines for duration_s, parse + count."""
        if self.role != "RX":
            raise RuntimeError(f"board_capture: requires role=RX, got role={self.role}")
        duration_s = float(args.get("duration_s", 5.0))
        config_idx = int(args["config_idx"])  # required
        lines = self.ctrl.drain(duration_s)
        # Also poll any port-buffered PKT lines that may have arrived during the
        # drain lock — board server's drain thread captures these.
        pkts = []
        k = 0
        n = 0
        for line in lines:
            pkt = sw.parse_pkt(line)
            if pkt is None:
                continue
            if pkt.get("config") != config_idx:
                continue
            pkts.append(pkt)
            n += 1
            if pkt.get("bit_err", 0) > 0:
                k += 1
        return {"ok": True, "pkts": pkts, "n": n, "k": k, "lines": lines}

    def tool_board_swd_reset(self, args: dict) -> dict:
        self.ctrl.swd_reset()
        return {"ok": True}


# ===========================================================================
# CVM board server — Nostr JSON-RPC via gift wrap
# ===========================================================================

class CVMBoardServer:
    """Nostr-backed CVM board server: serves BoardTools over gift-wrapped
    JSON-RPC.

    The serve() method:
    1. Loads server keys (hex or nsec).
    2. Adds all relays.
    3. Subscribes broadly to kind 1059.
    4. Filters incoming gift-wrap events by p tag == server pubkey.
    5. Unwraps via nostr_sdk.UnwrappedGift.from_gift_wrap.
    6. Dispatches the JSON-RPC in the inner event content.
    7. Sends back the JSON-RPC response as a gift-wrapped kind 1059 event.
    """

    def __init__(self, tools: BoardTools, server_keys, relays: list[str],
                 role: str, allowed_client_pubkeys: Optional[list[str]] = None,
                 log=print):
        """
        server_keys: nostr_sdk.Keys instance, OR None (for test/dispatch_rpc
                     only — calling serve() requires real keys).
        relays:      list of wss:// URLs (may be empty for tests).
        role:        "TX" or "RX" (informational, used in hello).
        allowed_client_pubkeys: optional hex pubkey allow-list. If empty/None,
                     the server responds to any wrapped request addressed to it.
        log:         callable(str) for log lines (default: print).
        """
        self.tools = tools
        self.server_keys = server_keys
        self.signer = None
        if server_keys is not None:
            import nostr_sdk
            self.signer = nostr_sdk.NostrSigner.keys(server_keys)
        self.relays = relays
        self.role = role.upper()
        self.allowed_clients = set(allowed_client_pubkeys) if allowed_client_pubkeys else None
        self.log = log
        self._running = False
        self._client: Any = None  # nostr_sdk.Client (async)

    # --- RPC dispatch ---

    async def dispatch_rpc(self, rpc: dict, sender_pk: str) -> dict:
        """Dispatch a JSON-RPC request dict → JSON-RPC response dict.

        Pure-Python: no Nostr. This is the seam tests target.
        """
        if not isinstance(rpc, dict):
            return self._error(None, JSON_RPC_ERROR["PARSE_ERROR"],
                                "request is not an object")
        rpc_id = rpc.get("id")
        if "jsonrpc" not in rpc or rpc["jsonrpc"] != "2.0":
            return self._error(rpc_id, JSON_RPC_ERROR["INVALID_REQUEST"],
                                "missing or invalid jsonrpc version")
        method = rpc.get("method")
        if not method:
            return self._error(rpc_id, JSON_RPC_ERROR["INVALID_REQUEST"],
                                "missing method")
        params = rpc.get("params", {})
        if not isinstance(params, dict):
            return self._error(rpc_id, JSON_RPC_ERROR["INVALID_PARAMS"],
                                "params must be an object")

        # Server-side allow-list (none = accept all)
        if self.allowed_clients is not None and sender_pk not in self.allowed_clients:
            return self._error(rpc_id, JSON_RPC_ERROR["INVALID_REQUEST"],
                                f"unauthorized client: {sender_pk[:16]}...")

        if method != "tools/call":
            return self._error(rpc_id, JSON_RPC_ERROR["METHOD_NOT_FOUND"],
                                f"unknown method: {method} (expected 'tools/call')")

        tool_name = params.get("name")
        if not tool_name:
            return self._error(rpc_id, JSON_RPC_ERROR["INVALID_PARAMS"],
                                "missing params.name")
        tool_args = params.get("arguments", {})
        if not isinstance(tool_args, dict):
            return self._error(rpc_id, JSON_RPC_ERROR["INVALID_PARAMS"],
                                "params.arguments must be an object")

        # Execute the tool. dispatch_tool catches its own hardware/argument
        # errors (TimeoutError/RuntimeError/ValueError) and returns
        # {"ok": False, "error": ...} dicts; the only exception it lets
        # propagate is ValueError for unknown tool names, which we map to
        # METHOD_NOT_FOUND. Anything else reaching here is genuinely
        # unexpected and becomes INTERNAL_ERROR.
        try:
            result = self.tools.dispatch_tool(tool_name, tool_args)
        except ValueError as e:
            return self._error(rpc_id, JSON_RPC_ERROR["METHOD_NOT_FOUND"], str(e))
        except TimeoutError as e:
            # Defensive: dispatch_tool catches TimeoutError itself, but a
            # mocked dispatch_tool (or a future code path) may raise.
            return self._error(rpc_id, JSON_RPC_ERROR["TOOL_TIMEOUT"], str(e))
        except Exception as e:
            # Unhandled — log stack trace, surface details to the client.
            traceback.print_exc()
            return self._error(rpc_id, JSON_RPC_ERROR["INTERNAL_ERROR"],
                                f"{type(e).__name__}: {e}")

        # Success path: JSON-RPC result with the tool's dict embedded in
        # MCP content[0].text. This is the same envelope the
        # applesauce-cvm client expects.
        text = json.dumps(result)
        return {
            "jsonrpc": "2.0",
            "id": rpc_id,
            "result": {
                "content": [{"type": "text", "text": text}],
            },
        }

    @staticmethod
    def _error(rpc_id, code, message):
        return {"jsonrpc": "2.0", "id": rpc_id,
                "error": {"code": code, "message": message}}

    # --- Nostr serve loop ---

    async def serve(self, ready_signal: Optional[asyncio.Event] = None):
        """Start the Nostr subscription loop. Blocks until stop() is called
        or SIGINT/SIGTERM is received."""
        if self.signer is None:
            raise RuntimeError("server_keys is None — cannot serve without keys")
        import nostr_sdk

        # Build client
        self._client = nostr_sdk.ClientBuilder().signer(self.signer).build()
        for url in self.relays:
            try:
                await self._client.add_relay(nostr_sdk.RelayUrl.parse(url))
            except Exception as e:
                self.log(f"[cvm-server] relay add failed {url}: {e}")
        await self._client.connect()
        self.log(f"[cvm-server] connected to {len(self.relays)} relays")

        # Broad subscribe to ALL kind 1059 events (p-tag filter unreliable)
        # We filter client-side via the p-tag check in handle().
        server_pk = self.server_keys.public_key()
        server_pk_hex = server_pk.to_hex()
        sub_filter = nostr_sdk.Filter().kinds([nostr_sdk.Kind(KIND_GIFT_WRAP)])
        await self._client.subscribe(sub_filter, None)
        self.log(f"[cvm-server] subscribed kind=1059 "
                 f"(server_pk={server_pk.bech32()[:24]}...)")

        # Announce ready (let parent proceed)
        if ready_signal is not None:
            ready_signal.set()

        handler = _NotificationHandler(self, server_pk_hex, self.log)
        self._running = True
        try:
            # handle_notifications blocks until the client shuts down
            await self._client.handle_notifications(handler)
        except asyncio.CancelledError:
            self.log("[cvm-server] serve cancelled")
        finally:
            self._running = False
            try:
                await self._client.shutdown()
            except Exception:
                pass

    def stop(self):
        self._running = False
        if self._client is not None:
            try:
                # schedule shutdown on the running loop
                asyncio.ensure_future(self._client.shutdown())
            except RuntimeError:
                pass

    async def _handle_request(self, event, server_pk_hex: str):
        """Process a single incoming gift-wrapped event. May raise."""
        import nostr_sdk
        # 1. Check p tag (server-side filter)
        p_tag = _extract_p_tag(event)
        if p_tag is None or p_tag != server_pk_hex:
            return  # not for us
        # 2. Unwrap
        unwrapped = await nostr_sdk.UnwrappedGift.from_gift_wrap(self.signer, event)
        inner = unwrapped.rumor()
        # 3. Parse JSON-RPC
        try:
            rpc = json.loads(inner.content())
        except json.JSONDecodeError as e:
            self.log(f"[cvm-server] bad JSON in inner event: {e}")
            return
        client_pk = inner.author()
        client_pk_hex = client_pk.to_hex()
        # 4. Dispatch
        t0 = time.monotonic()
        response = await self.dispatch_rpc(rpc, client_pk_hex)
        dt = time.monotonic() - t0
        err = response.get("error")
        self.log(f"[cvm-server] rpc id={rpc.get('id')} "
                 f"tool={rpc.get('params', {}).get('name', '?')} "
                 f"dt={dt:.2f}s "
                 f"{'OK' if not err else 'ERR:' + err.get('message', '')[:50]}")
        # 5. Wrap + send reply (gift wrap to client)
        await self._send_reply(client_pk, response)

    async def _send_reply(self, recipient_pk, response: dict):
        """Gift-wrap a response dict to recipient_pk and publish."""
        import nostr_sdk
        response_str = json.dumps(response)
        reply_ue = nostr_sdk.UnsignedEvent.from_json(json.dumps({
            "pubkey": self.server_keys.public_key().to_hex(),
            "kind": KIND_CVM_RPC,
            "tags": [["p", recipient_pk.to_hex()]],
            "content": response_str,
            "created_at": nostr_sdk.Timestamp.now().as_secs(),
        }))
        gw = await nostr_sdk.gift_wrap(self.signer, recipient_pk, reply_ue)
        await self._client.send_event(gw)


def _extract_p_tag(event) -> Optional[str]:
    """Pull the first 'p' tag value from a nostr_sdk Event."""
    try:
        for tag in event.tags().to_vec():
            v = tag.as_vec()
            if v and v[0] == "p" and len(v) >= 2:
                return v[1]
    except Exception:
        pass
    return None


class _NotificationHandler:
    """HandleNotification adapter for nostr_sdk.Client.handle_notifications.

    The uniffi trait signature calls async def handle(self, relay_url,
    subscription_id, event) → returns an awaitable (coroutine). Each event
    spawns an asyncio task so the trait call returns immediately while the
    slow unwrapping + tool dispatch runs separately.
    """

    def __init__(self, server: CVMBoardServer, server_pk_hex: str, log=print):
        self.server = server
        self.server_pk_hex = server_pk_hex
        self.log = log

    async def handle(self, relay_url, subscription_id, event):
        try:
            await self.server._handle_request(event, self.server_pk_hex)
        except Exception as e:
            self.log(f"[cvm-server] handle err: {type(e).__name__}: {e}")

    async def handle_msg(self, relay_url, msg):
        # Ignore non-event messages (EOSE, OK, NOTICE)
        return None


# ===========================================================================
# Server entrypoint
# ===========================================================================

def _load_keys(hexpass: Optional[str], nsec: Optional[str]):
    """Load nostr_sdk.Keys from one of the prompts."""
    import nostr_sdk
    if nsec:
        return nostr_sdk.Keys.parse(nsec)
    if hexpass:
        return nostr_sdk.Keys.parse(hexpass)
    raise SystemExit("ERROR: must pass --server-hex <hex> or --nsec nsec1... "
                     "(env: CVM_SERVER_HEX)")


def run_server(role: str, port_spec: str = "auto",
               server_keys=None, relays: Optional[list[str]] = None,
               allowed_clients: Optional[list[str]] = None,
               log=print) -> int:
    """Open the board, build the CVM server, serve forever.
    Returns exit code (0=clean, non-zero=error).
    """
    if relays is None:
        relays = list(DEFAULT_RELAYS)
    if server_keys is None:
        raise SystemExit("server_keys required to serve")

    # --- Open the board (reuse e80_board_server auto-detect) ---
    from e80_detect import check_deps, detect_board, query_id, parse_id_reply, \
        find_swd_probes

    deps = check_deps()
    if not deps["pyserial"]:
        print("ERROR: pyserial not installed. Run: pip install pyserial",
              file=sys.stderr)
        return 2
    if not deps["openocd"]:
        print("WARNING: openocd missing (SWD reset unavailable)",
              file=sys.stderr)

    if port_spec == "auto":
        result = detect_board(target_role=role)
        if "error" in result:
            print(f"ERROR: {result['error']}", file=sys.stderr)
            return 1
        serial_port = result["port"]
        probe_serial = result["probe_serial"]
        detected_role = result["role"]
    else:
        serial_port = port_spec
        id_reply = query_id(serial_port)
        id_parsed = parse_id_reply(id_reply) if id_reply else {}
        detected_role = id_parsed.get("role", "?")
        probe_serial = None
        probes = find_swd_probes()
        if len(probes) == 1:
            probe_serial = next(iter(probes.keys()))
            detected_role = probes[probe_serial]["role"]

    if role and detected_role and detected_role.upper() != role.upper():
        print(f"ERROR: expected role={role} but detected role={detected_role}",
              file=sys.stderr)
        return 1

    try:
        ctrl = bs.BoardController(serial_port, probe_serial=probe_serial)
        ctrl.role = detected_role or role or "?"
    except Exception as e:
        print(f"ERROR: cannot open {serial_port}: {e}", file=sys.stderr)
        return 1

    print(f"[cvm-server] Role={ctrl.role} Port={serial_port} "
          f"Probe={probe_serial or 'N/A'}", flush=True)

    # --- Build + serve ---
    tools = BoardTools(ctrl, role=ctrl.role)
    server = CVMBoardServer(tools, server_keys=server_keys, relays=relays,
                             role=ctrl.role, allowed_client_pubkeys=allowed_clients,
                             log=log)

    # Signal handling: SIGINT/SIGTERM → graceful shutdown
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    ready = asyncio.Event()

    def _stop_handler(*_):
        log("[cvm-server] stop signal received")
        server.stop()

    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, _stop_handler)
        except (NotImplementedError, RuntimeError):
            # Windows / no loop signal support
            signal.signal(sig, lambda *args: _stop_handler(*args))

    try:
        loop.run_until_complete(server.serve(ready_signal=ready))
    except KeyboardInterrupt:
        pass
    finally:
        ctrl.close()
        log("[cvm-server] clean shutdown")
    return 0


def main():
    ap = argparse.ArgumentParser(
        description="CVM (ContextVM/Nostr MCP) board server for E80 bench")
    ap.add_argument("--role", required=True, choices=["tx", "rx"],
                    help="Board role — TX or RX server")
    ap.add_argument("--port", default="auto",
                    help="Serial port ('auto' or /dev/ttyUSB3)")
    ap.add_argument("--relays", default=",".join(DEFAULT_RELAYS),
                    help="Comma-separated relay URLs")
    ap.add_argument("--server-hex", default=os.environ.get("CVM_SERVER_HEX"),
                    help="Server Nostr private key (64-char hex)")
    ap.add_argument("--nsec", default=os.environ.get("CVM_SERVER_NSEC"),
                    help="Server Nostr private key (nsec1... bech32)")
    ap.add_argument("--allowed-client-npubs",
                    default=os.environ.get("CVM_ALLOWED_CLIENTS", ""),
                    help="Comma-separated client npub allow-list (default: any)")
    args = ap.parse_args()

    # Validate keys
    if not args.server_hex and not args.nsec:
        print("ERROR: must pass --server-hex <hex> or --nsec nsec1... "
              "(env: CVM_SERVER_HEX)", file=sys.stderr)
        return 2

    server_keys = _load_keys(args.server_hex, args.nsec)
    print(f"[cvm-server] npub={server_keys.public_key().bech32()}",
          flush=True)

    relays = [r.strip() for r in args.relays.split(",") if r.strip()]
    allowed = [c.strip() for c in args.allowed_client_npubs.split(",")
               if c.strip()] or None
    # Convert client npubs to hex for comparison (or keep as npub — depends
    # on the relay's tag filter; we compare against inner.author().to_hex()
    # which is hex, but npub1 bech32 is the canonical form for the allow-list
    # since that's what nak key convert produces). Convert npub→hex:
    if allowed:
        import nostr_sdk
        allowed_hex = []
        for c in allowed:
            try:
                if c.startswith("npub1"):
                    allowed_hex.append(
                        nostr_sdk.PublicKey.parse(c).to_hex())
                else:
                    allowed_hex.append(c)  # already hex
            except Exception as e:
                print(f"WARNING: bad client npub {c}: {e}", file=sys.stderr)
        allowed = allowed_hex

    return run_server(args.role.upper(), port_spec=args.port,
                       server_keys=server_keys, relays=relays,
                       allowed_clients=allowed)


if __name__ == "__main__":
    sys.exit(main())
