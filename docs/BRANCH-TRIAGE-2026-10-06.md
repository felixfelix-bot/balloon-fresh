# Branch triage — balloon-fresh divergence from the consolidated trunk

Date: 2026-10-06 · trunk HEAD: `2c22d5811cfc` · repo: `felixfelix-bot/balloon-fresh`

## 1. What is already landed

- `main` and `master` are the **same commit** and both carry the consolidation (32 commits of previously-diverged branch work + the earlier 119). Verified by `git ls-remote`: both refs identical, and identical again after this triage round.
- 112 `archive/consolidate-2026-10-05/<branch>` tags preserve every branch tip that was moved, so nothing is lossy.
- Two zero-conflict branches merged in this round:
  - `pr/029-dual-band-flight-board` (+1) — FLRC throughput figure settled in the array-feasibility doc.
  - `worker-balloon/flrc-512b-audit` (+4) — the 2.6 Mbps claim is the **air rate, not goodput**; adds `tools/flrc_512b_throughput_audit.py` + its test + `docs/FLRC-512B-THROUGHPUT-AUDIT-2026-10-06.md`.

## 2. The 25 that disagree about code

Reproduce: `git merge-tree --write-tree --name-only HEAD <ref>` per branch (read-only; see `~/reports/balloon-consolidation/{triage.py,analyze.py}`).

Every branch has at least one commit the trunk does not have (`git cherry`: **0 obsolete branches**), so none of the 25 is a pure duplicate — but that does **not** mean each carries new work: for several the change is already on the trunk under a different commit.

- Conflicted files in total: **137** across 25 branches.
- Per-file three-way classification (`base`/`ours`/`theirs`): **COMPETING**=130, **BOTH-ADD**=4, **BRANCH-ONLY**=2, **BINARY**=1.
  `COMPETING` means both sides edited the same region — a union merge is **not** safe there.

