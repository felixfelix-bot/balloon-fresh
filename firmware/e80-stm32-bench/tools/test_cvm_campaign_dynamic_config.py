#!/usr/bin/env python3
"""test_cvm_campaign_dynamic_config.py — TDD tests for dynamic config pushing.

Tests that cvm_campaign.py uses the set_config MCP tool to push configs to
both TX and RX boards dynamically, instead of sending individual board_send
commands for MOD/FREQ/PA/ROLE.

RED phase: these tests are written BEFORE the implementation. They should
FAIL against the current cvm_sprt_run() which uses board_send for radio config.

Run:  python3 -m pytest test_cvm_campaign_dynamic_config.py -v
Or:   python3 test_cvm_campaign_dynamic_config.py
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
import unittest
from unittest.mock import MagicMock, patch, call

# Add tools dir for imports
_TOOLS_DIR = os.path.dirname(os.path.abspath(__file__))
if _TOOLS_DIR not in sys.path:
    sys.path.insert(0, _TOOLS_DIR)

# Reuse the mock infrastructure from the existing CVM test suite
from test_cvm_board_server import MockBoardController, MockCVMTransport


# ===========================================================================
# Helpers — build a single-config preset for set_config inline JSON
# ===========================================================================

def _single_config_preset(cfg: dict) -> str:
    """Wrap a single config entry into a preset JSON string for set_config."""
    return json.dumps({
        "name": "dynamic",
        "configs": [cfg],
    })


def _sample_lora_cfg() -> dict:
    """Return a sample LoRa config entry."""
    return {
        "label": "LoRa-SF7 BW125 LEN255",
        "mod": "lora", "sf": 7, "bw": 125, "br": None,
        "pa": 10, "freq": 868000000,
        "plen": 255, "gap": 10000, "n_pkts": 10,
    }


def _sample_flrc_cfg() -> dict:
    """Return a sample FLRC config entry."""
    return {
        "label": "FLRC-650 LEN511",
        "mod": "flrc", "sf": None, "bw": None, "br": 650,
        "pa": 10, "freq": 868000000,
        "plen": 511, "gap": 5000, "n_pkts": 10,
    }


# ===========================================================================
# Test: cvm_sprt_run uses set_config instead of individual board_send
# ===========================================================================

class TestDynamicConfigPushing(unittest.IsolatedAsyncioTestCase):
    """RED phase: verify cvm_sprt_run calls set_config on both boards."""

    async def test_sprt_run_calls_set_config_on_tx(self):
        """cvm_sprt_run should call set_config on the TX client."""
        from cvm_campaign import cvm_sprt_run
        from cvm_board_server import BoardTools, CVMBoardServer
        from cvm_campaign import CVMClient

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

        # Patch tx_client.call to track tool names
        original_tx_call = tx_client.call
        tx_tool_calls = []
        async def tracking_tx_call(tool_name, arguments, timeout=None):
            tx_tool_calls.append(tool_name)
            return await original_tx_call(tool_name, arguments, timeout=timeout)
        tx_client.call = tracking_tx_call

        cfg = _sample_lora_cfg()
        await cvm_sprt_run(cfg, tx_client, rx_client,
                           session_id=42, cfg_idx=3, n_cap=20)

        self.assertIn("set_config", tx_tool_calls,
                      "cvm_sprt_run should call set_config on TX client, "
                      f"got: {tx_tool_calls}")

    async def test_sprt_run_calls_set_config_on_rx(self):
        """cvm_sprt_run should call set_config on the RX client."""
        from cvm_campaign import cvm_sprt_run
        from cvm_board_server import BoardTools, CVMBoardServer
        from cvm_campaign import CVMClient

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

        # Patch rx_client.call to track tool names
        original_rx_call = rx_client.call
        rx_tool_calls = []
        async def tracking_rx_call(tool_name, arguments, timeout=None):
            rx_tool_calls.append(tool_name)
            return await original_rx_call(tool_name, arguments, timeout=timeout)
        rx_client.call = tracking_rx_call

        cfg = _sample_lora_cfg()
        await cvm_sprt_run(cfg, tx_client, rx_client,
                           session_id=42, cfg_idx=3, n_cap=20)

        self.assertIn("set_config", rx_tool_calls,
                      "cvm_sprt_run should call set_config on RX client, "
                      f"got: {rx_tool_calls}")

    async def test_set_config_receives_single_config_as_json(self):
        """set_config should receive config_json with a single config entry,
        not the entire preset."""
        from cvm_campaign import cvm_sprt_run
        from cvm_board_server import BoardTools, CVMBoardServer
        from cvm_campaign import CVMClient

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

        # Capture set_config arguments
        captured_args = []
        original_tx_call = tx_client.call
        async def capturing_tx_call(tool_name, arguments, timeout=None):
            if tool_name == "set_config":
                captured_args.append(arguments)
            return await original_tx_call(tool_name, arguments, timeout=timeout)
        tx_client.call = capturing_tx_call

        cfg = _sample_lora_cfg()
        await cvm_sprt_run(cfg, tx_client, rx_client,
                           session_id=42, cfg_idx=3, n_cap=20)

        self.assertTrue(len(captured_args) > 0,
                        "set_config was not called on TX")
        args = captured_args[0]
        # Should use config_json mode (inline JSON), not config_name
        self.assertIn("config_json", args,
                      "set_config should use config_json for dynamic pushing")
        # The JSON should contain exactly 1 config entry
        preset = json.loads(args["config_json"])
        self.assertEqual(len(preset["configs"]), 1,
                         "set_config should receive a single config entry")
        self.assertEqual(preset["configs"][0]["label"], cfg["label"],
                         "set_config should receive the correct config")

    async def test_no_individual_mod_freq_pa_role_board_send(self):
        """cvm_sprt_run should NOT send individual MOD/FREQ/PA/ROLE via
        board_send — set_config handles those."""
        from cvm_campaign import cvm_sprt_run
        from cvm_board_server import BoardTools, CVMBoardServer
        from cvm_campaign import CVMClient

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

        # Track all board_send lines
        board_send_lines = []
        original_tx_call = tx_client.call
        async def tracking_tx_call(tool_name, arguments, timeout=None):
            if tool_name == "board_send":
                board_send_lines.append(arguments.get("line", ""))
            return await original_tx_call(tool_name, arguments, timeout=timeout)
        tx_client.call = tracking_tx_call

        original_rx_call = rx_client.call
        async def tracking_rx_call(tool_name, arguments, timeout=None):
            if tool_name == "board_send":
                board_send_lines.append(arguments.get("line", ""))
            return await original_rx_call(tool_name, arguments, timeout=timeout)
        rx_client.call = tracking_rx_call

        cfg = _sample_lora_cfg()
        await cvm_sprt_run(cfg, tx_client, rx_client,
                           session_id=42, cfg_idx=3, n_cap=20)

        # board_send should NOT contain MOD, FREQ, PA, ROLE lines
        # (SESSION and CONFIG are still OK via board_send)
        mod_lines = [l for l in board_send_lines if l.startswith("MOD")]
        freq_lines = [l for l in board_send_lines if l.startswith("FREQ")]
        role_lines = [l for l in board_send_lines if l.startswith("ROLE")]
        pa_lines = [l for l in board_send_lines if l.startswith("PA ")]

        self.assertEqual(len(mod_lines), 0,
                         f"MOD should be sent via set_config, not board_send. "
                         f"Found: {mod_lines}")
        self.assertEqual(len(freq_lines), 0,
                         f"FREQ should be sent via set_config, not board_send. "
                         f"Found: {freq_lines}")
        self.assertEqual(len(role_lines), 0,
                         f"ROLE should be sent via set_config, not board_send. "
                         f"Found: {role_lines}")
        self.assertEqual(len(pa_lines), 0,
                         f"PA should be sent via set_config, not board_send. "
                         f"Found: {pa_lines}")

    async def test_sprt_verdict_still_correct_after_set_config(self):
        """SPRT verdict should still work correctly when using set_config."""
        from cvm_campaign import cvm_sprt_run
        from cvm_board_server import BoardTools, CVMBoardServer
        from cvm_campaign import CVMClient

        # 20 clean packets → CLEAN
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

        cfg = _sample_lora_cfg()
        result = await cvm_sprt_run(cfg, tx_client, rx_client,
                                    session_id=42, cfg_idx=3, n_cap=20)
        self.assertEqual(result.verdict, "CLEAN")
        self.assertEqual(result.n, 20)
        self.assertEqual(result.k, 0)

    async def test_set_config_failure_returns_dead(self):
        """If set_config fails on TX, cvm_sprt_run should return DEAD."""
        from cvm_campaign import cvm_sprt_run

        # Mock clients where TX set_config returns ok=False.
        # Use a mock that returns awaitable results.
        class FakeClient:
            def __init__(self, responses):
                self._responses = list(responses)
                self._idx = 0
            async def call(self, tool_name, arguments, timeout=None):
                if self._idx < len(self._responses):
                    r = self._responses[self._idx]
                    self._idx += 1
                    return r
                return {"ok": False, "error": "no more responses"}

        tx_client = FakeClient([
            {"ok": False, "error": "board not responding"},  # TX set_config
        ])
        rx_client = FakeClient([
            {"ok": True, "responses": []},  # RX set_config
        ])

        cfg = _sample_lora_cfg()
        result = await cvm_sprt_run(cfg, tx_client, rx_client,
                                    session_id=42, cfg_idx=3, n_cap=20)
        self.assertEqual(result.verdict, "DEAD")

    async def test_set_config_with_flrc_config(self):
        """set_config should work with FLRC configs too."""
        from cvm_campaign import cvm_sprt_run
        from cvm_board_server import BoardTools, CVMBoardServer
        from cvm_campaign import CVMClient

        pkts = [
            f"PKT,42,3,0,{i},{1000+i},-72,8,1,0,0,868000000,FLRC,0,0,650,10,51,0,0,0,0,0,0,{i}"
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

        # Capture set_config arguments
        captured_args = []
        original_tx_call = tx_client.call
        async def capturing_tx_call(tool_name, arguments, timeout=None):
            if tool_name == "set_config":
                captured_args.append(arguments)
            return await original_tx_call(tool_name, arguments, timeout=timeout)
        tx_client.call = capturing_tx_call

        cfg = _sample_flrc_cfg()
        await cvm_sprt_run(cfg, tx_client, rx_client,
                           session_id=42, cfg_idx=3, n_cap=20)

        self.assertTrue(len(captured_args) > 0,
                        "set_config was not called on TX for FLRC config")
        preset = json.loads(captured_args[0]["config_json"])
        self.assertEqual(preset["configs"][0]["mod"], "flrc")

    async def test_board_commands_sent_after_set_config(self):
        """After set_config, board_start_burst should be called on TX and
        board_capture on RX."""
        from cvm_campaign import cvm_sprt_run
        from cvm_board_server import BoardTools, CVMBoardServer
        from cvm_campaign import CVMClient

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

        # Track tool call sequence on TX
        tx_calls = []
        original_tx_call = tx_client.call
        async def tracking_tx_call(tool_name, arguments, timeout=None):
            tx_calls.append(tool_name)
            return await original_tx_call(tool_name, arguments, timeout=timeout)
        tx_client.call = tracking_tx_call

        rx_calls = []
        original_rx_call = rx_client.call
        async def tracking_rx_call(tool_name, arguments, timeout=None):
            rx_calls.append(tool_name)
            return await original_rx_call(tool_name, arguments, timeout=timeout)
        rx_client.call = tracking_rx_call

        cfg = _sample_lora_cfg()
        await cvm_sprt_run(cfg, tx_client, rx_client,
                           session_id=42, cfg_idx=3, n_cap=20)

        # TX should have: set_config, board_query (ARM TX), board_start_burst
        self.assertIn("set_config", tx_calls)
        self.assertIn("board_start_burst", tx_calls)
        # ARM TX is sent via board_query
        self.assertIn("board_query", tx_calls)

        # RX should have: set_config, board_capture
        self.assertIn("set_config", rx_calls)
        self.assertIn("board_capture", rx_calls)


# ===========================================================================
# Test: push_config_to_boards helper (if extracted)
# ===========================================================================

class TestPushConfigHelper(unittest.IsolatedAsyncioTestCase):
    """Test the push_config_to_boards helper function if it exists."""

    async def test_push_config_helper_exists(self):
        """cvm_campaign should expose a push_config_to_boards helper."""
        import cvm_campaign
        self.assertTrue(hasattr(cvm_campaign, 'push_config_to_boards'),
                        "cvm_campaign should have push_config_to_boards helper")

    async def test_push_config_calls_set_config_on_both(self):
        """push_config_to_boards should call set_config on both TX and RX."""
        from cvm_campaign import push_config_to_boards

        class FakeClient:
            def __init__(self, response):
                self._response = response
                self.calls = []
            async def call(self, tool_name, arguments, timeout=None):
                self.calls.append((tool_name, arguments))
                return self._response

        tx_client = FakeClient({"ok": True, "responses": [{"label": "test", "commands": [], "replies": []}]})
        rx_client = FakeClient({"ok": True, "responses": [{"label": "test", "commands": [], "replies": []}]})

        cfg = _sample_lora_cfg()
        result = await push_config_to_boards(cfg, tx_client, rx_client)
        self.assertTrue(result, "push_config_to_boards should return True on success")

        # Verify set_config was called on both
        tx_tools = [c[0] for c in tx_client.calls]
        rx_tools = [c[0] for c in rx_client.calls]
        self.assertIn("set_config", tx_tools)
        self.assertIn("set_config", rx_tools)


# ===========================================================================
# Helpers
# ===========================================================================

async def _async_return(value):
    """Return a coroutine that resolves to value."""
    return value


if __name__ == "__main__":
    unittest.main(verbosity=2)