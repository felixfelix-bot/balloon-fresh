# TOLLGATE PROTO CALL-SITE & CONSUMER INVENTORY (ground truth, read-only recon)

Task: inventory `tollgate_payment_proto` call sites and consumers in `tracker/firmware`.
Repo: `~/repos/balloon-fresh/tracker/firmware`, branch `autonomous/mesh-baseline`, HEAD `fb36809`.
Worktree used: `/home/c03rad0r/worktrees/tg-proto-scan` (read-only; no firmware file modified).

Sources read in full: `main/app_task.cpp` (164 L), `main/test/test_relay_pipeline.c` (637 L),
`main/tollgate_payment_proto.h` (114 L), `main/tollgate_payment_proto.c` (53 L),
`main/test/test_tollgate_payment_proto.c` (334 L), `main/app_main.cpp` (tollgate region 575-649),
`main/relay_types.h` (23 L), `test/integration/test_tollgate_payack.py` (469 L).

## 0. METHOD / EVIDENCE (all observed, not asserted)

Compiled and RAN both host suites from this worktree:

    gcc -Wall -Wextra -O2 -I main -o /tmp/tg_proto \
        main/test/test_tollgate_payment_proto.c main/tollgate_payment_proto.c
    -> "=== Results: 83 passed, 0 failed ==="

    gcc -Wall -O2 -I main -I components/nostr_store/include -o /tmp/tg_relay \
        main/test/test_relay_pipeline.c main/tollgate_payment_proto.c \
        components/nostr_store/nostr_store.c
    -> "=== Results: 12/12 passed ==="
       (sizeof(relay_packet_t)=528, sizeof(nostr_event_t)=1276, sizeof(nostr_store_t)=10380)

Empirical ABI probe (`/tmp/probe.c`, linked against the real `tollgate_payment_proto.c`):

    sizeof(tollgate_msg_hdr_t)=8   sizeof(ack)=14  sizeof(pay)=2048  sizeof(nack)=130
    offsetof version/type/seq/payload_len/reserved = 0/1/2/4/6
    offsetof ack session_id/expires_unix/quota_bytes/price_sats = 0/4/8/12
    TG_MSG_PAY=1  TG_MSG_ACK=2
    encode(buf,8,ACK,7,NULL,0) = 8     (header-only EXACT FIT SUCCEEDS — not an error)
    decode(8 bytes) = 8 ; payload ptr = set   (points at data+8, one past end — see F4)

NOTE ON A RENDER TRAP: an initial `read_file` of `tollgate_payment_proto.h` displayed the
header struct WITHOUT the `version` and `reserved` members and displayed `tollgate_msg_type_t`
closing on the wrong line. The on-disk bytes (byte-dump + `git show autonomous/mesh-baseline:...`
+ `awk NR>=46&&NR<=76`) DO contain `uint8_t version;` (line 50) and `uint16_t reserved;`
(line 54). The struct is 8 bytes as the tests assert. Any inventory that "found" the members
missing is a mis-read of that render, not a repo defect. Ground truth = the byte dump.

---

## 1. SYMBOL TABLE

Format: name | kind | exact signature/definition | file:line | assumptions made by that consumer

### 1a. Functions (API surface)

| symbol | kind | exact signature (as written) | file:line | consumer assumptions |
|---|---|---|---|---|
| `tollgate_proto_encode` | fn | `int tollgate_proto_encode(uint8_t *buf, uint16_t buf_len, tollgate_msg_type_t type, uint16_t seq, const char *payload, uint16_t payload_len)` | decl `main/tollgate_payment_proto.h:94-96`; def `main/tollgate_payment_proto.c:14-33` | ret > 0 == bytes written (hdr+payload); ret == -1 == error. Callers pass buf=`pkt.data+1` (uint8_t*), buf_len=`RELAY_PACKET_MAX_SIZE-1` (511, an `int` literal narrowed to uint16_t), seq from a *widened* source (see §2 D1). |
| `tollgate_proto_decode` | fn | `int tollgate_proto_decode(const uint8_t *data, uint16_t len, tollgate_msg_hdr_t *hdr, const uint8_t **payload)` | decl `main/tollgate_payment_proto.h:107-109`; def `main/tollgate_payment_proto.c:35-54` | ret > 0 == sizeof(hdr) (8), NOT payload length; ret == -1 == invalid. `*payload` is set to `data+8` whenever `payload != NULL`, even for a zero-length payload (F4). |

