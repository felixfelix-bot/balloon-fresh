import json, os, collections
p = os.path.expanduser("~/reports/balloon-consolidation/TRIAGE.json")
d = json.load(open(p))
bs = d["branches"]
print("branches:", len(bs))
print("verdicts:", collections.Counter(b["verdict"] for b in bs))
print()
classes = collections.Counter()
for b in bs:
    for f in b["files"]:
        classes[f["class"]] += 1
print("file classes:", dict(classes))
print()
print("=== MECHANICAL branches (safe resolution) ===")
for b in bs:
    if b["verdict"] == "MECHANICAL":
        rules = collections.Counter(f["class"] for f in b["files"])
        print(f'  {b["branch"]:<34} +{b["ahead"]:>3} {len(b["files"]):>2}f  {dict(rules)}')
print()
print("=== MIXED branches ===")
for b in bs:
    if b["verdict"] == "MIXED":
        c = [f for f in b["files"] if f["class"] in ("COMPETING", "BINARY")]
        print(f'  {b["branch"]:<34} +{b["ahead"]:>3} {len(b["files"]):>2}f  decisive={len(c)}')
        for f in c:
            print(f'        [{f["class"]}] {f["path"]}  already_present={f.get("already_present")}')
print()
print("=== DECISION branches ===")
for b in bs:
    if b["verdict"] == "DECISION":
        print(f'  {b["branch"]:<34} +{b["ahead"]:>3} {len(b["files"]):>2}f')
        for f in b["files"]:
            if f["class"] in ("COMPETING", "BINARY"):
                print(f'        [{f["class"]}] {f["path"]}  already_present={f.get("already_present")}  ev={str(f.get("evidence"))[:90]}')
print()
print("=== CLUSTERS (>=2 branches) ===")
for path, brs in sorted(d.get("clusters", {}).items(), key=lambda kv: -len(kv[1])):
    if len(brs) >= 2:
        print(f'  {len(brs)}x {path}')
        print(f'      {"; ".join(brs)}')
print()
print("=== already_present:yes on COMPETING code (branch is arguably superseded) ===")
for b in bs:
    for f in b["files"]:
        if f["class"] == "COMPETING" and f.get("already_present") == "yes":
            print(f'  {b["branch"]:<34} {f["path"]}')
