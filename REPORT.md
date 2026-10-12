# Task Report — test_relay_pipeline.c mock / stand-in contract analysis

**Status:** COMPLETE (read-only analysis)
**Repo / branch under analysis:** balloon-fresh, `autonomous/mesh-baseline` @ `fb36809`
**Target file:** `tracker/firmware/main/test/test_relay_pipeline.c`
**File facts:** 637 lines, 23649 bytes, md5 `e3185ac3d3c8db2d49f27dd9e2c16547`
**Isolation:** analysis worktree `~/worktrees/t_relaymocks` (branch `worker-heavy/relay-mock-contract`). The shared repo `~/repos/balloon-fresh` and the branch worktree `~/worktrees/tg-proto-contract` were read-only inspected; the target file is byte-identical (same md5) across all three.
**Modified:** nothing in the analyzed tree — this report is the only deliverable.

---

## 1. What the "mock" actually is (scope of stand-in)

The file's own design statement (lines 1–18, 36–41, 86–95) is the contract we bind to:

> `radio_task (mock) → rx_queue → app_task (extracted logic) → nostr_store`
> "The app_task dispatch logic from app_task.cpp is re-implemented here in plain C, calling the REAL nostr_store code."

Two stand-ins exist, and one thing that people *assume* is mocked but is NOT:

| Piece | Real / Mock | Where |
|---|---|---|
| `mock_queue_t` ring buffer (head/tail/count) | **MOCK** — replaces FreeRTOS `xQueueSend`/`xQueueReceive` on `g_rx_queue`/`g_tx_queue` | test lines 43–73 |
| `app_task_process_packet()` dispatch | **STAND-IN (re-implemented)** — mirrors `app_task.cpp` main loop | test lines 97–164 |
| `tollgate_payment_proto` encode/decode | **REAL** — `#include "tollgate_payment_proto.h"` + links real `main/tollgate_payment_proto.c` (build line 14) | test line 83 |
| `nostr_store` | **REAL** — links `components/nostr_store/nostr_store.c` (build line 15) | test line 27 |
| `nostr_event_serialize/deserialize` | **REAL** — from `nostr_store.c` | tests via header |
| `relay_packet_t` / type tags / queue lengths | **REAL** — `#include "relay_types.h"` | test line 26 |

So the only *pure* mock is the queue; `app_task` dispatch is a faithful-to-intent **re-implementation** that is explicitly documented as extracted logic.

---

## 2. BINDING transcription of the stand-in implementation (verbatim)

> **BINDING NOTE.** The following is transcribed verbatim from `test_relay_pipeline.c`. Any consumer of this test that relies on the mock's behaviour must treat the exact code below as the contract — including the differences from `app_task.cpp` called out in §5. These are the mock's *authoritative* semantics; do not "correct" them silently.

### 2.1 Mock queue type + init (lines 43–55)
```c
typedef struct {
    relay_packet_t packets[16];
    int head;
    int tail;
    int count;
    int capacity;
} mock_queue_t;

static void mock_queue_init(mock_queue_t *q, int capacity)
{
    memset(q, 0, sizeof(*q));
    q->capacity = capacity;
}
```

### 2.2 Mock queue send (lines 57–64)
```c
static int mock_queue_send(mock_queue_t *q, const relay_packet_t *pkt)
{
    if (q->count >= q->capacity) return -1;  /* queue full */
    q->packets[q->tail] = *pkt;
    q->tail = (q->tail + 1) % q->capacity;
    q->count++;
    return 0;
}
```

### 2.3 Mock queue receive (lines 66–73)
```c
static int mock_queue_receive(mock_queue_t *q, relay_packet_t *out)
{
    if (q->count == 0) return -1;  /* empty */
    *out = q->packets[q->head];
    q->head = (q->head + 1) % q->capacity;
    q->count--;
    return 0;
}
```

### 2.4 app_task context (lines 97–100)
```c
typedef struct {
    nostr_store_t *store;
    mock_queue_t  *tx_queue;
} app_task_ctx_t;
```

