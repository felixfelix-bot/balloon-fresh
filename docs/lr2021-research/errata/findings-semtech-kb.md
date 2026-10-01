# findings-semtech-kb — Semtech support portal / KB + web-search sourcing for LR2021 known-issue / errata articles

**Task:** t_c6ceaf5d — assemble findings-semtech-kb.md with required block format and hashes.
**Scope:** sourcing only. No summarising, no interpretation, no register-behaviour conclusions.
**Streams consolidated:** (A) Semtech support-portal / KB sweep, (B) general web-search sweep.
**Retrieval session (UTC):** 2026-10-01T03:46Z – 2026-10-01T03:54Z, host `c03rad0r-DQ05proplus`.
**Stream A/B raw captures (repo):** `docs/lr2021-research/errata/raw/semtech-kb/`
**Large / third-party artifacts (scratch):** `/tmp/lr2021-scratch/semtech-kb/`

> Consolidation note (not interpretation of content): the two upstream sourcing streams
> (t_f17a4c86, t_eb50ab25) were archived with `result = null` and no deliverable on disk —
> no `raw/semtech-kb/` tree existed on any ref and no attempt-log file existed. This assembly
> therefore performed the sourcing itself, verbatim and fresh, rather than consolidate
> non-existent inputs. Every `sha256` / `bytes` value below was re-measured from the file on
> disk at assembly time (see `## VERIFICATION (hash re-measure)` at the end).

---

## QUERIES RUN

Every query is listed verbatim with the stream it belongs to and the number of attempts made.

| # | query / URL (verbatim) | stream | attempts | outcome |
|---|---|---|---|---|
| Q1 | `https://support.semtech.com/` | portal | 1 | MISS — login wall (ManageEngine ServiceDesk Plus shell, HTTP 200) |
| Q2 | `https://support.semtech.com/search?q=LR2021` | portal | 1 | MISS — login wall, no server-rendered results (HTTP 200) |
| Q3 | `https://support.semtech.com/hc/en-us/search?query=LR2021` | portal | 1 | MISS — login wall, no server-rendered results (HTTP 200) |
| Q4 | `https://support.semtech.com/hc/en-us` | portal | 1 | MISS — ERROR: curl rc=56 (OpenSSL SSL_read: unexpected eof), HTTP 200 shell only |
| Q5 | `https://support.semtech.com/hc/en-us/articles/search?query=LR2021` | portal | 1 | MISS — ERROR: curl rc=56 (OpenSSL SSL_read: unexpected eof) |
| Q6 | `LR2021` @ `https://www.semtech.com/search?q=LR2021` | web | 1 | MISS — JS-only app; served HTML carries no result items |
| Q7 | `LR2021 errata` @ `https://www.semtech.com/search?q=LR2021+errata` | web | 1 | MISS — JS-only app; no result items, 0 `errata` content hits |
| Q8 | `LR2021 known issue` @ `https://www.semtech.com/search?q=LR2021+known+issue` | web | 1 | MISS — JS-only app; no result items |
| Q9 | `LR2021 limitation` @ `https://www.semtech.com/search?q=LR2021+limitation` | web | 1 | MISS — JS-only app; no result items |
| Q10 | `LR2021 errata` @ `https://www.semtech.com/search/results?q=LR2021+errata` | web | 1 | MISS — JS-only app; no result items |
| Q11 | `LR2021 errata semtech` @ `https://html.duckduckgo.com/html/?q=LR2021+semtech+errata+known+issue` | web | 1 | MISS — HTTP 202 bot challenge, no results |
| Q12 | `LR2021 errata semtech` @ `https://lite.duckduckgo.com/lite/?q=LR2021+errata+semtech` | web | 1 | MISS — HTTP 202 bot challenge, no results |
| Q13 | `LR2021 errata semtech` @ `https://www.bing.com/search?q=LR2021+errata+semtech` | web | 1 | MISS — only ad hosts (ionos.com, zhihu.com); no Semtech/KB document |
| Q14 | `repo:Lora-net/usp LR2021` @ `https://api.github.com/search/issues` | web | 1 | OK — captured (`web-github-search-lr2021-errata.json`) |
| Q15 | `LR2021` (document-index scan) @ `https://www.semtech.com/design-support/development-support-documents/` | portal | 1 | OK — captured (`semtech-design-support-documents.html`) |
| Q16 | `LR2021` @ `https://www.semtech.com/products/wireless-rf/lora-plus/lr2021` | portal | 1 | OK — captured (`semtech-lr2021-product.html`) |
| Q17 | `Lora-net/usp` pinned-commit raw artifact fetch (5 files) @ `https://raw.githubusercontent.com/Lora-net/usp/351b2015350670eb4dfa3aec35eb04433e062654/...` | web | 1 each | OK — 5 captured |
| Q18 | third-party pointer `developing-today/hardware-doc` LR2021 README @ `https://raw.githubusercontent.com/developing-today/hardware-doc/HEAD/components/semtech/lr2021/README.md` | web | 1 | OK — captured (scratch) |

