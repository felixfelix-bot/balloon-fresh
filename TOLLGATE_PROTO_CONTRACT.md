# TOLLGATE_PROTO_CONTRACT.md — Authoritative API Contract for `tollgate_payment_proto.h`

**Scope:** `tracker/firmware/main/tollgate_payment_proto.{h,c}` on branch `autonomous/mesh-baseline`.
**Revision:** 3 (2026-09-27, card `balloon:t_c360db44`) — see §0 for what changed and §0.5
for the review that prompted it.
**Status:** Normative **for the API shape** (field layouts, wire format, prototypes,
return-value semantics, error codes). The code and the pinned tests are normative **for the
values they assert**: where this document and the code disagree on a number the tests pin,
the tests win and this document is a bug — but where this document names a clause the code
violates, the code is the defect and gets a card (§7.1 D1/D2). Do not silently re-derive the
contract from the implementation.
**Related:** ADR-002 (`docs/adr/002-tollgate-over-fips-mesh-udp.md`), upstream component
`mesh-stack/tollgate/components/tollgate_balloon/`, sibling spec
`tracker/firmware/TOLLGATE_PROTO_API.md` (§0.2).

---

## 0. Provenance, revision status, and reconciliation (read this first)

**Revision 3**, 2026-09-27, card `balloon:t_c360db44`: revision 1 (commit `01f09534`) was
authored when the four recon inputs this card was meant to synthesize did not exist;
revision 2 reconciled the document with the shipped code and pinned tests; revision 3 applies
the six lineage-accuracy corrections raised by the cold cross-family review of revision 2
(§0.5). The normative content is unchanged from revision 2.

### 0.1 Inputs — what exists, and which of the four inputs actually ship on this branch

Revision 1 worked around four recon inputs that did not exist yet. All four now exist **on
the local lineage** (`autonomous/mesh-baseline`), but only **one** of them is tracked on
`origin/main` — the branch that carries this file (measured 2026-09-27 with
`git ls-tree -r origin/main --name-only | grep -iE "recon|PROTO_API|payack"`). The lineage
column below is therefore load-bearing: a reader on the published branch can open exactly
one row of this table.

| Recon input | Ships on `origin/main`? | Location / commit |
|---|---|---|
| spec search (upstream) | **NO — local lineage only** | `tracker/firmware/TOLLGATE_PROTO_API.md` (commit `2ab5058e`) + `docs/tollgate-payack-upstream-audit-2026-09-14.md` (commit `a9b9126f`) |
| app_task call sites | **NO — local lineage only** | `docs/recon/tollgate_proto_app_task_callsites.md` (commit `c45dec77`, 452 lines) |
| test/mock usage | **YES — tracked** | `docs/recon/tollgate_proto_test_mock.md` (514 lines, tracked by `b8aa95bf`) |
| framing + config | **NO — local lineage only** | `docs/recon/tollgate_proto_framing_config.md` (commit `b7db8b31`) + `docs/recon/.tollgate_framing_notes.md` (untracked on both lineages) |

Cross-check: the sibling index `tracker/firmware/.tollgate-recon-index.md` (card
`balloon:t_7676d001`, local lineage only) independently records the same three producer
reports and their commits.

Because three of the four inputs are absent from the published branch, **this file is
written to stand alone**: every value, layout, prototype and citation it needs is restated
in §2–§5, and the one input that does ship is the mock-usage recon
(`docs/recon/tollgate_proto_test_mock.md`). Nothing here requires the local-only files to
be readable.

The card body referenced repo path `~/repos/balloon-fresh/tracker/firmware/`; that path
does **not** exist on this machine. The actual worktree is `~/repos/balloon` (repo root,
remote `origin = https://github.com/felixfelix-bot/balloon-fresh.git`), already on branch
`autonomous/mesh-baseline` and containing `tracker/firmware/`. Same path correction as the
recon index.

### 0.2 Relationship to `tracker/firmware/TOLLGATE_PROTO_API.md` (no contradiction)

Two contract documents exist on this branch. They are **not** in conflict after this
revision; the division of labour is:

| Document | Scope |
|---|---|
| `tracker/firmware/TOLLGATE_PROTO_API.md` | Wire-format + API contract for the tracker-firmware copy, including it, with worked byte-layout examples and the full symbol coverage table |
| **this file** (`TOLLGATE_PROTO_CONTRACT.md`, repo root) | Same contract expressed as a **call-site conformance checklist**: field layouts, prototypes, return-value semantics, and a line-by-line mapping from every consumer back to the clause it depends on |

**Lineage caveat:** `tracker/firmware/TOLLGATE_PROTO_API.md` is **local-lineage-only** — it is
absent from `origin/main` (measured 2026-09-27). A reader on the published branch cannot open
it, so its §7 content is summarised in the table below and nothing in this file depends on
the sibling document being present.

`TOLLGATE_PROTO_API.md` §7 recorded three points where revision 1 of this file contradicted
the shipped code and pinned tests. Revision 2 resolves all three in favour of the code and
tests, and records the two remaining **implementation** deviations as filed defects (§7).
The three resolutions:

| # | Revision-1 text | Resolution (rev 2) |
|---|---|---|
| 7.1 | `tollgate_nack_payload_t` described as `packed (16 bytes)` | **Arithmetic error.** `int16_t(2) + char[128](128) = 130` bytes packed. Corrected in §3. |
| 7.2 | `encode(payload == NULL, payload_len > 0)` left as an either/or ("callers must not depend on it") | **Now normative: MUST return −1 and write nothing.** §5 clause E4. The shipped `.c` still succeeds in this case — filed as defect **DEF-1** (§7.1). |
| 7.3 | `decode(hdr == NULL)` silent | **Now normative: MUST return −1 with no writes.** §5 clause D1. The shipped `.c` dereferences NULL — filed as defect **DEF-2** (§7.1). |

