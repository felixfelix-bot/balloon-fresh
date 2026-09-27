# TollGate decode-side report — `tracker/firmware/main/app_task.cpp`

Audit pass (audit + format) of the decode-side firmware analysis. Consolidates three
upstream inputs — the call-site inventory (balloon/t_6d751797), the signature-inference
"decode side" section (balloon/t_5dad1c52, emerging from t_468339f2), and the
undefined-symbol list — into one self-contained document for a downstream author wiring
`tollgate_payment_proto.h`.

Every claim below was **independently re-run in this audit**, not copied from the inputs
(see "Auditor's independent re-verification" at the end). Only read-only tools were used:
`git rev-parse`, `git status`, `cat`, `sed`, `grep`, `rg`, `nm`. No file under
`~/repos/balloon-fresh/tracker/firmware/` was created, modified, formatted or staged.

---

## 0. Revision pin (verbatim commands and output)

```
$ git -C ~/repos/balloon-fresh/tracker/firmware/ rev-parse --abbrev-ref HEAD
feat/tracker-tx-tempcomp

$ git -C ~/repos/balloon-fresh/tracker/firmware/ rev-parse HEAD
64b8923d2780b021fddd40ca57b367e7f333667c
```

The three inputs were authored against `64b8923d`. During this audit a concurrent task
landed one non-source commit on top (`261ad57` `docs: inventory tollgate symbols
referenced-but-not-defined in app_task.cpp`). The audit pin above is kept at `64b8923d`;
the audited file is byte-identical at the newer commit — `git rev-parse
261ad57:tracker/firmware/main/app_task.cpp` = `64b8923:tracker/firmware/main/app_task.cpp` =
`e2cf9aca005c13244d68ff26af0a9ec60e617f57`.

Audited file identity (re-verified):

```
$ cd ~/repos/balloon-fresh/tracker/firmware
$ wc -l main/app_task.cpp
164 main/app_task.cpp
$ git hash-object main/app_task.cpp
e2cf9aca005c13244d68ff26af0a9ec60e617f57
$ git rev-parse HEAD:tracker/firmware/main/app_task.cpp
e2cf9aca005c13244d68ff26af0a9ec60e617f57      # working copy == committed blob
$ git -C ~/repos/balloon-fresh/tracker/firmware/ status --porcelain \
      -- main/app_task.cpp tollgate_payment_proto.h tollgate_payment_proto.c
(empty output — not modified, not staged, not untracked)
```

**Branch-pin note (material, carried from the inputs and re-verified here).** The upstream
cards pin branch `autonomous/mesh-baseline`; the checked-out revision is
`feat/tracker-tx-tempcomp` @ `64b8923d`. The audited files are byte-identical on the two
branches —

```
$ git rev-parse HEAD:tracker/firmware/main/tollgate_payment_proto.h \
                 autonomous/mesh-baseline:tracker/firmware/main/tollgate_payment_proto.h
c76ac5e618007fcdc1e535303b72c815fa6206e2
c76ac5e618007fcdc1e535303b72c815fa6206e2
$ git rev-parse HEAD:tracker/firmware/main/tollgate_payment_proto.c \
                 autonomous/mesh-baseline:tracker/firmware/main/tollgate_payment_proto.c
c6d71a0f7ba8b1997ab41e6fde185d597991374c
c6d71a0f7ba8b1997ab41e6fde185d597991374c
```

— **except `sdkconfig`, which differs (see §4).**

---

## 1. Inferred prototypes (decode side)

### 1.1 Prototype block

Derived solely from the call sites in `main/app_task.cpp`. This is **byte-identical to the
prototype already shipped** at `main/tollgate_payment_proto.h:107-109` (definition
`main/tollgate_payment_proto.c:35-53`), so no new header is required for this file to compile.

```c
int tollgate_proto_decode(const uint8_t *data, uint16_t len,
                          tollgate_msg_hdr_t *hdr,
                          const uint8_t **payload);
```

The sole decode call site (`main/app_task.cpp:120`, re-read this session):

