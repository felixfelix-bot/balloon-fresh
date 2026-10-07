#!/usr/bin/env python3
"""Gate: the WING board's committed 3D models stay parametric, sourced and assigned.

The wing render (`kicad-cli pcb render tracker/hardware/wing_board/wing_board_v9.kicad_pcb`)
is only as good as these four invariants, so each is checked here rather than trusted:

1. **Parametric.** `scripts/gen_3d_models_wing.py --check` must exit 0 -- the committed
   `tracker/hardware/3dmodels/**/*.wrl` are exactly what the generator produces, so an
   edit by hand is caught instead of silently diverging from the cited dimensions.
2. **Sourced.** Every model header carries a `# source` line, and the header cites an
   in-repo record (an ADR or the board file) *or* says `TODO(unverified)` out loud.
   An uncited number is the failure mode this gate exists to stop.
3. **KiCad VRML convention.** VRML 2.0 header, balanced braces, an IndexedFaceSet per
   shape, and -- the one that is easy to get wrong -- the coordinates are in KiCad's
   2.54 mm units, so a model's coordinate extent x 2.54 reproduces the cited mm size.
4. **Assigned.** The board's 12 placed references each carry either a `(model ...)`
   pointing at a file that exists, or are on the documented `NO_MODEL_OK` list.

Run:  python3 -m pytest tests/test_3d_models_wing.py -v
"""
from __future__ import annotations

import pathlib
import re
import subprocess
import sys

import pytest

REPO = pathlib.Path(__file__).resolve().parents[1]
MODEL_TREE = REPO / 'tracker' / 'hardware' / '3dmodels'
GEN = REPO / 'scripts' / 'gen_3d_models_wing.py'
BOARD = REPO / 'tracker' / 'hardware' / 'wing_board' / 'wing_board_v9.kicad_pcb'
COVERAGE_DOC = REPO / 'docs' / '3d-model-coverage-wing.md'

MM_PER_UNIT = 2.54

# References that deliberately carry no model, each with the measured reason (see
# docs/3d-model-coverage-wing.md): kicad-cli punches the NC drill bore itself and a model
# occupying that volume plugs it (measured: 20/25 -> 0/25 transparent px at each hole site).
NO_MODEL_OK = {'H1': 'NPTH bore rendered by kicad-cli itself; a model plugs it (measured)',
               'H2': 'NPTH bore rendered by kicad-cli itself; a model plugs it (measured)',
               'H3': 'NPTH bore rendered by kicad-cli itself; a model plugs it (measured)'}

# The three cells the wing carries, and the class they are (ADR-049 measured inputs: SMALL =
# 52.07 x 19.65 x 0.20-0.21 mm; LARGE = 78.55 x 38.90 x 0.21 mm, ADR-051 §1.4).
CELL_MODEL = 'solar_cell_small_52.07x19.65x0.21.wrl'

MODELS = sorted(MODEL_TREE.rglob('*.wrl'))


def _board() -> str:
    return BOARD.read_text()


def _blocks(text: str, tag: str):
    """Every balanced `(tag ...)` s-expression in text."""
    out = []
    for m in re.finditer(r'\(' + tag + r'\b', text):
        depth = 0
        for j in range(m.start(), len(text)):
            if text[j] == '(':
                depth += 1
            elif text[j] == ')':
                depth -= 1
                if depth == 0:
                    out.append(text[m.start():j + 1])
                    break
    return out


def _points(text: str):
    """All `x y z` triples inside `Coordinate { point [ ... ] }`."""
    pts = []
    for body in re.findall(r'point \[(.*?)\]', text, re.S):
        for tri in re.findall(r'(-?\d+\.?\d*(?:[eE][-+]?\d+)?)\s+'
                              r'(-?\d+\.?\d*(?:[eE][-+]?\d+)?)\s+'
                              r'(-?\d+\.?\d*(?:[eE][-+]?\d+)?)', body):
            pts.append(tuple(float(v) for v in tri))
    return pts


def test_models_exist():
    assert MODELS, f'no models under {MODEL_TREE}'
    assert any(m.name == CELL_MODEL for m in MODELS), 'the solar-cell model is missing'


def test_model_tree_is_what_the_generator_produces():
    r = subprocess.run([sys.executable, str(GEN), '--check'], cwd=REPO,
                       capture_output=True, text=True)
    assert r.returncode == 0, (
        'committed models differ from scripts/gen_3d_models_wing.py -- regenerate with\n'
        f'  python3 scripts/gen_3d_models_wing.py\nstdout:\n{r.stdout}\nstderr:\n{r.stderr}')


@pytest.mark.parametrize('path', MODELS, ids=lambda p: p.name)
def test_header_cites_a_source_or_says_todo(path: pathlib.Path):
    head = path.read_text().splitlines()
    assert head[0].strip() == '#VRML V2.0 utf8', f'{path.name}: not a VRML 2.0 file'
    src = [ln for ln in head[:20] if ln.startswith('# source')]
    assert src, f'{path.name}: no "# source" line -- provenance is mandatory'
    joined = ' '.join(src)
    cited = ('adr/' in joined) or ('kicad_pcb' in joined)
    assert cited or 'TODO(unverified)' in joined, (
        f'{path.name}: source line cites no in-repo record and does not say TODO(unverified): {src}')