### 1b. Structs / enums

| symbol | kind | exact definition | file:line | assumptions |
|---|---|---|---|---|
| `tollgate_msg_hdr_t` | struct (packed) | `{ uint8_t version; uint8_t type; uint16_t seq; uint16_t payload_len; uint16_t reserved; }` | `main/tollgate_payment_proto.h:49-55` | 8 bytes, offsets 0/1/2/4/6 (verified). Callers assume `seq` is *the* correlation key and read `.seq` after decode. |
| `tollgate_msg_type_t` | enum | `TG_MSG_PAY=0x01, TG_MSG_ACK=0x02, TG_MSG_NACK=0x03, TG_MSG_STATUS=0x04, TG_MSG_INFO=0x05, TG_MSG_REVOKE=0x06` | `main/tollgate_payment_proto.h:39-46` | Cast to `uint8_t` in encode; compared by value in the Python harness (duplicated literals — §2 D4). |
| `tollgate_pay_payload_t` | struct | `{ char token[2048]; }` | `main/tollgate_payment_proto.h:58-60` | Defined but NEVER used by any consumer — dead type. All PAY payloads are passed as raw `const char*`, not this struct. |
| `tollgate_ack_payload_t` | struct (packed) | `{ uint32_t session_id; uint32_t expires_unix; uint32_t quota_bytes; uint16_t price_sats; }` | `main/tollgate_payment_proto.h:63-68` | 14 bytes, offsets 0/4/8/12 (verified). Consumers only touch `.price_sats` (both zero it). No consumer ever sets session_id/expires_unix/quota_bytes → ACK conveys no session info (F3). |
| `tollgate_nack_payload_t` | struct (packed) | `{ int16_t error_code; char message[128]; }` | `main/tollgate_payment_proto.h:71-74` | 130 bytes. Referenced ONLY in the header; NO consumer constructs or encodes it (F2). |

### 1c. Constants / macros

| symbol | kind | definition | file:line | assumptions |
|---|---|---|---|---|
| `TOLLGATE_PROTO_VERSION` | macro | `1` | `main/tollgate_payment_proto.h:33` | encode writes it; decode rejects `hdr->version != 1`. Test pins version 0 and 255 both → -1. |
| `TOLLGATE_MAX_TOKEN_LEN` | macro | `2048` | `main/tollgate_payment_proto.h:36` | Only sizes `tollgate_pay_payload_t.token` (dead). NOTE the live CLI path truncates token at 511-9=502 bytes (§2 D5) — the macro is not enforced anywhere live. |
| `TG_MSG_*` | enum consts | see 1b | `main/tollgate_payment_proto.h:40-45` | Values 1..6. Live consumers use only `TG_MSG_PAY` and `TG_MSG_ACK`. |
| `TG_ERR_*` | macros (error codes) | `TG_ERR_INVALID_TOKEN(-1)`, `SWAP_FAILED(-2)`, `MINT_UNREACHABLE(-3)`, `ALREADY_PAID(-4)`, `RATE_LIMITED(-5)` | `main/tollgate_payment_proto.h:77-81` | Values −1..−5. NO consumer reads or emits any of them (F2). They are documentation-only. |

### 1d. Framing constants (relay layer, adjacent)

| symbol | kind | definition | file:line | assumptions |
|---|---|---|---|---|
| `RELAY_PACKET_MAX_SIZE` | macro | `512` | `main/relay_types.h:6` | Callers pass `RELAY_PACKET_MAX_SIZE - 1 = 511` as encode capacity to leave room for the 1-byte type tag. |
| `RELAY_TYPE_TOLLGATE_PAY` | macro | `0x02` | `main/relay_types.h:12` | First byte of the relay packet; proto bytes start at `data+1`. |
| `RELAY_TYPE_TOLLGATE_ACK` | macro | `0x03` | `main/relay_types.h:13` | Set by the ACK *builder*, but no consumer ever *receives* 0x03 (§2 D6). |
| `relay_packet_t` | struct | `{ uint8_t data[512]; size_t len; uint32_t timestamp; int rssi; }` | `main/relay_types.h:18-23` | `len` is **`size_t`** here, but `tollgate_proto_decode` takes `uint16_t len` → every call casts `(uint16_t)(pkt->len - 1)` (§2 D2). |

