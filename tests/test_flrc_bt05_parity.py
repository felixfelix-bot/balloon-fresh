"""TDD test for P0.5 — FLRC pulse shape BT0.5 unified across RP2040 + ESP32.

Spec (kanban t_dc858d9b): the ESP32 FLRC bench firmware initialised
SET_FLRC_MOD_PARAMS with byte3 = 0x27 — i.e. coding-rate 2 (None/1-0) with
BT = 7 (BT1.0) — while RP2040 used BT = 5 (BT0.5).  Both ends of a raw-FLRC
link must program the SAME modulation, so every FLRC MOD_PARAMS command in the
tree must encode BT0.5.

LR2021 SET_FLRC_MODULATION_PARAMS (opcode 0x0248), byte 3:

    bit7..4 = coding rate   (0x02 = CR 1/0 i.e. "None")
    bit3..0 = pulse shape BT (0x05 = BT0.5, 0x07 = BT1.0)

=> BT0.5 + CR-None == (0x02 << 4) | 0x05 == 0x25
=> BT1.0 + CR-None == (0x02 << 4) | 0x07 == 0x27

The 3 files named by the card are the cross-platform link under test:
  * mesh-stack/flrc-bench-espidf/main/esp32_raw_tx.cpp  (LSB / Toitria / raw)
  * mesh-stack/flrc-bench-espidf/main/esp32_raw_rx.cpp
  * firmware/rp2040/src/flrc_rx_raw.cpp

Hardware assertions ("no packet loss, correct CRC, good RSSI" on a real
ESP32<->RP2040 pair) need the boards attached and are covered by
`make test-hardware`, not here.  These tests are the host-side proof that
cannot drift: the register bytes the two platforms actually emit.
"""

import os
import re

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

FLRC_BENCH = os.path.join(REPO_ROOT, "mesh-stack", "flrc-bench-espidf", "main")
RP2040_SRC = os.path.join(REPO_ROOT, "firmware", "rp2040", "src")

ESP32_TX = os.path.join(FLRC_BENCH, "esp32_raw_tx.cpp")
ESP32_RX = os.path.join(FLRC_BENCH, "esp32_raw_rx.cpp")
RP2040_RX_RAW = os.path.join(RP2040_SRC, "flrc_rx_raw.cpp")

# LR2021 opcodes / field values this test is about
OP_FLRC_MOD_PARAMS = 0x48
CR_NONE = 0x02
BT_0_5 = 0x05
BT_1_0 = 0x07
BYTE3_BT05 = (CR_NONE << 4) | BT_0_5  # 0x25
BYTE3_BT10 = (CR_NONE << 4) | BT_1_0  # 0x27

# Matches the SPI command payload of a FLRC MOD_PARAMS write:
#   0x02, 0x48, <bitrate|bw>, <cr<<4 | bt>
# `brBw` may be a literal or a variable name, so capture it loosely.
RE_MOD_PARAMS = re.compile(
    r"\{\s*0x02\s*,\s*0x48\s*,\s*(?P<brbw>[A-Za-z0-9_]+)\s*,\s*"
    r"(?P<crbt>0x[0-9a-fA-F]{2})\s*\}"
)

# Every file in the tree that programs the LR2021 modem directly.
RE_CPP_SOURCES = re.compile(r"\.(?:cpp|cc|cxx|c|h)$", re.I)


def _read(path):
    with open(path, "r", encoding="utf-8", errors="replace") as fh:
        return fh.read()


def _mod_params_hits(source):
    """[(brbw, crbt_int)] for every FLRC MOD_PARAMS write in `source`."""
    return [
        (m.group("brbw"), int(m.group("crbt"), 16))
        for m in RE_MOD_PARAMS.finditer(source)
    ]


def _bt_of(byte3):
    return byte3 & 0x0F


def _cr_of(byte3):
    return (byte3 >> 4) & 0x0F


def _iter_flrc_mod_sources():
    """All .c/.h/.cpp files under the two firmware trees that touch 0x48."""
    for root_dir in (FLRC_BENCH, RP2040_SRC):
        if not os.path.isdir(root_dir):
            continue
        for name in sorted(os.listdir(root_dir)):
            if not RE_CPP_SOURCES.search(name):
                continue
            path = os.path.join(root_dir, name)
            if not os.path.isfile(path):
                continue
            text = _read(path)
            if _mod_params_hits(text):
                yield path, text


