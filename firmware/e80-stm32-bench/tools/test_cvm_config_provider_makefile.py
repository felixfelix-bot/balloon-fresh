#!/usr/bin/env python3
"""test_cvm_config_provider_makefile.py — TDD tests for the CVM Makefile targets.

Task 9 of the guard-time/config/CVM plan: update the Makefile CVM targets
(lines ~303-365) for the set_config dynamic config flow:

1. `range-cvm-server` must accept `CONFIGS` (config file to load initially),
   and pass it to the board server so the board starts in a known config.
2. `range-adaptive` must pass the config JSON to the coordinator (not just a
   preset name), so the coordinator does not need the config file locally
   (it may run on a third machine).
3. Document the CVM config provider pattern in the Makefile comments.

RED phase: these tests are written BEFORE the Makefile / CLI changes. They
should FAIL against the current Makefile + board server + coordinator.

Run:  python3 -m pytest test_cvm_config_provider_makefile.py -v
Or:   python3 test_cvm_config_provider_makefile.py
"""

from __future__ import annotations

import inspect
import json
import os
import pathlib
import re
import sys
import unittest

_TOOLS_DIR = os.path.dirname(os.path.abspath(__file__))
if _TOOLS_DIR not in sys.path:
    sys.path.insert(0, _TOOLS_DIR)

# Makefile is two levels up from tools/ (tools/ → e80-stm32-bench/)
MAKEFILE = pathlib.Path(__file__).resolve().parent.parent / "Makefile"


def _read_makefile() -> str:
    assert MAKEFILE.exists(), f"Makefile not found at {MAKEFILE}"
    return MAKEFILE.read_text()


# ===========================================================================
# Makefile — range-cvm-server passes CONFIGS to the board server
# ===========================================================================

class TestRangeCvmServerPassesConfigs(unittest.TestCase):
    """range-cvm-server target must accept CONFIGS and load it initially."""

    @classmethod
    def setUpClass(cls):
        cls.mk = _read_makefile()
        # Extract the range-cvm-server recipe block
        m = re.search(r'range-cvm-server:.*?(?=\n\S[^:]*:|$)', cls.mk,
                      re.DOTALL)
        assert m, "range-cvm-server target not found in Makefile"
        cls.recipe = m.group(0)

    def test_target_exists(self):
        self.assertIn("range-cvm-server:", self.mk)

    def test_recipe_passes_configs_to_board_server(self):
        """The cvm_board_server.py invocation must pass --configs from CONFIGS."""
        self.assertIn("--configs", self.recipe,
                      "range-cvm-server must pass --configs to cvm_board_server.py")
        self.assertIn("CONFIGS", self.recipe,
                      "range-cvm-server must reference the CONFIGS variable")

    def test_documents_config_provider(self):
        """Makefile should document the CVM config provider pattern."""
        self.assertIn("CONFIGS", self.mk,
                      "Makefile should document CONFIGS as the CVM config provider")

    def test_server_key_guard_retained(self):
        """The CVM_SERVER_HEX/CVM_SERVER_NSEC guard must still be present."""
        self.assertIn("CVM_SERVER_HEX", self.recipe)
        self.assertIn("CVM_SERVER_NSEC", self.recipe)


# ===========================================================================
# Makefile — range-adaptive passes config JSON to the coordinator
# ===========================================================================

class TestRangeAdaptivePassesConfigJson(unittest.TestCase):
    """range-adaptive must pass config JSON, not just a preset name."""

    @classmethod
    def setUpClass(cls):
        cls.mk = _read_makefile()
        m = re.search(r'range-adaptive:.*?(?=\n\S[^:]*:|$)', cls.mk,
                      re.DOTALL)
        assert m, "range-adaptive target not found in Makefile"
        cls.recipe = m.group(0)

    def test_uses_configs_json_flag(self):
        """The coordinator invocation must use --configs-json (inline JSON)."""
        self.assertIn("--configs-json", self.recipe,
                      "range-adaptive must pass --configs-json (config JSON) "
                      "to cvm_campaign.py, not a preset name")
        self.assertIn("CONFIGS", self.recipe,
                      "range-adaptive must read the config JSON from CONFIGS")

    def test_no_config_name_only(self):
        """The coordinator should not rely solely on --configs name/path."""
        # It may still pass --configs as a fallback, but must pass JSON too.
        self.assertIn("--configs-json", self.recipe)


# ===========================================================================
# Board server — accepts --configs
# ===========================================================================

class TestBoardServerAcceptsConfigs(unittest.TestCase):
    """cvm_board_server.py must accept a --configs arg (initial config)."""

    def test_source_has_configs_arg(self):
        import cvm_board_server
        src = inspect.getsource(cvm_board_server)
        self.assertIn("--configs", src,
                      "cvm_board_server must accept --configs for initial config")
        self.assertIn("config", src.lower(),
                      "cvm_board_server must reference config loading")

    def test_source_has_configs_env(self):
        import cvm_board_server
        src = inspect.getsource(cvm_board_server)
        self.assertIn("CVM_CONFIGS", src.upper(),
                      "cvm_board_server should read configs from CVM_CONFIGS env")


# ===========================================================================
# Coordinator — accepts config JSON
# ===========================================================================

class TestCoordinatorAcceptsConfigJson(unittest.TestCase):
    """cvm_campaign.py must accept an inline config JSON argument."""

    def test_source_has_configs_json_arg(self):
        import cvm_campaign
        src = inspect.getsource(cvm_campaign)
        self.assertIn("--configs-json", src,
                      "cvm_campaign must accept --configs-json (inline JSON)")

    def test_source_loads_configs_json(self):
        """The coordinator should parse --configs-json and load it."""
        import cvm_campaign
        src = inspect.getsource(cvm_campaign)
        # Should deserialize JSON and feed it to load_config_preset
        self.assertIn("json.loads", src,
                      "cvm_campaign must json.loads the --configs-json value")
        self.assertIn("load_config_preset", src,
                      "cvm_campaign must load the config via load_config_preset")


# ===========================================================================
# Sanity — the referenced config still validates
# ===========================================================================

class TestConfigProviderSanity(unittest.TestCase):
    """The default CONFIGS preset used by CVM must still be loadable."""

    def test_default_preset_loads(self):
        from e80_bench_ctl import load_config_preset
        cfgs = load_config_preset("envelope-4cfg-max")
        self.assertEqual(len(cfgs), 4)
        self.assertEqual(cfgs[0]["mod"], "flrc")
        self.assertEqual(cfgs[-1]["mod"], "lora")


if __name__ == "__main__":
    unittest.main(verbosity=2)