Additional non-search URL probes (existence checks, outcome recorded in the FAILED section):
`https://www.semtech.com/api/search?q=LR2021%20errata`, `https://www.semtech.com/support/technical-support`,
`https://community.semtech.com/search?q=LR2021`.

De-duplication performed by **URL** and by **sha256**: the five `Lora-net/usp` artifacts are byte-distinct
(5 distinct sha256). The three `support.semtech.com` responses are the same ManageEngine login shell
modulo per-response CSP nonces; they are recorded once in the FAILED section under the KB entry, not as
artifact blocks, because their body is an authentication shell and not KB content. Identical bytes captured
via two routes are emitted once.

---

## ARTIFACT BLOCKS

### semtech-usp-doc-KNOWN_LIMITATIONS
- location: docs/lr2021-research/errata/raw/semtech-kb/semtech-usp-doc-KNOWN_LIMITATIONS.md
- url: https://raw.githubusercontent.com/Lora-net/usp/351b2015350670eb4dfa3aec35eb04433e062654/doc/KNOWN_LIMITATIONS.md
- http_status: 200
- revision_or_publication_date: UNKNOWN
- retrieved_utc: 2026-10-01T03:48:24Z
- bytes: 3440
- sha256: 464c2ec1e9cb8ee557140594e7cc8c6bd34886177ebba68ccf8f57ad4d67d44e
- notes: Known Limitations

### semtech-usp-lr20xx_driver-README
- location: docs/lr2021-research/errata/raw/semtech-kb/semtech-usp-lr20xx_driver-README.md
- url: https://raw.githubusercontent.com/Lora-net/usp/351b2015350670eb4dfa3aec35eb04433e062654/smtc_rac_lib/radio_drivers/lr20xx_driver/README.md
- http_status: 200
- revision_or_publication_date: date code: 2513, version 0x0110 (as printed)
- retrieved_utc: 2026-10-01T03:48:24Z
- bytes: 11504
- sha256: 50cd34077db00dd41b1c04ac25bbe71457abcfcb198a97c5e706fd44a9a7b38c
- notes: LR20XX driver

### semtech-usp-lr20xx_driver-CHANGELOG
- location: docs/lr2021-research/errata/raw/semtech-kb/semtech-usp-lr20xx_driver-CHANGELOG.md
- url: https://raw.githubusercontent.com/Lora-net/usp/351b2015350670eb4dfa3aec35eb04433e062654/smtc_rac_lib/radio_drivers/lr20xx_driver/CHANGELOG.md
- http_status: 200
- revision_or_publication_date: [v1.3.4] - 2025-11-25 (as printed)
- retrieved_utc: 2026-10-01T03:48:25Z
- bytes: 1960
- sha256: 85fdcd2fdc26fe1c1c7008cd36e8296d7c792518f78c7c0d2583da3b1dfcecf6
- notes: Changelog

