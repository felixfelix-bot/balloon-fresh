# RECON lane B — plaintext / kind-1 fallback paths that bypass gift wrapping

- **Repo:** `/home/c03rad0r/repos/balloon-e80bench`
- **Scope:** `firmware/e80-stm32-bench/tools/` and everything reachable from it
- **Claim tested:** *any fallback path emits or leaks an unwrapped/plaintext event where a gift-wrapped one is expected.*
- **Mode:** READ-ONLY adversarial recon. No code, test, config or build file modified. One artifact added (this document).
- **Predecessor:** lane A `docs/RECON-duplicate-giftwrap-paths.md` (claim FALSIFIED — 5 kind-1059 emit sites exist; the outer wrap is always built inside the Rust FFI `nostr_sdk.gift_wrap`).

---

## 0. Verdict

**For the in-scope code (`firmware/e80-stm32-bench/tools/`): `no plaintext/kind-1 bypass found`.**

Every event emission in scope is the output of `nostr_sdk.gift_wrap(...)` — a kind-1059 event whose
inner rumor is kind-25910 (`KIND_CVM_RPC`). No kind-1 / text-note construction exists in scope, no
unwrapped value reaches a publish call, and the publish API is type-gated so a plaintext send is
structurally impossible from this code (see §3.3).

Two items are nevertheless flagged for a human decision, and one supporting finding is recorded:

| # | Item | Class |
|---|------|-------|
| **F1** | An **unencrypted, unauthenticated TCP control plane** exists alongside the gift-wrapped CVM transport in the same directory (`e80_board_server.py:1439` documents it; `e80_range_test.py:18-19` drives it). It is a **pre-existing, documented, separately-invoked** transport — **not** a fallback branch *from* CVM. | (b)+flagged |
| **F2** | A **literal kind-1 plaintext poster** exists in repo-root `tools/gh_ngit_watchdog.py:273,281,444,469,501`. It is **not reachable by import** from the scope directory. | (b)/out-of-scope |
| **F3** | `nostr-sdk` is **neither declared nor pinned** anywhere in the repo, though the entire in-scope security property depends on it (its FFI implements the wrap, and its Python stub enforces the send type-gate). | supporting finding |

A false "none found" is worse than a flagged false positive, so **F1 and F2 are reported explicitly
even though neither is a reachable bypass of the gift-wrap guarantee**. Neither is reachable as a
*fallback* of the wrapping path; the reasoning is in §2.

---

## 1. Evidence — every command executed (verbatim) and its result

Commands were run from the repo root unless the label says otherwise. `rc=` is the exit status of the
last command in the chain; where a pipe was used the exit status is the pipe's, so the piped checks
were re-run without the pipe where the distinction mattered (recorded as `b` suffixes).

