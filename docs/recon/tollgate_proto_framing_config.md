# Recon: relay_types.h framing + CONFIG_ENABLE_TOLLGATE guard conventions

Card: `balloon:t_96ea4fcf` (read-only recon; no code or config modified)
First written 2026-09-14; **re-verified 2026-09-27** against both published refs.

Scope: pin down the relay packet framing convention and the exact
`CONFIG_ENABLE_TOLLGATE` declaration/guard pattern so a new TollGate proto
header can match established conventions.

Provenance / lineage (2026-09-27 re-verification):

| Claim class | Verified on |
|---|---|
| relay types, framing examples, Kconfig, defaults, CMake | `origin/main` @ `c446ca9a` **and** `origin/autonomous/mesh-baseline` @ `97ac7561` — identical line numbers |
| generated `sdkconfig` flag state | **differs by lineage** — see §3/§5 |

Note on the path: the card text says `~/repos/balloon-fresh/tracker/firmware/`.
That path does not exist on this host; `~/repos/balloon` is the checkout whose
`origin` **is** `github.com/felixfelix-bot/balloon-fresh.git`. This document is
published from a worktree of that repo (see §6), so all file:line references
below are relative to the repo root, i.e. `tracker/firmware/...`.

---

## 1. Confirmed relay types (quoted lines)

Source: `tracker/firmware/main/relay_types.h` (entire file is 23 lines)

```
 6|#define RELAY_PACKET_MAX_SIZE 512
 7|#define RELAY_RX_QUEUE_LEN    8
 8|#define RELAY_TX_QUEUE_LEN    4
 9|
10|/* Packet type tags (1 byte, first byte of payload) */
11|#define RELAY_TYPE_NOSTR_EVENT  0x01
12|#define RELAY_TYPE_TOLLGATE_PAY 0x02
13|#define RELAY_TYPE_TOLLGATE_ACK 0x03
14|#define RELAY_TYPE_TELEMETRY    0x04
15|#define RELAY_TYPE_RAW          0xFF
```

**CONFIRMED:**
- `RELAY_TYPE_TOLLGATE_PAY == 0x02` — relay_types.h:12
- `RELAY_TYPE_TOLLGATE_ACK == 0x03` — relay_types.h:13

The types are `#define` constants, **not** an enum. The in-tree comment
at line 10 states the framing intent directly: *"Packet type tags
(1 byte, first byte of payload)"*.

The carrier struct that these tags travel in (`relay_types.h:18-23`):

```
18|typedef struct {
19|    uint8_t  data[RELAY_PACKET_MAX_SIZE];
20|    size_t   len;
21|    uint32_t timestamp;
22|    int      rssi;
23|} relay_packet_t;
```

Note: `len` counts the type-tag byte as part of the packet (see evidence
below: `len = payload_len + 1`).

## 2. Framing rule + concrete example

### The rule (explicit)

In a `relay_packet_t` handed between `radio_task` and `app_task` via the
FreeRTOS queues:

```
byte[0]   = relay type tag (one of RELAY_TYPE_*, e.g. 0x02 PAY / 0x03 ACK)
byte[1..] = payload
len       = 1 (tag) + payload_len
```

### Proof 1 — RX dispatch reads `data[0]`, payload starts at `data + 1`

`tracker/firmware/main/app_task.cpp:90-100`:

```
 90|        uint8_t pkt_type = (pkt.len > 0) ? pkt.data[0] : RELAY_TYPE_RAW;
 92|        switch (pkt_type) {
...
100|            if (nostr_event_deserialize(&event, pkt.data + 1, pkt.len - 1) > 0) {
```

- Line 90: type is read from **byte 0** (with a zero-length guard falling
  back to `RELAY_TYPE_RAW`).
- Line 100: payload is deserialized from **`data + 1`** with length
  **`len - 1`** — the tag byte is stripped before payload parsing.

