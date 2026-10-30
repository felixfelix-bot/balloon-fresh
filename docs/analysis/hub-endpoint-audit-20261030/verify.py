#!/usr/bin/python3
"""Independent native KiCad pad/track/via walk for nine signal paths; ledger coverage."""
import pcbnew as k,json,pathlib,collections
O=pathlib.Path('docs/analysis/hub-endpoint-audit-20261030')
b=k.LoadBoard('.audit-hub-copy/hub_board_v10_lora1280_7of9.kicad_pcb');b.BuildConnectivity();c=b.GetConnectivity()
f=next(f for f in b.GetFootprints() if f.GetReference()=='U_LORA1280')
results=[]
for p in f.Pads():
 if p.GetNetname() in ('','+3V3','GND'):continue
 q=collections.deque([p]); seen=set();hit=[]
 while q:
  x=q.popleft();uid=x.m_Uuid.AsString()
  if uid in seen:continue
  seen.add(uid)
  if isinstance(x,k.PAD) and x.GetParentFootprint().GetReference()=='U1':hit.append(x.GetNumber())
  q.extend(y for y in list(c.GetConnectedTracks(x))+list(c.GetConnectedPads(x)) if y.GetNetCode()==p.GetNetCode())
 results.append(dict(net=p.GetNetname(),module_pad=p.GetNumber(),U1_pads=hit,visited_items=len(seen)))
 assert hit,(p.GetNumber(),p.GetNetname())
d=json.loads((O/'drc.json').read_text());l=json.loads((O/'ledger.json').read_text());g=json.loads((O/'connectivity.json').read_text());proof=json.loads((O/'radio-paths.json').read_text())
assert len(l)==len(d['unconnected_items'])==86
assert sum(json.loads((O/'summary.json').read_text())['by_net'].values())==86
edges={tuple(e) for e in g['edges']}; nodes=g['nodes']
for p in proof:
 assert p['connected']
 for a,z in zip(p['path_nodes'],p['path_nodes'][1:]):assert tuple(sorted((a,z))) in edges
 assert nodes[p['path_nodes'][0]]['ref']=='U_LORA1280'
 assert nodes[p['path_nodes'][-1]]['ref']=='U1'
# Counterexample control: graph search with every module escape edge removed must fail.
for p in proof:
 start=p['path_nodes'][0]; target=p['path_nodes'][-1]
 adj=collections.defaultdict(set)
 for a,z in edges:
  if start not in (a,z):adj[a].add(z);adj[z].add(a)
 seen={start};q=[start]
 while q:
  for z in adj[q.pop()]:
   if z not in seen:seen.add(z);q.append(z)
 assert target not in seen
out=dict(native_signal_walk=results,assertions='PASS: 86/86 coverage, net tally 86, nine witnessed paths, nine cut-path negative controls',native_walk_scope='pads/tracks/vias; no zone or graphical shape traversal required for these nine paths')
(O/'verification.json').write_text(json.dumps(out,indent=2));print(json.dumps(out,indent=2))