| # | Verbatim command | Result |
|---|---|---|
| C-B1 | `rg -ni "plaintext\|plain_text\|plain text\|unencrypted\|un-encrypted\|cleartext\|clear_text\|in_the_clear" firmware/e80-stm32-bench/tools/` | 2 hits: `e80_board_relay.md:1439`, `e80_bench_ctl.py:1612` |
| C-B2 | `rg -ni "no_wrap\|nowrap\|skip_wrap\|skipwrap\|dont_wrap\|without_wrap\|disable_wrap\|wrap=false\|unwrapped\|wrap_enabled\|use_wrap" firmware/e80-stm32-bench/tools/` | 7 hits, **all** `unwrapped` = `UnwrappedGift` *receive*-side; zero wrap-suppression hits |
| C-B3 | `rg -ni "\bbypass\b\|\bfallback\b\|\braw\b\|\bunsafe\b\|\bunprotected\b\|\binsecure\b\|\blegacy\b\|\bplain\b" firmware/e80-stm32-bench/tools/` | 100+ hits, **all** CSV/legacy-format, CH340-port-detect, `--skip-fw-check`, `stop_verify.py:27` openocd-path bypass. None event-emission |
| C-B4 | `rg -ni "TODO\|FIXME\|HACK\|XXX\|BUG:\|WORKAROUND\|TEMP:\|TEMPORARY\|DEFERRED\|not implemented\|unimplemented" firmware/e80-stm32-bench/tools/` | 26 hits, **all** `tempfile.NamedTemporaryFile/TemporaryDirectory` (matched `TEMP`); zero wrap-related TODO/FIXME |
| C-B5 | `rg -ni "kind\s*:?\s*=\s*1\b\|kind\s*:?\s*1\b\|Kind::TextNote\|KIND_TEXT_NOTE\|TextNote\|text_note\|EventBuilder\|Event::new\|build_event\|create_event\|UnsignedEvent\|\.kinds\(" firmware/e80-stm32-bench/tools/` | **ZERO kind-1/text-note hits.** 6 `UnsignedEvent.from_json` (all kind 25910) + 3 `.kinds([...KIND_GIFT_WRAP])` |
| C-B6 | `rg -n -A6 "UnsignedEvent\.from_json" firmware/e80-stm32-bench/tools/` | All 6 inner events carry `"kind": KIND_CVM_RPC` (or literal `25910`). **No kind 1, no kind 13.** |
| C-B7 | `rg -l "def gift_wrap\|class UnwrappedGift" --glob "*.py" .` + `find . -name "nostr_sdk*"` | No vendored SDK in-repo — SDK is an installed dep (located via lane A) |
| C-B8 | `rg -n "KIND_[A-Z_]+\s*=\|^KIND\|\"kind\"" firmware/e80-stm32-bench/tools/*.py` | Only two kinds exist in scope: `KIND_CVM_RPC=25910`, `KIND_GIFT_WRAP=1059`. No third kind. |
| C-B9 | `rg -n "send_event\|\.publish\|publish_event\|add_event\|broadcast" firmware/e80-stm32-bench/tools/*.py` | **4 send sites total**, every one `send_event(gw…)` where `gw = gift_wrap(...)` |
| C-B10 | `rg -n -B2 -A4 "gift_wrap\|from_gift_wrap" firmware/e80-stm32-bench/tools/*.py \| rg -n "except\|pass\|continue\|return\|raise\|gift_wrap"` | Wrap/send error handling: `raise` only (`cvm_campaign.py:183`), no swallow |
| C-B11 | `rg -n '"EVENT"\|\x27EVENT\x27\|websockets\|ws\.send\|ws_send\|socket\.send' firmware/e80-stm32-bench/tools/*.py` | **rc=1, zero hits** — no raw NIP-01 EVENT frame or websocket write in scope |
| C-B12 | `rg -n "kind.{0,12}\b1\b\|\"\s*1\s*\"\|'1'\|…" firmware/e80-stm32-bench/tools/` | All `"1"` hits are CSV fields / `gps_fix` / argparse defaults. **No literal kind 1.** |
| C-B13 | `rg -ni "nostr\|gift_wrap\|1059\|25910\|kind" tools/` (repo-root) | **`tools/gh_ngit_watchdog.py:273 POST_TO_NOSTR kind:int=1`; :281 `nak event -k 1 -c content`** (all 5 hits at :273,:281,:444,:469,:501 — one emitter) |
| C-B14 | `rg -ni "nostr\|gift.?wrap\|kind\|1059\|25910\|encrypt\|plaintext" e80_board_relay.md` | 1 hit: `:1439` "The TCP port is unencrypted and unauthenticated" |
| C-B15 | `rg -n "cvm\|nostr\|relay" Makefile` (in `tools/`) | **rc=1, zero hits** — no Make target in the scope dir touches CVM |
| C-B16 | `rg -n "class .*Relay\|TCP\|tcp\|socket\|plaintext\|unencrypted\|fallback" e80_board_server.py cvm_board_server.py` | `e80_board_server.py` = TCP board server; `cvm_board_server.py:6` "**Replaces** the TCP-only e80_board_server.py" |
| C-B17 | `rg -ni "transport\|fallback\|fall back\|tcp\|nostr\|use_cvm\|degrade\|downgrade" cvm_campaign.py` | Only `transport=` **test seam** (`:88, :101, :143, :153`) — no CVM→TCP fallback |
| C-B18 | `rg -n "class CVMClient\|self\.transport\|transport=" cvm_campaign.py test_cvm_board_server.py` | `transport` is set **only** by tests (`test_cvm_board_server.py:406,439,440,525,526,564,565`) |
| C-B19 | `rg -n 'post_to_nostr\|"nak"\|\bnak\b.*event\|-k\",\s*str\|kind.*=\s*1\b…' --glob "*.py" --glob "*.sh" .` | 6 hits, **all** in `tools/gh_ngit_watchdog.py` |
| C-B20 | `rg -nli "plaintext\|unencrypted\|kind 1\b\|kind-1\b\|kind: 1\b" --glob "*.py" --glob "*.md" --glob "*.sh" .` | 16 files: mostly docs/cross-track spec; code files = `e80_board_relay.md`, `tools/gh_ngit_watchdog.py`, `tracker/…/test_nostr_roundtrip.py` |
| C-B21 | `rg -n "REPO_TOOLS\|import [a-z_]+" e80_bench_ctl.py` | `_REPO_TOOLS` (repo-root `tools/`) is inserted into `sys.path`; **only** import taken from it is `firmware_hash_gate` (`:50`) |
| C-B22 | `rg -ni "cvm\|nostr\|gift\|wrap\|relay" e80_bench_ctl.py` | Only `wrap_extra` / "preset wraps" band-swap arithmetic — **no Nostr** |
| C-B23 | `rg -n "kind\|publish\|1059\|25910\|gift\|wrap\|plaintext" tracker/firmware/test/integration/test_nostr_roundtrip.py` | `:146 kind: 1`, `:30 --kind 1`, `:277 relay_send_nostr …` — **out-of-scope** (different track; drives `balloon-fresh` firmware, needs PCB-V2 boards) |
| C-B24 | `rg -no "docs/[A-Za-z0-9_./-]+\.md…" firmware/e80-stm32-bench/tools/*.py` | Tools reference `docs/DESIGN-contextvm-adaptive.md` (from `cvm_board_server.py:19`) + 7 others |
| C-B25 | `rg -n "log\(.*(payload\|content\|inner\|rpc)" cvm_*.py` | 3 hits; **no** call logs the payload/rumor content |
| C-B26 | `rg -n "rumor\(\)\|inner\.content\|\.content\(\)" firmware/e80-stm32-bench/tools/*.py` | 6 hits; content only ever goes into `json.loads(...)`, never into a log |
| C-B27 | `rg -ni "plaintext\|unencrypted\|unwrapped\|no gift\|without gift\|skip.*wrap\|kind.?1\b\|text note" docs/DESIGN-contextvm-adaptive.md docs/plans/cvm-e28-integration-audit.md` | `DESIGN:69` privacy table; `DESIGN:131,343` unwrap; `cvm-e28:135` "**NOT plaintext kind 30315, which leaks RF intel**" |
| C-B28 | `sed -n '60,80p'` + `sed -n '330,350p' docs/DESIGN-contextvm-adaptive.md` | Privacy table: `TCP board server = plaintext`, `CVM (Nostr) = NIP-44 gift wrap`. Failure table: "Decryption fail (bad wrap) → Log + skip" |
| C-B29 | `sed -n '125,145p' docs/plans/cvm-e28-integration-audit.md` | Coordinator schedule published as "**gift-wrapped kind 1059** … NOT plaintext kind 30315" |
| C-B30 | `sed -n '1,35p' tracker/firmware/test/integration/test_nostr_roundtrip.py` | Preamble: needs **balloon-fresh** firmware + PCB-V2 boards → out of scope, no import edge |
| C-B31 | `rg -n "7780\|BoardTCPServer\|e80_board_server\|BoardClient\|_ClientTransport" firmware/e80-stm32-bench/tools/*.py` | TCP-7780 client = `e80_range_test.py`; `cvm_board_server.py` reuses `e80_board_server` **only** for `BoardController`/detection (`:59, :653`), not transport |
| C-B32 | `sed -n '725,809p' cvm_board_server.py \| rg "add_argument\|--"` | CLI: `--role/--port/--relays/--server-hex/--nsec/--allowed-client-npubs/--configs`. **No `--plain`, `--debug`, `--insecure`, `--no-wrap`** |
| C-B33 | `rg -n "add_argument\|--plain\|--no-\|--skip\|--debug\|--insecure\|--raw" cvm_campaign.py` | Full flag list; only `--dry-run`. **No wrap bypass flag** |
| C-B34 | `rg -ni "fallback\|fall back\|plaintext\|bypass\|degrad\|unavailable" docs/DESIGN-contextvm-adaptive.md` | **Single hit: `:69` privacy table.** No plaintext-fallback design anywhere |
| C-B35 | `find <repo> -name "*.py" -size +100k` | No in-repo SDK |
| C-B36 | `rg -ni "nostr\|kind\|gift\|wrap\|25910\|1059" e80_board_server.py` | **rc=0, 1 hit** = `:219` "TCP server **wrapping** a BoardController" (control-flow verb, not crypto) |
| C-B37 | `rg -n "kind.{0,6}13\b\|…\|seal" firmware/e80-stm32-bench/tools/*.py` | **rc=1, zero hits** — no kind-13/seal in scope (agrees with lane A) |
| C-B38 | `git status --short firmware/e80-stm32-bench/tools/ docs/` | Only pre-existing `??` docs from other sessions; no modification by this recon |
| C-B39 | `rg -n "nostr_sdk\.py" docs/RECON-duplicate-giftwrap-paths.md` | Lane A resolved the SDK at `/home/c03rad0r/.local/lib/python3.13/site-packages/nostr_sdk/nostr_sdk.py` |
| C-B40 | `rg -l "gift_wrap_from_seal" balloon-fresh balloon-e80bench mesh-stack` | Only this repo's lane-A report — no in-repo caller |
| C-B41 | `rg -ni "plaintext\|unencrypted\|cleartext\|\bfallback\b\|\bbypass\b\|insecure" <SDK>` | **All `bypass` hits are uniffi boilerplate** ("Lightly yucky way to bypass the usual `__init__` logic"); `plaintext` = doc wording of `human-readable summary`. No crypto bypass |
| C-B42 | `rg -n "KIND_TEXT_NOTE\|Kind::TextNote\|TextNote\|text_note\|Kind\(1\)\|kind=1\b" <SDK>` | Only **`EventBuilder.text_note`** FFI plumbing (`:37038`) — an API that *exists* but has **zero in-scope callers** (C-B5) |
| C-B43 | `sed -n '49240,49300p' <SDK>` | `gift_wrap(signer, receiver_pubkey, rumor: UnsignedEvent, extra_tags)` @49245; `gift_wrap_from_seal(receiver, seal: Event, …)` @49280 — **both always build kind 1059**; neither has a plaintext branch |
| C-B44 | `rg -n "async def send_event\|def publish\|async def sign_event\|UnsignedEvent" <SDK> \| rg -i "send_event\|sign_event\|def publish"` | `Client.send_event(self, event: "Event")` @33739; `sign_event(self, unsigned_event: UnsignedEvent)` @30921/31051 |
| C-B45 | `sed -n '37038,37052p' <SDK>` | `EventBuilder.text_note` body = pure FFI call, NIP-01 cited — reachable only if *called* |
| C-B46 | `rg -n -A1 "send_event\(" firmware/e80-stm32-bench/tools/*.py` | All 4 send sites receive `gw` / `gw2` (gift wraps) |
| C-B47 | `rg -n "sign_event\|Seal\|seal\|EventBuilder\|\.sign\(" firmware/e80-stm32-bench/tools/*.py` | **rc=1, zero hits** — no in-scope signing, sealing or builder use |
| C-B48 | `sed -n '33739,33752p' <SDK>` | `send_event` begins `_UniffiConverterTypeEvent.check_lower(event)` → **runtime type gate: an `UnsignedEvent` is rejected** |
| C-B49 | `rg -ni "nostr\|kind\|gift\|wrap\|1059\|25910" e80_range_test.py` | **rc=1** — the TCP client speaks JSON board protocol only; emits no Nostr event at all |
| C-B50 | `rg -n "kind.*1\b\|== 1\b\|as_u16" test_cvm_board_server.py` | `:485 assertEqual(inner_result.kind().as_u16(), 25910)` — the one kind assertion expects **25910** |
| C-B52b | `rg -ni "nostr" pyproject.toml; rg -ni "nostr-sdk" uv.lock` | **rc=1 and rc=1** — `nostr-sdk` is **not declared or pinned** anywhere |
| C-B53 | `rg -n "pynostr\|import nostr\b\|from nostr\b" firmware/e80-stm32-bench/tools/` | **rc=1** — a second Nostr lib (`pynostr 0.7.0`) is installed but never imported in scope |

