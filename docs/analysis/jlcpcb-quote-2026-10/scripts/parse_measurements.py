"""Parse the saved measurement .txt captures into a structured table (no browser)."""
import json, os, re, glob, sys

M = os.path.expanduser("~/quote-scratch/measurements")

def parse_txt(path):
    lines = [l.strip() for l in open(path).read().split("\n")]
    try:
        i0 = lines.index("Charge Details")
    except ValueError:
        return {"error": "no Charge Details"}
    try:
        i1 = lines.index("Calculated Price")
    except ValueError:
        i1 = len(lines)
    panel_lines = [l for l in lines[i0+1:i1] if l]
    # pair label->value
    pairs = []
    k = 0
    while k < len(panel_lines):
        lab = panel_lines[k]
        if k+1 < len(panel_lines) and panel_lines[k+1].startswith("$"):
            pairs.append((lab, panel_lines[k+1])); k += 2
        else:
            pairs.append((lab, None)); k += 1
    out = {"panel_pairs": pairs}
    # trailing summary values
    for i, l in enumerate(lines):
        if l == "Calculated Price":
            for j in range(i+1, min(i+8, len(lines))):
                if lines[j].startswith("$"):
                    out["calculated_price"] = lines[j]; break
        if l == "Shipping Estimate" and i+1 < len(lines):
            out["shipping"] = lines[i+1]
            out["carrier"] = lines[i+2] if i+2 < len(lines) else None
        if l == "Weight":
            for j in range(i+1, min(i+4, len(lines))):
                if re.match(r"^[0-9.]+ ?kg", lines[j] or ""):
                    out["weight"] = lines[j]; break
            out.setdefault("weight", None)
    # build-time option list (after 'PCB Build Time')
    bt = []
    for i, l in enumerate(lines):
        if l == "PCB Build Time":
            j = i+1
            while j < len(lines) and not lines[j].startswith("Calculated") and j < i+12:
                t = lines[j]
                if t == "" or t.startswith("$"):
                    j += 1; continue
                nxt = lines[j+1] if j+1 < len(lines) else ""
                bt.append((t, nxt if nxt.startswith("$") else None))
                j += 1
            break
    out["build_time_options"] = bt
    return out

def main():
    rows = []
    for jf in sorted(glob.glob(f"{M}/*.json")):
        name = os.path.basename(jf)[:-5]
        if name.startswith("SUMMARY") or name.startswith("probe"):
            continue
        j = json.load(open(jf))
        if not isinstance(j, dict) or "final_selected" not in j:
            continue
        tf = f"{M}/{name}.txt"
        p = parse_txt(tf) if os.path.exists(tf) else {}
        sel = j.get("final_selected", {})
        row = {
            "name": name,
            "at": j.get("at"),
            "dims": j.get("dims_entered"),
            "dims_readback": j.get("dims_input_readback"),
            "qty": j.get("qty"),
            "note": j.get("note"),
            "layers": sel.get("Layers"),
            "thickness": sel.get("PCB Thickness"),
            "surface_finish": sel.get("Surface Finish"),
            "via_covering": sel.get("Via Covering"),
            "outer_copper": sel.get("Outer Copper Weight"),
            "different_design": sel.get("Different Design"),
            "delivery_format": sel.get("Delivery Format"),
            "steps": j.get("steps"),
            "calculated_price": p.get("calculated_price"),
            "shipping": p.get("shipping"),
            "weight": p.get("weight"),
            "panel_pairs": p.get("panel_pairs"),
            "build_time_options": p.get("build_time_options"),
            "page_load": j.get("page_load"),
        }
        rows.append(row)
    with open(f"{M}/SUMMARY.json", "w") as fh:
        json.dump(rows, fh, indent=2)
    for r in rows:
        print(f"--- {r['name']}  dims={r['dims']} readback={r['dims_readback']} "
              f"{r['layers']}L {r['thickness']} {r['surface_finish']} qty={r['qty']}")
        print("    steps:", [(s.get('heading'), s.get('want'), s.get('got'), s.get('took', s.get('err'))) for s in (r['steps'] or [])])
        print("    panel:", r['panel_pairs'])
        print("    price:", r['calculated_price'], "| ship:", r['shipping'], "| wt:", r['weight'])

if __name__ == "__main__":
    main()
