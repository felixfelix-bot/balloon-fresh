"""
TDD tests for envelope-4cfg-max-plus.json — expanded throughput sweep configs.

Tests written RED-first (before config file exists). Validates:
- envelope-4cfg-max-plus.json exists and has 6 configs
- SF9 config has correct params (SF9, BW125, CR implied 4/5, 10 pkts, 868MHz, PA=10)
- SF7-500kHz config has BW=500000 (stored as 500 in kHz in config JSON)
- All configs have PA=10, 868MHz, 10 pkts, 255/511B payload
- Existing 4 configs from envelope-4cfg-max are preserved
"""
import json
import pathlib

CONFIGS_DIR = pathlib.Path(__file__).resolve().parent.parent.parent.parent / "configs"


def _load_cfg(name):
    cfg_path = CONFIGS_DIR / name
    assert cfg_path.exists(), f"{name} not found in configs/"
    return json.loads(cfg_path.read_text())


def test_envelope_4cfg_max_plus_exists():
    """envelope-4cfg-max-plus.json must exist."""
    cfg_path = CONFIGS_DIR / "envelope-4cfg-max-plus.json"
    assert cfg_path.exists(), "envelope-4cfg-max-plus.json not found in configs/"


def test_envelope_4cfg_max_plus_has_6_configs():
    """The plus preset must have 6 configs (4 original + 2 new)."""
    cfg = _load_cfg("envelope-4cfg-max-plus.json")
    assert len(cfg["configs"]) == 6, (
        f"Expected 6 configs, got {len(cfg['configs'])}"
    )


def test_envelope_4cfg_max_plus_preserves_original_4():
    """The first 4 configs must match the original envelope-4cfg-max configs."""
    orig = _load_cfg("envelope-4cfg-max.json")
    plus = _load_cfg("envelope-4cfg-max-plus.json")

    for i in range(4):
        orig_c = orig["configs"][i]
        plus_c = plus["configs"][i]
        assert orig_c["label"] == plus_c["label"], (
            f"Config {i}: label mismatch {orig_c['label']} vs {plus_c['label']}"
        )
        assert orig_c["mod"] == plus_c["mod"]
        assert orig_c["sf"] == plus_c["sf"]
        assert orig_c["bw"] == plus_c["bw"]
        assert orig_c["br"] == plus_c["br"]
        assert orig_c["plen"] == plus_c["plen"]


def test_sf9_config_has_correct_params():
    """SF9 255B config: LoRa, SF9, BW 125kHz, PA=10, 868MHz, 10 pkts, 255B."""
    cfg = _load_cfg("envelope-4cfg-max-plus.json")

    sf9_configs = [c for c in cfg["configs"] if c.get("sf") == 9]
    assert len(sf9_configs) == 1, f"Expected 1 SF9 config, got {len(sf9_configs)}"
    sf9 = sf9_configs[0]

    assert sf9["mod"] == "lora", f"SF9 config mod should be 'lora', got '{sf9['mod']}'"
    assert sf9["sf"] == 9, f"SF9 config sf should be 9, got {sf9['sf']}"
    assert sf9["bw"] == 125, f"SF9 config bw should be 125, got {sf9['bw']}"
    assert sf9["pa"] == 10, f"SF9 config pa should be 10, got {sf9['pa']}"
    assert sf9["freq"] == 868000000, f"SF9 config freq should be 868MHz, got {sf9['freq']}"
    assert sf9["plen"] == 255, f"SF9 config plen should be 255, got {sf9['plen']}"
    assert sf9["n_pkts"] == 10, f"SF9 config n_pkts should be 10, got {sf9['n_pkts']}"
    assert sf9["br"] is None, f"SF9 config br should be None, got {sf9['br']}"


def test_sf7_500khz_config_has_bw_500():
    """SF7 BW500kHz config: LoRa, SF7, BW=500 (kHz in JSON), PA=10, 868MHz, 10 pkts, 255B."""
    cfg = _load_cfg("envelope-4cfg-max-plus.json")

    # Find the SF7 with BW=500 (distinct from the original SF7 BW=125)
    sf7_500_configs = [
        c for c in cfg["configs"]
        if c.get("sf") == 7 and c.get("bw") == 500
    ]
    assert len(sf7_500_configs) == 1, (
        f"Expected 1 SF7 BW500 config, got {len(sf7_500_configs)}"
    )
    sf7_500 = sf7_500_configs[0]

    assert sf7_500["mod"] == "lora"
    assert sf7_500["sf"] == 7
    assert sf7_500["bw"] == 500, f"SF7-500kHz config bw should be 500, got {sf7_500['bw']}"
    assert sf7_500["pa"] == 10
    assert sf7_500["freq"] == 868000000
    assert sf7_500["plen"] == 255
    assert sf7_500["n_pkts"] == 10
    assert sf7_500["br"] is None


def test_all_configs_have_pa_10():
    """All 6 configs must have PA=10."""
    cfg = _load_cfg("envelope-4cfg-max-plus.json")
    for c in cfg["configs"]:
        assert c["pa"] == 10, f"Config {c['label']} should have pa=10, got {c['pa']}"


def test_all_configs_have_868mhz():
    """All 6 configs must be at 868 MHz."""
    cfg = _load_cfg("envelope-4cfg-max-plus.json")
    for c in cfg["configs"]:
        assert c["freq"] == 868000000, (
            f"Config {c['label']} should be 868MHz, got {c['freq']}"
        )


def test_all_configs_have_10_pkts():
    """All 6 configs must have 10 packets."""
    cfg = _load_cfg("envelope-4cfg-max-plus.json")
    for c in cfg["configs"]:
        assert c["n_pkts"] == 10, (
            f"Config {c['label']} should have 10 pkts, got {c['n_pkts']}"
        )


def test_all_configs_have_valid_payload():
    """All configs must have payload 255 (LoRa) or 511 (FLRC)."""
    cfg = _load_cfg("envelope-4cfg-max-plus.json")
    for c in cfg["configs"]:
        if c["mod"] == "flrc":
            assert c["plen"] == 511, (
                f"FLRC config {c['label']} should have plen=511, got {c['plen']}"
            )
        elif c["mod"] == "lora":
            assert c["plen"] == 255, (
                f"LoRa config {c['label']} should have plen=255, got {c['plen']}"
            )


def test_envelope_4cfg_max_plus_has_correct_name():
    """The preset name should be 'envelope-4cfg-max-plus'."""
    cfg = _load_cfg("envelope-4cfg-max-plus.json")
    assert cfg["name"] == "envelope-4cfg-max-plus"


def test_envelope_4cfg_max_plus_has_band_868():
    """The preset band should be '868'."""
    cfg = _load_cfg("envelope-4cfg-max-plus.json")
    assert cfg["band"] == "868"


def test_envelope_4cfg_max_plus_has_two_sf7_configs():
    """There should be 2 SF7 configs: one BW125 (original) and one BW500 (new)."""
    cfg = _load_cfg("envelope-4cfg-max-plus.json")
    sf7_configs = [c for c in cfg["configs"] if c.get("sf") == 7]
    assert len(sf7_configs) == 2, (
        f"Expected 2 SF7 configs (BW125 + BW500), got {len(sf7_configs)}"
    )
    bws = sorted([c["bw"] for c in sf7_configs])
    assert bws == [125, 500], f"SF7 configs should have BW [125, 500], got {bws}"