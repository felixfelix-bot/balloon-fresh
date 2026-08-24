"""
TDD tests for envelope-4cfg-max-plus.json — expanded throughput sweep configs.

Tests written RED-first (before config file exists). Validates:
- envelope-4cfg-max-plus.json exists and has 7 configs
- First config is FLRC-260 (most robust FLRC, 260 kbps)
- FLRC-260 has correct params (br=260, plen=511, pa=10, 868MHz, 10 pkts)
- SF9 config has correct params (SF9, BW125, CR implied 4/5, 10 pkts, 868MHz, PA=10)
- SF7-500kHz config has BW=500 (stored as 500 in kHz in config JSON)
- All configs have PA=10, 868MHz, 10 pkts, 255/511B payload
- At least one FLRC config exists at every distance in the matrix
"""
import json
import pathlib
import re

CONFIGS_DIR = pathlib.Path(__file__).resolve().parent.parent.parent.parent / "configs"
GUIDE_PATH = pathlib.Path(__file__).resolve().parent.parent / "docs" / "RANGE-TEST-GUIDE.md"


def _load_cfg(name):
    cfg_path = CONFIGS_DIR / name
    assert cfg_path.exists(), f"{name} not found in configs/"
    return json.loads(cfg_path.read_text())


def test_envelope_4cfg_max_plus_exists():
    """envelope-4cfg-max-plus.json must exist."""
    cfg_path = CONFIGS_DIR / "envelope-4cfg-max-plus.json"
    assert cfg_path.exists(), "envelope-4cfg-max-plus.json not found in configs/"


def test_envelope_4cfg_max_plus_has_7_configs():
    """The plus preset must have 7 configs (6 existing + FLRC-260 added)."""
    cfg = _load_cfg("envelope-4cfg-max-plus.json")
    assert len(cfg["configs"]) == 7, (
        f"Expected 7 configs, got {len(cfg['configs'])}"
    )


def test_first_config_is_flrc_260():
    """First config must be FLRC-260 (most robust FLRC first)."""
    cfg = _load_cfg("envelope-4cfg-max-plus.json")
    first = cfg["configs"][0]
    assert first["label"] == "FLRC-260 LEN511", (
        f"First config should be FLRC-260 LEN511, got '{first['label']}'"
    )
    assert first["mod"] == "flrc", (
        f"First config mod should be 'flrc', got '{first['mod']}'"
    )
    assert first["br"] == 260, (
        f"First config br should be 260, got {first['br']}"
    )
    assert first["plen"] == 511, (
        f"First config plen should be 511, got {first['plen']}"
    )


def test_flrc_260_has_correct_params():
    """FLRC-260 config: br=260, pa=10, freq=868MHz, n_pkts=10, gap=5000."""
    cfg = _load_cfg("envelope-4cfg-max-plus.json")
    flrc260 = cfg["configs"][0]

    assert flrc260["br"] == 260, f"FLRC-260 br should be 260, got {flrc260['br']}"
    assert flrc260["pa"] == 10, f"FLRC-260 pa should be 10, got {flrc260['pa']}"
    assert flrc260["freq"] == 868000000, (
        f"FLRC-260 freq should be 868MHz, got {flrc260['freq']}"
    )
    assert flrc260["n_pkts"] == 10, (
        f"FLRC-260 n_pkts should be 10, got {flrc260['n_pkts']}"
    )
    assert flrc260["plen"] == 511, (
        f"FLRC-260 plen should be 511, got {flrc260['plen']}"
    )
    assert flrc260["gap"] == 5000, (
        f"FLRC-260 gap should be 5000, got {flrc260['gap']}"
    )
    assert flrc260["sf"] is None, (
        f"FLRC-260 sf should be None, got {flrc260['sf']}"
    )
    assert flrc260["bw"] is None, (
        f"FLRC-260 bw should be None, got {flrc260['bw']}"
    )


def test_envelope_4cfg_max_plus_preserves_original_4():
    """The original 4 configs from envelope-4cfg-max must still be present."""
    orig = _load_cfg("envelope-4cfg-max.json")
    plus = _load_cfg("envelope-4cfg-max-plus.json")

    # Original configs should be at indices 1-4 in the plus config (after FLRC-260)
    for i in range(4):
        orig_c = orig["configs"][i]
        plus_c = plus["configs"][i + 1]
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
    """All 7 configs must have PA=10."""
    cfg = _load_cfg("envelope-4cfg-max-plus.json")
    for c in cfg["configs"]:
        assert c["pa"] == 10, f"Config {c['label']} should have pa=10, got {c['pa']}"