### Proof 2 — TX writers set the tag at `[0]`, payload at `+1`, len includes tag

TollGate PAY builder, `tracker/firmware/main/app_main.cpp:622` (see also the
documented format comment at `app_main.cpp:580-582`):

```
580| * Wire format in the relay packet:
581| *   data[0]    = RELAY_TYPE_TOLLGATE_PAY (0x02)
582| *   data[1..]  = tollgate_proto_encode(TG_MSG_PAY, seq, payload, len)
...
622|    pkt.data[0] = RELAY_TYPE_TOLLGATE_PAY;
```

TollGate ACK builder (RX side replying), `tracker/firmware/main/app_task.cpp:126-139`:

```
126|                ack_pkt.data[0] = RELAY_TYPE_TOLLGATE_ACK;
...
132|                int ack_len = tollgate_proto_encode(ack_pkt.data + 1,
133|                                                     RELAY_PACKET_MAX_SIZE - 1,
...
138|                    ack_pkt.len = ack_len + 1;
```

- `data[0]` = tag; encoder writes payload at `data + 1`; final `len` =
  payload bytes **+ 1** for the tag.

Telemetry (a third, comparable packet type), `tracker/firmware/main/app_main.cpp:839-841`:

```
839|        tx_pkt.data[0] = RELAY_TYPE_TELEMETRY;
840|        telemetry_serialize(&tpkt, tx_pkt.data + 1);
841|        tx_pkt.len = TELEMETRY_SIZE + 1;
```

Nostr event (fourth type), `tracker/firmware/main/app_main.cpp:447-452`:

```
447|    /* Serialize into relay packet (skip type tag byte at [0]) */
450|    pkt.data[0] = RELAY_TYPE_NOSTR_EVENT;
452|    uint16_t slen = nostr_event_serialize(&evt, pkt.data + 1, ...
```

Four independent packet types (NOSTR_EVENT, TOLLGATE_PAY/ACK, TELEMETRY) all
follow the same construction: tag at `[0]`, payload at `[1..]`, `len`
inclusive of the tag. The rule is uniform.

### Consequence for a new TollGate proto header

The proto header should define only the *payload* codec (what goes in
`data[1..]`); the relay type tag stays in `relay_types.h` and is prepended
by the caller. This is exactly how the existing
`tollgate_payment_proto.h` is structured — its own doc comment
(`main/tollgate_payment_proto.h:18-19`):

```
18| * In the relay pipeline, this message is preceded by a 1-byte relay
19| * type tag (RELAY_TYPE_TOLLGATE_PAY or RELAY_TYPE_TOLLGATE_ACK).
```

## 3. CONFIG_ENABLE_TOLLGATE — declaration + guard pattern

### Where the flag is declared (Kconfig)

`tracker/firmware/main/Kconfig.projbuild:141-148`:

```
141|config ENABLE_TOLLGATE
142|    bool "Enable TollGate payment processing (Cashu e-cash over mesh)"
143|    default n
144|    depends on ENABLE_RELAY_MODE
145|    help
146|        Enable TollGate payment handling in app_task. Decodes PAY
147|        messages from ground stations, validates Cashu tokens, and sends ACK
148|        responses with session info. Requires relay mode for continuous RX.
```

- Naming: Kconfig symbol is `ENABLE_TOLLGATE` (no `CONFIG_` prefix in
  Kconfig); the `CONFIG_` prefix is added by Kconfig itself.
- `default n` — off unless turned on in `sdkconfig.defaults*`.
- `depends on ENABLE_RELAY_MODE` (which in turn `select`s ENABLE_MESH and
  ENABLE_NOSTR_STORE, Kconfig.projbuild:131-139).

### Where the flag is set (sdkconfig)

`tracker/firmware/sdkconfig.defaults.esp32s3:82-83`:

```
82|# ── TollGate payment processing (relay mode required, already set above) ──
83|CONFIG_ENABLE_TOLLGATE=y
```

