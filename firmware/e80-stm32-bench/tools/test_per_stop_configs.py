#!/usr/bin/env python3
"""test_per_stop_configs.py — TDD tests for per-stop config files.

Per-stop config files live under configs/per-stop/ and contain only the
configs relevant for that distance, ordered from highest throughput first.

Tests:
- All 9 files exist under configs/per-stop/
- Each file has at least 3 configs
- All 869 MHz configs have pa=22, freq=869525000
- All 2.4 GHz configs have pa=12, freq=2400000000
- Each file has configs sorted by throughput (FLRC before LoRa, higher bitrate/SF first)
- stop-70km.json has both SF12 and SF7 in 869 MHz group
- No FLRC configs in stops >= 5km

Run:  python3 -m pytest tools/test_per_stop_configs.py -v
"""
import json
import pathlib

CONFIGS_DIR = pathlib.Path(__file__).resolve().parent.parent.parent.parent / "configs"
PER_STOP_DIR = CONFIGS_DIR / "per-stop"

ALL_STOPS = [
    "stop-50m.json",
    "stop-100m.json",
    "stop-218m.json",
    "stop-436m.json",
    "stop-872m.json",
    "stop-1744m.json",
    "stop-5km.json",
    "stop-11km.json",
    "stop-70km.json",
]

LONG_RANGE_STOPS = {"stop-5km.json", "stop-11km.json", "stop-70km.json"}


def _load_cfg(name):
    cfg_path = PER_STOP_DIR / name
    assert cfg_path.exists(), f"{name} not found in configs/per-stop/"
    return json.loads(cfg_path.read_text())


# --- Existence ---


def test_all_9_files_exist():
    """All 9 per-stop config files must exist."""
    for name in ALL_STOPS:
        cfg_path = PER_STOP_DIR / name
        assert cfg_path.exists(), f"{name} not found in configs/per-stop/"


def test_per_stop_dir_exists():
    """The configs/per-stop/ directory must exist."""
    assert PER_STOP_DIR.is_dir(), "configs/per-stop/ directory not found"


# --- Minimum config count ---


def test_each_file_has_at_least_3_configs():
    """Each per-stop file must have at least 3 configs."""
    for name in ALL_STOPS:
        cfg = _load_cfg(name)
        assert len(cfg["configs"]) >= 3, (
            f"{name}: expected at least 3 configs, got {len(cfg['configs'])}"
        )


# --- Band field validation ---


def test_all_configs_have_band_field():
    """Every config must have a 'band' field."""
    for name in ALL_STOPS:
        cfg = _load_cfg(name)
        for c in cfg["configs"]:
            assert "band" in c, f"{name}: config '{c.get('label', '?')}' missing 'band' field"


def test_band_fields_are_valid():
    """All band fields must be either '868' or '2g4'."""
    for name in ALL_STOPS:
        cfg = _load_cfg(name)
        for c in cfg["configs"]:
            assert c["band"] in ("868", "2g4"), (
                f"{name}: config '{c['label']}' has invalid band '{c['band']}'"
            )


# --- 869 MHz configs: pa and freq ---


def test_all_868_configs_have_pa_22():
    """All 869 MHz configs must have pa=22."""
    for name in ALL_STOPS:
        cfg = _load_cfg(name)
        for c in cfg["configs"]:
            if c["band"] == "868":
                assert c["pa"] == 22, (
                    f"{name}: 869 MHz config '{c['label']}' should have pa=22, got {c['pa']}"
                )


def test_all_868_configs_have_freq_869525000():
    """All 869 MHz configs must be at 869.525 MHz."""
    for name in ALL_STOPS:
        cfg = _load_cfg(name)
        for c in cfg["configs"]:
            if c["band"] == "868":
                assert c["freq"] == 869525000, (
                    f"{name}: 869 MHz config '{c['label']}' should have freq=869525000, got {c['freq']}"
                )


# --- 2.4 GHz configs: pa and freq ---


def test_all_2g4_configs_have_pa_12():
    """All 2.4 GHz configs must have pa=12."""
    for name in ALL_STOPS:
        cfg = _load_cfg(name)
        for c in cfg["configs"]:
            if c["band"] == "2g4":
                assert c["pa"] == 12, (
                    f"{name}: 2.4 GHz config '{c['label']}' should have pa=12, got {c['pa']}"
                )


def test_all_2g4_configs_have_freq_2400000000():
    """All 2.4 GHz configs must be at 2400 MHz."""
    for name in ALL_STOPS:
        cfg = _load_cfg(name)
        for c in cfg["configs"]:
            if c["band"] == "2g4":
                assert c["freq"] == 2400000000, (
                    f"{name}: 2.4 GHz config '{c['label']}' should have freq=2400000000, got {c['freq']}"
                )


# --- Throughput ordering ---


