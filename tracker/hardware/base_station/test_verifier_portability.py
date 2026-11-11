"""Run the actual capture checks from an isolated checkout, including one-fault controls."""
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

HERE = Path(__file__).resolve().parent


class CaptureChecks(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        root = Path(self.temp.name)
        self.board = root / "tracker/hardware/base_station"
        self.board.mkdir(parents=True)
        (root / "docs").mkdir()
        for name in ("spec.json", "base_station_v1.net", "test_spec_transcription.py",
                     "test_netlist_implements_spec.py"):
            shutil.copy2(HERE / name, self.board / name)
        shutil.copy2(HERE.parents[2] / "docs/BASE-STATION-PCBA-D14-FREEZE.md", root / "docs")

    def run_check(self, name):
        return subprocess.run([sys.executable, str(self.board / name)],
                              cwd=self.temp.name, text=True, capture_output=True)

    def mutate(self, change):
        path = self.board / "spec.json"
        spec = json.loads(path.read_text())
        change(spec)
        path.write_text(json.dumps(spec))

    def test_checks_are_checkout_relative(self):
        for name in ("test_spec_transcription.py", "test_netlist_implements_spec.py"):
            with self.subTest(name=name):
                result = self.run_check(name)
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_changed_lna_current_alone_is_rejected(self):
        self.mutate(lambda s: s["rails"]["plus5V_LNA_SW"].update(load="ZX60, 9 mA"))
        result = self.run_check("test_spec_transcription.py")
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("FAIL  LNA current matches frozen 95 mA", result.stdout)

    def test_missing_gate_alone_is_rejected(self):
        self.mutate(lambda s: s["gates_not_yet_passed"].pop())
        result = self.run_check("test_spec_transcription.py")
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("FAIL  4 gates carried", result.stdout)


if __name__ == "__main__":
    unittest.main()
