#!/usr/bin/env python3
"""Render the v10 2.4 GHz site status figure.

Two panels, one page:
  LEFT  — measured geometry: all copper faint, the new LoRa1280 site with its 16 pads,
          U1, and the 9 unrouted nets drawn as the connections that still have to be made.
  RIGHT — the numbers, and the two hypotheses that measurement has already eliminated.

The board is dumped by the distro python (pcbnew lives there) into JSON; this script only
draws, so it runs under the venv python that has matplotlib.
"""
from __future__ import annotations

import json
import pathlib
import subprocess

import matplotlib

matplotlib.use("Agg")
import matplotlib.patches as mp
import matplotlib.pyplot as plt

REPO = pathlib.Path(__file__).resolve().parents[2]
BOARD = REPO / "tracker/hardware/hub_board_v10.kicad_pcb"
OUT = REPO / "docs/fab/status/lora1280-site-status.png"

DUMP = r"""
import json, pcbnew
b = pcbnew.LoadBoard(%r)
o = {"tracks": [], "pads": [], "outline": [], "fp": {}, "nets": {}}
for d in b.GetDrawings():
    if d.GetLayerName() == "Edge.Cuts":
        try:
            o["outline"].append([d.GetStart().x/1e6, d.GetStart().y/1e6,
                                 d.GetEnd().x/1e6, d.GetEnd().y/1e6])
        except Exception:
            pass
for t in b.GetTracks():
    if isinstance(t, pcbnew.PCB_VIA):
        o["tracks"].append(["via", t.GetPosition().x/1e6, t.GetPosition().y/1e6,
                            t.GetPosition().x/1e6, t.GetPosition().y/1e6, t.GetLayerName()])
    else:
        o["tracks"].append(["seg", t.GetStart().x/1e6, t.GetStart().y/1e6,
                            t.GetEnd().x/1e6, t.GetEnd().y/1e6, t.GetLayerName()])
fp = next(f for f in b.GetFootprints() if f.GetReference() == "U_LORA1280")
for p in fp.Pads():
    o["pads"].append([p.GetNumber(), p.GetPinFunction(), p.GetNetname() or "",
                      p.GetPosition().x/1e6, p.GetPosition().y/1e6,
                      p.GetSize().x/1e6, p.GetSize().y/1e6])
o["fp"] = {"ref": "U_LORA1280", "x": fp.GetPosition().x/1e6, "y": fp.GetPosition().y/1e6,
           "layer": fp.GetLayerName()}
bb = b.GetBoardEdgesBoundingBox()
o["board"] = [bb.GetLeft()/1e6, bb.GetTop()/1e6, bb.GetRight()/1e6, bb.GetBottom()/1e6]
u1 = next((f for f in b.GetFootprints() if f.GetReference() == "U1"), None)
if u1:
    bb = u1.GetBoundingBox(False, False)
    o["fp_u1"] = [bb.GetLeft()/1e6, bb.GetTop()/1e6, bb.GetRight()/1e6, bb.GetBottom()/1e6]
RADIO = ["/SPI1_SCK","/SPI1_MOSI","/SPI1_MISO","/E28_CS_N","/E28_BUSY",
         "/E28_RESET_N","/E28_DIO1","/E28_DIO2","/E28_DIO3"]
for f in b.GetFootprints():
    for p in f.Pads():
        if p.GetNetname() in RADIO:
            o["nets"].setdefault(p.GetNetname(), []).append(
                [f.GetReference(), p.GetNumber(), p.GetPosition().x/1e6, p.GetPosition().y/1e6])
print(json.dumps(o))
""" % str(BOARD)


def dump() -> dict:
    r = subprocess.run(["/usr/bin/python3", "-c", DUMP], capture_output=True, text=True, timeout=300)
    if r.returncode != 0:
        raise SystemExit(f"board dump failed: {r.stderr[-600:]}")
    return json.loads(r.stdout.strip().splitlines()[-1])


