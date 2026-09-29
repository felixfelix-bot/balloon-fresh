# .ngit/ — Nostr CI (ngit-ci) configuration

This repo is mirrored on both GitHub (`felixfelix-bot/balloon-fresh`) and ngit.
Workloads:

| workflow | what it runs | engine notes |
|---|---|---|
| `act/workflows/host-tests.yml` | the host-side suites: nostr_store 7, relay-pipeline 12, tollgate ~350, ehash-relay 65, stratorelay 11, FLRC BT0.5 parity 12, UART telemetry 115, PCB pipeline gates 10, auto-BOOTSEL board 25 | same commands as `.github/workflows/ci-host-tests.yml`; one harness fix serves both engines |

Suite 6 (`tests/test_flrc_bt05_parity.py`, added by P0.5 / t_dc858d9b) is the
one pytest module that DOES run in CI: it is pure text/register-bytes
assertion over the checked-in firmware sources, needs no hardware, and imports
nothing outside the stdlib — so it is safe in the minimal act image
(`python3 -m pip install pytest` is the only dependency). It guards the RP2040
<-> ESP32 FLRC pulse-shape (BT0.5 => mod-params byte3 `0x25`) parity that makes
a raw-FLRC cross-platform link work.

What is NOT run under ngit-ci, and why:

- `.github/workflows/test.yml` (`pytest tests/`) — several modules need
  hardware (RP2040, board-lock fixtures) and `telnetlib` (removed from the
  CPython stdlib in 3.13+); the lane would be red for environment reasons, so
  it stays on GitHub/host runs where hardware can be attached. (The single
  exception is suite 6 above, which is scoped to one hardware-free module.)
- PCB/KiCad tooling (`tracker/hardware/`) — needs kicad-cli 9 + pcbnew, not
  available in the stock act image; verified locally/on-host instead.
  Two exceptions are lane-visible rather than environment-red:
  `tests/test_pcb_pipeline_gates.py` (10, static assertions) and
  `tracker/hardware/auto_bootsel/tests/test_auto_bootsel_pcb.py` (25 — its
  netlist/orientation/mass/negative-control checks are pure text assertions,
  and its two kicad-cli checks self-skip with an explicit `SKIP:` line printed
  by the lane, so a green run is never read as "the DRC gate ran here").

Local reproduction of the ngit lane: run the same five command blocks from the
repo root (needs `gcc`, `g++`, `make`, `libmbedtls-dev`, `libcjson-dev`).