| branch | tip | +commits | conflict files | recommendation |
|---|---|---|---|---|
| `balloon-mesh-wiring/radio-glue` | 2026-07-30 | 7 | 3 | [C6 nostr_store / mesh wiring component] `balloon-nostr/dev` carries a real `nostr_store` component change (+ `Kconfig.projbuild`/`app_main.cpp` absent on trunk). `balloon-tollgate-extract` and `balloon-mesh-wiring/radio-glue` are build-config only (CMakeLists/sdkconfig) — hand-merge the superset, do not union `sdkconfig` (key/value). One decision: is `nostr_store` on the trunk's current wisp-esp32 relay path or superseded by it? |
| `balloon-tollgate-extract` | 2026-07-30 | 2 | 2 | [C6 nostr_store / mesh wiring component] `balloon-nostr/dev` carries a real `nostr_store` component change (+ `Kconfig.projbuild`/`app_main.cpp` absent on trunk). `balloon-tollgate-extract` and `balloon-mesh-wiring/radio-glue` are build-config only (CMakeLists/sdkconfig) — hand-merge the superset, do not union `sdkconfig` (key/value). One decision: is `nostr_store` on the trunk's current wisp-esp32 relay path or superseded by it? |
| `balloon-circuit-design` | 2026-07-30 | 3 | 1 | DECISION — binary board artifact: pick the authoritative revision. |
| `phase1-interop-test` | 2026-08-01 | 8 | 6 | [C3 RP2040 / flrc-bench-espidf radio benches] NOT a free archive — an earlier 'already on the trunk' reading was a grep false positive (see section 4). Reverse-apply shows the branch carries changes the trunk lacks. One decision: is the RP2040/FLRC bench path still live (merge, tests after each) or retired (archive with an `archive/` tag)? |
| `speed-sustained-sweep` | 2026-08-05 | 22 | 10 | [C3 RP2040 / flrc-bench-espidf radio benches] NOT a free archive — an earlier 'already on the trunk' reading was a grep false positive (see section 4). Reverse-apply shows the branch carries changes the trunk lacks. One decision: is the RP2040/FLRC bench path still live (merge, tests after each) or retired (archive with an `archive/` tag)? |
| `balloon-nostr/dev` | 2026-08-05 | 5 | 9 | [C6 nostr_store / mesh wiring component] `balloon-nostr/dev` carries a real `nostr_store` component change (+ `Kconfig.projbuild`/`app_main.cpp` absent on trunk). `balloon-tollgate-extract` and `balloon-mesh-wiring/radio-glue` are build-config only (CMakeLists/sdkconfig) — hand-merge the superset, do not union `sdkconfig` (key/value). One decision: is `nostr_store` on the trunk's current wisp-esp32 relay path or superseded by it? |
| `balloon-tollgate/dev` | 2026-08-08 | 11 | 1 | [C6 nostr_store / mesh wiring component] `balloon-nostr/dev` carries a real `nostr_store` component change (+ `Kconfig.projbuild`/`app_main.cpp` absent on trunk). `balloon-tollgate-extract` and `balloon-mesh-wiring/radio-glue` are build-config only (CMakeLists/sdkconfig) — hand-merge the superset, do not union `sdkconfig` (key/value). One decision: is `nostr_store` on the trunk's current wisp-esp32 relay path or superseded by it? |
| `range-tests` | 2026-08-17 | 15 | 5 | [C3 RP2040 / flrc-bench-espidf radio benches] NOT a free archive — an earlier 'already on the trunk' reading was a grep false positive (see section 4). Reverse-apply shows the branch carries changes the trunk lacks. One decision: is the RP2040/FLRC bench path still live (merge, tests after each) or retired (archive with an `archive/` tag)? |
| `feat/e80-7-crc-logging` | 2026-08-20 | 1 | 8 | [C2 E80 STM32 bench firmware] FIX-T1..T7 + E80-7/SPI-bypass touch DIFFERENT functions of the same files (independent fixes); `feat/c3-harmonization` (23 files, 2026-08-25) is the wide/old one. Resolve: merge the FIX-T* set first, one at a time, running `firmware/e80-stm32-bench/tests` after each; then the features. One decision: is the STM32 bench firmware still live, or has the RP2040 path replaced it? |
| `feat/e80-spi-bypass` | 2026-08-20 | 10 | 8 | [C2 E80 STM32 bench firmware] FIX-T1..T7 + E80-7/SPI-bypass touch DIFFERENT functions of the same files (independent fixes); `feat/c3-harmonization` (23 files, 2026-08-25) is the wide/old one. Resolve: merge the FIX-T* set first, one at a time, running `firmware/e80-stm32-bench/tests` after each; then the features. One decision: is the STM32 bench firmware still live, or has the RP2040 path replaced it? |
| `fix/t1-sweep-start-validation` | 2026-08-21 | 2 | 3 | [C2 E80 STM32 bench firmware] FIX-T1..T7 + E80-7/SPI-bypass touch DIFFERENT functions of the same files (independent fixes); `feat/c3-harmonization` (23 files, 2026-08-25) is the wide/old one. Resolve: merge the FIX-T* set first, one at a time, running `firmware/e80-stm32-bench/tests` after each; then the features. One decision: is the STM32 bench firmware still live, or has the RP2040 path replaced it? |
| `fix/t3-flrc-match123` | 2026-08-21 | 2 | 2 | [C2 E80 STM32 bench firmware] FIX-T1..T7 + E80-7/SPI-bypass touch DIFFERENT functions of the same files (independent fixes); `feat/c3-harmonization` (23 files, 2026-08-25) is the wide/old one. Resolve: merge the FIX-T* set first, one at a time, running `firmware/e80-stm32-bench/tests` after each; then the features. One decision: is the STM32 bench firmware still live, or has the RP2040 path replaced it? |
| `fix/t2-rx-start-len-gate` | 2026-08-21 | 2 | 1 | MERGE NOW — 1 file, both sides insert, regions disjoint (BOTH-ADD); union is safe. |
| `fix/t4-fifo-clear` | 2026-08-22 | 4 | 3 | [C2 E80 STM32 bench firmware] FIX-T1..T7 + E80-7/SPI-bypass touch DIFFERENT functions of the same files (independent fixes); `feat/c3-harmonization` (23 files, 2026-08-25) is the wide/old one. Resolve: merge the FIX-T* set first, one at a time, running `firmware/e80-stm32-bench/tests` after each; then the features. One decision: is the STM32 bench firmware still live, or has the RP2040 path replaced it? |
| `feat/c3-harmonization` | 2026-08-25 | 2 | 23 | [C2 E80 STM32 bench firmware] FIX-T1..T7 + E80-7/SPI-bypass touch DIFFERENT functions of the same files (independent fixes); `feat/c3-harmonization` (23 files, 2026-08-25) is the wide/old one. Resolve: merge the FIX-T* set first, one at a time, running `firmware/e80-stm32-bench/tests` after each; then the features. One decision: is the STM32 bench firmware still live, or has the RP2040 path replaced it? |
| `feat/host-driven-bench` | 2026-08-28 | 29 | 5 | [C3 RP2040 / flrc-bench-espidf radio benches] NOT a free archive — an earlier 'already on the trunk' reading was a grep false positive (see section 4). Reverse-apply shows the branch carries changes the trunk lacks. One decision: is the RP2040/FLRC bench path still live (merge, tests after each) or retired (archive with an `archive/` tag)? |
| `feat/e80-cvm-go-mode` | 2026-09-13 | 20 | 3 | [C2 E80 STM32 bench firmware] FIX-T1..T7 + E80-7/SPI-bypass touch DIFFERENT functions of the same files (independent fixes); `feat/c3-harmonization` (23 files, 2026-08-25) is the wide/old one. Resolve: merge the FIX-T* set first, one at a time, running `firmware/e80-stm32-bench/tests` after each; then the features. One decision: is the STM32 bench firmware still live, or has the RP2040 path replaced it? |
| `fix/t6-sweep-preflight` | 2026-09-16 | 4 | 1 | [C2 E80 STM32 bench firmware] FIX-T1..T7 + E80-7/SPI-bypass touch DIFFERENT functions of the same files (independent fixes); `feat/c3-harmonization` (23 files, 2026-08-25) is the wide/old one. Resolve: merge the FIX-T* set first, one at a time, running `firmware/e80-stm32-bench/tests` after each; then the features. One decision: is the STM32 bench firmware still live, or has the RP2040 path replaced it? |
| `feat/tracker-tx-tempcomp` | 2026-09-18 | 14 | 8 | [C1 payack / tollgate_payment_proto] Sequential follow-ups on ONE PR line (all descend from the now-merged `pr/tollgate-payment-proto-tdd`), not competing implementations. Resolve: rebase onto the trunk in date order, union the docs/CI hunks, re-run `tracker/firmware/test/test_tollgate_payack_parse.py` + the integration test. One decision: accept the union as canonical. |
| `fix/tollgate-payack-harness-seq` | 2026-09-18 | 5 | 8 | [C1 payack / tollgate_payment_proto] Sequential follow-ups on ONE PR line (all descend from the now-merged `pr/tollgate-payment-proto-tdd`), not competing implementations. Resolve: rebase onto the trunk in date order, union the docs/CI hunks, re-run `tracker/firmware/test/test_tollgate_payack_parse.py` + the integration test. One decision: accept the union as canonical. |
| `fix/tollgate-payack-sid-price-exp` | 2026-09-18 | 11 | 8 | [C1 payack / tollgate_payment_proto] Sequential follow-ups on ONE PR line (all descend from the now-merged `pr/tollgate-payment-proto-tdd`), not competing implementations. Resolve: rebase onto the trunk in date order, union the docs/CI hunks, re-run `tracker/firmware/test/test_tollgate_payack_parse.py` + the integration test. One decision: accept the union as canonical. |
| `fix/tollgate-payack-seq-whitespace` | 2026-09-18 | 7 | 7 | [C1 payack / tollgate_payment_proto] Sequential follow-ups on ONE PR line (all descend from the now-merged `pr/tollgate-payment-proto-tdd`), not competing implementations. Resolve: rebase onto the trunk in date order, union the docs/CI hunks, re-run `tracker/firmware/test/test_tollgate_payack_parse.py` + the integration test. One decision: accept the union as canonical. |
| `docs/harm-t9-adoption` | 2026-09-27 | 16 | 7 | [C4 tracker port / adoption trio] `docs/harm-t9-adoption` is docs + AGENTS.md + README.md → prose union, lowest risk of the set. But `tracker/firmware/main/Kconfig.projbuild` + `app_main.cpp` conflict with `balloon-nostr/dev` on the same two files → sequence with C6, do not merge in parallel. |
| `worker-balloon/pcb-phase1-t877-main` | 2026-09-29 | 6 | 3 | [C5 PCB / KiCad board artifacts] `worker-balloon/pcb-phase1-t877-main` IS open PR #15 (CONFLICTING) → rebase onto the trunk, resolve, push to the PR branch (never force). `pcb-phase1-t877` is the earlier attempt of the same job → superseded by `-main`. `balloon-circuit-design` carries a BINARY `hub_board_v1.kicad_pcb` (2026-07-30): decide which board revision is authoritative first. |
| `worker-balloon/pcb-phase1-t877` | 2026-09-29 | 3 | 2 | [C5 PCB / KiCad board artifacts] `worker-balloon/pcb-phase1-t877-main` IS open PR #15 (CONFLICTING) → rebase onto the trunk, resolve, push to the PR branch (never force). `pcb-phase1-t877` is the earlier attempt of the same job → superseded by `-main`. `balloon-circuit-design` carries a BINARY `hub_board_v1.kicad_pcb` (2026-07-30): decide which board revision is authoritative first. |

