"""Host-side tests for the ESP32-C3 auto-BOOTSEL test firmware.

What this module proves, and what it deliberately does not:

* It compiles the SHIPPED controller (firmware/esp32-bootsel-controller/src/
  bootsel_controller.cpp) into a host binary with recording stubs and asserts on
  the observed pin trace, timings, ack strings and watchdog behaviour. The parser
  and sequence under test are the object code that is flashed — there is no
  second implementation to drift.
* It checks the board-facing sources and docs carry the same contract (pins,
  command letters, build env) so a doc/code divergence fails here.
* It does NOT claim the soldered circuit works. That is balloon:t_33db8c37 and
  needs both boards on a desk. Nothing here requires a serial port or hardware.
"""
from __future__ import annotations

import os
import pathlib
import subprocess
import tempfile

import pytest

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
FW_DIR = REPO_ROOT / "firmware" / "esp32-bootsel-controller"
SRC_DIR = FW_DIR / "src"
HARNESS = REPO_ROOT / "tests" / "src" / "ser_io_host.cpp"
CONTROLLER_SRC = SRC_DIR / "bootsel_controller.cpp"

# Contract numbers the firmware and the docs must agree on.
RUN_GPIO = 1
BOOTSEL_GPIO = 8
SETTLE_MS = 50
RUN_LOW_MS = 100
SAMPLE_MS = 500
WD_DEFAULT_MS = 8000

_CACHE: dict = {}


def _build_and_run() -> tuple[int, str]:
    """Compile + run the host harness once per session; return (rc, stdout)."""
    if "result" in _CACHE:
        return _CACHE["result"]

    for path in (HARNESS, CONTROLLER_SRC, SRC_DIR / "bootsel_controller.h"):
        assert path.is_file(), f"missing source file: {path}"

    binary = os.path.join(tempfile.gettempdir(), "ser_io_host_bootsel")
    cmd = [
        "g++", "-std=c++17", "-Wall", "-Wextra", "-Werror", "-O1",
        "-I", str(SRC_DIR),
        str(HARNESS), str(CONTROLLER_SRC),
        "-o", binary,
    ]
    build = subprocess.run(cmd, capture_output=True, text=True)
    assert build.returncode == 0, (
        "host harness failed to compile (the shipped controller must build "
        f"warning-free):\n{build.stdout}\n{build.stderr}"
    )

    run = subprocess.run([binary], capture_output=True, text=True, timeout=60)
    _CACHE["result"] = (run.returncode, run.stdout)
    return _CACHE["result"]


@pytest.fixture(scope="module")
def harness() -> tuple[int, str]:
    return _build_and_run()


def _props(out: str) -> dict[str, str]:
    """name -> verdict for every `PROP <name> <PASS|FAIL>` line the harness emits."""
    props: dict[str, str] = {}
    for line in out.splitlines():
        if line.startswith("PROP "):
            _, name, verdict = line.split(maxsplit=2)
            props[name] = verdict.strip()
    return props


def _facts(out: str) -> dict[str, str]:
    for line in out.splitlines():
        if line.startswith("FACT "):
            return dict(kv.split("=", 1) for kv in line.split()[1:])
    return {}


def test_harness_compiles_and_runs(harness):
    rc, out = harness
    assert "RESULT " in out, f"harness produced no RESULT line:\n{out}"
    assert rc == 0, f"harness exited {rc}:\n{out}"
    assert "RESULT ALL_PROPERTIES_PASS" in out


def test_all_recorded_properties_pass(harness):
    """Fail loudly and specifically: every PROP line the harness emits is PASS."""
    _, out = harness
    props = _props(out)
    # Anti-vacuity: a silently empty harness must not read as success.
    assert len(props) >= 30, f"only {len(props)} properties recorded:\n{out}"
    failed = {k: v for k, v in props.items() if v != "PASS"}
    assert not failed, f"properties failed: {failed}\n{out}"


def test_pin_and_timing_contract(harness):
    """The pins and delays the docs promise are the ones compiled in."""
    _, out = harness
    facts = _facts(out)
    assert facts, f"harness printed no FACT line:\n{out}"
    assert facts["run_gpio"] == str(RUN_GPIO)
    assert facts["bootsel_gpio"] == str(BOOTSEL_GPIO)
    assert facts["settle_ms"] == str(SETTLE_MS)
    assert facts["run_low_ms"] == str(RUN_LOW_MS)
    assert facts["sample_ms"] == str(SAMPLE_MS)
    assert facts["wd_default_ms"] == str(WD_DEFAULT_MS)


@pytest.mark.parametrize(
    "prop",
    [
        "bootsel_gp0_low_before_run_low",
        "bootsel_run_released_before_gp0_released",
        "bootsel_settle_is_50ms",
        "bootsel_hold_run_low_100ms",
        "bootsel_hold_gp0_low_500ms",
        "bootsel_sequence_exact",
        "bootsel_ends_idle_high",
    ],
)
def test_bootsel_entry_sequence(harness, prop):
    """GP0 LOW -> RUN LOW -> RUN HIGH -> GP0 HIGH, with the documented delays.

    This is order-critical: releasing GP0 before the RP2040 samples it boots
    the flash image instead of the bootloader, and driving GP0 HIGH to select
    the bootloader is the inverted-logic bug the skill warns about.
    """
    assert _props(harness[1]).get(prop) == "PASS"