### semtech-usp-lr20xx_workarounds.h
- location: docs/lr2021-research/errata/raw/semtech-kb/semtech-usp-lr20xx_workarounds.h
- url: https://raw.githubusercontent.com/Lora-net/usp/351b2015350670eb4dfa3aec35eb04433e062654/smtc_rac_lib/radio_drivers/lr20xx_driver/inc/lr20xx_workarounds.h
- http_status: 200
- revision_or_publication_date: Copyright Semtech Corporation 2025 (as printed)
- retrieved_utc: 2026-10-01T03:48:25Z
- bytes: 21680
- sha256: 1a3b6715c3bf2ba8301e140a281a15c01d68f7c72e477b19bae4679d8c31150e
- notes: @file lr20xx_workarounds.h — @brief System driver workarounds definition for LR20XX

### semtech-usp-lr20xx_workarounds.c
- location: docs/lr2021-research/errata/raw/semtech-kb/semtech-usp-lr20xx_workarounds.c
- url: https://raw.githubusercontent.com/Lora-net/usp/351b2015350670eb4dfa3aec35eb04433e062654/smtc_rac_lib/radio_drivers/lr20xx_driver/src/lr20xx_workarounds.c
- http_status: 200
- revision_or_publication_date: Copyright Semtech Corporation 2025 (as printed)
- retrieved_utc: 2026-10-01T03:48:26Z
- bytes: 30073
- sha256: b219a288bf9435ec0df731835003030559b52e00438eafe06193a99632ee6976
- notes: @file lr20xx_workarounds.c — @brief System driver workaround implementation for LR20XX

### semtech-design-support-documents
- location: docs/lr2021-research/errata/raw/semtech-kb/semtech-design-support-documents.html
- url: https://www.semtech.com/design-support/development-support-documents/
- http_status: 200
- revision_or_publication_date: 2026-08-08 (LR2021/22/12 Datasheet v2.2 DatePosted, as printed)
- retrieved_utc: 2026-10-01T03:48:35Z
- bytes: 813372
- sha256: bf95846a8dd7677a2c39579d46e9071f6dee09d7630349b7b488b7797b82cfbd
- notes: Development Support Documents | Semtech

### semtech-lr2021-product
- location: docs/lr2021-research/errata/raw/semtech-kb/semtech-lr2021-product.html
- url: https://www.semtech.com/products/wireless-rf/lora-plus/lr2021
- http_status: 200
- revision_or_publication_date: UNKNOWN
- retrieved_utc: 2026-10-01T03:46:41Z
- bytes: 226470
- sha256: 43d55f4a21ef360f0f877453a919dc11b42617f66f44ffc7efd49d0607792b56
- notes: LoRa Plus™ LR2021 | Fourth-generation LoRa® IP for Fast Long Range Communication (FLRC) | Semtech

### semtech-quality
- location: docs/lr2021-research/errata/raw/semtech-kb/semtech-quality.html
- url: https://www.semtech.com/quality
- http_status: 200
- revision_or_publication_date: UNKNOWN
- retrieved_utc: 2026-10-01T03:46:38Z
- bytes: 111430
- sha256: 152d50b40df67cdec83f88ace1887a0f744ba7a18a44b60e0012e45581bd9a2f
- notes: Quality Assurance | Committed to Quality and Reliability | Semtech

### semtech-design-support-faq
- location: docs/lr2021-research/errata/raw/semtech-kb/semtech-design-support-faq.html
- url: https://www.semtech.com/design-support/faq
- http_status: 200
- revision_or_publication_date: UNKNOWN
- retrieved_utc: 2026-10-01T03:48:37Z
- bytes: 122863
- sha256: 169aa4bd5ea328d7090fc8c3dfdb4842a744f3f3b469f32b7bf4c7d7c3a4c9f3
- notes: FAQ | Semtech

### web-github-search-lr2021-errata
- location: docs/lr2021-research/errata/raw/semtech-kb/web-github-search-lr2021-errata.json
- url: https://api.github.com/search/issues?q=repo%3ALora-net%2Fusp+LR2021
- http_status: 200
- revision_or_publication_date: UNKNOWN
- retrieved_utc: 2026-10-01T03:50:17Z
- bytes: 14920
- sha256: 14862800fcd71abcefcb4ab5d90dade3343db323980b4fd6aa127e5aa66a5008
- notes: total_count 3 — "[LR2021] GFSK bitrate 1000 KBPS works, bitrate 1041 KBPS - does not"; "[lbm-team] Radio Configuration for LR2021 LoRa Plus EVK for China or for specific PCBs"; "Compilation advices"

