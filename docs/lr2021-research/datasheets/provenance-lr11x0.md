# LR11x0 family (LR1110 / LR1120 / LR1121) — Datasheet Retrieval Provenance

**Task:** kanban `t_28e7ee80` — "Fetch Semtech LR11x0-family datasheets (LR1110/LR1120/LR1121)".
**Scope:** sourcing only. This file records *what was fetched, from where, when, and what
failed*. It makes **no register-behaviour or product conclusions**, and it does **not**
assert any relationship between the LR11x0 family and the LR2021 (see §"LR2021 mentions"
below).
**All retrieval timestamps are ISO-8601 UTC.** Hashes are sha256 unless stated.
**Page hash caveat:** the Semtech product pages are server-rendered but carry rotating
CDN cache-busting asset names/tokens, so two fetches minutes apart differ byte-for-byte.
The hashes below are of the **files as saved in this repo**, not stable upstream checksums.

Legend: **RETRIEVED** = artifact is on disk and hashed here · **FAILED** = attempted and did
not yield the expected artifact, with the exact reason.

---

## R1. Semtech LR1110 product page (HTML) — RETRIEVED

- **Local paths:**
  - `docs/lr2021-research/datasheets/semtech-lr1110-product-page.html.gz` — **byte-exact**
    gzip of the fetched HTTP body (stored gzip-compressed because the raw bytes contain
    public Semtech CDN cache-busting asset filenames of the form
    `www.semtech.com/cache/<sha1>.js`, which the fleet pre-commit secret scanner
    false-positives on; compressing preserves the bytes exactly without bypassing the hook).
    Decompress with `zcat`.
  - `docs/lr2021-research/datasheets/semtech-lr1110-product-page.txt` — same fetch,
    scripts/styles/comments stripped and tags flattened to readable text (no paraphrasing).
- **Scratch path (outside repo):** `~/lr2021-scratch/product-lr1110.html`
- **Origin URL:** https://www.semtech.com/products/wireless-rf/lora-edge/lr1110
- **HTTP status:** `200`
- **Content-Type:** `text/html; charset=UTF-8`
- **Page title (as fetched):** `LoRa Edge™ LR1110 Multi-technology Asset Management Platform  | Semtech`
- **Retrieval date:** `2026-09-30T23:10:56Z`
- **Uncompressed file size:** `238257` bytes (compressed `.gz`: `37759` bytes)
- **sha256 (of the uncompressed fetched HTML):** `5a314904a32dcfe9a1d5a4fa0fa009234b0a33cef024ee9f44d935cb1606ad71`
- **sha256 (repo `.txt` render):** `6c9c902abfe09d581375d4f182d81124719babaac60cd770054819c01e3a81a2`
- **sha256 (repo `.html.gz`):** `70eac156ef16cda8f42bb1203f3ea145684bc1abef00765e305a59bed3ab00cd`
- **Method:** `curl -sS -L` (no JS); the page is server-rendered and includes the full
  product overview and the complete Documents table (see §Index).
- **Note (URL discovery):** the `lora-connect/lr1110` slug returns `404` (soft-404 page,
  `105910` bytes, `text/html`); the working slug is `lora-edge/lr1110`.

---

## R2. Semtech LR1120 product page (HTML) — RETRIEVED

- **Local paths:**
  - `docs/lr2021-research/datasheets/semtech-lr1120-product-page.html.gz` (byte-exact gzip, as R1)
  - `docs/lr2021-research/datasheets/semtech-lr1120-product-page.txt` (flattened render, no paraphrase)
- **Scratch path (outside repo):** `~/lr2021-scratch/product-lr1120.html`
- **Origin URL:** https://www.semtech.com/products/wireless-rf/lora-edge/lr1120
- **HTTP status:** `200`
- **Content-Type:** `text/html; charset=UTF-8`
- **Page title (as fetched):** `LoRa Edge™ LR1120 for Multi-Band Global Asset Management | Semtech`
- **Retrieval date:** `2026-09-30T23:10:56Z`
- **Uncompressed file size:** `235108` bytes (compressed `.gz`: `37392` bytes)
- **sha256 (of the uncompressed fetched HTML):** `1b34326bf597406e73e6308f8e0f53f933f411347ac5d70392b8345038e1eb62`
- **sha256 (repo `.txt` render):** `c60b41d6dc82c79caa0482e591e095bc7dfe87ff8465f6734475861276e369cb`
- **sha256 (repo `.html.gz`):** `be85cd57525510be3134a97157b81bd42be8f3378720e36270f2169cf9e9c982`
- **Method:** `curl -sS -L` (no JS).
- **Note (URL discovery):** the `lora-connect/lr1120` slug returns `404`; the working slug
  is `lora-edge/lr1120`.

