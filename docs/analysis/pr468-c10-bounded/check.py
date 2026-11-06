import sys,json,pathlib,collections,hashlib
import pcbnew as k
sys.path.insert(0,'/home/c08r4d0r/reports/pr468-verification-853f648c/connectivity')
import graph_kernel as g
r=pathlib.Path(__file__).parent
b=k.LoadBoard(str(r/'candidate/board.kicad_pcb'))
items,nodes,bi,comps,roots,ci,_=g.build_copper_graph(b,contact_tolerance=.000003)
def pad(s): return next(i['id'] for i in items if i['kind']=='pad' and i['meta']['ref']+'.'+i['meta']['num']==s)
checks={a+' -> '+z:ci[pad(a)]==ci[pad(z)] for a,z in [('C10.1','U1.2'),('C10.2','U7.2')]}
a=json.loads(pathlib.Path('/home/c08r4d0r/reports/pr468-verification-853f648c/native-after.json').read_text())
c=json.loads((r/'native-candidate.json').read_text())
def sig(v):return (v['type'],v['severity'],v['description'],tuple(sorted(i['uuid'] for i in v['items'])))
aa=collections.Counter(map(sig,a['violations']));cc=collections.Counter(map(sig,c['violations']))
out={'targets':checks,'baseline_opens':len(a['unconnected_items']),'candidate_opens':len(c['unconnected_items']),'baseline_violations':len(a['violations']),'candidate_violations':len(c['violations']),'candidate_severities':dict(collections.Counter(v['severity'] for v in c['violations'])),'added_nonconnectivity':list((cc-aa).elements()),'removed_nonconnectivity':list((aa-cc).elements()),'source_unchanged':hashlib.sha256(pathlib.Path('/home/c08r4d0r/reports/pr468-verification-853f648c/connectivity/refilled-after/board.kicad_pcb').read_bytes()).hexdigest()=='a732114acc2e0cf5950b750d2b64ad6f42890b7687cad178bba2942e3c892ce9'}
(r/'comparison.json').write_text(json.dumps(out,indent=2));print(json.dumps(out,indent=2))