### web-github-hardware-doc-lr2021
- location: SCRATCH: /tmp/lr2021-scratch/semtech-kb/web-github-hardware-doc-lr2021.md
- url: https://raw.githubusercontent.com/developing-today/hardware-doc/HEAD/components/semtech/lr2021/README.md
- http_status: 200
- revision_or_publication_date: UNKNOWN
- retrieved_utc: 2026-10-01T03:48:40Z
- bytes: 60240
- sha256: 72fa21b2c27866a918e71d92365b6271c9ac5bc9e169cbd6d133d95f70f1e848
- notes: Semtech LR2021 — LoRa Plus™, the fourth-generation LoRa transceiver

---

## FAILED / NOT FOUND (semtech-kb)

Every query or URL that yielded no KB article, enumerated with its final status and attempt count.

### KB (support.semtech.com) — yielded nothing

- `https://support.semtech.com/` → HTTP 200 (ManageEngine ServiceDesk Plus login shell; no article content) (1)
- `https://support.semtech.com/search?q=LR2021` → HTTP 200 (login shell; no server-rendered results) (1)
- `https://support.semtech.com/hc/en-us/search?query=LR2021` → HTTP 200 (login shell; no server-rendered results) (1)
- `https://support.semtech.com/hc/en-us` → ERROR: curl rc=56 (OpenSSL SSL_read: unexpected eof while reading) (1)
- `https://support.semtech.com/hc/en-us/articles/search?query=LR2021` → ERROR: curl rc=56 (OpenSSL SSL_read: unexpected eof while reading) (1)

The Semtech support portal is a **login-walled ServiceDesk Plus instance** and returned no KB article
content for any query. **NOT FOUND after 5 attempts.**

### Semtech site search — yielded nothing (JS-only)

- `LR2021` @ `https://www.semtech.com/search?q=LR2021` → HTTP 200, no result items (1)
- `LR2021 errata` @ `https://www.semtech.com/search?q=LR2021+errata` → HTTP 200, no result items, 0 `errata` content hits (1)
- `LR2021 known issue` @ `https://www.semtech.com/search?q=LR2021+known+issue` → HTTP 200, no result items (1)
- `LR2021 limitation` @ `https://www.semtech.com/search?q=LR2021+limitation` → HTTP 200, no result items (1)
- `LR2021 errata` @ `https://www.semtech.com/search/results?q=LR2021+errata` → HTTP 200, no result items (1)

### General web search — yielded nothing usable

- `LR2021 errata semtech` @ `https://html.duckduckgo.com/html/` → HTTP 202 (bot challenge); no results parsed (1)
- `LR2021 errata semtech` @ `https://lite.duckduckgo.com/lite/` → HTTP 202 (bot challenge); no results parsed (1)
- `LR2021 errata semtech` @ `https://www.bing.com/search` → HTTP 200; result hosts were only `ionos.com` and `zhihu.com` (ads); no Semtech/KB document (1)

### Non-search endpoint probes — yielded nothing

- `https://www.semtech.com/api/search?q=LR2021%20errata` → HTTP 404 (1)
- `https://www.semtech.com/support/technical-support` → HTTP 404 (1)
- `https://community.semtech.com/search?q=LR2021` → ERROR: curl rc=6 (Could not resolve host: community.semtech.com) (1)

### Auth-walled copies — AUTH WALL / NOT FETCHED

- `https://support.semtech.com/` — AUTH WALL / NOT FETCHED (login shell only; no article body reachable)
- `https://support.semtech.com/search?q=LR2021` — AUTH WALL / NOT FETCHED
- `https://support.semtech.com/hc/en-us/search?query=LR2021` — AUTH WALL / NOT FETCHED

### No standalone Semtech LR2021 errata document

