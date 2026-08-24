#!/usr/bin/env python3
"""test_dualband_configs.py — TDD tests for envelope-dualband.json

Dual-band config: 7× 869 MHz (pa=22, freq=869525000) + 5× 2.4 GHz (pa=12, freq=2400000000).

Tests written RED-first (before config file exists). Validates:
- envelope-dualband.json exists
- Has 12 configs total (7 + 5)
- All 869 MHz configs have pa=22, freq=869525000
- All 2.4 GHz configs have pa=12, freq=2400000000
- Each config has a "band" field ("868" or "2g4")
- 2.4 GHz configs include SF12, SF9, SF7, FLRC-260, FLRC-2600
- 869 MHz configs match the 7 from envelope-4cfg-max-plus.json

Run:  python3 -m pytest tools/test_dualband_configs.py -v
"""
import json
import pathlib

CONFIGS_DIR = pathlib.Path(__file__).resolve().parent.parent.parent.parent / "configs"


def _load_cfg(name):
    cfg_path = CONFIGS_DIR / name
    assert cfg_path.exists(), f"{name} not found in configs/"
    return json.loads(cfg_path.read_text())


# --- Existence + count ---


def test_envelope_dualband_exists():
    """envelope-dualband.json must exist in configs/."""
    cfg_path = CONFIGS_DIR / "envelope-dualband.json"
    assert cfg_path.exists(), "envelope-dualband.json not found in configs/"


def test_envelope_dualband_has_12_configs():
    """Dual-band preset must have 12 configs (7 869 MHz + 5 2.4 GHz)."""
    cfg = _load_cfg("envelope-dualband.json")
    assert len(cfg["configs"]) == 12, (
        f"Expected 12 configs, got {len(cfg['configs'])}"
    )


def test_envelope_dualband_has_correct_name():
    """The preset name should be 'envelope-dualband'."""
    cfg = _load_cfg("envelope-dualband.json")
    assert cfg["name"] == "envelope-dualband"


# --- Band field ---


def test_all_configs_have_band_field():
    """Every config must have a 'band' field."""
    cfg = _load_cfg("envelope-dualband.json")
    for c in cfg["configs"]:
        assert "band" in c, f"Config '{c.get('label', '?')}' missing 'band' field"


def test_band_fields_are_valid():
    """All band fields must be either '868' or '2g4'."""
    cfg = _load_cfg("envelope-dualband.json")
    for c in cfg["configs"]:
        assert c["band"] in ("868", "2g4"), (
            f"Config '{c['label']}' has invalid band '{c['band']}', expected '868' or '2g4'"
        )


def test_has_7_868_configs():
    """There must be exactly 7 869 MHz configs (band='868')."""
    cfg = _load_cfg("envelope-dualband.json")
    count_868 = sum(1 for c in cfg["configs"] if c["band"] == "868")
    assert count_868 == 7, f"Expected 7 869 MHz configs, got {count_868}"


def test_has_5_2g4_configs():
    """There must be exactly 5 2.4 GHz configs (band='2g4')."""
    cfg = _load_cfg("envelope-dualband.json")
    count_2g4 = sum(1 for c in cfg["configs"] if c["band"] == "2g4")
    assert count_2g4 == 5, f"Expected 5 2.4 GHz configs, got {count_2g4}"


# --- 869 MHz configs: same 7 as envelope-4cfg-max-plus ---


def test_868_configs_match_envelope_4cfg_max_plus():
    """The 7 869 MHz configs must match envelope-4cfg-max-plus.json exactly."""
    dual = _load_cfg("envelope-dualband.json")
    plus = _load_cfg("envelope-4cfg-max-plus.json")

    dual_868 = [c for c in dual["configs"] if c["band"] == "868"]
    plus_configs = plus["configs"]

    assert len(dual_868) == len(plus_configs) == 7, (
        f"Expected 7 configs each, got {len(dual_868)} vs {len(plus_configs)}"
    )

    for i, (d, p) in enumerate(zip(dual_868, plus_configs)):
        assert d["label"] == p["label"], (
            f"Config {i}: label mismatch '{d['label']}' vs '{p['label']}'"
        )
        assert d["mod"] == p["mod"], f"Config {i}: mod mismatch"
        assert d["sf"] == p["sf"], f"Config {i}: sf mismatch"
        assert d["bw"] == p["bw"], f"Config {i}: bw mismatch"
        assert d["br"] == p["br"], f"Config {i}: br mismatch"
        assert d["pa"] == p["pa"], f"Config {i}: pa mismatch"
        assert d["freq"] == p["freq"], f"Config {i}: freq mismatch"
        assert d["plen"] == p["plen"], f"Config {i}: plen mismatch"


def test_all_868_configs_have_pa_22():
    """All 869 MHz configs must have PA=22 (max sub-GHz power, OUTDOOR mode)."""
    cfg = _load_cfg("envelope-dualband.json")
    for c in cfg["configs"]:
        if c["band"] == "868":
            assert c["pa"] == 22, (
                f"869 MHz config '{c['label']}' should have pa=22, got {c['pa']}"
            )


def test_all_868_configs_have_freq_869525000():
    """All 869 MHz configs must be at 869.525 MHz (EU high-power sub-band)."""
    cfg = _load_cfg("envelope-dualband.json")
    for c in cfg["configs"]:
        if c["band"] == "868":
            assert c["freq"] == 869525000, (
                f"869 MHz config '{c['label']}' should have freq=869525000, got {c['freq']}"
            )


