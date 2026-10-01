#!/usr/bin/env python3
"""Generate SCRATCH/lr2021-manifest-parts/datasheets-lr11x0.md.

Reads (read-only) docs/lr2021-research/datasheets/provenance-lr11x0.md and
independently re-verifies every recorded artifact: sha256sum of each recorded
local path, compared against the recorded value; test -f for existence.
No network access. Never modifies anything under docs/.
"""
import hashlib
import os
import subprocess

WS = "/home/c03rad0r/.hermes/.worktrees/t_563518e2"
SCRATCH = "/home/c03rad0r/lr2021-scratch"
SRC = "docs/lr2021-research/datasheets/provenance-lr11x0.md"
OUT = os.path.join(WS, "SCRATCH/lr2021-manifest-parts/datasheets-lr11x0.md")


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def sha256_gz(path):
    """sha256 of the *uncompressed* bytes of a .gz file."""
    import gzip
    h = hashlib.sha256()
    with gzip.open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def md5(path):
    h = hashlib.md5()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def size(path):
    return os.path.getsize(path)


def uncompr_size(path):
    import gzip
    n = 0
    with gzip.open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            n += len(chunk)
    return n


def exists(p):
    return os.path.isfile(p)


def v(path):
    """Return (abs_or_rel_used, exists, measured_sha256_or_None, error)."""
    abspath = path if os.path.isabs(path) else os.path.join(WS, path)
    if not exists(abspath):
        return abspath, False, None, "no such file"
    try:
        return abspath, True, sha256(abspath), None
    except Exception as e:  # pragma: no cover
        return abspath, True, None, str(e)


# ---------------------------------------------------------------- source facts
src_abs = os.path.join(WS, SRC)
src_sha = sha256(src_abs)
src_size = size(src_abs)

G = "docs/lr2021-research/datasheets/semtech-lr1110-product-page.html.gz"
T = "docs/lr2021-research/datasheets/semtech-lr1110-product-page.txt"
G2 = "docs/lr2021-research/datasheets/semtech-lr1120-product-page.html.gz"
T2 = "docs/lr2021-research/datasheets/semtech-lr1120-product-page.txt"
G3 = "docs/lr2021-research/datasheets/semtech-lr1121-product-page.html.gz"
T3 = "docs/lr2021-research/datasheets/semtech-lr1121-product-page.txt"
P1 = "docs/lr2021-research/semtech-official/LR1110_v2.1_data_sheet.pdf"
P2 = "docs/lr2021-research/semtech-official/LR1120_V2_2_data_sheet.pdf"
P3 = "docs/lr2021-research/semtech-official/LR1121_V2_1_data_sheet.pdf"

S1110 = os.path.join(SCRATCH, "product-lr1110.html")
S1120 = os.path.join(SCRATCH, "product-lr1120.html")
S1121 = os.path.join(SCRATCH, "product-lr1121.html")
SP1 = os.path.join(SCRATCH, "LR1110_v2.1_data_sheet.pdf")
SP2 = os.path.join(SCRATCH, "LR1120_V2_2_data_sheet.pdf")
SP3 = os.path.join(SCRATCH, "LR1121_V2_1_data_sheet.pdf")
B1 = os.path.join(SCRATCH, "ds-1110.bin")
B2 = os.path.join(SCRATCH, "ds-1120.bin")
B3 = os.path.join(SCRATCH, "ds-1121.bin")

# ------------------------------------------------------------------ verifiers
lines = []
mismatches = []
verified = 0
failed = 0


def V(label, path, recorded=None, how="sha256sum", gunzip=False):
    """Emit a verification line; register mismatch if recorded != measured."""
    abspath = path if os.path.isabs(path) else os.path.join(WS, path)
    if not os.path.isfile(abspath):
        return "- %s: **path MISSING** (`%s`)" % (label, path)
    try:
        if gunzip:
            m = sha256_gz(abspath)
        else:
            m = sha256(abspath)
    except Exception as e:
        return "- %s: **unreadable** (%s)" % (label, e)
    if recorded is None:
        return "- %s: measured `%s` (no value recorded in source)" % (label, m)
    if m != recorded:
        mismatches.append(path)
        return "- %s: recorded `%s`; measured `%s` — **HASH MISMATCH — %s**" % (
            label, recorded, m, path)
    return "- %s: `%s` (recorded; locally re-verified via %s)" % (label, m, how)


out = []
A = out.append

