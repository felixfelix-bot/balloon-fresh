# TOLLGATE_PROTO_CONTRACT.md — Authoritative wire contract for `tollgate_payment_proto.h`

**Status:** AUTHORITATIVE for branch `autonomous/mesh-baseline`
**Scope:** `tracker/firmware/main/tollgate_payment_proto.h` / `.c` — the TollGate
PAY/ACK message format as it crosses the tracker relay pipeline.
**Date:** 2026-09-27
**Supersedes:** the inline "Wire format (ADR-002)" comments in
`tracker/firmware/main/tollgate_payment_proto.h:8-19` and
`tracker/firmware/main/tollgate_payment_proto.c:4-8`, and the `RELAY_TYPE_*` /
`TG_MSG_*` prose scattered across `relay_types.h`, `app_task.cpp`, `app_main.cpp`.
**Nature of this document:** specification only. It changes no code. Nothing here
implements the header; where the current implementation disagrees with this
contract the disagreement is listed in §9 as a numbered DEVIATION, not silently
patched.

---

## 0. Inputs, and one gap

The task specified four recon notes as inputs. **All four are missing.** I verified
this directly rather than assuming:

| Expected input | Status |
|---|---|
| `docs/recon/tollgate_proto_spec_search.md` | **ABSENT** |
| `docs/recon/tollgate_proto_app_task_callsites.md` | **ABSENT** |
| `docs/recon/tollgate_proto_test_mock.md` | **ABSENT** |
| `docs/recon/tollgate_proto_framing_config.md` | **ABSENT** |

Evidence of absence:
* `docs/recon/` does not exist in this worktree (`ls -d docs/recon` → *No such file
  or directory*), and `tracker/firmware/docs/` does not exist either.
* A scan of **every** branch that exists in this repository
  (`git ls-tree -r --name-only <branch> | grep -c 'docs/recon/tollgate_proto'`)
  returns zero hits on all of them.

**Consequence:** no synthesis of recon prose was possible, and none was invented.
Instead this contract is derived from the primary sources the recon notes were meant
to summarise — the upstream spec itself, the real call sites, and the real tests,
read in full and executed. Every claim below carries a `file:line` citation, and
§10 records the exact commands and their output. This substitution is strictly
stronger evidence than a summary of those sources would have been, but it means the
"recon notes agree on X" cross-check that the task assumed is not available; if the
four notes are later recovered they should be diffed against §1–§7.

Primary sources actually used:

| Role | Path |
|---|---|
| Upstream spec (message types, header) | `mesh-stack/tollgate/components/tollgate_balloon/include/tollgate_balloon.h` |
| Upstream spec (payload structs, prototypes) | `mesh-stack/tollgate/components/tollgate_balloon/include/tollgate_payment_proto.h` |
| Upstream reference implementation | `mesh-stack/tollgate/components/tollgate_balloon/src/tollgate_payment_proto.c` |
| Upstream 1-byte framing analogue | `mesh-stack/tollgate/components/mesh_service_mux/include/mesh_service_mux.h` |
| Decision record | `docs/adr/002-tollgate-over-fips-mesh-udp.md` |
| Tracker header / impl | `tracker/firmware/main/tollgate_payment_proto.h` / `.c` |
| Relay framing | `tracker/firmware/main/relay_types.h` |
| Call sites | `tracker/firmware/main/app_task.cpp`, `tracker/firmware/main/app_main.cpp` |
| Host tests | `tracker/firmware/main/test/test_relay_pipeline.c`, `.../test_tollgate_payment_proto.c` |
| Hardware harness | `tracker/firmware/test/integration/test_tollgate_payack.py` |
| Build/config | `tracker/firmware/main/Kconfig.projbuild`, `tracker/firmware/main/CMakeLists.txt`, `.github/workflows/ci-host-tests.yml` |

---

## 1. Wire format of a TollGate message in the relay pipeline

```
 relay_packet_t.data:
 ┌─────────┬──────────────────────────────┬────────────────────────────┐
 │ byte 0  │ bytes 1..8                   │ bytes 9 .. 8+N             │
 │ RELAY   │ tollgate_msg_hdr_t (8 bytes, │ payload (N = payload_len   │
 │ TYPE    │ packed, little-endian)       │ bytes; N may be 0)         │
 │ tag     │                              │                            │
 └─────────┴──────────────────────────────┴────────────────────────────┘
   pkt.len = 1 + 8 + N                  N ≤ 503 on this transport
```

Rules:

1. **The 1-byte relay type tag is byte 0 of the relay frame, and it is not part of
   the TollGate message.** The TollGate message begins at `data + 1` and is exactly
   `8 + payload_len` bytes long. This is the "first-byte relay framing rule"
   (`main/relay_types.h:10`; `main/app_task.cpp:90` reads `pkt.data[0]`;
   `main/app_task.cpp:120` and `main/test/test_relay_pipeline.c:133` both call the
   decoder on `data + 1` with `len - 1`).
2. **The tag is chosen by direction, not by the inner message type** (see §4).
3. `pkt.len` MUST include the tag byte: producers set `pkt.len = enc_len + 1`
   (`app_main.cpp:634`, `app_task.cpp:138`, `test_relay_pipeline.c:149`).
4. Capacity: `RELAY_PACKET_MAX_SIZE` is 512 (`relay_types.h:6`). The encode target
   inside a frame is therefore `frame + 1` with capacity `512 - 1 = 511`, so the
   largest TollGate payload on this transport is `512 - 1 - 8 = 503` bytes. The
   `app_main.cpp:612` guard and this constant must stay equal; see §9 DEVIATION-3.

---

## 2. `tollgate_msg_hdr_t` — chosen layout

8 bytes, `__attribute__((packed))`, **little-endian**, byte order fixed by this
contract regardless of host (see DEVIATION-5).

| Off | Field | Type | Bytes | Endian | Value / range |
|---|---|---|---|---|---|
| 0 | `version` | `uint8_t` | 1 | n/a | `TOLLGATE_PROTO_VERSION` = 1 |
| 1 | `type` | `uint8_t` | 1 | n/a | `tollgate_msg_type_t` (0x01–0x06) |
| 2 | `seq` | `uint16_t` | 2 | LE | opaque u16 echo token, wraps mod 2^16 |
| 4 | `payload_len` | `uint16_t` | 2 | LE | bytes following the header, 0–503 |
| 6 | `reserved` | `uint16_t` | 2 | LE | MUST be written 0, MUST be ignored on read |

