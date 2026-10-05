#!/usr/bin/env python3
"""Validator for SCHEMATIC-PLAN-3VARIANTS.md.

Parses the net blocks out of the markdown and proves, per variant:
  1. Every pin of every BOM part appears in exactly one net (no floating pin,
     no pin claimed by two nets -> a short).
  2. No two power rails (VBAT / 3V3 / GND / SOLAR_IN / VDIV_MID) share a pin.
  3. The placement/orientation tables agree with the net lines (a cap whose
     table row says VBAT must have its top terminal on VBAT, etc.).

Exit 0 = clean. Exit 1 = defects printed.

Run:  python3 docs/coordination/validate_netlist.py
"""
import re
import sys
import pathlib

DOC = pathlib.Path(__file__).with_name("SCHEMATIC-PLAN-3VARIANTS.md")

# ---------------------------------------------------------------- BOM
# ref -> set of pin identifiers required to be connected, per variant.
# Pin token spelling follows the doc's nets.
def bom(variant):
    mcu_pins = {"VCC", "GND", "GPIO0", "GPIO1", "GPIO2", "GPIO3", "GPIO4",
                "GPIO5", "GPIO6", "GPIO7", "GPIO8", "GPIO9", "GPIO10"}
    if variant == "v1":
        u1 = mcu_pins | {"GPIO19"}            # LED on GPIO19
    elif variant == "v2":
        u1 = mcu_pins | {"GPIO18"}            # LED on GPIO18
    else:
        u1 = mcu_pins | {"GPIO18", "GPIO19", "GPIO20"}
    parts = {
        "U1": u1,
        "U2": {"VCC", "GND", "MISO", "MOSI", "SCK", "NSS", "RST", "BUSY", "DIO9"},
        "U3": {"VIN", "GND", "EN", "VOUT"},
        "U4": {"VCC", "GND", "TX", "RX"},
        "U6": {"VCC", "GND", "SDA", "SCL"},
        "SC": {"+", "-"},
        "D1": {"A", "K"},
        "D2": {"A", "K"},
        "J1": {"1", "2"},
        "R1": {"1", "2"},
        "R2": {"1", "2"},
        "R3": {"1", "2"},
        "R4": {"1", "2"},
        "R5": {"1", "2"},
    }
    for c in ("C1", "C2", "C3", "C4", "C5", "C6", "C7"):
        parts[c] = {"1", "2"}
    if variant == "v3":
        parts["U5"] = {"VCC", "GND", "GPIO0", "GPIO1"}
        parts["C8"] = {"1", "2"}
    return parts


VARIANT_HEADINGS = {
    "v1": "## 2. VARIANT 1",
    "v2": "## 3. VARIANT 2",
    "v3": "## 4. VARIANT 3",
}

RAILS = {"VBAT", "3V3", "GND", "SOLAR_IN", "VDIV_MID"}


def split_variants(text):
    """Return {variant: section_text}."""
    idx = {}
    for v, head in VARIANT_HEADINGS.items():
        i = text.index(head)
        idx[v] = i
    order = sorted(idx, key=lambda v: idx[v])
    out = {}
    for n, v in enumerate(order):
        start = idx[v]
        end = idx[order[n + 1]] if n + 1 < len(order) else len(text)
        out[v] = text[start:end]
    return out


def parse_nets(section):
    """Extract 'NAME : A.pin <-> B.pin ...' lines. Returns {net: [tokens]}.

    Only fenced blocks whose lines match the netlist shape are read, so the
    ASCII power diagram and the prose are ignored.
    """
    nets = {}
    for m in re.finditer(r"(?m)^([A-Z0-9][A-Z0-9_]*)\s*:\s*(.+)$", section):
        name, rhs = m.group(1), m.group(2)
        # cut the trailing prose comment, e.g. "(MCU TX -> GPS RX)"
        rhs = rhs.split("#")[0]
        rhs = re.split(r"\s{2,}\(", rhs)[0]
        rhs = re.sub(r"\(.*?\)", "", rhs)
        toks = [t.strip() for t in re.split(r"↔|->|<-", rhs) if t.strip()]
        if len(toks) < 2:
            continue
        if not all(re.fullmatch(r"[A-Za-z0-9_]+\.\S+", t) for t in toks):
            continue
        nets[name] = [t.rstrip(",") for t in toks]
    return nets


