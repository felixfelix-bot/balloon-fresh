## Tollgate API shape required by app_task.cpp (autonomous/mesh-baseline @ 4ec5e53)

Scope: every TollGate symbol reference in `tracker/firmware/main/app_task.cpp` on branch
`autonomous/mesh-baseline` at commit `4ec5e53` (`docs(tollgate): author
TOLLGATE_PROTO_CONTRACT.md …`). All paths below are relative to the worktree root
`/home/c03rad0r/worktrees/tg-proto-contract` unless prefixed with `tracker/firmware/`.

**Upstream-report provenance.** Report B was supplied and is on disk as
`docs/recon/.tollgate_config_notes.md` (verified line-for-line, see §d). **Report A had no
on-disk artifact** — `docs/recon/` contains only the Report-B scratch file, and
`git ls-tree -r` over every branch in the repo returns **zero** hits for
`docs/recon/tollgate_proto*`. Rather than fabricate Report A, its contents were
reconstructed from the primary source (`main/app_task.cpp`) and every line it would have
cited was re-read and verified directly; the 24/24 call-site citations and 34/34
config citations in this document are the verification result. This is stated up front
because the task's reconciliation step assumes an existing Report A to reconcile against.

Short SHA used in the title: **4ec5e53**. Full: `4ec5e53cfbdc3f672e698c9defe54395613f6230`.

---

### (a) Call-site table

Every TollGate symbol reference in `main/app_task.cpp`, exhaustively. "Line" is the
verified line number (see §b for verbatim quotes); none drifted.

| line | symbol | call site | argument types (ordered) | return type | result check | buffer/error assumptions |
|---|---|---|---|---|---|---|
| 32–34 | `CONFIG_ENABLE_TOLLGATE` | `#ifdef` guard around `#include "tollgate_payment_proto.h"` | n/a | n/a | n/a | Header only included when flag `=y`; include is guarded, **header body is not** |
| 90 | `pkt.data[0]`, `pkt.len`, `RELAY_TYPE_RAW` | relay framing: `uint8_t pkt_type = (pkt.len > 0) ? pkt.data[0] : RELAY_TYPE_RAW;` | `uint8_t[]`, `size_t` | `uint8_t` | `pkt.len > 0` guard | `data[0]` is the 1-byte relay tag; `len` may be 0 ⇒ must not read `data[0]` |
| 114–115 | `CONFIG_ENABLE_TOLLGATE`, `RELAY_TYPE_TOLLGATE_PAY` | `#ifdef` guard + `case RELAY_TYPE_TOLLGATE_PAY: {` | tag `uint8_t` (via `pkt_type`) | n/a | switch dispatch | Tag value `0x02` comes from `relay_types.h:12`; inner message type is a *different* namespace |
| 117 | `tollgate_msg_hdr_t` | `tollgate_msg_hdr_t hdr;` | — | — | — | Must be default-constructible and fully written by `decode`; caller does **not** `memset` it |
| 118 | `const uint8_t *` | `const uint8_t *payload = NULL;` | — | — | — | `payload` is an **out**-param slot; never dereferenced in this file |
| 120–121 | `tollgate_proto_decode` | `tollgate_proto_decode(pkt.data + 1, pkt.len - 1, &hdr, &payload) >= 0` | `uint8_t*`(→`const uint8_t*`), `size_t`(→`uint16_t`), `tollgate_msg_hdr_t*`, `const uint8_t**` | `int` | `>= 0` (weakest form; success is always `+8`, so `> 0` is equivalent) | Input starts at `data + 1` (tag skipped), length `len - 1`; both out-params non-NULL |
| 121 | `hdr.seq` | `ESP_LOGI(TAG, "TollGate PAY received (seq=%u)", hdr.seq)` | — | — | — | `hdr.seq` must be an integer promotable to `unsigned` for `%u` (⇒ ≤ `uint32_t`) |
| 124–126 | `relay_packet_t`, `RELAY_TYPE_TOLLGATE_ACK` | `relay_packet_t ack_pkt; memset(...); ack_pkt.data[0] = RELAY_TYPE_TOLLGATE_ACK;` | — | — | — | `data[0]` written **before** `encode` writes `data + 1` ⇒ `encode` must not disturb byte 0 |
| 128–130 | `tollgate_ack_payload_t` | `tollgate_ack_payload_t ack_payload; memset(...); ack_payload.price_sats = 0;` | — | — | — | Struct is `memset`-able and has a `.price_sats` member; only member touched here |
| 132–136 | `tollgate_proto_encode` | `tollgate_proto_encode(ack_pkt.data + 1, RELAY_PACKET_MAX_SIZE - 1, TG_MSG_ACK, hdr.seq, (const char *)&ack_payload, sizeof(ack_payload))` | `uint8_t*`, `int`(→`uint16_t`), enum, `uint16_t`, `const char*`, `size_t`(→`uint16_t`) | `int` | `ack_len > 0` at :137 | `buf` at `data + 1`, capacity **511**; payload is a **raw struct image**; `sizeof(size_t)`→`uint16_t` narrowing at arg 6 is implicit (see §c note) |
| 134 | `TG_MSG_ACK` | inner message type passed to `encode` | enum constant | — | — | Value **not** resolvable from `app_task.cpp`; defined in the header (`= 0x02`) |
| 137–140 | `ack_len`, `ack_pkt.len`, `xQueueSend`, `hdr.seq` | `if (ack_len > 0) { ack_pkt.len = ack_len + 1; xQueueSend(...); }` | `int` → `size_t`; `QueueHandle_t`, `void*`, `TickType_t` | `BaseType_t` (ignored) | `ack_len > 0`; `xQueueSend` result **not** checked | `encode`'s return is a **total message length** (`+1` yields frame length) — the key constraint; TX failure is silent |
| 143–145 | `break; }` + `#endif /* CONFIG_ENABLE_TOLLGATE */` | case close + guard close | — | — | — | Case body fully inside the same guard as the include |