Audited SDK identity (for reproducibility): `nostr-sdk==0.44.2`,
`/home/c03rad0r/.local/lib/python3.13/site-packages/nostr_sdk/nostr_sdk.py`,
sha256 `d6bb2552ceb73c107f45827ee91e7ab19fcf9ae9570eb08473989ccae0aac595`, 49686 lines.

---

## 2. Candidate table — every hit annotated

### 2.1 Event emission sites reachable from scope

| # | Absolute path | Line | Enclosing symbol | Judgement |
|---|---------------|------|------------------|-----------|
| 1 | `/home/c03rad0r/repos/balloon-e80bench/firmware/e80-stm32-bench/tools/cvm_board_server.py` | 573–581 | `CVMBoardServer._send_reply()` | **(a-adjacent) wrapped.** Inner rumor `kind=KIND_CVM_RPC(25910)` (:575) → `gift_wrap` (:580) → `send_event(gw)` (:581). Reachable; emits only kind 1059. |
| 2 | `/home/c03rad0r/repos/balloon-e80bench/firmware/e80-stm32-bench/tools/cvm_campaign.py` | 166–180 | `CVMClient._call_via_nostr()` | **wrapped.** Inner `kind=KIND_CVM_RPC` (:168) → `gift_wrap` (:179) → `send_event(gw)` (:180). |
| 3 | `/home/c03rad0r/repos/balloon-e80bench/firmware/e80-stm32-bench/tools/cvm_campaign.py` | 198–209 | `CVMClient._call_via_nostr()` retry branch | **wrapped.** Same shape, `gift_wrap` (:208) → `send_event(gw2)` (:209). |
| 4 | `/home/c03rad0r/repos/balloon-e80bench/firmware/e80-stm32-bench/tools/cvm_relay_test.py` | 74–83 | `test_relay_*` diagnostic self-wrap | **(b) diagnostic.** `kind=KIND_CVM_RPC` (:76) → `gift_wrap` (:82) → `send_event` (:83). |
| 5 | `/home/c03rad0r/repos/balloon-e80bench/firmware/e80-stm32-bench/tools/test_cvm_board_server.py` | 471–481 | `TestGiftWrapRoundTrip.test_wrap_and_unwrap_preserves_payload()` | **(b) test only.** Asserts inner kind == 25910 at :485. |
| 6 | `/home/c03rad0r/.local/lib/python3.13/site-packages/nostr_sdk/nostr_sdk.py` | 49245 / 49280 | `gift_wrap()` / `gift_wrap_from_seal()` | **(c) latent.** Both are wrap-only; `gift_wrap_from_seal` has zero in-scope callers (C-B40). Neither can emit plaintext. |

