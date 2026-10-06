# RECON: duplicate kind-1059 (NIP-59 gift-wrap) construction paths

Lane: **A** (adversarial recon, read-only)
Repo: `balloon-e80bench` (remote `github.com/felixfelix-bot/balloon-fresh`)
Scope: `firmware/e80-stm32-bench/tools/` and everything reachable from it
Base commit at recon time: `41504d774fac0ca0a15be394708bbfecde4445b5`
Date: 2026-09-28
Re-verified: 2026-10-06 against trunk `e7ec2d0` — the five emit sites
(`cvm_board_server.py:580`, `cvm_campaign.py:179,208`, `cvm_relay_test.py:82`,
`test_cvm_board_server.py:477`) and the shared `nostr_sdk.gift_wrap` primitive
are unchanged. **Delta since base:** a third `KIND_GIFT_WRAP = 1059`
definition now exists on trunk (`cvm_sync.py:68`), so the §1 "defined twice"
count is now three. See `docs/SECURITY-FINDINGS.md` and ADR-033.

Claim under test: **"exactly one construction path to a gift wrap (kind 1059) exists."**

---

## 1. Verdict

The claim is **FALSIFIED** in its literal form, and only narrowly defensible under a
very strict reading.

* There are **5 distinct call sites that emit a kind-1059 event** — 3 in non-test code
  (1 server reply, 2 client request/retry), 1 diagnostic tool, 1 unit test.
* The kind constant **`1059` is defined twice**, independently, in two modules
  (`cvm_board_server.py:74` and `cvm_campaign.py:64`). They do not import from each other.
* All 5 emit-sites route through **one shared upstream primitive**
  (`nostr_sdk.gift_wrap(signer, receiver, UnsignedEvent)`), which constructs the outer
  kind-1059 event inside the `nostr-sdk` binary. So there is **one *primitive*, but not
  one *path*** — the "one path" claim survives only if you define "path" as "the leaf
  library function that does the construction".
* A **second wrap-capable upstream entry point exists and is unused**
  (`nostr_sdk.gift_wrap_from_seal`) — a latent sixth path.
* The **seal (kind 13) lane is clean**: zero in-scope construction of a seal, either
  numeric or via `gift_wrap_from_seal`. No stray-seal second wrapping path found.

Per-lane conclusions are in §6.

---

## 2. Method — exact commands and output summary

All commands run from `<repo>` unless noted.
`tools/` shorthand = `firmware/e80-stm32-bench/tools/`.