Symbols referenced in `app_task.cpp` but **defined elsewhere** (see §e): `RELAY_TYPE_TOLLGATE_PAY`,
`RELAY_TYPE_TOLLGATE_ACK`, `RELAY_TYPE_RAW`, `RELAY_PACKET_MAX_SIZE`, `relay_packet_t`
(`main/relay_types.h`); `tollgate_msg_hdr_t`, `tollgate_ack_payload_t`, `TG_MSG_ACK`,
`tollgate_proto_decode`, `tollgate_proto_encode` (`main/tollgate_payment_proto.h`).

---

### (b) Verbatim code quotes

Each block is the exact text of `main/app_task.cpp` at the cited line, re-read on
`autonomous/mesh-baseline @ 4ec5e53`. Line numbers verified by scripted exact-substring
match (24/24).

`main/app_task.cpp:32-34` — include guard (the only header inclusion of the proto header):

```cpp
#ifdef CONFIG_ENABLE_TOLLGATE
#include "tollgate_payment_proto.h"
#endif
```

`main/app_task.cpp:90` — relay framing: the type tag is byte 0, and is read only when `len > 0`:

```cpp
        uint8_t pkt_type = (pkt.len > 0) ? pkt.data[0] : RELAY_TYPE_RAW;
```

`main/app_task.cpp:114-115` — dispatch: the case body lives inside the same `#ifdef` as the include:

```cpp
#ifdef CONFIG_ENABLE_TOLLGATE
        case RELAY_TYPE_TOLLGATE_PAY: {
```

`main/app_task.cpp:117-118` — declarations: `hdr` is uninitialised, `payload` is an out-slot:

```cpp
            tollgate_msg_hdr_t hdr;
            const uint8_t *payload = NULL;
```

`main/app_task.cpp:120-121` — **decode call site** (the sole one in this file):

```cpp
            if (tollgate_proto_decode(pkt.data + 1, pkt.len - 1, &hdr, &payload) >= 0) {
                ESP_LOGI(TAG, "TollGate PAY received (seq=%u)", hdr.seq);
```

`main/app_task.cpp:124-126` — ACK frame construction; byte 0 (the relay tag) is set before `encode` runs:

```cpp
                relay_packet_t ack_pkt;
                memset(&ack_pkt, 0, sizeof(ack_pkt));
                ack_pkt.data[0] = RELAY_TYPE_TOLLGATE_ACK;
```