@pytest.mark.parametrize('path', MODELS, ids=lambda p: p.name)
def test_model_is_wellformed_vrml(path: pathlib.Path):
    text = path.read_text()
    assert text.count('{') == text.count('}'), f'{path.name}: unbalanced braces'
    assert 'IndexedFaceSet' in text, f'{path.name}: no IndexedFaceSet'
    assert 'coordIndex' in text, f'{path.name}: no coordIndex'
    pts = _points(text)
    assert pts, f'{path.name}: no coordinates'
    for p in pts:
        assert all(abs(c) < 1000 for c in p), f'{path.name}: implausible coordinate {p}'
    # every face is a closed polygon (boxes are quads; the fiducial's caps are 18-gons)
    for idx in re.findall(r'coordIndex \[(.*?)\]', text, re.S):
        rows = [r.strip() for r in idx.split('-1') if r.strip().strip(',').strip()]
        for row in rows:
            n = len([v for v in row.split(',') if v.strip()])
            assert n >= 3, f'{path.name}: a face has {n} vertices, needs >= 3 ({row!r})'


def test_small_cell_model_matches_the_cited_size_in_kicad_units():
    """The load-bearing convention: KiCad reads a VRML coordinate as 2.54 mm.

    If the models were authored in mm the cell would render 2.54x too large (132 mm long
    against a 176 mm board) -- this asserts the size against ADR-049's measured 52.07 x
    19.65 x 0.20-0.21 mm, which is what the render confirmed (3 blue runs of 51.8 mm).
    """
    pts = _points((MODEL_TREE / 'cells' / CELL_MODEL).read_text())
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    zs = [p[2] for p in pts]
    size = ((max(xs) - min(xs)) * MM_PER_UNIT, (max(ys) - min(ys)) * MM_PER_UNIT,
            (max(zs) - min(zs)) * MM_PER_UNIT)
    assert abs(size[0] - 52.07) < 0.02, f'cell length {size[0]:.3f} mm != 52.07 mm'
    assert abs(size[1] - 19.65) < 0.02, f'cell width {size[1]:.3f} mm != 19.65 mm'
    # 0.21 mm cell + the 0.001 mm anti-z-fighting lift on the face plate
    assert abs(size[2] - 0.21) < 0.01, f'cell thickness {size[2]:.3f} mm != 0.21 mm'


def test_board_assigns_a_resolvable_model_to_every_reference():
    text = _board()
    refs, assigned = {}, {}
    for fp in _blocks(text, 'footprint'):
        ref = re.search(r'\(property "Reference" "([^"]*)"', fp).group(1)
        model = re.search(r'\(model "([^"]*)"', fp)
        refs[ref] = True
        if model:
            assigned[ref] = model.group(1)
    assert sorted(refs) == ['FB1', 'FID1', 'FID2', 'FID3', 'H1', 'H2', 'H3',
                            'J1', 'RF1', 'SC1', 'SC2', 'SC3'], sorted(refs)
    for ref, path in assigned.items():
        resolved = path.replace('${KIPRJMOD}', str(BOARD.parent))
        assert pathlib.Path(resolved).is_file(), f'{ref}: {path} does not resolve'
        assert path.startswith('${KIPRJMOD}/../3dmodels/'), f'{ref}: unexpected path {path}'
        assert not assigned.get(ref, '').startswith('/'), f'{ref}: absolute path is not portable'
    missing = sorted(set(refs) - set(assigned))
    assert missing == sorted(NO_MODEL_OK), f'unexplained references without a model: {missing}'
    assert len(assigned) == 9, f'expected 9 modelled references, got {len(assigned)}'


def test_coverage_report_exists_and_lists_every_reference():
    assert COVERAGE_DOC.is_file(), f'{COVERAGE_DOC} is missing'
    doc = COVERAGE_DOC.read_text()
    for ref in ('FB1', 'FID1', 'FID2', 'FID3', 'H1', 'H2', 'H3', 'J1', 'RF1',
                'SC1', 'SC2', 'SC3'):
        assert ref in doc, f'the coverage report never mentions {ref}'
    for needle in ('52.07', '19.65', 'NO MODEL', 'TODO(unverified)',
                   'assembly'):
        assert needle in doc, f'the coverage report never states {needle!r}'


def test_board_still_carries_the_wings_12_references_and_the_cells():
    text = _board()
    assert text.count('(footprint ') == 12
    assert text.count('(segment ') == 8
    # the three cells are the SMALL class of ADR-049 (52.07 x 19.65), not the LARGE one
    assert text.count('"WingV9:SolarCell_52x19mm"') == 3
    assert 'SolarCell_52x19mm_0.5V' in text