| # | Command (verbatim) | Output summary |
|---|--------------------|----------------|
| C1 | `rg -n --no-ignore --hidden -e '\b1059\b' .` | 34 relevant hits; in-scope code hits only in `tools/cvm_board_server.py`, `tools/cvm_relay_test.py`, `tools/cvm_campaign.py` (+ docs, tracker `.agents` skill docs, 2 KiCad coordinate hits `9.1059`, 1 unrelated `.json` index). |
| C2 | `rg -ni --no-ignore --hidden -e 'gift.?wrap' .` | Same 4 in-scope files + docs. No hidden 5th implementation. |
| C3 | `rg -n --no-ignore -i -e 'KIND_[A-Z_]*1059' -e 'KIND_SEAL' -e 'KIND_GIFT' -e 'GIFT_WRAP' -e 'gift_wrap' -e 'Kind\(1059\)' -e 'Kind::Seal' -e 'Kind::GiftWrap' firmware/e80-stm32-bench/` | 15 hits: 2 constant definitions, 1 import, 5 call sites, rest comments. |
| C3b | `grep -rIn --exclude-dir=.git --exclude-dir=__pycache__ -E 'KIND_[A-Z_]+\s*=' .` | Repo-wide: only 4 `KIND_*` definitions exist, all in `tools/`: `cvm_campaign.py:63 KIND_CVM_RPC=25910`, `:64 KIND_GIFT_WRAP=1059`, `cvm_board_server.py:72 KIND_CVM_RPC=25910`, `:74 KIND_GIFT_WRAP=1059`. |
| C4 | `rg -ni --no-ignore --hidden -e '\bseal\b' -e 'KIND_SEAL' -e 'Kind::Seal' .` | Zero code hits. All hits are balloon *heat-sealing* docs (`INTEGRATION-ASSESSMENT.md`, `docs/*`, `hardware/enclosure/*.scad` O-ring), plus one binary `.pyc` line. |
| C5 | `grep -rIn --exclude-dir=__pycache__ -E '["'"'"']kind["'"'"']\s*[:=]' .` (in `tools/`) | 5 hits, **all** `"kind": KIND_CVM_RPC` (inner 25910) inside `UnsignedEvent.from_json` JSON payloads + 1 test literal `25910`. No `"kind": 1059` authored anywhere. |
| C6 | `grep -rInwE --exclude-dir=__pycache__ '13' .` (in `tools/`) | 20 hits, all unrelated: `13-bit` ADC/temp, CSV column index `[13]`, JSON-RPC `id:"13"`. No kind-13. |
| C7 | `grep -rInE --exclude-dir=__pycache__ 'EventBuilder\|UnsignedEvent\|Event\.new\|build_event\|create_event\|seal' .` | Only `UnsignedEvent.from_json` at 5 sites. **No** `EventBuilder`, no `build_event`, no `create_event`, no `Event::new`. No hand-rolled outer-event constructor. |
| C8 | `grep -rInE --exclude-dir=__pycache__ 'gift_wrap\|from_gift_wrap\|UnwrappedGift' .` | 5 `nostr_sdk.gift_wrap(...)` call sites; 3 `UnwrappedGift.from_gift_wrap(...)` unwrap sites. |
| C9 | `find . -type d -name 'nostr_sdk*'` + `python3 -c "importlib.util.find_spec('nostr_sdk')"` + `pip show nostr-sdk` | No vendored copy in-repo. `nostr_sdk` is **not importable** by the default interpreter (PEP-668/`python3` 3.14.4); installed at `<site-packages>/nostr_sdk`, version **0.44.2**. |
| C10 | `unzip -l e80-range-test-e7a78e9.zip` + streamed per-file `grep -q 1059` | 5 `.py` files; **0** contain `1059`. Only hit was a C file (`ral_lr20xx_bsp.c`) where 1059 is a hex/data value. No second implementation. |
| C11 | `grep -nE 'cvm\|gift' firmware/e80-stm32-bench/Makefile` | 3 reachable targets: `range-cvm-server`→`tools/cvm_board_server.py`, `range-adaptive`→`tools/cvm_campaign.py`, `range-cvm-test`→`tools/cvm_relay_test.py`. |
| C12 | `find . -name '*.rs'` → 3 files (all under `tracker/ground-station/antenna-tracker/`), then `grep -rIn -E '1059\|GiftWrap\|gift_wrap\|Kind::\|Seal'` on them | Rust files are **out of scope** and have **zero** gift-wrap/seal/1059 hits. |
| C13 | `grep -rIn -E 'giftWrap\|gift_wrap\|GIFT_WRAP_KIND\|1059' tracker/ --include='*.ts' --include='*.js' --include='*.mjs'` | Zero code hits. `GIFT_WRAP_KIND = 1059` appears only inside agent-skill **documentation** (`.agents/skills/**/*.md`, `references/constants.md` code-fence) — docs, not built code. |
| C14 | `grep -rIn --exclude-dir=__pycache__ 'kinds(' tools/` | Exactly 3 hits, all `Filter().kinds([Kind(KIND_GIFT_WRAP)])` — **subscribe-side** (read), not construction. |
| C15 | `grep -rIn --exclude-dir=__pycache__ -E 'send_event\|publish' tools/` | Exactly 5 `send_event` sites → the same 5 wrap sites (4 files). No independent publish path. |
| C16 | `grep -rIn --exclude-dir=__pycache__ 'phase_schedule' tools/` | Zero hits — planned coordinator schedule path (`docs/plans/cvm-e28-integration-audit.md:134,266`) is **not implemented**. |
| C17 | `grep -rIn --exclude-dir=__pycache__ -E 'add_argument\([^)]*kind' tools/` | Zero hits — no kind is deserialized from CLI/config. |
| C18 | `grep -rIn --exclude-dir=__pycache__ -E '\b(1060\|0x423\|423)\b\|\+\s*59\b' tools/` | Zero hits — no integer arithmetic computes 1059. |
| C19 | `grep -rInw --exclude-dir=__pycache__ -e seal -e Seal -e gift_wrap_from_seal -e extra_tags -e GiftWrap tools/` | **Exit 1 — zero hits.** In-scope code never names a seal or the seal-based wrap API. |
| C20 | `grep -nE '^def (gift_wrap\|gift_wrap_from_seal\|unwrap)\|^class .*Seal' .../nostr_sdk/nostr_sdk.py` | Upstream exposes **two** wrap entry points: `async def gift_wrap(signer, receiver_pubkey, rumor: UnsignedEvent, ...)` @49245 and `def gift_wrap_from_seal(receiver, seal: Event, ...)` @49280. |
| C21 | `git ls-files graphify-out \| wc -l` + `grep -nE 'graphify' .gitignore` | 307 files under `graphify-out/` are **tracked despite** `.gitignore:46,49` ignoring `graphify-out/` and `graphify-out/cache/`. |
| C22 | graphify AST-cache scan for `1059` + context dump | 2 cache files hit, both merely `"source_location": "L1059"` (line numbers in `tracker/firmware/components/{crypto/RNG.cpp,wirehair/gf256.cpp}`), and the files index **another repo** (`balloon-fresh`). `stat-index.json` hit is `"size":1059`. Not kind values. |
| C23 | `grep -rIn --include='*.json' --include='*.yaml' --include='*.yml' --include='*.toml' -E '"kind"\|1059\|seal' firmware/e80-stm32-bench/` | Zero hits — no config-driven kind. |
| C24 | `unzip -Z1 e80-range-test-e7a78e9.zip \| grep -E '\.(py\|rs\|js\|mjs\|ts)$'` | 5 files, all superseded/stale vs current `tools/`. |

