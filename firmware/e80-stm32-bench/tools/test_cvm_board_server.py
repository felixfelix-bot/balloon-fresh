#!/usr/bin/env python3
"""test_cvm_board_server.py — unit tests for the CVM board server and coordinator.

Runs without real hardware or Nostr relays. The Nostr layer is mocked via
`MockCVMTransport`, which routes gift-wrapped events between registered
handlers in-memory. The board controller is mocked via
`MockBoardController` with scripted serial replies.

Run:  python3 -m pytest test_cvm_board_server.py -v
Or:   python3 test_cvm_board_server.py            (no pytest needed)
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
import unittest
from unittest.mock import MagicMock, patch

# Add tools dir for imports
_TOOLS_DIR = os.path.dirname(os.path.abspath(__file__))
if _TOOLS_DIR not in sys.path:
    sys.path.insert(0, _TOOLS_DIR)


# ---------------------------------------------------------------------------
# Mock board controller — mimics e80_board_server.BoardController
# ---------------------------------------------------------------------------

class MockBoardController:
    """In-memory controller that mimics a real E80 board."""
    def __init__(self, role="TX", replies=None):
        self.role = role
        self.port = "/dev/ttyMOCK"
        self.probe_serial = "MOCK1234"
        self.replies = replies or {}  # line → reply string
        self.written: list[str] = []
        self.drained_lines: list[str] = []
        self.swd_reset_count = 0
        self.alive = True

    def query(self, line, prefixes=("OK", "ERR", "STAT", "ID"), timeout=15.0):
        self.written.append(line)
        # Look for reply — try exact match, then prefix
        r = self.replies.get(line)
        if r is None:
            for k, v in self.replies.items():
                if line.startswith(k):
                    r = v
                    break
        if r is None:
            # Default pattern: OK <CAPITALIZED_LINE>
            if line.endswith("?"):
                key_word = line.rstrip("?").upper()
                r = f"{key_word} E80BENCH fw=0561b29"
                return r
            r = f"OK {line.upper()}"
        if r.startswith("ERR"):
            raise RuntimeError(f"board rejected '{line}': {r}")
        return r

    def cmd(self, line, timeout=15.0):
        return self.query(line, prefixes=("OK", "ERR"), timeout=timeout)

    def stat(self):
        return self.replies.get("STAT?", "STAT n=0 tx=0 rx=0")

    def id_query(self):
        return self.replies.get("ID?", "ID E80BENCH fw=0561b29 role=" + self.role)

    def drain(self, seconds=1.0):
        out = list(self.drained_lines)
        self.drained_lines.clear()
        return out

    def swd_reset(self):
        self.swd_reset_count += 1
        return True

    def ensure_alive(self):
        return self.alive

    def close(self):
        pass


# ---------------------------------------------------------------------------
# Mock CVM transport — simulates the Nostr relay pool in-memory
# ---------------------------------------------------------------------------

class MockCVMTransport:
    """In-memory bus that routes JSON-RPC requests between client and server.

    Both the server and client register a handler. When a client calls
    `call()`, the JSON-RPC request is dispatched synchronously to the
    registered server's `dispatch_rpc` method, and the response is returned.

    This matches the eventual network shape (request → server → reply) minus
    the NIP-44/NIP-59 gift-wrap layer, which is itself unit-tested separately
    in test_gift_wrap_round_trip().
    """
    def __init__(self):
        self.servers: dict[str, callable] = {}  # npub_hex → dispatch_fn

    async def register_server(self, npub_hex, dispatch_fn):
        """Register a server (its dispatch_rpc) at npub_hex."""
        self.servers[npub_hex] = dispatch_fn

    async def call(self, target_npub, rpc_request, timeout=30):
        """Client-side call: dispatch a JSON-RPC request to a registered server."""
        if target_npub not in self.servers:
            return {
                "jsonrpc": "2.0", "id": rpc_request.get("id"),
                "error": {"code": -32001, "message": f"unknown server: {target_npub[:8]}..."}
            }
        dispatch = self.servers[target_npub]
        # The dispatch callable may be a coroutine function OR a sync function
        # that returns a coroutine (e.g. `lambda r, c: server.dispatch_rpc(r, c)`
        # wrapping an async method). Invoke, then await if a coroutine came back.
        # Pass client_npub as a positional arg so the callable signature may be
        # either (rpc, client_npub) or (r, c) — both are valid in tests.
        result = dispatch(rpc_request, "client")
        if asyncio.iscoroutine(result):
            result = await result
        return result


# ===========================================================================
# BOARD TOOLS TESTS (pure Python, no Nostr)
# ===========================================================================

class TestPlatform:
    """Name the platform so tests can be skipped on missing deps."""
    @classmethod
    def have_nostr_sdk(cls):
        try:
            import nostr_sdk  # noqa: F401
            return True
        except ImportError:
            return False


class TestBoardTools(unittest.IsolatedAsyncioTestCase):
    """Tests the BoardTools layer (Hardware wrapper without Nostr)."""

    async def asyncSetUp(self):
        # Import inside the test so the file can be loaded even if nostr_sdk
        # is missing (some CI envs may not have it).
        from cvm_board_server import BoardTools
        self.BoardTools = BoardTools

    async def test_unknown_tool_returns_error(self):
        """Unknown tool name should raise ValueError (so dispatch_rpc can wrap it)."""
        ctrl = MockBoardController(role="TX")
        tools = self.BoardTools(ctrl, role="TX")
        with self.assertRaises(ValueError) as ctx:
            tools.dispatch_tool("nonexistent_tool", {})
        self.assertIn("unknown", str(ctx.exception).lower())

    async def test_board_query_ok_reply(self):
        ctrl = MockBoardController(role="TX",
                                   replies={"ID?": "ID E80BENCH fw=0561b29 role=TX"})
        tools = self.BoardTools(ctrl, role="TX")
        result = tools.dispatch_tool("board_query", {"line": "ID?"})
        self.assertTrue(result["ok"])
        self.assertIn("E80BENCH", result["reply"])

    async def test_board_query_with_prefixes(self):
        ctrl = MockBoardController(role="RX",
                                   replies={"STAT?": "STAT n=42 tx=20 rx=22"})
        tools = self.BoardTools(ctrl, role="RX")
        result = tools.dispatch_tool("board_query",
                                    {"line": "STAT?", "prefixes": ["STAT", "OK", "ERR"]})
        self.assertTrue(result["ok"])
        self.assertEqual(result["reply"], "STAT n=42 tx=20 rx=22")

    async def test_board_query_no_reply_timeout(self):
        # Custom controller that always raises TimeoutError
        class TimeoutCtrl(MockBoardController):
            def query(self, line, prefixes=("OK", "ERR", "STAT", "ID"), timeout=15.0):
                raise TimeoutError(f"timeout waiting for '{line}'")
        ctrl = TimeoutCtrl(role="TX")
        tools = self.BoardTools(ctrl, role="TX")
        result = tools.dispatch_tool("board_query", {"line": "ANY", "timeout": 1.0})
        self.assertFalse(result["ok"])
        self.assertIn("timeout", result["error"].lower())

    async def test_board_send_err_raises(self):
        ctrl = MockBoardController(role="TX", replies={"BAND OVERRIDE 2026": "ERR BAND INV"})
        tools = self.BoardTools(ctrl, role="TX")
        result = tools.dispatch_tool("board_send", {"line": "BAND OVERRIDE 2026"})
        self.assertFalse(result["ok"])
        # The error message bubbles from RuntimeError → JSON-RPC error
        self.assertIn("ERR BAND INV", result["error"])

    async def test_board_send_ok_rpc_response(self):
        # board_send returns OK + the reply line
        ctrl = MockBoardController(role="TX")
        tools = self.BoardTools(ctrl, role="TX")
        result = tools.dispatch_tool("board_send", {"line": "ROLE TX"})
        self.assertTrue(result["ok"])
        self.assertIn("OK", result["reply"])

    async def test_board_stat(self):
        ctrl = MockBoardController(role="TX",
                                   replies={"STAT?": "STAT n=42 tx=20 rx=22"})
        tools = self.BoardTools(ctrl, role="TX")
        result = tools.dispatch_tool("board_stat", {})
        self.assertTrue(result["ok"])
        self.assertEqual(result["reply"], "STAT n=42 tx=20 rx=22")

    async def test_board_swd_reset_calls_ctrl(self):
        ctrl = MockBoardController(role="TX")
        tools = self.BoardTools(ctrl, role="TX")
        result = tools.dispatch_tool("board_swd_reset", {})
        self.assertTrue(result["ok"])
        self.assertEqual(ctrl.swd_reset_count, 1)

    async def test_board_start_burst_args_validation(self):
        ctrl = MockBoardController(role="TX",
                                   replies={"START N=20 LEN=51 GAP=10000": "OK ARMED 20"})
        tools = self.BoardTools(ctrl, role="TX")
        # Missing n → error
        result = tools.dispatch_tool("board_start_burst", {"plen": 51, "gap_us": 10000})
        self.assertFalse(result["ok"])
        # With all args → OK_ARMED reply
        result = tools.dispatch_tool("board_start_burst",
                                     {"n": 20, "plen": 51, "gap_us": 10000})
        self.assertTrue(result["ok"])
        self.assertIn("ARMED", result["reply"])
        # Verify the START line was written to the mock controller
        self.assertTrue(any("START N=20 LEN=51 GAP=10000" in w for w in ctrl.written))

    async def test_board_start_burst_default_gap(self):
        ctrl = MockBoardController(role="TX", replies={"START N=10 LEN=51 GAP=10000": "OK ARMED 10"})
        tools = self.BoardTools(ctrl, role="TX")
        # gap_us defaults to 10000
        result = tools.dispatch_tool("board_start_burst", {"n": 10, "plen": 51})
        self.assertTrue(result["ok"])

    async def test_board_capture_parses_pkt(self):
        # Pre-load RX controller with drained PKT lines
        pkts = [
            "PKT,42,3,0,0,1000,-72,8,1,0,0,868000000,LORA,7,125,4,10,51,0,0,0,0,0,0,12345",
            "PKT,42,3,0,1,1100,-71,8,1,0,0,868000000,LORA,7,125,4,10,51,0,0,0,0,0,0,23456",
            "PKT,42,3,0,2,1200,-73,7,1,0,0,868000000,LORA,7,125,4,10,51,0,0,0,0,0,0,34567",
        ]
        ctrl = MockBoardController(role="RX")
        ctrl.drained_lines = list(pkts)
        tools = self.BoardTools(ctrl, role="RX")
        result = tools.dispatch_tool("board_capture",
                                    {"duration_s": 0.01, "config_idx": 3})
        self.assertTrue(result["ok"])
        self.assertEqual(result["n"], 3)
        # All packets have bit_err=0 → k=0
        self.assertEqual(result["k"], 0)
        self.assertEqual(len(result["pkts"]), 3)
        # Lines retained for debugging
        self.assertTrue(any("PKT" in l for l in result["lines"]))

    async def test_board_capture_filters_config_idx(self):
        # Mix of config_idx=3 (matching) and config_idx=5 (off-target)
        pkts = [
            "PKT,42,3,0,0,1000,-72,8,1,0,0,868000000,LORA,7,125,4,10,51,0,0,0,0,0,0,11111",
            "PKT,42,5,0,0,1000,-72,8,1,0,0,868000000,LORA,7,125,4,10,51,0,0,0,0,0,0,22222",
            "PKT,42,3,0,1,1100,-71,8,1,0,0,868000000,LORA,7,125,4,10,51,0,0,0,0,0,0,33333",
        ]
        ctrl = MockBoardController(role="RX")
        ctrl.drained_lines = list(pkts)
        tools = self.BoardTools(ctrl, role="RX")
        result = tools.dispatch_tool("board_capture",
                                    {"duration_s": 0.01, "config_idx": 3})
        self.assertTrue(result["ok"])
        self.assertEqual(result["n"], 2, "only 2 packets match config_idx=3")
        for pkt in result["pkts"]:
            self.assertEqual(pkt["config"], 3)

    async def test_board_capture_k_counts_bit_err(self):
        # 1 of 3 packets has bit_err > 0 → k=1
        pkts = [
            "PKT,42,3,0,0,1000,-72,8,1,0,0,868000000,LORA,7,125,4,10,51,0,0,0,0,0,0,1",
            "PKT,42,3,0,1,1100,-71,8,1,3,0,868000000,LORA,7,125,4,10,51,0,0,0,0,0,0,2",
            "PKT,42,3,0,2,1200,-73,7,1,0,0,868000000,LORA,7,125,4,10,51,0,0,0,0,0,0,3",
        ]
        ctrl = MockBoardController(role="RX")
        ctrl.drained_lines = list(pkts)
        tools = self.BoardTools(ctrl, role="RX")
        result = tools.dispatch_tool("board_capture",
                                    {"duration_s": 0.01, "config_idx": 3})
        self.assertTrue(result["ok"])
        self.assertEqual(result["n"], 3)
        self.assertEqual(result["k"], 1, "exactly one packet had bit_err > 0")

    async def test_board_info_includes_role_port_fw(self):
        ctrl = MockBoardController(role="TX",
                                   replies={"ID?": "ID E80BENCH fw=0561b29 role=TX"})
        tools = self.BoardTools(ctrl, role="TX")
        result = tools.dispatch_tool("board_info", {})
        self.assertTrue(result["ok"])
        self.assertEqual(result["role"], "TX")
        self.assertEqual(result["port"], "/dev/ttyMOCK")
        self.assertEqual(result["fw"], "0561b29")
        # TCP-vs-CVM detectable from id_reply prefix

    async def test_board_info_inactive_board(self):
        class DeadCtrl(MockBoardController):
            def id_query(self):
                return None
            def ensure_alive(self):
                return False
        ctrl = DeadCtrl(role="TX")
        tools = self.BoardTools(ctrl, role="TX")
        result = tools.dispatch_tool("board_info", {})
        self.assertTrue(result["ok"])
        self.assertFalse(result["alive"])


# ===========================================================================
# JSON-RPC DISPATCH TESTS
# ===========================================================================

class TestCVMRPCDispatch(unittest.IsolatedAsyncioTestCase):
    """Tests the CVMBoardServer.dispatch_rpc() JSON-RPC layer."""

    async def asyncSetUp(self):
        from cvm_board_server import BoardTools, CVMBoardServer, JSON_RPC_ERROR
        self.JSON_RPC_ERROR = JSON_RPC_ERROR
        # Use mock keys (no real key needed for dispatch) — but a placeholders
        # pubkey works for dispatch_rpc since we never check sender here.
        ctrl = MockBoardController(role="TX",
                                   replies={"ID?": "ID E80BENCH fw=0561b29 role=TX"})
        tools = BoardTools(ctrl, role="TX")
        self.server = CVMBoardServer(tools, server_keys=None, relays=[],
                                      role="TX")

    async def test_valid_method_returns_result(self):
        rpc = {"jsonrpc": "2.0", "method": "tools/call",
               "params": {"name": "board_stat", "arguments": {}}, "id": 1}
        resp = await self.server.dispatch_rpc(rpc, "client")
        self.assertEqual(resp["jsonrpc"], "2.0")
        self.assertEqual(resp["id"], 1)
        self.assertIn("result", resp)
        self.assertIn("content", resp["result"])
        self.assertGreaterEqual(len(resp["result"]["content"]), 1)

    async def test_unknown_method_returns_error(self):
        rpc = {"jsonrpc": "2.0", "method": "tools/call",
               "params": {"name": "unknown_tool"}, "id": 2}
        resp = await self.server.dispatch_rpc(rpc, "client")
        self.assertEqual(resp["id"], 2)
        self.assertIn("error", resp)
        self.assertEqual(resp["error"]["code"], self.JSON_RPC_ERROR["METHOD_NOT_FOUND"])

    async def test_malformed_rpc_returns_parse_error(self):
        rpc = {"jsonrpc": "2.0", "method": "tools/call", "params": "not_a_dict", "id": 3}
        resp = await self.server.dispatch_rpc(rpc, "client")
        self.assertIn("error", resp)
        self.assertEqual(resp["error"]["code"], self.JSON_RPC_ERROR["INVALID_PARAMS"])

    async def test_missing_method_key_returns_invalid_request(self):
        rpc = {"jsonrpc": "2.0", "id": 4}
        resp = await self.server.dispatch_rpc(rpc, "client")
        self.assertIn("error", resp)
        self.assertEqual(resp["error"]["code"], self.JSON_RPC_ERROR["INVALID_REQUEST"])

    async def test_tool_internal_error_returns_internal_error(self):
        # Force board_query to raise
        with patch.object(self.server.tools, "dispatch_tool") as m:
            m.side_effect = RuntimeError("unexpected board drivers missing")
            rpc = {"jsonrpc": "2.0", "method": "tools/call",
                   "params": {"name": "board_stat", "arguments": {}}, "id": 5}
            resp = await self.server.dispatch_rpc(rpc, "client")
        self.assertIn("error", resp)
        self.assertEqual(resp["error"]["code"], self.JSON_RPC_ERROR["INTERNAL_ERROR"])
        self.assertIn("unexpected board", resp["error"]["message"])


# ===========================================================================
# CVM TRANSPORT (MOCK) INTEGRATION TESTS
# ===========================================================================

class TestMockTransportIntegration(unittest.IsolatedAsyncioTestCase):
    """End-to-end test through the MockCVMTransport (no real Nostr)."""

    async def test_client_calls_server_through_mock_transport(self):
        from cvm_board_server import BoardTools, CVMBoardServer
        from cvm_campaign import CVMClient

        # Build a TX server
        ctrl_tx = MockBoardController(role="TX",
                                       replies={"ID?": "ID E80BENCH fw=0561b29 role=TX"})
        tools_tx = BoardTools(ctrl_tx, role="TX")
        server = CVMBoardServer(tools_tx, server_keys=None, relays=[], role="TX")

        # Build mock transport, register server
        transport = MockCVMTransport()
        npub_hex_server = "deadbeef" * 8
        await transport.register_server(npub_hex_server,
                                         lambda rpc, client_npub: server.dispatch_rpc(rpc, client_npub))
        # Build client backed by mock transport
        client_keys_hex = "1234567890abcdef" * 4
        tx_client = CVMClient(server_npub_hex=npub_hex_server,
                                client_keys_hex=client_keys_hex,
                                relays=[], transport=transport)

        # Invoke "board_stat" — should round-trip via mock transport
        result = await tx_client.call("board_stat", {})
        self.assertTrue(result["ok"])
        self.assertIn("reply", result)

    async def test_client_calls_both_tx_and_rx_servers(self):
        from cvm_board_server import BoardTools, CVMBoardServer
        from cvm_campaign import CVMClient

        # TX server
        ctrl_tx = MockBoardController(role="TX",
                                       replies={"ID?": "ID E80BENCH fw=0561b29 role=TX"})
        tx_server = CVMBoardServer(BoardTools(ctrl_tx, role="TX"),
                                    server_keys=None, relays=[], role="TX")

        # RX server  
        pkts = [
            "PKT,42,3,0,0,1000,-72,8,1,0,0,868000000,LORA,7,125,4,10,51,0,0,0,0,0,0,1",
            "PKT,42,3,0,1,1100,-71,8,1,0,0,868000000,LORA,7,125,4,10,51,0,0,0,0,0,0,2",
        ]
        ctrl_rx = MockBoardController(role="RX")
        ctrl_rx.drained_lines = list(pkts)
        rx_server = CVMBoardServer(BoardTools(ctrl_rx, role="RX"),
                                    server_keys=None, relays=[], role="RX")

        transport = MockCVMTransport()
        await transport.register_server("aabb" * 16,
                                         lambda r, c: tx_server.dispatch_rpc(r, c))
        await transport.register_server("ccdd" * 16,
                                         lambda r, c: rx_server.dispatch_rpc(r, c))

        tx_client = CVMClient("aabb" * 16, "00" * 32, [], transport=transport)
        rx_client = CVMClient("ccdd" * 16, "00" * 32, [], transport=transport)

        # TX arm
        r1 = await tx_client.call("board_send", {"line": "ROLE TX"})
        self.assertTrue(r1["ok"])
        # RX capture
        r2 = await rx_client.call("board_capture", {"duration_s": 0.01, "config_idx": 3})
        self.assertTrue(r2["ok"])
        self.assertEqual(r2["n"], 2)


# ===========================================================================
# GIFT WRAP ROUND TRIP TEST (skip if nostr_sdk missing)
# ===========================================================================

@unittest.skipUnless(TestPlatform.have_nostr_sdk(),
                     "nostr_sdk not installed (CI image without Rust bindings)")
class TestGiftWrapRoundTrip(unittest.TestCase):
    """Verifies the NIP-44/NIP-59 gift wrap round trip locally without relays."""

    def test_wrap_and_unwrap_preserves_payload(self):
        import nostr_sdk
        import json
        client_keys = nostr_sdk.Keys.generate()
        server_keys = nostr_sdk.Keys.generate()
        client_signer = nostr_sdk.NostrSigner.keys(client_keys)
        server_signer = nostr_sdk.NostrSigner.keys(server_keys)

        payload = {"jsonrpc": "2.0", "method": "tools/call",
                   "params": {"name": "board_query", "arguments": {"line": "ID?"}},
                   "id": 7}
        inner = nostr_sdk.UnsignedEvent.from_json(json.dumps({
            "pubkey": client_keys.public_key().to_hex(),
            "kind": 25910, "tags": [["p", server_keys.public_key().to_hex()]],
            "content": json.dumps(payload),
            "created_at": nostr_sdk.Timestamp.now().as_secs()
        }))
        gw = asyncio.run(nostr_sdk.gift_wrap(client_signer,
                                              server_keys.public_key(), inner))
        # Server unwraps
        unwrapped = asyncio.run(
            nostr_sdk.UnwrappedGift.from_gift_wrap(server_signer, gw))
        inner_result = unwrapped.rumor()
        # nostr_sdk Kind is a Rust enum wrapper (Custom(25910)); compare via
        # as_u16() to get the integer value (25910 fits in u16).
        self.assertEqual(inner_result.kind().as_u16(), 25910)
        self.assertEqual(inner_result.author(), client_keys.public_key())
        # Payload preserved through wrap+unwrap
        parsed = json.loads(inner_result.content())
        self.assertEqual(parsed, payload)


# ===========================================================================
# CVM CAMPAIGN INTEGRATION (SPRT loop with mock clients)
# ===========================================================================

class TestCVMCampaignSPRT(unittest.IsolatedAsyncioTestCase):
    """Tests cvm_sprt_run() — the distributed replacement for sprt_run()."""

    async def test_clean_burst_returns_clean(self):
        """A burst with 0 bit errors in n=10 packets should yield CLEAN via SPRT."""
        from cvm_campaign import cvm_sprt_run
        from cvm_board_server import BoardTools, CVMBoardServer
        from cvm_campaign import CVMClient

        # Pre-seed 10 clean packets on the RX server
        pkts = [
            f"PKT,42,3,0,{i},{1000+i},-72,8,1,0,0,868000000,LORA,7,125,4,10,51,0,0,0,0,0,0,{i}"
            for i in range(20)
        ]
        ctrl_rx = MockBoardController(role="RX")
        ctrl_rx.drained_lines = list(pkts)
        rx_server = CVMBoardServer(BoardTools(ctrl_rx, role="RX"),
                                    server_keys=None, relays=[], role="RX")
        ctrl_tx = MockBoardController(role="TX",
                                       replies={"ARM TX": "OK ARMED"})
        tx_server = CVMBoardServer(BoardTools(ctrl_tx, role="TX"),
                                    server_keys=None, relays=[], role="TX")

        transport = MockCVMTransport()
        await transport.register_server("aabb" * 16,
                                         lambda r, c: tx_server.dispatch_rpc(r, c))
        await transport.register_server("ccdd" * 16,
                                         lambda r, c: rx_server.dispatch_rpc(r, c))

        tx_client = CVMClient("aabb" * 16, "00" * 32, [], transport=transport)
        rx_client = CVMClient("ccdd" * 16, "00" * 32, [], transport=transport)

        cfg = {"mod": "lora", "sf": 7, "bw": 125, "pa": 10,
               "freq": 868000000, "plen": 51, "gap": 10000,
               "label": "CLEAN-SF7-BW125"}
        result = await cvm_sprt_run(cfg, tx_client, rx_client,
                                    session_id=42, cfg_idx=3, n_cap=20)
        # 20 clean packets → LLR ≤ LLR_LOW → CLEAN
        self.assertEqual(result.verdict, "CLEAN")
        self.assertEqual(result.n, 20)
        self.assertEqual(result.k, 0)

    async def test_dead_burst_returns_dead(self):
        """A burst with all bit errors should yield DEAD via SPRT."""
        from cvm_campaign import cvm_sprt_run
        from cvm_board_server import BoardTools, CVMBoardServer
        from cvm_campaign import CVMClient

        # All packets have bit_err > 0
        pkts = [
            f"PKT,42,3,0,{i},{1000+i},-72,8,1,5,0,868000000,LORA,7,125,4,10,51,0,0,0,0,0,0,{i}"
            for i in range(20)
        ]
        ctrl_rx = MockBoardController(role="RX")
        ctrl_rx.drained_lines = list(pkts)
        rx_server = CVMBoardServer(BoardTools(ctrl_rx, role="RX"),
                                    server_keys=None, relays=[], role="RX")
        ctrl_tx = MockBoardController(role="TX",
                                       replies={"ARM TX": "OK ARMED"})
        tx_server = CVMBoardServer(BoardTools(ctrl_tx, role="TX"),
                                    server_keys=None, relays=[], role="TX")

        transport = MockCVMTransport()
        await transport.register_server("aabb" * 16,
                                         lambda r, c: tx_server.dispatch_rpc(r, c))
        await transport.register_server("ccdd" * 16,
                                         lambda r, c: rx_server.dispatch_rpc(r, c))

        tx_client = CVMClient("aabb" * 16, "00" * 32, [], transport=transport)
        rx_client = CVMClient("ccdd" * 16, "00" * 32, [], transport=transport)

        cfg = {"mod": "lora", "sf": 7, "bw": 125, "pa": 10,
               "freq": 868000000, "plen": 51, "gap": 10000,
               "label": "DEAD-SF7-BW125"}
        result = await cvm_sprt_run(cfg, tx_client, rx_client,
                                    session_id=42, cfg_idx=3, n_cap=20)
        # All bit errors → LLR ≥ LLR_HIGH → DEAD
        self.assertEqual(result.verdict, "DEAD")


# ===========================================================================
# Entry point
# ===========================================================================

if __name__ == "__main__":
    unittest.main(verbosity=2)
