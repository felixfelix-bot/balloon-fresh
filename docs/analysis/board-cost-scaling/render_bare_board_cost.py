#!/usr/bin/env python3
"""render_bare_board_cost.py -- boards on the X axis, price on the Y axis, for BARE orders.

Follows the shape of docs/analysis/bulk-route-20261107/render_cost_curves.py, which the operator
asked for previously: per-board AND total on separate panels, because they answer different
questions and reading only one of them is how a cheap-per-board decision becomes an expensive order.

Panels:
  A  PER-BOARD cost vs quantity, per board type. Shows the convex rise to ~30 then the flat line.
     This is the panel that answers the operator's actual question ("is 25 similar to 10?") -- and
     the answer is visible without reading a number.
  B  TOTAL order spend vs quantity. Always rises. The panel that stops "per-board is cheap" from
     becoming "so buy 100".
  C  MARGINAL cost of the next board. The derivative of B; it shows the marginal board is cheapest
     at SMALL quantities, which is the reverse of the usual setup-amortisation intuition.

Every number comes from model_bare_board_cost.py. Nothing is invented here.

Run: python3 docs/analysis/board-cost-scaling/render_bare_board_cost.py
"""
import os
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from model_bare_board_cost import (  # noqa: E402
    BOARDS, ENIG_SURCHARGE, FOUR_LAYER_MULTIPLIER, SS24_PER_BOARD, SS24_UNIT,
    tier_price,
)

OUT = os.path.join(HERE, "assets")
os.makedirs(OUT, exist_ok=True)

QTYS = list(range(5, 121))
# One colour per board so the series are distinguishable in print and on a phone screen.
COLOURS = ["#1f77b4", "#d62728", "#2ca02c", "#9467bd"]


def per_board(name, layers, thick, q):
    mult = FOUR_LAYER_MULTIPLIER if layers == 4 else 1.0
    enig = ENIG_SURCHARGE if thick <= 0.4 else 0.0
    ss = SS24_UNIT * SS24_PER_BOARD if "solar" in name else 0.0
    return (tier_price(q) * mult + enig) / q + ss


def total(name, layers, thick, q):
    return per_board(name, layers, thick, q) * q


def main() -> int:
    fig, axes = plt.subplots(1, 3, figsize=(16.5, 5.0))

    # ---- A: per-board ----------------------------------------------------------------
    ax = axes[0]
    for (name, w, h, layers, thick, _note), col in zip(BOARDS, COLOURS):
        ax.plot(QTYS, [per_board(name, layers, thick, q) for q in QTYS],
                color=col, lw=2, label=f"{name} ({layers}L {thick}mm)")
    ax.axvline(10, color="grey", ls=":", lw=1)
    ax.axvline(25, color="grey", ls="--", lw=1)
    ax.annotate("qty 10", (10, ax.get_ylim()[1] * 0.9), fontsize=8, rotation=90,
                va="top", ha="right", color="grey")
    ax.annotate("qty 25", (25, ax.get_ylim()[1] * 0.9), fontsize=8, rotation=90,
                va="top", ha="right", color="grey")
    ax.set_title("A — per-board cost RISES to ~qty 30, then flat")
    ax.set_xlabel("boards ordered")
    ax.set_ylabel("USD per board")
    ax.grid(alpha=0.3)
    ax.legend(fontsize=7)

    # ---- B: total --------------------------------------------------------------------
    ax = axes[1]
    for (name, w, h, layers, thick, _note), col in zip(BOARDS, COLOURS):
        ax.plot(QTYS, [total(name, layers, thick, q) for q in QTYS], color=col, lw=2)
    ax.set_title("B — total spend always rises")
    ax.set_xlabel("boards ordered")
    ax.set_ylabel("USD total order")
    ax.grid(alpha=0.3)

    # ---- C: marginal, solar board only (the one being ordered) ------------------------
    ax = axes[2]
    name, _w, _h, layers, thick, _n = BOARDS[0]
    marg, xs = [], []
    for q in range(6, 121):
        marg.append(total(name, layers, thick, q) - total(name, layers, thick, q - 1))
        xs.append(q)
    ax.plot(xs, marg, color=COLOURS[0], lw=2)
    ax.set_title("C — solar connector: cost of the NEXT board")
    ax.set_xlabel("boards ordered")
    ax.set_ylabel("USD for one more board")
    ax.grid(alpha=0.3)
    ax.annotate("cheapest marginal board is at SMALL qty —\nnot after a setup amortises",
                xy=(8, marg[2]), xytext=(40, max(marg) * 0.55),
                fontsize=8, arrowprops=dict(arrowstyle="->", color="black", lw=0.8))

    fig.suptitle(
        "JLCPCB bare-board cost vs order quantity — measured tier table, not an assumption",
        fontsize=12, y=1.00)
    fig.tight_layout()
    p = os.path.join(OUT, "bare-board-cost-scaling.png")
    fig.savefig(p, dpi=150, bbox_inches="tight")
    print(f"wrote {p}")

    # a table the doc can quote, so the numbers in prose and the plot cannot drift
    print()
    print("solar connector, qty -> total / per board")
    for q in (5, 10, 25, 30, 50, 100):
        t = total(name, layers, thick, q)
        print(f"  {q:3d}  ${t:7.2f}  ${t / q:5.2f}/board")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