## 3. It is ~5 decisions, not 25

### C1 payack / tollgate_payment_proto
Contended surface: `tracker/firmware/main/tollgate_payment_proto.{c,h} + PAY/ACK parser tests + the two CI lanes`

- `feat/tracker-tx-tempcomp` (2026-09-18, +14) — 8 conflicting file(s)
  - docs(tracker/tollgate): say "producer", not "line", in the collision-scan notes
- `fix/tollgate-payack-harness-seq` (2026-09-18, +5) — 8 conflicting file(s)
  - ci(ngit): run the tracker tollgate proto + PAY/ACK parser suites in the ngit lane
- `fix/tollgate-payack-seq-whitespace` (2026-09-18, +7) — 7 conflicting file(s)
  - docs(tracker/tollgate): correct the stale producer line refs in the PAY/ACK docs
- `fix/tollgate-payack-sid-price-exp` (2026-09-18, +11) — 8 conflicting file(s)
  - docs(tracker/tollgate): describe the session_id field name without quoting a regex

### C2 E80 STM32 bench firmware
Contended surface: `firmware/e80-stm32-bench/{src,tests,tools} — the FIX-T1..T7 + E80 feature set`

- `fix/t1-sweep-start-validation` (2026-08-21, +2) — 3 conflicting file(s)
  - fix(tools): e80_sweep_full START-reply fail-fast + LoRa LEN cap + FLRC LEN sweep