```
117             tollgate_msg_hdr_t hdr;
118             const uint8_t *payload = NULL;
119
120             if (tollgate_proto_decode(pkt.data + 1, pkt.len - 1, &hdr, &payload) >= 0) {
121                 ESP_LOGI(TAG, "TollGate PAY received (seq=%u)", hdr.seq);
```

### 1.2 Per-element justification (each with the quoted line it rests on)

Line quotes below were reproduced with `sed -n 'Np' main/app_task.cpp` during this audit.

| # | element | claim | cited line (re-verified) | support |
|---|---|---|---|---|
| 1 | return type | signed `int` | `main/app_task.cpp:120` → `if (tollgate_proto_decode(...) >= 0) {` | `>= 0` is the file's only consumption. An unsigned return makes `>= 0` tautological; `bool` would not need `>=`. Sibling `encode` uses `int` (`:132`) with `> 0` (`:137`), so `int` is the idiomatic choice. **Alternative reading:** `ssize_t` — weaker, no in-file hint. |
| 2 | param 1 ®value | pointer, not by value | `main/app_task.cpp:120` arg `pkt.data + 1` | address-arithmetic argument ⇒ pointer. `pkt.data` is `uint8_t[512]` at `main/relay_types.h:19`, so the expression type is `uint8_t *`. |
| 2b | param 1 ®const | **UNDETERMINED from `app_task.cpp` alone** | — | A non-const `uint8_t *` binds to a `const uint8_t *` parameter with no source change, so the call site cannot distinguish the two. **Both readings permitted.** `const` is *better supported* (corroborated) — by the paired out-param at `:118` (`const uint8_t *payload = NULL;`, pointer-to-const) and by the shipped header (`tollgate_payment_proto.h:107`) — but that is a header/corroboration fact, not something this file proves. Do not present the `const` on param 1 as proven by `app_task.cpp`. |
| 3 | param 2 ®by value | by value | `main/app_task.cpp:120` arg `pkt.len - 1` | the argument is an rvalue; a C-linkage C API (this header is `extern "C"`, `tollgate_payment_proto.h:28-30`) cannot take a reference. |
| 3b | param 2 ®input-only | **PROVEN input-only** | `main/app_task.cpp:120` arg `pkt.len - 1` | `pkt.len - 1` is an rvalue — there is no storage a callee could write a modified length back into. An in/out length parameter is *impossible* at this call site. |
| 3c | param 2 ®width | `uint16_t` (best supported) | `main/app_task.cpp:120`; corroborated `main/test/test_relay_pipeline.c:133`, `main/test/test_tollgate_payment_proto.c:154` | `pkt.len` is `size_t` (`main/relay_types.h:20`), accepted here with **no cast** — so the file permits any integral width. The explicit `(uint16_t)(pkt->len - 1)` cast at `test_relay_pipeline.c:133` and `(uint16_t)sizeof(data)` at `test_tollgate_payment_proto.c:154` are only necessary for a 16-bit parameter, and the buffer is capped at `RELAY_PACKET_MAX_SIZE` = 512 (`relay_types.h:6`), so `pkt.len - 1 ≤ 511` never truncates. **Alternative:** `size_t` — weaker, contradicted by the casts. |
| 4 | param 3 | `tollgate_msg_hdr_t *` non-const out-param | `main/app_task.cpp:117`, `:120`, `:121`, `:140` | `:117 tollgate_msg_hdr_t hdr;` is declared with **no initialiser** and read after the call (`:121`, `:140` read `hdr.seq`) ⇒ the callee writes it. A written object cannot be `const`. Field access is `.seq`. |
| 5 | param 4 | `const uint8_t **` | `main/app_task.cpp:118`, `:120` | `:118 const uint8_t *payload = NULL;` + `:120 &payload`. Pointee-const is **proven at compile level**: passing `const uint8_t **` to a `uint8_t **` parameter is ill-formed (const-drop), so the parameter cannot be `uint8_t **`. Out-param (write-through) is *inferred* from the NULL-init idiom; see the caveat below. |
| 6 | arity/order | 4 positional params, order as shown | `main/app_task.cpp:120` | the call passes exactly four arguments in that order. |

