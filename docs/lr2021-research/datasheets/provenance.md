# LR2021 — Datasheet & Product Page Retrieval Provenance

**Task:** kanban `t_1c68efc3` — "Fetch Semtech LR2021 product page and official datasheet".
**Scope:** sourcing only. This file records *what was fetched, from where, when, and what
failed*. It makes **no register-behaviour or product conclusions**.
**All retrieval timestamps are ISO-8601 UTC.** Hashes are sha256 unless stated.
**Page hash caveat:** the Semtech product page is server-rendered but carries rotating
tokens/prices, so two fetches minutes apart differ byte-for-byte. The hash below is of the
**file as saved in this repo**, not a stable upstream checksum.

Legend: **RETRIEVED** = artifact is on disk and hashed here · **FAILED** = attempted and did
not yield the expected artifact, with the exact reason.

---

## R1. Semtech LR2021 product page (HTML) — RETRIEVED

- **Local paths:**
  - `docs/lr2021-research/datasheets/semtech-lr2021-product-page.html.gz` — **byte-exact**
    gzip of the fetched HTTP body (the raw `.html` is stored gzip-compressed because the
    raw bytes contain public Semtech CDN cache-busting asset filenames of the form
    `www.semtech.com/cache/<sha1>.js`, which the fleet pre-commit secret scanner
    false-positives on the z.ai-key pattern `[0-9a-f]{32}\.[A-Za-z0-9]{8,}`; compressing
    preserves the bytes exactly without bypassing the hook). Decompress with `zcat`.
  - `docs/lr2021-research/datasheets/semtech-lr2021-product-page.txt` — same fetch,
    scripts/styles/comments stripped and tags flattened to readable text (no paraphrasing;
    a lossless-visibility render). sha256 `3be37498b8a958efe8ce7955d4375bc9a5fceb10599e51e65f8a44f4e1824232`.
- **Origin URL:** https://www.semtech.com/products/wireless-rf/lora-plus/lr2021
- **HTTP status:** `200`
- **Content-Type:** `text/html; charset=UTF-8`
- **Page title (as fetched):** `LoRa Plus™ LR2021 | Fourth-generation LoRa® IP for Fast Long Range Communication (FLRC) | Semtech`
- **Product ID / part numbers listed on the page:** LR2021 (`LR2021IMLTRT`), LR2022 (`LR2022IMLTRT`)
- **Retrieval date:** `2026-09-30T23:05:32Z`
- **Uncompressed file size:** `226470` bytes (compressed `.gz`: `36039` bytes)
- **sha256 (of the uncompressed fetched HTML):** `73e70df675e2fdc9eac769bfb82b131d685c156297039e117a4289df904b3c49`
- **Method:** `curl -sS -L` (no JS); the page is server-rendered and includes the full
  product overview, features list, and the complete Documents table (see §Index below).
- **Note:** an immediate re-fetch at `2026-09-30T23:05:33Z` returned the same URL/HTTP
  status/size (`226470` bytes) but a different sha256
  (`91d157dfe9b80b7e344558023a935cf8ba33bbd399fd7403565d7ed99bd4c8c3`) — the page embeds
  rotating tokens. Only the saved copy (hash above) is the artifact of record.

---

## R2. LR2021/LR2022/LR2012 Datasheet Rev. 2.2 (PDF) — RETRIEVED (in-repo, browser-fetched)

- **Local path:** `docs/lr2021-research/semtech-official/LR2021_LR2022_LR2012_Datasheet_v2.2.pdf`
  (already tracked in this repo, added by kanban task `t_dbcc7e9a`, published 2026-10-01).
  The card's suggested `datasheets/` subdir was **not** used for a copy: the repo already
  tracks comparable binary artifacts under `semtech-official/`, so the committed path **is**
  the local path; duplicating a 5.7 MB PDF was avoided.
- **Origin URL (product page → Documents → Datasheets entry):**
  https://semtech.my.salesforce.com/sfc/p/E0000000JelG/a/RQ00000EZ5fu/L1sOvqDN_QMyCWYAAychIL5ygPsQw1AEq7xzcvpGNZg
  (listed on the product page as "LR2021/22/12 Datasheet v2.2", release date `2026-08-08`, type `PDF`).
- **Printed revision / part number:** `Rev. 2.2`, document code `DS.LR20xx`, family
  `LR2021/LR2022/LR2012`, cover reads "Final Datasheet Rev. 2.2". Part numbers on cover:
  `LR2021IMLTRT`, `LR2022IMLTRT`.