### 2.2 Flagged candidates (not bypasses, but reported for a human decision)

**F1 — unencrypted TCP control plane, documented.**

| Absolute path | Line | Enclosing symbol | Judgement |
|---|---|---|---|
| `…/firmware/e80-stm32-bench/tools/e80_board_server.py` | 218 (`class BoardTCPServer`), 221 (`host="0.0.0.0", port=7780`), 417 | `BoardTCPServer` / `run_server()` | **(b) + flagged.** Plaintext JSON-line TCP board control. Pre-existing; `cvm_board_server.py:6` states CVM "**replaces**" it, i.e. CVM is the successor, not a fallback consumer. |
| `…/firmware/e80-stm32-bench/tools/e80_range_test.py` | 18–19, 92, 549–552 | `main()`, `BoardClient.__init__` | **(b) + flagged.** Drives the TCP transport on 7780. `C-B49` (rc=1) proves it emits **no Nostr event at all** — so it neither bypasses nor leaks a wrap. |
| `…/firmware/e80-stm32-bench/tools/e80_board_relay.md` | 1439 | §14 "Known Limitations" | **doc.** "The TCP port is unencrypted and unauthenticated." |

**F2 — literal kind-1 plaintext poster, out of scope and not import-reachable.**

| Absolute path | Line | Enclosing symbol | Judgement |
|---|---|---|---|
| `/home/c03rad0r/repos/balloon-e80bench/tools/gh_ngit_watchdog.py` | 273 | `def post_to_nostr(content: str, config: dict, kind: int = 1)` | **(b)/out-of-scope.** Posts a **kind-1 text note** via `nak` with `content` in cleartext. |
| `/home/c03rad0r/repos/balloon-e80bench/tools/gh_ngit_watchdog.py` | 281 | `post_to_nostr()` | **(b)/out-of-scope.** `cmd = ["nak","event", … "‑k", str(kind), "‑c", content]` — the plaintext emission itself. |
| `/home/c03rad0r/repos/balloon-e80bench/tools/gh_ngit_watchdog.py` | 444, 469, 501 | `main()` / `mirror` paths | **(b)/out-of-scope.** Three callers: attention summary, per-item cross-post, full-report mirror (`report[:5000]`). |