- `https://www.semtech.com/design-support/development-support-documents/` → HTTP 200. Document index scanned:
  **`"Category":"Errata"` occurs 5 times**, with printed descriptions `"SX1276-7-8 Errata Note"` (×2),
  `"SX1272 Errata Note"`, `"Crosspoints Ballout Errata"`, `"Corecell Reference design V1, PCB#e539V01a Errata note"`.
  **No `Errata` entry names LR20xx or LR2021.**
- `https://www.semtech.com/products/wireless-rf/lora-plus/lr2021` → HTTP 200, `errata|erratum` matches: 0.
- `https://www.semtech.com/design-support/faq` → HTTP 200, `errata|erratum|known issue` matches: 0.
- `https://www.semtech.com/quality` → HTTP 200, `errata|erratum` matches: 0.

**Standalone Semtech LR2021 errata sheet: NOT FOUND after 5 Semtech-host attempts + 3 web-search-engine attempts.**

---

## VERIFICATION (hash re-measure)

Every artifact block above was re-measured from disk at assembly time with
`stat -c %s <file>` and `sha256sum <file>`; the values printed in the blocks are those results.
The independent verifier card t_b2ed116b re-runs the same commands against the same paths.
All listed `location:` paths exist on disk. `retrieved_utc` values are real UTC timestamps taken
from the file mtimes (`date -d @$(stat -c %Y <file>) -u +%Y-%m-%dT%H:%M:%SZ`), host clock
`+0200` at capture; the wall-clock UTC of the capture run was `2026-10-01T03:54Z`.

---

## VERIFICATION (independent)

**Verifier card:** `t_b2ed116b` (assignee `worker-reviewer-glm`, run 246).
**Verified artifact:** `docs/lr2021-research/errata/findings-semtech-kb.md` — 14550 B, sha256 `bafa1f6675e5626e8411fa644606954d3e986e4351b36126fc8b931e87ff53f6`.
**Verified against:** branch `pr/semtech-kb-findings` @ `452720070117b3cfd9ea4e75f368051efb35a6f7` (equals `origin/pr/semtech-kb-findings`).
**Method:** every location was re-measured from disk with `stat -c %s` / `sha256sum`; blocks were parsed by a standalone script (`/tmp/verify_semtech_kb.py`) reading the document text directly. The author's own verification section was not relied upon.

### Check results

| # | check | verdict | evidence |
|---|---|---|---|
| 1 | file exists; required headings present | **PASS** | file present (14550 B); `## QUERIES RUN`, `## ARTIFACT BLOCKS`, `## FAILED / NOT FOUND (semtech-kb)` all found |
| 2 | every artifact location exists; bytes + 64-hex sha256 match disk | **PASS** | 11/11 blocks; dead_paths=0; byte_mismatch=0; sha_mismatch=0 |
| 3 | nine required keys in required order; `retrieved_utc` = `YYYY-MM-DDTHH:MM:SSZ` | **PASS** | 11/11 blocks carry exactly `location,url,http_status,revision_or_publication_date,retrieved_utc,bytes,sha256,notes` under a `### <slug>` heading; 11/11 timestamps match the UTC regex |
| 4 | `notes` carry only article id / title as printed (no interpretation) | **PASS** | 0 flags over notes; all 11 notes are printed titles / `@file … @brief …` header lines / issue titles |
| 5 | ≥5 distinct queries across both streams; every MISS has exact status + attempt count | **PASS** | 18 distinct query rows (Q1–Q18); streams {`portal`,`web`}; all 13 MISS rows resolve to an exact status (`HTTP 200/202/404` or `curl rc=56/6`) plus `(1)` in the FAILED section |
| 6 | explicit 'NOT FOUND after N attempts' statement present and N matches the logged attempt count | **PASS** | KB section states NOT-FOUND-after-5-attempts; the KB block logs 5 attempts, each marked `(1)` → N=5 |

### Exact commands run for the hash re-computation