Per-field justification, by the call site or mock that forces it:

* **`version` @0, 1 byte** — load-bearing in `decode`: `hdr->version !=
  TOLLGATE_PROTO_VERSION → -1` (`tollgate_payment_proto.c:45-46`). The unit test
  pins the gate from both sides: version 0, 2 and 255 must all be rejected
  (`test_tollgate_payment_proto.c:194-212`), and the valid path asserts
  `hdr.version == TOLLGATE_PROTO_VERSION` (`:91`, `:109`, `:276-277`). It must be
  byte 0 of the *message* (i.e. byte 1 of the frame) because a receiver needs to
  reject a foreign protocol before trusting `type`/`payload_len`; a hand-crafted
  byte sequence in the unit test fixes it there (`:142-149`, first byte `0x01`).
* **`type` @1, 1 byte** — pinned by `ack_hdr.type == TG_MSG_ACK` in three separate
  pipeline tests (`test_relay_pipeline.c:374`, `:405`, `:513`) and by the
  `check_hdr_fields` calls in the unit test. Must be exactly 1 byte and sit after
  `version`, because the hand-crafted vector places the INFO type `0x05` at byte 1
  (`test_tollgate_payment_proto.c:143`). All six enum values fit in 1 byte.
* **`seq` @2, `uint16_t` LE** — the only header field the tracker firmware logic
  consumes: `app_task.cpp:121,134,140` reads `hdr.seq` and echoes it into the ACK
  (`tollgate_proto_encode(..., TG_MSG_ACK, hdr.seq, ...)`). Tests assert the echo
  survives encode→decode: `ack_hdr.seq == 42` (`test_relay_pipeline.c:375`),
  `h.seq == seq` for seq 100..104 (`:406`), `h.seq >= 200 && < 204` (`:514`), and
  `hdr.seq == 1234/5678/9012/3456` in the round-trip table
  (`test_tollgate_payment_proto.c:256-259`). 16 bits is sufficient (and is what the
  upstream spec uses); the LE byte order is pinned by the hand-crafted vector
  encoding seq=100 as `0x64, 0x00` (`:145`). The hardware harness compares the
  echoed `seq` for equality (`test_tollgate_payack.py:305-313`), which is the
  observable end-to-end consumer of this field.
* **`payload_len` @4, `uint16_t` LE** — the framed-length contract. `decode`
  rejects `payload_len > len - 8` (`tollgate_payment_proto.c:47-48`), so it is what
  makes a truncated frame detectable: `payload_len = 100` with 50 bytes available
  must fail, `payload_len = 50` with exactly 50 available must succeed, and one byte
  short must fail (`test_tollgate_payment_proto.c:219-244`). Encode writes it
  verbatim and the unit test reads it back (`:91`, `:109`). 16 bits is required
  because the protocol's own token cap is 2048 (`TOLLGATE_MAX_TOKEN_LEN`) — a
  `uint8_t` could not express it. LE pinned at `:146` (`0x05, 0x00` for 5).
* **`reserved` @6, `uint16_t`** — the field that makes the header exactly 8 bytes.
  That size is load-bearing arithmetic at three sites: `app_main.cpp:612` computes
  the max payload as `RELAY_PACKET_MAX_SIZE - 1 - sizeof(tollgate_msg_hdr_t)`;
  `app_task.cpp:132` and `test_relay_pipeline.c:143` pass
  `RELAY_PACKET_MAX_SIZE - 1` as the buffer capacity for a message placed at
  `data + 1`. The unit test asserts the size and the offset directly
  (`test_tollgate_payment_proto.c:65`, `:73` — offset 6). Encode zeroes it
  (`tollgate_payment_proto.c:26`) and the tests require 0 (`:91`, `:109`, `:277`).
  **Decode does not validate it** — see DEVIATION-4.

Header size = **8 bytes**, verified by execution on this branch (§10).

---

## 3. `tollgate_ack_payload_t` — chosen layout

14 bytes, `__attribute__((packed))`, little-endian, no padding. It is transmitted
**as a raw struct image**, i.e. the C struct layout *is* the wire format.

| Off | Field | Type | Bytes | Endian | Meaning |
|---|---|---|---|---|---|
| 0 | `session_id` | `uint32_t` | 4 | LE | 0 = no session established (v1: always 0) |
| 4 | `expires_unix` | `uint32_t` | 4 | LE | session expiry, unix seconds (v1: always 0) |
| 8 | `quota_bytes` | `uint32_t` | 4 | LE | data quota, 0 = unlimited / time-based (v1: 0) |
| 12 | `price_sats` | `uint16_t` | 2 | LE | price charged, sats (v1: 0, `TODO: real price`) |

Field-by-field justification:

* **Total 14 bytes / no padding** — pinned by execution:
  `sizeof(tollgate_ack_payload_t) == 14` is asserted in
  `test_tollgate_payment_proto.c:289`. Because `app_task.cpp:136` and
  `test_relay_pipeline.c:147` pass `sizeof(ack_payload)` as `payload_len`, any
  padding byte would be transmitted as payload — hence `packed` is mandatory, not
  stylistic.
* **`session_id`, `expires_unix`, `quota_bytes`, `price_sats`** — these four exist
  because the ACK is the *only* carrier of session information in the protocol, and
  the whole payment flow terminates in them:
  * `app_task.cpp:128-130` constructs the struct, zeroes it, and sets
    `price_sats = 0` with `TODO: real price from config` — so `price_sats` is the
    only field any tracker call site touches today, and it is a **zero sentinel**,
    not a computed price.
  * `test_tollgate_payment_proto.c:292-313` round-trips the struct through
    encode/decode and reinterprets the payload pointer as
    `const tollgate_ack_payload_t *` to assert `session_id` and `price_sats`
    survive — this is the mock that forbids changing the layout.
  * The hardware harness reads exactly these three concepts out of the ACK log
    (`test_tollgate_payack.py:106-109`, `:180-192`: `SESSION_ID_PATTERN`,
    `PRICE_PATTERN`, `EXPIRES_PATTERN`), and fails the round if it cannot
    (`:458`). So `session_id` / `expires` / `price` are required to be *observable*
    even though v1 transmits them as 0.
  * `quota_bytes` is the only field with **no call-site justification at all** —
    see the honest note in §8 (PROVENANCE-INVENTED-6).