Reachability reasoning for F2: this file sits in the **repo-root** `tools/`, not the scope `tools/`.
`e80_bench_ctl.py:44-50` inserts repo-root `tools/` on `sys.path` and takes exactly **one** import
from it — `firmware_hash_gate` (C-B21). No in-scope file imports `gh_ngit_watchdog` (C-B13 shows the
only hits are its own docstring); it is a manual/standalone CLI (`python3 gh_ngit_watchdog.py`). It is
therefore **not reachable from the scope directory's code paths**. It is flagged because it is a real
kind-1 plaintext emitter living in *this repo*, and a reader of the repo could conflate the two
`tools/` directories.

**F3 — undeclared, unpinned security-critical dependency.**

| Absolute path | Line | Enclosing symbol | Judgement |
|---|---|---|---|
| `…/firmware/e80-stm32-bench/tools/cvm_board_server.py` | 397, 491, 541, 571, 627 | `CVMBoardServer.__init__()` / `serve()` / `_handle_request()` / `_send_reply()` / `_load_keys()` | **supporting finding.** `import nostr_sdk` inside five functions. |
| `…/firmware/e80-stm32-bench/tools/cvm_campaign.py` | 103, 159, 262, 422 | `CVMClient.connect()` / `_call_via_nostr()` / notification handler / `_parse_pubkey()` | **supporting finding.** Same. |
| `…/pyproject.toml`, `…/uv.lock` | — | — | **C-B52b rc=1 both:** `nostr-sdk` appears in **neither**. `OPERATOR-QUICKSTART.md:28` instructs only `pip install pyserial`. |

