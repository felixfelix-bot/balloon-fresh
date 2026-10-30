"""Resolve the 27 zone-island unconnected records with island-level identity.

Method A (native): replace each multi-island zone with one zone per island, so KiCad's
own connectivity/DRC engine names the actual island instead of repeating the zone's
outline anchor. Copper polygons are copied verbatim (Subset(i,i+1)); only the grouping
changes, and the area sum is asserted against the original.

Method B (independent): geometric union-find over per-island polygons + pads/tracks/vias,
joined only on the same layer and same net, with only plated barrels bridging layers.

Read-only on the source board: all work happens on copies under --scratch.

Known pcbnew 9.0.9 hazard (measured): calling board.Remove() repeatedly corrupts the SWIG
type map, after which board.GetConnectivity() returns a bare SwigPyObject. So the mutation
phase saves the board and stops; verification runs on a freshly loaded board.
"""
import argparse
import collections
import hashlib
import json
import pathlib
import shutil
import subprocess

import sys

import pcbnew as k
from shapely.geometry import Polygon
from shapely.strtree import STRtree

STEM = 'hub_board_v10_lora1280_7of9'
CU = ('F.Cu', 'In1.Cu', 'In2.Cu', 'B.Cu')


def sha(p):
    return hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()


def contour_pts(c):
    return [(c.CPoint(i).x / 1e6, c.CPoint(i).y / 1e6) for i in range(c.PointCount())]


def polyset_to_shapely(s):
    out = []
    for i in range(s.OutlineCount()):
        p = Polygon(contour_pts(s.COutline(i)),
                    [contour_pts(s.CHole(i, j)) for j in range(s.HoleCount(i))])
        if not p.is_valid:
            p = p.buffer(0)
        out.append(p)
    return out


def board_stats(b):
    return dict(unconnected=b.GetConnectivity().GetUnconnectedCount(False),
                pads=sum(1 for f in b.GetFootprints() for _ in f.Pads()),
                tracks=len(b.GetTracks()), footprints=len(b.GetFootprints()),
                zones=len(b.Zones()))


def copper_area(b):
    tot = 0.0
    for z in b.Zones():
        tot += z.GetFilledPolysList(z.GetLayer()).Area() / 1e12
    return round(tot, 4)


# ---------------------------------------------------------------- method A: decompose
def decompose(src_pcb, out_pcb):
    b = k.LoadBoard(str(src_pcb))
    b.BuildConnectivity()
    base = board_stats(b)
    base_area = copper_area(b)

    plan = []            # per-island metadata, collected before any mutation
    for z in list(b.Zones()):
        lay = z.GetLayer()
        src = z.GetFilledPolysList(lay)
        n = src.OutlineCount()
        if n == 0:
            continue
        zone_area = src.Area() / 1e12
        zmeta = dict(zone_uuid=z.m_Uuid.AsString(), zone_name=z.GetZoneName(),
                     layer=b.GetLayerName(lay), net=z.GetNetname(),
                     island_count=n, zone_area_mm2=round(zone_area, 6))
        parts = []
        for i in range(n):
            one = src.Subset(i, i + 1)
            shp = polyset_to_shapely(one)[0]
            minx, miny, maxx, maxy = shp.bounds
            parts.append(dict(island=i, area_mm2=round(one.Area() / 1e12, 6),
                              bbox_mm=[round(v, 6) for v in (minx, miny, maxx, maxy)],
                              vertices=one.COutline(0).PointCount(),
                              holes=one.HoleCount(0)))
        got = sum(p['area_mm2'] for p in parts)
        if abs(got - zmeta['zone_area_mm2']) > 1e-4:
            raise SystemExit('AREA MISMATCH %s %.6f != %.6f' %
                             (zmeta['zone_name'], got, zmeta['zone_area_mm2']))
        zmeta['sum_of_island_area_mm2'] = round(got, 6)
        zmeta['islands'] = parts
        plan.append((z, zmeta))

    for z, zmeta in plan:
        lay = z.GetLayer()
        src = z.GetFilledPolysList(lay)
        for i in range(zmeta['island_count']):
            one = src.Subset(i, i + 1)
            c = z.Duplicate()
            c.SetFilledPolysList(lay, one)
            c.SetIsFilled(True)
            oc = c.Outline()
            oc.RemoveAllContours()
            oc.NewOutline()
            for p in contour_pts(one.COutline(0)):
                oc.Append(k.VECTOR2I(int(round(p[0] * 1e6)), int(round(p[1] * 1e6))))
            c.SetLayer(lay)
            c.SetNetCode(z.GetNetCode())
            c.SetAssignedPriority(z.GetAssignedPriority() + 1)
            c.SetZoneName('%s__ISL%d' % (zmeta['zone_name'], i))
            b.Add(c)
        b.Remove(z)

    k.SaveBoard(str(out_pcb), b)
    return dict(base=base, base_copper_area_mm2=base_area, plan=[
        dict(z, islands=[dict(p, clone_name='%s__ISL%d' % (z['zone_name'], p['island']))
                         for p in z['islands']])
        for _, z in plan])


def verify_decomposed(pcb_path):
    b = k.LoadBoard(str(pcb_path))
    b.BuildConnectivity()
    cd = b.GetConnectivity()
    stats = board_stats(b)
    islands = []
    for z in b.Zones():
        if '__ISL' not in z.GetZoneName():
            continue
        src = z.GetFilledPolysList(z.GetLayer())
        shp = polyset_to_shapely(src)[0]
        islands.append(dict(
            clone_name=z.GetZoneName(), clone_uuid=z.m_Uuid.AsString(), net=z.GetNetname(),
            layer=b.GetLayerName(z.GetLayer()),
            area_mm2=round(src.Area() / 1e12, 6),
            bbox_mm=[round(v, 6) for v in shp.bounds],
            native_pads=sorted('%s.%s' % (p.GetParentFootprint().GetReference(), p.GetNumber())
                               for p in cd.GetConnectedPads(z)),
            native_tracks=len(cd.GetConnectedTracks(z))))
    return dict(stats=stats, copper_area_mm2=copper_area(b), islands=islands)


# ------------------------------------------------- method B: geometric union-find
class GeoGraph:
    def __init__(self, pcb_path):
        b = k.LoadBoard(str(pcb_path))
        self.board = b
        self.layers = list(b.GetEnabledLayers().CuStack())
        self.layer_name = {l: b.GetLayerName(l) for l in self.layers}
        self.nodes, self.geoms, self.byuuid = [], [], collections.defaultdict(list)
        self.objects = {}
        items = list(b.GetPads()) + list(b.GetTracks()) + list(b.Zones())
        for f in b.GetFootprints():
            items += list(f.GraphicalItems())
        for obj in items:
            if not hasattr(obj, 'GetNetname'):
                continue
            uid = str(obj.m_Uuid.AsString())
            self.objects[uid] = obj
            for layer in self.layers:
                if not obj.IsOnLayer(layer):
                    continue
                if isinstance(obj, k.ZONE):
                    src = obj.GetFilledPolysList(layer)
                    pp = [polyset_to_shapely(src.Subset(i, i + 1))[0]
                          for i in range(src.OutlineCount())]
                    island_idx = list(range(len(pp)))
                else:
                    s = k.SHAPE_POLY_SET()
                    try:
                        obj.TransformShapeToPolygon(s, layer, 0, 1000, k.ERROR_INSIDE)
                    except (TypeError, AttributeError):
                        continue
                    pp = polyset_to_shapely(s)
                    island_idx = [0] * len(pp)
                for p, isl in zip(pp, island_idx):
                    if p.is_empty:
                        continue
                    n = dict(id=len(self.nodes), uuid=uid, kind=obj.GetClass(),
                             net=obj.GetNetname(), layer=self.layer_name[layer],
                             zone_name=(obj.GetZoneName() if isinstance(obj, k.ZONE) else None),
                             island=isl)
                    if isinstance(obj, k.PAD):
                        n.update(ref=obj.GetParentFootprint().GetReference(),
                                 pad=obj.GetNumber(), attribute=obj.GetAttribute(),
                                 pos_mm=[round(obj.GetPosition().x / 1e6, 4),
                                         round(obj.GetPosition().y / 1e6, 4)])
                    self.nodes.append(n)
                    self.geoms.append(p)
                    self.byuuid[uid].append(n['id'])
        self._union()

    def _union(self):
        n = len(self.nodes)
        adj = [set() for _ in range(n)]
        groups = collections.defaultdict(list)
        for nd in self.nodes:
            groups[nd['layer'], nd['net']].append(nd['id'])
        for ids in groups.values():
            tree = STRtree([self.geoms[i] for i in ids])
            for i in ids:
                for jj in tree.query(self.geoms[i].buffer(1e-6)):
                    j = ids[int(jj)]
                    if j > i and self.geoms[i].distance(self.geoms[j]) <= 1e-6:
                        adj[i].add(j)
                        adj[j].add(i)
        for uid, ids in self.byuuid.items():
            obj = self.objects[uid]
            plated = isinstance(obj, k.PCB_VIA) or (
                isinstance(obj, k.PAD) and obj.GetAttribute() == k.PAD_ATTRIB_PTH)
            if plated:
                for j in ids[1:]:
                    adj[ids[0]].add(j)
                    adj[j].add(ids[0])
        self.comp, self.components = {}, []
        for i in range(n):
            if i in self.comp:
                continue
            cid = len(self.components)
            stack, members = [i], []
            self.comp[i] = cid
            while stack:
                u = stack.pop()
                members.append(u)
                for v in adj[u]:
                    if v not in self.comp:
                        self.comp[v] = cid
                        stack.append(v)
            self.components.append(sorted(members))
        for nd in self.nodes:
            nd['component'] = self.comp[nd['id']]

    def island_components(self, zone_uuid, layer, island):
        ids = [n['id'] for n in self.nodes if n['uuid'] == zone_uuid
               and n['layer'] == layer and n['island'] == island]
        return sorted({self.comp[i] for i in ids})

    def pretty(self, cid):
        out = []
        for nid in self.components[cid]:
            nd = self.nodes[nid]
            if nd['kind'] == 'PAD':
                out.append('%s.%s' % (nd['ref'], nd['pad']))
            elif nd['kind'] == 'ZONE':
                out.append('%s#%d' % (nd['zone_name'], nd['island']))
            elif nd['kind'] == 'PCB_VIA':
                out.append('VIA@%s' % nd['layer'])
            else:
                out.append('%s@%s' % (nd['kind'], nd['layer']))
        return sorted(set(out))


PHASES = ('refill', 'decompose', 'verify', 'drc')


def paths(a):
    repo = pathlib.Path(a.repo).resolve()
    hw = repo / 'tracker/hardware'
    scratch = pathlib.Path(a.scratch)
    out = pathlib.Path(a.out)
    return dict(repo=repo, hw=hw, scratch=scratch, out=out,
                copy=scratch / 'copy',
                src=hw / (STEM + '.kicad_pcb'),
                pro=hw / (STEM + '.kicad_pro'),
                refill=scratch / 'copy' / (STEM + '_refill.kicad_pcb'),
                decom=scratch / 'copy' / (STEM + '_islands.kicad_pcb'),
                natives=out / 'island-natives.json')


def phase_refill(P):
    """Copy source + matching project into scratch, then refill the COPY only."""
    for s in ('.kicad_pcb', '.kicad_pro'):
        shutil.copy2(P['hw'] / (STEM + s), P['copy'] / (STEM + s))
    shutil.copy2(P['hw'] / 'fp-lib-table', P['copy'] / 'fp-lib-table')
    for name in ('footprints', 'schematics'):
        tgt = P['copy'] / name
        if not tgt.exists():
            tgt.symlink_to(P['hw'] / name, target_is_directory=True)
    shutil.copy2(P['copy'] / (STEM + '.kicad_pcb'), P['refill'])
    shutil.copy2(P['copy'] / (STEM + '.kicad_pro'),
                 P['refill'].with_suffix('.kicad_pro'))
    b = k.LoadBoard(str(P['refill']))
    k.ZONE_FILLER(b).Fill(b.Zones())
    k.SaveBoard(str(P['refill']), b)
    del b
    print('refill copy sha', sha(P['refill']),
          '| byte-identical to source', sha(P['refill']) == sha(P['src']))


def phase_decompose(P):
    dec = decompose(P['refill'], P['decom'])
    shutil.copy2(P['copy'] / (STEM + '.kicad_pro'), P['decom'].with_suffix('.kicad_pro'))
    (P['out'] / 'decompose.json').write_text(json.dumps(dec, indent=1))
    print('decomposed', len(dec['plan']), 'zones ->',
          sum(len(z['islands']) for z in dec['plan']), 'islands')
    print('base', dec['base'], 'copper_area', dec['base_copper_area_mm2'])


def phase_verify(P):
    ver = verify_decomposed(P['decom'])
    (P['out'] / 'verify.json').write_text(json.dumps(ver, indent=1))
    dec = json.loads((P['out'] / 'decompose.json').read_text())
    print('after', ver['stats'], 'copper_area', ver['copper_area_mm2'])
    print('copper delta mm2', round(ver['copper_area_mm2'] - dec['base_copper_area_mm2'], 6))


def phase_drc(P):
    for label, board in (('islands', P['decom']), ('base', P['refill'])):
        dest = P['out'] / ('drc-%s.json' % label)
        cmd = ['kicad-cli', 'pcb', 'drc', '--format', 'json', '--severity-all',
               '--output', str(dest), str(board)]
        p = subprocess.run(cmd, capture_output=True, text=True)
        rep = json.loads(dest.read_text())
        print(label, 'exit', p.returncode,
              '| unconnected', len(rep['unconnected_items']),
              '| violations', len(rep['violations']),
              '|', dict(collections.Counter(v['type'] for v in rep['violations'])))
        (P['out'] / ('drc-%s.meta.json' % label)).write_text(
            json.dumps(dict(command=cmd, exit=p.returncode,
                            stderr=p.stderr.strip(), stdout=p.stdout.strip()), indent=1))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--repo', required=True)
    ap.add_argument('--scratch', required=True)
    ap.add_argument('--out', required=True)
    ap.add_argument('--phase', choices=PHASES + ('all',), default='all')
    ap.add_argument('--select', default='', help='restrict Method B walk, comma-sep record ids')
    a = ap.parse_args()
    P = paths(a)
    P['scratch'].mkdir(parents=True, exist_ok=True)
    P['copy'].mkdir(parents=True, exist_ok=True)
    P['out'].mkdir(parents=True, exist_ok=True)

    if a.phase != 'all':
        globals()['phase_' + a.phase](P)
        return

    # Each phase gets its own interpreter: repeated board.Remove() corrupts the SWIG
    # type map process-wide (measured), so mutation and verification cannot share one.
    before = sha(P['src'])
    for ph in PHASES:
        cmd = [sys.executable, __file__, '--repo', str(P['repo']),
               '--scratch', str(P['scratch']), '--out', str(P['out']), '--phase', ph]
        r = subprocess.run(cmd, capture_output=True, text=True)
        print('== phase', ph, 'exit', r.returncode)
        for line in r.stdout.splitlines():
            if not line.startswith('2') and 'Debug:' not in line:
                print('   ', line)
        if r.returncode != 0:
            print(r.stderr[-3000:])
            raise SystemExit('phase %s failed' % ph)

    dec = json.loads((P['out'] / 'decompose.json').read_text())
    ver = json.loads((P['out'] / 'verify.json').read_text())
    island_report = json.loads((P['out'] / 'drc-islands.json').read_text())
    base_report = json.loads((P['out'] / 'drc-base.json').read_text())
    payload = dict(
        source_path=str(P['src'].relative_to(P['repo'])),
        source_sha256=before,
        source_sha256_after=sha(P['src']),
        source_unchanged=sha(P['src']) == before,
        refill_copy_sha256=sha(P['refill']),
        refill_is_byte_noop=(sha(P['refill']) == before),
        kicad=k.GetBuildVersion(),
        decompositions=dec,
        verification=ver,
        drc_islands=dict(meta=json.loads((P['out'] / 'drc-islands.meta.json').read_text()),
                         report=island_report),
        drc_base=dict(meta=json.loads((P['out'] / 'drc-base.meta.json').read_text()),
                      report=base_report),
    )
    P['natives'].write_text(json.dumps(payload, indent=1))
    print()
    print('source_unchanged', payload['source_unchanged'],
          '| refill_byte_noop', payload['refill_is_byte_noop'])
    print('copper area base', dec['base_copper_area_mm2'],
          '-> decomposed', ver['copper_area_mm2'])
    print('unconnected base', len(base_report['unconnected_items']),
          '-> islands', len(island_report['unconnected_items']))


if __name__ == '__main__':
    main()