No other clause of revision 1 changed its meaning; every number, offset, prototype, and
error value below is byte-for-byte what the pinned tests assert.

### 0.3 Primary sources actually used (revision 2)

| Topic | Source |
|---|---|
| Spec search (upstream) | `mesh-stack/tollgate/components/tollgate_balloon/include/tollgate_balloon.h`, `.../include/tollgate_payment_proto.h`, `.../src/tollgate_payment_proto.c`; `docs/adr/002-tollgate-over-fips-mesh-udp.md` |
| app_task call sites | `tracker/firmware/main/app_task.cpp` lines 32–33, 114–145 |
| Test/mock usage | `tracker/firmware/main/test/test_relay_pipeline.c` (lines 76–83, 101–164, 200–215, TEST 4/5/8/12); `tracker/firmware/main/test/test_tollgate_payment_proto.c` (14 test functions locally / 10 on `origin/main`) |
| Framing + config | `tracker/firmware/main/relay_types.h`; `main/Kconfig.projbuild` lines 141–147; `main/CMakeLists.txt` lines 29–31; `sdkconfig` line 576 |
| Shipped header + impl | `tracker/firmware/main/tollgate_payment_proto.h`, `tracker/firmware/main/tollgate_payment_proto.c` |

### 0.4 Lineage / applicability — read before treating a mismatch as a doc error

This contract was authored on the **local** lineage `autonomous/mesh-baseline`
(`~/repos/balloon`), which carries the protocol-hardening commit `38360fb1`
("test+fix(tollgate): msg_type validation, canary overflow checks, boundary tests"). The
published lineage `origin/main` (the base of the branch that carries this file) does **not**
carry `38360fb1` yet. Measured difference, 2026-09-27:

| Artifact | Local `autonomous/mesh-baseline` | `origin/main` |
|---|---|---|
| `tollgate_payment_proto.c` | 66 lines, `tg_type_is_valid()` bounds check in encode **and** decode | 53 lines, **no** bounds check |
| `tollgate_payment_proto.h` | return-value docs name the invalid-msg_type case | docs omit it |
| `test_tollgate_payment_proto.c` | 550 lines / 14 test functions / **133 assertions** → 133 passed, 0 failed | 334 lines / 10 test functions / **83 assertions** → 83 passed, 0 failed |
| `test_relay_pipeline.c` | 12/12 passed | 12/12 passed (byte-identical) |
| `app_task.cpp`, `relay_types.h` | byte-identical | byte-identical |
| `sdkconfig` line 576 | `CONFIG_ENABLE_TOLLGATE=y` (set by `55d79702`, local-only) | `# CONFIG_ENABLE_TOLLGATE is not set` — **feature compiled out at this head** (§6 item 5) |

All four test counts above were re-measured on the published head
`68c27cdda74f0f87b57029be42dd118b633f9c24` on 2026-09-27 (see §9 re-verification record).

Consequences for a reader on a branch whose base is `origin/main`:

- **Clauses violated on both lineages:** §5 E4 (`payload == NULL` with `payload_len > 0`)
  and §5 D1 (`hdr == NULL`) — defects **DEF-1**/**DEF-2** (§7.1). These are the defects a fix
  card must close.
- **Clauses satisfied only where `38360fb1` is present:** §5 E2 (encode rejects a `type`
  outside 0x01..0x06 without touching the buffer), §5 D5 (decode rejects such a type), and
  the canary/no-write guarantees proven by unit tests 11–14. On `origin/main` these are
  **unimplemented**, and unit tests 11–14 do not exist there (the published test file has 10
  test functions, hence 83 vs 133 assertions — the 50-assertion gap is exactly tests 11–14).
  A fix card that ports `38360fb1` closes this gap.
- **Compiled out unless enabled:** at the published head the whole payment feature is
  disabled (§6 item 5) — `tollgate_payment_proto.c` is not in the build and the PAY dispatch
  arm is compiled out. Any reader acting on this contract on `origin/main` must enable
  `CONFIG_ENABLE_TOLLGATE` first (or port `55d79702`); otherwise nothing here is executable.
- **Nothing in this document is contradicted by either lineage.** Every clause is either
  already implemented on both, or named here as a defect on one/both.

This document is therefore the **target** contract: it is normative for what the code must
do, not a description of what every branch does today. Before filing a "the contract is
wrong" bug, check which lineage you are on and re-read §7.1.

### 0.5 Revision 3 — cold-review corrections (F1–F6)

Revision 2 was reviewed cold and cross-family (card `balloon:t_9a5c6230`, reviewer
`glm-5.3`, tier `tier/review-glm`; author family deepseek) against published head
`68c27cdd`. Verdict: **CHANGES-REQUESTED** — the normative core (§5 clauses, DEF-1/DEF-2,
their blast radius) was independently re-derived and confirmed, but six statements were
false *on the lineage this file ships on*. Revision 3 applies all six; every number below
was re-measured first-hand on `origin/main`@`68c27cdd` before the edit.

| # | Finding (rev 2) | Fix in rev 3 |
|---|---|---|
| F1 | §6.5 claimed `CONFIG_ENABLE_TOLLGATE=y` in the tracked sdkconfig; on `origin/main` it reads `# CONFIG_ENABLE_TOLLGATE is not set`, so the feature is compiled out at the published head | §6 item 5 rewritten for the published value; §0.4 table row added |
| F2 | §0.1/§0.2/§0.3 treated all four recon inputs and the sibling spec as readable; only `docs/recon/tollgate_proto_test_mock.md` exists on `origin/main` | §0.1 relabelled by lineage + stand-alone statement; §0.2 lineage caveat; new gap §7.2 G2 |
| F3 | §0.1/§7.2 G1 called the mock recon "untracked, 504 lines"; it is tracked by `b8aa95bf` and is 514 lines | §0.1 row corrected; G1 closed for that file, remaining untracked files listed |
| F4 | §9 printed only 133/133 under a heading that applies to both lineages; the published branch yields 83/83 | §9 records split by lineage, both re-run first-hand; tests 11–14 marked local-only |
| F5 | §0.4 said "unit tests 11–13 do not exist there"; tests 11–**14** are absent (10 vs 14 test functions) | §0.4 corrected to 11–14 with measured file sizes |
| F6 | §5 E4 and §7.1 cited `.c:39`/`.c:53` — local-lineage numbers that point at unrelated code on `origin/main` | both lineages' line numbers now given, with the `origin/main` mapping stated |

No normative value, offset, prototype or error code changed in rev 3, and the two filed
defects (DEF-1/DEF-2) are unchanged and still open.

---

## 1. Relay frame layout (outer framing, tracker-local)

TollGate messages never travel alone on the tracker relay pipeline. They are carried in a
`relay_packet_t` (512-byte `data[]`, fields `len`/`timestamp`/`rssi`) between `radio_task`
and `app_task` via FreeRTOS queues. The first byte of `data[]` is a **relay type tag**:

```
Byte:      0                1                2 ... 8                9 ...
        ┌──────────┬──────────────────────────────┬──────────────────────────┐
Field:  │ relay tag │   tollgate_msg_hdr_t (8 B)   │   payload (N bytes)      │
        └──────────┴──────────────────────────────┴──────────────────────────┘
```

- Tag values (`relay_types.h`): `RELAY_TYPE_NOSTR_EVENT=0x01`, `RELAY_TYPE_TOLLGATE_PAY=0x02`,
  `RELAY_TYPE_TOLLGATE_ACK=0x03`, `RELAY_TYPE_TELEMETRY=0x04`, `RELAY_TYPE_RAW=0xFF`.
- `RELAY_TYPE_TOLLGATE_PAY` (0x02) frames a client→balloon message (normally `TG_MSG_PAY`).
- `RELAY_TYPE_TOLLGATE_ACK` (0x03) frames a balloon→client message (normally `TG_MSG_ACK`).
- The tag byte is **outside** the TollGate message: every API below operates on
  `data + 1` with `len - 1`. `app_task.cpp:120` and the mock both pass `pkt.data + 1, pkt.len - 1`.
- Direction is carried by the **relay tag**, not by the inner TollGate type. The tag byte and
  the inner `type` byte are two independent namespaces (see §4 collision table).
- **Size budget:** `RELAY_PACKET_MAX_SIZE = 512`, so a framed TollGate message is at most
  511 bytes, i.e. header + payload ≤ 503 payload bytes. The current ACK frame is
  1 + 8 + 14 = 23 bytes. A full-size Cashu token (`TOLLGATE_MAX_TOKEN_LEN = 2048`) does
  **not** fit in one relay packet — see §7 (open constraint).

## 2. `tollgate_msg_hdr_t` — field layout

Normative declaration (already in the header; reproduced here as the contract):

```c
typedef struct {
    uint8_t  version;       /* offset 0 */
    uint8_t  type;          /* offset 1 */
    uint16_t seq;           /* offset 2 */
    uint16_t payload_len;   /* offset 4 */
    uint16_t reserved;      /* offset 6 */
} __attribute__((packed)) tollgate_msg_hdr_t;   /* sizeof == 8, no padding */
```

| Offset | Field       | Type     | Bytes | Endianness | Meaning / rule |
|-------:|-------------|----------|------:|------------|----------------|
| 0 | `version`     | `uint8_t`  | 1 | — | Must be `TOLLGATE_PROTO_VERSION` (1). Encode always writes 1; decode rejects any other value. |
| 1 | `type`        | `uint8_t`  | 1 | — | `tollgate_msg_type_t` value, 0x01–0x06 (§4). Both encode and decode reject values outside 1..6. |
| 2 | `seq`         | `uint16_t` | 2 | little-endian | Sequence number for dedup; echoed verbatim by the balloon in the ACK. |
| 4 | `payload_len` | `uint16_t` | 2 | little-endian | Bytes of payload following the header. Must equal `frame_len − 8` exactly on decode (truncation check). |
| 6 | `reserved`    | `uint16_t` | 2 | little-endian | Encode writes 0. Decode does not require 0 (forward-compat) — unit tests pin round-trip of 0. |
| | **Total** | | **8** | | Packed, no padding. |

**Endianness:** all multi-byte fields serialize **little-endian**. Justification: (a) encode
casts the caller buffer to the packed struct and writes native-endian fields, and both ends
in this deployment are LE (ESP32-S3 Xtensa LX7, Linux/x86 host tests); (b) the unit test
vector pins it: seq=100 is the byte pair `64 00` (`test_tollgate_payment_proto.c` test 5);
(c) same packed-struct-cast technique as upstream. Caveat for implementers: a big-endian
host would emit non-conforming frames; the contract norm is the LE byte order, not
"whatever the host does".

**Per-field justification (call site / mock that demands it):**

- `version` — `app_task.cpp` and the mock must reject stale/garbage frames; unit test 7 pins
  rejection of 0, 2, 0xFF. Inherited from upstream (`tollgate_balloon.h:41`).
- `type` — dispatch (`TG_MSG_ACK` check at `test_relay_pipeline.c:374,405,513`); value-range
  validation 1..6 is tracker-added hardening (tests 11, 12).
- `seq` — the entire PAY→ACK path depends on it: `app_task.cpp:134` echoes `hdr.seq` into the
  ACK; mock asserts `h.seq == 42` (TEST 4), `seq` 100–104 round-trip (TEST 5), `200..203`
  preserved through mixed traffic (TEST 8); unit test 14 pins boundaries 0, 1, 0xFFFF.
  Inherited from upstream.
- `payload_len` — needed to make decode total-length safe without an outer length (tests 5,
  8, 13). The ACK path relies on `payload_len` matching `sizeof(tollgate_ack_payload_t)=14`
  so the mock can `decode(... ) > 0` then reinterpret the payload.
- `reserved` — alignment/future-use; keeps the header 8 bytes. Upstream field; encode pins 0.

`sizeof(tollgate_msg_hdr_t) == 8` and offsets 0/1/2/4/6 are asserted in unit test 1 and are
**contract** (a padded 10- or 12-byte struct would be a violation, not a style choice).

## 3. `tollgate_ack_payload_t` — field layout

Normative declaration:

```c
typedef struct {
    uint32_t session_id;      /* offset 0  */
    uint32_t expires_unix;    /* offset 4  */
    uint32_t quota_bytes;     /* offset 8  */
    uint16_t price_sats;      /* offset 12 */
} __attribute__((packed)) tollgate_ack_payload_t;   /* sizeof == 14 */
```

| Offset | Field         | Type     | Bytes | Endianness | Meaning |
|-------:|---------------|----------|------:|------------|---------|
| 0 | `session_id`   | `uint32_t` | 4 | LE | Session identifier (balloon-assigned). |
| 4 | `expires_unix` | `uint32_t` | 4 | LE | Session expiry, Unix seconds. |
| 8 | `quota_bytes`  | `uint32_t` | 4 | LE | Data quota; 0 = unlimited/time-based. |
| 12 | `price_sats`   | `uint16_t` | 2 | LE | Price actually charged, sats. |
| | **Total** | | **14** | | Packed. |

**Per-field justification:**

- Whole struct: `app_task.cpp:128-136` builds it on the stack, memsets it to 0, and passes
  `(const char *)&ack_payload, sizeof(ack_payload)` to encode; the mock mirrors this
  (`test_relay_pipeline.c:139-147`). Unit test 10 pins `sizeof == 14`; test 14 round-trips
  all-`0xFFFFFFFF`/`0xFFFF` fields. Layout is byte-identical to upstream
  (`mesh-stack/.../tollgate_payment_proto.h:29-34`).
- `session_id` / `expires_unix` / `quota_bytes` — carried for the future real session logic;
  current call sites zero them (session not yet implemented).
- `price_sats` — `app_task.cpp:130` and mock line 141 set it to 0 with a
  `TODO: real price from config`; unit tests 10 and 14 exercise values 0, 1, 21, `0xFFFF`,
  so the field must round-trip the full uint16 range now, before config wiring lands.

Other payload structs in the same header (for completeness; not sent by current tracker call
sites but part of the wire contract): `tollgate_pay_payload_t` = `char token[2048]`;
`tollgate_nack_payload_t` = `int16_t error_code` + `char message[128]` packed — **130 bytes**
(`2 + 128`; revision 1 of this file said "16 bytes", which was an arithmetic error;
confirmed against `tollgate_payment_proto.h:71-74`), with
`TG_ERR_INVALID_TOKEN −1`, `TG_ERR_SWAP_FAILED −2`, `TG_ERR_MINT_UNREACHABLE −3`,
`TG_ERR_ALREADY_PAID −4`, `TG_ERR_RATE_LIMITED −5`. All inherited from upstream.

## 4. Message type values and relay-tag relationship

```c
typedef enum {
    TG_MSG_PAY    = 0x01,  /* Client → Balloon: Cashu token payment */
    TG_MSG_ACK    = 0x02,  /* Balloon → Client: payment accepted + session info */
    TG_MSG_NACK   = 0x03,  /* Balloon → Client: payment rejected + reason */
    TG_MSG_STATUS = 0x04,  /* Client → Balloon: request status/pricing */
    TG_MSG_INFO   = 0x05,  /* Balloon → Client: status response */
    TG_MSG_REVOKE = 0x06,  /* Balloon → Client: session revoked */
} tollgate_msg_type_t;
```

- Valid range: **0x01..0x06** (`TG_MSG_TYPE_MIN..MAX` in the .c). Encode and decode both
  reject anything else. Boundaries are tested: 0x00, 0x07, 0xFF rejected; 0x01 and 0x06
  accepted (unit tests 11, 12).
- `TG_MSG_PAY = 0x01` and `TG_MSG_ACK = 0x02` are the two values exercised end-to-end:
  PAY built by `build_tollgate_pay_packet()` (mock, line 207-210), ACK built by
  `app_task.cpp:132-136` and mock lines 143-147.
- **Relationship to relay tags:** the relay tag selects the pipeline dispatch case
  (`case RELAY_TYPE_TOLLGATE_PAY:` at `app_task.cpp:115`); the inner `type` identifies the
  TollGate message kind inside the framed message. They occupy different bytes and are
  **independent namespaces** that happen to overlap numerically:

| Value | Relay tag (frame byte 0) | TollGate msg type (frame byte 1) |
|------:|--------------------------|----------------------------------|
| 0x01 | `RELAY_TYPE_NOSTR_EVENT` | `TG_MSG_PAY` |
| 0x02 | `RELAY_TYPE_TOLLGATE_PAY` | `TG_MSG_ACK` |
| 0x03 | `RELAY_TYPE_TOLLGATE_ACK` | `TG_MSG_NACK` |
| 0x04 | `RELAY_TYPE_TELEMETRY` | `TG_MSG_STATUS` |

  Consequences that implementers MUST respect:
  - `RELAY_TYPE_TOLLGATE_ACK == 0x03` does **not** mean the frame contains a NACK. The inner
    `type` byte is authoritative for the message kind.
  - The pipeline currently maps one tag to one inner type in practice
    (tag 0x02 ⇒ `TG_MSG_PAY`, tag 0x03 ⇒ `TG_MSG_ACK`), but the protocol does not
    require it; decode must be called and its `hdr.type` checked, exactly as the mock does
    (`assert(h.type == TG_MSG_ACK)`, line 374).
  - Tag constants are pinned by `test_relay_pipeline.c` TEST 12 (0x01/0x02/0x03/0x04/0xFF).

## 5. Function prototypes and return-value semantics

```c
int tollgate_proto_encode(uint8_t *buf, uint16_t buf_len,
                          tollgate_msg_type_t type, uint16_t seq,
                          const char *payload, uint16_t payload_len);

