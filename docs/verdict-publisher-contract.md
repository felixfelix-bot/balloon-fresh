# Verdict Publisher — Frozen Interface Contract (E80 range-sync via CVM)

**Status:** FROZEN (reconnaissance deliverable, no code)
**Date:** 2026-10-09
**Task:** `t_c589f7e6` (board `e80-bench`)
**Scope repo:** `firmware/e80-stm32-bench` (analysis/message layer only; no hardware)

This document is the frozen interface contract the rest of the phase-1
decomposition (Gate1 tests, publisher wiring, consolidation) depends on. Every
field below is traceable to a quoted source line. **Nothing here is invented**;
where a source is silent it is called out explicitly in §8.

## 0. Sources and pins

| Source | Path | Git object (blob) | Tip |
|---|---|---|---|
| Gap check / verdict text | `firmware/e80-stm32-bench/tools/range_check.py` | `26f6e162` | `origin/main` `ce491f93` |
| ADR (message layer) | `docs/ADR-range-sync-cvm.md` | `5c2c211d` | `origin/main` `ce491f93` |
| Transport (reused) | `firmware/e80-stm32-bench/tools/cvm_board_server.py` | `61a0968c` | `origin/main` `ce491f93` |
| P1 message layer | `firmware/e80-stm32-bench/tools/cvm_sync.py` | `1eeb269d` | `origin/main` `ce491f93` |
| VERDICT publisher (impl) | `firmware/e80-stm32-bench/tools/cvm_verdict_publisher.py` | `e624445e` | `a353fd98` (**NOT merged** to `origin/main`) |
| ARMED publisher (impl) | `firmware/e80-stm32-bench/tools/cvm_armed_publisher.py` | `8aa45e89` | `a353fd98` (**NOT merged**) |
| VERDICT tests (impl) | `firmware/e80-stm32-bench/tools/test_cvm_verdict_publisher.py` | `1faadeb9` | `a353fd98` (**NOT merged**) |

`origin/main` tip at time of writing: `ce491f93`.

> **Path convention.** The card header says "Repo: firmware/e80-stm32-bench",
> but its own item 2 names `docs/ADR-range-sync-cvm.md`, which lives at the
> **repo root** (`~/repos/balloon-e80bench/docs/`), not under the sub-project.
> This contract therefore lives beside the ADR it must stay consistent with:
> `docs/verdict-publisher-contract.md`. If a reviewer prefers the sub-project
> `firmware/e80-stm32-bench/docs/`, move the file — no content changes.

> **Merge state.** The phase-1 *message layer* (`cvm_sync.py`,
> `docs/ADR-range-sync-cvm.md`) is on `origin/main`. The VERDICT/ARMED
> *publisher* implementations (`cvm_verdict_publisher.py`,
> `cvm_armed_publisher.py`) are only on local/remote branches
> (`wt/t_49192514-verdict`, `feat/cvm-tx-listener`, `pr/e80-cvm-p1-phase1`).
> This contract describes the schema the **tests must pin**, whether asserted
> against the branch implementation now or after consolidation.

---

## 1. `range_check.py` — per-config result shape

### 1.1 Status enum (exactly three values)

`range_check.py:644-649` — the ONLY place a status is minted:

```python
if n_recv == 0:
    status = "MISS"
elif n_recv < thin_frac * n_pkts:
    status = "THIN"
else:
    status = "OK"
```

The docstring pins the same three values and their thresholds
(`range_check.py:620-623`):

```
Returns {config_idx: {"n_pkts": expected, "n_recv": best-pass count,
                      "per_replicate": {rep: count}, "status": ...}}
where status is "OK" (n_recv >= thin_frac*n_pkts), "THIN"
(0 < n_recv < thin_frac*n_pkts) or "MISS" (n_recv == 0).
```

- `thin_frac` default `DEFAULT_THIN_FRAC = 0.5` (`range_check.py:77`).
- Threshold is `>=` for OK and `<` for THIN (strict), `==` 0 for MISS.
- Counting is **best single surviving replicate**, never pooled
  (`range_check.py:642`: `n_recv = max(per_rep.values()) if per_rep else 0`),
  with the conditional warmup rule (`range_check.py:633-641`).

**Enum is exactly `{"OK", "THIN", "MISS"}` — no other value exists.** The
publisher refuses anything else (`cvm_verdict_publisher.py:160-164`).

### 1.2 Analysis-internal dict vs. emitted per-config row

Two different dicts exist; the contract uses the **emitted row**:

- `analyze_capture()` returns `{idx: {"n_pkts", "n_recv", "per_replicate", "status"}}`
  (`range_check.py:650-651`).
