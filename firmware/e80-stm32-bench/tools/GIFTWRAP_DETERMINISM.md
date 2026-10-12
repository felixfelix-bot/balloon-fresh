# GIFTWRAP_DETERMINISM.md — canonical session serialization + choke-point contract

**Status:** SPEC. Read-only audit deliverable (card `t_2294dea3`, board `e80-bench`).
No production behaviour was changed by the audit; this file is the only addition.

**Audited revision (pin this — every line number below is valid here and nowhere else):**

```
repo   balloon-e80bench  (remote origin = https://github.com/felixfelix-bot/balloon-fresh.git)
branch pr/giftwrap-deterministic
commit 9455b07a40e6f36948131c1fe84cb5986671abf3   (pushed to origin, verified)
```

**Important base fact:** `origin/main` (`ce491f93`) does **not** carry
`firmware/e80-stm32-bench/tools/nostr_giftwrap.py`. The choke-point module exists only on
the gift-wrap branch family (`pr/nostr-giftwrap` `8138ff64`, `pr/giftwrap-deterministic`
`9455b07a`, `pr/keymaterial-env-sole-source` `b201428e`). **Implementation workers must cut
their worktree from `origin/pr/giftwrap-deterministic` (or a descendant), not from
`origin/main`, or the module they are told to edit will not exist.**

Existing adversarial recon of the construction paths already lives on `origin/main` — read
it instead of re-deriving it:
`docs/RECON-duplicate-giftwrap-paths.md` (lane A),
`docs/RECON-lane-B-plaintext-fallback-paths.md` (lane B),
`docs/RECON-cfg-gated-wrap-paths.md` (lane C),
`docs/adr/033-giftwrap-single-construction-path.md` (ADR-033, the pinning decision).

---

## 1. The choke-point (path + symbol + lines)

**Module:** `firmware/e80-stm32-bench/tools/nostr_giftwrap.py` (738 lines, 30 903 bytes).

| Role | Symbol | Lines |
|---|---|---|
| **Construction choke-point (the one the card means)** | `build_gift_wrap(payload, tx_npub, signer, *, author=None, created_at=None)` (async) | 651–702 |
| ↳ the **only** `nostr_sdk.gift_wrap(...)` call in the module | `await nostr_sdk.gift_wrap(signer, nostr_sdk.PublicKey.parse(recipient), unsigned)` | **694** |
| Inner rumor builder | `build_inner_rumor(payload, tx_npub, *, author=None, created_at=None)` | 619–648 |
| **Emission choke-point** | `publish_gift_wrap(client, event, *, payload=None, tx_npub=None)` (async) | 709–725 |
| ↳ the only relay write | `await client.send_event(event)` | **724** |
| Failover-layer entry point | `publish_armed(payload, tx_npub, signer, client, *, author=None, created_at=None)` | 728–738 |
| Hard kind guard | `assert_gift_wrap_kind(event, *, context="emit")` → `PlaintextKindError` | 514–533 |
| Recipient guard | `assert_recipient_tag(event, tx_npub)` → `RecipientMismatchError` | 536–555 |
| Plaintext-leak guard | `assert_no_plaintext_leak(event, payload, *, context="emit")` → `PlaintextLeakError` | 594–612 |
| Canonical constant `KIND_GIFT_WRAP` (= 1059) | imported from `cvm_sync` (definition `cvm_sync.py:68`) | import at **93** |
| Forbidden plaintext kind | `KIND_PLAINTEXT_TALLY = 30315` | 132 |

Guard order at the choke-point is deliberate and must not be reordered: the kind assertion
runs **before** `client.send_event`, so a non-1059 event is rejected, never queued on the
relay pool. The module never signs anything itself; it reuses the `nostr_sdk` FFI primitive.