- **PDF internal metadata:** Title `LR20xx_final_datasheet.pdf`, Author `Semtech`,
  Producer `Adobe PDF Library 17.0`, CreationDate `2026-07-29 19:54:40 CEST`,
  ModDate `2026-07-29 18:19:17 CEST`, **250 pages**, PDF 1.6.
- **File size:** `5980032` bytes
- **sha256:** `7e55a15dcdbe044dd615eb1f1ea21c26bf8e28758d94face240998e5fbad25c2`
- **md5:** `18a392b72ff448083e6f26b2dd6e3925` (matches `SOURCES.md` A2; md5 kept for cross-ref)
- **Original retrieval date:** `2026-09-14` (via a JS-capable browser session — the Salesforce
  delivery link is a JavaScript content-distribution app; recorded by task `t_dbcc7e9a`).
- **Re-retrieval attempt (this task):** `2026-09-30T23:0xZ` via `curl` — **FAILED**, see F1/F2.
  The PDF bytes were not re-obtained by curl; the hashed artifact is the version already
  committed to this repo. Its content is verified here by `pdfinfo`/`pdftotext` (revision,
  page count, part numbers) rather than by a fresh download.

---

## FAILED entries — datasheet download attempts (curl, this task, 2026-09-30T23:0xZ)

Each was tried with `curl -sS -L -w '%{http_code} %{content_type} %{size_download}'`. A
`200` with `text/html` is a **soft-404 / JS gate**, i.e. **not** the PDF.

### F1. Salesforce delivery link, direct GET
- **URL:** https://semtech.my.salesforce.com/sfc/p/E0000000JelG/a/RQ00000EZ5fu/L1sOvqDN_QMyCWYAAychIL5ygPsQw1AEq7xzcvpGNZg
- **Result:** `HTTP 200`, `text/html; charset=utf-8`, `1359` bytes — **FAILED (login/JS gate)**
- **Reason:** response body is a stub `<form id="postBack" method="POST">` whose only action
  is `document.postBack.submit()`; **no PDF bytes**. Requires a JS-capable browser session.
- **Saved response:** `docs/lr2021-research/datasheets/semtech-salesforce-datasheet-link-response.html`
  (sha256 `ffa14a830ee0be6d34d2e383274197e5e15fff89c684fce9353d7a79fdf9920e`, 1359 bytes).

### F2. Salesforce delivery link, following the post-back POST
- **URL:** https://semtech.my.salesforce.com/sfc/p/#E0000000JelG/a/RQ00000EZ5fu/L1sOvqDN_QMyCWYAAychIL5ygPsQw1AEq7xzcvpGNZg
- **Request:** `POST compositePageName=E0000000JelG/a/RQ00000EZ5fu/L1sOvqDN_QMyCWYAAychIL5ygPsQw1AEq7xzcvpGNZg`
- **Result:** `HTTP 200`, `text/html; charset=UTF-8`, `53747` bytes — **FAILED (JS gate)**
- **Reason:** the post-back renders the Salesforce content-distribution shell (styled with
  `gc/contentDistribution.css`) with no direct file link / meta-refresh / form target to the
  PDF; the actual download is issued by client-side JS. Not scriptable via curl.

### F3. Guessed direct `uploads/documents` paths (4 candidates)
- https://www.semtech.com/uploads/documents/DS_LR20xx.pdf
- https://www.semtech.com/uploads/documents/LR20xx_datasheet.pdf
- https://www.semtech.com/uploads/documents/LR2021_LR2022_LR2012_Datasheet_v2.2.pdf
- https://www.semtech.com/uploads/documents/lr20xx_final_datasheet.pdf
- **Result (all 4):** `HTTP 200`, `text/html; charset=UTF-8`, `21149` bytes — **FAILED (soft-404)**
- **Reason:** the body is a HubSpot "Find Product Documentation" landing page, not a PDF.
  Semtech serves this soft-404 page with a `200` status, so status alone is not sufficient —
  content-type was checked.

### F4. Product-page `/documents` subpath
- **URL:** https://www.semtech.com/products/wireless-rf/lora-plus/lr2021/documents
- **Result:** `HTTP 404`, `text/html; charset=UTF-8`, `105910` bytes — **FAILED (404)**.

### F5. Salesforce link with `?asPdf=true`
- **URL:** …/RQ00000EZ5fu/L1sOvqDN_QMyCWYAAychIL5ygPsQw1AEq7xzcvpGNZg`?asPdf=true`
- **Result:** `HTTP 200`, `text/html; charset=utf-8`, `1359` bytes — **FAILED (same JS gate as F1)**.