int tollgate_proto_decode(const uint8_t *data, uint16_t len,
                          tollgate_msg_hdr_t *hdr,
                          const uint8_t **payload);
```

### `tollgate_proto_encode`

Writes `[hdr(8)][payload(payload_len)]` into `buf`. Returns:

- **Success:** total bytes written = `sizeof(tollgate_msg_hdr_t) + payload_len`
  (8 + N; header-only ⇒ 8). Always positive — required by the `if (ack_len > 0)` guards at
  `app_task.cpp:137` and mock line 148.
- **−1 on error**, zero bytes written in every error case (canary-proven, unit tests 12, 13):
  - **E1 — `buf == NULL`;**
  - **E2 — `type` outside 0x01..0x06** (checked before anything is written);
  - **E3 — buffer too small: `buf_len < 8 + payload_len`.** Precise boundary: `buf_len ==
    8 + payload_len` succeeds (exact fit, test 4/13 case 2); `buf_len == 7 + payload_len`
    fails (test 13 case 1) and **leaves the buffer 100% untouched** — no partial header,
    no partial payload.
- **Clause E4 — `payload == NULL` with `payload_len > 0` MUST return −1 and write nothing.**
  (`payload_status` was an unresolved either/or in revision 1; it is now normative.) The
  header's own parameter doc reads "may be `NULL` **if** `payload_len == 0`", and no pinned
  test exercises the lenient path. `payload` is therefore `NULL` **only when**
  `payload_len == 0` — both real call sites rely on exactly that:
  `build_tollgate_pay_packet` passes `NULL, 0`; `app_task.cpp`/`app_main.cpp` always pass a
  real pointer with a non-zero length. Reason the lenient behaviour is forbidden: the
  shipped `.c` (`.c:39-41` on the local lineage = `:28-30` on `origin/main`) skips the
  `memcpy` yet still writes `hdr->payload_len = N` and returns `8 + N` (local `.c:43` /
  `origin/main` `.c:32`), i.e. it emits a frame that claims N payload bytes which were never
  written — a corrupt frame that the receiver cannot detect. **The shipped `.c` violates
  clause E4 today — filed as defect DEF-1 in §7.1.**
- Note: `buf_len` is `uint16_t`; the ACK call site passes `RELAY_PACKET_MAX_SIZE - 1` (511).

### `tollgate_proto_decode`

Parses `[hdr(8)][payload]` from `data` (already tag-stripped). Returns:

- **Success:** `sizeof(tollgate_msg_hdr_t)` (= 8), i.e. the payload offset. Satisfies both
  the real caller (`>= 0`, `app_task.cpp:120`) and the mock (`> 0`, lines 133, 373, 404, 512)
  — a decoder returning 0-on-success would break the mock; a decoder returning anything
  but 8 would break both.
- **−1 on error**, and `*payload` is never written on failure:
  - **D1 — `hdr == NULL` MUST return −1 with no writes.** (Revision 1 was silent;
    `TOLLGATE_PROTO_API.md` §7.3 flagged it.) Passing `hdr == NULL` today is undefined
    behaviour, not a defined failure: the shipped `.c` (`:53` on the local lineage,
    `:42` on `origin/main`) calls
    `memcpy(hdr, ...)` unconditionally and segfaults. No pinned test and no consumer passes
    `hdr == NULL`. **Defect DEF-2 (§7.1).**
  - **D2 — `data == NULL`;**
  - **D3 — too short:** `len < 8` (this is the buffer-too-small case for decode;
    `len == 8 + payload_len` succeeds, `len == 7 + payload_len` fails — unit tests 6, 8);
  - **D4 — `hdr->version != 1`;**
  - **D5 — `hdr->type` outside 0x01..0x06;**
  - **D6 — truncated payload:** `hdr->payload_len > len − 8`.
- Post-failure state of `*hdr` (precise, callers must respect): for `data == NULL` or
  `len < 8`, `*hdr` is untouched (unit test 13 case 4 pins this with a canary). For the
  later checks (version/type/payload_len), the raw 8 header bytes have already been copied
  into `*hdr` before rejection — do **not** inspect `*hdr` after a −1 return.
- `payload` parameter may be `NULL` (caller not interested); on success it is set to
  `data + 8` — a pointer **into the input buffer**, never a copy (unit test 5 pins
  `payload == data + sizeof(hdr)`). Payload length is not returned separately; the caller
  reads `hdr->payload_len`.

## 6. `CONFIG_ENABLE_TOLLGATE` guard pattern

The header itself contains **no** ifdef guards and must stay includable unconditionally
(host tests include it bare, `test_relay_pipeline.c:83`). All guarding lives at the
consumers and build system:

1. **Kconfig** (`main/Kconfig.projbuild:141-147`): `config ENABLE_TOLLGATE`, bool,
   `default n`, `depends on ENABLE_RELAY_MODE`.
2. **CMake** (`main/CMakeLists.txt:29-31`): the source is compiled only when enabled:
   `if(CONFIG_ENABLE_TOLLGATE) list(APPEND APP_SRCS "tollgate_payment_proto.c") endif()`.
3. **app_task.cpp:32-33** — include guarded:
   `#ifdef CONFIG_ENABLE_TOLLGATE` / `#include "tollgate_payment_proto.h"`.