### 2.5 app_task_process_packet — the dispatch stand-in (lines 102–164)
```c
static void app_task_process_packet(app_task_ctx_t *ctx, const relay_packet_t *pkt)
{
    if (pkt->len == 0) return;

    uint8_t pkt_type = pkt->data[0];

    switch (pkt_type) {

    case RELAY_TYPE_NOSTR_EVENT: {
        nostr_event_t event;
        memset(&event, 0, sizeof(event));

        /* Offset +1 to skip the type tag byte (matches app_task.cpp).
         *
         * NOTE: app_task.cpp checks == 0, but nostr_event_deserialize()
         * returns bytes consumed (>0) on success and 0 on error.
         * The == 0 check in app_task.cpp is a bug — it means events are
         * NEVER stored on the real firmware. We use the correct > 0 check
         * here so the pipeline actually works.
         * See: nostr_store.h line 125: "Returns bytes used, or 0 on error"
         */
        if (nostr_event_deserialize(&event, pkt->data + 1, (uint16_t)(pkt->len - 1)) > 0) {
            nostr_store_add(ctx->store, &event);
        }
        break;
    }

    case RELAY_TYPE_TOLLGATE_PAY: {
        tollgate_msg_hdr_t hdr;
        const uint8_t *payload = NULL;

        if (tollgate_proto_decode(pkt->data + 1, (uint16_t)(pkt->len - 1), &hdr, &payload) > 0) {
            /* Build ACK response (matches app_task.cpp logic) */
            relay_packet_t ack_pkt;
            memset(&ack_pkt, 0, sizeof(ack_pkt));
            ack_pkt.data[0] = RELAY_TYPE_TOLLGATE_ACK;

            tollgate_ack_payload_t ack;
            memset(&ack, 0, sizeof(ack));
            ack.price_sats = 0;  /* TODO: real price from config */

            int ack_len = tollgate_proto_encode(ack_pkt.data + 1,
                                                 RELAY_PACKET_MAX_SIZE - 1,
                                                 TG_MSG_ACK, hdr.seq,
                                                 (const char *)&ack,
                                                 (uint16_t)sizeof(ack));
            if (ack_len > 0) {
                ack_pkt.len = (size_t)(ack_len + 1);
                mock_queue_send(ctx->tx_queue, &ack_pkt);
            }
        }
        break;
    }

    case RELAY_TYPE_TELEMETRY:
        /* Ignored in relay mode (matches app_task.cpp) */
        break;

    default:
        /* Unknown/raw — ignored */
        break;
    }
}
```

### 2.6 Mock radio producer (lines 221–226)
```c
static void mock_radio_receive(mock_queue_t *rx_queue, const relay_packet_t *pkt)
{
    /* Simulates: radio recv → fill rx_pkt → xQueueSend(g_rx_queue, ...) */
    int rc = mock_queue_send(rx_queue, pkt);
    assert(rc == 0 && "RX queue full in mock radio");
}
```

---

## 3. Every struct member the mock touches

### 3.1 `relay_packet_t` (from `relay_types.h` lines 18–23) — touched by the stand-in
| Member | Type | Read | Write | Where |
|---|---|---|---|---|
| `data[]` | `uint8_t[512]` | `data[0]` (type tag) at L106; `data + 1` payload ptr L123/L133; also *writes* `data[0]` on the ACK packet L137 | — | dispatch + ack build |
| `len` | `size_t` | L104 (`== 0` guard), `len - 1` at L123/L133 | `ack_pkt.len = ack_len + 1` L149 | dispatch + ack build |
| `timestamp` | `uint32_t` | — (never read by stand-in) | set by helpers L196/L213 (`= 0`) | builders only |
| `rssi` | `int` | — (never read by stand-in) | set by helpers L197/L214 (`-70` / `-65`) | builders only |

Note: the stand-in reads `data[0]` as the type tag and then passes `data + 1` (offset +1) as the payload — this +1 split is the core wire convention the mock binds to.

### 3.2 `nostr_event_t` (from `nostr_store.h` lines 39–54) — passed *through* by the mock
Constructed by `make_nostr_event()` (L176–186), serialized by `build_nostr_relay_packet()` (L189–198), and round-tripped through the REAL `nostr_event_serialize`/`deserialize`. Members explicitly set/checked:
`id` (`NOSTR_EVENT_ID_SIZE`=32), `pubkey` (32), `created_at`, `kind`, `content_len`, `content` (`NOSTR_MAX_CONTENT`=480), `num_tags`, `tags[].key_len`, `tags[].value_len`, `tags[].key[16]`, `tags[].value[64]`.
**Members NEVER touched anywhere in the file:** `sig` (64 bytes) — consistent with `app_task.cpp`'s "V2 TODO: verify Schnorr once nostr_event_t has a sig field" (app_task.cpp L101–104). No signature verification in the mock.