* **Field types are pinned by upstream, not by usage** — `uint32/uint32/uint32/
  uint16` is byte-for-byte identical to the upstream struct
  (`mesh-stack/.../tollgate_payment_proto.h:28-34`). No tracker call site requires
  32-bit widths; the widths are kept for wire parity. Changing them changes the wire.

`tollgate_pay_payload_t` (2048-byte `char token[]`, `tollgate_payment_proto.h:58-60`)
and `tollgate_nack_payload_t` (130 bytes, `:71-74`) are declared for parity but have
**no producer in this firmware**; see §8 and the checklist in §7.

---

## 4. `TG_MSG_PAY` / `TG_MSG_ACK` values and the two tag namespaces

### 4.1 Values (fixed, do not change)

```c
TG_MSG_PAY  = 0x01   /* client → balloon: payment */
TG_MSG_ACK  = 0x02   /* balloon → client: accepted + session info */
TG_MSG_NACK = 0x03
TG_MSG_STATUS = 0x04
TG_MSG_INFO   = 0x05
TG_MSG_REVOKE = 0x06
```

These are **not invented here** — they are copied verbatim from the upstream enum
(`mesh-stack/tollgate/components/tollgate_balloon/include/tollgate_balloon.h:31-38`),
and independently mirrored by the Python hardware harness
(`test_tollgate_payack.py:101-103`). They are also compiled into the tracker header
(`tollgate_payment_proto.h:39-46`).

### 4.2 Relationship to the relay tags

```c
RELAY_TYPE_NOSTR_EVENT  = 0x01   /* relay_types.h:11 */
RELAY_TYPE_TOLLGATE_PAY = 0x02   /* relay_types.h:12 */
RELAY_TYPE_TOLLGATE_ACK = 0x03   /* relay_types.h:13 */
RELAY_TYPE_TELEMETRY    = 0x04   /* relay_types.h:14 */
RELAY_TYPE_RAW          = 0xFF   /* relay_types.h:15 */
```

**The two namespaces live at different byte offsets and are never interchangeable.**

| Namespace | Byte offset | Meaning |
|---|---|---|
| `RELAY_TYPE_*` | frame offset **0** (`data[0]`) | which service the frame belongs to, and its direction |
| `TG_MSG_*` | message offset **1** (`data[2]` in the frame) | the inner TollGate message type |

The canonical two packets of the payment flow:

| Direction | `data[0]` | `data[2]` (`hdr.type`) | Shape |
|---|---|---|---|
| client → balloon (PAY) | `0x02` `RELAY_TYPE_TOLLGATE_PAY` | `0x01` `TG_MSG_PAY` | tag ≠ type |
| balloon → client (ACK) | `0x03` `RELAY_TYPE_TOLLGATE_ACK` | `0x02` `TG_MSG_ACK` | tag ≠ type |

### 4.3 The overlap is coincidental and is the number-one confusion hazard

`0x01`, `0x02`, `0x03`, `0x04` each mean two unrelated things in this protocol:

| Value | As a relay tag | As a message type |
|---|---|---|
| `0x01` | `RELAY_TYPE_NOSTR_EVENT` | `TG_MSG_PAY` |
| `0x02` | `RELAY_TYPE_TOLLGATE_PAY` | `TG_MSG_ACK` |
| `0x03` | `RELAY_TYPE_TOLLGATE_ACK` | `TG_MSG_NACK` |
| `0x04` | `RELAY_TYPE_TELEMETRY` | `TG_MSG_STATUS` |

Binding rules (normative):

1. Never compare `pkt.data[0]` against a `TG_MSG_*` constant.
2. Never compare `hdr.type` against a `RELAY_TYPE_*` constant.
3. Never derive one namespace's value from the other. In particular
   `RELAY_TYPE_TOLLGATE_PAY == 0x02 == TG_MSG_ACK` is a collision, **not** an
   identity: the PAY frame carries inner type `0x01`.
4. A receiver MAY sanity-check the frame: for a TollGate frame,
   `data[1] == TOLLGATE_PROTO_VERSION (0x01)`. This is what makes the two
   namespaces independently detectable despite the numeric overlap.
5. The tags are direction-bound: `RELAY_TYPE_TOLLGATE_PAY` marks client→balloon,
   `RELAY_TYPE_TOLLGATE_ACK` marks balloon→client, regardless of which inner
   message type is inside.
6. Current firmware **dispatches only on `RELAY_TYPE_TOLLGATE_PAY`**
   (`app_task.cpp:115`). A received `RELAY_TYPE_TOLLGATE_ACK` frame falls through to
   the `default:` branch and is logged as an unknown packet type
   (`app_task.cpp:151-154`) — the payer side does not parse returning ACKs.

### 4.4 Provenance note on the framing rule

Upstream uses a 1-byte prefix too, but a different one: a *service mux* tag
(`MESH_SVC_TOLLGATE = 0x01`, `MESH_SVC_NOSTR = 0x02`, `MESH_SVC_BLOSSOM = 0x03`;
`mesh_service_mux.h:38-40`). The tracker's `RELAY_TYPE_*` table is a local
re-invention of that shape with local values — so the tag values are **not**
interoperable with upstream mesh frames. See §8 (PROVENANCE-INVENTED-2).

---

## 5. `tollgate_proto_encode()` / `tollgate_proto_decode()`

### 5.1 Exact prototypes

```c
int tollgate_proto_encode(uint8_t *buf, uint16_t buf_len,
                          tollgate_msg_type_t type, uint16_t seq,
                          const char *payload, uint16_t payload_len);

int tollgate_proto_decode(const uint8_t *data, uint16_t len,
                          tollgate_msg_hdr_t *hdr,
                          const uint8_t **payload);
```

`tollgate_payment_proto.h:94-96` and `:107-109`. Note `buf`/`buf_len` are
`uint16_t`/`uint8_t *` (host-portable, no `size_t`), and both functions are
declared inside `extern "C"` (`:28-30`) because `app_task.cpp` / `app_main.cpp` are
C++ translation units (`app_task.cpp:33`, `app_main.cpp:79`).

### 5.2 `tollgate_proto_encode()` — return-value semantics

