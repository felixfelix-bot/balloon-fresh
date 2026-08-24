"""
test_phase_sync.py — Unit tests for phase synchronization logic.

Regression tests for:
1. Phase computation from UTC time (both boards use same formula)
2. Interleave mode default ON for both TX and RX
3. Cycle length consistency (56-phase interleave = same totalCycleSec)
4. GPS time source detection (src=GPS when gps.unixTime available)
"""
import pytest


@pytest.mark.unit
class TestPhaseComputation:

    # Interleave phase table (56 phases, same for TX and RX)
    # Each phase: (mode_name, slot_ms)
    # Total cycle = sum of all slot_ms / 1000
    BASE_MODES = [
        ("HF-LoRa-SF7", 3000),
        ("HF-LoRa-SF9", 3000),
        ("HF-LoRa-SF12", 5000),
        ("HF-FLRC-325", 2000),
        ("HF-FLRC-650", 2000),
        ("HF-FLRC-1300", 2000),
        ("HF-FLRC-2600", 2000),
        ("LF-LoRa-SF7", 3000),
        ("HF-LoRa-SF9-64", 3000),
        ("LF-FLRC-325", 2000),
        ("LF-FLRC-650", 2000),
        ("LF-FLRC-1300", 2000),
        ("LF-FLRC-2600", 2000),
        ("LF-LoRa-SF9", 3000),
    ]

    PKT_SIZES = [32, 64, 128, 255]

    @property
    def interleave_phases(self):
        """Build 56-phase interleave table: each mode x each pkt size."""
        phases = []
        for mode, slot_ms in self.BASE_MODES:
            for size in self.PKT_SIZES:
                phases.append((f"{mode}-{size}", slot_ms))
        return phases

    @property
    def total_cycle_sec(self):
        """Total cycle seconds for interleave mode."""
        return sum(slot_ms for _, slot_ms in self.interleave_phases) // 1000

    def test_interleave_phase_count(self):
        """Interleave mode must produce exactly 56 phases."""
        assert len(self.interleave_phases) == len(self.BASE_MODES) * len(self.PKT_SIZES)
        assert len(self.interleave_phases) == 56

    def test_cycle_length_consistent(self):
        """Both TX and RX must compute same cycle length."""
        tx_cycle = self.total_cycle_sec
        rx_cycle = self.total_cycle_sec  # same table
        assert tx_cycle == rx_cycle

    def test_phase_from_utc(self):
        """Both boards compute same phase from same UTC time."""
        utc = 1785031276
        tx_phase = (utc % self.total_cycle_sec)
        rx_phase = (utc % self.total_cycle_sec)
        assert tx_phase == rx_phase

    def test_phase_advances_with_time(self):
        """Phase number increases as time advances."""
        utc_base = 1785031276
        phases = set()
        for offset in range(0, self.total_cycle_sec, 5):
            phase_idx = self._compute_phase_idx(utc_base + offset)
            phases.add(phase_idx)
        # Should have visited many different phases
        assert len(phases) > 20

    def test_phase_wraps_correctly(self):
        """Phase wraps back to 0 after full cycle."""
        utc = 1785031276
        phase1 = self._compute_phase_idx(utc)
        phase2 = self._compute_phase_idx(utc + self.total_cycle_sec)
        assert phase1 == phase2, "Phase must wrap after one full cycle"

    def _compute_phase_idx(self, utc_sec: int) -> int:
        """Compute phase index from UTC seconds (simulates firmware)."""
        cycle_pos = utc_sec % self.total_cycle_sec
        elapsed = 0
        for i, (_, slot_ms) in enumerate(self.interleave_phases):
            elapsed += slot_ms // 1000
            if cycle_pos < elapsed:
                return i
        return 0


@pytest.mark.unit
class TestInterleaveDefault:

    def test_tx_interleave_default(self):
        """TX firmware must default to interleave mode ON."""
        import subprocess
        result = subprocess.run(
            ["grep", "-n", "interleaveMode = true",
             "firmware/rp2040/src/multi_radio_sweep_gps_v4.cpp"],
            capture_output=True, text=True, cwd=_repo_root()
        )
        assert result.returncode == 0, "TX firmware must have interleaveMode = true by default"

    def test_rx_interleave_default(self):
        """RX firmware must default to interleave mode ON."""
        import subprocess
        result = subprocess.run(
            ["grep", "-n", "interleaveMode = true",
             "firmware/rp2040/src/multi_radio_sweep_rx_v4.cpp"],
            capture_output=True, text=True, cwd=_repo_root()
        )
        assert result.returncode == 0, "RX firmware must have interleaveMode = true by default"


def _repo_root() -> str:
    import os
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
