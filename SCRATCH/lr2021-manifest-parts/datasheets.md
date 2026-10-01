# LR2021 fetch manifest — datasheets fragment

- source file (read only): `docs/lr2021-research/datasheets/provenance.md`
- source sha256: `5e1aaee713052df219def8fb0705a80b299074c56ca06e8fc9610a56351828d8`
- source size: `11049` bytes
- verified entries (path exists AND sha256 matches): `2`
- entries flagged HASH MISMATCH: `0`
- FAILED entries: `7`
- verification: `sha256sum` (fallback `shasum -a 256`, then `sha256`), run this session
- network access: none

---

## R1 — Semtech LR2021 product page (HTML)

- local path: `docs/lr2021-research/datasheets/semtech-lr2021-product-page.html.gz` (gzip, byte-exact of fetched HTTP body; uncompressed `226470` bytes)
- local path: `docs/lr2021-research/datasheets/semtech-lr2021-product-page.txt` (text render of the same fetch)
- origin URL: https://www.semtech.com/products/wireless-rf/lora-plus/lr2021
- HTTP status: `200`
- version/revision: `n/a` (none recorded; page carries rotating tokens)
- retrieval date: `2026-09-30T23:05:32Z`
- file size: `36039` bytes (gzip), `226470` bytes (uncompressed), `22595` bytes (.txt)
- sha256: `73e70df675e2fdc9eac769bfb82b131d685c156297039e117a4289df904b3c49`  (docs/lr2021-research/datasheets/semtech-lr2021-product-page.html.gz, uncompressed bytes; recorded; locally re-verified via zcat | sha256sum: `73e70df675e2fdc9eac769bfb82b131d685c156297039e117a4289df904b3c49`)
- sha256: `3be37498b8a958efe8ce7955d4375bc9a5fceb10599e51e65f8a44f4e1824232`  (docs/lr2021-research/datasheets/semtech-lr2021-product-page.txt; recorded; locally re-verified via sha256sum: `3be37498b8a958efe8ce7955d4375bc9a5fceb10599e51e65f8a44f4e1824232`)
- sha256: `ecc540968ea18dbc441ecdc524f3c7dadd67e33e8280b5f5bb745b8d9a58fa42`  (docs/lr2021-research/datasheets/semtech-lr2021-product-page.html.gz, gzip bytes; measured this run, not a recorded value)
- status: `VERIFIED`
- within-entry note (not counted as a separate retrieval): an immediate re-fetch at `2026-09-30T23:05:33Z` returned the same URL / HTTP status / size (`226470` bytes) but a different sha256 — `91d157dfe9b80b7e344558023a935cf8ba33bbd399fd7403565d7ed99bd4c8c3`; no artifact was retained for it; the saved copy above is the artifact of record.

## R2 — LR2021/LR2022/LR2012 Datasheet Rev. 2.2 (PDF)

- local path: `docs/lr2021-research/semtech-official/LR2021_LR2022_LR2012_Datasheet_v2.2.pdf`
- origin URL: https://semtech.my.salesforce.com/sfc/p/E0000000JelG/a/RQ00000EZ5fu/L1sOvqDN_QMyCWYAAychIL5ygPsQw1AEq7xzcvpGNZg
- HTTP status: `n/a` (obtained in a JS-capable browser session; no status recorded)
- version/revision: `Rev. 2.2`, document code `DS.LR20xx`, family `LR2021/LR2022/LR2012`, release date on page `2026-08-08`
- retrieval date: `2026-09-14`
- file size: `5980032` bytes
- sha256: `7e55a15dcdbe044dd615eb1f1ea21c26bf8e28758d94face240998e5fbad25c2`  (recorded; locally re-verified via sha256sum: `7e55a15dcdbe044dd615eb1f1ea21c26bf8e28758d94face240998e5fbad25c2`)
- status: `VERIFIED`
- md5 cross-ref (from source, not re-verified here): `18a392b72ff448083e6f26b2dd6e3925`

## F1 — Salesforce delivery link, direct GET