**Single-path pin:** `tools/test_giftwrap_single_path.py` (on the branch; also in the
Makefile gate) enumerates the expected `gift_wrap` / `from_gift_wrap` call count per file
(lines 17–21), the modules allowed to declare a local `KIND_GIFT_WRAP` (lines 24–29) and
forbids `gift_wrap_from_seal` (`FORBIDDEN_NAMES`, line 31). **Any new construction path or
extra call in `nostr_giftwrap.py` fails that test.**

---

## 2. Is it the only construction path? (grep evidence)

Command (run from `firmware/e80-stm32-bench/tools/`):

```
grep -rn --exclude-dir=__pycache__ -E '\b1059\b|KIND_GIFT_WRAP|GiftWrap|gift_wrap|giftwrap' .
grep -rn --include=*.py --include=*.rs --exclude-dir=.git -E '\.gift_wrap\(|nostr_sdk\.gift_wrap\(|gift_wrap\(' . | grep -v test_
```

Every **production call site that emits a kind-1059 event**, classified:

| # | Site | Classification |
|---|---|---|
| 1 | `nostr_giftwrap.py:694` | **INSIDE the audited choke-point** (`build_gift_wrap`) |
| 2 | `cvm_board_server.py:580` | **NOT the choke-point** — separate CVM server RPC reply wrap (pre-existing, ADR-033 known site) |
| 3 | `cvm_campaign.py:179` | **NOT the choke-point** — campaign client request wrap (pre-existing) |
| 4 | `cvm_campaign.py:208` | **NOT the choke-point** — campaign client retry wrap (pre-existing) |
| 5 | `cvm_relay_test.py:82` | **NOT a construction path in production** — diagnostic relay ping tool |
| 6 | `test_cvm_board_server.py:477` | **Test only** — round-trip unit test |

`KIND_GIFT_WRAP = 1059` is declared in **three** modules independently
(`cvm_sync.py:68`, `cvm_board_server.py:74`, `cvm_campaign.py:64`); `nostr_giftwrap.py`
imports it from `cvm_sync` rather than re-declaring it.

**Say it loudly, as lane A already did:** the claim "exactly one kind-1059 construction
path exists" is **FALSE in its literal, tree-wide form** — there are 5 emit sites (4
non-test + 1 test). It is **TRUE in the narrow, load-bearing form**: the ARMED/range-sync
CVM publish path has exactly **one** construction site and **one** emission site, both in
`nostr_giftwrap.py` (`build_gift_wrap` → `publish_gift_wrap`). All 5 sites route through the
same upstream leaf primitive `nostr_sdk.gift_wrap(...)`; ADR-033 governs that primitive, not
"one file". Do not silently narrow or widen either claim.

**No plaintext / kind-1 emission from this path — confirmed.** On this revision there is
zero production construction of kind 1 (`grep -rn -E 'KIND_TEXT_NOTE|Kind\(1\)|kind[[:space:]]*[:=][[:space:]]*1\b'`
returns only test literals: `test_nostr_giftwrap.py:318` `bad_kind in (1, 25910, 30023,
30315, 20000)` and `test_nostr_giftwrap_realsdk.py:126` kind 30315). The only inner kind
authored is `INNER_KIND = 25910` (`nostr_giftwrap.py:126`); the only forbidden plaintext
kind named is 30315. Every emission is gated by `assert_gift_wrap_kind`, which raises rather
than downgrades.

---

## 3. Canonical session serialization — **byte-exact contract**

This is the serialization both implementation workers MUST reproduce byte-for-byte. It is
already implemented on the audited revision; the spec freezes it, it does not invent it.

### 3.1 The session object ("payload")

The payload is a `Mapping` (the ARMED interface object minted by `cvm_sync`). Required ARMED
fields (`cvm_sync.ARMED_REQUIRED`, `cvm_sync.py:82`):
`session_id`, `stop`, `t_ready_utc`, `preset_hash`, `seq` — plus `type`, `created_at`,
`author` in practice. Canonical fixtures used by the existing tests:

```python
TX_HEX   = "79be667ef9dcbbac55a06295ce870b07029bfcdb2dce28d959f2815b16f81798"
TX_NPUB  = "npub10xlxvlhemja6c4dqv22uapctqupfhlxm9h8z3k2e72q4k9hcz7vqpkge6d"   # == TX_HEX
AUTHOR   = "aabbccddeeff00112233445566778899aabbccddeeff00112233445566778899"
PAYLOAD  = {"type": "ARMED", "session_id": "2608301440a3f", "stop": "stop-50m",
            "t_ready_utc": 1789000000, "preset_hash": "deadbeefcafe0001", "seq": 7,
            "created_at": 1788999990, "author": AUTHOR}
```

### 3.2 The serialization function

`canonical_session_bytes(payload, tx_npub, *, author=None, created_at=None) -> bytes`
(`nostr_giftwrap.py:183–199`):

```python
doc = {
    "author":     "" if author is None else str(author),
    "created_at": None if created_at is None else int(created_at),
    "payload":    _canonical_payload(payload),          # :168-180
    "recipient":  npub_to_hex(tx_npub),                 # :387-428, 64-char lowercase hex
}
return json.dumps(doc, sort_keys=True, separators=(",", ":"),
                  ensure_ascii=False).encode("utf-8")
```

Rules, exactly:

1. **Top-level shape:** a JSON **object** with exactly these four keys:
   `author`, `created_at`, `payload`, `recipient`. No more, no fewer (adding a field is a
   breaking change to the whole contract — it changes every derived key).
2. **Key order is irrelevant:** `sort_keys=True` sorts recursively, so *dict* insertion
   order never affects the bytes. **List/tuple order IS preserved** and is therefore
   load-bearing.
3. **Separators:** `(",", ":")` — no spaces anywhere.
4. **Encoding:** `ensure_ascii=False` then `.encode("utf-8")`. Non-ASCII characters are
   emitted raw as UTF-8 (they are **not** `\uXXXX`-escaped). No BOM, no trailing newline.
5. **Value domain:** `None`, `bool`, `int`, `float`, `str`; `Mapping` → object (keys
   coerced with `str(key)`); `list`/`tuple` → array. **Any other type raises `TypeError`**
   (`_canonical_payload`, lines 177–180). Do not pass `datetime`, `bytes`, `Decimal`, sets,
   or numpy scalars: the serialization is only defined for JSON-native values. Prefer `int`
   for all timestamps (`t_ready_utc`, `created_at`, `seq`).
6. **`recipient` is always normalized:** `npub_to_hex()` accepts `npub1…` (bech32,
   checksum-verified) or 64-char hex, and returns **64-char lowercase hex**. Two callers
   passing the same recipient as bech32 vs hex MUST get identical bytes.
7. **`author` is NOT normalized by the serializer** — it is `str(author)` verbatim (or `""`
   when `None`). Contract: **pass lowercase 64-char hex**, or byte-equality across callers
   is not guaranteed. (`build_inner_rumor` falls back to `payload["author"]`, line 638.)
8. **`created_at` in the serialization is the explicit keyword argument only** (`None` when
   omitted). It is *not* the derived rumor timestamp — see §5.

### 3.3 Byte-exact test vector (verify your implementation against this)

Inputs: `PAYLOAD` above, `TX_NPUB`, `author=AUTHOR`, `created_at=None`.

```
len(canonical_session_bytes) = 414
bytes (UTF-8, shown verbatim):
{"author":"aabbccddeeff00112233445566778899aabbccddeeff00112233445566778899","created_at":null,"payload":{"author":"aabbccddeeff00112233445566778899aabbccddeeff00112233445566778899","created_at":1788999990,"preset_hash":"deadbeefcafe0001","seq":7,"session_id":"2608301440a3f","stop":"stop-50m","t_ready_utc":1789000000,"type":"ARMED"},"recipient":"79be667ef9dcbbac55a06295ce870b07029bfcdb2dce28d959f2815b16f81798"}

sha256(canonical bytes)          = bde5824afeda55bde22f34f9249ddfad31fefebf60e0651e285e4d91fe89051b
session_fingerprint (HMAC below) = e04d9c9a4f682f0dc3113de669783e4f70a6d2ca2f31ee316acd9af0a179d219
derive_ephemeral_secret_key      = 528eb7d6b7acb25bcf91cb2f1f7a39cd34b2cfc5b03826d9980673afd099e7b1
derive_created_at                = 1788999990
```