Generated `tracker/firmware/sdkconfig:576`. **This line differs by lineage** —
quote both, because the same `defaults` line yields two different checked-in
states:

`origin/autonomous/mesh-baseline` @ `97ac7561` (flag ON):

```
573|CONFIG_ENABLE_MESH=y
574|# CONFIG_ENABLE_TDMA is not set
575|CONFIG_ENABLE_RELAY_MODE=y
576|CONFIG_ENABLE_TOLLGATE=y
577|CONFIG_ENABLE_NOSTR_STORE=y
578|# CONFIG_ENABLE_MESHCORE is not set
```

`origin/main` @ `c446ca9a` (flag tracked as OFF in the generated file):

```
576|# CONFIG_ENABLE_TOLLGATE is not set
```

On `origin/main` the feature is therefore compiled out at that head even though
`sdkconfig.defaults.esp32s3:83` requests `=y`; the defaults are re-applied on the
next `idf.py` (re)configure. See §5 for the status statement.

Materialized for the C preprocessor in `tracker/firmware/build/config/sdkconfig.h`:

```
# define CONFIG_ENABLE_TOLLGATE 1   (generated; line 441 on the 2026-09-14 build)
```

`build/config/sdkconfig.h` is **generated and untracked** (not present in a
fresh worktree — `git ls-tree origin/main` has no `build/config/` entry), so
its line number is only reproducible after a local build. The tracked sources
of truth are `Kconfig.projbuild` + `sdkconfig.defaults.esp32s3` + `sdkconfig`.

### The guard pattern (all sites)

The project convention is `#ifdef CONFIG_ENABLE_TOLLGATE` ...
`#endif`, optionally with a trailing comment. Five distinct usage shapes:

**a) Gated `#include` of the proto header** — `app_task.cpp:32-34`:

```
32|#ifdef CONFIG_ENABLE_TOLLGATE
33|#include "tollgate_payment_proto.h"
34|#endif
```

Identical at `app_main.cpp:78-80`. Note: the header itself is **not**
internally wrapped in the flag — gating happens at the include site and
around call sites, keeping the header self-contained and testable on host.

**b) Gated `switch` case block** — `app_task.cpp:114-145` (case +
body inside guard; trailing `#endif` comment):

```
114|#ifdef CONFIG_ENABLE_TOLLGATE
115|        case RELAY_TYPE_TOLLGATE_PAY: {
...
145|#endif /* CONFIG_ENABLE_TOLLGATE */
```

**c) Gated function definition** — `app_main.cpp:575` ... `649`:

```
575|#ifdef CONFIG_ENABLE_TOLLGATE
576|/*
577| * tollgate_send_pay — encode a TollGate PAY message and queue it for
...
649|#endif /* CONFIG_ENABLE_TOLLGATE */
```

**d) Gated CLI registration** — `app_main.cpp:670-673`:

```
670|#ifdef CONFIG_ENABLE_TOLLGATE
671|    cli_register_command("tollgate_send_pay", "Send TollGate PAY message (optional token arg)",
672|                          cli_cmd_tollgate_send_pay);
673|#endif
```

**e) Gated CMake source registration** — `main/CMakeLists.txt:29-31`:

```
29|if(CONFIG_ENABLE_TOLLGATE)
30|    list(APPEND APP_SRCS "tollgate_payment_proto.c")
31|endif()
```

(Compare `if(CONFIG_ENABLE_NOSTR_STORE)` / `if(CONFIG_ENABLE_MESHCORE)` at
CMakeLists.txt:14-16, 22-25 — CMake gets the same symbol name as a plain
`if()` variable, no `CONFIG_` gymnastics needed.)

### `#endif` comment style

Both styles occur: annotated `#endif /* CONFIG_ENABLE_TOLLGATE */`
(app_task.cpp:145, app_main.cpp:649) and bare `#endif` (app_task.cpp:34,
app_main.cpp:673). The annotated form is preferred for long/compound
blocks; bare is fine for short ones. For a two-flag compound guard, the
`#if defined(A) && defined(B)` form is used (app_main.cpp:662-664).