- `main()` flattens it into the operator-facing **results row**
  (`range_check.py:926-930`):

```python
results = [{"idx": int(c["idx"]), "label": c["label"],
            "n_pkts": per_cfg[int(c["idx"])]["n_pkts"],
            "counted": per_cfg[int(c["idx"])]["n_recv"],
            "status": per_cfg[int(c["idx"])]["status"]}
           for c in cfgs]
```

So the row shape is **`{idx:int, label:str, n_pkts:int, counted:int, status:str}`**
(`n_recv` is renamed to `counted` on the way out — this rename is the classic
transcription error; the verdict wire shape uses `counted`).

### 1.3 Verdict one-liner (the summary string)

`range_check.py:700-719` `verdict_line(dist, session, results, kind)` emits one
operator line; `kind ∈ {"PASS", "GAPS", "LOGGING_GAP"}`:

- `LOGGING_GAP` → `"<dist> s<session>: LOGGING GAP (0 STAT rows for session — rx logger problem, not RF; no resend file)"` (`:703-705`)
- `PASS` → `"<dist> s<session>: PASS (<clean>/<total> clean)"` (`:708-709`)
- `GAPS` → `"<dist> s<session>: GAPS c<i>:THIN <counted>/<n_pkts> c<j>:MISS (<clean>/<total> clean)"` (`:710-719`)

The publisher **reuses this function verbatim** as the message `summary`
(`cvm_verdict_publisher.py:197-199`) so wire text and terminal cannot drift.

### 1.4 Exit codes

`range_check.py:947-950` (COMPLETE→`return 0`), `:952-980` (GAPS→`return 1`),
`:915-921` (LOGGING GAP→`return 1`), `:827-831` (missing preset / usage→`return 2`).

| Code | Meaning |
|---|---|
| 0 | COMPLETE — all configs OK, no re-send needed |
| 1 | GAPS, or LOGGING GAP (logger failure; not RF) |
| 2 | usage / missing preset / stop mismatch / session mismatch |

### 1.5 `resend-<stop>.json` artifacts — produced on GAPS only, TWO names

A resend artifact is written **only when at least one config is non-OK**
(`build_resend_preset` returns `None` when all OK, `range_check.py:728-730`).
Two forms are written on the same run (`range_check.py:954-971`):

| Form | Writer | Path (relative to repo root) | `name` field |
|---|---|---|---|
| v1 (renumbered) | `write_resend_preset` (`:741-763`) | `configs/resend-<DIST>-s<SESSION>.json` | `resend-<dist>-s<session>` (`:751`) |
| v2 (idx-preserved; default out-dir) | inline in `main` (`:963-969`) | `configs/resend/resend-<dist>-<session>.json` (`--out-dir` default `configs/resend`, `:964-966`) | `resend-<dist>-<session>` (`:733`) |

- v1 keeps labels only; v2 keeps **explicit `idx`** matching the original preset
  (`:731-738`). The message inlines the resend JSON **verbatim** — see §2.
- On a full PASS (no gaps) **neither file is written**; on LOGGING GAP **no
  resend file exists at all** (`range_check.py:9-11`, `:703-705`).
- Artifact name in the card/ADR prose: `resend-<stop>.json` — in code `<stop>`
  is the **dist** (`50m`) and the file additionally carries the session.

### 1.6 `--json` does NOT exist on `range_check.py` (finding)

`range_check.py` argparse exposes exactly (`range_check.py:797-819`):
`--dist --session --rx-log --tx-log --configs --thin-frac --out-dir --repo-root`.
**There is no `--json` / machine-readable emitter.** The `--json` hits in
`tools/` belong to unrelated tools (`tools/cvm_relay_test.py:144`,
`tools/e80_detect.py:717`). The publisher docstring's example invocation
`python3 range_check.py --dist 50m --session … --json > out.json`
(`cvm_verdict_publisher.py:54`) is therefore **aspirational** — see §8 gap G1.

The publisher's `--results` ingest accepts a **bare list** of rows, or an
object with `results`/`per_config` + optional `resend_json`/`stat_count`
metadata (`cvm_verdict_publisher.py:350-373`). Until G1 is closed, that file
must be assembled by hand from `range_check` output.

### 1.7 Real example output (executed, not fabricated)

No field rx-log exists in the repo tree, so this was produced by building an
rx-log **with the repo's own formatters**
(`e80_bench_ctl.format_pkt_line` / `format_stat_line`) and running the real
`tools/range_check.py` against the real `configs/per-stop/stop-50m.json`
(4 configs; cfg0 10/10, cfg1 3/10, cfg2 0/10, cfg3 10/10, replicate 1):

