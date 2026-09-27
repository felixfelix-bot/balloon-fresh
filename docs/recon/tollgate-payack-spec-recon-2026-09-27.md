# TollGate PAY/ACK proto spec — findings report

**Task:** `balloon:t_4886e59b` — "Search repos and filesystem for existing tollgate PAY/ACK proto spec"
**Date:** 2026-09-27 (read-only recon; **no source files modified, no repo writes, no commits**)
**Scopes swept:** `~/repos/` (all checkouts + bare mirrors), `~/r2-work/`, `~/tollgate-artifacts/`.

---

## 0. Headline

**No upstream (non-balloon) normative PAY/ACK wire-format spec exists under the six
grepped symbol names.** All six symbols live exclusively in the balloon-fork family
(`balloon`, `e80-bench`, `balloon-e80bench` — all remote
`felixfelix-bot/balloon-fresh.git`), i.e. in our own self-authored binary protocol.

**But this question was already answered on 2026-09-14/15 and the answer is committed.**
Three prior artifacts in `~/repos/balloon` cover it; this report confirms them with a
fresh live sweep and adds the upstream spec families that they reference but did not
enumerate:

| Prior artifact | Path (branch `autonomous/mesh-baseline`) | What it establishes |
|---|---|---|
| Upstream audit | `docs/tollgate-payack-upstream-audit-2026-09-14.md` (commit `a9b9126f`) | Verdict **(b)**: only incidental references upstream; canonical definition lives in the balloon workspace |
| Six-symbol accounting | `docs/tollgate-six-symbol-grep-accounting-2026-09-14.md` (commit `b3ebd969`) | Per-symbol hit tables + counts; every real hit in the 3 balloon-family trees |
| Missed-location probe | `docs/tollgate-missed-location-probe-2026-09-15.md` | Probed bare-git/git-object blind spots + the never-searched `~/repos/tollgate` spec repo |
| Contract (rev 2) | `TOLLGATE_PROTO_CONTRACT.md` (§0.4 lineage) | Normative contract for the balloon header; records `~/repos/balloon-fresh/` does not exist |

**Verdict for this task: no upstream normative spec; only the balloon-local draft
(functional, not a mock).** A new header must be specified de novo and reconciled
against the two real upstream spec families in §4.

---

## 1. Symbol-by-symbol accounting (fresh sweep, this session)

Command shape used (GNU grep; `rg` is **not installed** on this host — verified again):

```
grep -rn --binary-files=without-match --exclude-dir=.git \
  -e tollgate_msg_hdr_t -e tollgate_ack_payload_t -e TG_MSG_PAY -e TG_MSG_ACK \
  -e tollgate_proto_encode -e tollgate_proto_decode <tree>
```

| Symbol | Hits outside balloon-family? | Verdict |
|---|---|---|
| `tollgate_msg_hdr_t` | **NO** | balloon-family only |
| `tollgate_ack_payload_t` | **NO** | balloon-family only |
| `TG_MSG_PAY` | **NO** | balloon-family only |
| `TG_MSG_ACK` | **NO** | balloon-family only |
| `tollgate_proto_encode` | **NO** | balloon-family only |
| `tollgate_proto_decode` | **NO** | balloon-family only |

Per-tree hit counts (text lines, `.git` excluded, measured this session):

| Tree | Branch / HEAD | Hits |
|---|---|---|
| `~/repos/balloon` | `autonomous/mesh-baseline` | **588** |
| `~/repos/e80-bench` | `wt/cvm-p1-tx-listener` | **256** |
| `~/repos/balloon-e80bench` | `main` | **256** |

All three are clones of the same remote (`github.com/felixfelix-bot/balloon-fresh.git`);
`balloon` is the freshest and carries the recon docs. No fourth tree anywhere on the box
has these symbols.

### Explicit "no matches" — upstream tollgate repos (all six symbols, each zero hits)

Swept this session, per repo, all six symbols:

- `~/repos/tollgate` — **OpenTollGate/tollgate**, branch `main` (the canonical *spec* repo) → **no matches**
- `~/repos/tollgate-rs` — **OpenTollGate/tollgate-rs**, branch `master` → **no matches**
- `~/repos/tollgate-module-basic-go` → **no matches**
- `~/repos/tollgate-software` → **no matches**
- `~/repos/gonuts-tollgate` → **no matches**
- `~/repos/tollgate-android` → **no matches**
- `~/repos/tollgate-installer` → **no matches**
- `~/repos/tollgate-captive-portal-site` → **no matches**
- `~/repos/tollgate-infrastructure-kit` → **no matches**
- `~/r2-work/*` (incl. `tollgate-go`, `tg-research`, `tg-t16` protocol dirs), `~/tollgate-artifacts/` → **no matches**

