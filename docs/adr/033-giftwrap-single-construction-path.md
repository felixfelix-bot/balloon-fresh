# ADR-033 — Gift-wrap construction has one canonical primitive

- Status: **Proposed** (2026-10-06). Recorded during the consolidation pass;
  the text has not been accepted by a human. Acceptance is a human action and
  must name the authoriser and the date.
- Date: 2026-10-06
- Decision owner: Felix (operator)
- Author: Hermes agent (consolidation pass)
- Related: `docs/RECON-duplicate-giftwrap-paths.md`,
  `docs/RECON-cfg-gated-wrap-paths.md`,
  `docs/RECON-lane-B-plaintext-fallback-paths.md`, ADR-008 (telemetry protocol),
  ADR-022 (mandatory test coverage)
- Related artefacts:
  `firmware/e80-stm32-bench/tools/test_giftwrap_single_path.py` (the pinning
  test), `docs/SECURITY-FINDINGS.md` (bypass channel tracked separately, #21)

---

## Context

Adversarial recon (original 2026-09-28; re-verified 2026-10-06 against trunk
`e7ec2d0`) tested three claims about the NIP-59 gift-wrap used by the CVM
transport:

1. **"Exactly one construction path to a kind-1059 event exists."** FALSIFIED
   in its literal form. Against current trunk there are four non-test emit
   sites, all calling the same upstream primitive: `cvm_board_server.py:580`,
   `cvm_campaign.py:179` and `:208`, `cvm_relay_test.py:82` (plus one test
   site, `test_cvm_board_server.py:477`).
2. **"No cfg/feature/env-gated alternate construction path exists."** No gated
   *construction* path found, but a live gated **bypass** exists: an
   unauthenticated, all-interfaces TCP board-control channel
   (`e80_board_server.py:221,417`, `0.0.0.0:7780`). That is a control-plane
   issue, not a wrap-construction issue; tracked in issue #21.
3. **"No plaintext / kind-1 fallback bypass exists."** True for the in-scope
   code: every emission is the output of `nostr_sdk.gift_wrap(...)`, and the
   publish API is type-gated.

Additional facts re-verified against `e7ec2d0`:

- The outer kind-1059 constructor is always the upstream FFI call
  `nostr_sdk.gift_wrap(...)`; no in-scope file hand-rolls an outer event (no
  `EventBuilder` / `Event.new` / `build_event` / `create_event`).
- The unused, seal-based entry point `nostr_sdk.gift_wrap_from_seal` is not
  referenced anywhere in `tools/` — a latent second path that is one import
  away from becoming real.
- `KIND_GIFT_WRAP = 1059` is authored independently in **three** modules
  (`cvm_board_server.py:74`, `cvm_campaign.py:64`, `cvm_sync.py:68`); none
  imports it from another. Drift-ready duplication.

## Decision

1. `nostr_sdk.gift_wrap(...)` is the **only** permitted construction of a
   kind-1059 event. Hand-rolling a kind-1059 event, or publishing a pre-built
   kind-1059 object supplied by a caller, is prohibited.
2. `nostr_sdk.gift_wrap_from_seal(...)` must not be used without a superseding
   ADR. It is the seam a second seal+wrap path would use.
3. The construction/unwrap surface and the set of `KIND_GIFT_WRAP` definition
   sites are pinned by
   `firmware/e80-stm32-bench/tools/test_giftwrap_single_path.py`. Adding a call
   site or a new constant definition requires updating this ADR and the test in
   the same change.
4. Security recon for this subsystem is public by design. Findings live in
   `docs/` and are enforced by tests, not left as prose.

## Consequences

- A second wrap-construction path cannot be introduced silently: any `pytest`
  run of the tools suite fails on a changed surface.
- The pin is an AST guard: it counts sites and definitions rather than pinning
  line numbers, so ordinary edits do not trip it while a new site does.
- The three duplicate `KIND_GIFT_WRAP` definitions are tolerated for now and
  enumerated explicitly; consolidating them to one module is a separate,
  non-blocking follow-up.
- The unauthenticated TCP control channel is explicitly **out of scope** for
  this ADR and handled under issue #21.
