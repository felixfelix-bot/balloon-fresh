#!/usr/bin/env python3
"""Read-only reference placement disposition, separate sides in common top-view XY.
Bounding boxes are not courtyard checks or a compact-placement result.
"""
import json
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle, Patch

HERE = Path(__file__).resolve().parent
audit = json.loads((HERE / 'layer_audit.json').read_text())
verdicts = json.loads((HERE / 'verdicts.json').read_text())['verdicts']
colors = {'KEEP': '#2e7d32', 'OPTIONAL': '#d99000', 'REMOVE': '#c62828', 'REPLACE': '#6a1b9a'}
board_only = {'U_E28': 'REMOVE', **{f'{s}{i}': 'KEEP' for s in ('H', 'HW') for i in range(1,5)}}
fig, axes = plt.subplots(1, 2, figsize=(15, 10), dpi=150)
bb = audit['outline']['bbox_mm']
seen = []
for ax, side in zip(axes, ('top', 'bottom')):
    ax.add_patch(Rectangle((bb['x_min'], bb['y_min']), bb['width_mm'], bb['height_mm'], fill=False, lw=2))
    parts = [fp for fp in audit['footprints'] if fp['side'] == side]
    # Numbered key below the figure avoids ambiguous, overlapping tiny references.
    key = []
    for fp in parts:
        ref = fp['ref']
        verdict = verdicts[ref]['verdict'] if ref in verdicts else board_only[ref]
        x,y,w,h = fp['bbox_mm']
        ax.add_patch(Rectangle((x,y),w,h,facecolor=colors[verdict],edgecolor=colors[verdict],alpha=.45))
        if w*h >= 30 or verdict in ('REMOVE','REPLACE'):
            ax.text(x+w/2,y+h/2,ref,ha='center',va='center',fontsize=9,
                    bbox=dict(facecolor='white',alpha=.9,edgecolor='none',pad=1))
        seen.append(ref)
        key.append(ref)
    ax.set(title=f'{side.title()} side — {len(parts)} footprints', xlabel='x (mm)', ylabel='y (mm)',
           xlim=(bb['x_min']-3,bb['x_max']+3),ylim=(bb['y_max']+3,bb['y_min']-3))
    ax.set_aspect('equal'); ax.grid(alpha=.15)
assert len(seen) == len(audit['footprints']) and len(set(seen)) == len(seen)
fig.suptitle(f'MINIMAL variant: disposition on existing stage-1 placement (SHA {audit["board_sha256"][:8]})',fontsize=14)
fig.legend(handles=[Patch(facecolor=colors[k],label=v) for k,v in [
    ('KEEP','Retain function / interface'),('OPTIONAL','Qualification pending; not permission to delete'),
    ('REMOVE','Remove U_C and ranging site U_E28'),('REPLACE','Replace J_PROG with pogo pads')]],
    loc='lower center',bbox_to_anchor=(.5,.065),ncol=2,fontsize=10)
fig.text(.5,.025,'Same top-view XY on both panels (bottom is NOT mirrored). Boxes are footprint extents, not exact bodies.\nSmall parts shown without labels; all references and dispositions are in the accompanying JSON. Not a new layout or a fit verdict.',
         ha='center',fontsize=9)
fig.subplots_adjust(top=.92,bottom=.18,wspace=.18)
out=HERE/'keep-optional-remove-plot.png'
fig.savefig(out,facecolor='white')
print(f'PASS: {len(seen)} unique footprints plotted on separate sides; wrote {out}')