Consequence: the wrap guarantee lives entirely in an **undeclared** dependency. The type-gate proved
in §3.3 is a property of `nostr-sdk==0.44.2`'s generated Python stub, and nothing in the repo pins
that version.

### 2.3 Kinds / construction vocabulary present in scope

| Candidate class | Result | Judgement |
|---|---|---|
| Literal `kind: 1` / `kind=1` | C-B5/C-B12 — zero | none found |
| `Kind::TextNote`, `KIND_TEXT_NOTE`, `TextNote`, `text_note` | C-B5 — zero in scope | none found |
| `EventBuilder` / `Event::new` / `build_event` / `create_event` | C-B7/C-B47 — zero | none found |
| Builder called with a **variable** kind that could resolve to 1 | C-B8 — no third kind constant exists; only 1059/25910 | none found |
| Kind deserialized from CLI/config/JSON | C-B32/C-B33 — no kind flag; C-B8 `"kind"` always literal 25910 | none found |
| Raw NIP-01 `["EVENT",…]` websocket frame | C-B11 — rc=1 | none found |
| Kind 13 / seal | C-B37 — rc=1 (agrees with lane A) | none found |

---

## 3. Implicit-bypass analysis

### 3.1 Fallible-wrap whose `Err` branch is swallowed → NOT present