| Condition | Return |
|---|---|
| success | **total bytes written = `8 + payload_len`** (header then payload) |
| `buf == NULL` | `-1` |
| `buf_len < 8 + payload_len` | `-1` |
| `payload_len == 0` | `8` (header only, payload pointer unused) |

Normative details:

1. **Return is a total length, not an offset.** Callers turn it into the frame
   length with `+ 1` for the tag: `pkt.len = enc_len + 1`
   (`app_main.cpp:634`, `app_task.cpp:138`, `test_relay_pipeline.c:149`, `:212`).
2. **Buffer-too-small is all-or-nothing.** The capacity check happens *before* any
   byte is written (`tollgate_payment_proto.c:18-19`), so a rejected call writes
   nothing and leaves `buf` untouched — there is no partial message to mis-frame.
   This must stay true: a caller that sees `-1` is entitled to retry with a larger
   buffer or drop the packet, and must never have to truncate.
3. **Exact fit must succeed.** `buf_len == 8 + payload_len` returns success, not
   `-1` — asserted at `test_tollgate_payment_proto.c:124-126` (29 bytes into a
   29-byte buffer). One byte less must fail (`:129-130`).
4. **Strict inequality is `buf_len < 8 + payload_len`.** Written with integer
   promotion of both `uint16_t` operands, so a pathological `payload_len` near
   65535 cannot wrap the comparison into a false success.
5. `payload == NULL && payload_len > 0` is **invalid and MUST return `-1`** — the
   current implementation returns a success length while silently skipping the
   copy, which is DEVIATION-1.
6. `version` is always written from `TOLLGATE_PROTO_VERSION` and `reserved` always
   as 0; callers cannot override either.

### 5.3 `tollgate_proto_decode()` — return-value semantics

| Condition | Return |
|---|---|
| success | **`sizeof(tollgate_msg_hdr_t)` = 8** — the payload *offset* |
| `data == NULL` | `-1` |
| `len < 8` | `-1` |
| `hdr->version != TOLLGATE_PROTO_VERSION` | `-1` |
| `hdr->payload_len > len - 8` | `-1` |
| extra bytes beyond `8 + payload_len` | **tolerated** (still succeeds) |

Normative details:

1. **The return value is an offset, not a length.** It is always `8` on success. It
   must never be used as the payload length or the consumed length — the payload
   length is `hdr->payload_len`, read from the header. Every call site is
   consistent with this (`app_task.cpp:120`, `test_relay_pipeline.c:133`, `:373`,
   `:404`, `:512`). Because success is always `8`, both `ret >= 0`
   (`app_task.cpp:120`) and `ret > 0` (`test_relay_pipeline.c:133`) are
   behaviourally identical; `ret > 0` is the recommended form.
2. **Validity = `len >= 8` AND `version == 1` AND `payload_len <= len - 8`.** The
   `len >= 8` test precedes the subtraction, so no unsigned underflow is possible
   (`tollgate_payment_proto.c:39-48`).
3. **Trailing slack is tolerated.** Only an *over-claimed* `payload_len` is
   rejected; a frame longer than `8 + payload_len` decodes fine and the surplus is
   ignored. This is required so that padded/oversized radio frames are not dropped
   mid-flight, and it is the reason the check is `>` rather than `!=`.
4. **`hdr` is a required, non-NULL out-parameter**; `decode` copies 8 bytes into it
   unconditionally. The current implementation does not guard `hdr == NULL`
   (DEVIATION-2).
5. **`payload` is an optional out-parameter.** When non-NULL it is always set to
   `data + 8` on success, *including* when `payload_len == 0`. When NULL, decode
   still succeeds — asserted at `test_tollgate_payment_proto.c:164-167`.
6. The pointed-to payload aliases the caller's buffer (zero-copy, no allocation);
   it is valid only for the lifetime of `data`.
7. Decode does not validate `type` against the enum (an unknown type byte still
   decodes) or `reserved`. Both are deliberate: `type` is checked by the caller,
   `reserved` is reserved.

### 5.4 Buffer-too-small, restated for the encode side

The precise requirement, because three call sites depend on it:

* `buf_len == 8 + payload_len` → **success**, returns `8 + payload_len`.
* `buf_len == 7 + payload_len` → `-1`, nothing written.
* `buf == NULL` → `-1`, even if `buf_len` is large.
* The capacity constant actually used by the firmware is `RELAY_PACKET_MAX_SIZE - 1`
  = 511 (`app_task.cpp:133`, `test_relay_pipeline.c:144`, `app_main.cpp:626`), giving
  the 503-byte payload ceiling of §1.

---

## 6. The `CONFIG_ENABLE_TOLLGATE` guard pattern

### 6.1 The Kconfig symbol

```
config ENABLE_TOLLGATE
    bool "Enable TollGate payment processing (Cashu e-cash over mesh)"
    default n
    depends on ENABLE_RELAY_MODE
```
(`main/Kconfig.projbuild:141-148`)

### 6.2 Required pattern

**The header itself must NOT be wrapped in the Kconfig guard.** It must remain a
dependency-free, host-compilable declaration file containing only:

1. the `#ifndef TOLLGATE_PAYMENT_PROTO_H` include guard,
2. `<stdint.h>` / `<stddef.h>` only,
3. `extern "C"` linkage guards.

Only three places may reference `CONFIG_ENABLE_TOLLGATE`, and they must agree:

| Site | Pattern | Reference |
|---|---|---|
| **Include** in a consumer | `#ifdef CONFIG_ENABLE_TOLLGATE` … `#include "tollgate_payment_proto.h"` … `#endif` | `app_task.cpp:32-34`, `app_main.cpp:79` |
| **Call sites** in a consumer | the *same* `#ifdef` must enclose the decode/encode logic, not just the include | `app_task.cpp:114-145`, `app_main.cpp:575-649`, `:670-673` |
| **Source registration** | `if(CONFIG_ENABLE_TOLLGATE) list(APPEND APP_SRCS "tollgate_payment_proto.c") endif()` | `main/CMakeLists.txt` |

Use `#ifdef`, never `#if`: ESP-IDF only defines `CONFIG_ENABLE_TOLLGATE` when the
symbol is `y`; when it is `n` the macro is absent entirely.

