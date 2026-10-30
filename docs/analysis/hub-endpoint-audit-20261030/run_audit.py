#!/usr/bin/python3
"""Read-only input capture and copy-only zone refill; run from repository root."""
import pathlib, subprocess, json, hashlib, shutil, os
ROOT=pathlib.Path.cwd(); OUT=ROOT/'docs/analysis/hub-endpoint-audit-20261030'; HW=ROOT/'tracker/hardware'; STEM='hub_board_v10_lora1280_7of9'
OUT.mkdir(parents=True,exist_ok=True)
COPY=ROOT/'.audit-hub-copy'; COPY.mkdir(exist_ok=True)
commands=[]
def run(args):
 p=subprocess.run(args,text=True,capture_output=True); commands.append(dict(command=args,exit_status=p.returncode,stdout=p.stdout,stderr=p.stderr)); (OUT/'commands.json').write_text(json.dumps(commands,indent=2)); return p
for s in ['.kicad_pcb','.kicad_pro','.kicad_dru']:
 p=HW/(STEM+s)
 if p.exists(): shutil.copy2(p,COPY/p.name)
shutil.copy2(HW/'fp-lib-table',COPY/'fp-lib-table')
for name in ['schematics','footprints']:
 if not (COPY/name).exists(): (COPY/name).symlink_to(HW/name,target_is_directory=True)
inputs=[HW/(STEM+s) for s in ['.kicad_pcb','.kicad_pro','.kicad_dru']]+[HW/'fp-lib-table']
inputs += list((HW/'footprints').rglob('*.kicad_mod')) + list((HW/'schematics/flight_board').rglob('*.kicad_mod'))
manifest={'commit':run(['git','rev-parse','HEAD']).stdout.strip(),'kicad':run(['kicad-cli','version']).stdout.strip(),'inputs':{str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() if p.exists() else None for p in inputs}}
(OUT/'manifest.json').write_text(json.dumps(manifest,indent=2))
run(['git','worktree','list','--porcelain'])
run(['gh','pr','list','--repo','felixfelix-bot/balloon-fresh','--limit','300','--json','number,title,headRefName,url'])
run(['/usr/bin/python3','-c',"import pcbnew; b=pcbnew.LoadBoard("+repr(str(COPY/(STEM+'.kicad_pcb')))+"); pcbnew.ZONE_FILLER(b).Fill(b.Zones()); pcbnew.SaveBoard(b.GetFileName(),b)"])
run(['kicad-cli','pcb','drc','--format','json','--severity-all','--exit-code-violations','--output',str(OUT/'drc.json'),str(COPY/(STEM+'.kicad_pcb'))])
manifest['refilled_board_sha256']=hashlib.sha256((COPY/(STEM+'.kicad_pcb')).read_bytes()).hexdigest()
manifest['source_unchanged']=all(not p.exists() or hashlib.sha256(p.read_bytes()).hexdigest()==manifest['inputs'][str(p.relative_to(ROOT))] for p in inputs)
(OUT/'manifest.json').write_text(json.dumps(manifest,indent=2))
print(json.dumps(commands[-2:],indent=2))
