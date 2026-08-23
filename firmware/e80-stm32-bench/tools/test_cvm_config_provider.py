#!/usr/bin/env python3
"""test_cvm_config_provider.py — TDD tests for the set_config MCP tool.

Tests the BoardTools.set_config tool which accepts either a config file name
(looked up in configs/<name>.json) or inline config JSON, sends MOD/FREQ/PA/ROLE
commands to the board via serial, and returns the board's responses.

Two modes:
  1. config_name — server looks up configs/<name>.json locally
  2. config_json — coordinator sends the full config JSON inline

Run:  python3 -m pytest test_cvm_config_provider.py -v
Or:   python3 test_cvm_config_provider.py
"""

from __future__ import annotations

import json
import os
import sys
import unittest
from unittest.mock import MagicMock

# Add tools dir for imports
_TOOLS_DIR = os.path.dirname(os.path.abspath(__file__))
if _TOOLS_DIR not in sys.path:
    sys.path.insert(0, _TOOLS_DIR)

# Reuse the mock controller from the existing CVM test suite
from test_cvm_board_server import MockBoardController


# ===========================================================================
# set_config tool — existence and dispatch
# ===========================================================================

class TestSetConfigToolExists(unittest.IsolatedAsyncioTestCase):
    """RED phase: verify set_config tool exists and is dispatchable."""

    async def asyncSetUp(self):
        from cvm_board_server import BoardTools
        self.BoardTools = BoardTools

    async def test_set_config_method_exists(self):
        """BoardTools should have a tool_set_config method."""
        ctrl = MockBoardController(role="TX")
        tools = self.BoardTools(ctrl, role="TX")
        self.assertTrue(hasattr(tools, "tool_set_config"),
                        "BoardTools must have tool_set_config method")

    async def test_set_config_dispatchable(self):
        """dispatch_tool('set_config', ...) should not raise ValueError."""
        ctrl = MockBoardController(role="TX")
        tools = self.BoardTools(ctrl, role="TX")
        # Provide minimal inline config to avoid missing-args error
        cfg = _sample_config()
        result = tools.dispatch_tool("set_config",
                                      {"config_json": json.dumps(cfg)})
        # Should return a dict (ok or error), not raise ValueError
        self.assertIsInstance(result, dict)

    async def test_set_config_in_source(self):
        """The cvm_board_server source should reference set_config."""
        import inspect
        import cvm_board_server
        source = inspect.getsource(cvm_board_server)
        self.assertIn("set_config", source,
                      "set_config tool not found in cvm_board_server source")


# ===========================================================================
# set_config — config_name mode (file lookup)
# ===========================================================================

class TestSetConfigByName(unittest.IsolatedAsyncioTestCase):
    """Test set_config with config_name (file lookup mode)."""

    async def asyncSetUp(self):
        from cvm_board_server import BoardTools
        self.BoardTools = BoardTools

    async def test_config_name_loads_file(self):
        """set_config with config_name='envelope-4cfg-max' should load the
        config file and send MOD/FREQ/PA/ROLE for each config entry."""
        ctrl = MockBoardController(role="TX")
        tools = self.BoardTools(ctrl, role="TX")
        result = tools.dispatch_tool("set_config",
                                      {"config_name": "envelope-4cfg-max"})
        self.assertTrue(result["ok"], f"set_config failed: {result.get('error', '')}")
        # Should have sent MOD commands for all 4 configs
        mod_writes = [w for w in ctrl.written if w.startswith("MOD")]
        self.assertGreater(len(mod_writes), 0, "No MOD commands sent to board")
        # Should have sent FREQ commands
        freq_writes = [w for w in ctrl.written if w.startswith("FREQ")]
        self.assertGreater(len(freq_writes), 0, "No FREQ commands sent to board")
        # Should have sent ROLE commands
        role_writes = [w for w in ctrl.written if w.startswith("ROLE")]
        self.assertGreater(len(role_writes), 0, "No ROLE commands sent to board")

    async def test_config_name_returns_responses(self):
        """set_config should return per-config responses."""
        ctrl = MockBoardController(role="TX")
        tools = self.BoardTools(ctrl, role="TX")
        result = tools.dispatch_tool("set_config",
                                      {"config_name": "envelope-4cfg-max"})
        self.assertTrue(result["ok"])
        # Response should contain a list of per-config results
        self.assertIn("responses", result)
        self.assertIsInstance(result["responses"], list)

    async def test_config_name_not_found_returns_error(self):
        """set_config with a nonexistent config_name should return ok=False."""
        ctrl = MockBoardController(role="TX")
        tools = self.BoardTools(ctrl, role="TX")
        result = tools.dispatch_tool("set_config",
                                      {"config_name": "nonexistent-config-xyz"})
        self.assertFalse(result["ok"])
        self.assertIn("error", result)


