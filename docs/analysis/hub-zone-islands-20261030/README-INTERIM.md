# Zone-island attribution — INTERIM, NOT A DELIVERABLE

**Status: INCOMPLETE. Do not cite. Do not merge as evidence.**
Branch `pr/hub-zone-islands-20261030` off `12537537`. Source board unchanged
(sha256 `732bfe889020b3c9…`, matches the audit baseline).

This directory is committed only so the negative results below survive the
session. `ledger2.json` and `attribute.py` are **known-wrong** and must be
rewritten.

## What was established (and is trustworthy)

### 1. The task's specified API path exists — it was found late

`CONNECTIVITY_DATA` exposes **40** methods (`probe_cd.py`). The entry points the
task named are real:

- `GetConnectedItems`
- `GetConnectedItemsAtAnchor`
- `FillIsolatedIslandsMap`
- `GetRatsnestForNet`
- `GetUnconnectedCount`

An earlier probe in this session recorded `RunOnUnconnectedEdges`,
`GetConnectedPads`, `GetConnectedTracks`, `IsConnected` as **unbound**. Those
negative results stand — but they were the wrong entry points, so they do not
justify abandoning the approach.

### 2. Zone decomposition resolves islands correctly, but only as SETS

Method A (isolate one zone, let DRC name the island) gives island-specific
positions where the base board reports only the outline anchor `(0.45, 0.45)`:

- record 7 → `P3V3_BCu__ISL2@(19.357, 4.251)` + `ISL0@(11.933, 11.215)`
- record 59 → `GND_FCu__ISL1` + `GND_BCu__ISL6`

Copper preserved byte-identically (`refill_is_byte_noop`; source sha256
unchanged).

### 3. BLOCKING: DRC record identity is NOT deterministic on identical bytes

Five DRC runs over the same board bytes, including single-threaded
(`taskset -c 0 OMP_NUM_THREADS=1`):

| run | records | index-wise equality vs run 1 |
|---|---:|---|
| 1 | 86 | 86/86 |
| 2 | 86 | 72/86 |
| 3 | 86 | 76/86 |
| 4 | 86 | 80/86 |
| 5 | 86 | — |

**86 records every time**, but only **65 distinct item-signatures**.

The set of 86 records is a **spanning forest**. The *components* are stable; *which
edge DRC names as closing each component* is not. Consequence: pairing
decomposition results to ledger1 IDs **by list index is invalid**, and
`attribute.py` does exactly that. Its output (75 REQUIRED / 11 EXTERNAL / 0
UNKNOWN) is built on that bad pairing and **must not be trusted**.

This also means every future DRC diff in this repo that compares record lists by
index is unsound — compare the component partition, or compare counts plus
signatures as a multiset.

### 4. The independent graph (Method B) is wrong, and why

`GeoGraph` unions only within `(layer, net)`, so a via or PTH pad never bridges
its `F.Cu` node to its `B.Cu` node:

- no via/PTH bridges → 408 components, Σ(comps−1) = 354
- with via/PTH bridges → 203 components, Σ = 149
- DRC says **86**

Still over-splitting. The correctness gate for Method B is
**Σ(comps−1) == 86**; until that holds it cannot corroborate Method A.

### 5. Two records are genuinely pinnable

Records **82** and **83** pair a zone with a *concrete pad* (`U_LORA1280` pad 14;
`J_HUB_PV` PTH pad 5), so their non-zone endpoint is deterministic without any
island ambiguity.

## Citations checked in-repo

- **ADR-136 §2.1** — `J_W` pad 2 unused on the flight build.
- **ADR-136 §2.2** — cut-sense DNP.
- **ADR-140 D3** — only the nine U1 ↔ `U_LORA1280` paths are proven.
- `Wing_Tab_4P` reuses the same pad number on `F.Cu` and `B.Cu`.

**Counter-citation that must be resolved, not ignored:**
`docs/fab/HUB-V9-ORDER-READINESS.md` treats this same discontinuity as copper
that should be **stitched**. So any EXTERNAL ruling here is
**documentation-based, not measurement-based**, and the two records disagree.
An ADR has to name the winner before any of these 27 records is waived.

## What remains (numbered, for the next attempt)

1. Probe `GetConnectedItems` / `FillIsolatedIslandsMap` — the method the task
   actually specified, and the one most likely to give per-record answers.
2. Fix the graph's layer bridging until **Σ(comps−1) == 86**. That is the gate;
   do not report graph output before it holds.
3. Key the ledger on **content** (zone/layer pair + item UUIDs), never list
   index. Where a base signature is ambiguous — the
   `GND_BCu@B.Cu, GND_FCu@F.Cu` group covers **13 records** — assign the whole
   island partition to the group rather than inventing a per-record mapping.
4. Rewrite `attribute.py` accordingly; regenerate `ledger2.json`.
5. Only then write the report, commit, and open a PR.

## The honest headline

Island attribution **is** resolvable. Per-record attribution for the 25
zone↔zone records is blocked by DRC non-determinism, and the correct response is
to **report at group granularity** — not to invent an ordering that the checker
does not provide.

## Files

- `run_zone_islands.py` — phasic pipeline (refill / decompose / verify / drc);
  runs clean, exit 0. Keep.
- `attribute.py` — **INVALID index pairing. Rewrite before use.**
- `ledger2.json` — **PROVISIONAL. Do not cite or merge.**