**Why the header must stay unguarded (this is the non-obvious part):** the host
tests include the header and link the implementation *without any sdkconfig at all*
(`.github/workflows/ci-host-tests.yml:41-46` compiles
`main/test/test_relay_pipeline.c` + `main/tollgate_payment_proto.c` with plain
`gcc -Wall -O2`, no `-DCONFIG_ENABLE_TOLLGATE`). Wrapping the header's contents in
`#ifdef CONFIG_ENABLE_TOLLGATE` would make `relay_types`/`TG_MSG_*`/the payload
structs vanish for those two suites and break both CI jobs. The guard belongs to
*consumers of the header on-target*, not to the header.

### 6.3 The failure mode this pattern exists to prevent (observed, not theoretical)

When the symbol is off, every guarded block disappears and the feature compiles
out **silently** — no warning, no link error. That actually happened on this
branch: `sdkconfig.defaults.esp32s3` had `CONFIG_ENABLE_TOLLGATE=y` while the
tracked `sdkconfig` still said `# CONFIG_ENABLE_TOLLGATE is not set`, and because
ESP-IDF ignores `sdkconfig.defaults*` once a `sdkconfig` file exists, the tollgate
code was compiled out (the `tollgate_send_pay` CLI command simply did not exist).
Fixed by `97ac756` (the current tip of this branch). Consequence for this contract:

> Enabling the feature requires `CONFIG_ENABLE_TOLLGATE=y` in the **tracked**
> `sdkconfig`, not only in `sdkconfig.defaults.esp32s3`. A green build proves
> nothing about the feature being present — verify by grepping the built image for
> the symbol or by checking that `tollgate_send_pay` registers (`app_main.cpp:670-673`).

---

## 7. Conformance checklist

Every call site and mock usage was cross-checked against §1–§6 by reading the file
and, where a claim is testable, by executing the suite (see §10).

### 7.1 `tracker/firmware/main/app_task.cpp` (RX path, balloon side)

| # | Site | Expectation from this contract | Status |
|---|---|---|---|
| A1 | `:32-34` `#ifdef CONFIG_ENABLE_TOLLGATE` around the `#include` | §6.2 guard on the include, not in the header | CONFORMS |
| A2 | `:114-145` the whole `case RELAY_TYPE_TOLLGATE_PAY` inside the same guard | call sites guarded identically | CONFORMS |
| A3 | `:90` `pkt_type = pkt.data[0]`, `:115` dispatched against `RELAY_TYPE_TOLLGATE_PAY` | §4.2 tag is byte 0 and is the RELAY namespace | CONFORMS |
| A4 | `:120` `tollgate_proto_decode(pkt.data + 1, pkt.len - 1, &hdr, &payload) >= 0` | §1 frame offset +1, length −1; §5.3 success is `8 > 0` | CONFORMS (`> 0` preferred) |
| A5 | `:121` `hdr.seq` used in the log line | §2 `seq` lives at hdr offset 2 | CONFORMS |
| A6 | `:126` `ack_pkt.data[0] = RELAY_TYPE_TOLLGATE_ACK` | §4.2 tag = `0x03` for balloon→client | CONFORMS |
| A7 | `:128-130` builds a zeroed `tollgate_ack_payload_t`, sets only `price_sats = 0` | §3 layout; v1 sends zeros | CONFORMS (values provisional) |
| A8 | `:132-136` `encode(ack_pkt.data + 1, RELAY_PACKET_MAX_SIZE - 1, TG_MSG_ACK, hdr.seq, (const char *)&ack_payload, sizeof(ack_payload))` | §1 capacity 511; §4.2 inner type `TG_MSG_ACK`=0x02 ≠ tag 0x03; §3 raw 14-byte struct image; §2 seq echoed verbatim | CONFORMS |
| A9 | `:137-139` `ack_pkt.len = ack_len + 1` then `xQueueSend` | §5.2 return is total length; §1 `pkt.len` includes the tag | CONFORMS |
| A10 | the `payload` pointer is never dereferenced | see CHECKLIST NOTE N1 — payload content is opaque in v1 | CONFIRMED-BY-DESIGN |
| A11 | no NACK / INFO / STATUS / REVOKE path, no token validation, no dedup | §8: declared-but-unimplemented; Kconfig help text slightly overstates behaviour | GAP (documented) |

### 7.2 `tracker/firmware/main/test/test_relay_pipeline.c` (the mock)

| # | Site | Expectation from this contract | Status |
|---|---|---|---|
| M1 | `:83` unguarded `#include "tollgate_payment_proto.h"` on host gcc | §6.2 header must stay Kconfig-free | CONFORMS |
| M2 | `:129-154` mock `app_task` dispatch mirrors `app_task.cpp` | same frame offsets as A4/A8 | CONFORMS |
| M3 | `:133` `decode(pkt->data + 1, pkt->len - 1, &hdr, &payload) > 0` | §5.3 | CONFORMS |
| M4 | `:137` `ack_pkt.data[0] = RELAY_TYPE_TOLLGATE_ACK` | §4.2 tag 0x03 | CONFORMS |
| M5 | `:139-141` zeroed `tollgate_ack_payload_t`, `price_sats = 0` | §3 | CONFORMS |
| M6 | `:143-147` `encode(ack_pkt.data + 1, RELAY_PACKET_MAX_SIZE - 1, TG_MSG_ACK, hdr.seq, (const char *)&ack, sizeof(ack))` | §1, §3, §4.2 | CONFORMS |
| M7 | `:148-150` `ack_len > 0` → `ack_pkt.len = ack_len + 1`, push to mock TX queue | §5.2 | CONFORMS |
| M8 | `:201-215` `build_tollgate_pay_packet`: `data[0] = RELAY_TYPE_TOLLGATE_PAY`, `encode(…, TG_MSG_PAY, seq, NULL, 0)`, `pkt.len = enc_len + 1` | §1; §5.2 zero-length payload legal (`NULL` + `0` → `8`) | CONFORMS |
| M9 | `:368` `ack_pkt.data[0] == RELAY_TYPE_TOLLGATE_ACK` (TEST 4) | §4.2 | CONFORMS |
| M10 | `:374-375` `ack_hdr.type == TG_MSG_ACK`, `ack_hdr.seq == 42` (TEST 4) | §2 `type`, §2 `seq` echo | CONFORMS |
| M11 | `:400`, `:405-406` (TEST 5, seq 100..104) | §2 seq echo | CONFORMS |
| M12 | `:509`, `:513-514` (TEST 8, seq 200..203) | §2 seq echo | CONFORMS |
| M13 | `:622-626` `RELAY_TYPE_*` constant asserts (`0x01/0x02/0x03/0x04/0xFF`) | §4.2 tag values frozen | CONFORMS |
| M14 | `:619` `sizeof(relay_packet_t) >= 512 + …` | §1 capacity basis | CONFORMS |
| M15 | TEST 10 `len == 0` → no crash, no TX | §1 `app_task.cpp:90` reads `data[0]` only when `len > 0`; contract implies no frame ⇒ no message | CONFORMS |

