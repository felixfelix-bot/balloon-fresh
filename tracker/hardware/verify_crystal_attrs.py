#!/usr/bin/env python3
"""Verify the candidate 52 MHz crystal against Table 3-9, on the part's own attribute data.

Table 3-9 (Semtech SX1280/SX1281 Rev 3.2):
    F_XOSC   52 MHz
    C_LOAD   10 pF typical
    C0_XTAL  typical 2 pF, MAX 5 pF
    R_S_XTAL typical 10 ohm, MAX 50 ohm (up to 90 ohm if C0 < 3 pF)
    C_M_XTAL 3 .. 3.52 .. 4 fF

All the cheap 52 MHz crystals found are 4-pad SMD (2016/2520/3225). A 4-pad crystal is a 2-electrode
crystal in a 4-pad package (the extra 2 pads are ground/shield), so the load capacitance still
applies. The deciding numbers are C_LOAD (must be 10 pF for the internal foot caps to resonate
correctly -- the datasheet says C_LOAD is INTERNAL, so the crystal must be specified AT that load),
C0 and R_S.

Fetch each candidate's attribute list and check it. Refuse to recommend a part whose C_LOAD is not
10 pF or whose values are absent -- absent is not "passes".
"""
import json
import subprocess

URL = ("https://jlcpcb.com/api/overseas-pcb-order/v1/shoppingCart/smtGood/"
       "selectSmtComponentList/v2")


def search(keyword, size=10):
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
    j = json.loads(p.stdout)
    d = j.get("data", {}).get("componentPageInfo", {})
    return d.get("total", 0), (d.get("list") or [])


# control
t, items = search("BQ25504RGTR", 3)
print(f"CONTROL BQ25504RGTR -> total={t}  {'OK' if t == 1 else '** BROKEN **'}")
print()

for kw in ("52MHz crystal", "52 MHz crystal SMD"):
    t, items = search(kw, 8)
    print(f"{'=' * 78}\nkeyword {kw!r} -> total={t}")
    for it in items:
        code = it.get("componentCode", "?")
        model = it.get("componentModelEn", "?")
        stock = it.get("stockCount")
        attrs = it.get("componentAttributes") or it.get("attributes") or []
        print(f"\n  {code}  {model}  stock={stock}")
        # print every attribute that mentions a relevant quantity
        found = {}
        for a in attrs:
            if not isinstance(a, dict):
                continue
            k = (a.get("attribute_name_en") or a.get("attributeNameEn")
                 or a.get("attribute_name") or "")
            v = (a.get("attribute_value") or a.get("attributeValue") or "")
            if not k:
                continue
            found[k] = v
        if not found:
            print("     (no attribute list returned)")
        for k, v in found.items():
            mark = ""
            kl = k.lower()
            if "load" in kl and "capacit" in kl:
                mark = "  <== C_LOAD must be 10 pF"
            elif "shunt" in kl or "c0" in kl:
                mark = "  <== C0 max 5 pF"
            elif "resistance" in kl or "esr" in kl or "r_s" in kl:
                mark = "  <== R_S max 50 ohm"
            elif "frequency" in kl:
                mark = "  <== must be 52 MHz"
            print(f"     {k} = {v}{mark}")