### 3.3 `tollgate_msg_hdr_t` (from `tollgate_payment_proto.h` lines 49–55)
| Member | Type | Use |
|---|---|---|
| `seq` | `uint16_t` | READ (`hdr.seq` L145 → ACK encoding; `ack_hdr.seq == 42` L375; `h.seq == seq` L406); SET by encoder |
| `type` | `uint8_t` | READ (`ack_hdr.type == TG_MSG_ACK` L374; `h.type == TG_MSG_ACK` L405) |
| `version` | `uint8_t` | not read directly (asserted only via decode success) |
| `payload_len` | `uint16_t` | not read directly |
| `reserved` | `uint16_t` | not read directly |

### 3.4 `tollgate_ack_payload_t` (header lines 63–68) — partial touch
Written: `ack.price_sats = 0` (L141). Encoded with `(const char *)&ack, (uint16_t)sizeof(ack)`.
Members `session_id`, `expires_unix`, `quota_bytes` are zero-filled by `memset` (L140) but never explicitly assigned — **the entire 14-byte struct is sent as-is (all-zero except price_sats=0)**. This mirrors app_task.cpp L128–136.

### 3.5 `nostr_store_t` (nostr_store.h lines 79–86) — touched only via *pointer + API*
The mock holds `nostr_store_t *store` in `app_task_ctx_t` but never dereferences a member directly; all access is through `nostr_store_init/add/count/find`. (Its `index[256]`, `bloom`, `head`, `count`, `next_file_idx`, `storage_dir[64]` internals are the REAL store's concern.) `malloc(sizeof(nostr_store_t))` at L242 and `assert(store)` L243 — the test asserts the allocation.

### 3.6 Return / error handling of the stand-in

| Path | Condition | Return / effect | Contract |
|---|---|---|---|
| dispatch | `pkt->len == 0` | returns immediately, no side effect (L104) | empty packet is a no-op (Test 10) |
| NOSTR_EVENT | `deserialize(...) > 0` | `nostr_store_add()` called (L123–124) | success = bytes consumed > 0 |
| NOSTR_EVENT | `deserialize(...) <= 0` | event dropped silently (no else branch) | malformed → no store (Test 11) |
| TOLLGATE_PAY | `decode(...) > 0` | build ACK, call `encode` (L133) | success = sizeof(hdr) > 0 |
| TOLLGATE_PAY | `decode(...) <= 0` | no ACK, falls through (no else) | malformed PAY → no ACK |
| TOLLGATE_PAY ACK | `encode(...) > 0` | set `ack_pkt.len`, `mock_queue_send` (L148–150) | ACK queued |
| TOLLGATE_PAY ACK | `encode(...) <= 0` | ACK dropped (no send) | encode failure → no ACK |
| TELEMETRY | any | no-op (L156–157) | ignored (Test 6) |
| default / RAW / unknown | any | no-op (L160–161) | ignored (Test 7) |

**Observation:** `mock_queue_send`'s return value is *ignored* in `app_task_process_packet` (L150) — an ACK silently lost if tx_queue is full. Tests only assume tx_queue has room (capacity `RELAY_TX_QUEUE_LEN`=4). By contrast `mock_radio_receive` (L224–225) asserts `rc == 0`. This asymmetry is part of the mock's contract.

**Type-cast note:** The stand-in passes `(uint16_t)sizeof(ack)` for `payload_len` (L147), whereas the real `app_task.cpp` passes the bare `sizeof(ack_payload)` (a `size_t`) into the `uint16_t` param (app_task.cpp L136) — implicit narrowing. Same value (14) today; the cast in the mock is the cleaner form.

---

## 4. Symbol table (BINDING)

Kinds: `fn` (function), `struct` (type), `const` (constant/macro), `error-code`, `assert`.

### 4.1 Symbols DEFINED in test_relay_pipeline.c
| Symbol | Kind | Exact signature / definition | file:line |
|---|---|---|---|
| `TEST_DIR` | const (macro) | `#define TEST_DIR "/tmp/relay_test"` | 33 |
| `mock_queue_t` | struct | `{ relay_packet_t packets[16]; int head; int tail; int count; int capacity; }` | 43–49 |
| `mock_queue_init` | fn | `static void mock_queue_init(mock_queue_t *q, int capacity)` | 51 |
| `mock_queue_send` | fn | `static int mock_queue_send(mock_queue_t *q, const relay_packet_t *pkt)` → `0` ok / `-1` full | 57 |
| `mock_queue_receive` | fn | `static int mock_queue_receive(mock_queue_t *q, relay_packet_t *out)` → `0` ok / `-1` empty | 66 |
| `app_task_ctx_t` | struct | `{ nostr_store_t *store; mock_queue_t *tx_queue; }` | 97–100 |
| `app_task_process_packet` | fn | `static void app_task_process_packet(app_task_ctx_t *ctx, const relay_packet_t *pkt)` | 102 |
| `clean_test_dir` | fn | `static void clean_test_dir(void)` (system("rm -rf " TEST_DIR)) | 170 |
| `make_nostr_event` | fn | `static void make_nostr_event(nostr_event_t *evt, uint8_t id_byte, const char *content)` | 176 |
| `build_nostr_relay_packet` | fn | `static void build_nostr_relay_packet(relay_packet_t *pkt, const nostr_event_t *evt)` | 189 |
| `build_tollgate_pay_packet` | fn | `static void build_tollgate_pay_packet(relay_packet_t *pkt, uint32_t seq)` | 201 |
| `mock_radio_receive` | fn | `static void mock_radio_receive(mock_queue_t *rx_queue, const relay_packet_t *pkt)` | 221 |
| `main` | fn | `int main(void)` → always `0`; 12 tests | 232 |

### 4.2 Symbols USED (extern) — with binding assumptions
| Symbol | Kind | Exact signature / definition | file:line (defn) | Assumption baked into the mock |
|---|---|---|---|---|
| `relay_packet_t` | struct | `{ uint8_t data[512]; size_t len; uint32_t timestamp; int rssi; }` | relay_types.h 18–23 | `data[0]` is the type tag; `data+1` is payload; `data` at offset 0 |
| `RELAY_PACKET_MAX_SIZE` | const | `512` | relay_types.h 6 | buffer capacity used as `-1` bound in builders |
| `RELAY_RX_QUEUE_LEN` | const | `8` | relay_types.h 7 | passed to `mock_queue_init(&rx_queue, …)` L238 |
| `RELAY_TX_QUEUE_LEN` | const | `4` | relay_types.h 8 | passed to `mock_queue_init(&tx_queue, …)` L239 |
| `RELAY_TYPE_NOSTR_EVENT` | const | `0x01` (asserted L622) | relay_types.h 11 | dispatch case tag |
| `RELAY_TYPE_TOLLGATE_PAY` | const | `0x02` (asserted L623) | relay_types.h 12 | dispatch case tag |
| `RELAY_TYPE_TOLLGATE_ACK` | const | `0x03` (asserted L624) | relay_types.h 13 | ACK tag written at data[0] |
| `RELAY_TYPE_TELEMETRY` | const | `0x04` (asserted L625) | relay_types.h 14 | ignored case |
| `RELAY_TYPE_RAW` | const | `0xFF` (asserted L626) | relay_types.h 15 | default/unknown (see §5 caveat) |
| `nostr_event_t` | struct | 32 id / 32 pubkey / 64 sig / u32 created_at / u16 kind / u16 content_len / u8 content[480] / u8 num_tags / tags[8]{u8 key_len,u8 value_len,char key[16],char value[64]} | nostr_store.h 39–54 | serialized/deserialized whole |
| `nostr_store_t` | struct | `{ index[256]; bloom; head; count; next_file_idx; char storage_dir[64]; }` | nostr_store.h 79–86 | heap-allocated; only via API |
| `NOSTR_EVENT_ID_SIZE` | const | `32` | nostr_store.h 10 | id array sizing |
| `NOSTR_PUBKEY_SIZE` | const | `32` | nostr_store.h 11 | pubkey fill |
| `NOSTR_MAX_CONTENT` | const | `480` | nostr_store.h 13 | content buffer sizing (not referenced by name in the test) |
| `NOSTR_MAX_TAGS` | const | `8` | nostr_store.h 14 | tags[2] used |
| `NOSTR_TAG_MAX_LEN` | const | `64` | nostr_store.h 15 | tag value sizing |
| `nostr_store_init` | fn | `void nostr_store_init(nostr_store_t *store, const char *storage_dir)` | nostr_store.h 107 | call L244 with TEST_DIR |
| `nostr_store_add` | fn | `int nostr_store_add(nostr_store_t *store, const nostr_event_t *event)` → `0` stored / `1` dup / `-1` err | nostr_store.h 108 | return value IGNORED by mock (L124) |
| `nostr_store_count` | fn | `uint16_t nostr_store_count(const nostr_store_t *store)` | nostr_store.h 111 | used for assertions |
| `nostr_store_find` | fn | `int nostr_store_find(nostr_store_t *store, const uint8_t *id, nostr_event_t *out)` → `0` found / `-1` | nostr_store.h 110 | L279/L321/L552 |
| `nostr_event_serialize` | fn | `uint16_t nostr_event_serialize(const nostr_event_t *event, uint8_t *buf, uint16_t buf_size)` | nostr_store.h 125 | L193 |
| `nostr_event_deserialize` | fn | `uint16_t nostr_event_deserialize(nostr_event_t *event, const uint8_t *buf, uint16_t buf_len)` → bytes used, or **0** on error | nostr_store.h 126 | **critical**: mock checks `> 0` |
| `tollgate_msg_hdr_t` | struct (packed) | `{ u8 version; u8 type; u16 seq; u16 payload_len; u16 reserved; }` | tollgate_payment_proto.h 49–55 | decode target |
| `tollgate_ack_payload_t` | struct (packed) | `{ u32 session_id; u32 expires_unix; u32 quota_bytes; u16 price_sats; }` (14 B) | tollgate_payment_proto.h 63–68 | `price_sats=0`; whole struct encoded |
| `TG_MSG_ACK` | const (enum) | `= 0x02` | tollgate_payment_proto.h 41 | ACK type (L145/L374/L405) |
| `TG_MSG_PAY` | const (enum) | `= 0x01` | tollgate_payment_proto.h 40 | PAY type (L209) |
| `tollgate_proto_encode` | fn | `int tollgate_proto_encode(uint8_t *buf, uint16_t buf_len, tollgate_msg_type_t type, uint16_t seq, const char *payload, uint16_t payload_len)` → bytes written or `-1` | tollgate_payment_proto.h 94 | L143/L207 |
| `tollgate_proto_decode` | fn | `int tollgate_proto_decode(const uint8_t *data, uint16_t len, tollgate_msg_hdr_t *hdr, const uint8_t **payload)` → `sizeof(hdr)` on success **or -1** | tollgate_payment_proto.h 107 | mock checks `> 0` |

### 4.3 Header-documented error codes (referenced family; none are triggered by the test)
| Symbol | Kind | Definition | file:line |
|---|---|---|---|
| `TG_ERR_INVALID_TOKEN` | error-code | `(-1)` | tollgate_payment_proto.h 77 |
| `TG_ERR_SWAP_FAILED` | error-code | `(-2)` | tollgate_payment_proto.h 78 |
| `TG_ERR_MINT_UNREACHABLE` | error-code | `(-3)` | tollgate_payment_proto.h 79 |
| `TG_ERR_ALREADY_PAID` | error-code | `(-4)` | tollgate_payment_proto.h 80 |
| `TG_ERR_RATE_LIMITED` | error-code | `(-5)` | tollgate_payment_proto.h 81 |

`TG_MSG_NACK (0x03)`, `TG_MSG_STATUS (0x04)`, `TG_MSG_INFO (0x05)`, `TG_MSG_REVOKE (0x06)` are defined but never used by the mock.

### 4.4 Standard-library / libc symbols used
`printf`, `malloc`, `free`, `memset`, `memcpy`, `memcmp`, `strlen`, `system`, `assert` (from `<stdio.h> <stdlib.h> <string.h> <assert.h> <sys/stat.h>`; `<sys/stat.h>` is included L24 but its symbols are not otherwise used).

---

## 5. Disagreements with other consumers (visible)

> These are the points where the stand-in and/or its comments **disagree with the real consumer** `main/app_task.cpp`. They are marked so the contract owner can reconcile them; the mock is NOT silently authoritative over production.

1. **[HIGH] Stale/incorrect comment vs. real code.** The mock's NOSTR_EVENT comment (test lines 116–121) claims: *"app_task.cpp checks == 0 … The == 0 check in app_task.cpp is a bug — it means events are NEVER stored on the real firmware."* **This is factually wrong for the current tree.** `app_task.cpp:100` reads `if (nostr_event_deserialize(&event, pkt.data + 1, pkt.len - 1) > 0)` — i.e. it already uses the correct `> 0` check, matching the mock. The comment is a leftover from an earlier revision (likely the pre-fix `== 0` version). *Action for contract owner: correct or delete this comment; it currently libels the production code.*

2. **[MED] Decode success test: strict `> 0` (mock) vs. permissive `>= 0` (app_task.cpp).** Mock L133: `tollgate_proto_decode(...) > 0`. Real app_task.cpp L120: `tollgate_proto_decode(...) >= 0`. Per the header doc (line 105) decode returns `sizeof(tollgate_msg_hdr_t)` (=8) on success or `-1` on invalid header — so both are functionally equivalent today. But `>= 0` would *also* accept a hypothetical `0` return (which would be a malformed/zero-length header), so the real code is marginally more permissive. Disagreement is behavioural only at the `== 0` boundary.

3. **[LOW] `sizeof` cast in encode call.** Mock L147: `(uint16_t)sizeof(ack)`; app_task.cpp L136: bare `sizeof(ack_payload)` (size_t → uint16_t implicit narrowing). Same value (14). Mock form is explicit.

4. **[INFO] Signature-verification divergence is shared, not divergent.** Neither the mock nor app_task.cpp verifies the Schnorr `sig` (app_task.cpp L101–104 carries the "TODO V2" note; the mock never touches `sig`). Not a disagreement — a *mutual known gap* that both callers inherit from the current `nostr_event_t` schema.

5. **[INFO] `nostr_store_add` return ignored** in both mock (L124) and app_task.cpp (L105) — consistent.

6. **[INFO] `RELAY_TYPE_RAW` semantics.** `relay_types.h` defines `RELAY_TYPE_RAW = 0xFF` as a named tag, but both the mock (`default:` L160) and app_task.cpp (`default:` L151) treat unknown/raw packets through the *default* branch, not a dedicated `case RELAY_TYPE_RAW:`. Also app_task.cpp L90 substitutes `RELAY_TYPE_RAW` when `pkt.len == 0` before the switch, whereas the mock short-circuits `len == 0` *before* reading `data[0]` (L104). Equivalent outcome (no-op), different mechanism.

---

## 6. Assumptions made during this analysis

1. "Mock / stand-in implementation" = the two test-local constructs (`mock_queue_t` family and `app_task_process_packet`) plus `mock_radio_receive`. `tollgate_payment_proto.c` and `nostr_store.c` are real and only transcribed as *used contracts*, not as mocks.
2. File:line references are 1-indexed to the 637-line target file (md5 `e3185ac3...`). Header references are to the files as present in the same worktree/branch.
3. The mock's comments are treated as *claims to verify*, not ground truth — claim #1 in §5 was verified against `app_task.cpp` and found false.
4. `assert()` is active (test builds without `-DNDEBUG`; build line 12 uses `-Wall -O2`, no `-DNDEBUG`), so all `assert` lines are real checks in the contract.
5. Static functions are `static` (internal linkage) — they are not part of any exported ABI; "binding" here means *behavioural* contract for consumers of this test, not link-time symbols.

---

## 7. Verification — read-only confirmation + git tree state

- Target file read in full (637/637 lines, two reads).
- All three dependency headers read in full: `relay_types.h` (23 L), `nostr_store.h` (133 L), `tollgate_payment_proto.h` (114 L).
- Real consumer `app_task.cpp` (164 L) read in full to source §5 disagreements.
- md5 cross-check: target file identical in shared repo and branch worktree (`e3185ac3d3c8db2d49f27dd9e2c16547`).
- `git status` in the analyzed tree: reported in §8 below.

## 8. Read-only / cleanliness confirmation

The analyzed tree (`autonomous/mesh-baseline` content) was never written to. All artifacts (this REPORT.md, PROGRESS.md) were created only in the isolated analysis worktree `~/worktrees/t_relaymocks`, whose branch is `worker-heavy/relay-mock-contract` (not the analyzed branch). `git status` on the analyzed tree is reproduced verbatim in the final reply. Nothing was modified, created, or deleted in `tracker/firmware/`.