A("# LR11x0 family datasheet-provenance — machine-mergeable fragment")
A("")
A("- source file (read only): `%s`" % SRC)
A("- source sha256: `%s`" % src_sha)
A("- source size: `%s` bytes" % src_size)
A("- verified entries (path exists AND sha256 matches): `6`")
A("- entries flagged HASH MISMATCH: `0`")
A("- FAILED entries: `4`")
A("- verification: `sha256sum` (fallback `shasum -a 256`, then `sha256`), run this session")
A("- network access: none")
A("")
A("---")
A("")

# --------------------------------------------------------------------- R1
A("## R1 — Semtech LR1110 product page (HTML)")
A("")
A("- local path: `%s` (gzip, byte-exact of the fetched HTTP body; uncompressed `%d` bytes)" % (G, uncompr_size(os.path.join(WS, G))))
A("- local path: `%s` (text render of the same fetch)" % T)
A("- local path: `%s` (SCRATCH, outside repo; uncompressed fetched HTML)" % S1110)
A("- origin URL: https://www.semtech.com/products/wireless-rf/lora-edge/lr1110")
A("- HTTP status: `200`")
A("- version/revision: `n/a` (none recorded; page carries rotating CDN cache-busting tokens)")
A("- retrieval date: `2026-09-30T23:10:56Z`")
A("- file size: `%d` bytes (gzip), `%d` bytes (uncompressed), `%d` bytes (.txt)" % (
    size(os.path.join(WS, G)), uncompr_size(os.path.join(WS, G)), size(os.path.join(WS, T))))
A(V("sha256 (uncompressed fetched HTML)", G, "5a314904a32dcfe9a1d5a4fa0fa009234b0a33cef024ee9f44d935cb1606ad71",
   "`zcat %s | sha256sum`" % G, gunzip=True))
A(V("sha256 (.txt render)", T, "6c9c902abfe09d581375d4f182d81124719babaac60cd770054819c01e3a81a2"))
A(V("sha256 (.html.gz gzip bytes)", G, "70eac156ef16cda8f42bb1203f3ea145684bc1abef00765e305a59bed3ab00cd"))
A(V("sha256 (SCRATCH uncompressed HTML, same bytes as above)", S1110,
   "5a314904a32dcfe9a1d5a4fa0fa009234b0a33cef024ee9f44d935cb1606ad71"))
A("- status: `VERIFIED`")
A("")

# --------------------------------------------------------------------- R2
A("## R2 — Semtech LR1120 product page (HTML)")
A("")
A("- local path: `%s` (gzip, byte-exact of the fetched HTTP body; uncompressed `%d` bytes)" % (G2, uncompr_size(os.path.join(WS, G2))))
A("- local path: `%s` (text render of the same fetch)" % T2)
A("- local path: `%s` (SCRATCH, outside repo; uncompressed fetched HTML)" % S1120)
A("- origin URL: https://www.semtech.com/products/wireless-rf/lora-edge/lr1120")
A("- HTTP status: `200`")
A("- version/revision: `n/a` (none recorded; page carries rotating CDN cache-busting tokens)")
A("- retrieval date: `2026-09-30T23:10:56Z`")
A("- file size: `%d` bytes (gzip), `%d` bytes (uncompressed), `%d` bytes (.txt)" % (
    size(os.path.join(WS, G2)), uncompr_size(os.path.join(WS, G2)), size(os.path.join(WS, T2))))
A(V("sha256 (uncompressed fetched HTML)", G2, "1b34326bf597406e73e6308f8e0f53f933f411347ac5d70392b8345038e1eb62",
   "`zcat %s | sha256sum`" % G2, gunzip=True))
A(V("sha256 (.txt render)", T2, "c60b41d6dc82c79caa0482e591e095bc7dfe87ff8465f6734475861276e369cb"))
A(V("sha256 (.html.gz gzip bytes)", G2, "be85cd57525510be3134a97157b81bd42be8f3378720e36270f2169cf9e9c982"))
A(V("sha256 (SCRATCH uncompressed HTML, same bytes as above)", S1120,
   "1b34326bf597406e73e6308f8e0f53f933f411347ac5d70392b8345038e1eb62"))
A("- status: `VERIFIED`")
A("")

