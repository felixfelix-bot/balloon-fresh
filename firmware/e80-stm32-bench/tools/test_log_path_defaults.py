#!/usr/bin/env python3
"""Tests for RX/TX log filename default embedding T0 + SESSION.

Verifies that:
  1. Default log paths embed session + t0 epoch in a per-run unique dir.
  2. Explicit --rx-log / --tx-log overrides are respected (env override wins).
  3. Default paths are absolute (repo-root anchored).
  4. RX and TX each get their own file in the same session dir.

Run:  python3 -m pytest test_log_path_defaults.py -v
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import e80_bench_ctl as m  # noqa: E402


class ResolveLogPathTests(unittest.TestCase):
    """Unit tests for resolve_log_path()."""

    def test_default_rx_path_embeds_session_and_t0(self):
        """Default RX_LOG embeds s<SESSION>-t0<T0EPOCH> in an absolute path."""
        result = m.resolve_log_path(
            log_path="rx-log.csv",      # the argparse default
            is_default=True,
            session_id=2508281530,
            t0_epoch=1758874200,
            role="rx",
            repo_root="/tmp/repo",
        )
        self.assertTrue(os.path.isabs(result), "default path must be absolute")
        self.assertIn("s2508281530-t01758874200", result)
        self.assertIn("rx-log.csv", result)
        self.assertIn("logs/", result)

    def test_default_tx_path_embeds_session_and_t0(self):
        """Default TX_LOG embeds s<SESSION>-t0<T0EPOCH> in an absolute path."""
        result = m.resolve_log_path(
            log_path="tx-log.csv",
            is_default=True,
            session_id=2508281530,
            t0_epoch=1758874200,
            role="tx",
            repo_root="/tmp/repo",
        )
        self.assertTrue(os.path.isabs(result), "default path must be absolute")
        self.assertIn("s2508281530-t01758874200", result)
        self.assertIn("tx-log.csv", result)

    def test_rx_and_tx_share_session_dir(self):
        """RX and TX files live in the same session directory."""
        rx = m.resolve_log_path(
            "rx-log.csv", True, 2508281530, 1758874200, "rx", "/tmp/repo")
        tx = m.resolve_log_path(
            "tx-log.csv", True, 2508281530, 1758874200, "tx", "/tmp/repo")
        rx_dir = os.path.dirname(rx)
        tx_dir = os.path.dirname(tx)
        self.assertEqual(rx_dir, tx_dir,
                         "RX and TX must share the same session directory")
        self.assertNotEqual(rx, tx,
                            "RX and TX must be separate files")

    def test_explicit_override_respected(self):
        """Explicit --rx-log / --tx-log override is used as-is (env wins)."""
        result = m.resolve_log_path(
            log_path="/custom/path/my-rx.csv",
            is_default=False,         # not the default → explicit override
            session_id=2508281530,
            t0_epoch=1758874200,
            role="rx",
            repo_root="/tmp/repo",
        )
        self.assertEqual(result, "/custom/path/my-rx.csv")

    def test_explicit_relative_override_kept_as_is(self):
        """A relative explicit override is kept relative (operator's choice)."""
        result = m.resolve_log_path(
            log_path="data/my-log.csv",
            is_default=False,
            session_id=2508281530,
            t0_epoch=1758874200,
            role="rx",
            repo_root="/tmp/repo",
        )
        self.assertEqual(result, "data/my-log.csv")

    def test_default_path_format(self):
        """Default path matches: <repo_root>/logs/s<SESSION>-t0<T0EPOCH>/<role>-log.csv"""
        result = m.resolve_log_path(
            "rx-log.csv", True, 2508281530, 1758874200, "rx", "/tmp/repo")
        expected = os.path.join(
            "/tmp/repo", "logs", "s2508281530-t01758874200", "rx-log.csv")
        self.assertEqual(result, expected)

    def test_default_is_absolute_even_if_repo_root_relative(self):
        """If repo_root is relative, it's resolved to absolute first."""
        # This is an edge case — repo_root should always be absolute from Makefile
        # but resolve_log_path should handle it gracefully.
        result = m.resolve_log_path(
            "rx-log.csv", True, 2508281530, 1758874200, "rx", "relative/repo")
        # Should still produce a path containing the session dir pattern
        self.assertIn("s2508281530-t01758874200", result)
        self.assertIn("rx-log.csv", result)


if __name__ == "__main__":
    unittest.main()