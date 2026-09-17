# .ngit/ — Nostr CI (ngit-ci) configuration

This repo is mirrored on both GitHub (`felixfelix-bot/balloon-fresh`) and ngit.
Workloads:

| workflow | what it runs | engine notes |
|---|---|---|
| `act/workflows/host-tests.yml` | the 5 host-side C/C++ unit suites (nostr_store 7, relay-pipeline 12, tollgate ~350, ehash-relay 65, stratorelay 11) | same commands as `.github/workflows/ci-host-tests.yml`; one harness fix serves both engines |

What is NOT run under ngit-ci, and why:

- `.github/workflows/test.yml` (`pytest tests/`) — several modules need
  hardware (RP2040, board-lock fixtures) and `telnetlib` (removed from the
  CPython stdlib in 3.13+); the lane would be red for environment reasons, so
  it stays on GitHub/host runs where hardware can be attached.
- PCB/KiCad tooling (`tracker/hardware/`) — needs kicad-cli 9 + pcbnew, not
  available in the stock act image; verified locally/on-host instead.

Local reproduction of the ngit lane: run the same five command blocks from the
repo root (needs `gcc`, `g++`, `make`, `libmbedtls-dev`, `libcjson-dev`).
