#!/usr/bin/env python3
"""Choose the 52 MHz crystal by PARSING the ERP name, which is where the spec actually lives.

Why this script exists: the list endpoint returns attribute NAMES with EMPTY values, and an empty
value read as "no constraint found" is how a wrong part gets chosen. The real spec is embedded in
`erpComponentName`, e.g. "52MHz +/-10ppm 8pF" -- so parse it.

Table 3-9 (Semtech SX1280/SX1281 Rev 3.2) requirements:
    F_XOSC   52 MHz
    C_LOAD   10 pF TYPICAL   <-- the datasheet's foot capacitance is INTERNAL and fixed, so the
                                 crystal must be specified AT 10 pF. A different C_LOAD will not
                                 sit on the right frequency.
    C0_XTAL  typ 2 pF, MAX 5 pF
    R_S_XTAL typ 10 ohm, MAX 50 ohm (up to 90 ohm if C0 < 3 pF)
    C_M_XTAL 3 .. 3.52 .. 4 fF

Selection rule, stated up front so it is not quietly bent to fit the cheapest part:
  1. frequency must be 52 MHz
  2. C_LOAD must be 10 pF  (REJECT 8 pF, 12 pF, 20 pF, or absent)
  3. then rank by: library tier (base > expand is NOT applicable here -- all were expand), then
     price, then stock
C0 / R_S are frequently absent from the ERP name; absent is reported as UNKNOWN, never as a pass.
"""
import json
import re
import subprocess

URL = ("https://jlcpcb.com/api/overseas-pcb-order/v1/shoppingCart/smtGood/"
       "selectSmtComponentList/v2")


def search(kw, size=60):
    body = {"currentPage": 1, "pageSize": size, "presaleType": "stock", "searchType": 2,
            "keyword": kw, "componentLibraryType": None, "stockFlag": None, "stockSort": None,
            "firstSortName": None, "secondSortName": None, "componentBrandList": [],
            "searchSource": "search", "componentSpecificationList": [],
            "componentAttributeList": [], "paramList": [], "startStockNumber": None,
            "sortMode": "", "sortASC": ""}
    p = subprocess.run(["curl", "-s", "-m", "60", "-X", "POST", URL,
                        "-H", "Content-Type: application/json",
                        "-H", "User-Agent: Mozilla/5.0",
                        "-H", "Origin: https://jlcpcb.com", "-H", "Referer: https://jlcpcb.com/parts",
                        "-d", json.dumps(body)], capture_output=True, text=True)
    j = json.loads(p.stdout)
    d = j.get("data", {}).get("componentPageInfo", {})
    return d.get("total", 0), (d.get("list") or [])


print("=== CONTROL: a known part must return exactly 1 hit ===")
t, _ = search("BQ25504RGTR", 3)
print(f"  BQ25504RGTR -> total={t}  {'OK' if t == 1 else '** ENDPOINT BROKEN **'}")
if t != 1:
    raise SystemExit("refusing to rank parts on a broken query")

# gather 52 MHz crystals across several search phrasings
seen = {}
for kw in ("52MHz crystal", "52 MHz crystal SMD", "crystal 52MHz", "52.000MHz crystal"):
    tot, items = search(kw, 60)
    print(f"  keyword {kw!r} -> total={tot}, got {len(items)}")
    for it in items:
        code = it.get("componentCode")
        if code and code not in seen:
            seen[code] = it

print(f"\n=== distinct 52 MHz crystal candidates: {len(seen)} ===")


def parse_spec(it):
    name = (it.get("erpComponentName") or "")
    spec = (it.get("componentSpecificationEn") or "")
    blob = f"{name} | {spec}"
    freq = re.search(r"(52(?:\.0+)?)\s*MHz", blob, re.I)
    load = re.search(r"(\d+(?:\.\d+)?)\s*pF", blob, re.I)
    tol = re.search(r"[±\+/-]*\s*(\d+(?:\.\d+)?)\s*ppm", blob, re.I)
    return {
        "freq": freq.group(1) if freq else None,
        "load": float(load.group(1)) if load else None,
        "tol_ppm": float(tol.group(1)) if tol else None,
        "raw": name,
    }


rows = []
for code, it in seen.items():
    s = parse_spec(it)
    pr = it.get("componentPrices") or []
    p1 = None
    for x in pr:
        if isinstance(x, dict) and x.get("startNumber") == 1:
            p1 = x.get("productPrice")
            break
    rows.append({
        "code": code,
        "model": it.get("componentModelEn") or "?",
        "brand": (it.get("componentBrandEn") or "?")[:14],
        "lib": it.get("componentLibraryType"),
        "stock": it.get("stockCount") or 0,
        "p1": p1 if p1 is not None else 999,
        "spec": it.get("componentSpecificationEn") or "",
        **s,
    })

print("\n=== ALL CANDIDATES ===")
for r in sorted(rows, key=lambda x: x["p1"]):
    print(f"  {r['code']:<12} {r['model'][:22]:<22} {r['brand']:<14} "
          f"stock={r['stock']:<7} @1={r['p1']:<8} load={r['load']}  {r['raw'][:34]}")

ok = [r for r in rows if r["load"] == 10.0]
nog = [r for r in rows if r["load"] is not None and r["load"] != 10.0]
unk = [r for r in rows if r["load"] is None]

print(f"\n=== FILTER: C_LOAD must be 10 pF ===")
print(f"  PASS  (10 pF)      : {len(ok)}")
print(f"  REJECT(not 10 pF)  : {len(nog)}  {sorted({r['load'] for r in nog})}")
print(f"  UNKNOWN (no value) : {len(unk)}")

if ok:
    print("\n=== RANKED PASSERS (by price) ===")
    for r in sorted(ok, key=lambda x: (x["p1"], -x["stock"])):
        print(f"  {r['code']:<12} {r['model'][:24]:<24} {r['brand']:<14} lib={r['lib']:<7} "
              f"stock={r['stock']:<7} @1=${r['p1']:<8} tol={r['tol_ppm']}ppm  {r['spec']}")
else:
    print("\n  ** NO 10 pF CANDIDATE -- a different approach is required **")
    print("  The datasheet says C_LOAD is internal. If no 10 pF crystal is stocked, options are:")
    print("    a) accept the closest C_LOAD and accept a frequency offset, or")
    print("    b) use the TCXO option (Figure 15-3) which does not depend on C_LOAD")
    print("\n  UNKNOWN-load candidates, cheapest first (NOT yet a recommendation):")
    for r in sorted(unk, key=lambda x: x["p1"])[:8]:
        print(f"  {r['code']:<12} {r['model'][:24]:<24} lib={r['lib']:<7} stock={r['stock']:<7} "
              f"@1=${r['p1']:<7} {r['raw'][:40]}")