---

## 2. CALL SITES (exact argument order, types, buffer exprs, return handling)

### CONSUMER A — `main/app_task.cpp` (decode PAY → build ACK), guarded by `#ifdef CONFIG_ENABLE_TOLLGATE`
Include: line 33 `#include "tollgate_payment_proto.h"` (inside `#ifdef CONFIG_ENABLE_TOLLGATE`, line 32).

**A-decode — `main/app_task.cpp:117-120`**
```
tollgate_msg_hdr_t hdr;
const uint8_t *payload = NULL;
if (tollgate_proto_decode(pkt.data + 1, pkt.len - 1, &hdr, &payload) >= 0) {
```
- arg1 `pkt.data + 1` : `uint8_t*` (skips relay type tag)
- arg2 `pkt.len - 1` : **`size_t`**, implicitly narrowed to `uint16_t` (D2)
- arg3 `&hdr` : `tollgate_msg_hdr_t*`
- arg4 `&payload` : `const uint8_t**`
- return: tested `>= 0` (defensive; the impl returns -1 or 8, never 0) — header accepted, payload NOT validated.
- `payload` is bound but **never read** in the whole file (dead binding).

**A-encode — `main/app_task.cpp:132-136`**
```
int ack_len = tollgate_proto_encode(ack_pkt.data + 1,
                                     RELAY_PACKET_MAX_SIZE - 1,
                                     TG_MSG_ACK, hdr.seq,
                                     (const char *)&ack_payload,
                                     sizeof(ack_payload));
```
- arg1 `ack_pkt.data + 1` : `uint8_t*`
- arg2 `RELAY_PACKET_MAX_SIZE - 1` : int literal `511`
- arg3 `TG_MSG_ACK` : enum = 2
- arg4 **`hdr.seq`** : `uint16_t` — passed *unchanged*
- arg5 `(const char *)&ack_payload` : reinterprets `tollgate_ack_payload_t*` as char buffer
- arg6 `sizeof(ack_payload)` : `size_t` = 14, narrowed to `uint16_t`
- return: `if (ack_len > 0)` then `ack_pkt.len = ack_len + 1;` — negative/zero is silently dropped (no log, no NACK).
- ACK payload built at lines 128-130: memset 0 then `ack_payload.price_sats = 0; /* TODO: real price from config */`.