`gift_wrap` is fallible (raises `NostrSdkError`). Every call site either lets it propagate or wraps it
in a `raise`:

- `cvm_campaign.py:179` → `except Exception as e: raise RuntimeError(f"send failed: {e}") from e` (:181–183).
- `cvm_campaign.py:208` → retry; its `except` (:211) catches **`asyncio.TimeoutError` only**, and re-raises `TimeoutError` (:213–214). A wrap failure is not swallowed.
- `cvm_board_server.py:580`, `cvm_relay_test.py:82` → no `except`; propagate to their handlers.

The two broad handlers (`_NotificationHandler.handle` at `cvm_board_server.py:610-614`,
`_ClientNotificationHandler.handle` at `cvm_campaign.py:279-280`) catch `Exception` and **only log** —
but they wrap *already-received* events, and the success path there is `UnwrappedGift.from_gift_wrap`
(:547 / :263). A decryption failure therefore ends in `log + skip`, which is exactly the documented
behaviour (`DESIGN-contextvm-adaptive.md:343`) and is **fail-closed**: nothing is published.

### 3.2 Error-handling that continues with an unwrapped event → NOT present

The parse-failure path in `_handle_request` logs and **returns** (`cvm_board_server.py:551-554`;
`cvm_campaign.py:266` path likewise cannot publish). There is no branch that, on failure, substitutes
`inner` for `gw` and sends it.

### 3.3 Structural barrier — the publish API is type-gated

This is the strongest evidence and does not depend on reading every branch:

1. `Client.send_event(self, event: "Event")` (`nostr_sdk.py:33739`) opens with
   `_UniffiConverterTypeEvent.check_lower(event)` (C-B48). An `UnsignedEvent` — the only shape this
   code ever constructs — **fails the gate**.
2. Only two calls can produce an `Event` from an in-scope rumor: `sign_event(UnsignedEvent)` and
   `gift_wrap(signer, pk, UnsignedEvent)`. **`sign_event` has zero in-scope callers** (C-B47, rc=1).
3. Therefore the sole `Event` this code can reach a relay with is the output of `gift_wrap`, which
   per its own FFI binding always yields a kind-1059 outer event (C-B43).

