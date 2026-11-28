#!/usr/bin/env python3
"""Writer -> reader round trip demo for the frozen s<sid>-go<epoch> contract.

Builds a GO-mode run dir with the WRITER's own helpers (e80_bench_ctl
resolve_log_path / HarmonizedRxLogWriter, the same writers the real
--sync cvm launcher uses), then runs the range_check CLI over it and shows
the reader joins the directory back to the writer's session id.
"""
import os
import pathlib
import subprocess
import sys
import tempfile

E80 = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOOLS = os.path.join(E80, "firmware", "e80-stm32-bench", "tools")
sys.path.insert(0, TOOLS)

import e80_bench_ctl as ctl          # noqa: E402
import range_check                   # noqa: E402
import test_range_check as t         # noqa: E402

tmp = pathlib.Path(tempfile.mkdtemp(prefix="go-join-demo-"))
t.write_go_preset(tmp)                       # configs/per-stop/stop-50m.json
rx = t.go_rx_log(tmp)                        # GO rx-log, writer-shaped rows

print("go flag passed to the writer: go=True")
print("writer dir   :", os.path.relpath(rx, tmp))
print("writer session (ARMED-carried):", t.GO_SESSION)
print("reader session_from_filename  :",
      range_check.session_from_filename(rx))
print("reader is_go_layout           :", range_check.is_go_layout(rx))

r = subprocess.run(
    [sys.executable, os.path.join(TOOLS, "range_check.py"),
     "--dist", "50m", "--repo-root", str(tmp), "--session", t.GO_SESSION],
    capture_output=True, text=True, cwd=str(tmp))
print("--- range_check CLI (exit {}) ---".format(r.returncode))
print(r.stdout)
if r.stderr:
    print("stderr:", r.stderr)
assert range_check.session_from_filename(rx) == t.GO_SESSION
assert "s{}".format(t.GO_SESSION) in r.stdout, r.stdout
print("DEMO OK: writer's GO dir joined to session", t.GO_SESSION)

# --- legacy boundary/manual dir: same reader, legacy spelling, unchanged ---
tmp2 = pathlib.Path(tempfile.mkdtemp(prefix="legacy-join-demo-"))
t.write_preset(tmp2)
lg = t.legacy_stop_log(tmp2)                 # logs/s<sid>-t0<t0>/stop-50m/...
print()
print("legacy dir   :", os.path.relpath(lg, tmp2))
print("writer session (legacy int)   :", t.LEGACY_SESSION)
print("reader session_from_filename  :",
      range_check.session_from_filename(lg))
print("reader is_go_layout           :", range_check.is_go_layout(lg))
r2 = subprocess.run(
    [sys.executable, os.path.join(TOOLS, "range_check.py"),
     "--dist", "50m", "--repo-root", str(tmp2), "--session", t.LEGACY_SESSION],
    capture_output=True, text=True, cwd=str(tmp2))
print("--- range_check CLI (exit {}) ---".format(r2.returncode))
print(r2.stdout)
assert range_check.session_from_filename(lg) == t.LEGACY_SESSION
assert "s{}".format(t.LEGACY_SESSION) in r2.stdout, r2.stdout
print("DEMO OK: legacy dir still joined to session", t.LEGACY_SESSION)