- `fix/t2-rx-start-len-gate` (2026-08-21, +2) — 1 conflicting file(s)
  - fix(bench): RX START per-mod LEN gate — parity with TX (GREEN, FIX-T2)
- `fix/t3-flrc-match123` (2026-08-21, +2) — 2 conflicting file(s)
  - FIX-T3: FLRC RX Match123 + pkt-params golden host tests + 255-branch hunt
- `fix/t4-fifo-clear` (2026-08-22, +4) — 3 conflicting file(s)
  - fix(fw): clear LR20xx RX FIFO per re-arm + TX FIFO before write (FIX-T4)
- `fix/t6-sweep-preflight` (2026-09-16, +4) — 1 conflicting file(s)
  - fix(tools): sections as builders, not dict tags — restore build_configs parity
- `feat/e80-7-crc-logging` (2026-08-20, +1) — 8 conflicting file(s) · 2 conflicting file(s) already carry this change on the trunk
  - feat(e80): log CRC-failed packets with RSSI (E80-7/M7)
- `feat/e80-spi-bypass` (2026-08-20, +10) — 8 conflicting file(s)
  - feat(c3): log CRC-failed packets (C3-4/M7)
- `feat/e80-cvm-go-mode` (2026-09-13, +20) — 3 conflicting file(s)
  - fix(e80): the stop sentinel '?' is no stop source, not a stop named '?', in GO mode
- `feat/c3-harmonization` (2026-08-25, +2) — 23 conflicting file(s)
  - docs(coordination): add DISCOVERIES.md — commit discovery index

### C3 RP2040 / flrc-bench-espidf radio benches
Contended surface: `firmware/rp2040/*, mesh-stack/flrc-bench-espidf/*`

- `speed-sustained-sweep` (2026-08-05, +22) — 10 conflicting file(s) · 3 conflicting file(s) already carry this change on the trunk
  - docs: discovery sync batch 5 — 3 PCB findings all N/A (2-layer board, DSN, pad collision)
- `phase1-interop-test` (2026-08-01, +8) — 6 conflicting file(s)
  - P1B.TEST Fix test runner: device reset between test groups
- `range-tests` (2026-08-17, +15) — 5 conflicting file(s)
  - docs(data): add data handover package — handover doc, census, gaps plan
- `feat/host-driven-bench` (2026-08-28, +29) — 5 conflicting file(s)
  - feat(bench): FW-6 dispatch layer — decision table, plan-executor wiring + host test

### C4 tracker port / adoption trio
Contended surface: `.gitignore, tracker/firmware/main/{app_main.cpp,Kconfig.projbuild}, firmware/rp2040/platformio.ini`

- `docs/harm-t9-adoption` (2026-09-27, +16) — 7 conflicting file(s)
  - docs(harm): bench console / RP2040 build+flash + harmonized bench role (HARM-T9)

### C5 PCB / KiCad board artifacts
Contended surface: `tracker/hardware/*, Makefile, drc_snapshots`