Reordering the payload mapping (`dict(reversed(items))`) gives **identical bytes**
(verified) — that is the invariant that makes the fingerprint a pure function of content.

### 3.4 Fingerprint

`session_fingerprint(payload, tx_npub, *, author=None, created_at=None) -> str`
(`:202–213`):

```
HMAC-SHA256(key = SESSION_DOMAIN_LABEL, msg = canonical_session_bytes(...)).hexdigest()
```

(Note the key/msg assignment: the domain label is the **HMAC key**, the canonical bytes are
the **message**. Do not swap them.)

---

## 4. Domain-separation labels (fixed strings — do not invent new ones)

| Constant | Value (bytes) | Used as | Line |
|---|---|---|---|
| `SESSION_DOMAIN_LABEL` | `b"e80-cvm/nip59/session/v1"` | HMAC-SHA256 **key** for `session_fingerprint` | 152 |
| `EPHEMERAL_DOMAIN_LABEL` | `b"e80-cvm/nip59/ephemeral/v1"` | HKDF-SHA256 **salt AND info** for `derive_ephemeral_secret_key` | 155 |

The task text's illustrative example `b"e80-giftwrap-ephemeral-key-v1"` is **superseded by
this spec** — the labels above are what the branch code and its 55 tests pin. Introducing a
second/renamed label would fork the derivation and break the byte contract. If a worker
believes a different label is required, **stop and report the gap** (`kanban_block`), do not
pick one unilaterally.

### 4.1 Ephemeral scalar derivation

`derive_ephemeral_secret_key(...)` (`:231–249`):

1. `ikm   = canonical_session_bytes(payload, tx_npub, author=..., created_at=...)`
2. `okm   = HKDF-SHA256(ikm, salt=EPHEMERAL_DOMAIN_LABEL, info=EPHEMERAL_DOMAIN_LABEL, L=32)`
   — RFC 5869 extract-then-expand, stdlib `hmac`/`hashlib` only (`_hkdf_sha256`, `:216–228`).
3. `scalar = int.from_bytes(okm, "big") % (SECP256K1_ORDER - 1) + 1`
   (`SECP256K1_ORDER` = secp256k1 n, `:158`; line 248)
4. return `"%064x" % scalar` → 64 lowercase hex chars, guaranteed in `[1, n-1]`.

`build_gift_wrap` re-checks `0 < int(derived, 16) < SECP256K1_ORDER` and raises
`GiftWrapError` otherwise (`:682–687`) — the derivation may never silently degrade.

---

## 5. `created_at` — frozen, never wall-clock

`derive_created_at(payload, tx_npub, *, author=None, created_at=None) -> int`
(`:252–272`), resolution order:

1. explicit `created_at` keyword argument;
2. `payload["created_at"]`;
3. `payload["t_ready_utc"]`;
4. `payload["t0"]`;
5. deterministic fallback `1_700_000_000 + (int(session_fingerprint(...), 16) % (1 << 31))`.

The wall clock is never consulted. `build_inner_rumor` uses it for the inner rumor
(`:646–647`).

**Byte-level asymmetry you must know (both are deterministic, they are not the same bytes):**

* key-derivation serialization uses `ensure_ascii=False`;
* the inner rumor **content** uses `json.dumps(body, sort_keys=True, separators=(",", ":"))`
  (`:643`) with the json default `ensure_ascii=True`.