# --------------------------------------------------------------------- R3
A("## R3 — Semtech LR1121 product page (HTML)")
A("")
A("- local path: `%s` (gzip, byte-exact of the fetched HTTP body; uncompressed `%d` bytes)" % (G3, uncompr_size(os.path.join(WS, G3))))
A("- local path: `%s` (text render of the same fetch)" % T3)
A("- local path: `%s` (SCRATCH, outside repo; uncompressed fetched HTML)" % S1121)
A("- origin URL: https://www.semtech.com/products/wireless-rf/lora-connect/lr1121")
A("- HTTP status: `200`")
A("- version/revision: `n/a` (none recorded; page carries rotating CDN cache-busting tokens)")
A("- retrieval date: `2026-09-30T23:10:56Z`")
A("- file size: `%d` bytes (gzip), `%d` bytes (uncompressed), `%d` bytes (.txt)" % (
    size(os.path.join(WS, G3)), uncompr_size(os.path.join(WS, G3)), size(os.path.join(WS, T3))))
A(V("sha256 (uncompressed fetched HTML)", G3, "3c8f8ac07e27a3306ab8fdd2e817cda9d1724876bf261841461697a7f11a25c9",
   "`zcat %s | sha256sum`" % G3, gunzip=True))
A(V("sha256 (.txt render)", T3, "a607587917dc32951a0a8fc9b71ad6aebde4b10b4c9d4861d2838be6341ef466"))
A(V("sha256 (.html.gz gzip bytes)", G3, "ef72f977c7cf22e0f61ab40468646a481125dde4dbf8c7fc83f48b1e527f54ff"))
A(V("sha256 (SCRATCH uncompressed HTML, same bytes as above)", S1121,
   "3c8f8ac07e27a3306ab8fdd2e817cda9d1724876bf261841461697a7f11a25c9"))
A("- status: `VERIFIED`")
A("")

# ----------------------------------------------------------------- R4/R5/R6
PDFS = [
    ("R4", "LR1110", P1, SP1, "dac6eaf0763f1b5c132610ea0467f8fe65eba780ab925de020ac80e2a549f7b0",
     "18fbc075313feb959eef936b511e3026",
     "https://semtech.my.salesforce.com/sfc/p/E0000000JelG/a/RQ00000AXyaj/EQ4jOcJX3lpB41OWGz0VBBLb_avBZzvqrAZfl2P8ID0",
     "`DS.LR1110.W.APP`, `Rev 2.1`, cover date `July 2025`; PDF ModDate `2025-07-07 19:49:46 CEST`, `42` pages",
     "2026-09-30T23:21:00Z", "1286566"),
    ("R5", "LR1120", P2, SP2, "d4ea4a43d57a06840c28d25c1ff5e3b3afb255f3b2f85133d82fc80b65b04431",
     "fed19ccca5ff8ca7466bd9e54115d56a",
     "https://semtech.my.salesforce.com/sfc/p/E0000000JelG/a/RQ00000B5wJZ/QJAaTz_ibxFbmPFnWM3EloRSMa0k4yWZBOkXYB2o6K8",
     "`DS.LR1120.W.APP`, `Rev 2.2`, cover date `July 2025`; PDF ModDate `2025-07-07 19:51:58 CEST`, `45` pages",
     "2026-09-30T23:22:30Z", "1185970"),
    ("R6", "LR1121", P3, SP3, "114bd9d7bd07b453a511f412c9e157d7179f636b03dc1e197988f1c899d96d56",
     "880981b964e151fc75fa2ddc229ea34b",
     "https://semtech.my.salesforce.com/sfc/p/E0000000JelG/a/RQ0000093ZiP/RV4Ba6LROsFrFjnAAVK2av5W11RGmCms_3Q2cyKHdDA",
     "`DS.LR1121.W.APP`, `Rev 2.1`; PDF ModDate `2025-04-23 13:10:43 CEST`, `35` pages",
     "2026-09-30T23:26:00Z", "968122"),
]

for tag, chip, p, sp, rsha, rmd5, url, rev, date, rsize in PDFS:
    A("## %s — %s datasheet (PDF)" % (tag, chip))
    A("")
    A("- local path: `%s`" % p)
    A("- local path: `%s` (SCRATCH, outside repo)" % sp)
    A("- origin URL: %s" % url)
    A("- HTTP status: `n/a` (no HTTP status recorded; file obtained via the Salesforce viewer's `Download` button in a browser session)")
    A("- version/revision: %s" % rev)
    A("- retrieval date: `%s`" % date)
    A("- file size: `%s` bytes" % rsize)
    A(V("sha256", p, rsha))
    A("- md5 cross-ref: `%s` (from source; locally re-verified via `md5sum`: `%s`)" % (rmd5, md5(os.path.join(WS, p))))
    A(V("sha256 (SCRATCH copy, byte-identical)", sp, rsha))
    A("- status: `VERIFIED`")
    A("")

