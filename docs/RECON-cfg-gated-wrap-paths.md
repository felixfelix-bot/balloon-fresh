# RECON lane C: cfg/feature/env-gated alternate wrap paths

Lane: **C** (adversarial recon, read-only)
Repo: `balloon-e80bench` (remote `github.com/felixfelix-bot/balloon-fresh`)
Scope: `firmware/e80-stm32-bench/tools/` and everything reachable from it
(manifests, build scripts, makefiles, CI configs).
Base commit at recon time: `b0a6899578a8a88a56290cd189fa3f144f08eb16`
(branch `pr/pcb-drc-scorecard`; wrap files byte-identical to `main`, verified C67)
Date: 2026-09-28
Companion: `docs/RECON-duplicate-giftwrap-paths.md` (lane A — construction sites)

Claim under test: **"no cfg/feature/env-gated alternate path to the wrap logic
exists — no second construction path and no bypass under any build/run
configuration."**

---

## 1. Verdict

**No gated alternate wrap CONSTRUCTION path found.** Nothing in the repo's
build system, manifests, feature flags, or configuration can enable a second
kind-1059 construction: there are no declared features, no cfg gates, no
optional dependencies, and every `gift_wrap()` call site is statically
enumerated and unconditional once its function is entered (lane A).

**BUT one live gated BYPASS path exists** — the repo ships a complete,
unauthenticated TCP board-control channel (`tools/e80_board_server.py`,
`BoardTCPServer`, `0.0.0.0:7780`) that reaches the exact same board commands
the CVM gift-wrap channel protects, with **zero authentication and no
allow-list**. It is fully wired via a *second* Makefile
(`tools/Makefile`: `tx-server`/`rx-server`/`range-test`) that the main
firmware Makefile never mentions. Under the lane-C framing ("a bypass under
some build/run configuration") this is candidate #1.

Additionally, three production wrap sites are **interpreter-gated in
practice**: every shipping entrypoint defaults to `PYTHON ?= python3`
(main `Makefile:34`, `tools/Makefile:18`), and on this fleet `python3`
has **no `nostr_sdk`** — so the wrap paths only run under an operator
override (`PYTHON=/opt/miniconda/bin/python` or a 3.13 interpreter).
No CI workflow and no release artifact ever enables them.

---

## 2. Method — exact commands and output summary

All commands run from `/home/c03rad0r/repos/balloon-e80bench` unless noted.
`tools/` shorthand = `firmware/e80-stm32-bench/tools/`.

| # | Command (verbatim) | Output summary |
|---|--------------------|---------------|
| C1 | `find firmware/e80-stm32-bench -name '*.rs' -o -name 'Cargo.toml' -o -name 'build.rs' -o -name 'Kconfig*' -o -name '*.cargo' -o -name 'rust-toolchain*'` | **Zero artifacts.** No Rust, no Cargo manifest, no build script, no Kconfig, no toolchain pin anywhere in the lane-C scope. |
| C3 | `grep -rIn --exclude-dir=.git --exclude-dir=build --exclude-dir=build-fw --exclude-dir=build-host --exclude-dir=__pycache__ --exclude='*.zip' -E '#\[cfg\|cfg!\(\|cfg_attr\|target_os\|target_arch\|feature\s*=\|features\s*=' firmware/e80-stm32-bench/` | **Exit 0 with zero output — zero cfg/feature gates in the entire firmware tree.** |
| C4 | `find . -path ./.git -prune -o \( -name '*.yml' -path '*workflow*' -o -name 'Dockerfile*' -o -name '*.nix' \) -print` | Only 2 in-repo CI workflows for this repo: `.github/workflows/ci-host-tests.yml`, `.github/workflows/test.yml`. Other workflow hits are vendored RadioLib copies (out of scope). **No Dockerfiles repo-wide** (C58). |
| C5 | `grep -nE 'sys\.path' cvm_board_server.py cvm_campaign.py cvm_relay_test.py test_cvm_board_server.py` (in `tools/`) | 4 files, all insert `_TOOLS_DIR` at sys.path[0] — defines the reachable import closure. |
| C6 | `grep -nB2 -A6 -E 'try:' cvm_board_server.py` | All try/except blocks are runtime error handling — **no try-import feature detection in production code**. |
| C7 | `grep -rInE 'environ\|getenv\|os\.env' --exclude-dir=__pycache__ .` (non-test, in `tools/`) | 11 hits, 7 env vars (table §4). |
| C8 | `grep -nE 'add_argument' cvm_board_server.py cvm_campaign.py cvm_relay_test.py` | All CLI flags (table §4). |
| C9 | `grep -rInE 'CVMClient\(\|transport\s*=\|RETRY_COUNT\|DEFAULT_TIMEOUT' --exclude-dir=__pycache__ .` | Every `transport=` caller is a **test file**; production `amain()` constructs `CVMClient` without `transport` (`cvm_campaign.py:531-533`). |
| C11 | `grep -nE 'allowed\|_auth\|verify' cvm_board_server.py` | Allow-list gate at `:430`, wired from `--allowed-client-npubs`/`CVM_ALLOWED_CLIENTS` at `:782-800`. |
| C12 | `grep -nE '^(RETRY_COUNT\|DEFAULT_TIMEOUT\|DEFAULT_RELAYS\|KIND_\|T0_\|E80_)' cvm_campaign.py cvm_board_server.py` | `RETRY_COUNT = 1` (`cvm_campaign.py:69`) — constant, not flag/env-settable; gates the retry wrap site. |
| C13 | `grep -rInE 'gift\|wrap\|nostr\|cvm\|1059\|25910' tools/e80_board_server.py tools/e80_campaign.py tools/e80_sweep_full.py tools/e80_detect.py` | Only docstring words ("wrapping a BoardController"). Import closure adds no wrap code. |
| C14 | `grep -l '__main__' tools/*.py` | 30+ entry scripts — all runnable standalone (relevant to reachability). |
| C15/C16 | `grep -nE 'cvm\|gift\|wrap' Makefile` + `cat ../../.github/workflows/*.yml` | 3 reachable make targets (CVM). **CI runs only C/C++ suites + root `tests/` — no CI job ever runs any `tools/` Python suite, let alone a wrap site.** |
| C17/C18 | `cat tools/create-range-test-zip.sh` + `unzip -Z1 e80-range-test-e7a78e9.zip` | The shipped release zip copies **only** `e80_bench_ctl.py, e80_detect.py, gps_stitch.py, merge_csvs.py, countdown.py` into `tools/`. **Zero `cvm_*.py` — no wrap code in the release artifact.** |
| C20 | `grep -rIn --include='*.toml' --include='*.txt' --include='*.cfg' --include='*.ini' -iE 'nostr\|requirements' pyproject.toml firmware/e80-stm32-bench/` | **Zero hits — `nostr_sdk` is not a declared dependency anywhere.** It is a lazy runtime import in 14 sites (C21). |
| C21 | `grep -rInB3 'import nostr_sdk' --exclude-dir=__pycache__ .` | 14 lazy `import nostr_sdk` sites: 12 in production modules, 1 in a test helper, 1 in the gated round-trip test. Module import never fails on a missing SDK — failure surfaces only at call time. |
| C22 | `grep -rInE 'sys\.version_info\|platform\.\|os\.name\|TYPE_CHECKING\|__debug__\|PYTHONASYNCIODEBUG' --exclude-dir=__pycache__ .` | Only `IS_MAC = platform.system() == "Darwin"` (`e80_detect.py:56`) — serial-path selection only, nothing near wrap. |
| C23 | `grep -rInE 'legacy\|compat\|\.get\(["'\''](enabled\|feature\|mode\|debug\|wrap)' --exclude='test_*' .` | `--format harmonized|legacy` toggle in `e80_bench_ctl.py:2490` (RX-log CSV parser choice, `parser = parse_pkt_line if use_harmonized else parse_pkt_line_legacy` at `:2061`) — **not wrap-related**; no `enabled/feature/wrap` config keys exist. |
| C24/C25 | `read_file pyproject.toml`, `read_file pytest.ini` | `pyproject.toml`: only dev dep `pytest>=9.1.1`; **no `[project]` deps, no optional extras, no entry points**. `pytest.ini`: markers unit/hardware only. |
| C26 | interpreter probe (for-loop over python3 / miniconda / 3.13) | **BLOCKED by the command guard** (nested executable body). Not re-attempted per guard instruction; `nostr_sdk` availability evidence is inherited from lane A (C9 there): installed at `~/.local/lib/python3.13/site-packages/nostr_sdk`, version 0.44.2, **not importable under default `python3`**. Recorded as an open question (§7.1). |
| C27 | `grep -rInE 'gift\|wrap\|1059\|25910\|nostr' --include='Makefile' --include='*.cmake' --include='CMakeLists.txt' --include='*.json' --include='*.sh' .` (excluding tools/, docs/) | Only Makefile help-text relay URLs. **No build/config file references wrap logic.** |
| C29 | `grep -nE 'option\|FEATURE\|BUILD_' CMakeLists.txt` | Zero CMake options/features (firmware build only). |
| C31 | `grep -rn 'class MockCVMTransport' .` | Defined at `test_cvm_board_server.py:93` — test-only. |
| C34 | `grep -nE 'except ImportError\|except ModuleNotFoundError' cvm_board_server.py cvm_campaign.py cvm_relay_test.py test_cvm_board_server.py` | Exactly 1: `test_cvm_board_server.py:141` (`TestPlatform.have_nostr_sdk`). Production code has no import fallbacks. |
| C36/C39/C40 | `grep -rIlE 'gift\|wrap\|cvm\|nostr' tests/` + detail greps | Root `tests/` (what CI `test.yml` runs) has **zero gift-wrap code** — hits are a C telemetry parser (`test_telemetry_to_nostr.py`), phase-wrap-around arithmetic, prose. |
| C37 | `grep -lIE 'gift_wrap\|KIND_GIFT\|1059\|nostr_sdk' firmware/e80-stm32-bench/tools/*.py` | **Exactly 4 files** carry wrap tokens: `cvm_board_server.py`, `cvm_campaign.py`, `cvm_relay_test.py`, `test_cvm_board_server.py`. |
| C41-C45 | structure greps on `e80_board_server.py` (`grep -nE 'class \|def main\|add_argument\|TCP\|socket\|serve'`) | Full TCP control path: `BoardController:75`, `BoardTCPServer:218`, `run_server:349`, `main:447`, default port 7780, `--tcp-port`, `--daemon`, `--role`. |
| C42 | `grep -nE 'e80_board_server' Makefile` (main fw Makefile) | **Exit 1 — zero references.** The TCP path is invisible from the main Makefile. |
| C46-C49 | `git branch -a` + `git log --all --oneline --source -- 'firmware/e80-stm32-bench/tools/cvm*'` + per-branch `git grep -lI 'gift_wrap\|KIND_GIFT_WRAP'` | Branches with wrap files: `main`(4), `pr/pcb-drc-scorecard`(4), `feat/quiet-mode`(4), `feat/e80-cvm-go-mode`(+`cvm_sync.py`), `wt/cvm-p1`(+`cvm_sync.py`), `feat/e28-ranging-bridge`(+`e28_board_server.py`), `feat/c3-harmonization`(4), `docs/lr2021-lessons`(4). |
| C48 | per-branch `git grep -lIE 'gift_wrap_from_seal\|from_seal\|EventBuilder\|KIND_SEAL'` | **0 files on every branch** — no seal-based or hand-rolled wrap alternate anywhere in branch history. |
| C50-C55 | per-5th-file usage greps + `git show <branch>:<file>` excerpts | `cvm_sync.py` (go-mode branch): third duplicate `KIND_GIFT_WRAP = 1059` at `:68`, **subscribe-only**. `e28_board_server.py` (e28 branch): `from cvm_board_server import ... KIND_GIFT_WRAP` at `:71`, reuse only. **Neither constructs a wrap** (construction grep exit 1). |
| C53 | per-branch `git grep -nE 'gift_wrap\('` (excluding `from_gift_wrap`) | Construction sites are **identical on every branch**: 4 production/test sites + 1 test site, same lines. No branch adds a construction. |
| C56 | `grep -nE '^PYTHON\|^TOOLDIR' firmware/e80-stm32-bench/Makefile` | `PYTHON ?= python3` (line 34). Same in `tools/Makefile:18`. |
| C57 | `grep -cE 'name = "nostr' uv.lock` | **0** — the lockfile pins no nostr package. |
| C59/C60 | `grep -nE 'e80_range_test\|range-tx:\|range-rx:' Makefile` | `range-tx`/`range-rx` invoke `e80_bench_ctl.py` (GO/legacy T0), **not** the TCP pair. |
| C61 | `grep -rn 'e80_range_test\|e80_board_server' docs/RANGE-TEST-GUIDE.md` | **Zero hits** — the TCP path is undocumented in the operator guide. |
| C63 | `grep -cE 'cvm\|armed\|ARMED\|started.json\|--sync' tools/e80_bench_ctl.py` | **0** — the GO-mode cvm_sync integration is absent from this checkout (branch-only). |
| C67 | `git diff --stat main -- <4 wrap files>` | Empty — current branch's wrap files are byte-identical to `main`. |
| C69/C70 | `grep -nA6 -E '^(range-test-host\|test-tools\|test-cvm):' Makefile` + `grep -n 'test_cvm' Makefile` | `range-test-host` runs only `test_e80_range_split.py` + `test_range_check.py`. **No make target runs any wrap test.** |
| C71 | `grep -rIlE 'e80_range_test\|e80_board_server' --include='*.py' --include='*.md' --include='Makefile' --include='*.sh' firmware/e80-stm32-bench/ docs/ scripts/` | Referenced by: `tools/Makefile` (the wiring), `e80_board_relay.md` (design doc), `docs/plans/cvm-e28-integration-audit.md` (plan). |
| C72/C75 | `grep -lE 'transport=' tools/*.py \| grep -v test_` + exact lines | Only `cvm_campaign.py` (the parameter definition itself, `:84`). **No production caller passes `transport=`.** |
| C77 | `grep -rInE 'client\.call\(' --exclude='test_*' .` | 12 production `CVMClient.call()` sites in `cvm_campaign.py:326-540` — all flow through the transport gate at `:143`. |
| C79 | `sed -n '44,60p' e80_board_server.py` | Plain imports (socket, socketserver, subprocess...). No gating at import time. |
| C80 | `grep -rn '8685' . --include='*.py' --include='*.md' --include='Makefile'` | Design doc `e80_board_relay.md` says **TCP 8685**, code says **7780** — stale-doc drift on the bypass channel. |
| C81 | `ls e28_board_server.py cvm_sync.py` | **Neither exists on this branch** — branch-only files. |
| C83 | `grep -nE 'auth\|token\|key\|secret\|allow' e80_board_server.py` | **Exit 0 with zero real hits** — no authentication of any kind on the TCP path. |
| C84 | `grep -nE '0\.0\.0\.0\|bind\|HOST' e80_board_server.py` | Binds `0.0.0.0:7780` (`:221`, `:232`, `:417`) — all interfaces. |

### Corrections / blocked commands (recorded for honesty)

* **C26 was blocked** by the agent command guard (nested loop over
  interpreters). Per guard instruction it was NOT retried or rephrased;
  interpreter evidence is inherited from lane A and flagged as open question §7.1.
* **C47/C48 were auto-approved** by the smart-approval security scan (nested
  `for b in $(git for-each-ref ...)` loop). Output was reviewed and is
  trustworthy; recorded here for full disclosure.
* C6's first form (context grep) initially matched unrelated try-blocks; the
  definitive result is C34 (exactly one `except ImportError` in the closure).

---

## 3. Master table — every gate found, with enablement analysis

### 3.1 Build-level gates

There are **no compiled-language feature gates in scope**: no `Cargo.toml`,
no `build.rs`, no `Kconfig`, no `.cargo/config`, no toolchain pin, no CMake
option, no `#[cfg]`/`cfg!`/`cfg_attr`/`target_os`/`target_arch` token anywhere
in `firmware/e80-stm32-bench/` (C1, C3, C29). The toolchain is pure Python;
"build configuration" reduces to: which interpreter runs, which make target is
invoked, and what the release/CI scripts copy.

| Gate | Where (absolute path : line) | Default | What enables it | Ships in a real build? | Judgement |
|---|---|---|---|---|---|
| Interpreter selection | `/home/c03rad0r/repos/balloon-e80bench/firmware/e80-stm32-bench/Makefile:34` `PYTHON ?= python3` | `python3` (no `nostr_sdk`) | `PYTHON=<sdk-capable python>` override | No build pins it; CI never sets it; zip's README says `pip install pyserial` only | **The effective master gate**: all 3 production wrap sites are unreachable under repo defaults |
| `nostr_sdk` dependency | absent from `pyproject.toml`, `uv.lock`, every manifest (C20, C57) | not declared | operator pip-installs it manually | Not in any artifact | undeclared lazy dep — the wrap path is opt-in by environment, not by build |
| Release artifact content | `/home/c03rad0r/repos/balloon-e80bench/firmware/e80-stm32-bench/tools/create-range-test-zip.sh` (tools loop, `for f in e80_bench_ctl.py e80_detect.py gps_stitch.py merge_csvs.py countdown.py`) | excludes all `cvm_*.py` | nothing — no flag can include them | The shipped zip contains **zero wrap code** | wrap paths are repo-only, not shipped |
| CI coverage | `/home/c03rad0r/repos/balloon-e80bench/.github/workflows/ci-host-tests.yml` (C suites only), `test.yml` (root `tests/` only) | never runs `tools/` Python | nothing | No CI config enables a wrap path | dead-in-CI, not shipped — but **reachable by an operator** |
| Firmware CMake | `/home/c03rad0r/repos/balloon-e80bench/firmware/e80-stm32-bench/CMakeLists.txt` | no options | — | n/a | no gate exists |

### 3.2 Runtime gates — environment variables

All env reads in the wrap-relevant closure (C7). None toggles wrapping on/off;
they supply keys, relays, or the auth allow-list.

| Env var | Absolute path : line | Enclosing block | Effect | Judgement |
|---|---|---|---|---|
| `CVM_SERVER_HEX` | `/home/c03rad0r/repos/balloon-e80bench/firmware/e80-stm32-bench/tools/cvm_board_server.py:757` | `main()` argparse default | server key (hex) — required together with `--nsec` or the server exits 2 (`:770-773`); `serve()` raises if `server_keys is None` (`:489-490`) | **gate ON the server wrap site** — without it, `_send_reply` is unreachable |
| `CVM_SERVER_NSEC` | `.../cvm_board_server.py:759` | `main()` argparse default | alternate key spelling | same gate, second key |
| `CVM_ALLOWED_CLIENTS` | `.../cvm_board_server.py:762` | `main()` argparse default | allow-list; empty string → `[...] or None` at `:782-783` → **`None` = accept ALL clients** (`:430` skips check) | **default-open auth gate** — see candidate #4 |
| `CVM_CONFIGS` | `.../cvm_board_server.py:765` | `main()` argparse default | initial preset push at startup (`:707-720`) | not a wrap toggle |
| `CVM_CLIENT_HEX` | `.../cvm_campaign.py:458` | `_parse_args()` | coordinator key; missing → exit 2 (`:521-524`) | **gate ON both client wrap sites** |
| `OPENOCD` | `.../tools/e80_detect.py:81` | `find_openocd()` | tool discovery | not wrap-related |
| `USER` | `.../tools/e80_bench_ctl.py:866,947`; `e80_range_test.py:583` | operator label | cosmetic | not wrap-related |

### 3.3 Runtime gates — CLI flags

| Flag | Absolute path : line | Enclosing block | Effect on wrap | Judgement |
|---|---|---|---|---|
| `--role tx|rx` (required) | `.../cvm_board_server.py:751` | `main()` | role assertion only | not a wrap toggle |
| `--dry-run` | `.../cvm_campaign.py:451` | `_parse_args()`; checked in `amain()` at `:508` | **returns 0 before any `CVMClient` is built (`:531`)** — suppresses ALL client wrapping | reachable no-wrap mode; a bypass of nothing (it constructs no traffic at all) |
| `--tx-npub` / `--rx-npub` | `.../cvm_campaign.py:454,456` | `_parse_args()`; required at `:517-520` | without both, exit 2 before clients exist | hard gate on client wrap sites |
| `--mode probe|good|degraded|cliff|full-stop` | `.../cvm_campaign.py:434` | `_parse_args()` | selects config preset list (`camp.build_campaign_configs`, `:503`) — changes *what* is wrapped, never *whether* | not a wrap toggle |
| `--band 868|2g4|both` | `.../cvm_campaign.py:437` | `_parse_args()` | config selection | not a wrap toggle |
| `--configs` / `--configs-json` | `.../cvm_campaign.py:464,467` | `_parse_args()`, consumed `:484-501` | inline preset delivery (the coordinator need not have the file) | changes transport payload only |
| `--relays` | `.../cvm_board_server.py:755`, `cvm_campaign.py:460`, `cvm_relay_test.py:142` | argparse defaults | relay list | not a wrap toggle |
| `--json`, `--relays-include-failures` | `.../cvm_relay_test.py:144,146` | `main()` | output format; `--relays-include-failures` merely extends the relay list with two known-broken relays (`:148-149`) | not a wrap toggle |
| `--format harmonized|legacy` | `.../tools/e80_bench_ctl.py:2490` (dispatch `:2058-2061`) | `main()` | **the only true legacy/compat mode flag in the closure** — selects RX-log CSV parser | **unrelated to gift-wrap** (log parsing), included for completeness |

### 3.4 Runtime gates — in-code conditionals around the wrap sites

| # | Gate | Absolute path : line | Enclosing function | What enables the wrap path | Judgement |
|---|---|---|---|---|---|
| G1 | `if self.transport is not None: return await self._call_via_mock(...)` / `return await self._call_via_nostr(...)` | `/home/c03rad0r/repos/balloon-e80bench/firmware/e80-stm32-bench/tools/cvm_campaign.py:143-145` (mock guard also `:101-102` in `connect()`) | `CVMClient.call()` | `transport=None` (production default, `amain:531-533`) → nostr wrap; any object → **wrap bypassed entirely** | **the only bypass of wrapping in the code** — but every `transport=` caller is a test (C9); **test-only alternate path** |
| G2 | `if RETRY_COUNT == 0: raise TimeoutError` — else second literal `gift_wrap` at `:208` | `.../cvm_campaign.py:191` (constant `:69` `RETRY_COUNT = 1`) | `CVMClient._call_via_nostr()` | module constant, **not settable by env/CLI**; =1 today | reachable second construction site (timeout-retry); flag-free |
| G3 | `if p_tag is None or p_tag != server_pk_hex: return` (before unwrap) | `.../cvm_board_server.py:544` | `CVMBoardServer._handle_request()` | p-tag match | unwrap gate, not construction |
| G4 | allow-list: `if self.allowed_clients is not None and sender_pk not in self.allowed_clients` | `.../cvm_board_server.py:430` | `CVMBoardServer.dispatch_rpc()` | **`None` (default) = accept all**; set via `--allowed-client-npubs`/`CVM_ALLOWED_CLIENTS` (`:782-800`) | auth gate, default-open |
| G5 | `if self.signer is None: raise RuntimeError` | `.../cvm_board_server.py:489-490` | `CVMBoardServer.serve()` | server keys present | hard gate on the server subscribe+reply loop |
| G6 | `@unittest.skipUnless(TestPlatform.have_nostr_sdk(), "nostr_sdk not installed (CI image without Rust bindings)")` | `.../tools/test_cvm_board_server.py:455` (predicate `:137-142`) | class `TestGiftWrapRoundTrip` | `import nostr_sdk` succeeding | **test-only wrap site**, correctly gated |
| G7 | lazy `import nostr_sdk` (14 sites) | e.g. `.../cvm_board_server.py:397,491,541,571,627,789`; `cvm_campaign.py:103,159,262,422`; `cvm_relay_test.py:32`; `test_cvm_board_server.py:139,461` | various | import succeeds at call time | no try/except anywhere in production (C34) — a missing SDK is a loud crash, **not a silent fallback** |
| G8 | platform gate `IS_MAC = platform.system() == "Darwin"` | `.../tools/e80_detect.py:56` | module level | OS | serial-path selection only — **the only `target_os`-analogous gate in scope, nowhere near wrap** |
| G9 | `--daemon` / `--tcp-port` | `.../tools/e80_board_server.py:452-453`, wiring `tools/Makefile:134-165` | `main()` / make targets | starting the TCP server | see candidate #1 — bypass channel |

---

## 4. Candidates (numbered)

1. **TCP board server — live unwrapped bypass channel.**
   `/home/c03rad0r/repos/balloon-e80bench/firmware/e80-stm32-bench/tools/e80_board_server.py:218`
   (`class BoardTCPServer`, bind `0.0.0.0:7780` at `:221/:232/:417`),
   entry `main():447`, `run_server():349`.
   What enables it: `tools/Makefile` targets `tx-server`/`rx-server`/`auto-server`/`range-test`/`all-in-one`
   (`tools/Makefile:131-252`) — a second Makefile the main firmware Makefile
   never references (C42 exit 1) and `docs/RANGE-TEST-GUIDE.md` never mentions
   (C61). Client: `tools/e80_range_test.py:92` (`BoardClient`, default port 7780).
   Judgement: **reachable alternate (bypass) path.** It exposes the same
   board commands (`BoardController`) the CVM channel exposes, over an
   unauthenticated, all-interfaces TCP socket — the authenticity/allow-list
   properties of the gift-wrap channel simply do not exist on this path.
   It does NOT construct kind-1059 events, so it is not a second wrap
   *construction*; it is a second *control* path that makes the wrap's
   protections non-exclusive. (Design doc `e80_board_relay.md` still says port
   8685 — stale vs code 7780, C80.)

2. **MockTransport wrap bypass — test-only.**
   `/home/c03rad0r/repos/balloon-e80bench/firmware/e80-stm32-bench/tools/cvm_campaign.py:143-145`
   in `CVMClient.call()`, with the guard `:101-102` in `connect()`.
   What enables it: passing `transport=` to the `CVMClient` constructor
   (`:84`). Every single caller that does is a test file
   (`test_cvm_board_server.py:404,439,525,565`; `test_cvm_campaign_dynamic_config.py`
   ×8); production `amain()` at `:531-533` never passes it (C72).
   Judgement: **test-only alternate path.** Not reachable in any shipping
   configuration — but it is the seam a future "local mode" flag would use.

3. **Retry-wrap second construction site — reachable, constant-gated.**
   `/home/c03rad0r/repos/balloon-e80bench/firmware/e80-stm32-bench/tools/cvm_campaign.py:208`
   in `CVMClient._call_via_nostr()`, gated by `RETRY_COUNT` (`:69` = 1, checked
   `:191`). Enabled by: module constant only — no env/CLI/manifest knob.
   Judgement: **reachable alternate path** (fires on a reply timeout), but not
   user-configurable; setting `RETRY_COUNT = 0` makes it dead code. Same shape
   as lane A candidate #5 — restated here because the gate is a compile-time
   constant, the closest thing this Python codebase has to a `#[cfg]`.

4. **Default-open auth gate on the wrap channel.**
   `/home/c03rad0r/repos/balloon-e80bench/firmware/e80-stm32-bench/tools/cvm_board_server.py:430`
   in `dispatch_rpc()`, with the `[...] or None` normalization at `:782-783`.
   An unset `CVM_ALLOWED_CLIENTS` / omitted `--allowed-client-npubs` makes the
   allow-list `None` → **every client is accepted**. The gate exists but its
   off state is the shipped default.
   Judgement: **reachable**; the "gate" is default-permissive.

5. **Interpreter-gated reachability of ALL production wrap sites.**
   `/home/c03rad0r/repos/balloon-e80bench/firmware/e80-stm32-bench/Makefile:34`
   (`PYTHON ?= python3`) + `tools/Makefile:18` + `nostr_sdk` absent from
   `pyproject.toml`/`uv.lock` (C20, C57). Under repo defaults, `import
   nostr_sdk` fails in `serve()`/`_call_via_nostr()`/`test_one_relay()`, i.e.
   every wrap site is effectively dead until an operator overrides the
   interpreter. No CI, Dockerfile, or release script (C4, C15-C18) ever
   enables a wrap-capable build.
   Judgement: **dead-by-default environment gate** — reachable only via
   manual operator configuration.

6. **Branch-only duplicate constant (merge-time risk, not a path today).**
   `feat/e80-cvm-go-mode:firmware/e80-stm32-bench/tools/cvm_sync.py:68`
   `KIND_GIFT_WRAP = 1059` — a **third** independent definition (in addition
   to lane A's two), comment says "same as cvm_board_server.py" but it does
   not import it. Subscribe-side only; no construction (C52 exit 1). Not on
   `main`/this branch (C81).
   Judgement: **dead code on this branch**; becomes live duplication if
   `feat/e80-cvm-go-mode` merges. Similarly
   `feat/e28-ranging-bridge:.../tools/e28_board_server.py:71` imports
   `KIND_GIFT_WRAP` from `cvm_board_server` (subscribe/unwrap reuse, no new
   construction) — plan `docs/plans/cvm-e28-integration-audit.md` documents it.

7. **Zero-config diagnostic self-wrap.**
   `/home/c03rad0r/repos/balloon-e80bench/firmware/e80-stm32-bench/tools/cvm_relay_test.py:82`
   in `test_one_relay()`, wired to `make range-cvm-test`
   (`Makefile:724-727`). Enabled by: **nothing** — it generates ephemeral keys
   (`:37`) and gift-wraps to itself; the only wrap site reachable with no
   keys, no allow-list, no coordinator. (Its `test_one_relay` name also makes
   it pytest-collectable — the standing `fixture 'url' not found` baseline
   error noted in the e80-range-bench skill.)
   Judgement: **reachable alternate path** (diagnostic), unconditional.

---

## 5. Enablement cross-check — could any build that ships enable these?

| Surface | Runs/contains wrap code? | Evidence |
|---|---|---|
| `.github/workflows/ci-host-tests.yml` | No — 5 C/C++ suites only | C16 |
| `.github/workflows/test.yml` | No — root `tests/` has zero gift-wrap code | C16, C36, C39, C40 |
| `create-range-test-zip.sh` / `e80-range-test-e7a78e9.zip` | **No — zero `cvm_*.py` in the artifact** | C17, C18 |
| Any Dockerfile | none exist | C4, C58 |
| Any Cargo feature / cfg / Kconfig / CMake option | none exist | C1, C3, C29 |
| `pyproject.toml` / `uv.lock` | no nostr dependency, no extras | C20, C24, C57 |
| `make range-cvm-server` / `range-adaptive` / `range-cvm-test` | Yes — **but only under an operator-supplied interpreter + keys** | C15, C56, §4.5 |
| `make range-test-host` (the host gate) | No — runs only `test_e80_range_split.py` + `test_range_check.py` | C69 |
| Bare `pytest tools/` | Collects `test_cvm_board_server.py` — the round-trip wrap test runs **iff nostr_sdk is importable** (G6) | C21, C70 |

**Conclusion:** no automated build, CI job, or release artifact that ships
today enables any wrap construction path. All wrap reachability is
operator-mediated (`make` target + env keys + a nostr_sdk-capable
interpreter). The one fully-wired alternate channel that DOES ship in the
repo and needs no keys is the TCP board server (candidate #1) — which is
precisely why it is the significant finding: it is enabled by nothing more
than `cd tools && make tx-server`.

---

## 6. Explicit conclusion

**No cfg/feature/env-gated alternate WRAP CONSTRUCTION path found.** There are
no declared features, no cfg gates, no optional dependencies; every
`gift_wrap()` construction site (4 production/test + 1 gated test, identical
on all branches, C53) is unconditional once entered, and nothing in any
manifest, makefile, or CI config can produce a second construction path.

**However, "no gated alternate path" is false in the broader sense the lane
asked about** — a numbered candidate list survives (§4):

1. `tools/e80_board_server.py:218` — live unauthenticated TCP bypass channel (reachable)
2. `tools/cvm_campaign.py:143-145` — MockTransport wrap bypass (test-only)
3. `tools/cvm_campaign.py:208` — retry-wrap second construction (reachable, constant-gated)
4. `tools/cvm_board_server.py:430` + `:782-783` — allow-list default-open (reachable)
5. `Makefile:34` + missing dep — all wrap sites dead under repo-default interpreter (dead-by-default)
6. branch-only `cvm_sync.py:68` third `KIND_GIFT_WRAP` constant (dead on main; merge risk)
7. `tools/cvm_relay_test.py:82` — zero-config diagnostic self-wrap (reachable, unconditional)

---

## 7. Open questions (NOT cleared)

1. **Runtime reachability was not exercised.** Everything above is static
   analysis; no wrap was executed, no board opened. In particular the
   `nostr_sdk`-per-interpreter evidence is inherited from lane A (C26's
   interpreter probe was blocked by the command guard and not re-run).
   Whether the field laptops (DQ05/TX) have a nostr_sdk-capable interpreter
   determines whether candidates 3/7 are *actually* live in the field.
2. **Is the TCP board server an accepted exposure?** It binds `0.0.0.0:7780`
   with no auth, is wired via `tools/Makefile` and the SSH targets
   (`rx-server-remote`, `all-in-one`), yet is absent from the operator guide
   and from the main Makefile. Deployment context (LAN-only? VPN?) decides
   severity; I could not determine intended network placement from the repo.
3. **`CVM_ALLOWED_CLIENTS` default-open semantics.** Empty env var means
   accept-all (`cvm_board_server.py:782-783`). Whether that is deliberate
   ("dev convenience") or an oversight is a design question the code cannot
   answer; the docstring at `:389` says "If empty/None, accept all", so it is
   at least *documented*.
4. **Port drift on the bypass channel**: `e80_board_relay.md` specifies 8685,
   code uses 7780 (C80). Indicates the design doc is stale relative to the
   shipped code; which one operators actually follow is unverifiable here.
5. **The merge risk of branch constants.** `feat/e80-cvm-go-mode`'s
   `cvm_sync.py` carries a third `KIND_GIFT_WRAP = 1059`. If that branch
   merges as-is, the duplicate-constant finding from lane A grows from 2 to 3
   definitions with no shared import. Intent (decoupling vs drift) unknown.
6. **`test_one_relay`'s dual identity** (pytest-collectable function AND the
   real diagnostic entrypoint) means a naive `pytest tools/` collects it with
   a missing `url` fixture — the standing baseline error. I did not assess
   whether any wrapper/CI could ever invoke it with the fixture supplied.

---

## 8. What I changed

* Added this report: `docs/RECON-cfg-gated-wrap-paths.md` (new file, only).
* **No source, test, config, or build files were modified.** No formatters,
  no `git add -A`.
* Pre-existing working-tree state (449 modified `data/**/*.log` deletions +
  untracked files) was **not** touched and is **not** part of this commit.
* Committed locally on the current branch only; **not pushed** (task body
  says do not push unless instructed).