## 4. Comparison with other CONFIG_ENABLE_* flags

Declaration sites (all in `main/Kconfig.projbuild`, bool type,
`config ENABLE_<FEATURE>` naming; all `default n` except ENABLE_BMP280
which is `default y`):

| Flag | Kconfig.projbuild | default | depends/selects | Used by (C/C++) |
|------|-------------------|---------|----------------|-----------------|
| ENABLE_BMP280 | :1 | **y** | — | app_main.cpp:42,100,211 |
| ENABLE_GPS | :8 | n | — | app_main.cpp:45,104,243 |
| ENABLE_FEM | :31 | n | — | app_main.cpp:49,217 |
| ENABLE_ANTENNA_SWITCH | :48 | n | — | app_main.cpp:52 |
| ENABLE_MESH | :116 | n | — | app_main.cpp:56,111,139 |
| ENABLE_TDMA | :123 | n | depends ENABLE_MESH | app_main.cpp:60 |
| ENABLE_RELAY_MODE | :131 | n | select MESH, NOSTR_STORE | app_main.cpp:69 |
| ENABLE_TOLLGATE | :141 | n | depends ENABLE_RELAY_MODE | app_task.cpp:32,114; app_main.cpp:78,575,670 |
| ENABLE_NOSTR_STORE | :150 | n | depends ENABLE_MESH | app_task.cpp:25,42,64,93; app_main.cpp:63,666 |
| ENABLE_MESHCORE | :158 | n | — | app_main.cpp:26 |

(All `config ENABLE_*` declarations verified via grep; sensor flags BMP280/
GPS/FEM/ANTENNA_SWITCH occupy lines 1-48 of Kconfig.projbuild, networking
flags lines 116-165.)

Defaults live in `sdkconfig.defaults.esp32s3` (lines 59-83), grouped under
`# ── section comment ──` headers:

```
59|# ── Mesh networking (same as C3 baseline) ──
60|CONFIG_ENABLE_MESH=y
...
64|CONFIG_ENABLE_RELAY_MODE=y
...
71|CONFIG_ENABLE_BMP280=y
74|# CONFIG_ENABLE_GPS is not set
77|# CONFIG_ENABLE_FEM is not set
80|# CONFIG_ENABLE_ANTENNA_SWITCH is not set
...
83|CONFIG_ENABLE_TOLLGATE=y
```

Conventions distilled:

1. **Naming:** Kconfig `ENABLE_<FEATURE>` → C `CONFIG_ENABLE_<FEATURE>`.
   Always verbs-first with `ENABLE_`; no `USE_`, no `_SUPPORT` suffix.
2. **Guard macro style:** universally `#ifdef CONFIG_ENABLE_X` (never
   `#if CONFIG_ENABLE_X` and never `#ifndef` as a feature-on test).
   sdkconfig materializes enabled flags as `#define CONFIG_ENABLE_X 1`,
   so `#ifdef` is the reliable truth test.
3. **Where flags live:** declaration in `main/Kconfig.projbuild`; defaults
   in `sdkconfig.defaults.esp32s3` (per-target) with an optional copy in
   `sdkconfig.defaults`; runtime state in generated `sdkconfig`/`build/config/sdkconfig.h`.
4. **Disabled convention:** a flag that is present but off appears as the
   literal comment line `# CONFIG_ENABLE_GPS is not set` (sdkconfig line 574
   style) — it is not deleted from the file.
5. **Header self-containment:** feature headers (e.g. `tollgate_payment_proto.h`)
   are NOT internally `#ifdef`-gated; the guard wraps the `#include` and the
   call sites. Host unit tests can then include the header without ESP-IDF
   config.
