# .ngit/ — Nostr CI (ngit-ci) configuration

This repo is mirrored on both GitHub (`felixfelix-bot/balloon-fresh`) and ngit.
Workloads:

| workflow | what it runs | engine notes |
|---|---|---|
| `act/workflows/host-tests.yml` | the host-side suites: nostr_store 7, relay-pipeline 12, tollgate ~350, ehash-relay 65, stratorelay 11, FLRC BT0.5 parity 12, UART telemetry 115, PCB pipeline gates 10, auto-BOOTSEL board 28 (15 run + 13 kicad-cli-gated skip in the stock image) | same commands as `.github/workflows/ci-host-tests.yml`; one harness fix serves both engines |

Suite 6 (`tests/test_flrc_bt05_parity.py`, added by P0.5 / t_dc858d9b) is the
one pytest module that DOES run in CI: it is pure text/register-bytes
assertion over the checked-in firmware sources, needs no hardware, and imports
nothing outside the stdlib — so it is safe in the minimal act image (pytest is
the only dependency). It guards the RP2040 <-> ESP32 FLRC pulse-shape (BT0.5 =>
mod-params byte3 `0x25`) parity that makes a raw-FLRC cross-platform link work.

Pitfall measured 2026-09-29 (t_dc858d9b): the act/debian image's `python3` is
apt-packaged and therefore PEP 668 `EXTERNALLY-MANAGED`, so a bare
`python3 -m pip install pytest` fails with `error: externally-managed-environment`
and takes the whole lane red. Suite 6 installs with the same graceful ladder the
build-dependency step uses (skip if importable, then plain pip, then
`--break-system-packages`, then `--user --break-system-packages`). Reproduce and
validate the ladder in a throwaway container:

```bash
docker run --rm debian:12 bash -c '
  apt-get update -qq >/dev/null 2>&1; apt-get install -y -qq python3 python3-pip >/dev/null 2>&1
  python3 -c "import pytest" 2>/dev/null || \
    python3 -m pip install --quiet pytest 2>/dev/null || \
    python3 -m pip install --quiet --break-system-packages pytest 2>/dev/null || \
    python3 -m pip install --user --quiet --break-system-packages pytest
  python3 -m pytest --version'
```

Note GitHub's ubuntu-latest runner is NOT externally managed, so the GitHub lane
passed on the same commit while the ngit lane failed — the two engines need the
tolerant ladder even though "one harness fix serves both".

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
  `tracker/hardware/auto_bootsel/tests/test_auto_bootsel_pcb.py` (28 — its
  netlist/orientation/mass/reproducibility/vendored-footprint checks are pure
  text assertions, and every kicad-cli-dependent check self-skips with an
  explicit `SKIP:` line printed by the lane, so a green run is never read as
  "the DRC gate ran here").

  This exception was ASPIRATIONAL until b7599e1. The generator built its
  footprints from `/usr/share/kicad/footprints`, so on the act image (no KiCad
  package) eleven tests ERRORED at fixture setup — `FileNotFoundError:
  .../TestPoint_THTPad_D2.5mm_Drill1.2mm.kicad_mod` on 778d662, lane RED — and
  the module's checks were therefore not "pure text assertions" at all. The
  three library footprints are now committed under
  `tracker/hardware/auto_bootsel/library.pretty/` and read from there, with the
  system library as a fallback (byte-identity asserted where KiCad exists), so
  the sentence above is now measured rather than claimed: 15 passed / 13
  skipped / 0 failed on the act image. Treat any future "runs anywhere" claim
  in this file as unverified until a lane run shows it.

Local reproduction of the ngit lane: run the same five command blocks from the
repo root (needs `gcc`, `g++`, `make`, `libmbedtls-dev`, `libcjson-dev`).
To reproduce the ACT-IMAGE behaviour of the auto-BOOTSEL suite specifically
(what CI actually sees), run it with a PATH that has no `kicad-cli` — the
kicad-cli checks skip, the rest must pass:
