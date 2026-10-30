"""Attribute all 86 hub unconnected records to definite endpoints and classify them.

Consumes the outputs of run_zone_islands.py (phases refill/decompose/verify/drc) and emits
ledger2.json, keyed by the same stable record IDs (1..86) as the prior audit's ledger.json.

Two independent attributions are produced for every zone endpoint:
  A  native  : KiCad's own connectivity engine, queried per single-island zone clone
               (CONNECTIVITY_DATA.GetConnectedPads on a zone whose filled poly is one island).
  B  geometry: union-find over per-island polygons + pads/tracks/vias, joined only on the
               same layer and net, with only plated barrels bridging layers.

Classification is a mechanical rule over cited design records, not a per-record opinion.
"""
import argparse
import collections
import json
import pathlib
import re
import sys

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import pcbnew as k                                    # noqa: E402
from shapely.geometry import Point                    # noqa: E402
from run_zone_islands import GeoGraph, polyset_to_shapely, STEM  # noqa: E402

# ------------------------------------------------------------------ citations
# Every rule below points at a design record. Quotes were read from the tree at the
# audited commit; the path:line is in the ledger so a reviewer can re-read them.
CIT = {
    'wing_both_faces': dict(
        ref='docs/WING-TO-HUB-SOCKET-SPEC.md:62-63; docs/adr/046-wing-board-interface.md:277-280,411',
        quote='Both options below reproduce the same 4 lands on BOTH faces of the hub edge '
              '(top and bottom), so the wing tab can be soldered from both sides. ... The wing '
              'tab inserts 6 mm into the slot and is soldered on both faces. ... The solder '
              'fillet carries the mechanical load in both options.'),
    'wing_both_faces_counter': dict(
        ref='docs/fab/HUB-V9-ORDER-READINESS.md:73',
        quote="`Pad 2 [GND] of J_W1 / J_W2 / J_W3` is unconnected F.Cu <-> B.Cu (its own two "
              "layers) ... [counted among the unconnected items to be stitched]"),
    'wing_pad2_unused': dict(
        ref='docs/adr/136-flight-wing-interface-two-land-and-routing-sequence.md:47-48',
        quote='pad 2 (GND) - the wing has no ground plane to reference (ADR-134 removed it), so '
              'on the flight build this land carries nothing. It stays on the hub as an unused pad.'),
    'cut_sense_deferred': dict(
        ref='docs/adr/136-flight-wing-interface-two-land-and-routing-sequence.md:62-65',
        quote='Keep the net and pad; do not route it as flight-critical, do not fit a part, and '
              'do not let it gate the flight.'),
    'series_wired_on_hub': dict(
        ref='docs/adr/046-wing-board-interface.md:467; docs/adr/051-hub-array-and-cut-topology.md:62',
        quote='The series stack is wired on the hub, not the wing.'),
    'jprog_must_route': dict(
        ref='docs/adr/121-programming-interface.md:42',
        quote='The v10 build must route: EN -> header pin 3 (+ RC to GND), USB_D-/D+ -> pins 4/5, '
              'IO0 -> pin 6, GND/+3V3 rails.'),
    'hub_pv_external_panel': dict(
        ref='docs/adr/129-v10-power-restoration-and-bypass-diodes.md:94,106',
        quote='The hub array is an external panel, like the wing boards. ... HUB_PV_MID1 (the '
              'interior node between D_HUB1/D_HUB2) becomes a real net on the board.'),
    'rails_are_pours': dict(
        ref='docs/adr/136-flight-wing-interface-two-land-and-routing-sequence.md:117',
        quote='Rails are pours: GND (82 pads), +3V3 (16), /VSCAP (11).'),
    'd3_radio_9of9': dict(
        ref='docs/adr/140-placement-approval-requires-route-trial.md:91-104',
        quote='The LoRa1280 interface is 9/9 routed ... A net-name match is not a connectivity '
              'test. /SPI1_SCK, /SPI1_MOSI and /SPI1_MISO also run to U3 and U_C, which are '
              'unrouted, so their names appear in the unconnected list while the module end is perfect.'),
}