4. **app_task.cpp:114-145** — the entire `case RELAY_TYPE_TOLLGATE_PAY:` dispatch arm is
   wrapped in `#ifdef CONFIG_ENABLE_TOLLGATE ... #endif`. When disabled, PAY-tagged packets
   fall through to the `default:` "unknown packet type" arm (no ACK, no crash).
5. **sdkconfig:576** — on the **published lineage** (`origin/main`, the branch that carries
   this file) the tracked sdkconfig reads **`# CONFIG_ENABLE_TOLLGATE is not set`**
   (measured 2026-09-27: `git show origin/main:tracker/firmware/sdkconfig | sed -n '576p'`;
   it is the only `ENABLE_TOLLGATE` occurrence in the file). With Kconfig `default n`
   (item 1) and the CMake guard (item 2), **the feature is compiled out at that head**:
   `tollgate_payment_proto.c` is not in the build and the whole `case RELAY_TYPE_TOLLGATE_PAY:`
   arm (item 4) is preprocessed away, so PAY-tagged packets fall through to `default:`.
   Enabling the feature therefore requires a sdkconfig change (or porting commit `55d79702`,
   which exists only on the local lineage `autonomous/mesh-baseline`, where the same line
   reads `CONFIG_ENABLE_TOLLGATE=y`). A stale flag silently compiling the feature out is the
   exact failure mode this guard pattern can hide; verify the flag after any sdkconfig
   regeneration, and check **which lineage you are on** before trusting this line.