# ===========================================================================
# set_config — config_json mode (inline)
# ===========================================================================

class TestSetConfigByJson(unittest.IsolatedAsyncioTestCase):
    """Test set_config with config_json (inline JSON mode)."""

    async def asyncSetUp(self):
        from cvm_board_server import BoardTools
        self.BoardTools = BoardTools

    async def test_config_json_sends_mod_freq_pa_role(self):
        """set_config with inline JSON should send MOD/FREQ/PA/ROLE commands."""
        ctrl = MockBoardController(role="TX")
        tools = self.BoardTools(ctrl, role="TX")
        cfg = _sample_config()
        result = tools.dispatch_tool("set_config",
                                      {"config_json": json.dumps(cfg)})
        self.assertTrue(result["ok"], f"set_config failed: {result.get('error', '')}")
        # Verify MOD was sent
        mod_writes = [w for w in ctrl.written if w.startswith("MOD")]
        self.assertGreater(len(mod_writes), 0, "No MOD commands sent")
        # Verify FREQ was sent
        freq_writes = [w for w in ctrl.written if w.startswith("FREQ")]
        self.assertGreater(len(freq_writes), 0, "No FREQ commands sent")
        # Verify ROLE was sent
        role_writes = [w for w in ctrl.written if w.startswith("ROLE")]
        self.assertGreater(len(role_writes), 0, "No ROLE commands sent")

    async def test_config_json_lora_sends_mod_lora(self):
        """LoRa config should produce 'MOD LORA <sf> <bw>' command."""
        ctrl = MockBoardController(role="TX")
        tools = self.BoardTools(ctrl, role="TX")
        cfg = {
            "name": "test-lora",
            "configs": [
                {"label": "LoRa-SF7", "mod": "lora", "sf": 7, "bw": 125,
                 "br": None, "pa": 10, "freq": 868000000,
                 "plen": 255, "gap": 10000, "n_pkts": 10}
            ]
        }
        result = tools.dispatch_tool("set_config",
                                      {"config_json": json.dumps(cfg)})
        self.assertTrue(result["ok"])
        mod_writes = [w for w in ctrl.written if w.startswith("MOD")]
        self.assertTrue(any("LORA" in w.upper() for w in mod_writes),
                        f"Expected MOD LORA command, got: {mod_writes}")

    async def test_config_json_flrc_sends_mod_flrc(self):
        """FLRC config should produce 'MOD FLRC <br> <pa>' command."""
        ctrl = MockBoardController(role="TX")
        tools = self.BoardTools(ctrl, role="TX")
        cfg = {
            "name": "test-flrc",
            "configs": [
                {"label": "FLRC-650", "mod": "flrc", "sf": None, "bw": None,
                 "br": 650, "pa": 10, "freq": 868000000,
                 "plen": 511, "gap": 5000, "n_pkts": 10}
            ]
        }
        result = tools.dispatch_tool("set_config",
                                      {"config_json": json.dumps(cfg)})
        self.assertTrue(result["ok"])
        mod_writes = [w for w in ctrl.written if w.startswith("MOD")]
        self.assertTrue(any("FLRC" in w.upper() for w in mod_writes),
                        f"Expected MOD FLRC command, got: {mod_writes}")

    async def test_config_json_invalid_returns_error(self):
        """Invalid JSON should return ok=False with an error message."""
        ctrl = MockBoardController(role="TX")
        tools = self.BoardTools(ctrl, role="TX")
        result = tools.dispatch_tool("set_config",
                                      {"config_json": "not valid json"})
        self.assertFalse(result["ok"])
        self.assertIn("error", result)

    async def test_config_json_missing_configs_key_returns_error(self):
        """JSON without 'configs' key should return ok=False."""
        ctrl = MockBoardController(role="TX")
        tools = self.BoardTools(ctrl, role="TX")
        result = tools.dispatch_tool("set_config",
                                      {"config_json": json.dumps({"name": "bad"})})
        self.assertFalse(result["ok"])
        self.assertIn("error", result)


