# LR2021 fetch manifest — errata fragment

- source file (read only): `docs/lr2021-research/errata/provenance.md`
- source sha256: `28ed23c417743daeeafc3226ea9028f66748b4821afa3c8e6e06eb5251543f64`
- source size: `15458` bytes
- verified entries (path exists AND sha256 matches): `12`
- entries flagged HASH MISMATCH: `0`
- FAILED entries: `20` (F1–F19, plus source §3.5's consolidated not-found record)
- unique IDs emitted: 32 (R1–R12, F1–F19, §3.5); every ID appears exactly once
- verification: `sha256sum` (fallback `shasum -a 256`, then `sha256`) + `test -f`, run this session
- network access: none

---

## VERIFIED

### R1 — Datasheet Rev. 2.2 §22 "Known Limitations and Workarounds" extract (artifact E1)
- local path: `docs/lr2021-research/errata/semtech-datasheet-v2.2-section22-known-limitations-and-workarounds.txt`
- origin URL: https://www.semtech.com/products/wireless-rf/lora-plus/lr2021
- HTTP status: `200`
- version/revision: Rev. 2.2 · footer `DS.LR20xx 29/07/26` · 250 pp.
- retrieval date: 2026-09-30T23:31Z
- file size: `6450`
- sha256: `445b7e226ee2f3b17c1e039e4fc5bd2f521204ec6d6c296d0ff8e9215f9c465a`
- sha256 (locally re-verified via sha256sum): `445b7e226ee2f3b17c1e039e4fc5bd2f521204ec6d6c296d0ff8e9215f9c465a`
- file size (measured this session): `6450` bytes
- derived-from local path: `docs/lr2021-research/semtech-official/LR2021_LR2022_LR2012_Datasheet_v2.2.pdf`
- derived-from sha256 (recorded `7e55a15dcdbe044dd615eb1f1ea21c26bf8e28758d94face240998e5fbad25c2`; locally re-verified via sha256sum: `7e55a15dcdbe044dd615eb1f1ea21c26bf8e28758d94face240998e5fbad25c2`)
- status: `VERIFIED`

### R2 — `doc/KNOWN_LIMITATIONS.md` (artifact E2)
- local path: `docs/lr2021-research/errata/semtech-usp-doc-KNOWN_LIMITATIONS.md`
- origin URL: https://raw.githubusercontent.com/Lora-net/usp/351b2015350670eb4dfa3aec35eb04433e062654/doc/KNOWN_LIMITATIONS.md
- HTTP status: `200`
- version/revision: no version string in file · repo `Lora-net/usp` commit `351b20153506` (2025-12-15T16:36:17Z)
- retrieval date: 2026-09-30T23:30Z
- file size: `3440`
- sha256: `464c2ec1e9cb8ee557140594e7cc8c6bd34886177ebba68ccf8f57ad4d67d44e`
- sha256 (locally re-verified via sha256sum): `464c2ec1e9cb8ee557140594e7cc8c6bd34886177ebba68ccf8f57ad4d67d44e`
- file size (measured this session): `3440` bytes
- status: `VERIFIED`

### R3 — `lr20xx_driver/README.md` (artifact E3)
- local path: `docs/lr2021-research/errata/semtech-usp-lr20xx_driver-README.md`
- origin URL: https://raw.githubusercontent.com/Lora-net/usp/351b2015350670eb4dfa3aec35eb04433e062654/smtc_rac_lib/radio_drivers/lr20xx_driver/README.md
- HTTP status: `200`
- version/revision: driver `lr20xx_driver` v1.3.4 (CHANGELOG top entry 2025-11-25) · file at repo commit `351b20153506` (2025-12-15)
- retrieval date: 2026-09-30T23:30Z
- file size: `11504`
- sha256: `50cd34077db00dd41b1c04ac25bbe71457abcfcb198a97c5e706fd44a9a7b38c`
- sha256 (locally re-verified via sha256sum): `50cd34077db00dd41b1c04ac25bbe71457abcfcb198a97c5e706fd44a9a7b38c`
- file size (measured this session): `11504` bytes
- status: `VERIFIED`

### R4 — `lr20xx_driver/CHANGELOG.md`
- local path: `docs/lr2021-research/errata/semtech-usp-lr20xx_driver-CHANGELOG.md`
- origin URL: https://raw.githubusercontent.com/Lora-net/usp/351b2015350670eb4dfa3aec35eb04433e062654/smtc_rac_lib/radio_drivers/lr20xx_driver/CHANGELOG.md
- HTTP status: `200`
- version/revision: top release `[v1.3.4] - 2025-11-25`
- retrieval date: 2026-09-30T23:30Z
- file size: `1960`
- sha256: `85fdcd2fdc26fe1c1c7008cd36e8296d7c792518f78c7c0d2583da3b1dfcecf6`
- sha256 (locally re-verified via sha256sum): `85fdcd2fdc26fe1c1c7008cd36e8296d7c792518f78c7c0d2583da3b1dfcecf6`
- file size (measured this session): `1960` bytes
- status: `VERIFIED`

### R5 — `lr20xx_workarounds.h` (artifact E3)
- local path: `docs/lr2021-research/errata/semtech-usp-lr20xx_workarounds.h`
- origin URL: https://raw.githubusercontent.com/Lora-net/usp/351b2015350670eb4dfa3aec35eb04433e062654/smtc_rac_lib/radio_drivers/lr20xx_driver/inc/lr20xx_workarounds.h
- HTTP status: `200`
- version/revision: file header "Copyright Semtech Corporation 2025" · repo commit 2025-12-15
- retrieval date: 2026-09-30T23:30Z
- file size: `21680`
- sha256: `1a3b6715c3bf2ba8301e140a281a15c01d68f7c72e477b19bae4679d8c31150e`
- sha256 (locally re-verified via sha256sum): `1a3b6715c3bf2ba8301e140a281a15c01d68f7c72e477b19bae4679d8c31150e`
- file size (measured this session): `21680` bytes
- status: `VERIFIED`

### R6 — `lr20xx_workarounds.c` (artifact E3)
- local path: `docs/lr2021-research/errata/semtech-usp-lr20xx_workarounds.c`
- origin URL: https://raw.githubusercontent.com/Lora-net/usp/351b2015350670eb4dfa3aec35eb04433e062654/smtc_rac_lib/radio_drivers/lr20xx_driver/src/lr20xx_workarounds.c
- HTTP status: `200`
- version/revision: file header "Copyright Semtech Corporation 2025" · repo commit 2025-12-15
- retrieval date: 2026-09-30T23:30Z
- file size: `30073`
- sha256: `b219a288bf9435ec0df731835003030559b52e00438eafe06193a99632ee6976`
- sha256 (locally re-verified via sha256sum): `b219a288bf9435ec0df731835003030559b52e00438eafe06193a99632ee6976`
- file size (measured this session): `30073` bytes
- status: `VERIFIED`
- source note: `Lora-net/usp` `main` head at retrieval `540bba008477a8969e554b8d10dbf90ff6160c8e` (2026-09-14T12:50:26Z); R2–R6 fetched at pinned commit `351b20153506` (2025-12-15)

### R7 — RadioLib in-tree LR2021 limitation/workaround excerpts
- local path: `docs/lr2021-research/errata/radiolib-lr2021-limitation-excerpts.txt`
- origin URL: n/a (derived in-repo from `docs/lr2021-research/radiolib-master/LR2021-module/`; no network retrieval)
- HTTP status: `n/a (local extraction, no network)`
- version/revision: RadioLib master snapshot @ `75e486a573bbaad443ffcafa23f9e3e3d2499914` (2026-09-13, v7.7.1-dev)
- retrieval date: 2026-09-30T23:31Z
- file size: `1208`
- sha256: `7d998818eb776347a5f52cd4d1c47a853944a8382e96cd874d6c27fe87038813`
- sha256 (locally re-verified via sha256sum): `7d998818eb776347a5f52cd4d1c47a853944a8382e96cd874d6c27fe87038813`
- file size (measured this session): `1208` bytes
- status: `VERIFIED`

### R8 — RadioLib LR2021 issue/PR index (live)
- local path: `docs/lr2021-research/errata/radiolib-lr2021-issue-index.txt`
- origin URL: live GitHub API (`gh api`) against `jgromes/RadioLib` (no exact URL recorded in source)
- HTTP status: `200`
- version/revision: master head at retrieval `2325a38a89dd0f0e402c19f67fe910111da1e246` (2026-09-28T12:59:24Z)
- retrieval date: 2026-09-30T23:31Z
- file size: `5295`
- sha256: `213ffc92def3f2261e5d1ab7d65fd4d5096c5eade40c79de8bb7a855a0790eb3`
- sha256 (locally re-verified via sha256sum): `213ffc92def3f2261e5d1ab7d65fd4d5096c5eade40c79de8bb7a855a0790eb3`
- file size (measured this session): `5295` bytes
- status: `VERIFIED`

### R9 — Semtech LR2021 product page (live HTML, SCRATCH only)
- local path: `~/scratch/lr2021-errata/semtech-lr2021-product.html`
- origin URL: https://www.semtech.com/products/wireless-rf/lora-plus/lr2021
- HTTP status: `200`
- version/revision: n/a (page live at retrieval)
- retrieval date: 2026-09-30T23:30Z
- file size: `226470`
- sha256: `ab8d0b48a520d76e72b904c994c2ecf3f3fe87532ee7ea518802b38eccbe366e`
- sha256 (locally re-verified via sha256sum): `ab8d0b48a520d76e72b904c994c2ecf3f3fe87532ee7ea518802b38eccbe366e`
- file size (measured this session): `226470` bytes
- status: `VERIFIED` (SCRATCH path; outside repo)
- source note: an earlier snapshot of this URL is committed at `docs/lr2021-research/datasheets/semtech-lr2021-product-page.html.gz` (+ `.txt`); not re-counted as a separate retrieval here

### R10 — Semtech site-search for "LR2021 errata" (SCRATCH only)
- local path: `~/scratch/lr2021-errata/semtech-search.html`
- origin URL: https://www.semtech.com/search?q=LR2021+errata
- HTTP status: `200`
- version/revision: n/a
- retrieval date: 2026-09-30T23:30Z
- file size: `107220`
- sha256: `a3d28bf4e2aade41e3bb67dc86b594fe1e431f78825f193e2143324c1cebcbd1`
- sha256 (locally re-verified via sha256sum): `a3d28bf4e2aade41e3bb67dc86b594fe1e431f78825f193e2143324c1cebcbd1`
- file size (measured this session): `107220` bytes
- status: `VERIFIED` (SCRATCH path; outside repo)

### R11 — LoRa Alliance site-search for "LR2021" (SCRATCH only)
- local path: `~/scratch/lr2021-errata/loraalliance.html`
- origin URL: https://lora-alliance.org/?s=LR2021
- HTTP status: `200`
- version/revision: n/a
- retrieval date: 2026-09-30T23:30Z
- file size: `243357`
- sha256: `250128c0b0043a5cb74ad1f8d10a6d169fd116c3f2fb179e5b3ebe3d5c39dcb1`
- sha256 (locally re-verified via sha256sum): `250128c0b0043a5cb74ad1f8d10a6d169fd116c3f2fb179e5b3ebe3d5c39dcb1`
- file size (measured this session): `243357` bytes
- status: `VERIFIED` (SCRATCH path; outside repo)

### R12 — Third-party compiled record `developing-today/hardware-doc` (SCRATCH only)
- local path: `~/scratch/lr2021-errata/hwdoc-lr2021.md`
- origin URL: https://raw.githubusercontent.com/developing-today/hardware-doc/HEAD/components/semtech/lr2021/README.md
- HTTP status: `200`
- version/revision: n/a
- retrieval date: 2026-09-30T23:30Z
- file size: `60240`
- sha256: `72fa21b2c27866a918e71d92365b6271c9ac5bc9e169cbd6d133d95f70f1e848`
- sha256 (locally re-verified via sha256sum): `72fa21b2c27866a918e71d92365b6271c9ac5bc9e169cbd6d133d95f70f1e848`
- file size (measured this session): `60240` bytes
- status: `VERIFIED` (SCRATCH path; outside repo)
- entry qualifier (per source §2 R12): non-authoritative / third-party — retained only as a pointer; source says do not cite as primary

---

## FAILED

### F1 — Semtech LR2021 product page, documentation list
- local path: `n/a` (no artifact retrieved)
- origin URL: https://www.semtech.com/products/wireless-rf/lora-plus/lr2021
- HTTP status: `200`
- version/revision: `n/a`
- retrieval date: n/a (per-attempt date not recorded; source retrieval session 2026-09-30T23:30Z–2026-09-30T23:35Z)
- file size: `n/a`
- sha256: `n/a`
- status: `FAILED`
- FAILED reason: zero `errata/erratum/known issue` matches in page (documentation list carries Datasheets + Application Notes only)

### F2 — archived product page snapshot
- local path: `n/a` (no artifact retrieved)
- origin URL: `docs/lr2021-research/datasheets/semtech-lr2021-product-page.html.gz` (local archived snapshot; no URL fetched in this attempt)
- HTTP status: `n/a`
- version/revision: `n/a`
- retrieval date: n/a (per-attempt date not recorded; source retrieval session 2026-09-30T23:30Z–2026-09-30T23:35Z)
- file size: `n/a`
- sha256: `n/a`
- status: `FAILED`
- FAILED reason: zero errata-term matches

### F3 — Semtech site-search
- local path: `n/a` (no artifact retrieved)
- origin URL: https://www.semtech.com/search?q=LR2021+errata
- HTTP status: `200`
- version/revision: `n/a`
- retrieval date: n/a (per-attempt date not recorded; source retrieval session 2026-09-30T23:30Z–2026-09-30T23:35Z)
- file size: `n/a`
- sha256: `n/a`
- status: `FAILED`
- FAILED reason: JS-only, no server-rendered results

### F4 — Semtech site-search (document type)
- local path: `n/a` (no artifact retrieved)
- origin URL: https://www.semtech.com/search?q=errata&type=document
- HTTP status: `200`
- version/revision: `n/a`
- retrieval date: n/a (per-attempt date not recorded; source retrieval session 2026-09-30T23:30Z–2026-09-30T23:35Z)
- file size: `n/a`
- sha256: `n/a`
- status: `FAILED`
- FAILED reason: no usable result list

### F5 — Semtech search API
- local path: `n/a` (no artifact retrieved)
- origin URL: https://www.semtech.com/api/search?q=LR2021%20errata
- HTTP status: `404`
- version/revision: `n/a`
- retrieval date: n/a (per-attempt date not recorded; source retrieval session 2026-09-30T23:30Z–2026-09-30T23:35Z)
- file size: `n/a`
- sha256: `n/a`
- status: `FAILED`
- FAILED reason: 404

### F6 — Semtech search results path
- local path: `n/a` (no artifact retrieved)
- origin URL: https://www.semtech.com/search/results?q=LR2021+errata
- HTTP status: `n/a`
- version/revision: `n/a`
- retrieval date: n/a (per-attempt date not recorded; source retrieval session 2026-09-30T23:30Z–2026-09-30T23:35Z)
- file size: `n/a`
- sha256: `n/a`
- status: `FAILED`
- FAILED reason: attempted (see F5 pattern); no API

### F7 — Semtech technical-support (KB entry point)
- local path: `n/a` (no artifact retrieved)
- origin URL: https://www.semtech.com/support/technical-support
- HTTP status: `404`
- version/revision: `n/a`
- retrieval date: n/a (per-attempt date not recorded; source retrieval session 2026-09-30T23:30Z–2026-09-30T23:35Z)
- file size: `n/a`
- sha256: `n/a`
- status: `FAILED`
- FAILED reason: 404

### F8 — Semtech quality / PCN page
- local path: `n/a` (no artifact retrieved)
- origin URL: https://www.semtech.com/quality
- HTTP status: `200`
- version/revision: `n/a`
- retrieval date: n/a (per-attempt date not recorded; source retrieval session 2026-09-30T23:30Z–2026-09-30T23:35Z)
- file size: `n/a`
- sha256: `n/a`
- status: `FAILED`
- FAILED reason: zero `errata/erratum` matches

### F9 — DuckDuckGo HTML search
- local path: `n/a` (no artifact retrieved)
- origin URL: https://html.duckduckgo.com/html/?q=LR2021+errata+semtech
- HTTP status: `202`
- version/revision: `n/a`
- retrieval date: n/a (per-attempt date not recorded; source retrieval session 2026-09-30T23:30Z–2026-09-30T23:35Z)
- file size: `n/a`
- sha256: `n/a`
- status: `FAILED`
- FAILED reason: bot challenge; no results parsed

### F10 — GitHub global search/repositories q='LR2021 errata'
- local path: `n/a` (no artifact retrieved)
- origin URL: GitHub search API `search/repositories` (q='LR2021 errata')
- HTTP status: `n/a`
- version/revision: `n/a`
- retrieval date: n/a (per-attempt date not recorded; source retrieval session 2026-09-30T23:30Z–2026-09-30T23:35Z)
- file size: `n/a`
- sha256: `n/a`
- status: `FAILED`
- FAILED reason: total_count 0

### F11 — GitHub global search/issues q='LR2021 errata'
- local path: `n/a` (no artifact retrieved)
- origin URL: GitHub search API `search/issues` (q='LR2021 errata')
- HTTP status: `n/a`
- version/revision: `n/a`
- retrieval date: n/a (per-attempt date not recorded; source retrieval session 2026-09-30T23:30Z–2026-09-30T23:35Z)
- file size: `n/a`
- sha256: `n/a`
- status: `FAILED`
- FAILED reason: total_count 2; neither is a Semtech errata sheet (ScotMesh/RepeaterTastic #3; LilyGO/T-Display-P4 #11)

### F12 — GitHub global search/code q='LR2021 errata'
- local path: `n/a` (no artifact retrieved)
- origin URL: GitHub search API `search/code` (q='LR2021 errata')
- HTTP status: `n/a`
- version/revision: `n/a`
- retrieval date: n/a (per-attempt date not recorded; source retrieval session 2026-09-30T23:30Z–2026-09-30T23:35Z)
- file size: `n/a`
- sha256: `n/a`
- status: `FAILED`
- FAILED reason: total_count 91; no errata document (hits are SX126x/LoRaWAN sources and third-party READMEs)

### F13 — RadioLib repo tree scan
- local path: `n/a` (no artifact retrieved)
- origin URL: GitHub API `repos/jgromes/RadioLib/git/trees/master?recursive=1` grep `errata|limitation`
- HTTP status: `n/a`
- version/revision: `n/a`
- retrieval date: n/a (per-attempt date not recorded; source retrieval session 2026-09-30T23:30Z–2026-09-30T23:35Z)
- file size: `n/a`
- sha256: `n/a`
- status: `FAILED`
- FAILED reason: 0 files

### F14 — RadioLib contents/docs
- local path: `n/a` (no artifact retrieved)
- origin URL: `.../contents/docs` (jgromes/RadioLib)
- HTTP status: `404`
- version/revision: `n/a`
- retrieval date: n/a (per-attempt date not recorded; source retrieval session 2026-09-30T23:30Z–2026-09-30T23:35Z)
- file size: `n/a`
- sha256: `n/a`
- status: `FAILED`
- FAILED reason: no `docs/` directory

### F15 — RadioLib root changelog
- local path: `n/a` (no artifact retrieved)
- origin URL: https://raw.githubusercontent.com/jgromes/RadioLib/master/CHANGELOG.md
- HTTP status: `404`
- version/revision: `n/a`
- retrieval date: n/a (per-attempt date not recorded; source retrieval session 2026-09-30T23:30Z–2026-09-30T23:35Z)
- file size: `n/a`
- sha256: `n/a`
- status: `FAILED`
- FAILED reason: no root changelog

### F16 — GitHub search/issues q='repo:jgromes/RadioLib errata'
- local path: `n/a` (no artifact retrieved)
- origin URL: GitHub search API `search/issues` (q='repo:jgromes/RadioLib errata')
- HTTP status: `n/a`
- version/revision: `n/a`
- retrieval date: n/a (per-attempt date not recorded; source retrieval session 2026-09-30T23:30Z–2026-09-30T23:35Z)
- file size: `n/a`
- sha256: `n/a`
- status: `FAILED`
- FAILED reason: total_count 13; none LR2021 (SX126x #1715/#65, SX127x, CC1101, LoRaWAN, …)

### F17 — RadioLib in-tree LR2021-module scan
- local path: `n/a` (no artifact retrieved)
- origin URL: in-tree scan of `LR2021-module/` (jgromes/RadioLib master)
- HTTP status: `n/a`
- version/revision: `n/a`
- retrieval date: n/a (per-attempt date not recorded; source retrieval session 2026-09-30T23:30Z–2026-09-30T23:35Z)
- file size: `n/a`
- sha256: `n/a`
- status: `FAILED`
- FAILED reason: no file named `*errata*`; only workaround/limitation references (see R7)

### F18 — LoRa Alliance site-search for "LR2021"
- local path: `n/a` (no artifact retrieved)
- origin URL: https://lora-alliance.org/?s=LR2021
- HTTP status: `200`
- version/revision: `n/a`
- retrieval date: n/a (per-attempt date not recorded; source retrieval session 2026-09-30T23:30Z–2026-09-30T23:35Z)
- file size: `n/a`
- sha256: `n/a`
- status: `FAILED`
- FAILED reason: no results

### F19 — LoRa Alliance resource hub
- local path: `n/a` (no artifact retrieved)
- origin URL: https://lora-alliance.org/resource_hub/
- HTTP status: `200`
- version/revision: `n/a`
- retrieval date: n/a (per-attempt date not recorded; source retrieval session 2026-09-30T23:30Z–2026-09-30T23:35Z)
- file size: `n/a`
- sha256: `n/a`
- status: `FAILED`
- FAILED reason: zero `LR2021|LR20xx` matches

### §3.5 — Semtech KB / support articles referencing LR2021 known issues
- local path: `n/a` (no artifact retrieved)
- origin URL: `n/a` (source §3.5 re-references the F5/F6/F7 URLs; no separate URL)
- HTTP status: `n/a`
- version/revision: `n/a`
- retrieval date: n/a (per-attempt date not recorded; source retrieval session 2026-09-30T23:30Z–2026-09-30T23:35Z)
- file size: `n/a`
- sha256: `n/a`
- status: `FAILED`
- FAILED reason: NOT FOUND after 3 attempts (F5, F6, F7); public KB entry point behind login/404

---

## Non-entry notes for the merge step (sourcing only, no technical conclusions)

Recorded so the merge step can see, rather than infer, which source items are retrievals
and which are not. Neither list below is a retrieval entry, so neither is counted above.

1. Source §1 artifacts E1–E3 map onto retrieval blocks already emitted above — emitting them
   again would duplicate a retrieval:
   - E1 (datasheet Rev 2.2 §22) ↔ R1
   - E2 (`doc/KNOWN_LIMITATIONS.md`) ↔ R2
   - E3 (`lr20xx_workarounds.{h,c}` + driver README "Workarounds" section) ↔ R3, R4, R5, R6
2. Source §3.2 is a table of four in-repo documents scanned locally for the terms
   `errata|erratum|known issue` (all 0 matches). These are local content scans of already-
   retrieved documents, not retrievals: no origin URL, HTTP status or retrieval was recorded
   for them, so they are not emitted as entries. Documents: `LR2021_LR2022_LR2012_Datasheet_v2.2.pdf`
   (0; has §22), `AN1200.101_LR2021_FLRC_Improvements.pdf` (0),
   `AN1200.102_LR20xx_LoRaImprovements_Rev1.1.pdf` (0), `AN1200.104_LR20xx_ModemInterface_v1.0.pdf` (0).
3. Source §2 R9 records an earlier committed snapshot of the same product page at
   `docs/lr2021-research/datasheets/semtech-lr2021-product-page.html.gz` (+ `.txt`); that artifact
   belongs to the datasheets category, not this fragment, and is not re-counted here.

END OF FRAGMENT