Any new consumer of the header must follow the same pattern: `#ifdef CONFIG_ENABLE_TOLLGATE`
around include and use, plus the CMake guard if a new .c file is added. The header must
remain self-contained (`<stdint.h>`, `<stddef.h>` only — no `relay_types.h`, no ESP-IDF,
no `tollgate_balloon.h`), because host unit tests compile it with plain gcc.

## 7. Constraints, known gaps, and filed defects

### 7.1 Filed defects — shipped implementation deviates from this contract

Both are **code** defects in `tracker/firmware/main/tollgate_payment_proto.c`. Neither is
fixed by this card (recon/documentation only); each must be fixed with a test that first
fails, and no existing consumer breaks when it is.

| ID | Clause | `.c` today | Required behaviour | Blast radius |
|---|---|---|---|---|
| **DEF-1** | §5 clause E4 | `payload_len > 0 && payload == NULL` → skips `memcpy`, still writes `hdr->payload_len = N`, returns `8 + N` (local `.c:39-43` = `origin/main` `.c:28-32`) | return −1, write nothing | none — no call site passes `NULL` with `payload_len > 0` |
| **DEF-2** | §5 clause D1 | `memcpy(hdr, data, 8)` with no NULL check (local `.c:53` = `origin/main` `.c:42`) → segfault | return −1, write nothing | none — no call site passes `NULL` |

Line numbers are given for **both** lineages: the local `autonomous/mesh-baseline` copy is 66
lines (hardening `38360fb1`), the published `origin/main` copy is 53 lines. A `.c` citation
without a lineage label is meaningless here — e.g. `origin/main` `.c:39` is the *decode*
guard `if (!data || len < 8) return -1;`, not the DEF-1 encode skip.

Both defects are detectable only by reading the implementation, which is why revision 1
listed the first one as a "wart" and missed the second entirely.

### 7.2 Documentation gaps