```
session: 2609130435a3f (explicit)

50m: GAPS c1 THIN 3/10, c2 MISS

per-config (best pass):
  c0  SF7-125k-64B            10/10  OK
  c1  SF8-125k-64B             3/10  THIN
  c2  SF12-125k-64B            0/10  MISS
  c3  FLRC-1.5M-64B           10/10  OK

log: /tmp/rc_demo/repo/rx-log.csv
50m s2609130435a3f: GAPS c1:THIN 3/10 c2:MISS (2/4 clean)
resend: configs/resend-50m-s2609130435a3f.json (labels: SF8-125k-64B, SF12-125k-64B)
TX: make range-tx CONFIGS=configs/resend-50m-s2609130435a3f.json T0=+90 PROBE=... PORT=<from detect>
resend (idx preserved): configs/resend/resend-50m-2609130435a3f.json

Paste-ready selective re-send (T0=1791504900 session=2610090015):
  TX: make range-tx DIST=50m CONFIGS=configs/resend/resend-50m-2609130435a3f.json T0=1791504900 SESSION_ID=2610090015   # run FIRST, banner prints instantly
  RX: make range-rx DIST=50m CONFIGS=configs/resend/resend-50m-2609130435a3f.json T0=1791504900 SESSION_ID=2610090015   # arm BEFORE T0
### exit code: 1
```

The summary line `50m s2609130435a3f: GAPS c1:THIN 3/10 c2:MISS (2/4 clean)`
is exactly what the publisher puts in the `summary` field (§2).

---

## 2. Config-end VERDICT payload — JSON schema

One **VERDICT** message per completed config scan (one per stop). Inner event
content is JSON; the outer Nostr event is the NIP-59 kind-1059 gift wrap
(§5). Constructed by `cvm_verdict_publisher.build_verdict`
(`cvm_verdict_publisher.py:175-213`); the P1 seam `cvm_sync.VerdictPublisher`
(`cvm_sync.py:312-340`) carries the same field set minus `log_gap`/`stat_count`
— the production builder is authoritative.

```json
{
  "type":       "VERDICT",
  "session_id": "2609130435a3f",
  "stop":       "50m",
  "summary":    "50m s2609130435a3f: GAPS c1:THIN 3/10 c2:MISS (2/4 clean)",
  "per_config": [
    {"idx": 0, "label": "SF7-125k-64B", "n_pkts": 10, "counted": 10, "status": "OK"},
    {"idx": 1, "label": "SF8-125k-64B", "n_pkts": 10, "counted": 3,  "status": "THIN"},
    {"idx": 2, "label": "SF12-125k-64B","n_pkts": 10, "counted": 0,  "status": "MISS"}
  ],
  "resend_json": { "name": "resend-50m-2609130435a3f", "configs": [ … ] },
  "log_gap":    false,
  "stat_count": 4,
  "created_at": 1789148009,
  "author":     "<hex pubkey>"
}
```

### Field table (type · required · source line)

| Field | Type | Required | Source line |
|---|---|---|---|
| `type` | `"VERDICT"` (literal) | yes | `cvm_verdict_publisher.py:100` (`VERDICT_TYPE`), `:201` |
| `session_id` | str, `^\d{10}[0-9a-f]{3}$` | yes | `:202`; regex `cvm_armed_publisher.py:73` |
| `stop` | str, non-empty, not `"?"` | yes | `:203`; guard `:190-191` |
| `summary` | str (from `range_check.verdict_line`) | yes | `:197-199` |
| `per_config` | array of row objects | yes | `:205`; rows `:165-171` |
| `resend_json` | object or `null` (inline verbatim) | yes (may be null) | `:206-208` |
| `log_gap` | bool | yes | `:209` |
| `stat_count` | int ≥ 0 | yes | `:210` |
| `created_at` | int (epoch seconds) | yes | `:211` |
| `author` | str (hex pubkey, may be `""`) | yes | `:212` |

`VERDICT_REQUIRED` (validated, `:106-109`):
`("type", "session_id", "stop", "summary", "per_config", "resend_json", "created_at")`.
`log_gap`/`stat_count`/`author` are emitted by the builder but are **not** in
the required tuple — they are additive, and `validate_verdict` (`:216-248`)
does not reject their absence. A Gate1 test MUST pin the emitted key set
explicitly (see §7, case P6) so this looseness cannot drift.