Bare mirrors `~/repos/mirrors/{tollgate-module-basic-go,gonuts-tollgate}.git` are mirrors
of repos already covered. `esp32-tollgate` and `awesome-tollgate` have **no checkout**
anywhere on this machine (name search, maxdepth 4; prior audit reached the same result by
unique-marker sweep — `tollgate_main.c`, `captive_portal.c`, `cvm_server.c`, … zero hits).

---

## 2. What the hits actually are (balloon-local, self-authored, NOT upstream)

Two wire-compatible copies of an 8-byte packed binary header, both authored in this fork:

### 2a. Tracker firmware — `balloon/tracker/firmware/main/tollgate_payment_proto.{h,c}`
Authored by our own commit `65a46fd1` (also present at `balloon-e80bench`).

```
Wire format (ADR-002):  [hdr(8, packed)] [payload(N)]
offset 0  version u8 | 1 type u8 | 2 seq u16 | 4 payload_len u16 | 6 reserved u16
TG_MSG_PAY=0x01, TG_MSG_ACK=0x02, TG_MSG_NACK=0x03, TG_MSG_STATUS=0x04,
TG_MSG_INFO=0x05, TG_MSG_REVOKE=0x06
```
Symbols: `tollgate_msg_hdr_t` (h:48-55), `tollgate_ack_payload_t` (h:57-74, 14 bytes
packed), `tollgate_proto_encode` (h:94 / c:14-32), `tollgate_proto_decode` (h:107 /
c:35-53).
Production call sites: `app_task.cpp:117-134` (PAY→ACK path), `app_main.cpp:612-627`
(CLI `tollgate_send_pay`).
Tests: `test/test_tollgate_payment_proto.c` (14 tests / 133 assertions),
`test/test_relay_pipeline.c`, `test/integration/test_tollgate_payack.py` (Python
**re-declares** `TG_MSG_PAY = 0x01`, `TG_MSG_ACK = 0x02` — a manual transcription, so the
header is not consumed from any shared normative artifact).

### 2b. Mesh component — `balloon/mesh-stack/tollgate/components/tollgate_balloon/`
Authored by our own commit `91707853`. Same `tollgate_msg_hdr_t` (in `tollgate_balloon.h`),
plus `tollgate_payment_proto.h` with `tollgate_ack_payload_t`, `tollgate_nack_payload_t`
(130 bytes packed), `TG_ERR_*` codes; impls in `src/`, client in
`components/tollgate_client/src/tollgate_client.c`, tests in `mesh-stack/tollgate/tests/unit/`.

### 2c. Verdict on the hits
**Functional, tested, image-linked implementations of a locally invented format — not
mocks, not stubs.** Caveats that matter for "is this normative?":
- It exists in **two divergent copies** (payload conventions differ: packed ACK struct vs
  JSON payloads) with no single normative source other than the prose contract
  `TOLLGATE_PROTO_CONTRACT.md` (rev 2) — which itself records two open deviations
  (DEF-1: `encode(NULL, len>0)` succeeds where the contract says −1; DEF-2: `decode(hdr==NULL)`
  dereferences NULL).
- Its ADR citation is misleading: `docs/adr/002-tollgate-over-fips-mesh-udp.md` decides
  *transport* (TollGate payment messages ride UDP over the FIPS mesh, not direct LR2021).
  It defines **no** header, message type, or encoding — the format lives only in code
  comments + `TOLLGATE_PROTO_CONTRACT.md`.
- One soft spot flagged by prior recon: `app_task.cpp` ACK path has
  `ack_payload.price_sats = 0; /* TODO: real price from config */` — a functional stub
  *inside* an otherwise real struct.

Path correction (consistent with the prior audit and `TOLLGATE_PROTO_CONTRACT.md` §0):
**`~/repos/balloon-fresh/` does not exist on this machine.** The task's referenced tree is
`~/repos/balloon` (branch `autonomous/mesh-baseline`); `balloon-e80bench` (branch `main`)
is the pushable clone of the same remote.

---

## 3. Where a "real" spec *does* live upstream (different shape — must be reconciled)