- **G1 — CLOSED for the mock-protocol recon; still open for the rest of the recon set.**
  `docs/recon/tollgate_proto_test_mock.md` is **tracked** on this branch by commit
  `b8aa95bf` ("docs(recon): track tollgate_proto_test_mock.md — the mock-protocol recon
  input was untracked"), 514 lines; §0.1's earlier claim that it was untracked was true only
  before that commit, which is the immediately preceding commit of the branch that carries
  this file. Still untracked (on both lineages): `tracker/firmware/docs/recon/raw_doc_scan.md`,
  `tracker/firmware/.tollgate-recon-index.md` and `docs/recon/.tollgate_framing_notes.md`.
  The recon index deliberately declares itself untracked; the others were blocked by a
  permission gate.
- **G2 — three of the four recon inputs exist only on the local lineage.** On `origin/main`
  only `docs/recon/tollgate_proto_test_mock.md` is present; the app-task call-site recon
  (`c45dec77`), the framing/config recon (`b7db8b31`), the sibling spec
  `tracker/firmware/TOLLGATE_PROTO_API.md` (`2ab5058e`) and the upstream audit
  (`a9b9126f`) are absent (measured 2026-09-27 with `git ls-tree -r origin/main --name-only
  | grep -iE "recon|PROTO_API|payack"`; none of those commits is an ancestor of
  `origin/main`). This file is therefore written to stand alone (§0.1) — porting those docs
  onto the published branch would let a fresh clone read the primary evidence instead of
  taking this document's word for it.

### 7.3 Constraints that are not defects

- **Token/PAY size mismatch:** `TOLLGATE_MAX_TOKEN_LEN` (2048) is inherited from the upstream
  UDP framing where a datagram can carry it. On the relay pipeline a framed message is
  capped at 511 bytes (payload ≤ 503), so a full-size Cashu token cannot cross the mesh in
  one relay packet. Current call sites never send a real token (PAY is built header-only in
  tests; app_task only ever *receives* PAY and *sends* ACK). Real token transport needs a
  future decision (chunking, compression, or cap) — out of scope here, but the contract
  must not pretend it fits.
- **Upstream divergence on payload kind:** the upstream header documents JSON payloads
  (ADR-002 open question 2 chose "JSON initially") and names the parameter `json_payload`.
  The tracker copy renamed it to `payload` and sends the **packed binary**
  `tollgate_ack_payload_t` — wire-incompatible with an upstream JSON ACK. The two copies are
  header/struct-compatible but payload-interpretation is per-deployment.
- **Decode success check differs by caller** (`>= 0` in app_task.cpp vs `> 0` in the mock).
  The return contract in §5 (8 on success, −1 on error) satisfies both; never return 0.
- **`seq` narrowing:** call sites hold `uint32_t` seq values and cast to `uint16_t` at the
  encode boundary (mock lines 209, 387). Values ≥ 65536 alias; callers must keep seq
  counters under 65536 or accept wrap semantics (dedup is the seq's purpose).

## 8. Provenance

### Inherited from upstream (mesh-stack `tollgate_balloon` component / ADR-002)

| Item | Upstream source |
|---|---|
| 8-byte packed header, fields and offsets (version/type/seq/payload_len/reserved) | `tollgate_balloon.h:40-46` |
| `tollgate_msg_type_t` values 0x01–0x06 with directions | `tollgate_balloon.h:31-38` |
| `TOLLGATE_PROTO_VERSION = 1` | `tollgate_balloon.h:48` |
| `TOLLGATE_MAX_TOKEN_LEN = 2048` | `tollgate_balloon.h:28` |
| `tollgate_ack_payload_t` (14-byte packed layout) | upstream `tollgate_payment_proto.h:29-34` |
| `tollgate_nack_payload_t`, `TG_ERR_*` codes −1..−5 | upstream `tollgate_payment_proto.h:37-47` |
| `tollgate_pay_payload_t` (`char token[2048]`) | upstream `tollgate_payment_proto.h:24-26` |
| encode/decode function shapes, "total bytes written" / "payload offset" returns | upstream `tollgate_payment_proto.h:60-75` |
| `[hdr(8)][payload]` wire format, UDP port 2121 framing | ADR-002 |

### Tracker-local inventions / deltas (with reasons)

| Invention | Reason |
|---|---|
| Self-contained header: enum + hdr + version + token-len inlined; `#include "tollgate_balloon.h"` removed | Upstream include drags in `tollgate_core`/`esp_err_t`; the tracker copy must compile with host gcc for unit tests and must not depend on the tollgate component |
| Parameter renamed `json_payload` → `payload` | `app_task.cpp:135` passes a packed binary struct (`(const char *)&ack_payload`), not JSON — the tracker use is payload-kind-agnostic (see §7 divergence note) |
| `tg_type_is_valid()` bounds check (1..6) in **encode** and **decode** | Upstream validated neither; hardening demanded by unit tests 11/12 (commit 38360fb1) — a bogus type byte must not enter or leave the device |
| No-write-on-failure guarantee pinned for encode; hdr-untouched pinned for truncated decode | Canary tests 12/13 (commit 38360fb1) — encode rejections must not partially scribble a radio buffer |
| `RELAY_TYPE_*` 1-byte tag prefix framing | Tracker relay pipeline (relay_types.h / radio↔app queues) — upstream framing was a bare UDP datagram on port 2121 with no tag byte. This is the transport delta of ADR-002 → tracker pipeline |
| Guard pattern: include + dispatch arm + CMake all behind `CONFIG_ENABLE_TOLLGATE`, header itself unguarded | Kconfig feature-gating (default n) while keeping host tests compilable |
| **Not ported:** `tollgate_proto_build_info_json()` | No tracker call site builds INFO JSON; keeping it out avoids a malloc'd-string API on device |

## 9. Conformance checklist — every call site and mock usage

**app_task.cpp** (all under `#ifdef CONFIG_ENABLE_TOLLGATE`):

- [x] L32-33 include inside the ifdef — header self-contained (§6)
- [x] L90 outer dispatch reads tag from byte 0 only when `pkt.len > 0` — empty packets fall to RAW/default, never reach decode
- [x] L117 `tollgate_msg_hdr_t hdr;` on stack — struct is 8 packed bytes (§2)
- [x] L120 `tollgate_proto_decode(pkt.data + 1, pkt.len - 1, &hdr, &payload) >= 0` — tag stripped; success = 8 ≥ 0 (§5)
- [x] L121/140 `hdr.seq` used for log + echo — seq round-trips (§2)
- [x] L126 ACK tag byte written at `data[0]` — outside the message (§1)
- [x] L128-129 `tollgate_ack_payload_t` memset to 0 — 14 packed bytes (§3)
- [x] L130 `ack_payload.price_sats = 0` — uint16_t field (§3)
- [x] L132-136 `encode(ack_pkt.data + 1, RELAY_PACKET_MAX_SIZE - 1, TG_MSG_ACK, hdr.seq, (const char *)&ack_payload, sizeof(ack_payload))` — arg types match prototype; 8+14=22 ≤ 511 (§5)
- [x] L137 `ack_len > 0` — success return 22 > 0 (§5)
- [x] L138 `ack_pkt.len = ack_len + 1` = 23 ≤ 512 (§1)

**test_relay_pipeline.c** (mock + helpers):

- [x] L83 bare `#include "tollgate_payment_proto.h"` — must compile with host gcc, no Kconfig (§6)
- [x] L104 mock drops `pkt->len == 0` before dispatch — decode never sees len 0 as PAY path
- [x] L129-154 PAY→ACK arm mirrors app_task, decode checked `> 0` — success = 8 > 0 (§5)
- [x] L137/141 tag byte + `ack.price_sats = 0` (§3)
- [x] L143-147 encode with `(const char *)&ack, (uint16_t)sizeof(ack)` — binary ACK payload, cast chain matches prototype (§5)
- [x] L148/149 `ack_len > 0`, `ack_pkt.len = ack_len + 1` (§5)
- [x] L201-215 `build_tollgate_pay_packet`: encode with `NULL, 0` payload — NULL allowed when len == 0 (§5); `assert(enc_len > 0)` ⇒ header-only encode returns 8 (§5); `(uint16_t)seq` narrowing (§7); `pkt->len = enc_len + 1`
- [x] L371-375 ACK frame decode: tag byte checked, `h.type == TG_MSG_ACK`, `h.seq == 42` round-trip (§2, §4)
- [x] L402-406 seq 100–104 round-trip through encode/decode
- [x] L503-515 mixed traffic: exactly 4 ACKs, tag byte on each, decode `> 0`, `TG_MSG_ACK`, seq window 200–203 preserved
- [x] L622-626 TEST 12 pins relay tag constants 0x01/0x02/0x03/0x04/0xFF (§4)

**test_tollgate_payment_proto.c** (wire-level pins — tests 1–10 exist and pass on **both**
lineages; tests 11–14 exist **only on the local lineage** `autonomous/mesh-baseline`):

- [x] Test 1: `sizeof(hdr) == 8`, field offsets 0/1/2/4/6 (§2)
- [x] Test 2/3: encode returns `8 + payload_len`; header-only returns 8; `reserved` written 0 (§2, §5)
- [x] Test 4: overflow → −1; exact fit (29) succeeds; one-byte-short → −1; NULL buf → −1 (§5)
- [x] Test 5: hand vector `01 05 64 00 05 00 00 00 "hello"` decodes; payload pointer == data+8; NULL payload-out param allowed; LE seq bytes `64 00` (§2, §5)
- [x] Test 6: len < 8, len == 0, NULL data → −1 (§5)
- [x] Test 7: version 0/2/0xFF → −1 (§2)
- [x] Test 8: `payload_len` > available → −1; exact fit succeeds; total one-byte-short → −1 (§5)
- [x] Test 9: round-trip PAY/ACK/NACK/INFO with payload equality
- [x] Test 10: `sizeof(tollgate_ack_payload_t) == 14`; ACK struct round-trips through encode/decode (§3)
- [x] Test 11 *(local lineage only)*: decode rejects type 0x00/0x07/0xFF, accepts boundary 0x01/0x06 (§4)
- [x] Test 12 *(local lineage only)*: encode rejects type 0/99/0xFF **without touching the buffer** (§5)
- [x] Test 13 *(local lineage only)*: canary — short encode writes nothing; exact fit leaves trailing bytes untouched; hdr-only fit; truncated decode leaves hdr + canary intact (§5)
- [x] Test 14 *(local lineage only)*: seq ∈ {0,1,0xFFFF} and price_sats ∈ {0,1,0xFFFF} round-trip; all-max ACK fields round-trip (§2, §3)

**Verification record — local lineage** (`autonomous/mesh-baseline`, `~/repos/balloon`,
2026-09-14, re-run 2026-09-27):

```
gcc -Wall -O2 -I main -o /tmp/test_tgproto main/test/test_tollgate_payment_proto.c \
    main/tollgate_payment_proto.c          && /tmp/test_tgproto
  → === Results: 133 passed, 0 failed ===   (exit 0)   # 14 test functions

gcc -Wall -O2 -I main -I components/nostr_store/include -o /tmp/test_relay \
    main/test/test_relay_pipeline.c main/tollgate_payment_proto.c \
    components/nostr_store/nostr_store.c   && /tmp/test_relay
  → === Results: 12/12 passed ===           (exit 0)
```

**Re-verification record — published branch** (`origin/main`, head
`68c27cdda74f0f87b57029be42dd118b633f9c24`, in the `~/worktrees/tollgate-contract-recon`
worktree, 2026-09-27, card `balloon:t_c360db44`): the *same* commands run against the tree
that actually carries this file yield **different, smaller** totals, because hardening
`38360fb1` and tests 11–14 are not on this lineage:

```
cd tracker/firmware
gcc -Wall -O2 -I main -o /tmp/test_tgproto_om main/test/test_tollgate_payment_proto.c \
    main/tollgate_payment_proto.c          && /tmp/test_tgproto_om
  → === Results: 83 passed, 0 failed ===    (exit 0)   # 10 test functions, 334-line file
gcc -Wall -O2 -I main -I components/nostr_store/include -o /tmp/test_relay_om \
    main/test/test_relay_pipeline.c main/tollgate_payment_proto.c \
    components/nostr_store/nostr_store.c   && /tmp/test_relay_om
  → === Results: 12/12 passed ===           (exit 0)
```

So: **133/133 is the local-lineage figure and 83/83 is the published-branch figure** — the
earlier revision of this section printed only the local number under a §9 heading that
applies to both, which is not reproducible on the branch the file ships on. Tests 1–10 and
`test_relay_pipeline`'s 12 tests run green on both lineages.

No warning on either build leg (`-Wall`). The two tests exercised the **real**
`tollgate_payment_proto.c`; the mock protocol that revision 1 of the card body referenced at
`test_relay_pipeline.c:75` was already removed by the time the header landed (mock lines
75–83 now state that the header exists and all tests exercise the real implementation).

Every clause above was additionally re-confirmed line-by-line against `app_task.cpp:85-145`
and `test_relay_pipeline.c:200-215` on 2026-09-27; all cited line numbers hold — those two
files are byte-identical on both lineages (`git diff --stat origin/main --
tracker/firmware/main/app_task.cpp tracker/firmware/main/relay_types.h` is empty), so their
citations need no lineage qualifier. The `.c` citations in §5/§7.1 do, and now carry one.

---

*End of contract. Revisions 2 and 3 are documentation-only: no implementation file was changed
in producing them. Revision 3 corrects lineage accuracy only (F1–F6, §0.5) — no normative
value, offset, prototype or error code moved between revisions 2 and 3. The two code defects
it records (§7.1 DEF-1/DEF-2) are filed, not fixed, and must be fixed in their own card with
a failing test first.*