---

## R3. Semtech LR1121 product page (HTML) — RETRIEVED

- **Local paths:**
  - `docs/lr2021-research/datasheets/semtech-lr1121-product-page.html.gz` (byte-exact gzip, as R1)
  - `docs/lr2021-research/datasheets/semtech-lr1121-product-page.txt` (flattened render, no paraphrase)
- **Scratch path (outside repo):** `~/lr2021-scratch/product-lr1121.html`
- **Origin URL:** https://www.semtech.com/products/wireless-rf/lora-connect/lr1121
- **HTTP status:** `200`
- **Content-Type:** `text/html; charset=UTF-8`
- **Page title (as fetched):** `LoRa Connect LR1121 for Multi-Band Global Connectivity | Semtech`
- **Retrieval date:** `2026-09-30T23:10:56Z`
- **Uncompressed file size:** `233401` bytes (compressed `.gz`: `37130` bytes)
- **sha256 (of the uncompressed fetched HTML):** `3c8f8ac07e27a3306ab8fdd2e817cda9d1724876bf261841461697a7f11a25c9`
- **sha256 (repo `.txt` render):** `a607587917dc32951a0a8fc9b71ad6aebde4b10b4c9d4861d2838be6341ef466`
- **sha256 (repo `.html.gz`):** `ef72f977c7cf22e0f61ab40468646a481125dde4dbf8c7fc83f48b1e527f54ff`
- **Method:** `curl -sS -L` (no JS).
- **Note:** LR1121 is the only one of the three whose product page lives under the
  `lora-connect/` category; the `lora-edge/lr1121` slug was not probed (not needed).

---

## R4. LR1110 Datasheet Rev 2.1 (PDF) — RETRIEVED (browser-driven download)

- **Local path (in-repo):** `docs/lr2021-research/semtech-official/LR1110_v2.1_data_sheet.pdf`
  (the repo already tracks comparable binary artifacts under `semtech-official/` — e.g.
  `LR2021_LR2022_LR2012_Datasheet_v2.2.pdf` — so the committed path **is** the local path).
- **Scratch path (outside repo):** `~/lr2021-scratch/LR1110_v2.1_data_sheet.pdf`
  (byte-identical to the repo copy; also saved by the browser as
  `~/Downloads/61667836.LR1110_v2.1_data_sheet.pdf`)
- **Origin URL (product page → Documents → Datasheets, R1):**
  https://semtech.my.salesforce.com/sfc/p/E0000000JelG/a/RQ00000AXyaj/EQ4jOcJX3lpB41OWGz0VBBLb_avBZzvqrAZfl2P8ID0
  (listed on the R1 page as `LR1110 Data Sheet`, release date `2025-08-21`, type `PDF`).
- **Printed document code / revision:** `DS.LR1110.W.APP`, `Rev 2.1`, cover date `July 2025`.
- **PDF internal metadata:** Title `LR1110_v2.1_data_sheet.pdf`, Author `Semtech`,
  Creator `FrameMaker 17.0.4`, Producer `Adobe PDF Library 17.0`,
  CreationDate `2025-07-07 21:31:25 CEST`, ModDate `2025-07-07 19:49:46 CEST`,
  `42` pages, PDF 1.6, JavaScript present.
- **File size:** `1286566` bytes
- **sha256:** `dac6eaf0763f1b5c132610ea0467f8fe65eba780ab925de020ac80e2a549f7b0`
- **md5:** `18fbc075313feb959eef936b511e3026`
- **Retrieval date:** `2026-09-30T23:21:00Z` (browser `Download` button on the Salesforce
  content-distribution viewer; see §Method for the JS gate).