### 3a. OpenTollGate/tollgate — Nostr event + HTTP specs (normative)
`~/repos/tollgate`, branch `main`, remote `github.com/OpenTollGate/tollgate.git`.
This is the canonical spec home — confirmed by
`tollgate-module-basic-go/docs/protocol/README.md` ("Protocol Specs — Moved →
https://github.com/OpenTollGate/tollgate").

- `TIP-01.md` — base events: advertisement `kind=10021`; Session `kind=1022`
  (tags `p`, `device-identifier`, `allotment`, `metric`); Notice events (`kind=21023`)
  with error codes e.g. `payment-error-token-spent`, `payment-error-mint-not-accepted`.
- `TIP-02.md` — Cashu payments: `price_per_step` tags advertise `cashu <price> <unit> <mint_url> <min_steps>`;
  "the customer sends a Cashu token directly over the TollGate's supported transport(s)".
- `HTTP-01.md` — **the closest thing to a normative PAY/ACK exchange**: on accepted
  payment the gateway MUST return HTTP `200 OK` whose body is a `kind=1022` Session event
  (= ACK); on invalid payment it SHOULD return a `kind=21023` Notice event with an error
  code and MAY use `402`/`400` (= NACK).
- `HTTP-02.md` — `GET /whoami` MUST return `200 OK` with the customer `<device-identifier>`
  to be included in the payment event. Plus `HTTP-03.md`, `NOSTR-01.md`, `WIFI-01.md`.
- `README.md` — layering (Protocol TIP / Interface HTTP,NOSTR / Medium WIFI); notes the
  March 2026 restructuring to plain bearer-asset tokens.

### 3b. OpenTollGate/tollgate-rs — CBOR message protocol (normative)
`~/repos/tollgate-rs` (`master`), spec at `docs/design/core/tollgate-protocol.md`, code in
`crates/tollgate-protocol/src/{lib,message,codec}.rs`.

- Encoding: **CBOR (RFC 8949)**, integer field keys, key `0` = message type. The doc
  explicitly rejects FIPS-style fixed binary (variable-length mint URLs / product lists).
- **15 message types**: `Announce=0x00, PriceSheet=0x01, Accept=0x02, ChannelReady=0x03,
  MeteringReport=0x04, BalanceUpdate=0x05, BalanceAck=0x06, BootstrapToken=0x07,
  BootstrapAck=0x08, RolloverInit=0x09, RolloverReady=0x0A, ChannelClose=0x0B,
  CloseAck=0x0C, Reject=0x0D, Disconnect=0x0E`.
  → **no PAY, no ACK**. Functional analogue: `BootstrapToken`(0x07, raw Cashu token) →
  `BootstrapAck`(0x08, status/reason), used by `tollgate-net/src/client.rs::pay()`.
- Framing: HTTP polling `POST /tollgate/v1/exchange` (port 4747, `application/cbor`,
  **2-byte little-endian length prefix** per message) or WebSocket `GET /tollgate/v1/ws`.
  No handshake — peers authenticated out-of-band (FIPS Noise IK / WireGuard).

### 3c. Others
`gonuts-tollgate/docs/` = Cashu library/wallet API docs (no wire protocol).
`tollgate-module-basic-go` holds no spec — its `docs/protocol/README.md` is a redirect
tombstone; its payment flow is an HTTP POST of a Cashu token to `:2121/` answered by a
Nostr kind-1022 event (documented in `docs/upstream_session_manager.md`).

**→ No upstream spec anywhere defines a packed binary PAY/ACK header. The two upstream
families (Nostr-event+HTTP; CBOR channels) both differ in shape from the balloon format.**

---

## 4. Bottom line for whoever writes the header

1. Do **not** claim an upstream spec exists — it does not. The balloon 8-byte header is a
   local invention; its only normative documentation is `TOLLGATE_PROTO_CONTRACT.md` (rev 2).
2. Any new header must be **specified de novo** and explicitly reconciled against:
   `TIP-02`/`HTTP-01` (token-over-transport, 200 + kind-1022, 21023 on error) and
   `tollgate-rs` CBOR framing (2-byte LE prefix, 15 typed messages) — with a stated reason
   for diverging (the balloon's constraint is FIPS-mesh UDP over LR2021, where CBOR/HTTP
   overhead and the 4747 endpoint are not obviously available).
3. Fix-order note: the ball-balloon code's own defects DEF-1/DEF-2 (contract §§7.1) and the
   `price_sats = 0` TODO should be resolved before the header is called normative.

---

## 5. Read-only attestation & method

- **No source files modified. No repo writes, no commits, no pushes, no clones/fetches.**
  The single write is this report file (into this card's kanban workspace + the
  `~/reports/reviews/` artifact channel).
- Commands were pure reads: `grep -rn -I`, `find`, `ls`, `sed -n`, `head`, `git remote -v`,
  `git log`, `git branch`, `git status` in `balloon-e80bench` (showed only a
  pre-existing untracked `firmware/e80-stm32-bench/rx-log.csv`, untouched).
- Known method limits (inherited and re-confirmed): `rg` absent on this host; a home-wide
  sweep outside `~/repos` was **not** performed (prior attempts in the 2026-09-15 probe
  were killed by timeouts / denied by the operator) — `~/worktrees` and other home trees
  remain an unsearched blind spot. Within-scope `~/repos` coverage is complete (union pass
  over all checkouts, plus bare mirrors identified).
- Duplicate-work note: this card re-asks a question already answered by
  `docs/tollgate-payack-upstream-audit-2026-09-14.md` (commit `a9b9126f`). Consumers should
  read that committed audit + the six-symbol accounting rather than re-running this sweep.