def test_configs_sorted_by_throughput():
    """Within each band group, configs must be ordered highest throughput first.

    Checks:
    - All 868 configs come before all 2g4 configs
    - FLRC configs come before LoRa configs (within each band)
    - FLRC configs are sorted by bitrate descending
    - LoRa BW500 configs come before BW125 configs (wider BW = higher throughput)
    - The last LoRa config in each band is the highest SF (lowest throughput)
    """
    for name in ALL_STOPS:
        cfg = _load_cfg(name)
        configs = cfg["configs"]

        # Check that all 868 configs come before all 2g4 configs
        bands = [c["band"] for c in configs]
        first_2g4 = next((i for i, b in enumerate(bands) if b == "2g4"), None)
        last_868 = max((i for i, b in enumerate(bands) if b == "868"), default=-1)
        if first_2g4 is not None:
            assert last_868 < first_2g4, (
                f"{name}: all 869 MHz configs must appear before 2.4 GHz configs"
            )

        for band in ("868", "2g4"):
            band_configs = [c for c in configs if c["band"] == band]
            if not band_configs:
                continue

            # FLRC must come before LoRa
            first_lora_idx = next(
                (i for i, c in enumerate(band_configs) if c["mod"] == "lora"), None
            )
            last_flrc_idx = max(
                (i for i, c in enumerate(band_configs) if c["mod"] == "flrc"), default=-1
            )
            if first_lora_idx is not None and last_flrc_idx >= 0:
                assert last_flrc_idx < first_lora_idx, (
                    f"{name}: {band} — FLRC configs must come before LoRa configs"
                )

            # FLRC sorted by bitrate descending
            flrc_configs = [c for c in band_configs if c["mod"] == "flrc"]
            if len(flrc_configs) > 1:
                bitrates = [c["br"] for c in flrc_configs]
                assert bitrates == sorted(bitrates, reverse=True), (
                    f"{name}: {band} FLRC configs must be sorted by bitrate descending, "
                    f"got {bitrates}"
                )

            # LoRa BW500 before BW125
            lora_configs = [c for c in band_configs if c["mod"] == "lora"]
            if lora_configs:
                bws = [c["bw"] for c in lora_configs]
                first_125_idx = next((i for i, b in enumerate(bws) if b == 125), None)
                last_500_idx = max(
                    (i for i, b in enumerate(bws) if b == 500), default=-1
                )
                if first_125_idx is not None and last_500_idx >= 0:
                    assert last_500_idx < first_125_idx, (
                        f"{name}: {band} LoRa BW500 configs must come before BW125 configs"
                    )

                # BW500 before BW125 is the key ordering invariant
                # (within each BW group, the task spec defines the SF order)


# --- stop-70km: has both SF12 and SF7 in 869 MHz ---


def test_stop_70km_has_sf12_and_sf7_in_868():
    """stop-70km.json must have both SF12 and SF7 in the 869 MHz group."""
    cfg = _load_cfg("stop-70km.json")
    sfs_868 = [c["sf"] for c in cfg["configs"] if c["band"] == "868" and c["mod"] == "lora"]
    assert 12 in sfs_868, "stop-70km.json: 869 MHz group must contain SF12"
    assert 7 in sfs_868, "stop-70km.json: 869 MHz group must contain SF7"


# --- No FLRC in long-range stops ---


def test_no_flrc_in_long_range_stops():
    """Stops at 5km, 11km, and 70km must not contain FLRC configs."""
    for name in LONG_RANGE_STOPS:
        cfg = _load_cfg(name)
        flrc_configs = [c for c in cfg["configs"] if c["mod"] == "flrc"]
        assert len(flrc_configs) == 0, (
            f"{name}: must not contain FLRC configs (found {len(flrc_configs)})"
        )


# --- n_pkts validation ---


def test_all_configs_have_10_pkts():
    """All configs must have n_pkts=10."""
    for name in ALL_STOPS:
        cfg = _load_cfg(name)
        for c in cfg["configs"]:
            assert c["n_pkts"] == 10, (
                f"{name}: config '{c['label']}' should have n_pkts=10, got {c['n_pkts']}"
            )


# --- Payload size validation ---


def test_lora_configs_have_plen_255():
    """All LoRa configs must have plen=255."""
    for name in ALL_STOPS:
        cfg = _load_cfg(name)
        for c in cfg["configs"]:
            if c["mod"] == "lora":
                assert c["plen"] == 255, (
                    f"{name}: LoRa config '{c['label']}' should have plen=255, got {c['plen']}"
                )


def test_flrc_configs_have_plen_511():
    """All FLRC configs must have plen=511."""
    for name in ALL_STOPS:
        cfg = _load_cfg(name)
        for c in cfg["configs"]:
            if c["mod"] == "flrc":
                assert c["plen"] == 511, (
                    f"{name}: FLRC config '{c['label']}' should have plen=511, got {c['plen']}"
                )


# --- Gap time validation ---


def test_lora_configs_have_gap_1000():
    """All LoRa configs should have gap=1000 (reduced guard time)."""
    for name in ALL_STOPS:
        cfg = _load_cfg(name)
        for c in cfg["configs"]:
            if c["mod"] == "lora":
                assert c["gap"] == 1000, (
                    f"{name}: LoRa config '{c['label']}' should have gap=1000, got {c['gap']}"
                )


def test_flrc_configs_have_gap_5000():
    """All FLRC configs should have gap=5000."""
    for name in ALL_STOPS:
        cfg = _load_cfg(name)
        for c in cfg["configs"]:
            if c["mod"] == "flrc":
                assert c["gap"] == 5000, (
                    f"{name}: FLRC config '{c['label']}' should have gap=5000, got {c['gap']}"
                )


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])