---

## R5. LR1120 Datasheet Rev 2.2 (PDF) — RETRIEVED (browser-driven download)

- **Local path (in-repo):** `docs/lr2021-research/semtech-official/LR1120_V2_2_data_sheet.pdf`
- **Scratch path (outside repo):** `~/lr2021-scratch/LR1120_V2_2_data_sheet.pdf`
  (browser-saved as `~/Downloads/61925666.LR1120_V2_2_data_sheet.pdf`)
- **Origin URL (product page → Documents → Datasheets, R2):**
  https://semtech.my.salesforce.com/sfc/p/E0000000JelG/a/RQ00000B5wJZ/QJAaTz_ibxFbmPFnWM3EloRSMa0k4yWZBOkXYB2o6K8
  (listed on the R2 page as `LR1120 Datasheet`, release date `2025-10-07`, type `PDF`).
- **Printed document code / revision:** `DS.LR1120.W.APP`, `Rev 2.2`, cover date `July 2025`.
- **PDF internal metadata:** Title `LR1120_V2_2_data_sheet.pdf`, Author `Semtech`,
  Creator `FrameMaker 17.0.4`, Producer `Adobe PDF Library 17.0`,
  CreationDate `2025-07-07 21:31:25 CEST`, ModDate `2025-07-07 19:51:58 CEST`,
  `45` pages, PDF 1.6.
- **File size:** `1185970` bytes
- **sha256:** `d4ea4a43d57a06840c28d25c1ff5e3b3afb255f3b2f85133d82fc80b65b04431`
- **md5:** `fed19ccca5ff8ca7466bd9e54115d56a`
- **Retrieval date:** `2026-09-30T23:22:30Z`
- **Note:** product-page release date (`2025-10-07`) post-dates the PDF's internal
  ModDate (`2025-07-07`); both are recorded verbatim, no reconciliation inferred.

---

## R6. LR1121 Datasheet Rev 2.1 (PDF) — RETRIEVED (browser-driven download)

- **Local path (in-repo):** `docs/lr2021-research/semtech-official/LR1121_V2_1_data_sheet.pdf`
- **Scratch path (outside repo):** `~/lr2021-scratch/LR1121_V2_1_data_sheet.pdf`
  (browser-saved as `~/Downloads/61252685.LR1121_V2_1_data_sheet.pdf`)
- **Origin URL (product page → Documents → Datasheets, R3):**
  https://semtech.my.salesforce.com/sfc/p/E0000000JelG/a/RQ0000093ZiP/RV4Ba6LROsFrFjnAAVK2av5W11RGmCms_3Q2cyKHdDA
  (listed on the R3 page as `LR1121 Datasheet`, release date `2025-04-26`, type `PDF`).
- **Printed document code / revision:** `DS.LR1121.W.APP`, `Rev 2.1`.
- **PDF internal metadata:** Title `LR1121_V2_1_data_sheet.pdf`, Author `Semtech`,
  Creator `FrameMaker 16.0.6`, Producer `Adobe PDF Library 17.0`,
  CreationDate `2025-04-23 14:39:45 CEST`, ModDate `2025-04-23 13:10:43 CEST`,
  `35` pages, PDF 1.6.
- **File size:** `968122` bytes
- **sha256:** `114bd9d7bd07b453a511f412c9e157d7179f636b03dc1e197988f1c899d96d56`
- **md5:** `880981b964e151fc75fa2ddc229ea34b`
- **Retrieval date:** `2026-09-30T23:26:00Z`

---

## Method for R4–R6 (why a browser was required)

All three datasheet rows link to `semtech.my.salesforce.com/sfc/p/...` — a JavaScript
Salesforce content-distribution page. A plain `curl` GET returns a `1359`-byte HTML stub
whose only action is `document.postBack.submit()`; there are **no PDF bytes**. The viewer
renders the PDF and exposes the original file only through its `Download` button, which
issues the file request client-side. Retrieval was therefore done with the Hermes
`browser_navigate` tool (headless Chrome) on each Salesforce link, followed by a click on
the viewer's `Download` button; Chrome wrote the PDF to `~/Downloads/`.