6. **CMake registration:** `if(CONFIG_ENABLE_X) list(APPEND ... SRCS) endif()`
   in `main/CMakeLists.txt` mirrors the Kconfig symbol 1:1.

## 5. Status summary

**`CONFIG_ENABLE_TOLLGATE` EXISTS (declared in Kconfig) and is REQUESTED ENABLED
in the per-target defaults. It does NOT need to be added and is NOT commented
out in `sdkconfig.defaults.esp32s3`. The only caveat is the checked-in generated
`sdkconfig`, whose state differs per lineage:**

- Declared: `main/Kconfig.projbuild:141-148` (`bool`, `default n`,
  `depends on ENABLE_RELAY_MODE`) — present on **both** lineages.
- Requested enabled in defaults: `sdkconfig.defaults.esp32s3:83` →
  `CONFIG_ENABLE_TOLLGATE=y` — present on **both** lineages (not commented out).
- Generated `sdkconfig:576`, dependency `CONFIG_ENABLE_RELAY_MODE=y` at `:575`
  is set on both lineages, so the `depends on` is satisfied everywhere:
  - `origin/autonomous/mesh-baseline` @ `97ac7561`: `CONFIG_ENABLE_TOLLGATE=y`
    → **enabled**, code compiled in (this is the branch the card names).
  - `origin/main` @ `c446ca9a`: `# CONFIG_ENABLE_TOLLGATE is not set`
    → **disabled in the checked-in generated file** at that head; the tollgate
    code is compiled out until the next `idf.py` reconfigure re-applies
    `sdkconfig.defaults.esp32s3`. (Where the flag is on, CPP sees
    `#define CONFIG_ENABLE_TOLLGATE 1`, which is why `#ifdef` — not `#if` — is
    the guard style used everywhere.)
- Same-repo evidence that this lineage split is known: the sibling recon card
  `balloon:t_c360db44` (GLM cold review, F1) independently recorded that the
  flag is `is not set` on the published lineage.

Therefore a new TollGate proto header should:

- Use tag values `RELAY_TYPE_TOLLGATE_PAY` (0x02) / `RELAY_TYPE_TOLLGATE_ACK`
  (0x03) from `relay_types.h` for the relay-level framing byte; encode only
  the payload (starting at `data[1]`), with `len = payload_len + 1`.
- Follow `tollgate_payment_proto.h` header style: classic include guard
  (`#ifndef X_H` / `#define X_H` / `#endif /* X_H */`), `extern "C"`
  wrapper, `__attribute__((packed))` wire structs. (Note: `relay_types.h`
  uses `#pragma once`, but the newer proto header uses classic guards —
  mirror the proto header for a new protocol header consumed from both
  .c and .cpp.)
- Expect consumers to gate with `#ifdef CONFIG_ENABLE_TOLLGATE ... #endif`
  around `#include` and call sites; register any new `.c` under
  `if(CONFIG_ENABLE_TOLLGATE)` in `main/CMakeLists.txt`.
- NOT redeclare or re-`#define` the flag anywhere — it flows exclusively
  Kconfig → sdkconfig.defaults → sdkconfig → sdkconfig.h.

---

## 6. Verification + publication record

- 2026-09-14: first pass; written read-only, no source/config/build file touched.
- 2026-09-27 (card `balloon:t_96ea4fcf`): every cited file:line in §1–§4
  re-checked on `origin/main` @ `c446ca9a` (fresh worktree
  `~/worktrees/t96-framing`) and, for the framing/Kconfig claims, on
  `origin/autonomous/mesh-baseline` @ `97ac7561`. All §1–§4 citations resolve to
  the same content on both refs; the only lineage-dependent line is
  `sdkconfig:576`, now documented in §3/§5.
- Changed by this card: this document only (`docs/recon/`). No code, config,
  firmware or build file was modified — the card is read-only recon.

*Recon verified read-only: `git status` in the publishing worktree shows only
this new untracked `docs/recon/tollgate_proto_framing_config.md`.*