`per_config` row (`:165-171`):
`{"idx": int ≥ 0, "label": str (default "?"), "n_pkts": int ≥ 0, "counted": int ≥ 0, "status": "OK"|"THIN"|"MISS"}`.
Unknown status → `VerdictError` (`:160-164`); negative/bool counts → refused
(`_nonneg_int`, `:132-144`). `idx`/`label`/`n_pkts`/`counted` map 1:1 onto the
`range_check` results row of §1.2 (`counted` == its `n_recv`).

### `log_gap` semantics (LOGGING-GAP variant)

`log_gap = (len(per_config) == 0)` (`:193`). When true:
`per_config == []`, `summary` is the LOGGING-GAP text
(`rc.verdict_line(stop, session_id, [], "LOGGING_GAP")`, `:197`), and
`resend_json` is normally `null` (no resend file — §1.5).
`validate_verdict` enforces the invariant "log_gap ⇒ no per_config rows"
(`:232-233`).

### `summary` kind selection (builder)

`kind = "PASS" if (per_config and all(status == "OK")) else "GAPS"`
(`:194-195`); `log_gap` overrides to the LOGGING-GAP text. Matches
`range_check`'s own selection.

---

## 3. Session linkage fields (exact list)

**The verdict→ARMED linkage is exactly two fields: `session_id` and `stop`.**

`cvm_verdict_publisher.py:112`:
```python
#: Fields that correlate a verdict back to the phase-1 ARMED session.
LINK_FIELDS = ("session_id", "stop")
```

Checked by `validate_session_link(verdict, armed)` (`:251-275`):
- `session_id` string-equality between verdict and ARMED (`:265-267`), and
- `stop` string-equality between verdict and ARMED (`:272-274`);
- missing either → refused (`:263-264`, `:270-271`).
CLI cross-checks against a pinned `armed.json` before publishing: mismatch →
exit 2 (`:438-444`, error class `VerdictError` → `:487-490`).

`session_id` format is RX-authored (`%y%m%d%H%M` + 3-hex nonce,
`cvm_sync.py:89-99`), regex `^\d{10}[0-9a-f]{3}$`
(`cvm_armed_publisher.py:73`, `validate_session_id` `:118-121`). RX is the
**sole session authority** (ADR §2.1, `docs/ADR-range-sync-cvm.md:39-45`).

**For contrast, the ARMED side carries five required fields**
(`cvm_sync.py:82`): `ARMED_REQUIRED = ("session_id", "stop", "t_ready_utc", "preset_hash", "seq")`
plus `type`, `created_at`, `author` (`cvm_armed_publisher.py:98`). Only
`session_id` + `stop` are copied onto the VERDICT as linkage — the other three
are ARMED-internal. This is the exact answer to the card's "session_id plus the
stop linkage field(s)": **`stop`, and nothing else.**

ADR status: §2.1 (`:49-56`) lists the ARMED fields (`session_id`, `stop`,
`t_ready_utc`, `preset_hash`, `seq`) but **does not name the linkage fields
explicitly** — linkage is only implied by `session_id`+`stop` appearing in
both message shapes. The concrete two-field list is pinned by
`LINK_FIELDS`/`validate_session_link` in the implementation, and by the ADR
§2.5 "one verdict per stop" wording (`:85-90`). This is recorded here as the
proposed-and-frozen minimal set; it is what the branch code implements.

---

## 4. Relay failover set and order

**Authoritative order (the list the publisher actually connects to)** —
`cvm_armed_publisher.py:89-96`, consumed unchanged by the verdict publisher
(`cvm_verdict_publisher.py:82-95` re-exports `failover_relays`; used at `:457`):

```python
FAILOVER_RELAYS = [
    "wss://nostr.mom",
    "wss://relay.primal.net",
    "wss://nos.lol",
    "wss://relay2.contextvm.org",
    "wss://relay.nostr.band",
]
DEAD_RELAYS = ("wss://relay.contextvm.org",)
```

Order: **`nostr.mom` → `relay.primal.net` → `nos.lol` → `relay2.contextvm.org`
→ `relay.nostr.band`**. `failover_relays(extra)` preserves this order, then
appends extras, filtering `DEAD_RELAYS` and duplicates
(`cvm_armed_publisher.py:242-252`).

Two same-set / different-order copies also exist and MUST be treated as the
same *set* (not order):
- `cvm_sync.py:59-65` `DEFAULT_RELAYS` — **`relay.primal.net` first**, then
  `nostr.mom`, `nos.lol`, `relay2.contextvm.org`, `relay.nostr.band`.
- `cvm_board_server.py:63-68` `DEFAULT_RELAYS` — same order as `cvm_sync`.

