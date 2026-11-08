from search import *
b=p.LoadBoard(str(O/'baseline/board.kicad_pcb'));obs=items(b);net=next(q.GetNetCode() for q,l,g in obs if q.m_Uuid.AsString() in AB);foreign=[(q,l,g) for q,l,g in obs if l==0 and q.GetNetCode()!=net]
def name(q):return q.GetParentFootprint().GetReference()+'.'+q.GetNumber() if isinstance(q,p.PAD) else q.m_Uuid.AsString()
rows=[]
for pt in [(8.75,41.25),(11.05,44.05),(8.35,42.5),(7.95,42.5),(7.55,42.5)]:
 near=sorted([(Point(pt).distance(g)-.1,name(q),q.GetNetname()) for q,l,g in foreign])[:5];rows.append({'point':pt,'nearest_copper_clearances_mm':near})
# Search positive/negative controls using synthetic free regions. These test the search, not board feasibility.
controls={'open':path((7,40),(11,45),box(6,39,12,46)) is not None,'wall_refused':path((7,40),(11,45),box(6,39,12,46).difference(box(8,39,9,46))) is None}
assert all(controls.values())
out={'points':rows,'controls':controls,'limits':'Only three F.Cu waypoint topologies on 0.05mm grid; no exhaustive feasibility conclusion. Failed waypoint legality is not a routing impossibility.'};(O/'constraints.json').write_text(json.dumps(out,indent=2));print(json.dumps(out,indent=2))