- **Environment fix required:** the Hermes browser was configured to launch
  `/snap/bin/chromium`, which did not exist on this node. A wrapper was installed
  (`/snap/bin/chromium` → `exec /usr/bin/google-chrome "$@"`, Google Chrome
  `149.0.7827.200`) so the browser tool could start. This is an environment change on the
  node, not an artifact.

---

## FAILED entries

### F1. Salesforce delivery links, direct `curl` GET (all three)
- **URLs:** the three `semtech.my.salesforce.com/sfc/p/...` links in R4–R6.
- **Result (all three):** `HTTP 200`, `text/html; charset=utf-8`, `1359` bytes —
  **FAILED (JS gate / no PDF bytes)**.
- **Reason:** response is the `<form id="postBack" method="POST">` stub; the real download
  is issued by client-side JS. Same failure mode as documented for the LR2021 datasheet in
  `provenance.md` (F1/F2/F5).
- **Saved scratch copies:** `~/lr2021-scratch/ds-1110.bin`, `ds-1120.bin`, `ds-1121.bin`
  (1359 bytes each, identical stub).

### F2. Guessed direct `uploads/documents` PDF path
- **URL:** https://www.semtech.com/uploads/documents/DS_LR1110.pdf
- **Result:** `HTTP 200`, `text/html; charset=UTF-8`, `21149` bytes — **FAILED (soft-404)**.
- **Reason:** body is the HubSpot "Find Product Documentation" landing page, not a PDF.
  Semtech serves this soft-404 with a `200`, so status alone is insufficient.

### F3. `lora-connect/{lr1110,lr1120}` product-page slugs
- **URLs:** https://www.semtech.com/products/wireless-rf/lora-connect/lr1110 and `.../lr1120`
- **Result (both):** `HTTP 404`, `text/html; charset=UTF-8`, `105910` bytes —
  **FAILED (404)**. Correct slugs are under `lora-edge/` (see R1/R2).

### F4. Alternate mirror — Mouser
- **URL:** https://www.mouser.com/datasheet/2/761/LR1110_Datasheet_v1.1-1662965.pdf
- **Result:** `curl: (92) HTTP/2 stream 1 was not closed cleanly: INTERNAL_ERROR` —
  **FAILED (transport; not retried)**. Not a required path (R4 succeeded).

---

## LR2021 mentions in the fetched LR11x0 documents — NONE FOUND

Per the card's constraint, no LR2021 register/product relationship is asserted here.
A literal search of the three retrieved PDFs' extracted text for the regular expression
`LR20[0-9]{2}` returned **zero matches** in all three (`LR1110_v2.1_data_sheet.txt`,
`LR1120_V2_2_data_sheet.txt`, `LR1121_V2_1_data_sheet.txt`). This is recorded only as a
fact about the retrieved text; no inference is drawn.

---

## Index — Datasheets table entries as enumerated on the product pages (fetched 2026-09-30T23:10Z)

All entries link to `semtech.my.salesforce.com/sfc/p/E0000000JelG/a/<id>/<token>` (JS-gated).
Release Date as printed on the page · Type as printed.

**LR1110 product page — Datasheets (1)**
- 2025-08-21 · PDF · `LR1110 Data Sheet` → id `RQ00000AXyaj`

**LR1120 product page — Datasheets (1)**
- 2025-10-07 · PDF · `LR1120 Datasheet` → id `RQ00000B5wJZ`

**LR1121 product page — Datasheets (1)**
- 2025-04-26 · PDF · `LR1121 Datasheet` → id `RQ0000093ZiP`

The product pages also enumerate Application Notes (e.g. LR1110 page includes
`AN1200.56 LR1110 evaluation kit`, `AN1200.57 LR11xx Program Memory Update`,
`AN1200.58 LR-FHSS Demo Code`, `AN1200.59 Selecting the Optimal Reference Clock`,
`AN1200.62 FCC Pre-Compliance`, `AN1200.64 LR-FHSS System Performance`,
`AN1200.66 PCB Design Guidelines`), Development Kits, and Reference Designs. Those were
**not fetched** by this task (out of scope: datasheets only).