ADR §2.3 (`docs/ADR-range-sync-cvm.md:76-77`) lists, in this order:
`nostr.mom`, `relay.primal.net`, `nos.lol`, `relay2.contextvm.org`,
`relay.nostr.band` — i.e. **matching `FAILOVER_RELAYS`**, not the
`cvm_sync`/`cvm_board_server` ordering. The card's item 3 quotes the same
ADR/mom-first order. Gate1 asserts the **mom-first** order for the publisher.

### `relay.contextvm.org` — "DEAD" claim is FALSIFIED (liveness finding)

The ADR (`:76-77`), `cvm_sync.py:58`, `cvm_armed_publisher.py:88` and
`cvm_board_server` all annotate `relay.contextvm.org` as **DEAD** and exclude it;
`cvm_armed_publisher.DEAD_RELAYS` filters it even if supplied, and a Gate1 test
asserts it is never returned (`test_cvm_verdict_publisher.py:546-549`).

However, a **liveness probe from CobradorWave on 2026-10-09 shows it is UP**:

```
getent hosts relay.contextvm.org   -> 51.68.216.210
curl -H 'Accept: application/nostr+json' https://relay.contextvm.org/
  -> HTTP 200, NIP-11:
     {"description":"A strfry relay running at relay.contextvm.org",
      "name":"strfry relay at relay.contextvm.org","negentropy":1,
      "pubkey":"6b3780ef2972e73d370b84a3e51e7aa9ae34bf412938dcfbd9c5f63b221416c8", …}
WS upgrade (Connection: Upgrade / Upgrade: websocket) -> HTTP 200 (switching protocols)
```

**Conclusion:** the card's premise "Confirm relay.contextvm.org is dead and
excluded" is **half true**. *Excluded*: yes, hardcoded in `DEAD_RELAYS` and
filtered by `failover_relays`. *Dead*: **no** — it serves NIP-11 and accepts a
WebSocket upgrade from the router host. Do **not** cite "DEAD" as a live fact;
it is a stale design-time annotation. The code exclusion stands as a deliberate
policy (redundancy/avoid single-vendor relay), and Gate1 tests must keep
asserting the exclusion — just not the liveness claim. Re-probing from the TX
laptop (DQ05) is a field-ops question, not a contract change.

---

## 5. Key-source rule (env only) and gift-wrap / no-plaintext rule

### 5.1 Keys: env vars only, never a CLI arg; client ≠ server

ADR §2.3 (`docs/ADR-range-sync-cvm.md:78`):
> `- Keys via **env var, never CLI arg**. Client/server keys **must differ**.`

Implemented in `cvm_armed_publisher.py` and reused verbatim by the verdict
publisher (`cvm_verdict_publisher.py:82-95` imports the helpers; tests assert
identity — `test_cvm_verdict_publisher.py:493-499`):

- Env names (`cvm_armed_publisher.py:80-86`):
  `CVM_RX_NSEC`, `CVM_RX_HEX`, alias `CVM_CLIENT_NSEC`, `CVM_CLIENT_HEX`
  (client/RX); `CVM_SERVER_NSEC`, `CVM_SERVER_HEX` (board server);
  `CVM_TX_NPUB` (recipient).
- `load_env_secrets(env=None)` reads env only and **raises `EnvKeyError` when
  either side is missing — "there is deliberately no CLI fallback"**
  (`:182-201`, quote at `:186-187`).
- The CLI parser exposes **no key-bearing option** (`cvm_verdict_publisher.py:387-416`);
  `--tx-npub` defaults from `CVM_TX_NPUB` env (`:408-411`); a test greps the
  parser and the module source for `nsec|hex|key|secret|priv` options
  (`test_cvm_verdict_publisher.py:480-491`, `:516-528`).
- `assert_keys_differ(client_pub_hex, server_pub_hex)` raises
  `KeyCollisionError` when equal, **before anything is sent**
  (`cvm_armed_publisher.py:204-216`); `load_and_check_keys` is the single
  entry (`:225-235`), called first in `run` (`cvm_verdict_publisher.py:422`).
  Rationale (`:206-208`): a shared key makes the client unwrap its own gift
  wraps and self-deliver on its own subscription.
- Failure → exit 2 (`cvm_verdict_publisher.py:487-490`).

### 5.2 Wrapping: NIP-59 kind-1059, no plaintext leak

ADR §2.3 (`:70-73`): messages are gift-wrapped **NIP-59 kind-1059 stored
wrappers, not plaintext kind-30315** (RF recon leak). ADR §2.5 (`:85-90`):
the verdict wraps `range_check` per-config output + inline `resend-<stop>.json`.