```
cd docs/lr2021-research/errata/raw/semtech-kb
stat -c %s semtech-usp-doc-KNOWN_LIMITATIONS.md        # 3440
stat -c %s semtech-usp-lr20xx_driver-README.md          # 11504
stat -c %s semtech-usp-lr20xx_driver-CHANGELOG.md       # 1960
stat -c %s semtech-usp-lr20xx_workarounds.h             # 21680
stat -c %s semtech-usp-lr20xx_workarounds.c             # 30073
stat -c %s semtech-design-support-documents.html        # 813372
stat -c %s semtech-lr2021-product.html                  # 226470
stat -c %s semtech-quality.html                         # 111430
stat -c %s semtech-design-support-faq.html              # 122863
stat -c %s web-github-search-lr2021-errata.json         # 14920
sha256sum semtech-usp-doc-KNOWN_LIMITATIONS.md \
          semtech-usp-lr20xx_driver-README.md \
          semtech-usp-lr20xx_driver-CHANGELOG.md \
          semtech-usp-lr20xx_workarounds.h \
          semtech-usp-lr20xx_workarounds.c \
          semtech-design-support-documents.html \
          semtech-lr2021-product.html \
          semtech-quality.html \
          semtech-design-support-faq.html \
          web-github-search-lr2021-errata.json
# scratch block (location: "SCRATCH: /tmp/…"):
stat -c %s /tmp/lr2021-scratch/semtech-kb/web-github-hardware-doc-lr2021.md   # 60240
sha256sum   /tmp/lr2021-scratch/semtech-kb/web-github-hardware-doc-lr2021.md
# retrieved_utc cross-check (doc value == file mtime in UTC):
date -d @$(stat -c %Y <file>) -u +%Y-%m-%dT%H:%M:%SZ
# format/content parser:
python3 /tmp/verify_semtech_kb.py
```

Re-measured digests (all identical to the document):

```
464c2ec1e9cb8ee557140594e7cc8c6bd34886177ebba68ccf8f57ad4d67d44e  semtech-usp-doc-KNOWN_LIMITATIONS.md
50cd34077db00dd41b1c04ac25bbe71457abcfcb198a97c5e706fd44a9a7b38c  semtech-usp-lr20xx_driver-README.md
85fdcd2fdc26fe1c1c7008cd36e8296d7c792518f78c7c0d2583da3b1dfcecf6  semtech-usp-lr20xx_driver-CHANGELOG.md
1a3b6715c3bf2ba8301e140a281a15c01d68f7c72e477b19bae4679d8c31150e  semtech-usp-lr20xx_workarounds.h
b219a288bf9435ec0df731835003030559b52e00438eafe06193a99632ee6976  semtech-usp-lr20xx_workarounds.c
bf95846a8dd7677a2c39579d46e9071f6dee09d7630349b7b488b7797b82cfbd  semtech-design-support-documents.html
43d55f4a21ef360f0f877453a919dc11b42617f66f44ffc7efd49d0607792b56  semtech-lr2021-product.html
152d50b40df67cdec83f88ace1887a0f744ba7a18a44b60e0012e45581bd9a2f  semtech-quality.html
169aa4bd5ea328d7090fc8c3dfdb4842a744f3f3b469f32b7bf4c7d7c3a4c9f3  semtech-design-support-faq.html
14862800fcd71abcefcb4ab5d90dade3343db323980b4fd6aa127e5aa66a5008  web-github-search-lr2021-errata.json
72fa21b2c27866a918e71d92365b6271c9ac5bc9e169cbd6d133d95f70f1e848  /tmp/lr2021-scratch/semtech-kb/web-github-hardware-doc-lr2021.md
```

### Corrections

**None.** All 11 byte counts and all 11 sha256 values matched the files on disk; all 11 `location:` paths exist; all 11 `retrieved_utc` values are valid `YYYY-MM-DDTHH:MM:SSZ` and equal the corresponding file mtime in UTC. No before/after edits were required, and no block was modified.

### Verdict

`VERDICT: PASS` — 6/6 checks PASS, 0 deviations, 0 corrections. The document is left byte-identical to `45272007` apart from this appended verification section; every listed sha256 verifies on disk.
