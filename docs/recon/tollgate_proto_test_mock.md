# Recon: test_relay_pipeline.c mock TollGate proto contract

> **Status note (added 2026-09-27, card `balloon:t_c360db44`):** this report documents the
> **superseded mock** protocol that `test_relay_pipeline.c` used while
> `tollgate_payment_proto.h` did not exist. The real header has since landed
> (`65a46fd1`), the mock was **removed**, and the test now exercises the real
> implementation with a bare `#include "tollgate_payment_proto.h"`
> (`test_relay_pipeline.c:75-83`). This file is retained as the historical input to
> `TOLLGATE_PROTO_CONTRACT.md` §0.1 and the delta record for the mock→real transition — it is
> **not** the current contract. For the current contract see
> `tracker/firmware/TOLLGATE_PROTO_API.md` and repo-root `TOLLGATE_PROTO_CONTRACT.md`.

Date: 2026-09-14
Branch: `autonomous/mesh-baseline` (worktree `/home/c03rad0r/repos/balloon`)
Scope: read-only recon. No source, test, or header file modified.
Purpose: capture the MOCK TollGate payment-protocol contract that
`test_relay_pipeline.c` assumed while the real `tollgate_payment_proto.h`
did not exist, so the real header can be built/audited against the mocked
contract.

---

## 0. Summary — and a premise correction (read first)

