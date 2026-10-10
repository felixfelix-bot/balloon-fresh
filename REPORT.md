# REPORT — Consolidate the e80-cvm PR stack (#26–#34) into ONE PR

Card: `t_cde6b4fd` (board `balloon`). Repo: `~/repos/balloon-fresh`
(remote `origin` = github.com/felixfelix-bot/balloon-fresh).
Worktree/branch: `~/worktrees/t_cde6b4fd` on `pr/e80-cvm-consolidated`,
based on `origin/main`.

Status: **complete and pushed** — one PR open, the nine superseded PRs closed,
host suite green (counts below), nothing merged to `main`.

---

## 1. Findings

1. **The fold was not mechanical.** Five of the nine commits conflicted; two of
   those conflicts were *intent* conflicts, not text conflicts:

   | file | conflicting intents |
   |---|---|
   | `tools/nostr_giftwrap.py` | #32 (`t_4c98fbe7`) replaced the caller-supplied `signer` with `keys=KeyMaterial`; #30/#34 (`t_c4c43d76`) call `build_gift_wrap(payload, npub, signer)` positionally |
   | `tools/keymaterial.py` | #32 reads only `E80_CLIENT_*`/`E80_SERVER_*`; #28 (`t_9db98e6d`) reads the `CVM_*` names the ADR and RANGE-TEST-GUIDE document |

   The naive merge of the first pair left a **live `UnboundLocalError`** in
   `build_gift_wrap` (`signer` referenced before assignment), i.e. the
   consolidated branch was broken at HEAD before this run: 33 test failures
   (`test_nostr_giftwrap.py` 9, `test_giftwrap_determinism.py` 11,
   `test_giftwrap_determinism_spec.py` 13).

2. **#28's env interface was *not* fully subsumed** (see §3 — the base had lost
   the `CVM_*` names, and the publish path resolves keys through that module).

3. **`tools/test_giftwrap_determinism_spec.py` could never run** in a bare
   environment: its 14 coroutine tests are `@pytest.mark.asyncio` and no branch
   declared `pytest-asyncio`, so `python3 -m pytest` reports *"async def
   functions are not natively supported"*. Fixed in-repo instead of adding an
   undeclared third-party dependency (§4).

4. **The relay family's four test files were not collected by the curated
   `make range-test-host` target** (their commits never touched the Makefile).
   Now they are (§4) — otherwise the PR's own entry point would not exercise
   the fold's relay tests.

5. **Pre-existing on the vehicle, not introduced here — left alone, reported:**
   `cvm_tx_listener.load_and_check_keys(env)` ignores its `env` argument
   (it calls the accessor, which reads `os.environ` only). Byte-identical to
   `origin/pr/keymaterial-env-sole-source`, so it is #32's design, not a fold
   regression. Needs an `env`-mapping parameter on the accessor; out of scope
   for a consolidation PR.

## 2. Fold table — nine commits → source PR → consolidated SHA