- `balloon-circuit-design` (2026-07-30, +3) — 1 conflicting file(s)
  - fix(pcb): F33 v6/v7 DRC reports + PCB updates — 16 shorts remaining (SPI rt.connect + B.Cu congestion)
- `worker-balloon/pcb-phase1-t877` (2026-09-29, +3) — 2 conflicting file(s)
  - fix(pcb): correct DSN track import — Y inversion + degenerate-segment collapse
- `worker-balloon/pcb-phase1-t877-main` (2026-09-29, +6) — 3 conflicting file(s)
  - fix(pcb): decide the fallback refusal before importing pcbnew (t_877751ec)

### C6 nostr_store / mesh wiring component
Contended surface: `tracker/firmware/components/nostr_store/*, CMakeLists + sdkconfig`

- `balloon-nostr/dev` (2026-08-05, +5) — 9 conflicting file(s)
  - feat: adopt tollgate_payment_proto + relay_send_nostr CLI + tests from balloon-hermes
- `balloon-mesh-wiring/radio-glue` (2026-07-30, +7) — 3 conflicting file(s)
  - plan: branch consolidation — merge 8 active branches to master in dependency order
- `balloon-tollgate-extract` (2026-07-30, +2) — 2 conflicting file(s)
  - fix(tollgate): add test_tollgate_client to Makefile — 14/14 suites
- `balloon-tollgate/dev` (2026-08-08, +11) — 1 conflicting file(s)
  - docs: discovery sync batch 10 — diagonal 45° routing, zero tollgate impact

## 4. Superseded-in-effect? REFUTED — nothing is a free archive

Two independent tests, both negative:

1. `git cherry HEAD <ref>` — patch-id comparison over each branch's commits: **0 of 25 branches** are duplicates.
2. Reverse-apply test — for every conflicted file, `git diff <merge-base> <ref> -- <file> | git apply --check -R -` against the trunk. No branch produced even one clean reverse-apply, i.e. no file's branch version is already the trunk's version. Data: `~/reports/balloon-consolidation/applied.json` (script `applied.py`).

**Correction to an earlier claim in this triage.** A grep of each branch's added lines against the trunk blob reported `already_present: partial/yes` on 54 of the competing code files, and that was read as "C3 is the cheapest win — its change may already be on the trunk". **That was a false positive.** The greps matched generic lines that occur everywhere (`#ifdef __cplusplus`, bare `}`, `/*`). The reverse-apply test is the reliable one, and it says the opposite. No branch in the 25 can be archived as superseded.

The two branches that DO show a clean reverse-apply are the two already merged into the trunk in this round (`balloon-tollgate/dev` and `fix/t2-rx-start-len-gate`), which is a consistency check on the method, not a finding.

## 5. Operator decisions (recorded so this is not re-litigated)

- **`balloon-circuit-design` — ARCHIVE, do not merge** (operator-confirmed 2026-10-06). It carries an OLDER `tracker/hardware/hub_board_v1.kicad_pcb` (43,526 B) than the trunk (44,438 B); the trunk received `circuit-design-dev` on 2026-10-06, and `tracker/hardware` has had 52 commits since 2026-09-01. Merging it would move the hub board backwards. Its tip is preserved by the annotated tag `archive/consolidate-2026-10-05/balloon-circuit-design` on GitHub — nothing is discarded, only not merged.
- **`worker-balloon/pcb-phase1-t877` — ARCHIVE** (same reasoning: earlier attempt of the `-main` job). Tag: `archive/consolidate-2026-10-05/worker-balloon/pcb-phase1-t877`.
- **`worker-balloon/pcb-phase1-t877-main` — REBASE** onto the trunk and resolve; it is open PR #15 and is the live attempt. Not an archive case. Tag stays as the pre-rebase safety net.

## 6. Method / reproduction

- Conflict discovery: `git merge-tree --write-tree --name-only HEAD <ref>` (never touches worktree/index).
- Already-applied detection: `git cherry HEAD <ref>` (patch-id) for commit-level, and per-file `git diff <merge-base> <ref> -- <file> | git apply --check -R -` for file-level. **The earlier grep of added lines against the trunk blob was a false positive and is NOT used as evidence** (see section 4).
- Per-file class: three-way blob diff (`base` = merge-base, `ours` = trunk, `theirs` = branch); `COMPETING` when both sides modify/delete the same region; BINARY for non-line-based artifacts.
- Scripts: `~/reports/balloon-consolidation/{triage.py,meta.py,cherry.py,analyze.py,show.py}`.
- Raw data: `~/reports/balloon-consolidation/{TRIAGE.json,cherry.json,triage.json}`.