@pytest.mark.parametrize(
    "prop",
    ["run_pulse_drives_run_low", "run_pulse_releases_100ms",
     "run_pulse_never_touches_gp0", "run_pulse_counted",
     "run_pulse_clears_liveness"],
)
def test_reset_is_a_run_pulse_only(harness, prop):
    """`r` resets the RP2040 and must never drag it into the bootloader."""
    assert _props(harness[1]).get(prop) == "PASS"


@pytest.mark.parametrize(
    "prop",
    ["cmd_r_acks_ok", "cmd_b_acks_ok", "cmd_unknown_is_error",
     "cmd_empty_is_silent", "cmd_s_prints_status", "cmd_w_on_acks",
     "cmd_w_off_acks", "cmd_w_needs_arg", "cmd_h_records_heartbeat",
     "cmd_leading_space_ok", "cmd_long_reset_ok", "cmd_long_bootsel_ok",
     "cmd_long_status_ok"],
)
def test_serial_command_interface(harness, prop):
    """r=reset, b=bootsel, s=status (plus w/h and the long aliases) answer with acks."""
    assert _props(harness[1]).get(prop) == "PASS"


@pytest.mark.parametrize(
    "prop",
    ["cmd_prefix_is_rejected", "cmd_sentence_is_rejected",
     "cmd_rejected_lines_move_no_pins", "cmd_rejected_lines_count_nothing"],
)
def test_command_parse_is_exact(harness, prop):
    """A line that merely STARTS with a command letter is an error.

    These strings can reset the RP2040 or park it in the bootloader, so
    "bootselx" or a banner line must never be executed as a command. Caught by
    this suite on first run: the initial parser matched any line starting with a
    command letter, so `BL` force-entered the bootloader.
    """
    assert _props(harness[1]).get(prop) == "PASS"


@pytest.mark.parametrize(
    "prop",
    ["wd_off_is_inert", "wd_off_no_pin_change", "wd_not_due_before_threshold",
     "wd_due_at_threshold", "wd_tick_fires", "wd_tick_resets_only_run",
     "wd_tick_never_enters_bootloader", "wd_tick_counted",
     "wd_latches_single_fire", "wd_rearms_after_heartbeat",
     "wd_second_trigger_counted", "wd_no_heartbeat_ever_is_inert",
     "wd_no_heartbeat_no_pin_change"],
)
def test_heartbeat_watchdog(harness, prop):
    """Silence past the threshold resets the RP2040 exactly once per episode.

    Never BOOTSEL: an RP2040 parked in the bootloader in flight has no USB host
    to hand it a UF2, so it is unrecoverable. And a controller that has never
    observed a heartbeat must stay inert — absence of evidence is not a hang.
    """
    assert _props(harness[1]).get(prop) == "PASS"


def test_firmware_sources_match_the_documented_contract():
    """The flashable sources still carry the contract this suite asserts on."""
    main_src = (SRC_DIR / "main.cpp").read_text()
    header = (SRC_DIR / "bootsel_controller.h").read_text()
    ini = (FW_DIR / "platformio.ini").read_text()

    # the controller logic is shared with the tests, not duplicated in main.cpp
    ctrl_src = (SRC_DIR / "bootsel_controller.cpp").read_text()
    assert '#include "bootsel_controller.h"' in main_src
    for token in ('token_eq(line, "r")', 'token_eq(line, "b")',
                  'token_eq(line, "s")', 'lc == \'w\'', 'token_eq(line, "h")'):
        assert token in ctrl_src, f"command dispatch {token} disappeared from the parser"

    assert "#define BOOTSEL_GPIO_RUN     1u" in header
    assert "#define BOOTSEL_GPIO_BOOTSEL 8u" in header
    assert "#define BOOTSEL_WD_DEFAULT_MS 8000u" in header

    # the UART fallback is mandatory: this board's USB CDC console is broken
    assert "Serial1.begin" in main_src
    assert "USB_BAUD" in main_src

    # build env for the interactive controller stays defined and links both TUs
    assert "[env:esp32c3]" in ini
    assert "bootsel_controller.cpp" in ini
    # the flag must not be SET in any build_flags (a comment warning about it is fine):
    # setting it switches to native CDC and kills the console on 303a:1001
    active = [ln for ln in ini.splitlines() if not ln.lstrip().startswith(";")]
    assert all("-DARDUINO_USB_MODE" not in ln for ln in active)
    assert all("-DARDUINO_USB_CDC_ON_BOOT" not in ln for ln in active)


def test_readme_documents_pins_commands_and_limits():
    """Operators must be able to wire and drive this without reading the source."""
    readme = (FW_DIR / "README.md").read_text()
    for token in ("GPIO1", "GPIO8", "RPI-RP2", "115200"):
        assert token in readme, f"README lost the {token} contract"
    # the command letters are documented
    for letter in ("`r`", "`b`", "`s`"):
        assert letter in readme, f"README does not document the {letter} command"
    # the serial caveat must be stated, not left for the next operator to rediscover
    assert "303a:1001" in readme