`main/app_task.cpp:128-130` — ACK payload build; `price_sats` is the only member written, as a zero sentinel:

```cpp
                tollgate_ack_payload_t ack_payload;
                memset(&ack_payload, 0, sizeof(ack_payload));
                ack_payload.price_sats = 0;  /* TODO: real price from config */
```

`main/app_task.cpp:132-136` — **encode call site** (the sole one in this file):

```cpp
                int ack_len = tollgate_proto_encode(ack_pkt.data + 1,
                                                     RELAY_PACKET_MAX_SIZE - 1,
                                                     TG_MSG_ACK, hdr.seq,
                                                     (const char *)&ack_payload,
                                                     sizeof(ack_payload));
```

`main/app_task.cpp:137-140` — return-value check and queueing; the result is treated as a **total length**:

```cpp
                if (ack_len > 0) {
                    ack_pkt.len = ack_len + 1;
                    xQueueSend(g_tx_queue, &ack_pkt, pdMS_TO_TICKS(100));
                    ESP_LOGI(TAG, "TollGate ACK queued (seq=%u)", hdr.seq);
                }
```

`main/app_task.cpp:143-145` — case close, then guard close:

```cpp
            break;
        }
#endif /* CONFIG_ENABLE_TOLLGATE */
```

---

### (c) Inferred prototypes

Derived solely from the call sites above. The shape below is **proven to compile
unchanged against `main/app_task.cpp`** (see §e, verification log).

```c++
/* ---------------------------------------------------------------------------
 * Minimum declarations required by main/app_task.cpp.
 * Header must be C-linkage (app_task.cpp is a C++ TU: :33) and must NOT be
 * wrapped in CONFIG_ENABLE_TOLLGATE — see §d.
 * ------------------------------------------------------------------------- */

/* Message types. In app_task.cpp only TG_MSG_ACK is referenced (:134); its value
 * is NOT resolvable from app_task.cpp alone — pinned by the header to 0x02.
 * TG_MSG_PAY is NOT referenced in app_task.cpp at all (it appears only at
 * app_main.cpp:627). Values below are the header's, not this file's. */
typedef enum {
    TG_MSG_PAY = 0x01,   /* observed value: header tollgate_payment_proto.h:40 */
    TG_MSG_ACK = 0x02,   /* observed value: header tollgate_payment_proto.h:41 */
} tollgate_msg_type_t;

/* Header struct. app_task.cpp touches ONLY the .seq member (:121, :134, :140),
 * so the minimum field set implied by this file is { uint16_t seq; }.
 * The full 8-byte packed layout is required by the struct-size arithmetic at
 * :133 (RELAY_PACKET_MAX_SIZE - 1) and :136 (sizeof(ack_payload)); it is
 * defined elsewhere (header) and is not independently derivable from
 * app_task.cpp. Verified: sizeof == 8, seq at offset 2. */
typedef struct {
    uint8_t  version;       /* header :50 — not touched by app_task.cpp */
    uint8_t  type;          /* header :51 — not touched by app_task.cpp */
    uint16_t seq;           /* :121, :134, :140 — the only member read */
    uint16_t payload_len;   /* header :53 — not touched by app_task.cpp */
    uint16_t reserved;      /* header :54 — not touched by app_task.cpp */
} __attribute__((packed)) tollgate_msg_hdr_t;

/* ACK payload. app_task.cpp touches ONLY .price_sats (:130) and takes its
 * sizeof (:136). Implied minimum field set: { <integer> price_sats; } plus a
 * fixed size that must equal what is transmitted. Full packed 14-byte layout
 * is defined elsewhere (header); verified sizeof == 14. */
typedef struct {
    uint32_t price_sats;    /* :130 — narrowed view of header's uint16_t (see NOTE-2) */
} __attribute__((packed)) tollgate_ack_payload_t;

/* ENCODE. Constrained by :132-136 (args) and :137-138 (return semantics):
 *   arg1 uint8_t*                 ack_pkt.data + 1        (:132)
 *   arg2 uint16_t                 RELAY_PACKET_MAX_SIZE-1 (:133) => 511
 *   arg3 tollgate_msg_type_t      TG_MSG_ACK              (:134)
 *   arg4 uint16_t                 hdr.seq                 (:134)
 *   arg5 const char*              (const char *)&ack_payload (:135)
 *   arg6 uint16_t                 sizeof(ack_payload)     (:136)
 * RETURN: total bytes written = header + payload. MUST be a total length, not
 * an offset: :138 does `ack_pkt.len = ack_len + 1` and expects the frame length
 * to be 1 tag byte + the whole message. Success is strictly positive (:137). */
int tollgate_proto_encode(uint8_t *buf, uint16_t buf_len,
                          tollgate_msg_type_t type, uint16_t seq,
                          const char *payload, uint16_t payload_len);

/* DECODE. Constrained solely by :120:
 *   arg1 const uint8_t*           pkt.data + 1            (:120)
 *   arg2 uint16_t                 pkt.len - 1             (:120)
 *   arg3 tollgate_msg_hdr_t*      &hdr   (required, filled unconditionally)
 *   arg4 const uint8_t**          &payload (optional out-slot; never read here)
 * RETURN: int. The check is `>= 0` (:120). Success must be >= 0 and the
 * implementation returns sizeof(header) == 8 on success; nothing in this file
 * consumes the actual value, so any non-negative success code compiles. */
int tollgate_proto_decode(const uint8_t *data, uint16_t len,
                          tollgate_msg_hdr_t *hdr,
                          const uint8_t **payload);
```