### CONSUMER B — `main/test/test_relay_pipeline.c` (re-implementation of A) — **BINDING mock, see §3**
Include line 83. Decode at line 133 (`> 0` — stricter than A's `>= 0`). Encode at 143-147:
```
int ack_len = tollgate_proto_encode(ack_pkt.data + 1,
                                     RELAY_PACKET_MAX_SIZE - 1,
                                     TG_MSG_ACK, hdr.seq,
                                     (const char *)&ack,
                                     (uint16_t)sizeof(ack));
```
Same arg order/types as A; the ONLY differences are `> 0` vs `>= 0` on decode (D3) and an
explicit `(uint16_t)` cast on the size arg. Return handled `if (ack_len > 0)` — identical.

### CONSUMER C — `main/app_main.cpp` (CLI `tollgate_send_pay`, a THIRD producer not named in the brief)
Include line 79. **`main/app_main.cpp:624-628`:**
```
s_tollgate_seq++;
int enc_len = tollgate_proto_encode(pkt.data + 1,
                                     RELAY_PACKET_MAX_SIZE - 1,
                                     TG_MSG_PAY, (uint16_t)s_tollgate_seq,
                                     payload, payload_len);
if (enc_len < 0) { printf(...); return; }
pkt.len = (size_t)(enc_len + 1);
```
- arg4 `(uint16_t)s_tollgate_seq` : source is a **`uint32_t`** truncated to 16 bits (D1).
- return: **`< 0` treated as error ONLY**; `enc == 0` or `enc == 8` (zero-payload frame) is accepted (inconsistent with A's `> 0`, D7).
- guard before the call: `if (payload_len > RELAY_PACKET_MAX_SIZE - 1 - sizeof(tollgate_msg_hdr_t))` → 502-byte cap (D5).

### CONSUMER D — `main/test/test_tollgate_payment_proto.c` (unit tests; describe the intended contract)
Calls at lines 84, 103, 120, 125, 129, 133, 266, 301 (encode) and 154, 165, 180, 183, 186, 201,
207, 211, 232, 237, 242, 273, 307 (decode). Same positional order as A/B/C throughout.
Pins the load-bearing numbers: hdr==8, ack==14, offsets 0/1/2/4/6 and 0/4/8/12, encode `-1` on
overflow/NULL/one-short, decode `-1` on short/NULL/bad-version/truncated.

### CONSUMER E — `test/integration/test_tollgate_payack.py` (Python, live-board)
Duplicates the constants by value, does NOT include the header:
lines 97-98 `RELAY_TYPE_TOLLGATE_PAY = 0x02`, `RELAY_TYPE_TOLLGATE_ACK = 0x03`;
lines 101-103 `TG_MSG_PAY = 0x01`, `TG_MSG_ACK = 0x02`, `TG_MSG_NACK = 0x03`.
It never decodes bytes itself — it regex-scrapes serial ASCII for `seq`, `price`, `session_id`,
`expires` (lines 106-113, 172-192). So its "ACK payload" expectations are textual, not wire.

---

## 3. BINDING MOCK MATERIAL — `main/test/test_relay_pipeline.c` (verbatim, citable)

Header comment (lines 76-81) states the stand-in policy and is **binding**:
> `/* TollGate payment protocol — uses the REAL tollgate_payment_proto.h */`
> `/* The header now exists at main/tollgate_payment_proto.h with        */`
> `/* encode/decode functions matching ADR-002. The mock has been removed */`
> `/* and all tests now exercise the real protocol implementation.       */`

So: there is NO local mock proto left. The mock that
remains is the **queue + dispatch harness**; the proto symbols are the REAL ones. The binding
surface the harness fixes is therefore:

1. **Link contract** (build recipe in the file header, lines 12-15): the test is built by linking
   `main/tollgate_payment_proto.c` directly. Any authoring task that changes the .c must keep it
   host-linkable with zero ESP-IDF deps (the .c currently includes only `<string.h>`).
2. **`relay_packet_t` shape** (via `relay_types.h`): the mock touches `.data[0]`, `.data+1`,
   `.len`, `.timestamp`, `.rssi` — asserted at line 619 as
   `sizeof(relay_packet_t) >= RELAY_PACKET_MAX_SIZE + sizeof(size_t)+sizeof(uint32_t)+sizeof(int)`.
3. **Dispatch by `pkt->data[0]`** (line 106) — the type tag MUST stay byte 0.
4. **Proto call shapes** — identical positional order/types to app_task.cpp (lines 133, 143-147).
5. **Struct members touched by the harness**: only `tollgate_msg_hdr_t.type` (lines 374,405,513)
   and `tollgate_msg_hdr_t.seq` (375,406,514), plus `tollgate_ack_payload_t.price_sats` (141).
6. **Return-handling semantics the harness asserts**: decode `> 0` (133,373,404,512); encode
   `> 0` (148); ACK carries `seq` back equal to PAY `seq` (assert 375, 406, `h.seq == seq`);
   `h.type == TG_MSG_ACK` (374,405,513). **These are the clauses a re-authoring must not break.**
7. **Flagged discrepancy the harness itself documents** (lines 114-122) — the harness deliberately
   *diverges* from app_task.cpp on the Nostr branch, quoting:
   > `NOTE: app_task.cpp checks == 0, but nostr_event_deserialize()`
   > `returns bytes consumed (>0) on success and 0 on error.`
   > `The == 0 check in app_task.cpp is a bug — it means events are`
   > `NEVER stored on the real firmware. We use the correct > 0 check here`
   This is about `nostr_event_deserialize` (NOT the tollgate proto). I verified the contract it
   cites: `components/nostr_store/include/nostr_store.h:126` declares
   `uint16_t nostr_event_deserialize(...)` and the comment at :123 says
   `Returns bytes used, or 0 on error`. **BUT app_task.cpp:100 actually reads
   `if (nostr_event_deserialize(...) > 0)`** — i.e. app_task.cpp ALREADY uses `>0`, matching the
   harness. The harness's "bug" note is itself STALE on this revision (D8).

---

## 4. DISAGREEMENTS BETWEEN CONSUMERS (exact conflicting quotes)

**D1 — seq width: producers truncate, consumer widens.**
- `app_main.cpp:591` `static uint32_t s_tollgate_seq = 0;` then `:624` `s_tollgate_seq++;` and
  `:627` `TG_MSG_PAY, (uint16_t)s_tollgate_seq,` → a 32-bit counter forced through 16 bits
  (wraps at 65536; two producers can collide, and dedup-by-seq has no epoch).
- `app_task.cpp:134` / `test_relay_pipeline.c:145` pass `hdr.seq` (`uint16_t`) — the header's width.
- Header declares `uint16_t seq; /* Sequence number for dedup */` (`tollgate_payment_proto.h:52`).
  Meaning: the API is 16-bit; one producer holds 32-bit state but the *wire* field is 16-bit.

**D2 — length width: `size_t` frame vs `uint16_t` proto.**
- `relay_types.h:20` `size_t len;`  vs  `tollgate_payment_proto.h:107`
  `int tollgate_proto_decode(const uint8_t *data, uint16_t len, ...)`.
- Both real call sites narrow implicitly: `app_task.cpp:120` `tollgate_proto_decode(pkt.data + 1, pkt.len - 1, ...)`
  (no cast) vs `test_relay_pipeline.c:133` `..., (uint16_t)(pkt->len - 1), ...` (explicit cast).
  Same value (packets ≤512 so no wrap today), but one site is cast-clean and one is a silent narrowing.

**D3 — decode success test: `>= 0` vs `> 0`.**
- `app_task.cpp:120` `if (tollgate_proto_decode(...) >= 0) {`
- `test_relay_pipeline.c:133` `if (tollgate_proto_decode(...) > 0) {`
- `test_tollgate_payment_proto.c:274` `ASSERT_EQ_INT((int)sizeof(tollgate_msg_hdr_t), dec, "decode offset");`
  The impl (`tollgate_payment_proto.c:39-53`) only ever returns `-1` or `8`, so today they agree
  by accident. They would diverge if decode ever returned 0 (e.g. a future zero-length ack).

**D4 — message-type / relay-tag values duplicated across a language boundary.**
- C side is authoritative: `tollgate_payment_proto.h:40-42` (`0x01/0x02/0x03`) and
  `relay_types.h:12-13` (`0x02/0x03`).
- Python side re-hardcodes them: `test_tollgate_payack.py:97-103`
  `RELAY_TYPE_TOLLGATE_PAY = 0x02` / `TG_MSG_PAY = 0x01`. No import, no generated header — a
  silent drift risk if either enum moves.

**D5 — token length cap: 2048 declared vs 502 enforced.**
- `tollgate_payment_proto.h:36` `#define TOLLGATE_MAX_TOKEN_LEN  2048` and `:59`
  `char token[TOLLGATE_MAX_TOKEN_LEN];`.
- `app_main.cpp:617-619` `if (payload_len > RELAY_PACKET_MAX_SIZE - 1 - sizeof(tollgate_msg_hdr_t))`
  → `512 - 1 - 8 = 503` (message: "payload too long (%u > %d max)"). The live PAY token is
  therefore capped at **503 bytes**, ~4× smaller than the declared 2048, and
  `tollgate_pay_payload_t` is never used to carry it.

**D6 — relay ACK tag (0x03) is written but never read.**
- Written: `app_task.cpp:126` `ack_pkt.data[0] = RELAY_TYPE_TOLLGATE_ACK;` (and mock
  `test_relay_pipeline.c:137`).
- Read: nowhere. `grep -rn "RELAY_TYPE_TOLLGATE_ACK" main/` returns only the *definition*
  (`relay_types.h:13`), the two writers above, and the header comment. There is **no consumer
  branch** for `case RELAY_TYPE_TOLLGATE_ACK:` — the ACK the firmware transmits is never decoded
  by any firmware code path (only the Python harness text-scrapes for it, and the host test
  decodes its own just-built packet, `test_relay_pipeline.c:373`).

**D7 — encode error test: `> 0` vs `< 0`.**
- `app_task.cpp:137` `if (ack_len > 0) {` and `test_relay_pipeline.c:148` `if (ack_len > 0) {`
- `app_main.cpp:629` `if (enc_len < 0) { printf("tollgate_send_pay: proto_encode failed...") }`
  For a zero-payload frame `encode` returns exactly `8` (proven: `/tmp/probe`). A treats `8>0` as
  success; C treats `8>=0` as success — but C would also accept a hypothetical `0` that A rejects.

**D8 — stale bug note in the binding mock (see §3.7).**
- `test_relay_pipeline.c:116-118` quotes: `app_task.cpp checks == 0` … `The == 0 check in
  app_task.cpp is a bug`.
- Actual `app_task.cpp:100`: `if (nostr_event_deserialize(&event, pkt.data + 1, pkt.len - 1) > 0) {`
  → already `> 0`. The mock's warning describes a revision that no longer ships; do not carry the
  claimed bug into the contract as a live defect.

**D9 — `>= 0` in A also under-validates the payload.**
- A accepts when `decode(...) >= 0` (`app_task.cpp:120`) and then *logs `hdr.seq` and re-encodes*
  without ever consulting `payload`/`hdr.payload_len`. So a PAY with `payload_len=0` (which
  `encode(NULL,0)` produces) is answered with a success ACK even though no token was attached —
  the mock has the same hole but at least binds `payload` (still unused). This is a semantic gap,
  not a type clash: **no consumer verifies that a PAY actually carries a Cashu token.**

---

## 5. REFERENCED-BUT-NOT-FOUND / DEAD

Nothing referenced by a live call site or by the mock is undefined — the tree is self-consistent
at link time (both suites compile and pass). What IS dead/unused, and worth naming for the
authoring task:

1. `tollgate_pay_payload_t` — defined `tollgate_payment_proto.h:58-60`, used by NO consumer.
2. `tollgate_nack_payload_t` — defined `:71-74`, used by NO consumer.
3. `TG_ERR_*` (all five) — defined `:77-81`, used by NO consumer.
4. `TG_MSG_NACK/STATUS/INFO/REVOKE` — defined `:42-45`, used by NO *firmware* consumer; only
   `TG_MSG_STATUS`/`TG_MSG_INFO`/`TG_MSG_NACK` appear in unit-test vectors
   (`test_tollgate_payment_proto.c:103,158,258`).
5. `tollgate_msg_hdr_t.payload_len` — written by encode, validated by decode, but read by NO
   application consumer (consumers read only `.seq` and `.type`).
6. `tollgate_msg_hdr_t.reserved` / `.version` — no consumer reads them; version is enforced
   inside decode only.
7. In `app_task.cpp` the local `const uint8_t *payload` (line 118) and in
   `test_relay_pipeline.c` the local `payload` (line 131) are **bound but never read**.
8. `test_relay_pipeline.c` `int packets_processed = 12;` (line 496) then `(void)packets_processed;`
   — vestigial.
9. NOT FOUND, by design: no `case RELAY_TYPE_TOLLGATE_ACK` consumer anywhere (§D6); no
   `msg_type` symbol outside the header/its tests (grep for `msg_type` returns only the header
   comment lines and the enum typedef name `tollgate_msg_type_t`); no `tollgate_*` symbol exists
   under `components/` — the proto lives only in `main/`.

---

## 6. ONE-LINE HANDOFF

The contract a re-authoring must preserve: `int encode(uint8_t* buf, uint16_t buf_len,
tollgate_msg_type_t type, uint16_t seq, const char* payload, uint16_t payload_len)` returning
`8+payload_len` or `-1`, and `int decode(const uint8_t* data, uint16_t len,
tollgate_msg_hdr_t* hdr, const uint8_t** payload)` returning `8` or `-1`, with an 8-byte packed
header at offsets 0/1/2/4/6, a 14-byte packed ACK payload at 0/4/8/12, and `RELAY_PACKET_MAX_SIZE-1`
(511) as the capacity every real call site passes. The three live call sites (app_task.cpp:120/132,
app_main.cpp:627, and the binding harness test_relay_pipeline.c:133/143) must all keep compiling
and both host suites must stay green (83/83 and 12/12).
