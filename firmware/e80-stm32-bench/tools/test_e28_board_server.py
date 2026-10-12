#!/usr/bin/env python3
"""test_e28_board_server.py — unit tests for the E28 CVM board server.

Runs without real hardware or Nostr relays. The Nostr layer is mocked via
`MockCVMTransport` (routes gift-wrapped events between registered handlers
in-memory). The E28 serial console is mocked via `MockE28Controller` with
scripted serial replies matching the E28 ranging console protocol
(firmware/esp32-e28-range/src/e28_range_console.c):

    ID?          -> E28-RANGE v1.0 fw=<hash>
    STAT?        -> role=<master|slave|idle> freq=<MHz> sf=<n> bw=<kHz>
                    pa=<dBm> addr=<0x…> last=<m|none> err=<code>
    RANGE        -> master: DIST=<m>m | RANGE TIMEOUT
    RANGE-SLAVE  -> slave: SLAVE OK
    RANGE?       -> DIST=<m>m (or DIST=none)
    FREQ <hz> / SF <n> / BW <khz> / PA <dbm> / ADDR <hex> / HELP

Run:  python3 -m pytest test_e28_board_server.py -v
Or:   python3 test_e28_board_server.py            (no pytest needed)
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
import unittest

# Add tools dir for imports
_TOOLS_DIR = os.path.dirname(os.path.abspath(__file__))
if _TOOLS_DIR not in sys.path:
    sys.path.insert(0, _TOOLS_DIR)


# ---------------------------------------------------------------------------
# Mock E28 controller — mimics the E28 ranging serial console
# ---------------------------------------------------------------------------

class MockE28Controller:
    """In-memory controller that mimics the E28 ranging serial console."""

    def __init__(self, role="TX", replies=None):
        self.role = role
        self.port = "/dev/ttyE28MOCK"
        self.replies = replies or {}  # line → reply string
        self.written: list[str] = []
        self.alive = True

    def query(self, line, prefixes=("OK", "ERR", "STAT", "ID", "DIST", "SLAVE"),
              timeout=15.0):
        self.written.append(line)
        # Look for reply — try exact match, then prefix
        r = self.replies.get(line)
        if r is None:
            for k, v in self.replies.items():
                if line.startswith(k):
                    r = v
                    break
        if r is None:
            # Default pattern per E28 console protocol
            if line == "ID?":
                r = "E28-RANGE v1.0 fw=2a088f0"
            elif line == "STAT?":
                r = ("role=idle freq=2440 sf=7 bw=812.5 pa=10 "
                     "addr=0xE80E2801 last=none err=0")
            elif line == "RANGE?":
                r = "DIST=none"
            elif line == "RANGE":
                r = "DIST=12.34m"
            elif line == "RANGE-SLAVE":
                r = "SLAVE OK"
            else:
                r = f"OK {line.upper()}"
        if r.startswith("ERR"):
            raise RuntimeError(f"E28 rejected '{line}': {r}")
        return r

    def cmd(self, line, timeout=15.0):
        return self.query(line, prefixes=("OK", "ERR"), timeout=timeout)

    def send(self, line):
        """Fire-and-forget write (E28 FREQ/SF/BW/PA emit no success reply)."""
        self.written.append(line)
        return None

    def id_query(self):
        return self.replies.get("ID?", "E28-RANGE v1.0 fw=2a088f0")

    def ensure_alive(self):
        return self.alive

    def close(self):
        pass


# ---------------------------------------------------------------------------
# Mock CVM transport — simulates the Nostr relay pool in-memory
# ---------------------------------------------------------------------------

class MockCVMTransport:
    """In-memory bus that routes JSON-RPC requests between client and server."""

    def __init__(self):
        self.servers: dict[str, callable] = {}  # npub_hex → dispatch_fn

    async def register_server(self, npub_hex, dispatch_fn):
        self.servers[npub_hex] = dispatch_fn

    async def call(self, target_npub, rpc_request, timeout=30):
        if target_npub not in self.servers:
            return {
                "jsonrpc": "2.0", "id": rpc_request.get("id"),
                "error": {"code": -32001, "message": f"unknown server: {target_npub[:8]}..."}
            }
        dispatch = self.servers[target_npub]
        result = dispatch(rpc_request, "client")
        if asyncio.iscoroutine(result):
            result = await result
        return result


# ===========================================================================
# E28 TOOLS TESTS (pure Python, no Nostr)
# ===========================================================================

class TestE28Tools(unittest.IsolatedAsyncioTestCase):
    """Tests the E28Tools layer (serial wrapper without Nostr)."""

    async def asyncSetUp(self):
        from e28_board_server import E28Tools
        self.E28Tools = E28Tools

    async def test_unknown_tool_returns_error(self):
        ctrl = MockE28Controller(role="TX")
        tools = self.E28Tools(ctrl, role="TX")
        with self.assertRaises(ValueError) as ctx:
            tools.dispatch_tool("nonexistent_tool", {})
        self.assertIn("unknown", str(ctx.exception).lower())

    # --- e28_range (TX master) ---

    async def test_e28_range_tx_master(self):
        ctrl = MockE28Controller(role="TX",
                                replies={"RANGE": "DIST=12.34m"})
        tools = self.E28Tools(ctrl, role="TX")
        result = tools.dispatch_tool("e28_range", {})
        self.assertTrue(result["ok"])
        self.assertIn("DIST", result["status"])
        self.assertIn("RANGE", ctrl.written)

    async def test_e28_range_role_enforced_tx_only(self):
        # RX side must NOT be able to initiate a master ranging exchange
        ctrl = MockE28Controller(role="RX")
        tools = self.E28Tools(ctrl, role="RX")
        result = tools.dispatch_tool("e28_range", {})
        self.assertFalse(result["ok"])
        self.assertIn("role", result["error"].lower())
        self.assertNotIn("RANGE", ctrl.written)

    async def test_e28_range_timeout(self):
        ctrl = MockE28Controller(role="TX",
                                replies={"RANGE": "RANGE TIMEOUT"})
        tools = self.E28Tools(ctrl, role="TX")
        result = tools.dispatch_tool("e28_range", {})
        self.assertTrue(result["ok"])
        self.assertIn("TIMEOUT", result["status"])

    # --- e28_range_slave (RX responder) ---

    async def test_e28_range_slave_rx(self):
        ctrl = MockE28Controller(role="RX",
                                 replies={"RANGE-SLAVE": "SLAVE OK"})
        tools = self.E28Tools(ctrl, role="RX")
        result = tools.dispatch_tool("e28_range_slave", {})
        self.assertTrue(result["ok"])
        self.assertIn("SLAVE OK", result["status"])
        self.assertIn("RANGE-SLAVE", ctrl.written)

    async def test_e28_range_slave_role_enforced_rx_only(self):
        # TX side must NOT respond as a slave
        ctrl = MockE28Controller(role="TX")
        tools = self.E28Tools(ctrl, role="TX")
        result = tools.dispatch_tool("e28_range_slave", {})
        self.assertFalse(result["ok"])
        self.assertIn("role", result["error"].lower())
        self.assertNotIn("RANGE-SLAVE", ctrl.written)

    # --- e28_query (distance) ---

    async def test_e28_query_parses_distance(self):
        ctrl = MockE28Controller(role="TX",
                                 replies={"RANGE?": "DIST=12.34m"})
        tools = self.E28Tools(ctrl, role="TX")
        result = tools.dispatch_tool("e28_query", {})
        self.assertTrue(result["ok"])
        self.assertAlmostEqual(result["distance_m"], 12.34, places=2)
        self.assertIn("RANGE?", ctrl.written)

    async def test_e28_query_no_result(self):
        ctrl = MockE28Controller(role="TX",
                                 replies={"RANGE?": "DIST=none"})
        tools = self.E28Tools(ctrl, role="TX")
        result = tools.dispatch_tool("e28_query", {})
        self.assertTrue(result["ok"])
        self.assertIsNone(result["distance_m"])

    # --- e28_config (best-effort) ---

    async def test_e28_config_sends_commands(self):
        ctrl = MockE28Controller(role="TX")
        tools = self.E28Tools(ctrl, role="TX")
        result = tools.dispatch_tool("e28_config",
                                     {"freq": 2440000000, "sf": 7,
                                      "bw": 812.5, "pa": 10})
        self.assertTrue(result["ok"])
        # FREQ, SF, BW, PA commands should have been written
        self.assertTrue(any(w.startswith("FREQ") for w in ctrl.written))
        self.assertTrue(any(w.startswith("SF") for w in ctrl.written))
        self.assertTrue(any(w.startswith("BW") for w in ctrl.written))
        self.assertTrue(any(w.startswith("PA") for w in ctrl.written))

    async def test_e28_config_empty_uses_known_good(self):
        # No args → best-effort known-good manual config (no crash)
        ctrl = MockE28Controller(role="TX")
        tools = self.E28Tools(ctrl, role="TX")
        result = tools.dispatch_tool("e28_config", {})
        self.assertTrue(result["ok"])


# ===========================================================================
# JSON-RPC DISPATCH TESTS
# ===========================================================================

class TestE28CVMRPCDispatch(unittest.IsolatedAsyncioTestCase):
    """Tests the E28BoardServer.dispatch_rpc() JSON-RPC layer."""

    async def asyncSetUp(self):
        from e28_board_server import E28Tools, E28BoardServer, JSON_RPC_ERROR
        self.JSON_RPC_ERROR = JSON_RPC_ERROR
        ctrl = MockE28Controller(role="TX")
        tools = E28Tools(ctrl, role="TX")
        self.server = E28BoardServer(tools, server_keys=None, relays=[],
                                     role="TX")

    async def test_valid_method_returns_result(self):
        rpc = {"jsonrpc": "2.0", "method": "tools/call",
               "params": {"name": "e28_query", "arguments": {}}, "id": 1}
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


# ===========================================================================
# CVM TRANSPORT (MOCK) INTEGRATION TESTS
# ===========================================================================

class TestE28MockTransportIntegration(unittest.IsolatedAsyncioTestCase):
    """End-to-end test through the MockCVMTransport (no real Nostr)."""

    async def test_client_calls_e28_server_through_mock_transport(self):
        from e28_board_server import E28Tools, E28BoardServer
        from cvm_campaign import CVMClient

        ctrl = MockE28Controller(role="TX",
                                 replies={"RANGE?": "DIST=12.34m"})
        tools = E28Tools(ctrl, role="TX")
        server = E28BoardServer(tools, server_keys=None, relays=[], role="TX")

        transport = MockCVMTransport()
        npub_hex_server = "deadbeef" * 8
        await transport.register_server(
            npub_hex_server,
            lambda rpc, client_npub: server.dispatch_rpc(rpc, client_npub))
        client_keys_hex = "1234567890abcdef" * 4
        tx_client = CVMClient(server_npub_hex=npub_hex_server,
                              client_keys_hex=client_keys_hex,
                              relays=[], transport=transport)

        result = await tx_client.call("e28_query", {})
        self.assertTrue(result["ok"])
        self.assertAlmostEqual(result["distance_m"], 12.34, places=2)

    async def test_client_calls_both_tx_and_rx_e28_servers(self):
        from e28_board_server import E28Tools, E28BoardServer
        from cvm_campaign import CVMClient

        # TX server (master)
        ctrl_tx = MockE28Controller(role="TX",
                                    replies={"RANGE": "DIST=12.34m"})
        tx_server = E28BoardServer(E28Tools(ctrl_tx, role="TX"),
                                  server_keys=None, relays=[], role="TX")
        # RX server (slave)
        ctrl_rx = MockE28Controller(role="RX",
                                    replies={"RANGE-SLAVE": "SLAVE OK"})
        rx_server = E28BoardServer(E28Tools(ctrl_rx, role="RX"),
                                  server_keys=None, relays=[], role="RX")

        transport = MockCVMTransport()
        await transport.register_server("aabb" * 16,
                                        lambda r, c: tx_server.dispatch_rpc(r, c))
        await transport.register_server("ccdd" * 16,
                                        lambda r, c: rx_server.dispatch_rpc(r, c))

        tx_client = CVMClient("aabb" * 16, "00" * 32, [], transport=transport)
        rx_client = CVMClient("ccdd" * 16, "00" * 32, [], transport=transport)

        # TX initiates master ranging
        r1 = await tx_client.call("e28_range", {})
        self.assertTrue(r1["ok"])
        # RX responds as slave
        r2 = await rx_client.call("e28_range_slave", {})
        self.assertTrue(r2["ok"])
        self.assertIn("SLAVE OK", r2["status"])
        # TX queries distance
        r3 = await tx_client.call("e28_query", {})
        self.assertTrue(r3["ok"])
        self.assertAlmostEqual(r3["distance_m"], 12.34, places=2)


if __name__ == "__main__":
    unittest.main()