**Caveat on param 4 (out-param write-through) — labelled UNDETERMINED.** In
`app_task.cpp` the identifier `payload` appears on exactly two lines, `:118` (`= NULL`) and
`:120` (`&payload`); it is **never dereferenced afterwards**. The write-through inference
therefore rests on the NULL-initialisation idiom alone. From this file, a conforming
`decode` could legally leave `*payload` untouched; that `decode` *does* set it
(`tollgate_payment_proto.c:50-51`) is a header/implementation fact, not an `app_task.cpp`
requirement.

**Ambiguity ledger (alternative readings, explicitly labelled):**

* param 1 `const` — permitted vs proven: **UNDETERMINED from this file**, corroborated by header.
* param 2 width `uint16_t` vs `size_t` — this file permits either; `uint16_t` better supported (sibling casts + 512 cap).
* return type `int` vs `ssize_t` — `int` better supported.
* `payload` write-through — **UNDETERMINED from this file** (NULL idiom only).

Nothing in `main/app_task.cpp` fixes: parameter *names*, whether `decode` copies/validates
the payload, the exact error sentinel (`:120` proves only "negative ⇒ failure, `>= 0` ⇒
usable"), or `sizeof(tollgate_msg_hdr_t)` / `sizeof(tollgate_ack_payload_t)`.

---

## 2. Tollgate symbols referenced but not defined in `app_task.cpp`

Full reference set from the file (re-run this audit):

```
$ rg -n -i 'tollgate' main/app_task.cpp
6: *   - TollGate PAY → decode → ACK encode → push to tx_queue
32:#ifdef CONFIG_ENABLE_TOLLGATE
33:#include "tollgate_payment_proto.h"
114:#ifdef CONFIG_ENABLE_TOLLGATE
115:        case RELAY_TYPE_TOLLGATE_PAY: {
117:            tollgate_msg_hdr_t hdr;
120:            if (tollgate_proto_decode(pkt.data + 1, pkt.len - 1, &hdr, &payload) >= 0) {
121:                ESP_LOGI(TAG, "TollGate PAY received (seq=%u)", hdr.seq);
126:                ack_pkt.data[0] = RELAY_TYPE_TOLLGATE_ACK;
128:                tollgate_ack_payload_t ack_payload;
132:                int ack_len = tollgate_proto_encode(ack_pkt.data + 1,
140:                    ESP_LOGI(TAG, "TollGate ACK queued (seq=%u)", hdr.seq);
145:#endif /* CONFIG_ENABLE_TOLLGATE */
```

One entry per symbol. Each carries the exact search command re-run in this audit and its
raw classification.

### `tollgate_payment_proto.h` (the include, `app_task.cpp:33`) — DEFINED ELSEWHERE

```
$ find . -name 'tollgate_payment_proto*' | sort
./main/tollgate_payment_proto.c
./main/tollgate_payment_proto.h
```

### `tollgate_proto_decode` — DECLARED elsewhere + DEFINED elsewhere

```
$ rg -n 'tollgate_proto_decode' . | grep tollgate_payment
./main/tollgate_payment_proto.c:35:int tollgate_proto_decode(const uint8_t *data, uint16_t len,
./main/tollgate_payment_proto.h:107:int tollgate_proto_decode(const uint8_t *data, uint16_t len,
```

### `tollgate_proto_encode` — DECLARED elsewhere + DEFINED elsewhere

```
$ rg -n 'tollgate_proto_encode' main/tollgate_payment_proto.h main/tollgate_payment_proto.c
main/tollgate_payment_proto.h:94:int tollgate_proto_encode(uint8_t *buf, uint16_t buf_len,
main/tollgate_payment_proto.c:14:int tollgate_proto_encode(uint8_t *buf, uint16_t buf_len,
```

### `tollgate_msg_hdr_t` — DEFINED elsewhere

```
$ rg -n 'tollgate_msg_hdr_t' main/tollgate_payment_proto.h
main/tollgate_payment_proto.h:55:} __attribute__((packed)) tollgate_msg_hdr_t;
main/tollgate_payment_proto.h:108:                           tollgate_msg_hdr_t *hdr,
```

### field `hdr.seq` — DEFINED elsewhere

```
$ rg -n 'uint16_t seq' main/tollgate_payment_proto.h
main/tollgate_payment_proto.h:52:    uint16_t seq;           /* Sequence number for dedup */
```

### `tollgate_ack_payload_t` — DEFINED elsewhere

```
$ rg -n 'tollgate_ack_payload_t' main/tollgate_payment_proto.h
main/tollgate_payment_proto.h:68:} __attribute__((packed)) tollgate_ack_payload_t;
```

### field `ack_payload.price_sats` — DEFINED elsewhere

```
$ rg -n 'price_sats' main/tollgate_payment_proto.h
main/tollgate_payment_proto.h:67:    uint16_t price_sats;       /* Price that was charged */
```

### `TG_MSG_ACK` — DEFINED elsewhere (`0x02`)

```
$ rg -n 'TG_MSG_ACK' main/tollgate_payment_proto.h
main/tollgate_payment_proto.h:41:    TG_MSG_ACK      = 0x02,  /* Balloon → Client: Payment accepted + session info */
```

### `RELAY_TYPE_TOLLGATE_PAY` / `RELAY_TYPE_TOLLGATE_ACK` — DEFINED elsewhere

```
$ rg -n 'RELAY_TYPE_TOLLGATE' main/relay_types.h
main/relay_types.h:12:#define RELAY_TYPE_TOLLGATE_PAY 0x02
main/relay_types.h:13:#define RELAY_TYPE_TOLLGATE_ACK 0x03
```

### `RELAY_TYPE_RAW`, `RELAY_PACKET_MAX_SIZE`, `relay_packet_t` — DEFINED elsewhere

```
$ rg -n 'RELAY_TYPE_RAW|RELAY_PACKET_MAX_SIZE|relay_packet_t' main/relay_types.h
main/relay_types.h:6:#define RELAY_PACKET_MAX_SIZE 512
main/relay_types.h:15:#define RELAY_TYPE_RAW          0xFF
main/relay_types.h:18:typedef struct {
main/relay_types.h:23:} relay_packet_t;
```

### `g_rx_queue`, `g_tx_queue` — DECLARED elsewhere (app_main.cpp)

`app_task.cpp:39-40` declares both `extern`; `main/app_main.cpp:75-76` also carries
`extern` declarations. Both resolve; classification: **declared elsewhere, defined in the
app_main translation unit** (exact definition line not isolated read-only — see Evidence gaps).

### NOT FOUND — none

Symbols referenced in `app_task.cpp` but absent from the tree: **zero.** Every symbol
above resolves to a definition or declaration in `main/tollgate_payment_proto.h`,
`main/relay_types.h`, or `main/app_main.cpp`. The tree-wide tollgate surface is:

```
$ rg -il 'tollgate' main/ | sort
main/app_main.cpp
main/app_task.cpp
main/CMakeLists.txt
main/Kconfig.projbuild
main/relay_types.h
main/test/test_relay_pipeline.c
main/test/test_tollgate_payment_proto.c
main/tollgate_payment_proto.c
main/tollgate_payment_proto.h
```

No symbol resolves by declaration only with no body anywhere.

### Protocol-family symbols NOT referenced by `app_task.cpp` (completeness for the header author)

Re-run this audit, output genuinely empty:

```
$ rg -n 'tollgate_pay_payload_t|tollgate_nack_payload_t|TOLLGATE_PROTO_VERSION|TG_MSG_PAY|TG_ERR_' main/app_task.cpp
$ echo rc=$?
rc=1
```

All defined in the same header: `tollgate_msg_type_t` (`.h:39-46`), `TG_MSG_PAY` (`.h:40`),
`TG_MSG_NACK` (`.h:42`), `TG_MSG_STATUS` (`.h:43`), `TG_MSG_INFO` (`.h:44`),
`TG_MSG_REVOKE` (`.h:45`), `tollgate_pay_payload_t` (`.h:57-60`),
`tollgate_nack_payload_t` (`.h:74`), `TG_ERR_*` (`.h:77-81`),
`TOLLGATE_PROTO_VERSION` (`.h:33`), `TOLLGATE_MAX_TOKEN_LEN` (`.h:36`).

---

## 3. Struct shapes the file constrains (context for the header author)

Definitions live in the header the file already includes; the file pins only two members.

`main/tollgate_payment_proto.h:48-55` (8-byte packed):
`version` u8 @0, `type` u8 @1, `seq` u16 @2, `payload_len` u16 @4, `reserved` u16 @6.
Corroborated by `test_tollgate_payment_proto.c:65-66` (`sizeof == 8`) and the offset table
in `tollgate_payment_proto.h:11-16`.

`main/tollgate_payment_proto.h:63-68` (14-byte packed):
`session_id` u32 @0, `expires_unix` u32 @4, `quota_bytes` u32 @8, `price_sats` u16 @12.
Corroborated by `test_tollgate_payment_proto.c:289-290` (`== 14 (packed)`).

From `app_task.cpp` **alone**, only two members are pinned: `hdr.seq` (must exist, printable
with `%u`, `:121`/`:140`) and `ack_payload.price_sats` (must exist, accept `0`, `:130`).
Order, packing, size and all other fields are **UNDETERMINED** from this file.

---

## 4. Feature flag

All three named inputs agree with this audit: the flag is **OFF** on the pinned revision.

Declaration, `main/Kconfig.projbuild:141-148` (re-read, matches):

```
config ENABLE_TOLLGATE
    bool "Enable TollGate payment processing (Cashu e-cash over mesh)"
    default n
    depends on ENABLE_RELAY_MODE
    help
        ...
```

Guard idiom in the tree (re-run this audit): `#ifdef CONFIG_ENABLE_*` only — **49** hits in
`main/`+`components/` (`48` in `main/`, `1` in `components/`), **zero** `#if CONFIG_ENABLE_`,
and **2** compound `#if defined(...) && defined(...)` (`main/app_main.cpp:382`, `:662`).
The idiomatic form is therefore `#ifdef` / `#endif`, not `#if`.

**State of the flag — OFF on the pinned revision, and it differs on the sibling branch:**

```
$ sed -n '576p' sdkconfig                                  # feat/tracker-tx-tempcomp
# CONFIG_ENABLE_TOLLGATE is not set
$ git show autonomous/mesh-baseline:tracker/firmware/sdkconfig | sed -n '576p'
CONFIG_ENABLE_TOLLGATE=y
```

Consequences for a downstream author reading *this* report (pinned at `64b8923d`):

* On the audit revision the macro is **unset**, so the whole `#ifdef CONFIG_ENABLE_TOLLGATE`
  block in `app_task.cpp` (`:32-34`, `:114-145`) is **compiled out** — the `:120` decode call
  site is not built.
* `sdkconfig.defaults.esp32s3:83` is `CONFIG_ENABLE_TOLLGATE=y` (re-verified), but ESP-IDF
  ignores `sdkconfig.defaults*` once a `sdkconfig` exists, so the tracked `sdkconfig` governs.
* A green build proves nothing about the feature being present; verify `sdkconfig:576`
  directly.
* Build wiring: `main/CMakeLists.txt:29-31` adds `tollgate_payment_proto.c` only
  `if(CONFIG_ENABLE_TOLLGATE)`; `:27` lists the three app sources unconditionally.

---

## 5. Evidence gaps — what this file cannot decide

1. **`const` on decode param 1** — not decidable from `app_task.cpp`; permitted either way.
   Corroborated as `const` only by the shipped header.
2. **`payload` write-through** — the out-param is never dereferenced here; the NULL-init
   idiom is the only evidence. Write-through is a header/impl fact.
3. **`sizeof(tollgate_msg_hdr_t)` / `sizeof(tollgate_ack_payload_t)`** — used as opaque size
   arithmetic (`:133`, `:136`); values (8, 14) come from the header/tests, not this file.
4. **`TG_MSG_ACK` value** — referenced at `:134` only; `0x02` is a header fact.
5. **Non-`seq` header fields and the PAY payload's internal format** — the payload pointer
   is obtained at `:120` but never dereferenced, so the file constrains nothing about it.
6. **Exact error sentinel** — `:120` proves only "negative ⇒ failure".
7. **`g_rx_queue` / `g_tx_queue` definition line** — `extern`-declared at `app_task.cpp:39-40`
   and `app_main.cpp:75-76`; the defining line was not isolated in this read-only pass.
8. **Exact guard-idiom census figure** — this audit counts 49 `#ifdef CONFIG_ENABLE_*` + 2
   `#if defined(...) && defined(...)` in `main/`+`components/`. The *material* claim (zero
   `#if CONFIG_ENABLE_`; the guarded idiom is `#ifdef`) holds, but a single exact census
   number is methodology-dependent, so treat any specific count as approximate.
9. **Branch-dependent `sdkconfig`** — §4: `:576` is `not set` on `feat/tracker-tx-tempcomp`
   @ `64b8923d` and `=y` on `autonomous/mesh-baseline`. All three named inputs state
   `not set` (matching this audit); §4 records the sibling-branch difference for completeness.

---

## 6. Auditor's independent re-verification

Re-run in this audit (not trusted from the inputs):

* **Pinned revision** — `rev-parse --abbrev-ref HEAD` → `feat/tracker-tx-tempcomp`;
  `rev-parse HEAD` → `64b8923d…`. Matches all inputs.
* **Line quotes** — `sed -n 'Np'` for every cited `app_task.cpp` line (32-34, 80, 90,
  114-121, 124-130, 132-140, 142, 143, 145): **all 30 match exactly**. Also re-read every
  cited out-of-file line (`tollgate_payment_proto.h` 33/36/39-46/48-55/62-68/74/77-81/92/94-96/102-109,
  `relay_types.h` 6/12-23, `proto.c` 14-53, `Kconfig.projbuild:141-148`, `CMakeLists.txt:29-31`,
  `test_tollgate_payment_proto.c:65-66/154/289-290`, `test_relay_pipeline.c:133`,
  `app_main.cpp:78-80/575/612/625-628/649/662/670-673`): **all match**.
* **NOT-FOUND list** — every symbol search re-run; output non-empty for all ten ⇒ **genuinely
  zero NOT FOUND**. The §2 "protocol-family not referenced" search re-run ⇒ **rc=1, empty**.
* **Blob identity** — `hash-object` == `rev-parse HEAD:…` == `e2cf9aca…`; path-scoped
  `status --porcelain` empty.
* **Discrepancies found and addressed in this report:**
  1. `sdkconfig:576` differs by branch (§4). All three named inputs state `not set` for the
     pinned revision — **corroborated, not contradicted**. The `=y` figure originates in a
     sibling worktree artifact (`~/worktrees/tg-proto-contract/TOLLGATE_API_SHAPE.md`); §4
     records the difference so the two are not conflated.
  2. The guard count is methodology-dependent; the material claim (zero `#if
     CONFIG_ENABLE_`; guarded idiom is `#ifdef`) holds. Exact figure flagged in §5.8.
  3. The signature inputs present decode param-1 `const` as the safe inference; this audit
     keeps it **UNDETERMINED** from `app_task.cpp` alone (permitted, not proven) and labels
     it as such in §1.2, since the inputs' support leans on the header/callee, not this file.
* **Claims downgraded to UNDETERMINED:** decode param-1 `const`; `payload` write-through
  (§1.2).