def test_all_configs_have_868mhz():
    """All 7 configs must be at 868 MHz."""
    cfg = _load_cfg("envelope-4cfg-max-plus.json")
    for c in cfg["configs"]:
        assert c["freq"] == 868000000, (
            f"Config {c['label']} should be 868MHz, got {c['freq']}"
        )


def test_all_configs_have_10_pkts():
    """All 7 configs must have 10 packets."""
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


# --- Distance matrix tests ---


def test_distance_matrix_has_flrc_260_column():
    """The distance matrix in RANGE-TEST-GUIDE.md must include FLRC-260 511B column."""
    text = GUIDE_PATH.read_text()
    assert "FLRC-260 511B" in text, (
        "Distance matrix should have FLRC-260 511B column header"
    )


def test_distance_matrix_flrc_260_at_every_flrc_stop():
    """FLRC-260 should appear (✓) at every stop where any FLRC might work.

    Per the task spec, FLRC-260 should be ✓ at: Baseline, B2, Sanity, D1, D2, D3.
    It should be — at: D4, D5, D6.
    """
    text = GUIDE_PATH.read_text()

    # Extract the distance matrix table section
    # Find the table with FLRC-260 in it
    lines = text.splitlines()
    in_matrix = False
    matrix_lines = []
    for line in lines:
        if "| Stop | Dist |" in line and "FLRC-260" in line:
            in_matrix = True
            matrix_lines.append(line)
            continue
        if in_matrix:
            if line.startswith("|") and "---" not in line:
                matrix_lines.append(line)
            elif line.strip() == "":
                break
            elif line.startswith("|") and "---" in line:
                matrix_lines.append(line)
                continue

    assert len(matrix_lines) > 0, "Could not find distance matrix table with FLRC-260"

    # Parse the matrix to find FLRC-260 column index
    header = matrix_lines[0]
    cols = [c.strip() for c in header.split("|")]
    # Remove empty first/last from leading/trailing |
    cols = [c for c in cols if c]

    flrc260_idx = None
    for i, col in enumerate(cols):
        if "FLRC-260" in col:
            flrc260_idx = i
            break

    assert flrc260_idx is not None, "FLRC-260 column not found in matrix header"

    # Check each data row
    for row_line in matrix_lines:
        if "---" in row_line:
            continue
        row_cols = [c.strip() for c in row_line.split("|")]
        row_cols = [c for c in row_cols if c != ""]
        if len(row_cols) <= flrc260_idx:
            continue
        stop = row_cols[0]
        dist = row_cols[1]
        flrc260_val = row_cols[flrc260_idx]

        if dist in ("50m", "100m", "218m", "436m", "872m", "1744m"):
            assert flrc260_val == "✓", (
                f"FLRC-260 should be ✓ at {stop} ({dist}), got '{flrc260_val}'"
            )
        elif dist in ("5km", "11km", "70km"):
            assert flrc260_val == "—", (
                f"FLRC-260 should be — at {stop} ({dist}), got '{flrc260_val}'"
            )


def test_at_least_one_flrc_config_at_every_distance():
    """At least one FLRC config (260 or 650 or 2600) should be ✓ at every stop
    where FLRC might work (Baseline through D3)."""
    text = GUIDE_PATH.read_text()

    lines = text.splitlines()
    in_matrix = False
    matrix_lines = []
    for line in lines:
        if "| Stop | Dist |" in line and "FLRC-260" in line:
            in_matrix = True
            matrix_lines.append(line)
            continue
        if in_matrix:
            if line.startswith("|") and "---" not in line:
                matrix_lines.append(line)
            elif line.strip() == "":
                break
            elif line.startswith("|") and "---" in line:
                matrix_lines.append(line)
                continue

    assert len(matrix_lines) > 0, "Could not find distance matrix table"

    header = matrix_lines[0]
    cols = [c.strip() for c in header.split("|")]
    cols = [c for c in cols if c]

    # Find all FLRC column indices
    flrc_indices = []
    for i, col in enumerate(cols):
        if "FLRC" in col:
            flrc_indices.append(i)

    assert len(flrc_indices) > 0, "No FLRC columns found in matrix"

    # For stops Baseline through D3, at least one FLRC should be ✓
    flrc_stops = {"50m", "100m", "218m", "436m", "872m", "1744m"}
    for row_line in matrix_lines:
        if "---" in row_line:
            continue
        row_cols = [c.strip() for c in row_line.split("|")]
        row_cols = [c for c in row_cols if c != ""]
        if len(row_cols) < 2:
            continue
        dist = row_cols[1]
        if dist not in flrc_stops:
            continue

        has_flrc = False
        for idx in flrc_indices:
            if idx < len(row_cols) and row_cols[idx] == "✓":
                has_flrc = True
                break

        assert has_flrc, (
            f"At least one FLRC config should be ✓ at {row_cols[0]} ({dist})"
        )