def main() -> int:
    d = dump()
    fig = plt.figure(figsize=(13.6, 8.0), facecolor="#0d1117")
    gs = fig.add_gridspec(1, 2, width_ratios=[1.0, 0.82], wspace=0.06)
    ax = fig.add_subplot(gs[0, 0])
    tx = fig.add_subplot(gs[0, 1])

    for a in (ax, tx):
        a.set_facecolor("#0d1117")
    ax.set_aspect("equal")
    ax.invert_yaxis()          # pcbnew Y grows downward

    # board outline as one clean rectangle (the segment list produced a stray diagonal
    # wherever a rectangle shape reported only its two corners)
    bb = d["board"]
    ax.add_patch(mp.Rectangle((bb[0], bb[1]), bb[2] - bb[0], bb[3] - bb[1], facecolor="none",
                              edgecolor="#3d4652", lw=1.2, zorder=1))

    # all copper, faint; B.Cu lighter than F.Cu so the bottom side reads as the active one
    for kind, x1, y1, x2, y2, lay in d["tracks"]:
        c = "#26313d" if lay.startswith("F") else "#2f3f33"
        if kind == "via":
            ax.add_patch(mp.Circle((x1, y1), 0.25, color="#4a5a6a", zorder=2))
        else:
            ax.plot([x1, x2], [y1, y2], color=c, lw=0.55, zorder=2, solid_capstyle="round")

    # U1
    if "fp_u1" in d:
        l, t, r_, b_ = d["fp_u1"]
        ax.add_patch(mp.Rectangle((l, t), r_ - l, b_ - t, facecolor="#1f6feb",
                                  alpha=0.20, edgecolor="#58a6ff", lw=1.2, zorder=3))
        ax.text(l + 0.5, t + 2.2, "U1  ESP32-S3", color="#9ecbff", fontsize=9,
                fontweight="bold", zorder=6)

    # the new site
    fpx, fpy = d["fp"]["x"], d["fp"]["y"]
    ax.add_patch(mp.Rectangle((fpx - 8.0, fpy - 8.0), 16.0, 16.0, facecolor="#b62324",
                              alpha=0.13, edgecolor="#ff7b72", lw=1.6, ls="--", zorder=4))
    ax.text(fpx - 7.6, fpy - 9.4, "U_LORA1280   (B.Cu, 16x16)",
            color="#ff9d95", fontsize=9.5, fontweight="bold", zorder=9,
            bbox=dict(facecolor="#0d1117", edgecolor="none", pad=1.6))
    for num, func, net, x, y, sx, sy in d["pads"]:
        col = "#f0b429" if func == "ANT" else "#e6edf3"
        ax.add_patch(mp.Rectangle((x - sx / 2, y - sy / 2), sx, sy, facecolor=col,
                                  alpha=0.85, edgecolor="none", zorder=5))
        if func in ("ANT", "VCC", "NSS", "NRESET"):
            ax.text(x, y, num, color="#0d1117", fontsize=6.5, ha="center",
                    va="center", fontweight="bold", zorder=7)
    ax.text(fpx + 9.1, fpy + 7.1, "ANT", color="#f0b429", fontsize=8.5, ha="left",
            va="center", fontweight="bold", zorder=9)

    # the 9 connections still to be made
    cols = ["#ff7b72", "#79c0ff", "#7ee787", "#d2a8ff", "#ffa657", "#f778ba",
            "#56d364", "#ffd33d", "#a5d6ff"]
    for i, (net, pads) in enumerate(sorted(d["nets"].items())):
        if len(pads) < 2:
            continue
        far = next((p for p in pads if p[0] != "U_LORA1280"), pads[0])
        near = [p for p in pads if p[0] == "U_LORA1280"]
        if not near:
            continue
        near = near[0]
        ax.plot([near[2], far[2]], [near[3], far[3]], color=cols[i % len(cols)],
                lw=1.1, ls=(0, (3, 2)), alpha=0.95, zorder=6)
        ax.plot([far[2]], [far[3]], marker="o", ms=2.6, color=cols[i % len(cols)], zorder=7)

    # escape-corridor arrow, annotation kept clear of the arrowhead
    ax.annotate("", xy=(fpx, fpy - 8.0 - 7.0), xytext=(fpx, fpy - 8.0),
                arrowprops=dict(arrowstyle="-|>", color="#3fb950", lw=2.0), zorder=6)
    ax.text(fpx - 7.6, fpy - 8.0 - 9.2, "16.0 mm clear (B.Cu)", color="#3fb950",
            fontsize=8.5, fontweight="bold", zorder=8, va="bottom",
            bbox=dict(facecolor="#0d1117", edgecolor="none", pad=1.4))

    ax.set_xlim(-2, 74)
    ax.set_ylim(82, -2)
    ax.set_title("hub v10 — 2.4 GHz site: measured state", color="#e6edf3",
                 fontsize=12.5, fontweight="bold", pad=10)
    ax.set_xticks([]); ax.set_yticks([])
    for s in ax.spines.values():
        s.set_color("#30363d")

    # ---------------- numbers panel ----------------
    tx.axis("off")
    tx.set_xlim(0, 1); tx.set_ylim(0, 1)

    def block(y, title, rows, title_col="#e6edf3"):
        tx.text(0.02, y, title, color=title_col, fontsize=10.5, fontweight="bold",
                transform=tx.transAxes, va="top")
        yy = y - 0.062
        for label, val, col in rows:
            tx.text(0.04, yy, label, color="#8b949e", fontsize=9, transform=tx.transAxes, va="top")
            tx.text(0.97, yy, val, color=col, fontsize=9, ha="right",
                    fontweight="bold", transform=tx.transAxes, va="top")
            yy -= 0.050
        return yy - 0.022

    y = 0.965
    y = block(y, "ROUTING", [
        ("nets routed", "0 / 9", "#ff7b72"),
        ("unconnected items", "98", "#ff7b72"),
        ("DRC violations", "80", "#d29922"),
        ("  of which pre-existing", "35", "#8b949e"),
        ("tracks on board", "659", "#e6edf3"),
    ])

    y = block(y, "PLACEMENT  (measured, not inferred)", [
        ("site centre", "(53.000, 68.100)", "#e6edf3"),
        ("side", "B.Cu  bottom", "#7ee787"),
        ("outline / pitch / rows", "16.0 / 2.00 / 14.30", "#e6edf3"),
        ("u6 courtyard clash", "none  (dy +1.5)", "#7ee787"),
        ("escape corridor", "16.0 mm clear", "#7ee787"),
    ])

    y = block(y, "HYPOTHESES TESTED THIS TURN", [
        ("1. router treats pours as solid", "ELIMINATED", "#7ee787"),
        ("   (router has no zone model)", "0 refs", "#8b949e"),
        ("2. pad-to-net association", "next", "#d29922"),
        ("3. stale --append model", "open", "#d29922"),
    ])

    tx.text(0.02, y - 0.005,
             "A routing failure is evidence about the ROUTER\n"
             "until a corridor measurement says the copper\n"
             "is too narrow. This session had it backwards.",
             color="#8b949e", fontsize=8.6, style="italic", transform=tx.transAxes, va="top")

    fig.savefig(OUT, dpi=170, facecolor=fig.get_facecolor(), bbox_inches="tight")
    print("wrote", OUT)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
