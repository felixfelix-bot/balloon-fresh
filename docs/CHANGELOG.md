# Changelog

All notable firmware version tags for the balloon-speed-tests optimization track are
documented in this file.

## Versioning Policy

Versions follow **semantic versioning** (`vMAJOR.MINOR.PATCH`):

- **MAJOR** — architecture change (new radio mode, new platform, protocol change)
- **MINOR** — throughput improvement or new feature (new optimization, new measurement capability)
- **PATCH** — bugfix that maintains or improves all metrics

A new version is tagged **only** when a firmware change produces a successful test showing
progress over the previous version with **no regressions** in any metric (throughput, error
rate, reliability, range). If a regression is found, the change is not tagged until the
regression is fixed and all metrics are ≥ the previous tag.

Each git tag is annotated with: throughput measured (RP2040 + ESP32), what changed since
the last tag, test conditions (payload size, SPI clock, modulation params), and confirmation
that no regressions were found.

See `docs/adr/ADR-017-version-tagging-policy.md` for the full policy.

## Version History

| Version | Date | RP2040 (kbps) | ESP32 (kbps) | Δ RP2040 | Δ ESP32 | Changes | Test Conditions | No Regressions |
|---------|------|---------------|--------------|----------|---------|---------|-----------------|----------------|
| v0.1.0-baseline | 2026-07-29 | 1377 | 838 | — | — | Starting point before optimization. Baseline FLRC throughput on LR2021 with RadioLib v7.6.0. | Payload: 64 bytes, SPI: 8 MHz, FLRC BW=800 kHz CR=4/8 | Baseline — no prior version to compare |