**Justification (one line each):**

* `tollgate_proto_encode` — six positional args in the order `(uint8_t*, uint16_t, enum, uint16_t, const char*, uint16_t)` and a positive-total-length return are forced by the single call site `main/app_task.cpp:132-136` together with the check `ack_len > 0` and the `+1` framing at `main/app_task.cpp:137-138`.
* `tollgate_proto_decode` — four positional args `(const uint8_t*, uint16_t, tollgate_msg_hdr_t*, const uint8_t**)` and a non-negative-success return are forced by the single call site `main/app_task.cpp:120`.
* `tollgate_msg_hdr_t` — its shape is pinned by the `.seq` read at `main/app_task.cpp:121/134/140` (⇒ a `uint16_t`-promotable `seq` member) plus the size arithmetic that positions the message after the tag at `main/app_task.cpp:133`; the remaining fields come from the header, not from this file.
* `tollgate_ack_payload_t` — its shape is pinned by the `.price_sats = 0` write at `main/app_task.cpp:130` and by `sizeof(ack_payload)` being transmitted verbatim at `main/app_task.cpp:136`.
* `TG_MSG_ACK` — referenced at `main/app_task.cpp:134`; its **value** is unresolved from this file alone (defined in the header as `0x02`). `TG_MSG_PAY` is not referenced in `app_task.cpp` at all.

**RECONCILIATION — are the implied prototypes inconsistent?** No conflict. In
`app_task.cpp` there is exactly **one** `encode` call site (:132-136) and exactly
**one** `decode` call site (:120), so no intra-file argument-order disagreement is
possible. The only other call sites in the firmware are in `main/app_main.cpp`, and they
constrain the *same* signature in the *same* order, so the common denominator is
unambiguous:

| Constraint | `app_task.cpp` (this file) | `app_main.cpp` (corroborating, out of scope) |
|---|---|---|
| `encode` arg1 | `ack_pkt.data + 1` (`uint8_t*`) :132 | `pkt.data + 1` (`uint8_t*`) :625 |
| `encode` arg2 | `RELAY_PACKET_MAX_SIZE - 1` :133 | `RELAY_PACKET_MAX_SIZE - 1` :626 |
| `encode` arg3 | `TG_MSG_ACK` :134 | `TG_MSG_PAY` :627 |
| `encode` arg4 | `hdr.seq` (`uint16_t`) :134 | `(uint16_t)s_tollgate_seq` :627 |
| `encode` arg5 | `(const char *)&ack_payload` :135 | `payload` (`const char*`) :628 |
| `encode` arg6 | `sizeof(ack_payload)` :136 | `payload_len` (`uint16_t`) :628 |
| `encode` framing | `len = ack_len + 1` :138 | `len = enc_len + 1` :634 |
| `encode` failure check | `ack_len > 0` :137 | `enc_len < 0` :629 |