So a payload containing non-ASCII text produces UTF-8 bytes in the derivation input and
`\uXXXX` escapes in the rumor content. Both are frozen; do not "harmonise" them without a
card that says so.

---

## 6. Randomness inventory

**Inside the derivation path (`nostr_giftwrap.py`): NONE.**
`grep -rnE "os\.urandom|secrets|random|uuid4|Nonce|Random" nostr_giftwrap.py` matches only
docstring/comment text (lines 66, 68, 69, 147, 149, 207, 218, 238, 260). The derivation uses
`hashlib` and `hmac` only. This is unchanged by the audit; keep it that way.

**Outside the choke-point (session minting / tooling — permitted, and inputs to the wrap):**

| File:line | Source | Relevance |
|---|---|---|
| `cvm_sync.py:54` | `import random` | session minting |
| `cvm_sync.py:97` | `nonce = "{:03x}".format(random.randrange(0x1000))` | the 3-hex part of `session_id` (`generate_session_id`) |
| `cvm_sync.py:232` | `await asyncio.sleep(random.uniform(lo, hi))` | ARMED re-broadcast jitter (10–15 s) |
| `cvm_sync.py:95, 113, 141, 158` | `time.time()` (incl. `created_at`) | ARMED/STARTED message minting |
| `cvm_relay_test.py:37` | `nostr_sdk.Keys.generate()` | diagnostic tool, fresh keypair |
| `buf_smoke_t3.py:180` | `os.urandom(args.size)` | **unrelated** (UART buffer smoke payload) |
| `cvm_board_server.py:558`, `cvm_campaign.py:186, 557, 563`, `e80_*` | `time.monotonic()` / `datetime.now()` | unrelated timing/logging |

**Rule:** randomness is permitted where a *session is minted* (a session is identified by
its fields, so a random `session_id` nonce is an **input**, not a derivation-path defect);
randomness is forbidden on the derivation path. Determinism is therefore *per session*: same
session fields ⇒ same canonical bytes, same fingerprint, same inner rumor, same derived
ephemeral scalar.

---

## 7. Exact test invocation

Working directory: **`firmware/e80-stm32-bench/tools`** (flat test layout; tests are
`tools/test_*.py`, there is no `tests/` dir here).

```bash
cd firmware/e80-stm32-bench/tools

# full host suite (measured at 9455b07a, no hardware, ~9-11 s)
python3 -m pytest -q
#   => 862 passed, 8 skipped in 8.93s

# the gift-wrap subset
python3 -m pytest -q test_nostr_giftwrap.py test_giftwrap_determinism.py test_giftwrap_single_path.py
#   => 55 passed in 1.11s

# real-SDK suite (needs an interpreter with the Rust bindings)
/opt/miniconda/bin/python -m pytest -q test_nostr_giftwrap_realsdk.py
#   => 7 passed in 0.31s
```

* **Config:** `pytest.ini` at the **repo root** is tracked and **wins** over the root
  `pyproject.toml` — pytest prints `configfile: pytest.ini (WARNING: ignoring pytest config
  in pyproject.toml!)`. Running pytest from `tools/` collects `tools/test_*.py`.
* **conftest:** none anywhere under `firmware/e80-stm32-bench` (verified:
  `find . -maxdepth 3 -name conftest.py` is empty). No fixtures/env needed for the host suite.
* **Env:** host suite needs **no** environment variables and **no** `nostr_sdk`. The 8 skips
  are exactly `test_nostr_giftwrap_realsdk.py` (7) + `test_cvm_board_server.py:460`, all
  `nostr_sdk not installed`. `/opt/miniconda/bin/python` (3.13.11) has `nostr_sdk` 0.44.2;
  the default `python3` (Hermes venv 3.13.7, pytest 9.1.1) does not.