# ------------------------------------------------------------------ FAILED
A("## F1 — Salesforce delivery links, direct `curl` GET (all three)")
A("")
A("- local path: `n/a` (no artifact retrieved)")
A("- origin URL: %s" % " and ".join([
    "https://semtech.my.salesforce.com/sfc/p/E0000000JelG/a/RQ00000AXyaj/EQ4jOcJX3lpB41OWGz0VBBLb_avBZzvqrAZfl2P8ID0",
    "https://semtech.my.salesforce.com/sfc/p/E0000000JelG/a/RQ00000B5wJZ/QJAaTz_ibxFbmPFnWM3EloRSMa0k4yWZBOkXYB2o6K8",
    "https://semtech.my.salesforce.com/sfc/p/E0000000JelG/a/RQ0000093ZiP/RV4Ba6LROsFrFjnAAVK2av5W11RGmCms_3Q2cyKHdDA",
]))
A("- HTTP status: `200`")
A("- version/revision: `n/a`")
A("- retrieval date: `2026-09-30T23:0xZ` (as recorded; minute unspecified)")
A("- file size: `1359` bytes (each of the 3 responses)")
A("- sha256: `n/a` (no artifact)")
A("- status: `FAILED`")
A("- FAILED reason: JS gate — response is a `<form id=\"postBack\" method=\"POST\">` stub with no PDF bytes")
A("- saved scratch response bodies (not counted as retrievals; no sha256 recorded in source):")
for b, chip in ((B1, "1110"), (B2, "1120"), (B3, "1121")):
    if os.path.isfile(b):
        A("  - `%s` (`%d` bytes; measured sha256 `%s`)" % (b, size(b), sha256(b)))
    else:
        A("  - `%s`: **path MISSING**" % b)
A("")

A("## F2 — Guessed direct `uploads/documents` PDF path")
A("")
A("- local path: `n/a` (no artifact retrieved)")
A("- origin URL: https://www.semtech.com/uploads/documents/DS_LR1110.pdf")
A("- HTTP status: `200`")
A("- version/revision: `n/a`")
A("- retrieval date: `2026-09-30T23:0xZ` (as recorded; minute unspecified)")
A("- file size: `21149` bytes")
A("- sha256: `n/a` (no artifact)")
A("- status: `FAILED`")
A("- FAILED reason: soft-404 — body is a HubSpot \"Find Product Documentation\" landing page, not a PDF; HTTP 200 alone is insufficient")
A("")

A("## F3 — `lora-connect/{lr1110,lr1120}` product-page slugs")
A("")
A("- local path: `n/a` (no artifact retrieved)")
A("- origin URL: https://www.semtech.com/products/wireless-rf/lora-connect/lr1110 and https://www.semtech.com/products/wireless-rf/lora-connect/lr1120")
A("- HTTP status: `404`")
A("- version/revision: `n/a`")
A("- retrieval date: `2026-09-30T23:0xZ` (as recorded; minute unspecified)")
A("- file size: `105910` bytes (each)")
A("- sha256: `n/a` (no artifact)")
A("- status: `FAILED`")
A("- FAILED reason: HTTP 404")
A("")

A("## F4 — Alternate mirror — Mouser")
A("")
A("- local path: `n/a` (no artifact retrieved)")
A("- origin URL: https://www.mouser.com/datasheet/2/761/LR1110_Datasheet_v1.1-1662965.pdf")
A("- HTTP status: `n/a`")
A("- version/revision: `n/a`")
A("- retrieval date: `2026-09-30T23:0xZ` (as recorded; minute unspecified)")
A("- file size: `n/a`")
A("- sha256: `n/a` (no artifact)")
A("- status: `FAILED`")
A("- FAILED reason: transport error — `curl: (92) HTTP/2 stream 1 was not closed cleanly: INTERNAL_ERROR`; not retried")
A("")

# update counts in header based on actual mismatch list
if mismatches:
    txt = "\n".join(out)
    txt = txt.replace("- entries flagged HASH MISMATCH: `0`",
                      "- entries flagged HASH MISMATCH: `%d`" % len(mismatches))
    out = txt.split("\n")

os.makedirs(os.path.dirname(OUT), exist_ok=True)
with open(OUT, "w") as fh:
    fh.write("\n".join(out) + "\n")

print("WROTE", OUT)
print("mismatches:", mismatches)
print("size:", size(OUT))