### F6. Browser (headless) retrieval
- **Tool:** Hermes browser_navigate on the Salesforce link.
- **Result:** **FAILED (environment)** — `Failed to launch Chrome at "/snap/bin/chromium":
  No such file or directory`. No browser available in this execution environment, so the
  JS-gated download could not be driven.

### F7. Wayback Machine availability API (not a direct fetch)
- **URL:** https://archive.org/wayback/available?url=www.semtech.com/uploads/documents/LR20xx_final_datasheet.pdf
- **Result:** `HTTP 429 Too Many Requests` — **FAILED (rate-limited)**. Not retried; not a
  required path (the artifact is already in-repo via R2).

**Conclusion of FAILED set:** the official datasheet PDF is delivered only through a
JavaScript Salesforce content-distribution page and **cannot be fetched by curl**; it was
obtained once via a real browser session (R2) and is committed in this repo.

---

## Index — Documents table as enumerated on the product page (fetched 2026-09-30T23:05Z)

All entries link to `semtech.my.salesforce.com/sfc/p/E0000000JelG/a/<id>/<token>` (JS-gated).
Release Date as printed on the page · Type as printed.

**Datasheets (1)**
- 2026-08-08 · PDF · `LR2021/22/12 Datasheet v2.2` → id `RQ00000EZ5fu`

**Application Notes (14)**
- 2026-08-18 · PDF · `AN1200.101 - LR2021 FLRC Improvements` → `RQ00000EeWQv`
- 2026-07-02 · PDF · `AN1200.102 - LR20xx LoRa Improvements` → `RQ00000EB4bK`
- 2025-10-23 · PDF · `AN1200.103 - LR20xx CPFSK Modem Improvements v1.0` → `RQ00000BLYl7`
- 2025-10-31 · PDF · `AN1200.104 - LR20xx Modem Interface v1.0` → `RQ00000BReCj`
- 2025-10-25 · PDF · `AN1200.106 - LR20xx Xtal Temperature drift Mitigation v1.0` → `RQ00000BNEdR`
- 2025-12-18 · PDF · `AN1200.107 - LR20xx Analog Improvements Application Note` → `RQ00000C7IUL`
- 2025-10-28 · PDF · `AN1200.110 - LR20xx Evaluation Guide v1.0` → `RQ00000BOVyn`
- 2026-07-27 · PDF · `AN1200.112 - SubGHz FLRC Regulatory Measurement Reports v2.0` → `RQ00000EQc4n`
- 2025-10-23 · PDF · `AN1200.114 - LR20xx Ranging Demo v1.0` → `RQ00000BLVNS`
- 2026-09-16 · PDF · `AN1200.116 - LR20xx 1 Watt Reference Design Documentation and Regulatory Pre-Scan Report` → `RQ00000EvEB3`
- 2026-07-16 · PDF · `AN1200.59 - Selecting the Optimal Reference Clock` → `RQ00000EKp1X`
- 2026-05-20 · PDF · `AN1200.66: PCB Design Guidelines` → `RQ00000Dk9f7`
- 2026-09-11 · PDF · `AN1200.86 LoRa and LoRaWAN` → `RQ00000EsB85`
- 2026-09-10 · PDF · `AN1200.87 LoRaWAN Device Classes` → `RQ00000ErRlB`

**Test Reports (2, ZIP)**
- 2026-08-25 · ZIP · `LR2021 ref. design ETSI prescan Radio Test Report` → `RQ00000EhrsD`
- 2026-08-25 · ZIP · `LR2021 ref. design FCC Prescan Radio Test Report` → `RQ00000Ehryf`

**Reference Designs (3, ZIP)**
- 2026-08-18 · ZIP · `LR202x 490 MHz & 2.4 GHz Reference Design Files for CN490 region` → `RQ00000EeH25`
- 2026-08-18 · ZIP · `LR202x 868 MHz & 2.4 GHz Reference Design Files for EU868 region` → `RQ00000EeGfV`
- 2026-08-18 · ZIP · `LR202x 915 MHz & 2.4 GHz Reference Design Files for US915 region` → `RQ00000EeGqn`

**Document categories present on the page:** Datasheets, Application Notes, Reference
Designs, Test Reports, Software Releases (Firmware). There is **no errata category** —
consistent with `docs/lr2021-research/SOURCES.md` §C1 (no LR2021 errata sheet published).
This file records that observation only; it draws no errata conclusions.

**Dev kits listed (context, not fetches):** `LR2021EVK2XBS1` (EU868 + 2.4 GHz),
`LR2021EVK2XCS1` (NA915 + 2.4 GHz), `LR2021EVK2XGS1` (CN490 + 2.4 GHz).