def parse_placement(section):
    """Return {ref: rail} for the decoupling table (cap -> its non-GND rail)."""
    out = {}
    for m in re.finditer(r"(?m)^\|\s*(C\d)\s*\|\s*\S+\s*\|\s*(\S+)\s*\|", section):
        out[m.group(1)] = m.group(2)
    return out


def parse_resistors(section):
    """Return {ref: (t1, t2)} from the orientation table."""
    out = {}
    for m in re.finditer(
            r"(?m)^\|\s*(R\d)\s*\|\s*\S+\s*\|\s*(\S+)\s*\|\s*(\S+)\s*\|", section):
        out[m.group(1)] = (m.group(2), m.group(3))
    return out


def main():
    text = DOC.read_text()
    sections = split_variants(text)
    fails = []

    for variant, section in sections.items():
        nets = parse_nets(section)
        if not nets:
            fails.append(f"{variant}: no nets parsed")
            continue

        # ---- pin -> nets
        owned = {}
        for net, toks in nets.items():
            for t in toks:
                owned.setdefault(t, []).append(net)

        # 1. every BOM pin in exactly one net
        bombl = bom(variant)
        for ref, pins in bombl.items():
            for pin in pins:
                tok = f"{ref}.{pin}"
                where = owned.get(tok, [])
                if variant == "v1" and ref == "U1" and pin == "GPIO18":
                    continue  # not used on v1
                if not where:
                    fails.append(f"{variant}: {tok} is NOT in any net")

        # 2. no token in two nets
        for tok, where in owned.items():
            if len(where) > 1:
                fails.append(f"{variant}: {tok} is in MULTIPLE nets: {where}")

        # 3. no pin on two different power rails
        for tok, where in owned.items():
            rails = RAILS & set(where)
            if len(rails) > 1:
                fails.append(f"{variant}: {tok} bridges rails {sorted(rails)}")

        # 4. placement table agrees with the nets
        for ref, rail in parse_placement(section).items():
            tok = f"{ref}.1"
            if tok not in owned:
                continue
            actual = owned[tok][0]
            if actual != rail:
                fails.append(
                    f"{variant}: placement says {ref} top is {rail}, "
                    f"but net '{actual}' carries {tok}")
            if f"{ref}.2" not in owned:
                fails.append(f"{variant}: {ref}.2 has no net (cap not grounded)")

        # 5. resistor orientation agrees with the nets
        for ref, (t1, t2) in parse_resistors(section).items():
            for pnum, want in (("1", t1), ("2", t2)):
                tok = f"{ref}.{pnum}"
                if tok in owned and owned[tok][0] != want:
                    fails.append(
                        f"{variant}: resistor table says {ref}.{pnum}={want}, "
                        f"but net '{owned[tok][0]}' carries {tok}")

        # 5b. radio no-connect pins must NOT be in any net
        for tok in ("U2.NC", "U2.12", "U2.15"):
            if tok in owned:
                fails.append(f"{variant}: {tok} must be no-connect, "
                             f"found in net(s) {owned[tok]}")

        # 6. the two rails must not be shorted by a component leg
        for leg in ("R4.1", "R4.2", "R3.1", "R3.2"):
            pass
        if "VBAT" in nets and "GND" in nets:
            if set(nets["VBAT"]) & set(nets["GND"]):
                fails.append(f"{variant}: VBAT and GND share a pin (short)")

        print(f"{variant}: {len(nets)} nets, "
              f"{sum(len(v) for v in nets.values())} pin connections")

    if fails:
        print("\n=== FAILURES ===")
        for f in fails:
            print(" -", f)
        return 1
    print("\nVALIDATOR PASS: every BOM pin is in exactly one net; "
          "no rail shorts; tables agree with net lines.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