### 7.3 Peripheral consumers (not in the acceptance list, checked for completeness)

| # | Site | Expectation | Status |
|---|---|---|---|
| P1 | `main/app_main.cpp:575, 612-646` `tollgate_send_pay` CLI | §1 `data[0]=0x02`, `encode(data+1, MAX-1, TG_MSG_PAY, seq, payload, len)`, `pkt.len = enc_len+1`; §1.4 503-byte ceiling computed at `:612` | CONFORMS |
| P2 | `main/app_main.cpp:591` `static uint32_t s_tollgate_seq` cast to `uint16_t` at `:627` | §2 `seq` is 16-bit; the counter wraps at 65535 as the cast implies | CONFORMS (see DEVIATION-6 for the type) |
| P3 | `main/app_main.cpp:670-673` CLI registration inside `#ifdef CONFIG_ENABLE_TOLLGATE` | §6.2 | CONFORMS |
| P4 | `main/test/test_tollgate_payment_proto.c` (83 assertions) | §2 offsets/size, §3 size=14, §5.2 exact-fit/NULL, §5.3 short/bad-version/truncated — **executed: 83/83 pass** | CONFORMS |
| P5 | `test/integration/test_tollgate_payack.py:97-103` Python mirror of the constants | §4.1/§4.2 values match the C header exactly | CONFORMS (constants only) |
| P6 | `main/CMakeLists.txt` conditional `APP_SRCS` append | §6.2 | CONFORMS |
| P7 | `.github/workflows/ci-host-tests.yml:41-46` builds both host suites with no Kconfig | §6.2 (header must be Kconfig-free) | CONFORMS |

### 7.4 Checklist notes

* **N1** — `app_task.cpp:118/120` takes `&payload` from `decode()` but never reads
  the payload bytes; the ACK carries no token data. So **the internal format of the
  PAY payload is not pinned by any tracker call site** in v1: `app_main.cpp:603-608`
  sends either a raw token string or the literal `{"token":"test"}`, and both are
  accepted by the balloon. This contract therefore declares the PAY payload
  *opaque application data* of length `payload_len` — chosen deliberately, because
  inventing a format here would contradict the observation that no code consumes it.
* **N2** — `tollgate_pay_payload_t` is a declared-but-unused 2048-byte struct. No
  call site instantiates it, so it imposes no wire requirement, but note that
  instantiating it on a FreeRTOS task stack is a real hazard (2 KB).
* **N3** — all three producer log lines that the hardware harness parses are part of
  the *de-facto* interface even though they are not wire format:
  `app_task.cpp:121` (`TollGate PAY received (seq=%u)`), `:140`
  (`TollGate ACK queued (seq=%u)`), `app_main.cpp:645`
  (`tollgate_send_pay: queued %u bytes (seq=%u, …)`). Changing these strings breaks
  `test_tollgate_payack.py` silently. Frozen by this contract as an observability
  interface.
* **N4** — the harness compares PAY and ACK `seq` for exact equality
  (`test_tollgate_payack.py:305-313`), which is the end-to-end reason the echo
  semantics of §2 are normative.

---

## 8. Provenance

### 8.1 From the upstream spec (values/types copied, not invented)

| Item | Upstream source | Tracker location | Fidelity |
|---|---|---|---|
| `TG_MSG_*` enum values 0x01–0x06 | `tollgate_balloon.h:31-38` | `tollgate_payment_proto.h:39-46` | identical |
| `tollgate_msg_hdr_t` fields, order, types | `tollgate_balloon.h:40-46` | `:49-55` | identical (incl. `packed`) |
| `TOLLGATE_PROTO_VERSION = 1` | `tollgate_balloon.h:48` | `:33` | identical value |
| `TOLLGATE_MAX_TOKEN_LEN = 2048` | `tollgate_balloon.h:28` | `:36` | identical value |
| `tollgate_ack_payload_t` layout | `tollgate_payment_proto.h:28-34` | `:63-68` | byte-identical |
| `tollgate_nack_payload_t` layout | `tollgate_payment_proto.h:37-40` | `:71-74` | byte-identical |
| `TG_ERR_*` codes −1…−5 | `tollgate_payment_proto.h:43-47` | `:77-81` | identical |
| `tollgate_proto_encode()` signature | `tollgate_payment_proto.h:64-66` | `:94-96` | identical |
| `tollgate_proto_decode()` signature | `tollgate_payment_proto.h:73-75` | `:107-109` | identical |
| encode/decode behaviour | `…/src/tollgate_payment_proto.c:14-54` | `tollgate_payment_proto.c:14-54` | logic identical; the tracker adds a `(uint16_t)` cast on the `sizeof` comparison, which is semantically inert |

Note: the upstream declarations live in **two** headers
(`tollgate_msg_type_t`/`tollgate_msg_hdr_t`/`TOLLGATE_PROTO_VERSION`/
`TOLLGATE_MAX_TOKEN_LEN` in `tollgate_balloon.h`, the payload structs and prototypes
in `tollgate_payment_proto.h`); the header's cross-reference to
`mesh-stack/tollgate/components/tollgate_balloon/` is therefore accurate.

### 8.2 Invented / local decisions, with reasons

**PROVENANCE-INVENTED-1 — the four shared declarations were relocated into the
proto header.** Upstream's proto header does `#include "tollgate_balloon.h"`, which
pulls `tollgate_platform.h` and `esp_err.h` — not host-compilable. The tracker header
therefore *redeclares* the enum, the header struct, the version and the token cap
locally so that it compiles with plain `gcc` (values unchanged). Reason: CI suites 2
and P4 build it with no ESP-IDF. Cost: the values now exist in two places and can
drift; this document is the tie-breaker.

