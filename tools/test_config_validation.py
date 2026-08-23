"""
Tests for config file validation — envelope-4cfg-max and general config structure.

TDD red-first: these tests are written BEFORE the config file exists.
The envelope-4cfg-max tests should fail until the config is created.
"""
import json
import pathlib

CONFIGS_DIR = pathlib.Path(__file__).resolve().parent.parent / "configs"


def _load_cfg(name):
    cfg_path = CONFIGS_DIR / name
    assert cfg_path.exists(), f"{name} not found in configs/"
    return json.loads(cfg_path.read_text())


# --- envelope-4cfg-max tests (RED until config created) ---

def test_envelope_4cfg_max_structure():
    """Validate envelope-4cfg-max.json has the correct 4-config structure."""
    cfg = _load_cfg("envelope-4cfg-max.json")

    assert cfg["name"] == "envelope-4cfg-max"
    assert len(cfg["configs"]) == 4

    # FLRC configs use max payload 511
    for c in cfg["configs"]:
        if c["mod"] == "flrc":
            assert c["plen"] == 511, f"FLRC config {c['label']} should use 511B max payload"

    # LoRa configs use max payload 255
    for c in cfg["configs"]:
        if c["mod"] == "lora":
            assert c["plen"] == 255, f"LoRa config {c['label']} should use 255B max payload"

    # All 10 packets
    for c in cfg["configs"]:
        assert c["n_pkts"] == 10, f"Config {c['label']} should have 10 packets"

    # All 868 MHz
    for c in cfg["configs"]:
        assert c["freq"] == 868000000, f"Config {c['label']} should be 868 MHz"

    # All pa=10
    for c in cfg["configs"]:
        assert c["pa"] == 10, f"Config {c['label']} should have pa=10"

    # Verify expected modulations present
    labels = [c["label"] for c in cfg["configs"]]
    assert any("FLRC-650" in l for l in labels), "Missing FLRC-650"
    assert any("FLRC-2600" in l for l in labels), "Missing FLRC-2600"
    assert any("SF7" in l for l in labels), "Missing LoRa SF7"
    assert any("SF12" in l for l in labels), "Missing LoRa SF12"


def test_envelope_4cfg_max_flrc_2600_kept():
    """FLRC-2600 must be present — it's the mission goal (high data rate at range)."""
    cfg = _load_cfg("envelope-4cfg-max.json")

    flrc_2600 = [c for c in cfg["configs"] if c.get("br") == 2600]
    assert len(flrc_2600) == 1, "Exactly one FLRC-2600 config expected"
    assert flrc_2600[0]["plen"] == 511, "FLRC-2600 should use max payload 511B"


def test_envelope_4cfg_max_modulation_order():
    """Configs should cover FLRC first (high data rate), then LoRa (range)."""
    cfg = _load_cfg("envelope-4cfg-max.json")
    mods = [c["mod"] for c in cfg["configs"]]
    # FLRC configs should come before LoRa
    first_lora = next(i for i, m in enumerate(mods) if m == "lora")
    last_flrc = max(i for i, m in enumerate(mods) if m == "flrc")
    assert last_flrc < first_lora, "FLRC configs should come before LoRa configs"


def test_envelope_4cfg_max_all_same_band():
    """All configs should be in the 868 MHz band."""
    cfg = _load_cfg("envelope-4cfg-max.json")
    assert cfg.get("band") == "868"
    for c in cfg["configs"]:
        assert c["freq"] == 868000000


def test_envelope_4cfg_max_no_2g4():
    """No 2.4 GHz configs in the 868 MHz envelope preset."""
    cfg = _load_cfg("envelope-4cfg-max.json")
    for c in cfg["configs"]:
        assert c["freq"] < 2400000000, f"Config {c['label']} should not be 2.4 GHz"


# --- general config validation tests ---

def test_all_configs_have_required_fields():
    """Every config in every JSON config file must have required fields."""
    required = {"label", "mod", "pa", "freq", "plen", "gap", "n_pkts"}
    for cfg_file in CONFIGS_DIR.glob("*.json"):
        cfg = json.loads(cfg_file.read_text())
        if "configs" not in cfg:
            continue
        for c in cfg["configs"]:
            missing = required - set(c.keys())
            assert not missing, f"{cfg_file.name}: config {c.get('label', '?')} missing fields: {missing}"


def test_envelope_3cfg_still_valid():
    """The existing envelope-3cfg.json should still pass basic validation."""
    cfg = _load_cfg("envelope-3cfg.json")
    assert cfg["name"] == "envelope-3cfg"
    assert len(cfg["configs"]) == 3
    for c in cfg["configs"]:
        assert c["n_pkts"] == 10
        assert c["freq"] == 868000000