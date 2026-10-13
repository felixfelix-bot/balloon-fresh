# LR2021 errata / application-note / known-limitations — provenance

**Task:** t_b7a77949 — "Locate LR2021 errata, application notes, and known-limitations docs"
**Scope:** sourcing + provenance only. This file makes **no register-behaviour conclusions**.
**Retrieval session (UTC):** 2026-09-30T23:30Z – 2026-09-30T23:35Z, host `c03rad0r-DQ05proplus`.
**Worktree:** `/home/c03rad0r/.hermes/.worktrees/t_b7a77949` (branch `pr/lr2021-errata`),
repo `felixfelix-bot/balloon-fresh`.
**Scratch (outside repo):** `/home/c03rad0r/scratch/lr2021-errata/` (intermediate HTML/JSON
fetches; not committed).

Legend — **HTTP** is the status observed at retrieval; **sha256** is of the local file as
stored/committed; **size** is bytes.

---

## 1. PRIMARY FINDING — the errata / known-limitations content that DOES exist

There is **no standalone Semtech "errata sheet" PDF** for the LR2021 (see §3). However three
**Semtech-authored** artifacts that carry known-limitation / workaround content **were located
and retrieved**:

| # | Artifact | Nature | Where it lives |
|---|---|---|---|
| E1 | Datasheet Rev 2.2, **§22 "Known Limitations and Workarounds"** (pp. 232–234) | Known-limitations chapter *inside the datasheet* | in-repo PDF |
| E2 | **`doc/KNOWN_LIMITATIONS.md`** (USP repo, Semtech) | Repo-level known-limitations document (USP platform); contains LR20xx-specific entries | `Lora-net/usp` |
| E3 | **`lr20xx_workarounds.h` / `.c` + driver README "Workarounds" section** (Semtech official LR20xx driver) | Silicon workaround catalogue for LR20xx engineering samples | `Lora-net/usp` |

These are the closest published equivalents to an errata sheet. Whether they should be
*cited as errata* downstream is a judgement call left to the consuming task.

---

## 2. RETRIEVAL BLOCKS

### R1 — Datasheet Rev 2.2 §22 extract (E1) — **committed**

- **Local path:** `docs/lr2021-research/errata/semtech-datasheet-v2.2-section22-known-limitations-and-workarounds.txt`
- **Derived from (in-repo source):** `docs/lr2021-research/semtech-official/LR2021_LR2022_LR2012_Datasheet_v2.2.pdf`
  — sha256 `7e55a15dcdbe044dd615eb1f1ea21c26bf8e28758d94face240998e5fbad25c2`, size 5980032.
- **Extraction command:** `pdftotext -layout <pdf> -` then lines 12296–12416 selected.
- **Origin URL (of the PDF):** Semtech LR2021 product page
  `https://www.semtech.com/products/wireless-rf/lora-plus/lr2021` → "LR2021/22/12 Datasheet v2.2"
  (delivery via session-scoped `semtech.my.salesforce.com` link, see `SOURCES.md` A2).
- **HTTP:** 200 (product page, R9 below).
- **Revision / publication date:** Rev. 2.2, footer `DS.LR20xx 29/07/26`, 250 pp.
- **Retrieval date (of extract):** 2026-09-30T23:31Z.
- **File size:** 6450 · **sha256:** `445b7e226ee2f3b17c1e039e4fc5bd2f521204ec6d6c296d0ff8e9215f9c465a`
- **Contents (verbatim extract, not summarised):** §22 intro; §22.1 OOK Detection Threshold
  Adjustment (LR20xx); §22.2 RTTOF Accuracy for SX1280-compatible Bandwidths (LR2021/LR2022);
  §22.3 Firmware Patch RAM (PRAM) + §22.3.1/§22.3.2; §22.4 Regulatory Compliance (§22.4.1 CN470
  SRRC, §22.4.2 IN865).

