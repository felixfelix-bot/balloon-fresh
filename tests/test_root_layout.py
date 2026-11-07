#!/usr/bin/env python3
"""Root directory hygiene — MECHANICAL, not conventional.

WHY
---
The repository root had accumulated 23 loose files: 19 v10 debug/render probes, a
poisoned test board and a KiCad scratch project. Two of them
(`render_layers_distinct.py`) were invoked by path from `tracker/hardware/`, so the
clutter was load-bearing — moving it without fixing the callers breaks renders.

The operator asked for these to be organised into subdirectories, and the repo's own
convention (AGENTS.md: *"'always X' => mechanical gate (hook), never convention"*)
means the rule must be enforced by a test a hook can run, not by a comment.

THE RULE
--------
The repository ROOT may contain only files on an explicit allow-list. Anything else
at root fails. This is allow-listed rather than deny-listed on purpose: a deny-list
lets the next stray file through, which is exactly how 23 of them accumulated.

WHERE FILES GO
--------------
  *.py debug/render/probe one-offs   -> tracker/hardware/tmp_probes/
  board/project scratch              -> tracker/hardware/tmp_probes/
  (see tracker/hardware/tmp_probes/README.md for the hazard rules)

RUN
---
    python3 -m pytest tests/test_root_layout.py -q
"""
from __future__ import annotations

import os
import subprocess

import pytest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Files that legitimately live at the repository root. Everything else must be in a
# subdirectory. Adding to this list is the ONE way to add a root file — and the
# reason must be a repo-wide entry point, not "it was convenient".
ROOT_ALLOWLIST = {
    # VCS / tooling config
    ".gitignore", ".gitmodules", ".secret-patterns.txt",
    # repo-wide docs and licence
    "AGENTS.md", "README.md", "PROGRESS.md", "LICENSE",
    # build / test / project config
    "Makefile", "pyproject.toml", "pytest.ini", "uv.lock",
}


def tracked_root_files() -> set[str]:
    """Root-level files that WILL EXIST after this change commits.

    Uses `git ls-files --cached` (the index) and drops anything deleted in the
    index: during a move the index briefly lists both the old path and the new one,
    and the old path is a pending deletion, not a file. Reading the working tree
    instead would miss nothing here but would also see untracked scratch files,
    which is not the invariant — the invariant is about what is COMMITTED.
    """
    out = subprocess.run(["git", "ls-files", "--cached"],
                         cwd=REPO, capture_output=True, text=True, check=True).stdout
    result = set()
    for line in out.splitlines():
        if not line or "/" in line:
            continue
        # a path that no longer exists on disk is a pending deletion
        if os.path.exists(os.path.join(REPO, line)):
            result.add(line)
    return result


def test_root_has_no_unexpected_files():
    """The gate. Any root file not on the allow-list fails, and is NAMED."""
    unexpected = sorted(tracked_root_files() - ROOT_ALLOWLIST)
    assert not unexpected, (
        "Untracked-at-root files found — root may only contain the allow-listed "
        "entry points.\n"
        "Move them: probes/debug/render one-offs -> tracker/hardware/tmp_probes/; "
        "docs -> docs/.\n"
        "Offending files:\n  " + "\n  ".join(unexpected)
    )


def test_the_former_strays_are_filed_not_deleted():
    """The specific 19 probes moved by pr/root-file-tidy must still EXIST, filed.

    This is the anti-regression half: a tidy that deletes work is not a tidy. Every
    script that was at root is still in the repo, under tmp_probes/.
    """
    probes = os.path.join(REPO, "tracker", "hardware", "tmp_probes")
    moved = [
        "make_progress_map.py", "make_registry_view.py", "render_cross_side.py",
        "render_layer.py", "render_layers_distinct.py", "trackdbg.py", "u2pads.py",
        "census2.py", "clean_dead_tracks.py", "conncheck_repo.py", "layercheck.py",
        "dbg_uc9.py", "paddbg.py", "poison_uc9.py", "samechip.py", "trackdump.py",
        "ucmeasure.py", "ucnet.py", "zoom_defect.py",
    ]
    missing = [f for f in moved if not os.path.exists(os.path.join(probes, f))]
    assert not missing, f"filed probes missing from tmp_probes/: {missing}"
    # and the two scratch artefacts went with them
    for f in ("poison_uc9.kicad_pcb", "scratch.kicad_pro"):
        assert os.path.exists(os.path.join(probes, f)), f"{f} not filed"


def test_callers_of_moved_scripts_point_at_the_new_path():
    """A move that leaves a broken caller is worse than the clutter.

    `render_routing_status.py` and `render_hop_zoom.py` invoke
    `render_layers_distinct.py`; both resolved it as `../../`, i.e. repo root.
    """
    for caller in ("tracker/hardware/render_routing_status.py",
                   "tracker/hardware/render_hop_zoom.py"):
        path = os.path.join(REPO, caller)
        if not os.path.exists(path):
            pytest.skip(f"{caller} no longer exists")
        with open(path) as fh:
            body = fh.read()
        assert "tmp_probes" in body, (
            f"{caller} still references render_layers_distinct.py at the old path"
        )
        assert '"..", "..", "render_layers_distinct.py"' not in body, (
            f"{caller} still uses the pre-move ../../ relative path"
        )
