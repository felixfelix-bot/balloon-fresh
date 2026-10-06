# Balloon-Fresh Consolidation Triage

Read-only analysis. HEAD (trunk) = `consolidation/main` @ `f2a8629f`. 25 branches analyzed vs HEAD via `git merge-tree --write-tree`.

**Total conflicted files: 137** (the prompt's "133" was a transcription error — the 25 per-branch counts actually sum to 137; computed total matches the true sum exactly).

## Summary counts

| Verdict | Branches | Meaning |
|---|---|---|
| MECHANICAL | 1 | All conflicts resolve by a fixed rule (keep trunk / take branch / union disjoint insertions) |
| MIXED | 3 | Some files mechanical, some need a decision |
| DECISION | 21 | At least one file needs a human engineering decision |

File-level conflict classes (137 total): COMPETING 130 · BOTH-ADD 4 · BRANCH-ONLY 2 · BINARY 1.

## Branch table

| Branch | Ahead | Conflicts | Verdict | One-line contents |
|---|---|---|---|---|
| feat/c3-harmonization | 2 | 23 | DECISION | E80 bench suite + docs (added independently on both sides) |
| speed-sustained-sweep | 22 | 10 | MIXED | FLRC GPS/range TX-RX + board-lock; several already-present in trunk |
| balloon-nostr/dev | 5 | 9 | DECISION | nostr_store + tollgate_payment_proto (tracker) |
| feat/e80-7-crc-logging | 1 | 8 | MIXED | CRC logging in bench_pkt/bench_cmd; 2 disjoint BOTH-ADD |
| feat/e80-spi-bypass | 10 | 8 | DECISION | SPI bypass + firmware_hash_gate + session_manager tools |
| feat/tracker-tx-tempcomp | 14 | 8 | DECISION | TX temp-comp + payack proto + CI/host-tests |
| fix/tollgate-payack-harness-seq | 5 | 8 | DECISION | payack harness sequence + CI/host-tests |
| fix/tollgate-payack-sid-price-exp | 11 | 8 | DECISION | payack SID price expansion + CI/host-tests |
| docs/harm-t9-adoption | 16 | 7 | DECISION | T9 harmonization docs + platformio/config |
| fix/tollgate-payack-seq-whitespace | 7 | 7 | DECISION | payack seq whitespace + CI/host-tests |
| phase1-interop-test | 8 | 6 | DECISION | interop tests + build config |
| feat/host-driven-bench | 29 | 5 | DECISION | host-driven bench + platformio/config/docs |
| range-tests | 15 | 5 | DECISION | range tests + platformio/config/docs |
| balloon-mesh-wiring/radio-glue | 7 | 3 | DECISION | radio glue + 2 build-config files |
| feat/e80-cvm-go-mode | 20 | 3 | DECISION | CVM go-mode + docs |
| fix/t1-sweep-start-validation | 2 | 3 | DECISION | sweep start validation + tests CMake + README |
| fix/t4-fifo-clear | 4 | 3 | DECISION | fifo clear + tests CMake + README |
| worker-balloon/pcb-phase1-t877-main | 6 | 3 | MIXED | host-tests.yml BOTH-ADD + CI |
| balloon-tollgate-extract | 2 | 2 | DECISION | tollgate extract (code only) |
| fix/t3-flrc-match123 | 2 | 2 | DECISION | flrc match123 + tests CMake |
| worker-balloon/pcb-phase1-t877 | 3 | 2 | DECISION | pcb-phase1 t877 |
| balloon-circuit-design | 3 | 1 | DECISION | hub_board_v1.kicad_pcb (BINARY) |
| balloon-tollgate/dev | 11 | 1 | DECISION | docs only |
| fix/t2-rx-start-len-gate | 2 | 1 | MECHANICAL | bench_cmd.h — BOTH-ADD (union, safe) |
| fix/t6-sweep-preflight | 4 | 1 | DECISION | sweep preflight (docs) |

## CLUSTERS — one decision unblocks many branches

Shared conflicting files, by branch count (top clusters):

| File | Branches | Single decision needed |
|---|---|---|
| firmware/e80-stm32-bench/tests/CMakeLists.txt | 5 (c3-harmonization, e80-7-crc-logging, t1-sweep-start-validation, t3-flrc-match123, t4-fifo-clear) | Pick canonical test-list layout |
| docs/INTEGRATION-ASSESSMENT.md | 5 (nostr/dev, harm-t9, host-driven-bench, range-tests, speed-sustained-sweep) | Pick canonical assessment doc |
| tracker/firmware/main/tollgate_payment_proto.{c,h} + test | 5 (nostr/dev, tracker-tx-tempcomp, payack-harness-seq, payack-seq-whitespace, payack-sid-price-exp) | Pick canonical payment-proto definition |
| .ngit/act/workflows/host-tests.yml | 5 (tracker-tx-tempcomp, payack-harness-seq, payack-seq-whitespace, payack-sid-price-exp, pcb-phase1-t877-main) | Pick canonical host-tests workflow |
| firmware/rp2040/platformio.ini | 4 (harm-t9, host-driven-bench, range-tests, speed-sustained-sweep) | Pick canonical platformio config |
| tracker/firmware/main/Kconfig.projbuild + app_main.cpp | 4 (nostr/dev, harm-t9, host-driven-bench, range-tests) | Pick canonical tracker main config |
| .github/workflows/ci-host-tests.yml | 4 (tracker-tx-tempcomp, payack-harness-seq, payack-seq-whitespace, payack-sid-price-exp) | Pick canonical CI workflow |

The **payment_proto family** (`tollgate_payment_proto.c/.h` + test) is the single densest cluster: 4 fix branches + balloon-nostr/dev all rewrite the same proto. Deciding the canonical proto content unblocks all 5.

## MECHANICAL branches (safe resolution rules)

- **fix/t2-rx-start-len-gate** → `firmware/e80-stm32-bench/src/bench_cmd.h` is BOTH-ADD (both sides insert disjoint lines). Resolve by **union of both insertions** — safe, no decision.

## 5 biggest DECISION blockers (one line each)

1. **feat/c3-harmonization** (23 files) — entire `firmware/e80-stm32-bench/` tree was created independently on trunk AND on this branch since the merge-base; every file is "added on both sides, differ". Must pick which side's E80 bench suite is canonical (or manually reconcile ~20 .c/.h/.py files).
2. **tollgate_payment_proto.c/.h** (shared by 4 fix branches + balloon-nostr/dev) — competing rewrites of the payment protocol structs/encoding; the four `fix/tollgate-payack-*` branches are largely mutually exclusive and must be reconciled to one canonical proto.
3. **speed-sustained-sweep** (10 files) — `esp32-c3-flrc/main/main.cpp`, `flrc_cont_tx_fast.cpp`, `balloon-board-lock.py` are `already_present: partial` → branch carries trunk work but diverges; needs a merge decision on which supersedes.
4. **balloon-circuit-design** → `tracker/hardware/hub_board_v1.kicad_pcb` is a **BINARY** KiCad board file — cannot be text-merged; requires a human to open both and decide (or pick one side wholesale).
5. **feat/e80-spi-bypass** (8 files) — new tooling `firmware_hash_gate.py`, `session_manager.py`, `rx_range_logger.py` + `range_test.cpp` all "added on both sides, differ" — independent parallel implementations that need a functional pick.

## already_present signal (COMPETING code files, n=54)

- yes: 5 — branch's change is already effectively in trunk (superseded)
- partial: 31 — branch carries trunk work but diverged (real merge needed)
- no: 18 — branch carries work the trunk lacks (keep, decide how)
- n/a: 37 (non-code files or add/add)

Branches most clearly superseded in effect: several `speed-sustained-sweep` rp2040 files (`flrc_range_rx_auto.cpp`, `flrc_range_rx_gps.cpp`, `flrc_range_tx_auto.cpp` — `already_present: yes`) and `feat/e80-7-crc-logging`'s `bench_cmd.h` + `tests/CMakeLists.txt` (`yes`). Those files can likely be resolved "keep trunk" even though the classifier flags them COMPETING.

## Not determined

- Whether any COMPETING code file actually compiles/links after a proposed union — this is diff-level triage only; no build was run (as instructed).
- The correct canonical content for any DECISION file — that requires the human/domain decision this triage is meant to flag.