- local path: `n/a` (no artifact retrieved)
- origin URL: https://semtech.my.salesforce.com/sfc/p/E0000000JelG/a/RQ00000EZ5fu/L1sOvqDN_QMyCWYAAychIL5ygPsQw1AEq7xzcvpGNZg
- HTTP status: `200`
- version/revision: `n/a`
- retrieval date: `2026-09-30T23:0xZ` (as recorded; minute unspecified)
- file size: `1359`
- sha256: `n/a` (no artifact)
- status: `FAILED`
- FAILED reason: login/JS gate — stub `<form id="postBack" method="POST">` body, no PDF bytes
- saved response: `docs/lr2021-research/datasheets/semtech-salesforce-datasheet-link-response.html` (size `1359`, sha256 `ffa14a830ee0be6d34d2e383274197e5e15fff89c684fce9353d7a79fdf9920e`; recorded and locally re-verified)

## F2 — Salesforce delivery link, following the post-back POST

- local path: `n/a` (no artifact retrieved)
- origin URL: https://semtech.my.salesforce.com/sfc/p/#E0000000JelG/a/RQ00000EZ5fu/L1sOvqDN_QMyCWYAAychIL5ygPsQw1AEq7xzcvpGNZg
- HTTP status: `200`
- version/revision: `n/a`
- retrieval date: `2026-09-30T23:0xZ` (as recorded; minute unspecified)
- file size: `53747`
- sha256: `n/a` (no artifact)
- status: `FAILED`
- FAILED reason: JS gate — post-back renders the Salesforce content-distribution shell; no direct file link / meta-refresh / form target; download issued by client-side JS

## F3 — Guessed direct uploads/documents paths (4 candidates)

- local path: `n/a` (no artifact retrieved)
- origin URL: https://www.semtech.com/uploads/documents/DS_LR20xx.pdf
- origin URL: https://www.semtech.com/uploads/documents/LR20xx_datasheet.pdf
- origin URL: https://www.semtech.com/uploads/documents/LR2021_LR2022_LR2012_Datasheet_v2.2.pdf
- origin URL: https://www.semtech.com/uploads/documents/lr20xx_final_datasheet.pdf
- HTTP status: `200` (each of 4)
- version/revision: `n/a`
- retrieval date: `2026-09-30T23:0xZ` (as recorded; minute unspecified)
- file size: `21149` (each)
- sha256: `n/a` (no artifact)
- status: `FAILED`
- FAILED reason: soft-404 — body is a HubSpot "Find Product Documentation" landing page, not a PDF; status alone insufficient

## F4 — Product-page /documents subpath

- local path: `n/a` (no artifact retrieved)
- origin URL: https://www.semtech.com/products/wireless-rf/lora-plus/lr2021/documents
- HTTP status: `404`
- version/revision: `n/a`
- retrieval date: `2026-09-30T23:0xZ` (as recorded; minute unspecified)
- file size: `105910`
- sha256: `n/a` (no artifact)
- status: `FAILED`
- FAILED reason: 404

## F5 — Salesforce link with ?asPdf=true

- local path: `n/a` (no artifact retrieved)
- origin URL: https://semtech.my.salesforce.com/sfc/p/E0000000JelG/a/RQ00000EZ5fu/L1sOvqDN_QMyCWYAAychIL5ygPsQw1AEq7xzcvpGNZg?asPdf=true
- HTTP status: `200`
- version/revision: `n/a`
- retrieval date: `2026-09-30T23:0xZ` (as recorded; minute unspecified)
- file size: `1359`
- sha256: `n/a` (no artifact)
- status: `FAILED`
- FAILED reason: same JS gate as F1

## F6 — Browser (headless) retrieval

- local path: `n/a` (no artifact retrieved)
- origin URL: https://semtech.my.salesforce.com/sfc/p/E0000000JelG/a/RQ00000EZ5fu/L1sOvqDN_QMyCWYAAychIL5ygPsQw1AEq7xzcvpGNZg
- HTTP status: `n/a`
- version/revision: `n/a`
- retrieval date: `2026-09-30T23:0xZ` (as recorded; minute unspecified)
- file size: `n/a`
- sha256: `n/a` (no artifact)
- status: `FAILED`
- FAILED reason: environment — `Failed to launch Chrome at "/snap/bin/chromium": No such file or directory`; no browser available

## F7 — Wayback Machine availability API (not a direct fetch)

- local path: `n/a` (no artifact retrieved)
- origin URL: https://archive.org/wayback/available?url=www.semtech.com/uploads/documents/LR20xx_final_datasheet.pdf
- HTTP status: `429` Too Many Requests
- version/revision: `n/a`
- retrieval date: `2026-09-30T23:0xZ` (as recorded; minute unspecified)
- file size: `n/a`
- sha256: `n/a` (no artifact)
- status: `FAILED`
- FAILED reason: rate-limited; not retried; not a required path