**PROVENANCE-INVENTED-2 — the 1-byte relay tag and its `0x02`/`0x03` values.**
Upstream's framing prefix is a *service mux* id (`MESH_SVC_TOLLGATE = 0x01`) applied
to FIPS mesh datagrams. The tracker has a different transport (`relay_packet_t` over
the LR2021/FLRC relay pipeline) and invented `RELAY_TYPE_TOLLGATE_PAY = 0x02` /
`RELAY_TYPE_TOLLGATE_ACK = 0x03` in `relay_types.h:12-13`, validated only by
`test_relay_pipeline.c:622-626`. Reason: the tracker must demultiplex TollGate from
Nostr events and telemetry inside one radio frame, and `0x01`/`0x04` were already
taken by `RELAY_TYPE_NOSTR_EVENT`/`RELAY_TYPE_TELEMETRY`. Consequence: the 1-byte
prefix is **not** interoperable with upstream mesh frames — a mesh-side integrator
must translate the tag. This invention is the direct cause of the numeric collisions
in §4.3.

**PROVENANCE-INVENTED-3 — the ACK payload is a raw packed binary struct, not
JSON.** ADR-002 explicitly leaves the message format open and *proposes* JSON
(`docs/adr/002-tollgate-over-fips-mesh-udp.md:83-84`), and upstream's proto header
comment says "Payloads are JSON for v1" while simultaneously declaring the packed
binary structs (an internal contradiction upstream). The tracker resolved it to
binary-packed, justified by its only call site: `app_task.cpp:135` passes
`(const char *)&ack_payload` with `sizeof(ack_payload)`, and
`test_tollgate_payment_proto.c:311-313` reinterprets the decoded payload pointer as
`const tollgate_ack_payload_t *`. Reason: no JSON codec is linked into the tracker's
ACK path and the fixed 14-byte struct is cheaper than formatting JSON on a balloon.
This is a documented deviation from the ADR's proposal, not an oversight.

**PROVENANCE-INVENTED-4 — decode tolerates trailing bytes; `payload_len` over-claim
is the only truncation signal.** Upstream's `if (hdr->payload_len > len -
sizeof(hdr))` happens to behave this way, but neither the upstream comment nor
ADR-002 states the tolerance as a rule. It is stated here because the tracker's
frame is radio-delivered and may be padded.

**PROVENANCE-INVENTED-5 — `reserved` must be ignored by receivers.** Upstream labels
it "Alignment / future use" but never says what a receiver does with a non-zero
value; the tracker implementation writes 0 and does not check it. Resolved here as
"write 0, ignore on read" so that a future use is not a breaking change, and so that
`decode` never rejects a frame for a field it cannot interpret.

**PROVENANCE-INVENTED-6 — `quota_bytes` has no tracker justification.** It is copied
from upstream for wire parity. No tracker call site sets it, no test asserts its
value, and the Kconfig help text does not mention quotas. It is retained only because
dropping it would change the 14-byte wire layout and break upstream parity. Flagged
as the one ACK field with no call-site consumer.

**PROVENANCE-INVENTED-7 — the error model (`-1` + no partial write; NULL payload with
non-zero length invalid; `hdr` required non-NULL).** Upstream returns `-1` without
specifying write behaviour on failure and without guarding these inputs. The stricter
semantics are fixed here because three call sites treat `-1` as "nothing was queued"
(`app_task.cpp:137`, `app_main.cpp:629`, `test_relay_pipeline.c:148`).

**PROVENANCE-INVENTED-8 — the `CONFIG_ENABLE_TOLLGATE` guard pattern.** Upstream
components are not Kconfig-gated per feature; the tracker's guard convention (and the
"header stays unguarded" rule) is local, derived from the two host test suites that
compile the header with no sdkconfig. The silent-compile-out failure mode is
evidenced by commit `97ac756`.

**PROVENANCE-INVENTED-9 — ADR-002 is cited but does not specify this layout.**
`tollgate_payment_proto.h:8` says "Wire format (ADR-002)". A full read of ADR-002
shows it specifies the *transport* (TollGate as L7 over FIPS mesh UDP, port 2121,
nucula wallet unchanged) and leaves "Payment message format: JSON over UDP? CBOR?
Protocol buffers?" as an **Open Question** (lines 83-84). The byte-level 8-byte header
comes from the `tollgate_balloon` component code, not from ADR-002. The citation is
therefore loose; this document is the correct byte-level authority.

### 8.3 Upstream capabilities the tracker does NOT implement (honest scope)

The header comment claims "Wire-compatible with the tollgate component's version" —
true for the header, the ACK/NACK payloads and the enum values, but **not** API- or
behaviour-complete:

1. `tollgate_proto_build_info_json()` exists upstream
   (`tollgate_payment_proto.h:81-84`) and is **absent** from the tracker header.
2. `TG_MSG_NACK`, `TG_MSG_STATUS`, `TG_MSG_INFO`, `TG_MSG_REVOKE` are declared but
   have **no producer or consumer** in the tracker.
3. `TG_MSG_PAY` payload semantics (token encoding) are unimplemented on the receiver:
   no token parsing, no Cashu validation, no mint contact — despite
   `Kconfig.projbuild:146-148` saying the feature "validates Cashu tokens". The
   current ACK is unconditional on PAY receipt (`app_task.cpp:115-144`).
4. `session_id` / `expires_unix` / `quota_bytes` are transmitted as zeros; the ACK
   conveys no session.

A conforming implementation of this contract is therefore *interoperable on the
wire* with upstream for PAY and ACK, and *not* a complete TollGate implementation.

---

## 9. Deviations between this contract and the current implementation

These are stated, not fixed — fixing them is implementation work outside this task.
Each is a place where the code does not satisfy §5. The shipped tests pass either way
(they do not exercise these paths), so none is currently caught by CI.

**DEVIATION-1 (correctness) — `encode` reports a length it did not write.**
`tollgate_payment_proto.c:28-30` copies the payload only when
`payload_len > 0 && payload != NULL`, but `:18` admits the call and `:32` returns
`8 + payload_len` regardless. So `encode(buf, 256, TG_MSG_PAY, 1, NULL, 20)` returns
`28` while leaving 20 uninitialised bytes in the frame, which are then transmitted as
"payload". Contract requires `-1` (§5.2 item 5). No call site triggers it today
(`app_main.cpp:603` always has a non-NULL string; `test_relay_pipeline.c:207-210`
passes `NULL` with length `0`), but the CLI would hit it the moment a caller passes
`payload_len > 0` with a NULL pointer.

**DEVIATION-2 (robustness) — `decode` dereferences `hdr` without a NULL check.**
`tollgate_payment_proto.c:42` `memcpy(hdr, …)`. Contract §5.3 item 4 makes `hdr`
required non-NULL; a conforming implementation should return `-1` instead of invoking
undefined behaviour. All current call sites pass a valid `&hdr` (A4, M3, M10).

**DEVIATION-3 (latent) — the 503-byte budget is a call-site constant, not an
enforced protocol limit.** `app_main.cpp:612` computes
`RELAY_PACKET_MAX_SIZE - 1 - sizeof(tollgate_msg_hdr_t)` inline; `app_task.cpp` does
not check the ceiling at all (its ACK is always 22 bytes, so it cannot exceed it
today). `TOLLGATE_MAX_TOKEN_LEN` is 2048, four times what the relay frame can carry,
so a 2048-byte token is rejected only by `encode`'s capacity check at the call site
that remembers to pass 511. Contract §1 requires the ceiling to be a single named
constant equal to 503 and enforced in the encode path (see §11 item 3).

**DEVIATION-4 (unstated, currently harmless) — `reserved` is not validated.** By
design per PROVENANCE-INVENTED-5; recorded here only so that "decode accepts a
non-zero `reserved`" is not mistaken for a bug later.

**DEVIATION-5 (portability) — the wire layout is host-endianness dependent.**
The header/struct fields are written by direct C struct assignment
(`tollgate_payment_proto.c:21-26`), so the byte order is the host's. All hosts in play
(Xtensa LX7 on the ESP32-S3, x86-64 for the host tests) are little-endian, and
`test_tollgate_payment_proto.c:145-146` hard-codes LE (`0x64,0x00` = 100,
`0x05,0x00` = 5), which passes on both. The contract fixes **little-endian** as the
wire format, so a conforming implementation must serialise explicitly
(byte-by-byte or LE accessors) rather than relying on host order — otherwise the
protocol silently changes on a big-endian target.

**DEVIATION-6 (cosmetic, but a wrap hazard) — the producer's counter is wider than
the field.** `app_main.cpp:591` `static uint32_t s_tollgate_seq` is narrowed by
`(uint16_t)` at `:627`. The wire contract is 16-bit; the counter should be `uint16_t`
so that wrap behaviour is explicit rather than implied by a cast.

**DEVIATION-7 (contract documentation, not code) — "u16 echo token" semantics are
not stated on this branch.** The mesh-baseline header says only "Sequence number for
dedup" (`tollgate_payment_proto.h:52`), which is wrong on two counts: there is **no
deduplication anywhere** in the firmware, and the actual semantics are *echo*:
`app_task.cpp:134` copies the requester's `seq` into the ACK and
`test_tollgate_payack.py:305-313` requires exact equality. §2 of this document fixes
the wording; a future header revision should carry it (see §11 item 2).

---

## 10. Verification performed

All commands run in the task worktree checked out at branch
`autonomous/mesh-baseline` (`97ac756`), `tracker/firmware/`:

```
$ gcc -Wall -Wextra -O2 -I main -o /tmp/test_tg_proto \
      main/test/test_tollgate_payment_proto.c main/tollgate_payment_proto.c \
  && /tmp/test_tg_proto
