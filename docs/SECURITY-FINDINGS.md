# Security findings — e80 bench tooling

Public-by-design register for the adversarial recon pass (original 2026-09-28,
re-verified 2026-10-06 against trunk `e7ec2d0`). The gift-wrap construction
guarantee itself is recorded and enforced separately in
[`docs/adr/033-giftwrap-single-construction-path.md`](adr/033-giftwrap-single-construction-path.md).

| ID | Finding | Class | Severity | Where | Status |
|----|---------|-------|----------|-------|--------|
| E80-2026-01 | Unauthenticated, all-interfaces TCP board-control channel | control-plane bypass | medium (network-bounded) | `firmware/e80-stm32-bench/tools/e80_board_server.py:221,417` (`0.0.0.0:7780`), wired via `tools/Makefile` | **Open — tracked in #21** |
| E80-2026-02 | Literal kind-1 plaintext poster outside the CVM scope | out-of-scope plaintext emit | low | repo-root `tools/gh_ngit_watchdog.py:273,281,444,469,501` | Open, out of CVM scope |
| E80-2026-03 | `nostr-sdk` neither declared nor pinned though the wrap guarantee depends on it | supply-chain / reproducibility | low | absent from `pyproject.toml` / `uv.lock` | Open |

## E80-2026-01 — unauthenticated TCP board-control channel

`BoardTCPServer` binds `0.0.0.0:7780` with no token, key, or allow-list
(`C83`/`C84` in the lane-C recon) and is reachable via the secondary
`firmware/e80-stm32-bench/tools/Makefile` (`tx-server`/`rx-server`). It exposes
the same `BoardController` commands the gift-wrapped CVM channel protects, so
the wrap channel's authenticity/allow-list properties do not apply to this
path. It is **not** a kind-1059 construction bug — the wrap primitive is
unaffected (ADR-033) — but it is a second, unauthenticated control path.

Severity is bounded by network reachability (bench/host network). Mitigation
options and discussion: issue #21.

## Non-findings (re-verified)

- No plaintext / kind-1 fallback in `firmware/e80-stm32-bench/tools/`
  (`RECON-lane-B-plaintext-fallback-paths.md`).
- No cfg / feature / env-gated alternate gift-wrap *construction* path
  (`RECON-cfg-gated-wrap-paths.md`).
- `nostr_sdk.gift_wrap_from_seal` is unused (latent); pinned out by
  `firmware/e80-stm32-bench/tools/test_giftwrap_single_path.py` under ADR-033.
