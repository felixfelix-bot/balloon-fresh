#!/usr/bin/env python3
"""Query JLCPCB for the SX1280 support parts, using the endpoint PROVEN in verify_c5913567.py.

Endpona shape matters: LCSC is /v2 componentPageInfo, and JLCPCB's own SMT list is
jlcpcb.com/api/overseas-pcb-order/v1/shoppingCart/smtGood/selectSmtComponentList/v2 with
data.componentPageInfo.{total,list}. A wrong host returns total=0 for EVERYTHING, which is
indistinguishable from "part not found" -- hence the CONTROLS below.

CONSTRAINTS READ FROM THE DATASHEET (Semtech SX1280/SX1281 Rev 3.2)
  Table 3-9 Crystal Oscillator Specifications
      F_XOSC  = 52 MHz
      C_LOAD  = 10 pF typical
      C0_XTAL typical 2 pF, max 5 pF
      R_S_XTAL typical 10 ohm, max 50 ohm (up to 90 ohm if C0 < 3 pF)
      C_M_XTAL 3 .. 3.52 .. 4 fF
  Figure 15-1 reference design passives
      L4  15 uH    DC-DC inductor (DCC_FB <-> DCC_SW)
      C9  470 nF   DC-DC filter cap
      C5  10 nF    VR_PA
      C6  10 nF    VDD_IN
      C8  100 nF   VBAT_IO
      C10 100 nF   VBAT
      R15 0 R      VDD_RADIO <-> I/O rail link
"""
import json
import subprocess

URL = ("https://jlcpcb.com/api/overseas-pcb-order/v1/shoppingCart/smtGood/"
       "selectSmtComponentList/v2")


def search(keyword, size=8):
    body = {
        "currentPage": 1, "pageSize": size, "presaleType": "stock", "searchType": 2,
        "keyword": keyword, "componentLibraryType": None, "stockFlag": None, "stockSort": None,
        "firstSortName": None, "secondSortName": None, "componentBrandList": [],
        "searchSource": "search", "componentSpecificationList": [],
        "componentAttributeList": [], "paramList": [], "startStockNumber": None,
        "sortMode": "", "sortASC": "",
    }
    p = subprocess.run([
        "curl", "-s", "-m", "40", "-X", "POST", URL,
        "-H", "Content-Type: application/json",
        "-H", "User-Agent: Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
              "(KHTML, like Gecko) Chrome/124 Safari/537.36",
        "-H", "Origin: https://jlcpcb.com", "-H", "Referer: https://jlcpcb.com/parts",
        "-d", json.dumps(body)], capture_output=True, text=True)
    try:
        j = json.loads(p.stdout)
        d = j.get("data", {}).get("componentPageInfo", {})
        return d.get("total", 0), (d.get("list") or [])
    except Exception as e:
        return -1, [{"error": str(e), "raw": p.stdout[:160]}]


def show(label, kw, size=6, fields=("componentCode", "componentModelEn", "componentBrandEn",
                                    "stockCount", "componentPrices", "componentLibraryType",
                                    "componentSpecificationEn")):
    total, items = search(kw, size)
    print(f"\n{'=' * 78}\n{label}\n  keyword {kw!r} -> total={total}")
    if total == -1:
        print("   QUERY ERROR:", items[0].get("error"), "| raw:", items[0].get("raw"))
        return []
    if total == 0:
        print("   no hits")
        return []
    got = []
    for it in items[:size]:
        code = it.get("componentCode", "?")
        model = (it.get("componentModelEn") or "?")[:26]
        brand = (it.get("componentBrandEn") or "?")[:11]
        stock = it.get("stockCount")
        lib = it.get("componentLibraryType")
        spec = (it.get("componentSpecificationEn") or "")[:34]
        pr = it.get("componentPrices") or []
        p1 = None
        if pr:
            p1 = pr[0].get("productPrice") if isinstance(pr[0], dict) else pr[0]
        print(f"   {code:<12} {model:<26} {brand:<11} lib={lib!s:<7} stock={stock:<9} "
              f"@1={p1}  {spec}")
        got.append((code, model, lib, stock, p1))
    return got


print("=== CONTROLS (must return hits; otherwise the endpoint shape is wrong) ===")
show("CONTROL SS24", "SS24")
show("CONTROL BQ25504RGTR", "BQ25504RGTR")

print("\n\n=== 1. 52 MHz crystal ===")
show("52 MHz crystal", "52MHz crystal")
show("52 MHz crystal (alt spelling)", "52 MHz crystal SMD")

print("\n\n=== 2. 15 uH inductor ===")
show("15 uH inductor", "15uH inductor")

print("\n\n=== 3. 470 nF 0402 ===")
show("470 nF", "470nF 0402")

print("\n\n=== 4. 10 nF 0402 ===")
show("10 nF", "10nF 0402 50V")

print("\n\n=== 5. 100 nF 0402 ===")
show("100 nF", "100nF 0402 50V")

print("\n\n=== 6. 0 ohm 0402 ===")
show("0 R", "0R 0402")