**The mock no longer exists at current HEAD.** The task premise ("the real
proto header it comments about does not exist yet") describes a historical
state of the file, not the current one:

- The mock proto (structs + encode/decode + type defines) existed in exactly
  **one commit: `4e861741`** ("test: host-side relay pipeline integration test
  — no hardware needed", Felix, 2026-08-05 12:01:02 +0530), which is also the
  commit that introduced the test file.
- The real header was created ~80 minutes later in **`65a46fd1`**
  ("feat: create tollgate_payment_proto.h + implement tollgate_send_pay CLI",
  Felix, 2026-08-05 13:21:10 +0530), which rewrote the test to call the real
  API and deleted the mock block wholesale.
- At current HEAD (`b7db8b31`), `tracker/firmware/main/test/test_relay_pipeline.c`
  is byte-identical to the `65a46fd1` version (verified: `git diff 65a46fd1 HEAD`
  on the file is empty), the real header lives at
  `tracker/firmware/main/tollgate_payment_proto.h` (created `65a46fd1`,
  hardened in `38360fb1`, 2026-09-14), and **zero** references to the mock
  symbols remain anywhere in the tree (grep over `*.c/*.h/*.cpp` finds none;
  the only textual mentions are in `docs/coordination/CONSULTANT-PLAN-REVIEW-V3.md:22-23`,
  which calls them "invented function names").

Therefore this document reconstructs the mock contract from
`git show 4e861741:tracker/firmware/main/test/test_relay_pipeline.c`
(690 lines). **All mock-era line numbers below refer to that version.**
Where current-HEAD line numbers are cited (mainly in §6), they refer to
`tracker/firmware/main/app_task.cpp` and the current test file at HEAD.

For contrast, the comment block that sits at the same location (line ~75)
at current HEAD now reads (test file lines 75-83, quoted verbatim):

```
75|/* ------------------------------------------------------------------ */
76|/* TollGate payment protocol — uses the REAL tollgate_payment_proto.h  */
77|/*                                                                    */
78|/* The header now exists at main/tollgate_payment_proto.h with        */
79|/* encode/decode functions matching ADR-002. The mock has been removed */
80|/* and all tests now exercise the real protocol implementation.       */
81|/* ------------------------------------------------------------------ */
82|
83|#include "tollgate_payment_proto.h"
```

The build recipe in the file header also marks the era boundary: the mock-era
version (lines 11-14) compiles only the test + `nostr_store.c`; the HEAD
version (line 14) additionally links `main/tollgate_payment_proto.c`.

What the mock contract pinned down (full detail in §2-§4):
- 7-byte wire prefix `[1 type][4 seq BE][2 payload_len LE][payload]`
- `uint32_t seq`, big-endian on the wire; `payload_len` little-endian
- two structs `tollgate_msg_header_t` / `tollgate_msg_t` (NOT packed)
- encode returns total bytes written or `-1`; decode returns `0` on success
  or `-1` on error (POSIX style)
- two message types only: `TOLLGATE_MSG_PAY 0x01`, `TOLLGATE_MSG_ACK 0x02`
- transport envelope: relay type tag byte at `data[0]`, proto message at
  `data+1`, `pkt->len` counts tag + message bytes

The real header answered several of these differently (§7 tabulates every
divergence; the mock and real formats are **not wire-compatible**).

---

## 1. Verbatim line ~75 comment (mock era, commit 4e861741)

Exact line span: **lines 74-80** of
`4e861741:tracker/firmware/main/test/test_relay_pipeline.c`
(a `/* --- */`-fenced banner block; the "doesn't exist yet" sentence is on
line 75). Quoted verbatim, character-exact including the ragged `*/`
alignment:

```
74|/* ------------------------------------------------------------------ */
75|/* Mock tollgate protocol (tollgate_payment_proto.h doesn't exist yet) */
76|/*                                                                    */
77|/* Minimal encode/decode matching the usage in app_task.cpp.           */
78|/* When the real header is written, these tests can be updated to     */
79|/* include it and call the real functions.                            */
80|/* ------------------------------------------------------------------ */
```

There are **no TODO/FIXME markers, no author, and no date** inside this
block. A grep over the entire mock-era file finds **zero** TODO/FIXME/XXX
markers anywhere. (The `price_sats = 0; /* TODO: real price from config */`
comments at current-HEAD test line 141 / app_task.cpp:130 exist only in the
post-header versions — the mock era had no price concept. The known-bug
annotation at mock-era lines 167-175 is about `nostr_event_deserialize`,
not the tollgate proto.) The immediately
following lines, 82-83, define the message-type constants:

```
82|#define TOLLGATE_MSG_PAY  0x01
83|#define TOLLGATE_MSG_ACK  0x02
```

The mock block spans lines 74-136 in total (comment 74-80, defines 82-83,
structs 85-95, encode 97-115, decode 117-136).

---

## 2. Mock structs (commit 4e861741, quoted with line numbers)

Two structs, declaration order preserved. **Neither has `#pragma pack` nor
`__attribute__((packed))`** — there is no packing directive anywhere in the
file. This is safe on the wire only because the codec serializes
field-by-field (§4), so struct padding never reaches the buffer.

```
85|typedef struct {
86|    uint8_t  type;
87|    uint32_t seq;
88|} tollgate_msg_header_t;
89|
90|typedef struct {
91|    uint8_t  type;
92|    uint32_t seq;
93|    uint8_t  payload[256];
94|    uint16_t payload_len;
95|} tollgate_msg_t;
```

Field-by-field, in declaration order:

**`tollgate_msg_header_t`** (lines 85-88) — the decode result:
| # | field  | type       | notes |
|---|--------|------------|-------|
| 1 | `type` | `uint8_t`  | message type tag |
| 2 | `seq`  | `uint32_t` | sequence number |

**`tollgate_msg_t`** (lines 90-95) — the encode source:
| # | field         | type        | notes |
|---|---------------|-------------|-------|
| 1 | `type`        | `uint8_t`   | message type tag |
| 2 | `seq`         | `uint32_t`  | sequence number |
| 3 | `payload`     | `uint8_t[256]` | fixed inline array, no const |
| 4 | `payload_len` | `uint16_t`  | bytes of `payload` in use |

No designated initializers are used against these structs anywhere in the
file; all instances are `memset` to zero then field-assigned (e.g. lines
192-195, 257-261 — quoted in §4). No `sizeof` assertion is made on either
struct (TEST 12 only checks `relay_packet_t`, line 672).

---

## 3. Function signatures (commit 4e861741, quoted with line numbers)

Both are file-local `static` C functions (not `extern`, no explicit calling
convention; compiled as plain C by host gcc per the file-header recipe,
lines 11-14). Doc-comments quoted with them.

**Encode** — comment line 97, signature line 98, body 99-115:

```
 97|/* Encode: [1 type][4 seq BE][2 payload_len LE][payload] */
 98|static int tollgate_msg_encode(const tollgate_msg_t *msg, uint8_t *buf, size_t buf_size)
 99|{
100|    size_t needed = 1 + 4 + 2 + msg->payload_len;
101|    if (buf_size < needed) return -1;
102|
103|    size_t pos = 0;
104|    buf[pos++] = msg->type;
105|    buf[pos++] = (uint8_t)(msg->seq >> 24);
106|    buf[pos++] = (uint8_t)(msg->seq >> 16);
107|    buf[pos++] = (uint8_t)(msg->seq >> 8);
108|    buf[pos++] = (uint8_t)(msg->seq);
109|    buf[pos++] = (uint8_t)(msg->payload_len & 0xFF);
110|    buf[pos++] = (uint8_t)((msg->payload_len >> 8) & 0xFF);
111|    memcpy(buf + pos, msg->payload, msg->payload_len);
112|    pos += msg->payload_len;
113|
114|    return (int)pos;
115|}
```

Contract encoded by the body:
- Return: total bytes written (7-byte prefix + payload) cast to `int`, or
  `-1` if `buf_size < 1+4+2+payload_len` (line 101). `-1` is the only error.
- **`seq` is serialized BIG-ENDIAN** (lines 105-108, MSB first).
- **`payload_len` is serialized LITTLE-ENDIAN** (lines 109-110) — note the
  deliberate mixed endianness vs `seq`.
- No version byte, no reserved field, no type validation, no magic value.

**Decode** — comment line 117, signature lines 118-120, body 121-136:

```
117|/* Decode: returns 0 on success, fills hdr and sets *payload pointer */
118|static int tollgate_msg_decode(const uint8_t *buf, size_t buf_len,
119|                               tollgate_msg_header_t *hdr,
120|                               const uint8_t **payload)
121|{
122|    if (buf_len < 7) return -1;
123|
124|    size_t pos = 0;
125|    hdr->type = buf[pos++];
126|    hdr->seq  = ((uint32_t)buf[pos] << 24) | ((uint32_t)buf[pos+1] << 16) |
127|                ((uint32_t)buf[pos+2] << 8) | (uint32_t)buf[pos+3];
128|    pos += 4;
129|
130|    uint16_t plen = (uint16_t)(buf[pos] | (buf[pos+1] << 8));
131|    pos += 2;
132|
133|    if (pos + plen > buf_len) return -1;
134|    *payload = buf + pos;
135|    return 0;
136|}
```

Contract encoded by the body:
- Return: **`0` on success** (POSIX style — the inverse of the real header's
  contract, see §7), `-1` on: `buf_len < 7` (line 122) or declared payload
  overruns the buffer (line 133).
- `hdr` is caller-allocated and filled field-by-field (`hdr->type` line 125,
  `hdr->seq` line 126-127 big-endian, mirroring encode).
- `*payload` is set to point **into the caller's buffer** (`buf + pos`,
  line 134) — zero-copy, no 256-byte copy. `plen` (line 130, little-endian)
  is checked but **not returned**; callers must re-derive payload length.
- No `hdr`/`payload` NULL guard (both are always valid in this test).
- No version check, no type validation.

**Call sites inside the test** (they pin the calling convention the real
header would have to serve):

Dispatch path, `app_task_process_packet` TOLLGATE_PAY case, lines 182-205:

```
182|    case RELAY_TYPE_TOLLGATE_PAY: {
183|        tollgate_msg_header_t hdr;
184|        const uint8_t *payload = NULL;
185|
186|        if (tollgate_msg_decode(pkt->data + 1, pkt->len - 1, &hdr, &payload) == 0) {
187|            /* Build ACK response (matches app_task.cpp logic) */
188|            relay_packet_t ack_pkt;
189|            memset(&ack_pkt, 0, sizeof(ack_pkt));
190|            ack_pkt.data[0] = RELAY_TYPE_TOLLGATE_ACK;
191|
192|            tollgate_msg_t ack_msg;
193|            memset(&ack_msg, 0, sizeof(ack_msg));
194|            ack_msg.type = TOLLGATE_MSG_ACK;
195|            ack_msg.seq = hdr.seq;
196|
197|            int ack_len = tollgate_msg_encode(&ack_msg, ack_pkt.data + 1,
198|                                              RELAY_PACKET_MAX_SIZE - 1);
199|            if (ack_len > 0) {
200|                ack_pkt.len = (size_t)(ack_len + 1);
201|                mock_queue_send(ctx->tx_queue, &ack_pkt);
202|            }
203|        }
204|        break;
205|    }
```

PAY packet builder, lines 252-268 (helper used by TEST 4/5/8):

```
252|static void build_tollgate_pay_packet(relay_packet_t *pkt, uint32_t seq)
253|{
254|    memset(pkt, 0, sizeof(*pkt));
255|    pkt->data[0] = RELAY_TYPE_TOLLGATE_PAY;
256|
257|    tollgate_msg_t pay_msg;
258|    memset(&pay_msg, 0, sizeof(pay_msg));
259|    pay_msg.type = TOLLGATE_MSG_PAY;
260|    pay_msg.seq = seq;
261|    pay_msg.payload_len = 0;
262|
263|    int enc_len = tollgate_msg_encode(&pay_msg, pkt->data + 1, RELAY_PACKET_MAX_SIZE - 1);
264|    assert(enc_len > 0);
265|    pkt->len = (size_t)(enc_len + 1);
266|    pkt->timestamp = 0;
267|    pkt->rssi = -65;
268|}
```

Transport-envelope convention pinned by these call sites (the real header
must live inside it):
- Byte 0 of `relay_packet_t.data` is the relay type tag
  (`RELAY_TYPE_TOLLGATE_PAY 0x02` in, `RELAY_TYPE_TOLLGATE_ACK 0x03` out);
  the proto message starts at `data + 1`.
- Buffer budget for the message is `RELAY_PACKET_MAX_SIZE - 1` = 511 bytes
  (relay_types.h:6 defines `RELAY_PACKET_MAX_SIZE 512`).
- `pkt->len` (a `size_t`) counts **tag + message bytes**: `len = enc_len + 1`
  (lines 200, 265); decode is always called as
  `decode(data + 1, len - 1, ...)`.
- PAY→ACK carries `seq` over verbatim (`ack_msg.seq = hdr.seq`, line 195);
  the ACK payload is empty (`payload_len` left 0 by the memset, price TODO
  below).
- Note the test's ACK sets no price field — the mock `tollgate_msg_t` has no
  price concept at all. (The current-HEAD code adds
  `ack.price_sats = 0;  /* TODO: real price from config */` at test line 141 /
  app_task.cpp:130, because the real header introduced
  `tollgate_ack_payload_t`.)

---

## 4. Assertions on returns and buffers (commit 4e861741)

The file uses plain C `assert()` from `<assert.h>` — there are **no
EXPECT_EQ/gtest macros** anywhere. On the tollgate path there are **no
memcmp assertions on payload bytes, no magic-value checks, and no version
checks** — the mock has no payload content to compare (PAY/ACK payloads are
always empty) and no version field. The wire format (including endianness)
is pinned only *indirectly*, by encode→decode round-trips inside one
process. Exhaustive tollgate-relevant assertion list, by test:

**In `build_tollgate_pay_packet`:**
- `264|    assert(enc_len > 0);` — encode succeeded, return is positive total
  length (7 for empty payload).

**TEST 4 — single PAY (seq=42) → ACK (lines 403-433):**
- `415|    assert(tx_queue.count == 1);` — exactly one ACK queued
- `417|    assert(mock_queue_receive(&tx_queue, &ack_pkt) == 0);`
- `420|    assert(ack_pkt.len > 1);` — ACK packet length: tag + ≥1 proto bytes
- `421|    assert(ack_pkt.data[0] == RELAY_TYPE_TOLLGATE_ACK);` — ACK relay tag
- `426|    assert(tollgate_msg_decode(ack_pkt.data + 1, ack_pkt.len - 1, &ack_hdr, &ack_payload) == 0);` — **decode success predicate is `== 0`** (mock semantics)
- `427|    assert(ack_hdr.type == TOLLGATE_MSG_ACK);` — type survives round-trip
- `428|    assert(ack_hdr.seq == 42);` — **seq survives round-trip (endianness check by value, not bytes)**
- `431|    assert(tx_queue.count == 0);` — queue drained

**TEST 5 — five round-trips, seq=100..104 (lines 438-464):**
- `450|        assert(tx_queue.count == 1);` — one ACK per PAY
- `452|        assert(mock_queue_receive(&tx_queue, &a) == 0);`
- `453|        assert(a.data[0] == RELAY_TYPE_TOLLGATE_ACK);`
- `457|        assert(tollgate_msg_decode(a.data + 1, a.len - 1, &h, &pl) == 0);`
- `458|        assert(h.type == TOLLGATE_MSG_ACK);`
- `459|        assert(h.seq == seq);` — per-seq fidelity (100,101,102,103,104)
- `462|    assert(tx_queue.count == 0);`

**TEST 6 — telemetry ignored (lines 469-487):**
- `484|    assert(nostr_store_count(store) == store_before);` — no store write
- `485|    assert(tx_queue.count == 0);` — **no ACK emitted for telemetry**

**TEST 7 — unknown type 0xFE ignored (lines 492-508):**
- `505|    assert(nostr_store_count(store) == store_before);`
- `506|    assert(tx_queue.count == 0);` — **no ACK for unknown types**

**TEST 8 — mixed traffic, 4× PAY seq=200..203 (lines 513-572):**
- `554|    assert(nostr_store_count(store) == store_before + 4);`
- `557|    assert(tx_queue.count == 4);` — 4 ACKs pending
- `562|        assert(ack_pkt.data[0] == RELAY_TYPE_TOLLGATE_ACK);`
- `565|        assert(tollgate_msg_decode(ack_pkt.data + 1, ack_pkt.len - 1, &h, &pl) == 0);`
- `566|        assert(h.type == TOLLGATE_MSG_ACK);`
- `567|        assert(h.seq >= 200 && h.seq < 204);` — range check on seq preservation
- `570|    assert(ack_count == 4);`

**TEST 10 — empty packet, `len = 0` (lines 625-637):**
- `635|    assert(tx_queue.count == 0);` — no crash, no ACK (guards the
  `pkt->data + 1, pkt->len - 1` arithmetic on the dispatch path)

**TEST 12 — envelope sanity (lines 669-681):**
- `672|    assert(sizeof(relay_packet_t) >= RELAY_PACKET_MAX_SIZE + sizeof(size_t) + sizeof(uint32_t) + sizeof(int));`
- `675|    assert(RELAY_TYPE_NOSTR_EVENT  == 0x01);`
- `676|    assert(RELAY_TYPE_TOLLGATE_PAY == 0x02);` — PAY tag value pinned
- `677|    assert(RELAY_TYPE_TOLLGATE_ACK == 0x03);` — ACK tag value pinned
- `678|    assert(RELAY_TYPE_TELEMETRY    == 0x04);`
- `679|    assert(RELAY_TYPE_RAW          == 0xFF);`

Endianness assumptions, summarized: `seq` big-endian (encode 105-108 /
decode 126-127), `payload_len` little-endian (encode 109-110 / decode 130).
These are never asserted at the byte level — only via seq round-trip asserts
(428, 459, 567). A real header that flipped seq to little-endian would pass
every assert in this file (same-process round-trip), which is worth knowing
when auditing.

---

## 5. app_task.cpp cross-check — mock era (commit 4e861741)

`app_task.cpp` **does use the mock symbols** at the mock-era commit (inside
`#ifdef CONFIG_ENABLE_TOLLGATE`, lines 95-123 of
`4e861741:tracker/firmware/main/app_task.cpp`). Side-by-side with the test:

| Aspect | test_relay_pipeline.c @4e861741 | app_task.cpp @4e861741 | Verdict |
|---|---|---|---|
| header struct | `tollgate_msg_header_t hdr;` (183) | `tollgate_msg_header_t hdr;` (98) | MATCH |
| decode call | `tollgate_msg_decode(pkt->data + 1, pkt->len - 1, &hdr, &payload) == 0` (186) | `tollgate_msg_decode(pkt.data + 1, pkt.len - 1, &hdr, &payload) == 0` (101) | MATCH — 4 args, same order, same `== 0` success predicate |
| ACK msg struct | `tollgate_msg_t ack_msg;` + `type = TOLLGATE_MSG_ACK; seq = hdr.seq;` (192-195) | `tollgate_msg_t ack_msg;` + `type = TOLLGATE_MSG_ACK; seq = hdr.seq;` (109-112) | MATCH |
| encode call | `tollgate_msg_encode(&ack_msg, ack_pkt.data + 1, RELAY_PACKET_MAX_SIZE - 1)` (197-198) | `tollgate_msg_encode(&ack_msg, ack_pkt.data + 1, RELAY_PACKET_MAX_SIZE - 1)` (114) | MATCH — 3 args, same buffer budget |
| encode check | `if (ack_len > 0)` (199) | `if (ack_len > 0)` (115) | MATCH |
| ACK len assignment | `ack_pkt.len = (size_t)(ack_len + 1);` (200) | `ack_pkt.len = ack_len + 1;` (116) | cosmetic only — test adds explicit `(size_t)` cast; same value |
| decode buffer-len arg | `pkt->len - 1` (186) — `size_t`, `pkt` is `const relay_packet_t *` | `pkt.len - 1` (101) — `size_t`, `pkt` is by-value `relay_packet_t` | MATCH (pointer vs value is the queue-mock vs FreeRTOS difference, not a contract difference) |

**Structural mismatches found (mock era):**

1. **The include asymmetry.** `app_task.cpp:33` (inside
   `#ifdef CONFIG_ENABLE_TOLLGATE`, lines 32-34) reads
   `#include "tollgate_payment_proto.h"` — a header that **did not exist
   anywhere in the tracker firmware tree at commit 4e861741**. The test file
   deliberately does NOT include it; it defines the mock inline. So at that
   commit, any build with `CONFIG_ENABLE_TOLLGATE` defined would fail to
   compile `app_task.cpp`, while the host test compiled fine.
2. **The guard was dead code at that commit.** `CONFIG_ENABLE_TOLLGATE` had
   **no Kconfig entry** at 4e861741 (`git show 4e861741:.../Kconfig.projbuild`
   contains no `TOLLGATE`; `git grep ENABLE_TOLLGATE 4e861741` hits only
   app_task.cpp itself and a coordination doc). The Kconfig flag was added
   later the same day in `cb49869a` ("fix: tollgate API alignment — correct
   function names, add Kconfig flag"). This is why the missing header never
   broke the firmware build: the `#ifdef` block was unreachable.
3. **Known deliberate divergence — NOT tollgate, but the only logic
   mismatch in the shared dispatch:** the test checks
   `nostr_event_deserialize(&event, pkt->data + 1, (uint16_t)(pkt->len - 1)) > 0`
   (line 176) while `app_task.cpp:81` checked `... == 0`. The test documents
   this at its lines 167-175: the `== 0` check is inverted
   (`nostr_event_deserialize` returns bytes consumed on success —
   nostr_store.h:122: "Returns bytes used, or 0 on error"), so events were
   never stored on real firmware. Fixed later in `f11ddd62`
   ("fix: inverted nostr_event_deserialize return check — events were
   never stored", 2026-08-05 12:05:17 +0530, i.e. 4 minutes after the test
   commit — the test found the bug).
4. Also at 4e861741, `app_task.cpp:101` passes `pkt.len - 1` (`size_t`)
   straight into the `size_t buf_len` param — identical to the test; no
   truncation issue exists in the mock era because the param is `size_t`.
   (This becomes a real cast question only under the real header, whose
   params are `uint16_t` — see §6.)

---

## 6. app_task.cpp cross-check — current HEAD

At HEAD, **no usage of the mock symbols exists** — grep for
`tollgate_msg_t`, `tollgate_msg_header_t`, `tollgate_msg_encode`,
`tollgate_msg_decode`, `TOLLGATE_MSG_PAY`, `TOLLGATE_MSG_ACK` across
`*.c/*.h/*.cpp` returns zero source hits. Both files now use the real API,
with small residual divergences worth recording:

| Aspect | test_relay_pipeline.c @HEAD | app_task.cpp @HEAD | Verdict |
|---|---|---|---|
| decode predicate | `tollgate_proto_decode(pkt->data + 1, (uint16_t)(pkt->len - 1), &hdr, &payload) > 0` (133) | `tollgate_proto_decode(pkt.data + 1, pkt.len - 1, &hdr, &payload) >= 0` (120) | **MISMATCH (benign)** — `>` vs `>=`; real decode returns 8 or -1, never 0, so both pass, but the predicates differ |
| len cast | explicit `(uint16_t)(pkt->len - 1)` (133) | implicit `size_t → uint16_t` (120) | cosmetic; safe because `len ≤ RELAY_PACKET_MAX_SIZE = 512` |
| ACK payload | `ack.price_sats = 0;` with `(uint16_t)sizeof(ack)` cast into encode (139-147) | `ack_payload.price_sats = 0;` with un-cast `sizeof(ack_payload)` (128-136) | same TODO in both ("real price from config"); cast is cosmetic |
| encode buffer budget | `RELAY_PACKET_MAX_SIZE - 1` (144) | `RELAY_PACKET_MAX_SIZE - 1` (133) | MATCH |

Both sides agree on the transport envelope (tag at `data[0]`, message at
`data+1`, `len = enc_len + 1`), and TEST 4/5/8 still assert `type == TG_MSG_ACK`
and `seq` preservation (lines 374-375, 405-406, 513-514 at HEAD) — the
assertion *shape* carried over intact from the mock era; only the symbols
and the success predicate (`== 0` → `> 0`) changed.

---

## 7. Open questions for the real header — and how the shipped header answered them

The header now exists (`tracker/firmware/main/tollgate_payment_proto.h`,
created `65a46fd1`, hardened `38360fb1`; authoritative contract in
`TOLLGATE_PROTO_CONTRACT.md` at repo root). Recording the questions the mock
left open, with the observed answers, because the two are **not
wire-compatible** and any future reader must know where the mock contract
was superseded:

| # | Open question from the mock | Real header's answer |
|---|---|---|
| 1 | `seq` width: mock `uint32_t`, big-endian | `uint16_t seq`, little-endian (`tollgate_payment_proto.h:52,54`) — a mock-era `seq > 65535` truncates, and BE↔LE makes the formats mutually unintelligible |
| 2 | Header size: mock needs 7 bytes (`[1][4][2]`) | 8-byte packed header `[version(1)][type(1)][seq(2)][payload_len(2)][reserved(2)]` (`h:49-55`, `__attribute__((packed))`) |
| 3 | Version field: none | `uint8_t version = TOLLGATE_PROTO_VERSION (1)`, validated on decode (`tollgate_payment_proto.c:56-57`) |
| 4 | Decode success return: mock `0` on success | `sizeof(tollgate_msg_hdr_t)` = 8 on success, `-1` on error (`h:108`, `c:66`) — callers had to switch from `== 0` to `> 0`/`>= 0` (both files did) |
| 5 | Type namespace: 2 defines (`TOLLGATE_MSG_PAY/ACK`) | enum `tollgate_msg_type_t` with 6 values `TG_MSG_PAY..TG_MSG_REVOKE` (`h:39-46`), bounds-validated on both encode and decode (`c:15-21,58-59`) |
| 6 | Payload handling: fixed inline `uint8_t[256]` | caller-owned pointer + `uint16_t payload_len` into encode; decode yields pointer into the input buffer (`h:97-99,112-114`) — the 256-byte inline array is gone; note real `TOLLGATE_MAX_TOKEN_LEN 2048` (`h:36`) exceeds the 511-byte relay budget, so full-size tokens cannot traverse this relay packet anyway |
| 7 | Struct naming: `tollgate_msg_header_t` / `tollgate_msg_t` | `tollgate_msg_hdr_t` (+ typed payloads `tollgate_pay_payload_t`, `tollgate_ack_payload_t`, `tollgate_nack_payload_t`) — renaming broke the `cb49869a` build, which is exactly the "API alignment" that commit fixed |
| 8 | Validation: mock validates nothing beyond length | real validates version, type bounds, payload_len vs buffer (`c:27-30,50-61`); canary/overflow checks added in `38360fb1` |
| 9 | Where does the price live? mock has no price concept | `tollgate_ack_payload_t {uint32_t session_id; uint32_t expires_unix; uint32_t quota_bytes; uint16_t price_sats;}` (`h:63-68`); both call sites still hard-code `price_sats = 0` with the same TODO |
| 10 | Endianness assertion gap: mock's mixed BE/LE is only pinned by in-process round-trip | unchanged in spirit — the real header's all-LE layout relies on host endianness via packed-struct `memcpy` (`c:32-40,53`); the ESP32-S3 (little-endian) and host gcc x86-64 (little-endian) agree, but the wire is only LE by platform convention, not by explicit byte-shuffling like the mock did |

Remaining genuinely-open items (not answerable from the code):
- The TODO price feed (`price_sats = 0`) is still unresolved on both sides.
- Nothing on either side asserts the *wire bytes* of a tollgate message
  against a golden vector — all tests are same-process round-trips, so an
  endianness or layout regression that is self-consistent would pass both
  the mock-era and current tests. `test_tollgate_payment_proto.c` (added
  `38360fb1`) still round-trips; a byte-level golden test would be the
  only true lock on the wire format.
- PAY/ACK type asymmetry: the mock, the real header, and app_task.cpp all
  treat `RELAY_TYPE_TOLLGATE_ACK` as the relay-layer tag while the type
  byte *inside* the message is `TG_MSG_ACK` — two type fields saying the
  same thing, with no cross-check between them in any test.

---

## 8. Provenance of every quotation in this doc

- Mock-era quotations (§1-§5): `git show 4e861741:tracker/firmware/main/test/test_relay_pipeline.c`
  (and `git show 4e861741:tracker/firmware/main/app_task.cpp`),
  2026-08-05 12:01:02 +0530, author Felix. Line numbers are from those blobs.
- HEAD quotations (§0, §6): working tree at `b7db8b31`
  (`tracker/firmware/main/test/test_relay_pipeline.c`,
  `tracker/firmware/main/app_task.cpp`,
  `tracker/firmware/main/tollgate_payment_proto.h/.c`,
  `tracker/firmware/main/relay_types.h`,
  `tracker/firmware/main/Kconfig.projbuild`,
  `components/nostr_store/include/nostr_store.h`).
- relay_types.h is byte-identical between 4e861741 and HEAD (verified by
  diff), so envelope constants (§3) are era-independent.

No source, test, header, or config file was modified to produce this
document. The only artifact created is this file.