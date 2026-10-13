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

**A comparison is only valid when Test Conditions match.** The P0.2 entry below originally
reported `+944 kbps (+113%)` by differencing against the baseline row; those two rows were
measured at different payload sizes *and* different SPI clocks, so that delta is not a
measurement of the code change and has been withdrawn. Use the `Same-conditions delta`
column — it is blank wherever the revision's delta has not been isolated by a controlled
A/B, rather than being filled with an incomparable number.

See `docs/adr/102-version-tagging-policy.md` for the full policy.

## Version History

| Version | Date | RP2040 (kbps) | ESP32 (kbps) | Same-conditions delta | Changes | Test Conditions | No Regressions |
|---------|------|---------------|--------------|-----------------------|---------|-----------------|----------------|
| v0.2.1-p0.2r | 2026-09-29 | — | not measured (no C3 radio board attached) | — | **P0.2 remediation** — cold cross-family review of `v0.2.0-p0.2`. (1) Timeout recovery now clears the sticky error register **unconditionally** (the old `irqStatus & 0x00030000` guard could not fire: `rfClearIrq()` drops the error IRQ *flags* on the next packet, so the test saw a clean IRQ word while the error stayed latched for the whole burst); (2) recovery also issues `rfClearIrq()` so the next iteration cannot read a stale `TX_DONE` from the timed-out packet; (3) recovery records the failing packet's IRQ word + DIO9 level; (4) restored the per-250 progress line and the machine-parseable `TX_DONE_STATS` summary (both dropped by v0.2.0-p0.2) and added `fail_irq`/`fail_dio9` to it; (5) header comment corrected; (6) round-2 review fixes — the invariant suite's region extraction switched from a lazy `.*?` (which stopped at the DIO9 poll's inner brace, so the assertions could not see a re-added per-packet clear) to comment/string-aware brace matching, with a new test asserting the extracted region spans the whole loop, plus comment-stripper/brace-matcher self-tests; the ngit workflow lane now lists the suites in the same order as the GitHub lane. Gate: `make test-unit` 64 passed (16 in this suite), negative control fails, `idf.py build` OK. | Pure reasoning change — no timing measured; `TX_DONE_STATS` restored so the next on-hardware run is parseable | Not verified on hardware this revision (boards absent); hot-loop command order unchanged from v0.2.0-p0.2, so the v0.2.0-p0.2 hot-loop result still applies to the loop |
| v0.2.0-p0.2 | 2026-07-29 | — | 1782 | *(withdrawn — conditions differ, see above)* | **P0.2**: Remove redundant `CLR_TX_FIFO` + conditional `CLR_ERRORS` from ESP32 RAW_TX hot loop. Error register cleared only when ERROR/CMD_ERROR IRQ bits are set (timeout recovery path). | Payload: **255 bytes**, SPI: **40 MHz**, FLRC 2.4 GHz BT0.5, fixed length 255 | Build OK; 1000/1000 TX done, 0 timeouts, throughput 1781.7 kbps on 3 consecutive bursts. **TX-side TX_DONE only — no RX-side decode confirmation.** |
| v0.1.0-baseline | 2026-07-29 | 1377 | 838 | — | Starting point before optimization. Baseline FLRC throughput on LR2021 with RadioLib v7.6.0. | Payload: **64 bytes**, SPI: **8 MHz**, FLRC BW=800 kHz CR=4/8 | Baseline — no prior version to compare. **Not comparable to v0.2.0-p0.2** (different payload size and SPI clock). |