# ===========================================================================
# set_config — argument validation
# ===========================================================================

class TestSetConfigValidation(unittest.IsolatedAsyncioTestCase):
    """Test argument validation for set_config."""

    async def asyncSetUp(self):
        from cvm_board_server import BoardTools
        self.BoardTools = BoardTools

    async def test_no_args_returns_error(self):
        """set_config with no config_name or config_json should error."""
        ctrl = MockBoardController(role="TX")
        tools = self.BoardTools(ctrl, role="TX")
        result = tools.dispatch_tool("set_config", {})
        self.assertFalse(result["ok"])
        self.assertIn("error", result)

    async def test_both_args_returns_error(self):
        """Providing both config_name and config_json should error."""
        ctrl = MockBoardController(role="TX")
        tools = self.BoardTools(ctrl, role="TX")
        cfg = _sample_config()
        result = tools.dispatch_tool("set_config",
                                      {"config_name": "envelope-4cfg-max",
                                       "config_json": json.dumps(cfg)})
        self.assertFalse(result["ok"])
        self.assertIn("error", result)


# ===========================================================================
# set_config — responses structure
# ===========================================================================

class TestSetConfigResponses(unittest.IsolatedAsyncioTestCase):
    """Test the structure of set_config responses."""

    async def asyncSetUp(self):
        from cvm_board_server import BoardTools
        self.BoardTools = BoardTools

    async def test_responses_per_config(self):
        """Each config entry should produce a response with label, commands, replies."""
        ctrl = MockBoardController(role="TX")
        tools = self.BoardTools(ctrl, role="TX")
        cfg = _sample_config()
        result = tools.dispatch_tool("set_config",
                                      {"config_json": json.dumps(cfg)})
        self.assertTrue(result["ok"])
        responses = result["responses"]
        self.assertEqual(len(responses), len(cfg["configs"]),
                         "Should have one response per config entry")
        for resp in responses:
            self.assertIn("label", resp)
            self.assertIn("commands", resp)
            self.assertIn("replies", resp)

    async def test_responses_include_mod_command(self):
        """Each response should include the MOD command in its commands list."""
        ctrl = MockBoardController(role="TX")
        tools = self.BoardTools(ctrl, role="TX")
        cfg = _sample_config()
        result = tools.dispatch_tool("set_config",
                                      {"config_json": json.dumps(cfg)})
        self.assertTrue(result["ok"])
        for resp in result["responses"]:
            cmds = resp["commands"]
            self.assertTrue(any(c.startswith("MOD") for c in cmds),
                             f"Response for {resp['label']} missing MOD command: {cmds}")


# ===========================================================================
# Helpers
# ===========================================================================

def _sample_config() -> dict:
    """Return a minimal 2-config preset for testing."""
    return {
        "name": "test-sample",
        "description": "2-config test preset",
        "configs": [
            {"label": "FLRC-650 LEN511", "mod": "flrc", "sf": None, "bw": None,
             "br": 650, "pa": 10, "freq": 868000000,
             "plen": 511, "gap": 5000, "n_pkts": 10},
            {"label": "LoRa-SF7 BW125 LEN255", "mod": "lora", "sf": 7, "bw": 125,
             "br": None, "pa": 10, "freq": 868000000,
             "plen": 255, "gap": 10000, "n_pkts": 10},
        ]
    }


if __name__ == "__main__":
    unittest.main(verbosity=2)