### Commands that failed or were corrected (recorded for honesty)

* **C3 (first attempt) was invalid.** I ran
  `rg -rn --no-ignore --hidden -e 'KIND_[A-Z_]+' ...` — `rg -r` is ripgrep's **replace**
  flag, not recursive, so it substituted matches with the literal string `n`
  (output showed `n = 25910`). Re-run correctly as C3/C3b above. Any reader re-deriving
  this recon from that command gets garbage; the corrected forms are authoritative.
* **C4 emitted one binary line** from a `.pyc` inside `__pycache__`
  (`-a`-style binary match) — noise, excluded downstream.
* **Two commands were rejected** by the agent's hardline command-payload guard
  (oversized inline one-liner). Both were re-run via the saved recovery scripts /
  split into smaller invocations; results are folded into C10/C12/C13/C22 above.
* **C21 note:** the `__init__.py` "exported names" grep was **inconclusive by method** —
  `nostr_sdk/__init__.py` is a 2-line blanket `from nostr_sdk.nostr_sdk import *`, so all
  public defs are exposed regardless of what the name-grep returns. `gift_wrap_from_seal`
  is therefore importable as `nostr_sdk.gift_wrap_from_seal`.

---

## 3. Lane A1 — every candidate that can yield a kind-1059 outer event

### A1.1 Kind constant definitions (numeric literal 1059)

| # | Absolute path | Line | Enclosing symbol | Judgement |
|---|---------------|------|------------------|-----------|
| 1 | `<repo>/firmware/e80-stm32-bench/tools/cvm_board_server.py` | 74 | module level, `KIND_GIFT_WRAP = 1059` | **(a) reachable** — server's canonical constant; consumed at `:507`. Not itself a construction. |
| 2 | `<repo>/firmware/e80-stm32-bench/tools/cvm_campaign.py` | 64 | module level, `KIND_GIFT_WRAP = 1059` | **FLAG — duplicate definition.** Second independent literal; `cvm_campaign.py` does **not** import it from `cvm_board_server.py`. Consumed at `:126` (subscribe only). Drift risk, not itself an emit path. |

Both constants are used **only** in `Filter().kinds(...)` subscriptions (C14). Neither is
used to set a `kind` field on an outgoing event — the outgoing kind is produced inside
upstream `gift_wrap`.

### A1.2 Gift-wrap emit sites (the actual construction paths)

