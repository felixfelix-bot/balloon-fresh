# ADR 017: Version Tagging Policy — Tag on Progress Without Regressions

## Status

Accepted

## Context

The balloon-speed-tests worktree runs a 4-phase optimization plan (Phase 0–3, 15 tasks) to
increase FLRC throughput on LR2021 radio modules from a baseline of:

- **RP2040:** 1377 kbps
- **ESP32-C3:** 838 kbps

Target: 2540 kbps.

Each phase produces firmware changes and test results. Without a tagging policy there is
no way to identify which commits represent verified progress milestones vs. experimental
work that may have regressed. We need a discipline that:

1. Records a git tag only when a change is **demonstrably better** than the previous tagged
   version — no regressions in any measured metric.
2. Produces a human-readable progress timeline via annotated tag messages.
3. Maintains a structured CHANGELOG with before/after metrics for each version.

## Decision

### Tagging Trigger

Tag a new version **whenever a firmware change produces a successful test showing progress
over the previous tagged version.**

### Definition of Progress

Progress means **any one** of the following, with **zero regressions** in all other metrics:

- **Measurable throughput improvement** — RP2040 or ESP32 throughput increased relative to
  the previous tag.
- **Verified feature addition** — a new capability confirmed by test (new optimization,
  new measurement capability, new radio mode).

### Definition of Regression

A regression is **any metric that got worse** relative to the previous tagged version:

| Metric | Regression |
|--------|-----------|
| Throughput (RP2040) | Dropped below previous tag's measured value |
| Throughput (ESP32) | Dropped below previous tag's measured value |
| Error rate | Increased |
| Reliability (packet loss / stability) | Decreased |
| Range | Decreased |

If **any** regression is found: **do NOT tag.** Fix the regression first. Tag only when all
metrics are ≥ the previous tagged version.

### Version Format

Semantic versioning: `vMAJOR.MINOR.PATCH`

| Bump | When |
|------|------|
| **MAJOR** | Architecture change — new radio mode, new platform, protocol change |
| **MINOR** | Throughput improvement or new feature — new optimization, new measurement capability |
| **PATCH** | Bugfix that maintains or improves all metrics |

### Annotated Tag Message Requirements

Each tag **must** be created with `git tag -a` and include an annotated message documenting:

1. **Throughput measured** — RP2040 kbps, ESP32 kbps (if applicable)
2. **What changed** since the last tag (concise summary)
3. **Test conditions** — payload size, SPI clock, modulation parameters
4. **Confirmation: no regressions** — explicit statement that all other metrics are ≥ previous tag

Example tag message:

```
v0.2.0 — Phase 1: SPI clock optimization

Throughput:
  RP2040: 1620 kbps (prev: 1377 kbps, +243 kbps)
  ESP32:  980 kbps (prev: 838 kbps, +142 kbps)

Changes since v0.1.0-baseline:
  - Increased SPI clock from 8 MHz to 16 MHz
  - Enabled FLRC 1.3 Mbps raw mode on RP2040

Test conditions:
  Payload: 64 bytes
  SPI clock: 16 MHz
  Modulation: FLRC, BW=800 kHz, CR=4/8, SF auto

No regressions: error rate, reliability, and range all unchanged or improved.
```

### CHANGELOG

Maintain `docs/CHANGELOG.md` tracking each version tag with a before/after metrics table.
The CHANGELOG is the human-readable companion to the annotated git tags.

## Consequences

- Developers **must** run the full test suite and compare against the previous tag's
  metrics before tagging.
- Tags are the authoritative progress timeline — experimental commits that regress are
  not tagged and remain in development history only.
- The CHANGELOG must be updated in the same commit or immediately after creating a tag.
- Reverting a tagged version requires a new tag (e.g., `v0.2.1`) — old tags are never
  deleted or moved.

## References

- Baseline metrics: RP2040=1377 kbps, ESP32=838 kbps
- Target: 2540 kbps
- Related: 4-phase optimization plan (Phase 0–3, 15 tasks)
- `docs/CHANGELOG.md` — version tracking table