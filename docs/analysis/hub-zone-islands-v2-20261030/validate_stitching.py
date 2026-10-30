"""Validate EVERY isolated island's stitch prediction empirically.

For each isolated island: add one via at the predicted site on a fresh copy, refill,
run kicad-cli DRC, and record delta_unconnected and delta_violations.

Prediction contract:
  legal=True   -> delta_unconnected == -1  AND delta_violations == 0
  legal=False  -> delta_unconnected == 0   (it cannot resolve, by definition)

Writes stitch_validation.json next to the inventory.
"""
import json
import pathlib
import shutil
import subprocess
import sys

import pcbnew as k

SRC = pathlib.Path('/home/c08r4d0r/worktrees/zi2-v2/tracker/hardware')
BASE = pathlib.Path('/home/c08r4d0r/worktrees/zi2-v2/.zi2scratch/allarms')
STEM = 'hub_board_v10_lora1280_7of9'
DRU = SRC / 'jlcpcb-s1-frozen.kicad_dru'


def fresh(tag):
    w = BASE / tag
    if w.exists():
        shutil.rmtree(w)
    w.mkdir(parents=True)
    for f in SRC.glob(STEM + '.kicad_*'):
        shutil.copy(f, w / f.name)
    for f in SRC.glob('*.kicad_dru'):
        shutil.copy(f, w / f.name)
    return w


def counts(pcb):
    b = k.LoadBoard(str(pcb))
    b.BuildConnectivity()
    return b.GetConnectivity().GetUnconnectedCount(False)


def drc(pcb, out):
    subprocess.run(['kicad-cli', 'pcb', 'drc', '--format', 'json', '-o', str(out),
                    '--severity-all', str(pcb)], capture_output=True, text=True)
    try:
        d = json.loads(pathlib.Path(out).read_text())
        import collections
        return len(d['violations']), dict(collections.Counter(v['type'] for v in d['violations']))
    except Exception:
        return None, {}


def add_via(tag, x, y, netname):
    w = fresh(tag)
    pcb = w / (STEM + '.kicad_pcb')
    b = k.LoadBoard(str(pcb))
    v = k.PCB_VIA(b)
    v.SetPosition(k.VECTOR2I(int(round(x * 1e6)), int(round(y * 1e6))))
    v.SetWidth(500000)
    v.SetDrill(300000)
    v.SetViaType(k.VIATYPE_THROUGH)
    v.SetLayerPair(b.GetLayerID('F.Cu'), b.GetLayerID('B.Cu'))
    v.SetNet(b.FindNet(netname))
    b.Add(v)
    k.ZONE_FILLER(b).Fill(b.Zones())
    k.SaveBoard(str(pcb), b)
    return w


if __name__ == '__main__':
    if len(sys.argv) > 2:
        add_via(sys.argv[1], float(sys.argv[2]), float(sys.argv[3]), sys.argv[4])
        sys.exit(0)

    inv_path = pathlib.Path(sys.argv[1])
    inv = json.loads(inv_path.read_text())

    # baseline
    wb = fresh('BASE')
    base_pcb = wb / (STEM + '.kicad_pcb')
    base_u = counts(base_pcb)
    base_v, base_types = drc(base_pcb, wb / 'drc.json')
    print(f'baseline: unconnected={base_u} violations={base_v}')

    iso = [i for i in inv['islands'] if i['status'] == 'ISOLATED' and i.get('stitch')]
    print(f'isolated islands with a stitch candidate: {len(iso)}')

    results = []
    for n, i in enumerate(iso):
        tag = f'arm{n:02d}'
        st = i['stitch']
        x, y = st['candidate_site_mm']
        predicted = st['legal']
        w = add_via(tag, x, y, i['net'])
        pcb = w / (STEM + '.kicad_pcb')
        u = counts(pcb)
        v, types = drc(pcb, w / 'drc.json')
        new_types = {k2: types[k2] - base_types.get(k2, 0)
                     for k2 in types if types[k2] != base_types.get(k2, 0)}
        rec = dict(island_id=i['island_id'], net=i['net'], layer=i['layer'],
                   area_mm2=i['area_mm2'], site=[x, y], predicted_legal=predicted,
                   unconnected_before=base_u, unconnected_after=u,
                   delta_unconnected=u - base_u,
                   violations_before=base_v, violations_after=v,
                   delta_violations=(v - base_v) if v is not None else None,
                   new_violation_types={kk: vv for kk, vv in new_types.items() if vv > 0},
                   hard_clearance_mm=st['hard_clearance_mm'],
                   frozen_fill_clearance_mm=st['frozen_fill_clearance_mm'],
                   lands_on=st['lands_on_same_net_layers'])
        # Two SEPARATE claims, each checked against its own evidence:
        #   resolves_connectivity -> the unconnected count must fall
        #   legal                 -> no new violation may appear
        pred_resolves = st['resolves_connectivity']
        pred_legal = st['legal']
        rec['predicted_resolves'] = pred_resolves
        rec['actual_resolved'] = rec['delta_unconnected'] < 0
        rec['actual_legal'] = (rec['delta_violations'] == 0)
        rec['resolves_held'] = (pred_resolves == rec['actual_resolved'])
        rec['legal_held'] = (pred_legal == rec['actual_legal'])
        rec['prediction_held'] = rec['resolves_held'] and rec['legal_held']
        results.append(rec)
        print(f"{tag} {i['island_id']:20s} "
              f"resolves pred={str(st['resolves_connectivity']):5s} act={str(rec['actual_resolved']):5s} "
              f"| legal pred={str(st['legal']):5s} act={str(rec['actual_legal']):5s} "
              f"| du={rec['delta_unconnected']:+d} dv={rec['delta_violations']:+d} "
              f"{'OK' if rec['prediction_held'] else '*** FAILED ***'}")

    held = sum(1 for r in results if r['prediction_held'])
    res_held = sum(1 for r in results if r['resolves_held'])
    leg_held = sum(1 for r in results if r['legal_held'])
    print()
    print(f'both claims held : {held}/{len(results)}')
    print(f'resolves claim   : {res_held}/{len(results)}')
    print(f'legal claim      : {leg_held}/{len(results)}')
    print(f'predicted legal AND actually legal: '
          f"{sum(1 for r in results if r['predicted_legal'] and r['actual_legal'])}"
          f"/{sum(1 for r in results if r['predicted_legal'])}")
    out = dict(baseline_unconnected=base_u, baseline_violations=base_v,
               arms=results, predictions_held=held, resolves_held=res_held,
               legal_held=leg_held, arms_total=len(results))
    (inv_path.parent / 'stitch_validation.json').write_text(json.dumps(out, indent=1))
    print('wrote stitch_validation.json')