* **Makefile gate:** `firmware/e80-stm32-bench/Makefile:657–660` —
  `make range-test-host` runs `cd tools && $(PYTHON) -m pytest test_e80_range_split.py
  test_range_check.py test_nostr_giftwrap.py test_giftwrap_determinism.py
  test_giftwrap_single_path.py -v`. It enumerates files **explicitly**: a NEW test module is
  **not** auto-collected until it is added to that line. (`PYTHON ?= python3`, so set
  `PYTHON=/opt/miniconda/bin/python` to exercise the real-SDK path.)

---

## 8. Verified state of the determinism claim (READ BEFORE IMPLEMENTING)

A read-only probe at 9455b07a built the same wrap in three separate processes (fixed signer,
fixed payload, fixed recipient, `nostr_sdk` 0.44.2). Result:

```
process 1  outer_id=15fb968d…  outer_pubkey=07bdb891…  created_at=1791393631
process 2  outer_id=7c077b17…  outer_pubkey=2aa7fae5…  created_at=1791421904
process 3  outer_id=96d8c46c…  outer_pubkey=b6fff7c8…  created_at=1791478293

every run: derived_eph_secret = f98f6151…  (identical)
every run: fingerprint       = 2ab2ff50…  (identical)
```

Interpretation — this is the central open issue and both workers must agree on it:

* The **derivation half is deterministic and process-stable**: canonical bytes, fingerprint,
  derived ephemeral scalar, and the frozen inner-rumor `created_at` are identical across
  processes. That is the contract §3–§5 freezes.
* The **outer kind-1059 event is NOT process-stable**: `nostr_sdk.gift_wrap` generates the
  outer ephemeral key internally and stamps the outer `created_at` from the wall clock, and
  `build_gift_wrap` does **not** feed its derived scalar into that constructor. Idempotency
  today comes **only** from the in-process `_WRAP_CACHE` (`:164–165`, lookup `:674–677`,
  insert `:701–702`), i.e. repeated calls in the *same* process return the identical event
  object, but a restart re-signs a different outer event id.
* Cross-process determinism of the **outer** id therefore cannot be reached without either
  (a) hand-rolling the kind-1059 event, or (b) calling the `gift_wrap_from_seal` seam —
  **both forbidden by ADR-033 and pinned by `test_giftwrap_single_path.py`**
  (`FORBIDDEN_NAMES`), and any second `gift_wrap()` call in `nostr_giftwrap.py` breaks the
  per-file call-count pin.

**Consequence for the sibling cards:** the acceptance check "run two separate `python -c`
processes and confirm both print the same event id" (verifier card `t_9e0ca391`, item 4)
**fails on this revision**. Do not fake it, do not delete assertions to make it pass, and do
not hand-roll a constructor. Either the requirement is renegotiated with the operator (e.g.
"same id within one broker process / same message after relay dedupe") or ADR-033 must be
amended first — that is a human decision, and the ADR's own status line says acceptance is a
human action.

---

## 9. Frozen contract — the checklist both workers must keep byte-identical

1. Module path and choke-point symbol unchanged: `tools/nostr_giftwrap.py` /
   `build_gift_wrap` (one `nostr_sdk.gift_wrap` call) → `publish_gift_wrap` (one
   `send_event`).
2. `canonical_session_bytes` doc keys and values exactly as §3.2 (four keys, sorted keys,
   `(",", ":")`, `ensure_ascii=False`, UTF-8, recipient hex-normalized, author verbatim).
3. Labels unchanged and unswapped: `b"e80-cvm/nip59/session/v1"` (HMAC key),
   `b"e80-cvm/nip59/ephemeral/v1"` (HKDF salt=info).
4. HKDF-SHA256 → 32 bytes → `% (n-1) + 1` → 64 lowercase hex.
5. `created_at` order §5, wall clock never consulted on the derivation path.
6. No randomness on the derivation path; no kind-1/plaintext emission; no second
   construction path; `gift_wrap_from_seal` never used.
7. `test_giftwrap_single_path.py` stays green; the byte vector in §3.3 still matches.