### R2 — `doc/KNOWN_LIMITATIONS.md` (E2) — **committed**

- **Local path:** `docs/lr2021-research/errata/semtech-usp-doc-KNOWN_LIMITATIONS.md`
- **Origin URL:** `https://raw.githubusercontent.com/Lora-net/usp/351b2015350670eb4dfa3aec35eb04433e062654/doc/KNOWN_LIMITATIONS.md`
  (repo `Lora-net/usp`, commit `351b20153506`, committed 2025-12-15T16:36:17Z).
- **HTTP:** 200 · **Size:** 3440 · **sha256:** `464c2ec1e9cb8ee557140594e7cc8c6bd34886177ebba68ccf8f57ad4d67d44e`
- **Revision / publication date:** no version string in file; repo commit 2025-12-15.
- **Retrieval date:** 2026-09-30T23:30Z.
- **File:** USP platform known-limitations list (support of NUCLEO-L073RZ; hw_modem integration
  #131; hw_modem store&forward #119; dropped programmed packets #130; geolocation tools #129;
  out-of-range frequency accepted #98; **LR20xx BW 7/10/15/20 division-by-zero #94**;
  `symb_nb_timeout` uint8 limit #102; rf_certification unavailable; CAD_LBT mode #125). Stored
  verbatim.

### R3 — `lr20xx_driver/README.md` (E3) — **committed**

- **Local path:** `docs/lr2021-research/errata/semtech-usp-lr20xx_driver-README.md`
- **Origin URL:** `https://raw.githubusercontent.com/Lora-net/usp/351b2015350670eb4dfa3aec35eb04433e062654/smtc_rac_lib/radio_drivers/lr20xx_driver/README.md`
- **HTTP:** 200 · **Size:** 11504 · **sha256:** `50cd34077db00dd41b1c04ac25bbe71457abcfcb198a97c5e706fd44a9a7b38c`
- **Revision / publication date:** driver `lr20xx_driver` v1.3.4 (CHANGELOG top entry 2025-11-25);
  this file at repo commit `351b20153506` (2025-12-15).
- **Retrieval date:** 2026-09-30T23:30Z.
- **File:** contains a "## Workarounds" section (LR20xx engineering samples date code `2513`,
  version `0x0110`) enumerating workaround functions: Bluetooth LE PHY-coded syncwords,
  frequency drift, 2 Mbps preamble length, LoRa SX1276 compatibility mode, LoRa freq-hop
  SX1276 compatibility, OOK detection threshold level, and retention-memory storage pattern.
  Stored verbatim.

### R4 — `lr20xx_driver/CHANGELOG.md` — **committed**

- **Local path:** `docs/lr2021-research/errata/semtech-usp-lr20xx_driver-CHANGELOG.md`
- **Origin URL:** `https://raw.githubusercontent.com/Lora-net/usp/351b2015350670eb4dfa3aec35eb04433e062654/smtc_rac_lib/radio_drivers/lr20xx_driver/CHANGELOG.md`
- **HTTP:** 200 · **Size:** 1960 · **sha256:** `85fdcd2fdc26fe1c1c7008cd36e8296d7c792518f78c7c0d2583da3b1dfcecf6`
- **Revision / publication date:** top release `[v1.3.4] - 2025-11-25`.
- **Retrieval date:** 2026-09-30T23:30Z.

### R5 — `lr20xx_workarounds.h` (E3) — **committed**

- **Local path:** `docs/lr2021-research/errata/semtech-usp-lr20xx_workarounds.h`
- **Origin URL:** `https://raw.githubusercontent.com/Lora-net/usp/351b2015350670eb4dfa3aec35eb04433e062654/smtc_rac_lib/radio_drivers/lr20xx_driver/inc/lr20xx_workarounds.h`
- **HTTP:** 200 · **Size:** 21680 · **sha256:** `1a3b6715c3bf2ba8301e140a281a15c01d68f7c72e477b19bae4679d8c31150e`
- **Revision / publication date:** file header "Copyright Semtech Corporation 2025"; repo commit 2025-12-15.
- **Retrieval date:** 2026-09-30T23:30Z.

### R6 — `lr20xx_workarounds.c` (E3) — **committed**

- **Local path:** `docs/lr2021-research/errata/semtech-usp-lr20xx_workarounds.c`
- **Origin URL:** `https://raw.githubusercontent.com/Lora-net/usp/351b2015350670eb4dfa3aec35eb04433e062654/smtc_rac_lib/radio_drivers/lr20xx_driver/src/lr20xx_workarounds.c`
- **HTTP:** 200 · **Size:** 30073 · **sha256:** `b219a288bf9435ec0df731835003030559b52e00438eafe06193a99632ee6976`
- **Revision / publication date:** file header "Copyright Semtech Corporation 2025"; repo commit 2025-12-15.
- **Retrieval date:** 2026-09-30T23:30Z.
- **Note:** `Lora-net/usp` `main` head at retrieval = `540bba008477a8969e554b8d10dbf90ff6160c8e`
  (2026-09-14T12:50:26Z); the four R2–R6 files were fetched at **pinned commit `351b20153506`**
  (2025-12-15), the commit RadioLib cites in-tree (see R7).

### R7 — RadioLib in-tree LR2021 limitation/workaround excerpts — **committed**

- **Local path:** `docs/lr2021-research/errata/radiolib-lr2021-limitation-excerpts.txt`
- **Derived from (in-repo snapshot):** `docs/lr2021-research/radiolib-master/LR2021-module/`
  (RadioLib master snapshot @ `75e486a573bbaad443ffcafa23f9e3e3d2499914`, 2026-09-13, v7.7.1-dev;
  see `radiolib-master/PROVENANCE.md`).
- **Extraction command:** `grep -rn -i "workaround\|limitation\|errata\|known issue\|silicon" LR2021-module/`
- **Retrieval date:** 2026-09-30T23:31Z.
- **File size:** 1208 · **sha256:** `7d998818eb776347a5f52cd4d1c47a853944a8382e96cd874d6c27fe87038813`
- **Contents (verbatim grep output):** the DCDC workaround call sites
  (`setDCDCworkaround()` / `resetDCDCworkaround()` in `LR2021_cmds_{radio,ook,gfsk,flrc,lora}.cpp`),
  `LR2021.h:790 "The following limitations apply:"` (LoRa side-detector constraints),
  and `LR2021_cmds_chip_control.cpp:348-350` citing Semtech's own
  `lr20xx_workarounds.c` at `Lora-net/usp` commit `351b20153506`.

### R8 — RadioLib LR2021 issue/PR index (live) — **committed**

- **Local path:** `docs/lr2021-research/errata/radiolib-lr2021-issue-index.txt`
- **Origin:** live GitHub API (`gh api`) against `jgromes/RadioLib`.
- **HTTP:** 200 (API).
- **Revision / publication date:** master head at retrieval
  `2325a38a89dd0f0e402c19f67fe910111da1e246` (2026-09-28T12:59:24Z).
- **Retrieval date:** 2026-09-30T23:31Z.
- **File size:** 5295 · **sha256:** `213ffc92def3f2261e5d1ab7d65fd4d5096c5eade40c79de8bb7a855a0790eb3`
- **Contents:** `search/issues q='repo:jgromes/RadioLib LR2021' per_page=100` → **60** items
  (titles + state); plus `q='repo:jgromes/RadioLib errata' per_page=50` → total_count 13, none
  LR2021-specific. No conclusion drawn.

### R9 — Semtech LR2021 product page (live HTML) — **SCRATCH only**

- **Scratch path:** `~/scratch/lr2021-errata/semtech-lr2021-product.html`
- **Origin URL:** `https://www.semtech.com/products/wireless-rf/lora-plus/lr2021`
- **HTTP:** 200 · **Size:** 226470 · **sha256:** `ab8d0b48a520d76e72b904c994c2ecf3f3fe87532ee7ea518802b38eccbe366e`
- **Publication date:** page live at retrieval.
- **Retrieval date:** 2026-09-30T23:30Z.
- **Note:** an earlier snapshot of this same page is already committed at
  `docs/lr2021-research/datasheets/semtech-lr2021-product-page.html.gz` (+ `.txt`,
  `provenance.md`). This live re-fetch confirmed the documentation list is unchanged in shape.
  The page's Documentation list (parsed from this fetch) contains **Datasheets** and
  **Application Notes** only — listed ANs: AN1200.59, .66, .86, .87, .101, .102, .103, .104,
  .106, .107, .110, .112, .114, .116; plus "LR2021/22/12 Datasheet v2.2". **No "errata"
  category or document appears** (grep for `errata|erratum|known issue` → 0 hits).

### R10 — Semtech site-search for "LR2021 errata" — **SCRATCH only**

- **Scratch path:** `~/scratch/lr2021-errata/semtech-search.html`
- **Origin URL:** `https://www.semtech.com/search?q=LR2021+errata`
- **HTTP:** 200 · **Size:** 107220 · **sha256:** `a3d28bf4e2aade41e3bb67dc86b594fe1e431f78825f193e2143324c1cebcbd1`
- **Retrieval date:** 2026-09-30T23:30Z.
- **Note:** results are loaded client-side (JS app); the served HTML contains **no result
  items** — the only `errata` occurrences are the page's own `hreflang` alternate links for the
  query URL. A server-side render was not obtainable (R13, R14).

### R11 — LoRa Alliance site-search for "LR2021" — **SCRATCH only**

- **Scratch path:** `~/scratch/lr2021-errata/loraalliance.html`
- **Origin URL:** `https://lora-alliance.org/?s=LR2021`
- **HTTP:** 200 · **Size:** 243357 · **sha256:** `250128c0b0043a5cb74ad1f8d10a6d169fd116c3f2fb179e5b3ebe3d5c39dcb1`
- **Retrieval date:** 2026-09-30T23:30Z.
- **Note:** search returns **no results** for "LR2021" (page text contains "no results";
  `LR2021` appears only in the search-query metadata, not in any result entry).

### R12 — Third-party compiled record `developing-today/hardware-doc` — **SCRATCH only**

- **Scratch path:** `~/scratch/lr2021-errata/hwdoc-lr2021.md`
- **Origin URL:** `https://raw.githubusercontent.com/developing-today/hardware-doc/HEAD/components/semtech/lr2021/README.md`
- **HTTP:** 200 · **Size:** 60240 · **sha256:** `72fa21b2c27866a918e71d92365b6271c9ac5bc9e169cbd6d133d95f70f1e848`
- **Retrieval date:** 2026-09-30T23:30Z.
- **Status:** **non-authoritative / third-party**. Retained only as a pointer — it independently
  cross-references the same primary artifacts (§1 E1/E3, datasheet §22, `Lora-net/usp`
  `lr20xx_driver`). It has §7 "Known limitations, workarounds and the PRAM" and §10 "Caveats,
  gaps and errata". Not committed; do not cite as primary.

---

## 3. FAILED / NOT-FOUND

Every attempt recorded, including misses.

### 3.1 Standalone Semtech LR2021 errata sheet — **NOT FOUND**

| Attempt | URL / action | Result |
|---|---|---|
| F1 | `https://www.semtech.com/products/wireless-rf/lora-plus/lr2021` (documentation list, R9) | HTTP 200; doc list has Datasheets + Application Notes only; **0** `errata/erratum/known issue` matches in page |
| F2 | archived product page `docs/lr2021-research/datasheets/semtech-lr2021-product-page.html.gz` | **0** errata-term matches |
| F3 | `https://www.semtech.com/search?q=LR2021+errata` (R10) | HTTP 200; JS-only, no server-rendered results |
| F4 | `https://www.semtech.com/search?q=errata&type=document` | HTTP 200; no usable result list |
| F5 | `https://www.semtech.com/api/search?q=LR2021%20errata` | **HTTP 404** |
| F6 | `https://www.semtech.com/search/results?q=LR2021+errata` | attempted (see F5 pattern); no API |
| F7 | `https://www.semtech.com/support/technical-support` (KB entry point) | **HTTP 404** |
| F8 | `https://www.semtech.com/quality` (quality/PCN page) | HTTP 200; **0** `errata/erratum` matches |
| F9 | `https://html.duckduckgo.com/html/?q=LR2021+errata+semtech` | **HTTP 202** (bot challenge); no results parsed |
| F10 | GitHub global `search/repositories q='LR2021 errata'` | total_count **0** |
| F11 | GitHub global `search/issues q='LR2021 errata'` | total_count **2**; neither is a Semtech errata sheet (ScotMesh/RepeaterTastic #3; LilyGO/T-Display-P4 #11) |
| F12 | GitHub global `search/code q='LR2021 errata'` | total_count 91; no errata document — hits are SX126x/LoRaWAN sources and third-party READMEs |

### 3.2 Datasheet / app-note PDFs — no "errata" term

| Document (in-repo) | `errata|erratum|known issue` matches |
|---|---|
| `LR2021_LR2022_LR2012_Datasheet_v2.2.pdf` | 0 (but **has §22** — see E1/R1) |
| `AN1200.101_LR2021_FLRC_Improvements.pdf` | 0 |
| `AN1200.102_LR20xx_LoRaImprovements_Rev1.1.pdf` | 0 |
| `AN1200.104_LR20xx_ModemInterface_v1.0.pdf` | 0 |

### 3.3 RadioLib

| Attempt | Result |
|---|---|
| F13 | `repos/jgromes/RadioLib/git/trees/master?recursive=1` grep `errata|limitation` → **0** files |
| F14 | `.../contents/docs` | **HTTP 404** (no `docs/` directory) |
| F15 | `raw.githubusercontent.com/jgromes/RadioLib/master/CHANGELOG.md` | **HTTP 404** (no root changelog) |
| F16 | `search/issues q='repo:jgromes/RadioLib errata'` | total_count 13; **none LR2021** (SX126x #1715/#65, SX127x, CC1101, LoRaWAN, …) |
| F17 | in-tree scan of `LR2021-module/` | no file named `*errata*`; only workaround/limitation references (R7) |

### 3.4 LoRa Alliance / LoRaWAN

| Attempt | Result |
|---|---|
| F18 | `https://lora-alliance.org/?s=LR2021` (R11) | HTTP 200; **no results** |
| F19 | `https://lora-alliance.org/resource_hub/` | HTTP 200; **0** `LR2021|LR20xx` matches |

### 3.5 Semtech KB / support articles referencing LR2021 known issues — **NOT FOUND**

- F7 above (support page 404). No Semtech support/KB article referencing LR2021 known issues was
  reachable; the public KB entry point is behind a login/404. **Status: NOT FOUND after 3 attempts
  (F5, F6, F7).**

---

## 4. Summary of status

- **Standalone errata sheet:** NOT FOUND (see §3.1).
- **Known-limitations / workaround documentation:** FOUND — datasheet Rev 2.2 §22 (E1/R1);
  `Lora-net/usp doc/KNOWN_LIMITATIONS.md` (E2/R2); `lr20xx_workarounds.{h,c}` + driver README
  (E3/R3–R6).
- **Application notes:** listed on the product page (R9); the 3 most TX-relevant are already in
  this corpus under `semtech-official/`.
- No register-behaviour conclusions are drawn here.