- Outer wrap kind `KIND_GIFT_WRAP = 1059` — imported from `cvm_sync`
  (`cvm_sync.py:68`), asserted at import (`cvm_verdict_publisher.py:119-121`);
  a second local definition would fork the ADR-033 single-path pin
  (`tools/test_giftwrap_single_path.py`).
- Inner envelope kind `KIND_CVM_RPC = 25910` (`cvm_armed_publisher.py:77`),
  carried as the rumor content under `[["p", tx_pubkey_hex]]`
  (`build_inner_event`, `:259-273`).
- Publish path: `NostrTxTransport` (`cvm_armed_publisher.py`), reusing the
  `cvm_board_server.py` pattern — `nostr_sdk.ClientBuilder().signer(signer).build()`
  (`cvm_board_server.py:494`), `nostr_sdk.NostrSigner.keys(server_keys)`
  (`:398`), `nostr_sdk.gift_wrap(...)` (`:580`), `UnwrappedGift.from_gift_wrap`
  (`:547`), `HandleNotification` adapter (`_NotificationHandler`, `:597-610`).
- Send-path guard: `FORBIDDEN_PLAINTEXT_TYPES = ("TALLY",)` and
  `publish()` raises `PlaintextKindError` (`cvm_verdict_publisher.py:115`,
  `:316-318`).
- Subscribe pattern (TX side, ADR §2.4 `:80-83`): **broad kind-1059 subscribe +
  client-side npub allowlist** (server-side `#p` filtering is unreliable —
  `cvm_board_server.py:508-510`).

---

## 6. Repo test conventions

- **Where tests live:** `firmware/e80-stm32-bench/tools/test_*.py`
  (32 modules at `origin/main`), sibling to the module under test. New legacy
  or C++ suites live elsewhere, but the message-layer tools are all here.
- **Invocation (documented host gate):** `firmware/e80-stm32-bench/Makefile:657-659`

  ```make
  range-test-host: ## Run pytest for distributed range test split logic
  	@echo "=== Running distributed range test unit tests ==="
  	cd $(TOOLDIR)/tools && $(PYTHON) -m pytest test_e80_range_split.py test_range_check.py -v
  ```

  The Makefile **enumerates pytest files explicitly** — a new module is NOT
  auto-collected until it is added to that line. Single module run:
  `cd firmware/e80-stm32-bench/tools && python3 -m pytest test_<name>.py -v`.
- **No pytest config file** at the sub-project root (`pytest.ini`/`setup.cfg`/
  `pyproject.toml` absent) — plain `python -m pytest`.
- **CI does not run these Python tools tests:** `.github/workflows/ci-host-tests.yml`
  runs only C/C++ suites (nostr_store, relay-pipeline, payment-proto, tollgate,
  ehash-relay, stratorelay). Python message-layer coverage is a **host-gate**
  responsibility (`make range-test-host`), not CI.
- **Env vars in tests:** the modules avoid mutating `os.environ`. Key loaders
  take an explicit `env` mapping (`load_env_secrets(env=None)` →
  `load_env_secrets({...})`; `cvm_armed_publisher.py:182-201`), and tests pass a
  literal dict:
  `load_env_secrets({"CVM_RX_NSEC": "nsec1x", "CVM_SERVER_NSEC": "nsec1y"})`
  (`test_cvm_verdict_publisher.py:501-508`). CLI behaviour is tested by
  `subprocess.run([sys.executable, <module>, "--help"], …)`
  (`:516-520`, `:530-537`). No `monkeypatch.setenv` / `patch.dict` usage.
- **Import style:** modules `sys.path.insert(0, <tools dir>)` and import
  siblings bare (`import cvm_sync as cvm`, `import range_check as rc`) —
  `cvm_verdict_publisher.py:96-114`. Tests import the module under test the
  same way.
- **Known ADR-033 pin:** `tools/test_giftwrap_single_path.py` forbids a local
  `gift_wrap()` wrapper / a second `KIND_GIFT_WRAP` literal. A fake transport
  in a NEW test must not name its method `gift_wrap`.

---

## 7. Gate1 test cases (enumerated, unambiguous)

A fresh worker must be able to write these directly. Each case: **given → when
→ then**, plus the source it pins. The already-written
`test_cvm_verdict_publisher.py` (blob `1faadeb9`) contains these; Gate1 is to
**verify/port them into the tree that will be tested post-consolidation**, not
to re-invent.

### Group P — payload shape