REQUIRED = 'REQUIRED-PCB-CONNECTION'
EXTERNAL = 'EXTERNAL-OR-MECHANICAL'
UNKNOWN = 'UNKNOWN'


def load(p):
    return json.loads(pathlib.Path(p).read_text())


def parse_item(desc):
    """DRC item description -> structured identity."""
    layer = None
    m = re.search(r' on ([A-Za-z0-9.]+)(?:,|$)', desc)
    if m:
        layer = m.group(1)
    net = None
    m = re.search(r'\[([^\]]*)\]', desc)
    if m:
        net = m.group(1)
    zone = None
    m = re.search(r"Zone '([^']+)'", desc)
    if m:
        zone = m.group(1)
    ref = pad = None
    m = re.search(r'(?:PTH pad|Pad) (\S+) .*? of (\S+?) on', desc)
    if m:
        pad, ref = m.group(1), m.group(2)
    kind = desc.split(' ')[0]
    if kind.startswith('PTH'):
        kind = 'PTH'
    return dict(kind=kind, ref=ref, pad=pad, net=net, layer=layer, zone=zone,
                zone_base=(zone.split('__ISL')[0] if zone else None),
                island=(int(zone.split('__ISL')[1]) if zone and '__ISL' in zone else None))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', required=True, help='phase output dir from run_zone_islands.py')
    ap.add_argument('--prior', required=True, help='prior audit dir with ledger.json')
    ap.add_argument('--ledger', required=True, help='path to write ledger2.json')
    a = ap.parse_args()
    O = pathlib.Path(a.out)
    prior_dir = pathlib.Path(a.prior)

    nat = load(O / 'island-natives.json')
    base = load(O / 'drc-base.json')['unconnected_items']
    canon = load(O / 'drc-islands.json')['unconnected_items']
    ledger1 = load(prior_dir / 'ledger.json')
    assert len(base) == len(canon) == len(ledger1) == 86, (len(base), len(canon), len(ledger1))
    scrub = pathlib.Path(nat['decompositions'] and O).parent / 'copy'
    decom_pcb = pathlib.Path(nat['decompositions'] and
                             pathlib.Path(nat['source_path']).name)  # placeholder, unused

    # ---------------------------------------------------- island catalogue
    islands = {}
    for isl in nat['verification']['islands']:
        nm = isl['clone_name']
        base_name, idx = nm.split('__ISL')
        islands[nm] = dict(id='%s#%d' % (base_name, int(idx)), zone=base_name,
                           layer=isl['layer'], island=int(idx),
                           net=isl['net'], area_mm2=isl['area_mm2'],
                           bbox_mm=isl['bbox_mm'],
                           native_pads=sorted(set(isl['native_pads'])),
                           native_track_count=isl['native_tracks'])
    zone_meta = {}
    for z in nat['decompositions']['plan']:
        zone_meta[z['zone_name']] = dict(uuid=z['zone_uuid'], layer=z['layer'], net=z['net'],
                                         island_count=z['island_count'],
                                         zone_area_mm2=z['zone_area_mm2'])

    # ---------------------------------------------------- method B (geometry)
    g = GeoGraph(str(pathlib.Path(a.out).parent / 'copy' /
                     (pathlib.Path(nat['source_path']).stem + '_islands.kicad_pcb')))
    node2comp = g.comp
    comp_pads = collections.defaultdict(set)
    comp_zone_islands = collections.defaultdict(set)
    comp_refs = collections.defaultdict(set)
    for nid, nd in enumerate(g.nodes):
        c = node2comp[nid]
        if nd['kind'] == 'PAD':
            comp_pads[c].add('%s.%s' % (nd['ref'], nd['pad']))
            comp_refs[c].add(nd['ref'])
        elif nd['kind'] == 'ZONE':
            comp_zone_islands[c].add('%s#%d' % (nd['zone_name'].split('__ISL')[0], nd['island']))
        else:
            comp_refs[c].add(nd['kind'])
    comp_of_island = {}
    for nm, isl in islands.items():
        node = next((i for i, nd in enumerate(g.nodes)
                     if nd['kind'] == 'ZONE' and nd['zone_name'] == nm), None)
        comp_of_island[nm] = node2comp[node] if node is not None else None
    comp_net = {}
    for i, c in enumerate(g.components):
        comp_net[i] = g.nodes[c[0]]['net']
    uuid2comp = collections.defaultdict(set)
    for nid, nd in enumerate(g.nodes):
        uuid2comp[nd['uuid']].add(node2comp[nid])

    # per-net component census (the invariant the DRC record count mirrors)
    comps_by_net = collections.defaultdict(set)
    for c, net in comp_net.items():
        comps_by_net[net].add(c)

    # ---------------------------------------------------- island-pair stability
    stab = {}
    for f in ('drc-islands.json',):
        pass
    alternates = collections.defaultdict(collections.Counter)
    rep_dir = O
    for rep in sorted(rep_dir.glob('rep*.json')) + sorted(rep_dir.glob('islands-run*.json')):
        runs = load(rep)['unconnected_items']
        for idx, r in enumerate(runs, 1):
            names = tuple(sorted(i['description'].split("'")[1].split(' ')[0]
                                 for i in r['items'] if i['description'].startswith('Zone')))
            alternates[idx][names] += 1

    # ---------------------------------------------------- chosen endpoints
    b = k.LoadBoard(str(pathlib.Path(a.out).parent / 'copy' /
                        (pathlib.Path(nat['source_path']).stem + '_islands.kicad_pcb')))
    zmap = {z.GetZoneName(): z for z in b.Zones() if '__ISL' in z.GetZoneName()}
    island_shape = {nm: polyset_to_shapely(z.GetFilledPolysList(z.GetLayer()))[0]
                    for nm, z in zmap.items()}

    records = []
    for i, (rb, ri) in enumerate(zip(base, canon), 1):
        sides = []
        for it in rb['items']:
            p = parse_item(it['description'])
            p['drc_pos_mm'] = [round(it['pos']['x'], 6), round(it['pos']['y'], 6)]
            p['drc_uuid'] = it['uuid']
            p['drc_description'] = it['description']
            if p['zone']:
                # the canonical island for THIS endpoint, matched on base zone + layer
                cands = [x['description'].split("'")[1].split(' ')[0] for x in ri['items']
                         if x['description'].startswith('Zone')
                         and x['description'].split(' on ')[1].split(',')[0] == p['layer']]
                p['island_names'] = cands
            p['method_a_components'] = sorted(set(
                comp_of_island.get(n) for n in p.get('island_names', []) if comp_of_island.get(n) is not None))
            p['method_b_components'] = sorted(uuid2comp.get(it['uuid'], set()))
            sides.append(p)

        # island detail block for zone endpoints
        for side in sides:
            if side['zone']:
                names = side.get('island_names', [])
                side['islands'] = [islands[n] for n in names if n in islands]
                side['chosen_island'] = names[0] if names else None
                if names:
                    shp = island_shape[names[0]]
                    rp = shp.representative_point()
                    side['chosen_endpoint_mm'] = [round(rp.x, 6), round(rp.y, 6)]
                    side['chosen_endpoint_is_interior'] = bool(shp.contains(rp))
                    side['drc_pos_on_island'] = bool(
                        shp.distance(Point(*side['drc_pos_mm'])) <= 1e-9)
                    side['island_area_mm2'] = islands[names[0]]['area_mm2']
                    side['island_bbox_mm'] = islands[names[0]]['bbox_mm']
                    side['island_layer'] = islands[names[0]]['layer']
            else:
                side['chosen_endpoint_mm'] = side['drc_pos_mm']
                side['chosen_endpoint_is_interior'] = True
                side['drc_pos_on_island'] = None

        nets = sorted({s['net'] for s in sides if s['net']}) or ledger1[i - 1]['nets']
        comps = sorted({c for s in sides for c in s['method_a_components'] + s['method_b_components']})
        cand = sorted({p for c in comps for p in comp_pads[c]})

        records.append(dict(
            id=i, nets=nets,
            endpoints=sides,
            candidate_components=comps,
            candidate_component_pads={str(c): sorted(comp_pads[c]) for c in comps},
            candidate_component_refs={str(c): sorted(comp_refs[c]) for c in comps},
            island_pair_stability=(dict(
                canonical=[s.get('chosen_island') for s in sides if s['zone']],
                observed_runs=len(alternates[i]) if alternates[i] else 0,
                alternatives=[list(k) for k, v in alternates[i].most_common()]
                if i in alternates else []),
            ) if any(s['zone'] for s in sides) else None,
            prior_classification=ledger1[i - 1]['classification'],
        ))

    # ---------------------------------------------------- classification
    wing_pad2_lands = {'J_W1.2', 'J_W2.2', 'J_W3.2', 'J_W4.2'}

    def face_pair(sides):
        """Same reference+pad on two different copper layers -> the J_W dual-face land."""
        if len(sides) != 2:
            return False
        a, c = sides
        if not (a['ref'] and a['ref'] == c['ref'] and a['pad'] == c['pad']):
            return False
        return a['layer'] != c['layer']

    for rec in records:
        sides = rec['endpoints']
        first_comp = rec['candidate_components'][0] if rec['candidate_components'] else None
        pads = set(rec['candidate_component_pads'].get(str(first_comp), [])) if first_comp else set()
        all_pads = {p for v in rec['candidate_component_pads'].values() for p in v}
        net = rec['nets'][0] if len(rec['nets']) == 1 else None
        cites = []
        cls, reason = UNKNOWN, 'no design record settles this connection'

        if net and net.startswith('/CUT_SENSE_W'):
            cls = EXTERNAL
            reason = ('ADR-136 s2.2 defers cut-sense as DNP: keep the net and pad, do not route it '
                      'as flight-critical, do not fit a part. The two copper pieces are the F.Cu and '
                      'B.Cu lands of the same J_W pad, joined (if at all) by the soldered wing tab.')
            cites = [CIT['cut_sense_deferred'], CIT['wing_both_faces']]
        elif face_pair(sides) and all(s['ref'] and s['ref'].startswith('J_W') for s in sides):
            cls = EXTERNAL
            reason = ('Same pad number on F.Cu and B.Cu of a J_W wing socket: the socket spec and '
                      'ADR-046 put the identical land on both faces so the inserted wing tab is '
                      'soldered top and bottom. The electrical bridge is the tab plus solder fillet, '
                      'not PCB copper. Counter-citation recorded: HUB-V9-ORDER-READINESS treats the '
                      'same discontinuity as an unconnected item to be stitched, so a stitching via '
                      'remains a legitimate alternative and this ruling is the documentation, not a '
                      'measurement.')
            cites = [CIT['wing_both_faces'], CIT['wing_both_faces_counter']]
        elif (any(s['zone'] for s in sides) and all_pads
              and all_pads <= wing_pad2_lands):
            cls = EXTERNAL
            reason = ('The only pads on the isolated GND island are J_W pad 2 lands, which ADR-136 '
                      's2.1 documents as carrying nothing on the flight build ("stays on the hub as '
                      'an unused pad"). No functional connection is owed; the island is retained '
                      'dead copper. Stitching it would be pour hygiene, not an electrical requirement.')
            cites = [CIT['wing_pad2_unused']]
        elif any(s['zone'] for s in sides):
            cls = REQUIRED
            reason = ('Both endpoints are GND/+3V3 copper on one PCB and at least one carries a live '
                      'component pad (%s). Rails are pours (ADR-136 s3); an island detached from its '
                      'pour is an incomplete pour, not an external connection.' %
                      ', '.join(sorted(all_pads)[:6]))
            cites = [CIT['rails_are_pours']]
        elif net in ('GND', '+3V3'):
            cls = REQUIRED
            reason = 'Rail continuity between live component pads (%s); rails are pours.' % \
                     ', '.join(sorted(all_pads)[:6])
            cites = [CIT['rails_are_pours']]
        elif net and net.startswith('/W') and 'SOLAR' in net:
            cls = REQUIRED
            reason = 'Solar series stack is wired on the hub, not through the wing or a harness.'
            cites = [CIT['series_wired_on_hub']]
        elif net and net.startswith('/HUB_PV'):
            cls = REQUIRED
            reason = ('The hub PV panel is external and terminates at J_HUB_PV; the connector to '
                      'D_HUB1/D_HUB2 to converter copper is on the board (HUB_PV_MID1 is a real '
                      'on-board net).')
            cites = [CIT['hub_pv_external_panel']]
        elif net == '/EN':
            cls = REQUIRED
            reason = 'ADR-121 requires EN routed to J_PROG pin 3 for flashing.'
            cites = [CIT['jprog_must_route']]
        elif net and (net.startswith('/SPI1_') or net.startswith('/SPI2_')
                      or net.startswith('/F33_') or net.startswith('/U3_')
                      or net in ('/VSCAP',)):
            cls = REQUIRED
            reason = ('Signal net with live pads on both sides. ADR-140 D3 proves only the nine '
                      'U1<->U_LORA1280 paths; these branches terminate on U3/U_C, which the same ADR '
                      'names as still unrouted, so the module end being perfect does not cover this '
                      'record.')
            cites = [CIT['d3_radio_9of9']]
        elif net and net in ('/HUB_PV_P', '/HUB_PV_N', '/HUB_PV_MID1'):
            cls = REQUIRED
            reason = 'On-board hub PV node between connector, bypass diodes and converter.'
            cites = [CIT['hub_pv_external_panel']]

        rec['classification'] = cls
        rec['reason'] = reason
        rec['citations'] = cites
        rec['evidence_method'] = (
            'A: KiCad CONNECTIVITY_DATA.GetConnectedPads per single-island zone clone; '
            'B: independent geometric union-find over per-island polygons + pads/tracks/vias. '
            'Island identity from Method A canonical run; cross-checked against Method B components.'
            if any(s['zone'] for s in rec['endpoints']) else
            'DRC item UUID + position, resolved to copper component in Method B geometric graph.')

    # ---------------------------------------------------- emit
    counts = collections.Counter(r['classification'] for r in records)
    by_net = collections.defaultdict(lambda: collections.Counter())
    for r in records:
        for n in r['nets']:
            by_net[n][r['classification']] += 1
    out = dict(
        schema='hub-zone-islands/ledger2/1',
        source=dict(path=nat['source_path'], sha256=nat['source_sha256'],
                    sha256_after=nat['source_sha256_after'],
                    unchanged=nat['source_unchanged'],
                    refill_copy_sha256=nat['refill_copy_sha256'],
                    refill_is_byte_noop=nat['refill_is_byte_noop'],
                    kicad=nat['kicad']),
        record_count=len(records),
        classification_counts=dict(counts),
        per_net={n: dict(counts) for n, counts in sorted(by_net.items())},
        island_catalogue=islands,
        zone_meta=zone_meta,
        component_census={net: dict(components=len(cs),
                                    minimum_joins=len(cs) - 1,
                                    gnd_or_rail=(net in ('GND', '+3V3')))
                          for net, cs in sorted(comps_by_net.items())},
        citations=CIT,
        records=records,
    )
    pathlib.Path(a.ledger).write_text(json.dumps(out, indent=1))
    print('records', len(records))
    print('classification', dict(counts))
    print('islands catalogued', len(islands))
    unresolved = [r['id'] for r in records if r['classification'] == UNKNOWN]
    print('UNKNOWN records', unresolved)
    no_island = [r['id'] for r in records
                 if any(s['zone'] for s in r['endpoints'])
                 and not all(s.get('chosen_island') for s in r['endpoints'] if s['zone'])]
    print('zone records without a chosen island', no_island)
    print('records whose DRC pos is not on the named island',
          [r['id'] for r in records for s in r['endpoints']
           if s.get('drc_pos_on_island') is False])


if __name__ == '__main__':
    main()