Both files therefore agree byte-for-byte on order, capacity constant, and
total-length return. **Safest common denominator** = exactly the two prototypes above,
unchanged. Argument-order drift would be a hard compile error, so a signature that
compiles against `app_task.cpp` and `app_main.cpp` is uniquely determined.

**Three real (non-conflicting) divergences that must be handled by types, not order:**

* **NOTE-1 — `decode` success check is the weak `>= 0`.** `app_task.cpp:120` uses `>= 0`,
  whereas `test_relay_pipeline.c:133` uses `> 0`. Since the implementation returns
  `sizeof(hdr) == 8` on success, both are behaviourally identical; if the header were ever
  changed to return `0` on success, `app_task.cpp` would accept it and the test would not.
  `> 0` is the safer form to standardise on.
* **NOTE-2 — `sizeof(ack_payload)` narrows to the `uint16_t` payload-length parameter at
  `app_task.cpp:136`.** The argument's type is `size_t` (8 bytes on this host) against a
  `uint16_t` parameter. This compiles silently (no diagnostic under `-Wall -Wextra`); it is
  the reason the ACK payload must remain small. `sizeof(tollgate_ack_payload_t) == 14` was
  verified — see §e.
* **NOTE-3 — `decode` arg2 `pkt.len - 1` narrows `size_t` → `uint16_t` at
  `app_task.cpp:120`.** Same class of implicit narrowing; benign here because
  `RELAY_PACKET_MAX_SIZE == 512`.

---

### (d) Feature flag

**Declaration.** The flag is declared once in `main/Kconfig.projbuild:141-148` and set in
two sdkconfig files. Quoted verbatim (all references re-verified 34/34):

`tracker/firmware/main/Kconfig.projbuild:141-144`:

```
config ENABLE_TOLLGATE
    bool "Enable TollGate payment processing (Cashu e-cash over mesh)"
    default n
    depends on ENABLE_RELAY_MODE
```

`tracker/firmware/sdkconfig:576` (tracked, generated — the one that actually governs the build):

```
CONFIG_ENABLE_TOLLGATE=y
```

`tracker/firmware/sdkconfig.defaults.esp32s3:83` (S3 defaults):

```
CONFIG_ENABLE_TOLLGATE=y
```

Context, `tracker/firmware/sdkconfig:575-577` — the flag sits in a block of related ENABLE_* symbols:

```
CONFIG_ENABLE_RELAY_MODE=y
CONFIG_ENABLE_TOLLGATE=y
CONFIG_ENABLE_NOSTR_STORE=y
```

**Consumption / guard sites (quoted):**

`main/app_task.cpp:32-34` — include guard:

```cpp
#ifdef CONFIG_ENABLE_TOLLGATE
#include "tollgate_payment_proto.h"
#endif
```

`main/app_task.cpp:114-145` — the dispatch case, inside the **same** guard:

```cpp
#ifdef CONFIG_ENABLE_TOLLGATE
        case RELAY_TYPE_TOLLGATE_PAY: {
            ...
#endif /* CONFIG_ENABLE_TOLLGATE */
```

`main/app_main.cpp:78-80` (second consumer include) and `main/app_main.cpp:575` /
`:649` / `:670-673` (function definition and CLI registration):

```cpp
#ifdef CONFIG_ENABLE_TOLLGATE
#include "tollgate_payment_proto.h"
#endif
```

`main/CMakeLists.txt:29-31` — build-system guard:

```cmake
if(CONFIG_ENABLE_TOLLGATE)
    list(APPEND APP_SRCS "tollgate_payment_proto.c")
endif()
```

**RECOMMENDED IDIOM — and a correction to the task wording.** The task asks for "the
recommended `#if CONFIG_ENABLE_TOLLGATE` idiom". That form is **contradicted by the
evidence** and must not be used here. Report B's survey of the tree found **50
`#if(n?def)? CONFIG_ENABLE_*` hits, every one of them `#ifdef`, and zero
`#if CONFIG_ENABLE_`**. ESP-IDF defines `CONFIG_ENABLE_TOLLGATE` only when the symbol is
`y`; when it is `n` the macro is absent entirely, so `#if CONFIG_ENABLE_TOLLGATE` would be
a compile error (or silently `0` under `-Wundef`, which this tree does not rely on). The
idiom to use is therefore:

