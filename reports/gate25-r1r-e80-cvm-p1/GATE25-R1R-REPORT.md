# GATE25-R1R — Gate 2.5 cross-family cold re-review: E80-CVM-P1 (after R1 + consolidation)

- Verdict: **APPROVE**
- Repo: `/home/c03rad0r/repos/balloon-e80bench`
- Reviewed ref/SHA: `origin/pr/e80-cvm-consolidated` @ `086c11a79c53f3ee05bce53fb1700d8f7dbae486`
- Review worktree (read-only): `/home/c03rad0r/worktrees/e80-cvm-p1-rereview` (detached at the SHA)
- Mode: read-only. No repo source files modified. The only writes are PROGRESS.md, REPORT.md
  and the verdict JSON in the review worktree / home reports dir.
- Prior round: REVISE (R1 blocking). This round re-verifies R1 + the original PASS items +
  consolidation fidelity + TDD + full-suite green.

## 0. Scope note — the briefed branch name does not exist

The brief names branch `pr/e80-cvm-p1-phase1` and tasks `t_3253903d` / `t_cdcf6d90` / `t_e70f2d0a`.
None of those resolve in this repo/board:

- `git ls-remote origin | grep -i phase1` → no `pr/e80-cvm-p1-phase1` ref on origin/github/ngit.
- `hermes kanban --board e80-bench show t_3253903d` → `no such task` (also absent on `balloon`).
- The prior verdict file `/home/c03rad0r/reports/reviews/e80-cvm-p1-gate25-cold-review-t_e70f2d0a.json`
  does not exist on disk (nothing matching `*e80-cvm-p1*gate25*` or `*t_e70f2d0a*` anywhere under
  `/home/c03rad0r`).

