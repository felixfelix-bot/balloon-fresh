# .ngit/ — Nostr CI (ngit-ci) configuration

This repo is mirrored on both GitHub (`felixfelix-bot/balloon-fresh`) and ngit
(`npub1nng5mxkdh2mu593twukfr7j3fk5wxfy0v8ujf0e5g8nwwtzlphhqksqpew/balloon-fresh`).
Workflows run on the ngit-ci coordinator; a push of any ref triggers the jobs
whose `on:` block matches.

| workflow | what it runs | notes |
|---|---|---|
| `act/workflows/bootsel-controller.yml` | the ESP32-C3 auto-BOOTSEL controller: compiles and runs its host harness, then `tests/test_bootsel_controller.py` (47 tests) | host-side only, no boards, no packages beyond g++ + pytest, seconds to run |

Adding a lane here is how a code-tier kanban card can satisfy the `ci_evidence`
gate: the gate's reader (`ngit_ci_evidence.py`) requires a **published commit**
with a green kind-9842 result, not a landed one, so a card that must not touch
`master` can push `refs/heads/ci/<slug>` and trigger a workflow at that ref.

**Every lane runs on every push.** A workflow that fails on master is therefore
worse than no workflow: it turns the whole repository's CI red and blocks the
`ci_evidence` gate for unrelated cards. Before adding one, run its command blocks
on the branch you are pushing and delete it if they do not hold there.

The repository-wide host suites (nostr_store, relay-pipeline, tollgate,
ehash-relay, stratorelay, FLRC BT0.5 parity, UART telemetry) live on the `ci/*`
branches as `.ngit/act/workflows/host-tests.yml`, not on master, because two of
its steps reference files that do not exist on master
(`tests/test_flrc_bt05_parity.py`, `tracker/firmware/components/uart_telemetry/`).
Merging that lane to master requires adding those first — see
`ci/uart-telemetry-protocol`.

## Adding a lane

1. `.ngit/act/workflows/<name>.yml`, written the same way as a GitHub workflow
   (`on:`, `jobs:`, `steps:`, `uses: actions/checkout@v4`).
2. Keep it host-only and self-contained. There are no boards, no ESP-IDF, no
   Pico-SDK and no apt-installed KiCad in the act image; anything needing those
   stays on GitHub/host runs.
3. `python3 -m pip install <pkg>` needs the `--break-system-packages` fallback:
   the container's python3 is externally managed (PEP 668) and a bare install
   exits 1, which fails the whole lane (observed 2026-09-29 on `d3a3b45a`).
4. Verify locally first — run the exact command blocks from the repo root.

## What deliberately does NOT run here

- `.github/workflows/test.yml` (`pytest tests/`) — several modules need hardware
  (RP2040, board-lock fixtures) or `telnetlib` (removed in CPython 3.13+), so the
  lane would be red for environment reasons. Individual hardware-free modules
  get their own lane instead (see `bootsel-controller.yml`).
- PCB/KiCad tooling (`tracker/hardware/`) — needs kicad-cli 9 + pcbnew.