- **P1 required keys present.** Given one non-empty `per_config` list → when
  `build_verdict(...)` → then the emitted dict contains every name in
  `VERDICT_REQUIRED = ("type","session_id","stop","summary","per_config","resend_json","created_at")`
  and `type == "VERDICT"`. (src `:106-109`, `:200-213`)
- **P2 per_config row shape.** Each row has exactly `{idx,label,n_pkts,counted,status}`,
  `idx|n_pkts|counted` are non-negative ints, `label` is a str. (src `:165-171`)
- **P3 status enum.** `status ∈ {"OK","THIN","MISS"}`; a row with
  `status="DOWN"` (or any other) raises `VerdictError`. (src `:100`, `:160-164`)
- **P4 bad counts refused.** `n_pkts=-1`, `counted=-1`, `counted=True`,
  `idx=None` each raise `VerdictError`. (src `:132-144`)
- **P5 resend inline verbatim.** Given a `resend_json` object → it appears under
  `resend_json` **deep-copied** (mutating the source afterwards does not change
  the message); absent → `null`. (src `:206-208`) A **path string** is never
  accepted — `resend_json` must be an object or null. (`validate_verdict`
  `:245-247`)
- **P6 emitted key set pinned.** The exact set of top-level keys of the built
  message equals `{type,session_id,stop,summary,per_config,resend_json,log_gap,stat_count,created_at,author}`
  — guards `log_gap`/`stat_count`/`author` (emitted but not in `VERDICT_REQUIRED`)
  against silent removal. (src `:106-109` vs `:200-213`)
- **P7 summary == range_check.verdict_line.** For a mixed scan the message
  `summary` byte-equals `range_check.verdict_line(stop, session_id, rows, "GAPS")`;
  all-OK → the `PASS` line. (src `:194-199`; `range_check.py:700-719`)
- **P8 JSON round-trip.** `json.loads(json.dumps(msg)) == msg`. (src `:253-257`
  in tests; message is pure JSON types)
- **P9 LOGGING-GAP variant.** `build_verdict(..., results=[])` → `log_gap is
  True`, `per_config == []`, `summary` is the LOGGING GAP text, `resend_json`
  is null. (src `:193-197`)
- **P10 validate_verdict rejects log_gap+rows.** A message with `log_gap=True`
  and non-empty `per_config` → `(False, reason)`. (src `:232-233`)

### Group C — config-end aggregation (N packets ⇒ exactly 1 verdict)

- **C1 one message regardless of packet count.** Drive a completed scan whose
  capture holds 0, 1, 7, 250 and 1000 packets → `publisher.published_count == 1`
  for each, and the message is complete (all rows present), never partial.
  (src `:282-343`; P1 `VerdictPublisher`, `cvm_sync.py:284-340`)
- **C2 count tracks config-end calls, not packets.** Two completed stops →
  exactly 2 messages; a scan with 1000 packets but one call → 1 message.
  (src `:311-338`)
- **C3 no per-packet API surface.** AST/source guard: the module defines no
  method that takes a single packet / publishes per packet (the branch test
  uses an AST scan). (src `:340-352` in tests)

### Group L — session linkage

- **L1 link field list.** `LINK_FIELDS == ("session_id", "stop")`. (src `:112`)
- **L2 valid link.** Verdict `{session_id:S, stop:D}` vs ARMED `{session_id:S,
  stop:D}` → `validate_session_link` returns `(True, "")`. (src `:251-275`)
- **L3 mismatched session refused.** verdict `session_id != armed.session_id`
  → `(False, ...)`. (src `:265-267`)
- **L4 mismatched stop refused.** `stop` differ → `(False, ...)`. (src `:272-274`)
- **L5 missing link field refused.** Either side missing `session_id`/`stop`
  → `(False, ...)`. (src `:263-264`, `:270-271`)
- **L6 bad session format refused.** `session_id="260913"` / `"…"` not matching
  `^\d{10}[0-9a-f]{3}$` → refused at build AND at publish. (src `:187-189`;
  regex `cvm_armed_publisher.py:73`)
- **L7 placeholder stop refused.** `stop=""` or `"?"` → refused. (src `:190-191`)
- **L8 CLI --armed cross-check.** `--armed <armed.json>` whose session/stop
  differ from `--session-id`/`--stop` → exit 2, nothing published. (src `:438-444`)

### Group W — kind-1059 wrapping, no plaintext leak

- **W1 publish routes through gift wrap kind 1059.** Publish → the transport
  receives a kind-1059 wrap (fake SDK asserts `gift_wrap` called with the inner
  kind-25910 event). (src `:82-95`, `:453-468`)