class TestP05Esp32ModParamsBt05:
    """ESP32 TX + RX must program BT0.5 (0x25), not BT1.0 (0x27)."""

    def test_esp32_tx_source_exists(self):
        assert os.path.isfile(ESP32_TX), f"missing source: {ESP32_TX}"

    def test_esp32_rx_source_exists(self):
        assert os.path.isfile(ESP32_RX), f"missing source: {ESP32_RX}"

    def test_esp32_tx_uses_bt05(self):
        hits = _mod_params_hits(_read(ESP32_TX))
        assert hits, "no FLRC SET_FLRC_MOD_PARAMS (0x0248) write found in esp32_raw_tx.cpp"
        byte3s = {crbt for _, crbt in hits}
        assert byte3s == {BYTE3_BT05}, (
            "esp32_raw_tx.cpp FLRC mod params must be 0x%02X (CR-None, BT0.5); "
            "found %s" % (BYTE3_BT05, sorted(hex(b) for b in byte3s))
        )

    def test_esp32_rx_uses_bt05(self):
        hits = _mod_params_hits(_read(ESP32_RX))
        assert hits, "no FLRC SET_FLRC_MOD_PARAMS (0x0248) write found in esp32_raw_rx.cpp"
        byte3s = {crbt for _, crbt in hits}
        assert byte3s == {BYTE3_BT05}, (
            "esp32_raw_rx.cpp FLRC mod params must be 0x%02X (CR-None, BT0.5); "
            "found %s" % (BYTE3_BT05, sorted(hex(b) for b in byte3s))
        )

    def test_rp2040_rx_raw_uses_bt05(self):
        """RP2040's raw RX init was the last BT1.0 holdout; P0.5 fixed it too."""
        hits = _mod_params_hits(_read(RP2040_RX_RAW))
        assert hits, "no FLRC SET_FLRC_MOD_PARAMS (0x0248) write found in flrc_rx_raw.cpp"
        byte3s = {crbt for _, crbt in hits}
        assert byte3s == {BYTE3_BT05}, (
            "firmware/rp2040/src/flrc_rx_raw.cpp FLRC mod params must be 0x%02X; "
            "found %s" % (BYTE3_BT05, sorted(hex(b) for b in byte3s))
        )

    def test_no_bt10_left_in_the_three_link_files(self):
        """Direct regression guard: 0x27 must not reappear in the link files."""
        for path in (ESP32_TX, ESP32_RX, RP2040_RX_RAW):
            bad = [hex(b) for _, b in _mod_params_hits(_read(path)) if b == BYTE3_BT10]
            assert not bad, (
                f"{os.path.relpath(path, REPO_ROOT)} still writes "
                f"0x{BYTE3_BT10:02X} (CR-None, BT1.0) — cross-platform BT mismatch"
            )