```cpp
#ifdef CONFIG_ENABLE_TOLLGATE
    ... /* guarded block */
#endif /* CONFIG_ENABLE_TOLLGATE */
```

and for compound conditions, the tree's existing form at `main/app_main.cpp:662`:

```cpp
#if defined(CONFIG_ENABLE_RELAY_MODE) && defined(CONFIG_ENABLE_NOSTR_STORE)
```

**Two further rules the new header must obey (both evidenced):**

1. **Do NOT guard the header body.** `main/tollgate_payment_proto.h:22-30` uses a plain
   `#ifndef TOLLGATE_PAYMENT_PROTO_H` include guard plus `extern "C"`, with **no**
   `CONFIG_ENABLE_TOLLGATE` wrapper. Wrapping the body would break the host test suites,
   which compile the header and implementation with plain `gcc` and **no sdkconfig at
   all** (`.github/workflows/ci-host-tests.yml:41-46`). Guard the `#include` at the
   consumer (`app_task.cpp:32-34`, `app_main.cpp:78-80`), never the header.
2. **Do NOT add an `#ifndef CONFIG_*` fallback** for a boolean feature flag. In this tree
   the `#ifndef … #define … #endif` pattern exists only for integer pin/baud config values
   (`components/gps/gps.c:12-20`); boolean `ENABLE_*` flags rely on Kconfig for the default.

**Failure mode this convention protects against.** `#ifdef`-only guards compile the whole
feature out **silently** — no warning, no link error. That is observed history on this
lineage: `sdkconfig.defaults.esp32s3` had `=y` while the tracked `sdkconfig` still said
`# CONFIG_ENABLE_TOLLGATE is not set`, and because ESP-IDF ignores `sdkconfig.defaults*`
once a `sdkconfig` exists, the tollgate code was absent (the `tollgate_send_pay` CLI
command simply did not register). A green build therefore proves nothing about the feature
being present; verify by confirming `CONFIG_ENABLE_TOLLGATE=y` in the **tracked**
`sdkconfig` (line 576).

---

### (e) Coverage & gaps

**Symbols referenced in `app_task.cpp` but defined elsewhere:**

| Symbol | Referenced at | Defined at |
|---|---|---|
| `RELAY_PACKET_MAX_SIZE` (512) | `app_task.cpp:133` | `main/relay_types.h:6` |
| `RELAY_TYPE_TOLLGATE_PAY` (0x02) | `app_task.cpp:115` | `main/relay_types.h:12` |
| `RELAY_TYPE_TOLLGATE_ACK` (0x03) | `app_task.cpp:126` | `main/relay_types.h:13` |
| `RELAY_TYPE_RAW` (0xFF) | `app_task.cpp:90` | `main/relay_types.h:15` |
| `relay_packet_t` (`{uint8_t data[512]; size_t len; uint32_t timestamp; int rssi;}`) | `app_task.cpp:80, 124` | `main/relay_types.h:18-23` |
| `tollgate_msg_hdr_t` | `app_task.cpp:117` | `main/tollgate_payment_proto.h:49-55` |
| `tollgate_ack_payload_t` | `app_task.cpp:128` | `main/tollgate_payment_proto.h:63-68` |
| `tollgate_proto_decode` | `app_task.cpp:120` | `main/tollgate_payment_proto.h:107-109` (impl `…\.c:35-54`) |
| `tollgate_proto_encode` | `app_task.cpp:132` | `main/tollgate_payment_proto.h:94-96` (impl `…\.c:14-33`) |
| `TG_MSG_ACK` | `app_task.cpp:134` | `main/tollgate_payment_proto.h:41` (= 0x02) |
| `g_rx_queue`, `g_tx_queue` | `app_task.cpp:39-40, 139` | `main/app_main.cpp` (globals, `extern`-declared at :39-40) |