`git cherry origin/pr/keymaterial-env-sole-source origin/<branch>` produced the
fold set ('+' rows only); `82e3309` (the un-PR'd `wt/t_0049ed58-rxarmed` commit)
was **not** carried, and no commit already inside the base was re-folded.

| original SHA | source branch (PR) | consolidated SHA | what landed |
|---|---|---|---|
| `9455b07a` | `pr/giftwrap-deterministic` (#30) | `5a29106` | deterministic, idempotent NIP-59 gift-wrap (t_c4c43d76) |
| `53aeacaa` | `pr/giftwrap-deterministic` (#30) | `0f758a5` | `docs/GIFTWRAP_DETERMINISM.md` |
| `39e72f7f` | `pr/giftwrap-deterministic` (#30) | `c38f0fd` | wrap-cache lifetime/eviction docs |
| `1a603067` | `pr/giftwrap-determinism-spec` (#34) | `e1e66c1` | hermetic spec-conformance suite (14 tests) |
| `ae0d1021` | `pr/relay-failover-publisher` (#26) | `6e07f60` | deterministic relay-failover kind-1059 publisher |
| `469c5b2e` | `pr/relay-scaffold-testkit` (#29) | `87bfe1c` | relay fan-out scaffolding (`relay_testkit.py`) |
| `7dbf7872` | `pr/fake-relay-transport-double` (#31) | `33f60c6` | hard-error flavours, attempts/reset, no-network pin |
| `f2f5b20a` | `pr/failover-relays-constant` (#33) | `1d38c4f` | `FAILOVER_RELAYS` single-sourced as bare hostnames |
| `882184ec` | `pr/keymaterial-env-accessor` (#28) | `459df15` + `5ba7b79` | **module subsumed — see §3**; its only non-subsumed delta kept, and the `CVM_*` behaviour the base lacked restored |

Conflict resolutions, per file (both intents preserved, no test dropped):

* `nostr_giftwrap.py` — the base's env-only `keys=KeyMaterial` path stays
  **primary**; the determinism suite's third positional (a pre-built signer) is
  accepted as a documented seam and used only to scope the wrap cache, so all
  24 determinism/spec tests run unmodified against an env-only production path
  (`_signer_cache_identity` now handles a `str` signer and `client_pubkey`, and
  the cache identity is taken from the *KeyMaterial* when present, so a fresh
  SDK signer object cannot defeat the cache). ADR §2.3/§2.3.1 document exactly
  this `build_gift_wrap(payload, tx_npub, signer)` shape.
* `cvm_armed_publisher.py`, `relay_testkit.py`, `Makefile`, `PROGRESS.md`,
  `REPORT.md` — union/adapters; the Makefile target is the union of both sides'
  curated lists (nothing removed).
* kind-1059 + plaintext-leak guard preserved (`test_nostr_giftwrap.py`, incl.
  the real-Tag regression test, all green).

## 3. #28 vs #32 reconciliation decision

**Decision: fold `882184ec` as a curated commit, do not add a second module.**
`keymaterial.py` is **subsumed** by the base in every respect that matters —
same single accessor, a *stricter* invariant (construction-time
`KeyCollisionError` instead of a separate `assert_keys_differ` call), plus
`MissingKeyError`/redacted `repr`, and the base ships its own broader
`test_keymaterial.py` (31 tests). Adding #28's module would duplicate the API.

**But #28 was not *fully* subsumed.** Evidence, reproduced before the fix:

```
$ CVM_RX_NSEC=… CVM_SERVER_HEX=… python3 -c 'import keymaterial; keymaterial.load_keys()'
keymaterial.MissingKeyError: E80_CLIENT_NSEC or E80_CLIENT_HEXKEY is not set
```

`cvm_armed_publisher.run()` resolves its keys through `keymaterial.load_keys()`
(the base's chosen design), while ADR `docs/ADR-range-sync-cvm.md` §2.3 and
`docs/RANGE-TEST-GUIDE.md` (lines 661, 703) document `CVM_RX_NSEC`/`CVM_SERVER_HEX`
as the operator interface. So the *documented* invocation of the very publisher
this PR ships could not start. `882184ec`'s accessor read the `CVM_*` names; the
base lost that.

Kept, as adapters on the base module (commit `5ba7b79`) — one module, no
duplicate API:

* every logical key resolves from an ordered name tuple: canonical `CVM_*`
  first, then `CVM_CLIENT_*`, then the `E80_*` names the base already accepted;
  the canonical name wins when several are set (per the ADR), and a blank value
  never shadows a real alias;
* `load_keys(client_names=…, client_hex_names=…)` selects the role's names —
  default is the RX/publish set, `cvm_tx_listener.load_and_check_keys()` passes
  the TX set, so the guide's `CVM_TX_*`-only environment resolves **and** a host
  exporting both roles can never sign TX traffic with the RX key;
* the missing-key message names the canonical names *and* every accepted alias;
* the base's `KeyCollisionError`-at-construction invariant is untouched.

`assert_keys_differ()`/`EnvKeyError` were **not** re-added: the base already
covers both (`KeyCollisionError` at construction, `MissingKeyError`), and the
existing `cvm_tx_listener` shims still expose those names as aliases.

## 4. Other reconciliation decisions

* **`tools/conftest.py` (new).** A ~25-line `pytest_pyfunc_call` hook runs
  coroutine test functions with `asyncio.run`, so the #34 spec suite runs under
  plain pytest. If `pytest-asyncio` is installed it registers the same
  first-result hook and wins; the tests run exactly once either way. Chosen over
  installing an undeclared plugin. `pytest.ini` registers the `asyncio` marker
  so the run is warning-free.
* **`tools/nostr_giftwrap.py` (fix `d339bd5`).** The merge's live
  `UnboundLocalError` fixed by ordering signer/keys resolution and deriving the
  cache identity *before* the cache lookup; the signer object is only built on a
  cache miss. Production callers pass `keys=` or nothing.
* **`Makefile` (fix `9cb4545`).** Curated target extended with the relay
  family's four test files (`test_relay_testkit.py`,
  `test_relay_failover_publisher.py`, `test_fake_relay_transport.py`,
  `test_failover_relays_constant.py`) so the PR's own entry point collects
  everything the fold brings. Union with #28's `test_keymaterial.py` line, no
  test removed.

## 5. Verification (verbatim)

```
$ cd firmware/e80-stm32-bench/tools && python3 -m pytest . -q -p no:cacheprovider
1114 passed, 9 skipped in 40.24s

$ cd firmware/e80-stm32-bench && make range-test-host
413 passed, 1 skipped, 19 subtests passed in 34.76s

$ cd <worktree root> && python3 -m pytest tests/ -q --continue-on-collection-errors
566 passed, 37 skipped, 0 collection errors
```

Before this run the same `tools/` suite was **1070 passed / 33 failed** —
the 33 failures were the gift-wrap `UnboundLocalError` plus the 14 unrunnable
async spec tests. Nothing is blamed on pre-existing failures: `origin/main` was
not used for a baseline blame because every failure was reproduced and fixed
here.

New test files brought in by the stack (13, all collected, all passing):

```
test_cvm_armed_publisher.py      test_keymaterial.py
test_cvm_tx_listener.py          test_nostr_giftwrap.py
test_cvm_verdict_publisher.py    test_nostr_giftwrap_realsdk.py  (skips w/o SDK)
test_failover_relays_constant.py test_relay_failover_publisher.py
test_fake_relay_transport.py     test_relay_testkit.py
test_giftwrap_determinism.py     test_rx_armed_publisher.py
test_giftwrap_determinism_spec.py
```

Tests added by this run: 11 in `test_keymaterial.py` (name precedence, aliases,
canonical-wins, blank-shadowing, message completeness, accessor/message-layer
drift guard) and 2 in `test_cvm_tx_listener.py` (the TX role's name set through
the accessor, and RX/TX role separation).

## 6. Commits pushed (branch `pr/e80-cvm-consolidated`)

```
4a39746 docs(progress): record the key-interface reconciliation
5ba7b79 fix(e80-cvm): the key accessor must accept the documented CVM_* env names
9cb4545 chore(e80): collect the folded relay-family tests in the curated range-test-host run
d339bd5 fix(e80-cvm): reconcile the t_c4c43d76 signer seam with t_4c98fbe7's env-only keys
459df15 chore(e80-cvm): curate test_keymaterial.py into the range-test-host target
1d38c4f refactor(e80): single-source FAILOVER_RELAYS as bare hostnames
33f60c6 feat(e80): split hard-error flavours, add attempts/reset + no-network pin …
87bfe1c feat(e80): relay fan-out scaffolding - exact relay set, dead-host absence test …
6e07f60 feat(e80): deterministic relay-failover kind-1059 publisher + tests (t_120db4f6)
e1e66c1 test(e80-cvm): hermetic spec-conformance suite for gift-wrap determinism
c38f0fd docs(e80-cvm): document gift-wrap wrap-cache lifetime/eviction policy
0f758a5 docs(e80-cvm): add GIFTWRAP_DETERMINISM.md …
5a29106 feat(e80-cvm): deterministic, idempotent NIP-59 gift-wrap events (t_c4c43d76)
+ the 12 vehicle (#32) commits, a45490c … 9204759
```

`git status --short` is empty; the branch is at `origin/pr/e80-cvm-consolidated`.

## 7. Ship state

* PR: **one** consolidated PR → `main` (see the PR body for the fold table,
  the #28/#32 decision and the test counts).
* Superseded PRs closed with a cross-reference: **#26, #27, #28, #29, #30, #31,
  #33, #34** — and **#32 as well**, because the new branch carries every #32
  commit. Evidence: `git cherry HEAD origin/pr/keymaterial-env-sole-source`
  reports exactly one '+' row, `2aa55cbb` (#27's gift-wrap builder), whose
  content *is* in HEAD but whose patch differs because the base's own
  `91952be` rewrote those lines in place (the kind-1059/plaintext guard and its
  real-`Tag` regression test both pass here); the branch is based on
  `origin/main` (`git merge-base --is-ancestor origin/main HEAD`, exit 0).
* Nothing merged to `main`; #35/#43 untouched; `wt/t_0049ed58-rxarmed` untouched;
  no force-push to any other branch.