# --- 2.4 GHz configs ---


def test_all_2g4_configs_have_pa_12():
    """All 2.4 GHz configs must have PA=12 (HF PA max, chip hardware limit)."""
    cfg = _load_cfg("envelope-dualband.json")
    for c in cfg["configs"]:
        if c["band"] == "2g4":
            assert c["pa"] == 12, (
                f"2.4 GHz config '{c['label']}' should have pa=12, got {c['pa']}"
            )


def test_all_2g4_configs_have_freq_2400000000():
    """All 2.4 GHz configs must be at 2400 MHz (below WiFi, clear spectrum)."""
    cfg = _load_cfg("envelope-dualband.json")
    for c in cfg["configs"]:
        if c["band"] == "2g4":
            assert c["freq"] == 2400000000, (
                f"2.4 GHz config '{c['label']}' should have freq=2400000000, got {c['freq']}"
            )


def test_2g4_configs_include_sf12():
    """2.4 GHz configs must include SF12 (max sensitivity, bracket the cliff)."""
    cfg = _load_cfg("envelope-dualband.json")
    sf12_2g4 = [
        c for c in cfg["configs"]
        if c["band"] == "2g4" and c.get("sf") == 12
    ]
    assert len(sf12_2g4) == 1, (
        f"Expected 1 2.4 GHz SF12 config, got {len(sf12_2g4)}"
    )


def test_2g4_configs_include_sf9():
    """2.4 GHz configs must include SF9 (mid-range sensitivity)."""
    cfg = _load_cfg("envelope-dualband.json")
    sf9_2g4 = [
        c for c in cfg["configs"]
        if c["band"] == "2g4" and c.get("sf") == 9
    ]
    assert len(sf9_2g4) == 1, (
        f"Expected 1 2.4 GHz SF9 config, got {len(sf9_2g4)}"
    )


def test_2g4_configs_include_sf7():
    """2.4 GHz configs must include SF7 (high throughput, marginal at 70 km)."""
    cfg = _load_cfg("envelope-dualband.json")
    sf7_2g4 = [
        c for c in cfg["configs"]
        if c["band"] == "2g4" and c.get("sf") == 7
    ]
    assert len(sf7_2g4) == 1, (
        f"Expected 1 2.4 GHz SF7 config, got {len(sf7_2g4)}"
    )


def test_2g4_configs_include_flrc_260():
    """2.4 GHz configs must include FLRC-260 (short range characterization)."""
    cfg = _load_cfg("envelope-dualband.json")
    flrc260_2g4 = [
        c for c in cfg["configs"]
        if c["band"] == "2g4" and c.get("mod") == "flrc" and c.get("br") == 260
    ]
    assert len(flrc260_2g4) == 1, (
        f"Expected 1 2.4 GHz FLRC-260 config, got {len(flrc260_2g4)}"
    )


def test_2g4_configs_include_flrc_2600():
    """2.4 GHz configs must include FLRC-2600 (high data rate, short range)."""
    cfg = _load_cfg("envelope-dualband.json")
    flrc2600_2g4 = [
        c for c in cfg["configs"]
        if c["band"] == "2g4" and c.get("mod") == "flrc" and c.get("br") == 2600
    ]
    assert len(flrc2600_2g4) == 1, (
        f"Expected 1 2.4 GHz FLRC-2600 config, got {len(flrc2600_2g4)}"
    )


# --- 2.4 GHz payload sizes ---


def test_2g4_lora_configs_have_plen_255():
    """All 2.4 GHz LoRa configs must have plen=255."""
    cfg = _load_cfg("envelope-dualband.json")
    for c in cfg["configs"]:
        if c["band"] == "2g4" and c["mod"] == "lora":
            assert c["plen"] == 255, (
                f"2.4 GHz LoRa config '{c['label']}' should have plen=255, got {c['plen']}"
            )


def test_2g4_flrc_configs_have_plen_511():
    """All 2.4 GHz FLRC configs must have plen=511."""
    cfg = _load_cfg("envelope-dualband.json")
    for c in cfg["configs"]:
        if c["band"] == "2g4" and c["mod"] == "flrc":
            assert c["plen"] == 511, (
                f"2.4 GHz FLRC config '{c['label']}' should have plen=511, got {c['plen']}"
            )


# --- All configs: n_pkts ---


def test_all_configs_have_10_pkts():
    """All 12 configs must have n_pkts=10."""
    cfg = _load_cfg("envelope-dualband.json")
    for c in cfg["configs"]:
        assert c["n_pkts"] == 10, (
            f"Config '{c['label']}' should have n_pkts=10, got {c['n_pkts']}"
        )


# --- Band ordering (869 first, then 2.4 GHz) ---


def test_868_configs_before_2g4_configs():
    """869 MHz configs must come before 2.4 GHz configs in the array."""
    cfg = _load_cfg("envelope-dualband.json")
    bands_in_order = [c["band"] for c in cfg["configs"]]
    first_2g4_idx = next(
        (i for i, b in enumerate(bands_in_order) if b == "2g4"), None
    )
    last_868_idx = max(
        (i for i, b in enumerate(bands_in_order) if b == "868"), default=-1
    )
    if first_2g4_idx is not None:
        assert last_868_idx < first_2g4_idx, (
            "All 869 MHz configs must appear before 2.4 GHz configs"
        )


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])