=== Results: 83 passed, 0 failed ===        # exit 0
# pins: sizeof(hdr)==8, field offsets 0/1/2/4/6, LE byte order, exact-fit encode,
#       NULL-buffer -1, decode offset==8, version gate, truncation gate,
#       sizeof(ack_payload)==14, ACK round-trip

$ gcc -Wall -O2 -I main -I components/nostr_store/include -o /tmp/test_relay_pipeline \
      main/test/test_relay_pipeline.c main/tollgate_payment_proto.c \
      components/nostr_store/nostr_store.c \
  && /tmp/test_relay_pipeline
=== Results: 12/12 passed ===               # exit 0
# pins: the mock dispatch (M2-M12), RELAY_TYPE_* values (M13), frame len = enc+1 (M7/M8)
```

These are the same two invocations CI uses
(`.github/workflows/ci-host-tests.yml:41-46`); both suites are green on this branch,
which is why §7 can assert CONFORMS for the sites those tests cover, and why §9's
deviations are marked as not currently caught by CI.

---

## 11. Forward work this contract implies (not done here)

1. **DEVIATION-1** — return `-1` for `payload == NULL && payload_len > 0`.
2. **DEVIATION-7 / §2** — put the u16 echo-token wording in the header comment, and
   delete the false "for dedup" claim, or implement dedup and change this contract.
3. **DEVIATION-3** — name the ceiling (`TOLLGATE_MAX_PAYLOAD_RELAY = 503`) and enforce
   it inside the encode path so callers cannot pass `RELAY_PACKET_MAX_SIZE` by mistake.
4. **DEVIATION-5 / DEVIATION-2** — explicit little-endian serialisation and a NULL
   `hdr` guard.
5. **§4.3** — add a compile-time-visible warning (comment block or static assert pair)
   next to the two enum tables so the tag/type namespaces are not cross-compared.

**Reconciliation note (in-flight work, outside this branch's contract surface).** A
newer lineage than `autonomous/mesh-baseline` already carries some of items 1–5 in
`tracker/firmware/main/tollgate_payment_proto.h` — an additive
`tollgate_proto_encode_relay(frame, frame_len, …)` that writes at `frame+1` and owns
the 503-byte budget, `TG_ENC_ERR_TOO_LONG`, `TOLLGATE_MAX_PAYLOAD_RELAY`,
`tollgate_seq_next()`/`tollgate_seq_equal()`, and an explicit seq echo-token comment
(sibling branches `fix/tollgate-payack-harness-seq`,
`fix/tollgate-payack-sid-price-exp`, `fix/tollgate-payack-seq-whitespace`; defect ids
D1/D5/D6). Those branches are 273–280 commits ahead of and 2 behind
`autonomous/mesh-baseline`, i.e. they are a different lineage, **not** the branch this
contract is authoritative for. This document deliberately specifies the
`encode(data + 1, MAX - 1, …)` form that `app_task.cpp` and `test_relay_pipeline.c`
actually call on `autonomous/mesh-baseline` (§7 A8/M6), and records the additive
`encode_relay()` form here so the eventual merge has one place that states which call
shape the callers must use after the merge.