I therefore reviewed the **actual phase-1 consolidated stack**: `pr/e80-cvm-consolidated`, whose tip
`086c11a` is the merge target of PR #44 (`3020f0b Merge pull request #44 from
felixfelix-bot/pr/e80-cvm-consolidated`) and which **contains the R1 fix commit `37181f3`** plus every
source-branch artifact the brief names. This is the correct object to review; the branch-name
mismatch is reported, not treated as a finding against the work.

## 1. R1 closures — reproduced behaviorally at the reviewed SHA (not by reading the diff)

Probe `_probe_r1.py` (throwaway; imported `tools/cvm_sync.py` and drove it; file deleted after use).
`NOW=1788096000`, `ALLOWED={'aa'*32}`.

### R1(a) absent `created_at` → reject (allowlist given OR None)
```
absent created_at, allowlist=ALLOWED   -> (False, 'missing required field: created_at')   (no exception)
absent created_at, allowlist=None      -> (False, 'missing required field: created_at')   (no exception)
```
`created_at` is now in `ARMED_REQUIRED` (`tools/cvm_sync.py:85-86`), so the structural loop at
`tools/cvm_sync.py:196-198` rejects it. The pre-fix guard `if created is not None`
(`37181f3^:cvm_sync.py`) is gone.

### R1(b) malformed `created_at` → reject with NO exception
```
'not-a-number'  -> (False, "bad created_at: 'not-a-number'")
None            -> (False, 'bad created_at: None')
1.5             -> (False, 'bad created_at: 1.5')
True            -> (False, 'bad created_at: True')      # bool explicitly rejected
[1]             -> (False, 'bad created_at: [1]')
{'x': 1}        -> (False, 'bad created_at: {'x': 1}')
<object ...>    -> (False, 'bad created_at: <object object at 0x...>')
```
Strict typing at `tools/cvm_sync.py:206-207`: `isinstance(created, bool) or not isinstance(created,
int)` — no `int()` cast, so nothing hostile can raise. Every case returns `(False, reason)`.

### R1(c) non-allowlisted author → reject by allowlist BEFORE any `created_at` parse
```
non-allowlisted author + malformed created_at -> (False, 'author not in allowlist: cccccccccccccccc')  (no exception)
reason names allowlist, not created_at: True
non-allowlisted author + valid created_at     -> (False, 'author not in allowlist: cccccccccccccccc')
```
Authz runs at `tools/cvm_sync.py:200-203`, strictly before the freshness block at 204-207 — the
attacker-controlled `created_at` is never parsed for a rejected identity.

### Control
```
valid ARMED, allowlist=ALLOWED -> (True, '')      (no false rejection)
valid ARMED, allowlist=None    -> (True, '')
```

### A1 — `generate_session_id` twin hardened
```
cvm_sync id          : 2608301320dd1   matches ^\d{10}[0-9a-f]{3}$: True
prefix == %y%m%d%H%M : True            suffix == 3-hex nonce: True
source has 'random.randrange': False   source has 'secrets.randbelow': True
```
`tools/cvm_sync.py:93-116` uses `secrets.randbelow(0x1000)` + `urllib.parse.quote(..., safe="")`,
matching `cvm_armed_publisher.generate_session_id`.

## 2. No regression of the original PASS items

| Item | Evidence |
|------|----------|
| No plaintext kind-30315 emission | `nostr_giftwrap.py:130-134,548-563` — `KIND_PLAINTEXT_TALLY=30315` is the FORBIDDEN constant; `PlaintextKindError` on any non-1059 kind. AST guards in `test_cvm_armed_publisher.py:316-321` and `test_cvm_verdict_publisher.py:446-449` assert no module authors the literal. |
| Session authority RX-only | `generate_session_id` is defined ONLY in `cvm_sync.py:102` and `cvm_armed_publisher.py:146`. `cvm_tx_listener.py` has no `generate_session_id`; it validates the id (`validate_session_id` at :119-122) and echoes it. |
| Keys env-only + client!=server gate | `keymaterial.load_keys` (`keymaterial.py:401-461`) reads `os.environ` only. Probe: same key both roles → `KeyCollisionError: client key and server key resolve to the same pubkey ...; refusing to publish`; absent key → `MissingKeyError` naming the variable. Passed clients: `cvm_armed_publisher.py:11`, `cvm_verdict_publisher.py:421`. |
| 60 s skew / 30 s stale exactly | `cvm_sync.py:76-77` `MAX_CREATED_AT_SKEW=60.0`, `STALE_ABORT=30.0`; `cvm_tx_listener.py:79-80` aliases them (single source of truth). |
| Relay set = mandated 5, `relay.contextvm.org` absent | Probe: `cvm_sync.DEFAULT_RELAYS`, `cvm_tx_listener.FAILOVER_RELAYS`, `cvm_armed_publisher.FAILOVER_RELAYS` and `FAILOVER_RELAY_URLS` all == `{nostr.mom, relay.primal.net, nos.lol, relay2.contextvm.org, relay.nostr.band}`; `relay.contextvm.org` present in none (only in `DEAD_RELAYS`, asserted absent). |
| Verdict publisher config-end granularity | `cvm_verdict_publisher.py:12-16` one verdict per completed config scan (never per packet); `per_config` rows + counts travel inside the single message; `validate_verdict` (:229-247) enforces one object per config. |

## 3. Consolidation fidelity (both source branches merged; no dropped test; no conflict markers)

- `a353fd98` (`wt/t_49192514-verdict`) adds 4 files — `cvm_armed_publisher.py`,
  `cvm_verdict_publisher.py`, `test_cvm_armed_publisher.py`, `test_cvm_verdict_publisher.py` — ALL
  PRESENT at tip `086c11a`.
- `d30a0d6f` (`feat/cvm-tx-listener`) adds 2 files — `cvm_tx_listener.py`,
  `test_cvm_tx_listener.py` — BOTH PRESENT at tip.
- **Byte-identity check**: `git rev-parse a353fd98:<verdict publisher> 086c11a:<same>` are equal
  (`e624445e…` and `1faadeb9…`) — the verdict publisher + its test landed verbatim from a353fd98.
- **No dropped test file**: all 34 `test_*.py` files on `a353fd98` exist at the tip (missing=0).
- **Evolution (not a silent drop)** on the tx-listener lane: tip folds the key taxonomy into
  `keymaterial.py` (`EnvKeyError = keymaterial.MissingKeyError`,
  `load_keys = keymaterial.load_keys`) and aligns `ARMED_FIELDS` to drop the now-duplicate
  `created_at` — the A1/R1 delta, consistent with commit `37181f3`'s message.
- **No conflict markers**: `git grep -nE '^(<<<<<<< |=======$|>>>>>>> )' 086c11a --
  firmware/e80-stm32-bench/` is EMPTY; Makefile diff adds none. `Makefile:660-662` wires all five
  cvm/giftwrap test files into the curated suite — no dropped Makefile target.

## 4. TDD — RED-then-GREEN observed

New classes `TestValidateArmedStrictCreatedAt` (`test_cvm_sync.py:449`) and `TestSessionIdHardening`
(`:574`). RED against the pre-fix module (`37181f3^:firmware/e80-stm32-bench/tools/cvm_sync.py`):

```
20 failed, 6 passed, 31 deselected in 2.94s
FAILED ...::test_created_at_is_a_required_field
FAILED ...::test_malformed_created_at_rejected_without_raising  (SUBFAILED for 9 created_at kinds)
FAILED ...::test_allowlist_runs_before_created_at_parsing
FAILED ...::TestSessionIdHardening::test_nonce_does_not_use_the_random_module
FAILED ...::TestSessionIdHardening::test_parity_with_armed_publisher
...
```
This matches the fix commit's own claim ("observed RED … 20 failed, 37 passed … 48 passed after").
The tip module was restored immediately (`git diff --stat tools/cvm_sync.py` → empty) and GREEN
re-confirmed.

## 5. Full suite green (mandated command)

```
$ cd firmware/e80-stm32-bench && PYTHONDONTWRITEBYTECODE=1 python3 -m pytest \
    tools/test_cvm_sync.py tools/test_cvm_armed_publisher.py \
    tools/test_cvm_verdict_publisher.py tools/test_cvm_tx_listener.py \
    tools/test_giftwrap_single_path.py -q -p no:cacheprovider
184 passed in 4.43s
```
(Re-run after the RED probe restore: 184 passed in 33.93s.)

## Verdict JSON

```json
{
  "verdict": "APPROVE",
  "reviewed_sha": "086c11a79c53f3ee05bce53fb1700d8f7dbae486",
  "reviewed_branch": "origin/pr/e80-cvm-consolidated",
  "briefed_branch_name": "pr/e80-cvm-p1-phase1",
  "briefed_branch_exists": false,
  "issues": [],
  "notes": [
    "R1(a)/(b)/(c) closed and reproduced behaviorally at 086c11a.",
    "A1 session-id twin hardened (secrets.randbelow + percent-encoded timestamp).",
    "No regression of any original PASS item.",
    "Consolidation faithful: verdict files byte-identical to a353fd98; both source branches present; no dropped test file; no conflict markers.",
    "TDD RED (20 failed/6 passed vs 37181f3^) -> GREEN (48/48) observed; full suite 184 passed.",
    "Scope note: briefed branch pr/e80-cvm-p1-phase1 and tasks t_3253903d/t_cdcf6d90/t_e70f2d0a do not resolve; reviewed the actual consolidated stack pr/e80-cvm-consolidated @ 086c11a which contains R1 37181f3."
  ]
}
```
