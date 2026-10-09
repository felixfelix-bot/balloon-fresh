# REPORT — docs/program-gap-analysis

**Deliverable:** `docs/analysis/PROGRAM-GAP-ANALYSIS.md`
**Branch:** `docs/program-gap-analysis`  **Base:** `github/main` @ `09e1b69`

## SHAs

- **Deliverable commit** (`docs/analysis/PROGRAM-GAP-ANALYSIS.md`): `398cc70862a8e13de5e6607a2f2a189de47c0e3f`
- Verified on all three remotes at the time of that push:
  - `git ls-remote github refs/heads/docs/program-gap-analysis` → `398cc70862a8e13de5e6607a2f2a189de47c0e3f`
  - `git ls-remote origin refs/heads/docs/program-gap-analysis` → `398cc70862a8e13de5e6607a2f2a189de47c0e3f`
  - `git ls-remote ngit   refs/heads/docs/program-gap-analysis` → `398cc70862a8e13de5e6607a2f2a189de47c0e3f`

> **Branch tip advances with this file.** REPORT.md is gitignored and force-added, so every edit to it
> is a new commit and moves the tip. The **doc commit** above is stable; the tip after the last report
> commit must be read with `git ls-remote <remote> refs/heads/docs/program-gap-analysis`.
> Pushed **github first, then ngit separately** (no `--atomic`).
> Base: `github/main` @ `09e1b69`.

## What was produced

- §1 plain-language inventory of the whole system + mermaid block diagram.
- §2 status ledger for 14 workstreams with evidence.
- §3a/§3b/§3c end-to-end gap analyses (pre-pressurisation board; RX/TX BOM + assembly plan;
  HIGH/LOW-power flight boards ± wings).
- §4 fifteen numbered decisions with options / recommendation / consequence / what they block.
- §5 consolidation ledger (16 unmerged design branches) + ADR-number collision map.

## Method

Read-only over every other branch (`git show`, `git diff`, `git ls-tree`). No merge. No push to main.
Prices/parts/specs taken only from the in-repo documents that cite URLs; unsourced ⇒ `TODO(unverified)`.


---

# REPORT t_588b1d1b — relay-set constant, absence test, fake relay transport

Branch: `pr/relay-scaffold-testkit` (stacked on `pr/relay-failover-publisher` @ ae0d1021).
Repo path: `firmware/e80-stm32-bench/tools/`.

## Deliverables
- `relay_testkit.py` — single declared source of truth for the failover relay set
  (bare hosts, exact order) + dead-host hostname-boundary matcher + importable fake
  relay transport double (async `FakeRelayTransport`, sync `SyncFakeRelayTransport`)
  with per-relay injectable behaviour ACCEPT / TIMEOUT / HARD_ERROR / BLOCKED.
- `test_relay_testkit.py` — 13 pins: exact set, derived URL view, consistency with
  the landed publisher, dead-host absence (runtime + boundary source scan incl. a
  non-false-positive proof for `relay2.contextvm.org`), the double's named behaviours,
  and two end-to-end smoke tests driving the real `RelayFailoverPublisher`.

## Exact commands + observed result
RED (test present, `relay_testkit.py` absent):
    python3 -m pytest -q firmware/e80-stm32-bench/tools/test_relay_testkit.py
    -> exit 2; ModuleNotFoundError: No module named 'relay_testkit' (1 error)
GREEN:
    python3 -m pytest -q firmware/e80-stm32-bench/tools/test_relay_testkit.py
    -> 13 passed in 0.14s
Regression:
    python3 -m pytest -q firmware/e80-stm32-bench/tools/test_relay_failover_publisher.py
    -> 19 passed in 0.19s
    python3 -m pytest -q firmware/e80-stm32-bench/tools/test_giftwrap_single_path.py
    -> 4 passed in 0.96s

## Step 1 note (honesty)
The card asked to paste RED output from the *sibling failover tests*; those are
already GREEN (19 passed) because the publisher landed earlier (ae0d1021, t_120db4f6).
No RED exists for that suite. The RED pasted above is the genuine red for THIS card's
own new test (missing scaffold module). Nothing was fabricated.

## Single-source-of-truth note
`relay_testkit.FAILOVER_RELAYS` is the canonical bare-host list (card-exact);
`FAILOVER_RELAY_URLS` is derived from it. The landed publisher keeps its own `wss://`
list re-exported from the gift-wrap choke-point; the scaffold is the declared source
and `test_publisher_relay_set_matches_the_constant` pins the publisher's set equal to
it, so drift breaks a test.