class TestP05CrossPlatformParity:
    """RP2040 and ESP32 must agree on modulation, or the link cannot work."""

    def test_all_flrc_mod_params_are_bt05(self):
        offenders = []
        for path, text in _iter_flrc_mod_sources():
            for brbw, crbt in _mod_params_hits(text):
                if _bt_of(crbt) != BT_0_5:
                    offenders.append(
                        "%s: brBw=%s crbt=0x%02X (BT%d.%d)"
                        % (os.path.relpath(path, REPO_ROOT), brbw, crbt,
                           _bt_of(crbt), 5 if _bt_of(crbt) == 5 else 0)
                    )
        assert not offenders, (
            "FLRC pulse shape is not unified on BT0.5 in:\n  " + "\n  ".join(offenders)
        )

    def test_esp32_and_rp2040_bt_and_cr_match(self):
        """The TX/RX pair of each platform programs the same BR/BW + CR + BT."""
        pairs = {
            "esp32": (_read(ESP32_TX), _read(ESP32_RX)),
            "rp2040": (_read(os.path.join(RP2040_SRC, "flrc_raw_tx.cpp")),
                       _read(RP2040_RX_RAW)),
        }
        for platform, (tx_src, rx_src) in pairs.items():
            tx = set(_mod_params_hits(tx_src))
            rx = set(_mod_params_hits(rx_src))
            assert tx, f"{platform}: TX has no FLRC MOD_PARAMS write"
            assert rx, f"{platform}: RX has no FLRC MOD_PARAMS write"
            assert tx == rx, (
                f"{platform} TX/RX modulation mismatch: TX={sorted(tx)} RX={sorted(rx)}"
            )

    def test_esp32_matches_rp2040_exactly(self):
        """Cross-platform: ESP32 TX and RP2040 TX program identical mod params."""
        esp = set(_mod_params_hits(_read(ESP32_TX)))
        rp_tx = set(_mod_params_hits(_read(os.path.join(RP2040_SRC, "flrc_raw_tx.cpp"))))
        assert esp == rp_tx, (
            "ESP32 and RP2040 TX FLRC modulation differ: "
            f"esp32={sorted(esp)} rp2040={sorted(rp_tx)}"
        )

    def test_byte3_decodes_to_cr_none_and_bt05(self):
        """Guard the encoding itself, so a comment/doc typo cannot pass."""
        assert _cr_of(BYTE3_BT05) == CR_NONE
        assert _bt_of(BYTE3_BT05) == BT_0_5
        hits = _mod_params_hits(_read(ESP32_TX))
        for _, crbt in hits:
            assert _cr_of(crbt) == CR_NONE, (
                f"coding rate drifted to 0x{_cr_of(crbt):X} in esp32_raw_tx.cpp"
            )
            assert _bt_of(crbt) == BT_0_5, (
                f"pulse shape drifted to BT0x{_bt_of(crbt):X} in esp32_raw_tx.cpp"
            )


class TestP05Docs:
    """The card requires docs updated: no doc may still claim BT1.0 for FLRC."""

    DOC_DIR = os.path.join(REPO_ROOT, "docs")

    # A doc may still show the BT1.0 encoding as *reference* (the LR2021
    # encoding table) — that is not a claim about what this firmware programs.
    # What must not survive P0.5 is a doc asserting BT1.0 as the value IN USE
    # (or "proven working"), which is what the next reader would copy.
    RE_BT10_IN_USE = re.compile(
        r"^.*0x0?2\s*,\s*0x48\s*,\s*[\w\d]+\s*,\s*0x27.*$", re.I | re.M)
    RE_IN_USE_WORDS = re.compile(
        r"proven|working|we\s+use|in\s+use|we\s+set|current|default|"
        r"our\s+(?:value|config)|must\s+use|is\s+used", re.I)

    def test_no_doc_claims_bt10_is_the_value_in_use(self):
        if not os.path.isdir(self.DOC_DIR):
            return
        offenders = []
        for name in sorted(os.listdir(self.DOC_DIR)):
            if not name.endswith(".md"):
                continue
            text = _read(os.path.join(self.DOC_DIR, name))
            if not re.search(r"\b0x0248\b|FLRC_MOD|MOD_PARAMS", text, re.I):
                continue
            for m in self.RE_BT10_IN_USE.finditer(text):
                line = m.group(0)
                if self.RE_IN_USE_WORDS.search(line):
                    lineno = text.count("\n", 0, m.start()) + 1
                    offenders.append(f"{name}:{lineno}: {line.strip()}")
        assert not offenders, (
            "docs still assert BT1.0/0x27 as the FLRC mod params in use:\n  "
            + "\n  ".join(offenders)
        )

    def test_spi_protocol_reference_states_bt05_on_both_platforms(self):
        """The canonical SPI reference must carry the P0.5 decision."""
        path = os.path.join(self.DOC_DIR, "lr2021-spi-protocol-reference.md")
        if not os.path.isfile(path):
            return
        text = _read(path)
        assert re.search(r"0x0?2\s*,\s*0x48\s*,\s*[\w\d]+\s*,\s*0x25", text, re.I), (
            "lr2021-spi-protocol-reference.md does not document the 0x25 "
            "(CR-None, BT0.5) FLRC mod-params payload"
        )
        assert re.search(r"BT\s*0?\.?5|Bt0p5|0x05", text), (
            "lr2021-spi-protocol-reference.md does not document BT0.5 as the "
            "pulse shape in use"
        )
