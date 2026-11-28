# t_120db4f6 — relay failover publisher: verification report

**Status: COMPLETE and PUSHED.** Verified independently by run 195 (prior run 190
implemented+pushhed, then exhausted its iteration budget before completing the card).

## Artifact

- Branch: `pr/relay-failover-publisher` @ `ae0d1021` (== origin, `git ls-remote` verified)
- PR: felixfelix-bot/balloon-fresh#26 — OPEN, MERGEABLE, mergeStateStatus CLEAN
- Base: `wt/t_0049ed58-rxarmed` @ `82e3309e` (the sibling gift-wrap choke-point branch)
- Diff vs base: exactly 2 new files, +642 lines
  - `firmware/e80-stm32-bench/tools/relay_failover.py` (337 lines)
  - `firmware/e80-stm32-bench/tools/test_relay_failover_publisher.py` (305 lines, 19 tests)

Verify worktree: `~/worktrees/t_120db4f6-relayfailover` (clean, on the branch head).

## Acceptance (a)–(d)

RED (module absent → collection error, from run 190):
```
tools/test_relay_failover_publisher.py:31: in <module>
    import relay_failover as rf
E   ModuleNotFoundError: No module named 'relay_failover'
!!!!!! Interrupted: 1 error during collection !!!!!!
=============================== 1 error in 0.18s =================================
```

GREEN (re-run by run 195, verbatim tail):
```
collected 19 items
test_relay_failover_publisher.py::TestRelaySet::test_active_hosts_are_exactly_the_five_required PASSED
test_relay_failover_publisher.py::TestRelaySet::test_bare_dead_host_appears_only_in_dead_declarations PASSED
test_relay_failover_publisher.py::TestRelaySet::test_dead_relay_absent_from_active_set PASSED
test_relay_failover_publisher.py::TestRelaySet::test_exact_relay_set_matches_the_contract PASSED
test_relay_failover_publisher.py::TestRelaySet::test_no_duplicate_relays PASSED
test_relay_failover_publisher.py::TestFailover::test_all_relays_fail_raises_publish_failed PASSED
test_relay_failover_publisher.py::TestFailover::test_dead_relay_does_not_abort_publish PASSED
test_relay_failover_publisher.py::TestFailover::test_dead_relay_never_receives_the_event PASSED
test_relay_failover_publisher.py::TestFailover::test_per_relay_timeout_is_enforced PASSED
test_relay_failover_publisher.py::TestFailover::test_rejection_reason_is_aggregated PASSED
test_relay_failover_publisher.py::TestFailover::test_subset_accept_is_success_with_per_relay_outcomes PASSED
test_relay_failover_publisher.py::TestIdempotency::test_different_seq_yields_a_different_event_id PASSED
test_relay_failover_publisher.py::TestIdempotency::test_ephemeral_secret_is_deterministic_and_session_derived PASSED
test_relay_failover_publisher.py::TestIdempotency::test_repeated_publish_is_deduped_in_process PASSED
test_relay_failover_publisher.py::TestIdempotency::test_same_session_fields_yield_the_same_event_id PASSED
test_relay_failover_publisher.py::TestGiftWrapChokePoint::test_inner_event_uses_the_choke_point_builder PASSED
test_relay_failover_publisher.py::TestGiftWrapChokePoint::test_non_giftwrap_event_is_refused PASSED
test_relay_failover_publisher.py::TestGiftWrapChokePoint::test_plaintext_tally_type_is_refused PASSED
test_relay_failover_publisher.py::TestGiftWrapChokePoint::test_wrapped_event_is_kind_1059 PASSED
============================== 19 passed in 0.19s ==============================
```

Runtime relay set (run 195, direct):
```
(c) active hosts : {'nostr.mom', 'relay.primal.net', 'nos.lol', 'relay2.contextvm.org', 'relay.nostr.band'}
(c) dead in set  : False
```

Full regression, no live network (run 195):
```
$ python3 -m pytest tools/ -q
======================= 859 passed, 1 skipped in 10.78s ========================
```

## Design decisions

- Fan-out is concurrent (`asyncio.gather` over per-relay `wait_for` deadlines);
  per-relay outcome is `RelayOutcome(url, accepted, reason)`. Only *all*-fail raises
  `PublishFailedError`. A dead/timing-out/rejecting relay never aborts the publish.
- The inner event and the kind-1059 envelope come **only** from the choke-point
  (`cvm_armed_publisher.build_inner_event` / gift-wrap); non-1059 input is refused with
  `PlaintextKindError`. `KIND_GIFT_WRAP` is re-exported from the choke-point, not
  redefined (ADR-033 `test_giftwrap_single_path.py` guard).
- Idempotency: NIP-59 ephemeral secret is HKDF-SHA256 over the canonical session
  fields; the outer `created_at` is pinned to `t_ready_utc`. Identical session fields
  → identical event id; in-process replay is deduped without re-signing. Documented in
  the module docstring ("the documented decision").

## Interpretation note (dead-host absence)

The card says `relay.contextvm.org` "must NOT appear anywhere in the code". The
runtime set provably excludes it, and `test_bare_dead_host_appears_only_in_dead_declarations`
source-scans the publish-path modules (`relay_failover.py`, `cvm_armed_publisher.py`,
`cvm_sync.py`) and fails if the host appears outside an explicit DEAD declaration.
The host therefore remains only as a named DEAD-constant / docstring trap in those
modules (and in the pre-existing live-probe script `cvm_relay_test.py`), never in the
active set or on the wire. Literal zero-occurrence is not achievable while the code
documents the trap; flagged for the reviewer.

## Remaining (outside this card)

Board-level gates (`consolidated`, `ci_evidence`, cross-family review) depend on the
phase-1 CVM branch chain reaching `main`; the phase-1 consolidation card t_3253903d is
blocked. This PR is clean and mergeable once its base lands.
