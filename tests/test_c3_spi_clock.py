"""Regression gate for P0.4: LR2021 SPI clock must stay inside the datasheet maximum.

The LR2021 datasheet caps the SPI clock at 16 MHz. The ESP32-C3 bench HAL
(``mesh-stack/flrc-bench-espidf/main/EspHalC3.h``) previously drove the radio at
40 MHz (GDMA HAL, commit d7ba37a) and, on the non-GDMA branch, at 18 MHz. Both
ran fine at ~1 m bench distance but violated the spec and risked SPI timing
failures with real link margin / temperature swing.

These tests are host-only: they parse the firmware sources, so they run in CI
and in ``make test-unit`` without any board attached. They exist so the clock
cannot silently drift back above spec.

RED demonstration (the test detects the original violation) can be reproduced
against the pre-fix revision:

    cd ~/repos/balloon-fresh
    git show d7ba37a:mesh-stack/flrc-bench-espidf/main/EspHalC3.h > /tmp/EspHalC3_40MHz.h
    C3_HAL_PATH=/tmp/EspHalC3_40MHz.h python -m pytest tests/test_c3_spi_clock.py -v
"""

import os
import re

import pytest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BENCH_MAIN = os.path.join(REPO_ROOT, "mesh-stack", "flrc-bench-espidf", "main")
HAL_PATH = os.environ.get("C3_HAL_PATH", os.path.join(BENCH_MAIN, "EspHalC3.h"))

# LR2021 datasheet maximum SPI clock.
DATASHEET_MAX_HZ = 16_000_000

# Files that talk to the LR2021 radio (the 16 MHz limit applies to all of them).
RADIO_SOURCES = ("EspHalC3.h", "esp32_raw_tx.cpp", "esp32_raw_rx.cpp")


def _read(path: str) -> str:
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def _eval_int_expr(expr: str) -> int:
    """Evaluate a simple integer arithmetic expression such as ``16 * 1000 * 1000``."""
    if not re.fullmatch(r"[\d\s*+()/]+", expr):
        raise AssertionError(f"unexpected non-arithmetic SPI clock expression: {expr!r}")
    return int(eval(expr, {"__builtins__": {}}, {}))  # noqa: S307 - regex-validated


def _parse_spi_hz_macro(text: str) -> int:
    match = re.search(r"#define\s+ESPHAL_C3_SPI_HZ\s+\(([^)]*)\)", text)
    if not match:
        match = re.search(r"#define\s+ESPHAL_C3_SPI_HZ\s+([0-9\s*+()]+)", text)
    assert match, "ESPHAL_C3_SPI_HZ is not defined in the C3 radio HAL"
    return _eval_int_expr(match.group(1).strip())


class TestC3SpiClockDatasheetCompliance:
    """ESPHAL_C3_SPI_HZ and every LR2021 radio SPI device config stay <= 16 MHz."""

    def test_hal_file_exists(self):
        assert os.path.isfile(HAL_PATH), f"C3 radio HAL not found: {HAL_PATH}"

    def test_spi_hz_macro_within_datasheet_max(self):
        hz = _parse_spi_hz_macro(_read(HAL_PATH))
        assert hz <= DATASHEET_MAX_HZ, (
            f"ESPHAL_C3_SPI_HZ = {hz} Hz exceeds the LR2021 datasheet maximum "
            f"of {DATASHEET_MAX_HZ} Hz"
        )

    def test_spi_hz_macro_is_arithmetic_and_nonzero(self):
        hz = _parse_spi_hz_macro(_read(HAL_PATH))
        assert hz > 0, "ESPHAL_C3_SPI_HZ must be a positive clock value"

    def test_radio_device_config_uses_the_macro(self):
        """dev_cfg.clock_speed_hz must reference the macro, not a magic literal."""
        text = _read(HAL_PATH)
        assignments = re.findall(r"dev_cfg\.clock_speed_hz\s*=\s*([^;]+);", text)
        assert assignments, "no dev_cfg.clock_speed_hz assignment found in the HAL"
        assert any(
            "ESPHAL_C3_SPI_HZ" in a for a in assignments
        ), f"radio SPI device clock is not driven by ESPHAL_C3_SPI_HZ: {assignments}"
        for literal in assignments:
            if "ESPHAL_C3_SPI_HZ" in literal:
                continue
            numbers = re.findall(r"\d+", literal)
            for n in numbers:
                assert int(n) <= DATASHEET_MAX_HZ, (
                    f"literal radio SPI clock {literal!r} exceeds the LR2021 "
                    f"datasheet maximum of {DATASHEET_MAX_HZ} Hz"
                )

    def test_no_literal_radio_spi_clock_above_spec(self):
        """No radio source may hard-code an SPI clock above the 16 MHz datasheet max."""
        offenders = []
        for name in RADIO_SOURCES:
            path = os.path.join(BENCH_MAIN, name)
            if not os.path.isfile(path):
                continue
            for lineno, line in enumerate(_read(path).splitlines(), 1):
                if "clock_speed_hz" not in line or "ESPHAL_C3_SPI_HZ" in line:
                    continue
                for n in re.findall(r"\b(\d{7,9})\b", line):
                    if int(n) > DATASHEET_MAX_HZ:
                        offenders.append(f"{name}:{lineno}: {line.strip()}")
        assert not offenders, "radio SPI clock above datasheet max:\n" + "\n".join(offenders)

    def test_firmware_reports_the_same_clock_it_configures(self):
        """Runtime banners must print ESPHAL_C3_SPI_HZ so a flashed board self-reports."""
        reporters = [
            name for name in ("esp32_raw_tx.cpp", "esp32_raw_rx.cpp")
            if os.path.isfile(os.path.join(BENCH_MAIN, name))
        ]
        assert reporters, "expected at least one raw C3 bench application in main/"
        for name in reporters:
            text = _read(os.path.join(BENCH_MAIN, name))
            assert re.search(r'SPI clock = %d Hz\\n",\s*ESPHAL_C3_SPI_HZ', text), (
                f"{name} does not report ESPHAL_C3_SPI_HZ in its startup banner"
            )


class TestC3SpiClockRegressionAtOriginalValue:
    """Guard against the exact historical violations (40 MHz GDMA HAL, 18 MHz legacy)."""

    @pytest.mark.parametrize("bad_hz", [40_000_000, 18_000_000])
    def test_historical_violations_would_be_rejected(self, bad_hz):
        fake = f"#define ESPHAL_C3_SPI_HZ   ({bad_hz // 1_000_000} * 1000 * 1000)\n"
        assert _parse_spi_hz_macro(fake) > DATASHEET_MAX_HZ