| # | Absolute path | Line | Enclosing symbol | Judgement |
|---|---------------|------|------------------|-----------|
| 3 | `<repo>/firmware/e80-stm32-bench/tools/cvm_board_server.py` | 580 | `CVMBoardServer._send_reply(self, recipient_pk, response)` | **(a) reachable duplicate wrapping path.** Server→client reply wrap. Invoked from `_handle_request` `:567`. Reachable via `make range-cvm-server`. |
| 4 | `<repo>/firmware/e80-stm32-bench/tools/cvm_campaign.py` | 179 | `CVMClient._call_via_nostr(self, tool_name, arguments, timeout)` | **(a) reachable duplicate wrapping path.** Client→server request wrap (`gw`). Reachable via `make range-adaptive`. |
| 5 | `<repo>/firmware/e80-stm32-bench/tools/cvm_campaign.py` | 208 | `CVMClient._call_via_nostr(self, tool_name, arguments, timeout)` | **(a) reachable duplicate wrapping path.** Retry copy (`gw2`) after timeout; same function, second literal construction+send. |
| 6 | `<repo>/firmware/e80-stm32-bench/tools/cvm_relay_test.py` | 82 | `test_one_relay()` → nested `SelfHandler.handle_msg()` | **(a) reachable** — diagnostic self-wrap. Reachable via `make range-cvm-test`. Bench/diagnostic path, distinct from the production client/server paths. |
| 7 | `<repo>/firmware/e80-stm32-bench/tools/test_cvm_board_server.py` | 477 | `TestGiftWrapRoundTrip.test_wrap_and_unwrap_preserves_payload()` | **(b) test only.** Constructs a wrap to verify round-trip; asserts `Kind::Custom(25910)` on the inner rumor. |

**Shared primitive:** all five call `nostr_sdk.gift_wrap(signer, receiver, UnsignedEvent)`
— upstream signature confirmed at `nostr_sdk.py:49245`. The outer kind-1059 event (and the
inner seal) is constructed inside the `nostr-sdk` FFI binary. **No in-scope file
hand-rolls an outer event** (C7: no `EventBuilder`/`build_event`/`create_event`/`Event.new`).

### A1.3 Unused alternate upstream construction entry point

| # | Absolute path | Line | Enclosing symbol | Judgement |
|---|---------------|------|------------------|-----------|
| 8 | `<site-packages>/nostr_sdk/nostr_sdk.py` | 49280 | `def gift_wrap_from_seal(receiver: PublicKey, seal: Event, extra_tags) -> Event` | **(c) dead *for this codebase*** — zero in-scope references (C19, exit 1). Latent second wrap-capable entry point, importable via the blanket `from ... import *`. It takes a pre-built seal (kind 13), i.e. it is the API a hand-rolled seal+wrap path would use. |

### A1.4 Kind by deserialization / arithmetic / config

| Candidate class | Result | Judgement |
|---|---|---|
| Deserialized from config/JSON/DB | (c) **none** — C17 (no kind arg), C23 (no config kind), C5 (`"kind"` only ever 25910). | none found |
| Integer arithmetic computing 1059 | (c) **none** — C18 zero hits (no `1060`, `0x423`, `423`, `+59`). | none found |
| Enum variant (`Kind::GiftWrap`, `KIND_GIFT_WRAP`, `GIFT_WRAP_KIND`) | Only the 2 python constants (A1.1). `GIFT_WRAP_KIND` exists only in out-of-scope TS *skill docs* (C13). | covered by A1.1 |
| Other repo areas reachable from tools/ | C9 no vendored copy; C10 zip stale/no py hits; C21/C22 graphify is line-number/size noise. | none found |

---

## 4. Lane A2 — seal (kind 13) constructed outside the primary wrap module

**Result: none found.**

* C4: repo-wide `\bseal\b` → **zero code hits**; all matches are balloon heat-sealing docs
  and enclosure O-ring comments.
* C6: `tools/` word-boundary `13` → 20 hits, all `13-bit` / CSV index `[13]` / RPC `id`.
* C19: `tools/` word-boundary `seal` / `Seal` / `gift_wrap_from_seal` / `extra_tags` /
  `GiftWrap` → **exit 1, zero hits**.