- **W2 no 30315 literal.** Source scan: the string `30315` appears nowhere in
  the module (or its literal kind is never constructed). (src `:13-14` docstring,
  guard `:115`, `:316-318`)
- **W3 plaintext TALLY refused.** `publish({"type":"TALLY", ...})` raises
  `PlaintextKindError`. (src `:115`, `:316-318`)
- **W4 shared transport identity.** `cvm_verdict_publisher.failover_relays is
  cvm_armed_publisher.failover_relays` and the key helpers are the same objects
  (no re-implementation). (branch test `:493-499`, `:551-554`)
- **W5 KIND_GIFT_WRAP imported.** `cvm_verdict_publisher.KIND_GIFT_WRAP == 1059`
  and is imported from `cvm_sync` (ADR-033 pin stays green). (src `:81`, `:119-121`)

### Group R — relay set (supports W)

- **R1 exact ordered set.** `failover_relays()` == `["wss://nostr.mom",
  "wss://relay.primal.net", "wss://nos.lol", "wss://relay2.contextvm.org",
  "wss://relay.nostr.band"]`. (src `cvm_armed_publisher.py:89-96`)
- **R2 dead relay never included.** `relay.contextvm.org` ∉
  `failover_relays(["wss://relay.contextvm.org"])` and ∉ `failover_relays()`.
  (src `:96`, `:242-252`)

### Group K — key source (supports the env-only rule)

- **K1 no key-bearing CLI option.** No option string in `build_parser()` or in
  the module source contains `nsec|hex|key|secret|priv`. (src `:387-416`)
- **K2 missing key raises.** `load_env_secrets({})` raises `EnvKeyError`;
  the error text says "never a CLI arg". (src `cvm_armed_publisher.py:193-200`)
- **K3 identical keys refused.** `assert_keys_differ(h, h)` raises
  `KeyCollisionError`; distinct hex does not. (src `:204-216`)
- **K4 --help leaks no key.** `python3 cvm_verdict_publisher.py --help` exit 0,
  lists `--session-id/--stop/--results`, contains no `--key/--secret/--priv/nsec1`.
  (branch test `:516-528`)

---

## 8. Open gaps and falsified premises (frozen with the contract)

- **G1 — `range_check.py` has NO `--json` emitter** (§1.6). The publisher's
  docstring example `range_check.py … --json > out.json`
  (`cvm_verdict_publisher.py:54`) cannot run today; `--results` must be
  hand-assembled (bare list, or object with `results`/`per_config` +
  `resend_json`/`stat_count`). This is a **transcription-error risk** and a real
  follow-up (belongs to the P2/P3 track, not Gate1). Gate1 tests feed
  `--results` directly and are unaffected.
- **G2 — the ADR does not name the linkage fields** (§3). It lists the five
  ARMED fields but never states "linkage = session_id + stop"; that list is
  pinned only in the implementation (`LINK_FIELDS`, `validate_session_link`).
  If Gate1 must cite the ADR, the ADR needs a one-line addition; this contract
  records the minimal set as **`session_id` + `stop`**.
- **G3 — `VERDICT_REQUIRED` omits `log_gap`/`stat_count`** although the builder
  always emits them (§2, case P6). Add them to the tuple, or freeze the emitted
  key set in a test.
- **G4 — `relay.contextvm.org` "DEAD" is stale** (§4). It is excluded by code
  (kept), but a probe from CobradorWave on 2026-10-09 found it live (NIP-11
  200, WS upgrade 200). Correct the ADR/comment annotation; keep the exclusion.
- **G5 — publishers not merged.** `cvm_verdict_publisher.py` /
  `cvm_armed_publisher.py` are on branches, not `origin/main` (§0). Gate1 must
  run against the consolidation branch, or the publisher + the Makefile
  `range-test-host` line must land first (the Makefile enumerates pytest files
  explicitly — §6).
- **Falsified premise (recorded):** the card's item 3 asks to "confirm
  `relay.contextvm.org` is dead". Confirmed **excluded**, but **not dead**
  (§4). Do not propagate the liveness claim.

---

## 9. Acceptance traceability

- Schema field → source line: §2 table.
- Session linkage field list → §3 (`LINK_FIELDS`, `validate_session_link`).
- Relay failover order → §4 (`FAILOVER_RELAYS`).
- Key-source rule → §5.1 (`load_env_secrets` / `assert_keys_differ`).
- Gate1 test list → §7 (P/C/L/W/R/K groups).
- Real quoted behaviour → §1.7 (executed `range_check.py`, exit 1).