To emit a plaintext event from this scope one would have to call `EventBuilder.text_note(...)` — which
exists in the reachable SDK (`nostr_sdk.py:37038`, C-B42) but has **zero in-scope callers** (C-B5).
That is a latent capability of the dependency, not a bypass in the code under audit.

### 3.4 Logging / telemetry printing pre-wrap contents → NOT a leak

C-B25/C-B26: the six `rumor()`/`content()` reads feed `json.loads(...)` only. The RPC log line
(`cvm_board_server.py:562-565`) prints `rpc.get('id')`, the tool *name*, elapsed time and an error
*message* — **not** `payload` or content. So the pre-wrap JSON-RPC payload is never written to logs,
telemetry or the CSV artifacts.

---

## 4. Conclusion

- **Primary claim, in-scope:** **`no plaintext/kind-1 bypass found`** in
  `firmware/e80-stm32-bench/tools/`.
  - Zero kind-1 / text-note construction in scope (C-B5, C-B8, C-B12, C-B42-caller-check).
  - All 4 send sites publish only gift-wrapped kind-1059 events (C-B9, C-B46); all 6 inner rumors are
    kind 25910 (C-B6); the single test kind assertion expects 25910 (C-B50).
  - The publish API rejects unsigned events, and no in-scope code signs or seals (C-B47, C-B48), so a
    plaintext publication is structurally unreachable from this code.
  - No wrap-suppression switch exists in code or CLI (C-B2, C-B32, C-B33).
  - No error path falls back to an unwrapped event; decryption failure is fail-closed (log + skip).
- **Flagged, not bypasses:** F1 (documented unencrypted TCP transport — a *parallel predecessor*, not
  a fallback of the wrap; its client emits no Nostr event whatsoever) and F2 (a real kind-1 plaintext
  poster elsewhere in the repo, not import-reachable from scope).
- **Supporting finding:** F3 — the whole guarantee rests on an **undeclared and unpinned**
  `nostr-sdk` (audited at 0.44.2, sha256 recorded above).

This lane did not falsify a *security* claim so much as confirm one: the CVM path is wrap-only. The
exposure surfaces are (F1) an unauthenticated plaintext transport that predates it and (F2) plaintext
kind-1 posting in an adjacent, unrelated tool — neither of which is a fallback *out of* gift wrapping.

## 5. Open questions (reachability not provable either way from this scope alone)

1. **F1 — is the TCP 7780 control plane still operated?** The code is live and documented, but no
   in-scope Make target starts it (C-B15 rc=1). Whether a deployment still runs
   `e80_board_server.py` (and on which network) cannot be determined from this repo alone. If it is
   ever run on an untrusted segment, the control plane is cleartext — per the doc's own footnote this
   is accepted for "a direct Ethernet cable or trusted Netbird network" only.
2. **F2 — is `tools/gh_ngit_watchdog.py` invoked by any cron/systemd unit?** It is not imported by any
   in-scope module (C-B13), but this recon cannot see the host's crontab or systemd units. If it runs
   on a schedule it publishes plaintext kind-1 notes (its own docstring advertises `--nose-mirror`-style
   mirroring), which may be intended but is a plaintext-by-design surface.
3. **F3 — which `nostr-sdk` version does a real deployment resolve to?** Not pinned (C-B52b). The
   type-gate argument in §3.3 was verified against 0.44.2 only. A future major (or the co-installed
   `pynostr 0.7.0`, currently unimported — C-B53) could change the emission primitives.
4. **Not audited (out of scope, declared):** `tracker/firmware/test/integration/test_nostr_roundtrip.py`
   publishes kind-1 plaintext **into the balloon-fresh firmware's relay store** over the radios
   (C-B23, C-B30). It requires two PCB-V2 `balloon-fresh` boards and belongs to another track's scope;
   it is recorded here because it is the second genuine kind-1 emitter reachable from this repo's tree,
   and it should be adjudicated by that track's lane, not this one.