* C20: upstream has no public `Seal` class; a seal is passed as a plain `Event` to
  `gift_wrap_from_seal`, which is unused (A1.3).
* The only seal created in this pipeline is the one inside upstream `gift_wrap`.
  There is **no stray seal made directly**, therefore no second wrapping path via a
  hand-built seal.

---

## 5. Open questions (NOT cleared)

1. **Unused seal-based wrap API** (`gift_wrap_from_seal`, A1.3). Currently unreferenced,
   so today it is dead for this codebase — but it is one import away from becoming a
   genuine second construction path. I could not prove intent (planned vs never-intended).
   Flagging as latent, not cleared.
2. **Duplicated kind constant** across two modules (A1.1 #1/#2). Not an emit path, but the
   same protocol constant is authored independently twice with no shared import. Whether
   this is deliberate decoupling or drift-ready duplication is a design question I cannot
   resolve from the code.
3. **`graphify-out/` is tracked despite being gitignored** (C21: 307 tracked files;
   `.gitignore:46,49` ignore it). Its cached index refers to a *different repo*
   (`balloon-fresh`, `<home>/repos/balloon-fresh/...`) and its `1059` matches are
   `"size":1059` and `"source_location":"L1059"` — i.e. not kind values. I found no code
   that reads this cache to derive a kind, so I judge it non-constructing; but the
   tracked-ignored-file anomaly itself is unresolved and could surprise a future grep-based
   audit (as it did here).
4. **Reachability of emit sites could not be exercised at runtime.** All 5 sites are
   guarded by `if self.transport is not None` (mock mode) or by being invoked only after a
   successful relay connect; `nostr_sdk` is not importable under the default `python3`
   (3.14.4) — it is installed for 3.13. I confirmed reachability **statically** (Makefile
   targets → module → function → call) and did **not** execute a live wrap. Treat
   "reachable" as static-reachability, not runtime-verified.
5. **Out-of-scope neighbours checked but not authoritative.** The 3 Rust files
   (`tracker/.../antenna-tracker/**`) and the TS skill docs are outside my scope; I checked
   them only because a duplicate could hide there. Zero hits, but I am not the owner of
   those lanes.

---

## 6. Per-lane conclusions

**Lane A1 (kind 1059):**
`no duplicate kind-1059 construction found` is **NOT** supportable. Candidates:
1. `tools/cvm_board_server.py:74` — duplicate `KIND_GIFT_WRAP = 1059` definition (reachable, constant only).
2. `tools/cvm_campaign.py:64` — duplicate `KIND_GIFT_WRAP = 1059` definition (reachable, constant only).
3. `tools/cvm_board_server.py:580` — `_send_reply()` wrap emit (reachable).
4. `tools/cvm_campaign.py:179` — `_call_via_nostr()` request wrap (reachable).
5. `tools/cvm_campaign.py:208` — `_call_via_nostr()` retry wrap (reachable).
6. `tools/cvm_relay_test.py:82` — diagnostic self-wrap (reachable via `make range-cvm-test`).
7. `tools/test_cvm_board_server.py:477` — test-only wrap.
8. `site-packages/nostr_sdk/nostr_sdk.py:49280` — unused `gift_wrap_from_seal` (latent).

→ **Duplicate wrapping paths exist (3 reachable production sites + 1 diagnostic + 1 test),
all funnelled to one upstream primitive.** The claim "exactly one construction path" holds
only if "path" is redefined as "the single leaf library function"; under any reading that
counts the code paths that emit a kind-1059 event, it is false.

**Lane A2 (seal kind 13):**
`no duplicate kind-1059/seal construction found` for the seal lane — **no in-scope seal is
constructed at all**; the only seal lives inside upstream `gift_wrap`. The one seam that
would enable a second wrapping path (`gift_wrap_from_seal`) is unused (§5.1).

---

## 7. What I changed

* Added this report: `docs/RECON-duplicate-giftwrap-paths.md` (new file).
* **No source, test, config, or build files were modified.** No formatters, no `git add -A`.
* Pre-existing working-tree state included a large set of deleted `data/**/*.log` files that
  were **not** touched by this recon and are **not** part of this commit.
* Commit: see `git log` message `docs(recon) ...` for the SHA.
