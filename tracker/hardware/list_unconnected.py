#!/usr/bin/env python3
"""List the unconnected items in a kicad-cli DRC JSON with their nets/pads."""
import json
import sys

path = sys.argv[1] if len(sys.argv) > 1 else "/tmp/h70_drc.json"
d = json.load(open(path))
u = d.get("unconnected_items", [])
print(f"unconnected items: {len(u)}\n")
for n, x in enumerate(u, 1):
    print(f"--- item {n}: {x.get('description','?')}")
    for it in x.get("items", []):
        print(f"      {it.get('description','?')}")
        print(f"        pos=({it.get('pos',{}).get('x')},{it.get('pos',{}).get('y')})")
