# GATE25-R1R — PROGRESS

Task: re-review phase-1 after R1 hardening + consolidation. Emit APPROVE/REVISE.
Repo: balloon-e80bench  Reviewed SHA: 086c11a79c53f3ee05bce53fb1700d8f7dbae486
Ref reviewed: `origin/pr/e80-cvm-consolidated` (= the brief's phase-1 stack; the briefed
name `pr/e80-cvm-p1-phase1` does NOT exist on any remote and t_3253903d is not on board
`e80-bench`/`balloon` — the actual consolidated stack is `pr/e80-cvm-consolidated` @ 086c11a,
which contains the R1 fix 37181f3 and both source branches' content).

## Finding -> status -> files touched

| # | Check | Status | Evidence |
|---|-------|--------|----------|
| 1 | R1(a) absent created_at -> reject | PASS | probe: (False,'missing required field: created_at') x2 |
| 1 | R1(b) malformed created_at -> reject, no exception | PASS | probe: 7 malformed types all (False,'bad created_at: ...') |
| 1 | R1(c) non-allowlisted author -> reject BEFORE parse | PASS | probe: reason='author not in allowlist', no exception |
| 1 | A1 generate_session_id CSPRNG + shape | PASS | probe: matches ^\d{10}[0-9a-f]{3}$, secrets.randbelow, no randrange |
| 2 | no plaintext kind 30315 | PASS | nostr_giftwrap PlaintextKindError; AST guards in tests |
| 2 | session authority RX-only | PASS | gen_session_id only in cvm_sync+cvm_armed_publisher; TX validates only |
| 2 | keys env-only + client!=server gate | PASS | probe: KeyCollisionError on same key; MissingKeyError naming var |
| 2 | 60s skew / 30s stale exactly | PASS | MAX_CREATED_AT_SKEW=60.0, STALE_ABORT=30.0 |
| 2 | relay set = mandated 5, no relay.contextvm.org | PASS | probe: all 3 relay lists == mandated set |
| 2 | verdict publisher config-end granularity | PASS | one verdict per config scan; per_config rows inside |
| 3 | consolidation faithful (both branches, no dropped test) | PASS | verdict files byte-identical to a353fd98; tx_listener evolved |
| 3 | no conflict markers / no doc+Makefile conflict | PASS | git grep for markers: empty |
| 4 | TDD RED-then-GREEN | PASS | RED 20 failed/6 passed vs 37181f3^; GREEN 48/48 |
| 5 | full suite green | PASS | 184 passed |

## Files touched
- REPORT.md (this review's full report — read-only review, no source files modified)
- PROGRESS.md (this file)
- /home/c03rad0r/reports/reviews/e80-cvm-p1-gate25-rerreview-t_e70f2d0a.json (verdict)

## Verdict
APPROVE