**Not resolvable from these two files alone:**

1. **`sizeof(tollgate_msg_hdr_t)` and `sizeof(tollgate_ack_payload_t)`.** `app_task.cpp`
   uses both as size arithmetic (`:133`, `:136`) but never reveals the numbers. The values
   (8 and 14) come from the header, not from this file; they were confirmed by compiling
   and running an offset/size probe (below), not inferred from `app_task.cpp`.
2. **The value of `TG_MSG_ACK`.** Used at `:134` but defined elsewhere; the header pins it
   to `0x02` (`tollgate_payment_proto.h:41`). From `app_task.cpp` alone it is *unresolved
   — defined elsewhere*.
3. **`hdr`'s non-`seq` fields.** `version`, `type`, `payload_len`, `reserved` are never
   touched by `app_task.cpp`; only `decode` fills them. Their layout is a header fact.
4. **The PAY payload's internal format.** `app_task.cpp:118-120` obtains a `payload`
   pointer and **never dereferences it** (verified: no `*payload` read anywhere in the
   file). The format of the PAY payload is therefore wholly unconstrained by
   `app_task.cpp`, and its pointer semantics reduce to "assignable to
   `const uint8_t*`".
5. **Whether `decode` writes `payload` at all.** The out-param is passed but never read,
   so a conforming `decode` could legally leave `*payload` untouched as far as
   `app_task.cpp` is concerned. (The header's contract does set it — that is a header
   fact, not an `app_task.cpp` requirement.)
6. **`app_main.cpp` sites.** `:625-628`, `:612`, `:629-634`, `:670-673` constrain the same
   prototypes and were used above only as corroboration; they are outside this task's
   stated scope (`main/app_task.cpp`).

**Verification log (real tool output, not inference).** Run on
`autonomous/mesh-baseline @ 4ec5e53`:

* **Citation re-verification:** scripted exact-substring match over `main/app_task.cpp`
  → **24/24 call-site citations verified, 0 mismatches**; over the Report-B site set
  → **34/34 verified, 0 mismatches**. **No line drift found** — every quoted line number
  in Reports A/B was already correct, so there was nothing to correct.
* **(A) Compiles against the real repo header:** the `app_task.cpp:114-145` block,
  structurally verbatim with only FreeRTOS/ESP-IDF stubbed, compiled under
  `g++ -std=c++17 -Wall -Wextra -Werror -DCONFIG_ENABLE_TOLLGATE -I tracker/firmware/main`
  → **PASS**.
* **(B) Compiles against the minimal reconstructed header in §c:** same translation unit,
  `-I <reconstructed>` → **PASS**. This is the acceptance test — a header consisting of
  exactly the §c prototypes and structs compiles the call sites unchanged.
* **(C) Flag off:** the same file with no `-DCONFIG_ENABLE_TOLLGATE` → **PASS**, i.e. the
  block vanishes entirely and zero tollgate symbols are referenced (demonstrating the
  silent-compile-out hazard of §d).
* **(D) Positive control:** forcing the block with `#if 1` while the flag is undefined
  produced compilation errors, confirming the block genuinely depends on the header
  declarations (the test is not vacuous).
* **Struct probe (§c values):** `sizeof(tollgate_msg_hdr_t)=8`, offsets
  `version=0 type=1 seq=2 payload_len=4 reserved=6`; `sizeof(tollgate_ack_payload_t)=14`;
  `512 - 1 - sizeof(tollgate_msg_hdr_t) = 503`.
* **Existing host unit tests green:** `test_tollgate_payment_proto.c` →
  **Results: 83 passed, 0 failed**, so this analysis is consistent with the shipped suite.

**Repo state — confirmation of no source modification.**
No file under `tracker/firmware/` was modified. The only change produced by this task is
the addition of this document as a new, non-source markdown file
(`TOLLGATE_API_SHAPE.md`) at the worktree root, committed locally to
`autonomous/mesh-baseline`. `git status --porcelain` after the commit shows a clean tree
apart from the pre-existing untracked `docs/recon/` scratch file belonging to Report B
(which is itself documented as delete-after-consolidation). All compiler probes were run
in `/tmp/tgverify`, outside the repo.
