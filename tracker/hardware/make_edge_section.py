#!/usr/bin/env python3
"""Edge-launch / wing-socket drawing for the JLCPCB query -- v3: the COMMITTED geometry, measured.

WHAT THIS SHEET IS. It depicts the hub-side wing interface as DECIDED by ADR-048 -- a routed slot
0.9 mm wide x 6.0 mm deep in the hub edge, the 0.6 mm tab seated 6.0 mm into it, the four lands on the
slot's faces, and the solder fillet loaded in SHEAR on both faces -- and it says, on the sheet, that the
BOARD AS BUILT still implements Option B (no slot, `J_W*` lands on F.Cu only, fillet in peel;
ADR-046 s4.2.1, measured by tracker/hardware/introspect_edge_interface.py).

WHY THAT DISTINCTION IS THE WHOLE POINT. v1 and v2 of this generator drew two boards end-to-end with a
solder bridge. That was ACCURATE TO THE BOARD and a vision review flagged it as looking wrong; the
resolution was not "fix the drawing" but two ADR records (ADR-046 s4.2.2 and ADR-048) that decide the
direction toward the slot. So the sheet now draws the COMMITTED geometry, and it says so, because a
drawing of a decided-but-unbuilt interface that does not say so would be read as a claim about the
board. ADR-046 s4.2.2's own wording is used: "Option A is the committed geometry".

WHAT v2 GOT WRONG (each found by reviewing the render, not by reading the code):
  1. it never drew the slot it named -- no 0.9 mm dimension, no slot, no seated tab (COMPLETENESS)
  2. two boards end-to-end with a solder bridge: Option B depicted while calling the geometry Option A
  3. ENIG on the pad faces does not establish a finish on copper newly exposed by ROUTING. A routed slot
     exposes copper on a CUT face. This sheet depicts that distinction and asks the fabricator; it does
     NOT answer it (requirement row "Surface finish -- routed faces" and QUESTION Q1).
  4. inward-pointing dimension arrows, whose heads read as motion arrows. Heads are drawn with their APEX
     ON the extension line (base inside the span); where the span is too narrow for two heads they move
     OUTSIDE and still point inward. No `<marker>` elements anywhere: force/dimension heads are explicit
     polygons, because `orient="auto"` with a custom refX/refY rotates about a point offset from the shaft
     centre and rendered a sideways head on the sibling peel-coupon drawing.
  5. View B's 4.0 mm dimension drawn as a plain underline. That 4.0 mm is the land's extent along the
     INSERTION AXIS, so it is now dimensioned in View A -- the view whose axis it lies on -- with
     extension lines and opposed heads. View B dimensions what lies on ITS axes (pitch, land width, tab
     width, slot width, tab thickness) and says in its legend which dimension is normal to the view.
  6. a misspelled finish abbreviation ("HASBL"). The requirement table is generated from one list and
     spells out HASL; a typo is visible in one place.
  7. text collisions and regions with no separation. Every string is measured before it is written: see
     the layout guard below. This is the sibling drawing's hard-won lesson -- measure, do not eyeball.

DEFECTS THE FIRST CLEAN RENDER STILL CARRIED, and what changed (review cycle r1, gpt-6-astra, 10 defects):
  * the red interface-edge line crossed its own label; the "tab outside 2.0 mm" extension line crossed its
    label's right end; View B's callout 7 sat on the lower land/fillet. Labels moved, leaders shortened.
  * View B's two right-hand dimensions read as reversed, because both extension-line pairs started at the
    same x. The tab-thickness dimension now sits on the OPPOSITE side from the slot-width one.
  * legend note 10 claimed the tab was "1.2 mm clear of the slot's side walls" -- a clearance no record
    fixes and no line drew. The claim is gone; the slot's extent ALONG the hub edge is now marked as not
    fixed by any cited record.
  * the routed slot's inner end was drawn square. A routed end carries a CUTTER RADIUS, so the end is now
    drawn as a semicircular arc and both the end radius and the tab-tip relief are ASKED (QUESTION Q7).
  * the sheet asserted broad copper lands on the slot's faces without specifying a construction that
    produces them under "no plating". That construction is now an explicit QUESTION (Q6), not a claim.
  * the tab's 0.6 mm is the SUBSTRATE thickness (ADR-046 s4.1), so the FINISHED tab is thicker and the
    finished solder gap differs from the 0.30 mm nominal. Stated, with the dependency named.

DEFECTS THE r4 REVIEW FOUND IN THE THREE-MECHANICAL SET, and what changed (review cycle r5):
  * View B drew the tab-face copper as a CONTINUOUS strip across the tab's full width. Fabricated literally
    that connects W1_SOLAR_P, GND, W1_RF and W1_SOLAR_N -- four nets shorted. The copper is now FOUR
    SEPARATE CONDUCTORS per face, one per land, with bare substrate drawn in the 0.6 mm gap between them.
  * View B's 0.6 mm dimension attached to the tab's outside copper surfaces, contradicting note 5 and the
    tab-stack-up row, which assign 0.6 mm to the FR4 substrate alone. The tab's copper is now drawn on the
    substrate's OUTER faces, so the extension lines attach to the substrate's own boundaries and the span
    excludes both copper layers; the label is now "FR4 substrate 0.6 mm".
  * View B callout 10 sat inside the hub material with nothing connecting it to the tab it names. It now
    carries a leader to the tab.
  Because the tab's copper is drawn OUTSIDE the substrate, the DRAWN fillet lane is the FINISHED gap, which
  is narrower than ADR-046 s4.1's 0.30 mm nominal (computed on bare substrate). Legends 4 and 8 say so.
  Two r4 defects are NOT drawing problems and are left as stated "UNVERIFIED -- under query": the slot-face
  copper CONSTRUCTION (asked of JLCPCB as Q6 / section 2A of the query message) and the mating-fit SPEC
  (finished tab thickness, slot tolerances, tip relief -- design decisions no record fixes).

HOW THE LAYOUT GUARD WORKS, AND WHY IT IS TRUSTWORTHY HERE. rsvg-convert lays text out through Pango, and
PIL's ImageFont.getlength() with /usr/share/fonts/truetype/dejavu/DejaVuSans.ttf reproduces rsvg's
rendered ink extent. MEASURED ON THIS HOST before relying on it (/tmp/verify_font_metric.py): for
font-family "DejaVu Sans" at sizes 11.5-20 the prediction is 2-6 units WIDER than the render, i.e. the
guard errs CONSERVATIVE -- it cannot miss a collision it would have caused, it can only over-report one.
That measurement is why the SVG sets font-family="DejaVu Sans" ALONE: a 'Helvetica' fallback in the family
list resolved to a different (narrower) face on this host, and a metric that does not match the renderer
would make every check a guess. The guard refuses to write a canvas whose text collides with other text,
sits on a solid drawn feature, or runs off the sheet, and the script exits non-zero instead.

DRAWING CONVENTIONS (deliberate, and reviewer-visible):
  * balloon callouts (numbered circles) with SHORT leaders, legends in their own band -- a long leader from
    a stacked label column necessarily crosses text, which the peel-coupon loop measured. Balloon DIGITS
    register as markers, not labels, so a deliberate callout on a feature is not reported as a collision;
    every other string is checked against the drawn blocks.
  * every text node goes through esc(); a literal '<' once made the SVG unparseable and the render printed
    nothing, so a stale PNG was reviewed as if it were new
  * a render that produces no file FAILS LOUDLY (non-zero exit carrying rsvg's stderr)
  * nothing is invented: the slot's lateral extent is SCHEMATIC because no record fixes it, the hub
    thickness is TODO(unverified), the slot tolerance is marked PROPOSED, and the routed-face finish, the
    slot-face copper construction and the slot end radius are QUESTIONS, not claims

Usage: make_edge_section.py [--out PATH] [--check]
"""
import argparse
import hashlib
import os
import shutil
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET

# ---------------------------------------------------------------------------------------------------
# CONSTANTS. Every number is either read from a record (cited) or marked as an assumption. The drawing
# must not contain a fabricator-facing number that no record or measurement owns.
# ---------------------------------------------------------------------------------------------------
W = 1700                      # sheet width, SVG user units (= px; the PNG is rendered at 2000 px wide)

SLOT_W_MM = 0.9               # [repo] ADR-046 s4.1 / ADR-048 s2.2: slot width
SLOT_TOL_MM = 0.10            # [repo] ADR-048 s2.2; the tolerance itself is TODO(unverified), ADR-046 s4.3
SLOT_DEPTH_MM = 6.0           # [repo] ADR-046 s4.1 / ADR-048 s2.2: slot depth = insertion depth
TAB_T_MM = 0.6                # [repo] ADR-046 s4.1: tab SUBSTRATE thickness
TAB_LEN_MM = 8.0              # [repo] ADR-046 s3.2: tab protrusion beyond the body
LAND_LEN_MM = 4.0             # [repo] ADR-048 s2.2: land along the insertion axis
LAND_WID_MM = 1.2             # [repo] ADR-048 s2.2: land across
LAND_PITCH_MM = 1.8           # [repo] ADR-048 s2.2: 1.8 mm pitch -> 0.6 mm between lands
LAND_EDGE_MM = 1.0            # [repo] ADR-048 D-1: the land row's near edge sits 1.0 mm inboard
TAB_WID_MM = 9.0              # [repo] ADR-046 s2.1/s4.1: 9.0 mm tab = 4 x 1.2 + 3 x 0.6 + 2 x 1.2
GAP_TOTAL_MM = SLOT_W_MM - TAB_T_MM      # 0.30 mm nominal, derived (ADR-046 s4.1)
GAP_PER_FACE_MM = GAP_TOTAL_MM / 2.0     # 0.15 mm nominal per face

# Drawn thickness of a copper layer in these sections. The real figure is 35 um (1 oz); 0.05 mm is
# thickened just enough to read. It is drawn on the OUTER face of the substrate -- OUTSIDE the 0.6 mm
# span -- so the substrate's own boundaries stay clean and the FR4 dimension excludes the copper
# (review r4 defect 1). Drawing the copper INSIDE the 0.6 mm span made the dimension bracket the copper.
CU_DRAWN_MM = 0.05

# View A scale: 60 units/mm. The finished fillet lane is 0.10 mm = 6 units -- thin, so the fillet is
# ANNOTATED (balloon 4) rather than dimensioned.
S_A = 60.0
A_XE = 330                    # the interface edge (the plane the outline lies in) in View A
A_YC = 470                    # the joint's centre line in View A
A_HUB_R = 800                 # right end of the drawn hub block (SCHEMATIC)
A_BLOCK = 70                  # drawn lateral extent of hub material either side of the slot (SCHEMATIC)

# View B scale: 44 units/mm, so the 9.0 mm tab is 396 units and the 0.9 mm slot is 39.6 units -- still
# wider than the 34-unit threshold below which dimension heads have to move outside the span.
S_B = 44.0
B_YC = 470
B_TAB_X0 = 1060               # left end of the drawn tab width in View B
B_BLOCK = 30                  # drawn hub material beyond the tab's ends (SCHEMATIC)
B_SLOT_MARGIN = 70            # drawn hub material above/below the slot walls (SCHEMATIC)

# Region layout. LEG_Y is the top of the two legend bands; the table starts below the taller one, and the
# sheet height is computed from the table's REAL height so a longer table can never clip.
PANEL_Y0, PANEL_Y1 = 172, 700
LEG_Y = PANEL_Y1 + 32
A_PANEL_X0, A_PANEL_X1 = 56, 880
B_PANEL_X0, B_PANEL_X1 = 900, 1644

RED = "#b00020"
INK = "#111"
GREY = "#555"
GREEN, GREEN_DK = "#2f6b3a", "#1d4425"
COPPER, COPPER_DK = "#c8751a", "#8a4d0c"
GOLD = "#e0a53a"
STEEL, STEEL_DK = "#dfe6ee", "#33475b"
CUT = "#8d8d8d"               # a routed (cut) face
VOID = "#ffffff"              # the routed slot's void


def esc(s):
    """Escape XML text. A literal '<' is a tag start and makes the whole SVG unparseable -- measured on the
    sibling drawing: rsvg-convert reported 'XML parse error ... invalid element name' and the script printed
    nothing, so a stale PNG was reviewed as if it were the new one."""
    return str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


# ---------------------------------------------------------------------------------------------------
# THE LAYOUT GUARD. Ported from tracker/hardware/svg_layout_guard.py (branch pr/peel-coupon, which took a
# sibling drawing to a CLEAN review after six cycles) and INLINED so this generator has no cross-branch
# dependency. Verified against this host's renderer before use -- see the module docstring.
# ---------------------------------------------------------------------------------------------------
FONT_REG = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
FONT_BOLD = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
_FONT_CACHE = {}


def _font(size, weight):
    from PIL import ImageFont
    key = (round(float(size), 2), str(weight))
    if key not in _FONT_CACHE:
        path = FONT_BOLD if str(weight) in ("bold", "700", "600") else FONT_REG
        _FONT_CACHE[key] = ImageFont.truetype(path, max(1, int(round(float(size)))))
    return _FONT_CACHE[key]


def text_ink_box(x, y, s, size, weight="normal", anchor="start"):
    """Ink box (x0, y0, x1, y1) of `s` with its baseline at (x, y), in SVG units."""
    f = _font(size, weight)
    adv = f.getlength(s)
    if anchor == "middle":
        x -= adv / 2.0
    elif anchor in ("end", "right"):
        x -= adv
    bx = f.getbbox(s)
    asc = f.getmetrics()[0]
    return (x + bx[0], y - asc + bx[1], x + bx[2], y - asc + bx[3])


def text_width(s, size, weight="normal"):
    return _font(size, weight).getlength(s)


def wrap(s, size, max_w, weight="normal"):
    """Greedy word wrap against the MEASURED width. Returns a list of lines."""
    words, lines, cur = str(s).split(), [], ""
    for w in words:
        trial = f"{cur} {w}".strip()
        if cur and text_width(trial, size, weight) > max_w:
            lines.append(cur)
            cur = w
        else:
            cur = trial
    if cur:
        lines.append(cur)
    return lines or [""]


def _inter(a, b):
    x0, y0 = max(a[0], b[0]), max(a[1], b[1])
    x1, y1 = min(a[2], b[2]), min(a[3], b[3])
    return 0.0 if (x1 <= x0 or y1 <= y0) else (x1 - x0) * (y1 - y0)


def _area(a):
    return max(0.0, a[2] - a[0]) * max(0.0, a[3] - a[1])


class OverlapError(Exception):
    pass


class Canvas:
    """An SVG canvas that refuses to emit text that collides with other text or with a solid feature.

    Registered `shape` boxes are tested against `label` text only: shape over shape is normal drawing, and
    a balloon DIGIT sitting on the feature it calls out is the callout convention, not a defect -- so
    balloons register as markers (`collide=False`) and every other string is a label.
    """

    CELL_FRAC = 0.10     # kept for reference; superseded by CELL_MIN (see check())
    CELL_MIN = 1.25      # overlap must cover >= 1.25 glyph cells of the SMALLER label
    CELL_AREA = 160.0    # u^2: ~2 cells of an 11 px font
    MARGIN_U = 1.6       # u of outset per glyph cell

    def __init__(self, w, h, font="DejaVu Sans"):
        self.w, self.h = w, h
        # DejaVu Sans ALONE: measured on this host, a 'Helvetica' fallback resolves to a narrower face, and
        # the guard's metric must match what Pango actually renders.
        self.parts = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" '
                      f'viewBox="0 0 {w} {h}" font-family="{font}">',
                      f'<rect width="{w}" height="{h}" fill="#ffffff"/>']
        self.text_boxes = []
        self.shape_boxes = []

    # ---- primitives ------------------------------------------------------------------------------
    def rect(self, x, y, w, h, tag="rect", collide=True, **kw):
        self.parts.append(f'<rect x="{x:g}" y="{y:g}" width="{w:g}" height="{h:g}" {_fmt(kw)}/>')
        if collide:
            self.shape_boxes.append(((x, y, x + w, y + h), tag))

    def raw(self, s):
        self.parts.append(s)

    def line(self, x1, y1, x2, y2, tag="line", **kw):
        self.parts.append(f'<line x1="{x1:g}" y1="{y1:g}" x2="{x2:g}" y2="{y2:g}" {_fmt(kw)}/>')

    def path(self, d, tag="path", collide_box=None, **kw):
        self.parts.append(f'<path d="{d}" {_fmt(kw)}/>')
        if collide_box is not None:
            self.shape_boxes.append((collide_box, tag))

    def text(self, x, y, s, size=13.5, weight="normal", anchor="start", fill=INK, tag="text",
             collide=True):
        box = text_ink_box(x, y, s, size, weight, anchor)
        self.parts.append(f'<text x="{x:g}" y="{y:g}" font-size="{size:g}" font-weight="{weight}" '
                          f'fill="{fill}" text-anchor="{anchor}">{esc(s)}</text>')
        if collide:
            self.text_boxes.append((box, tag, str(s)))
        return box

    # ---- validation ------------------------------------------------------------------------------
    def check(self):
        bad = []
        for i in range(len(self.text_boxes)):
            ai, ti, si = self.text_boxes[i]
            for j in range(i + 1, len(self.text_boxes)):
                bj, tj, sj = self.text_boxes[j]
                if _inter(ai, bj) <= 0:
                    continue
                # Glyph-cell measure, taken against the SMALLER label's own cell size. Two labels on
                # adjacent baselines share ink-box area in the ascender/descender gap where no glyphs
                # live, and calling that a collision would make the guard useless on a dense sheet. The
                # earlier rule ("overlap >= 10% of the smaller label's AREA") let a long heading run 12 u
                # into its neighbouring column, because 10% of a long label is a lot of units. Measuring
                # in cells of the smaller label fixes that and is the review-cycle r3 lesson.
                m = self.MARGIN_U
                x0, x1 = max(ai[0], bj[0] - m), min(ai[2], bj[2] + m)
                y0, y1 = max(ai[1], bj[1] - m), min(ai[3], bj[3] + m)
                if x1 <= x0 or y1 <= y0:
                    continue
                bs, ss = (ai, si) if _area(ai) <= _area(bj) else (bj, sj)
                cw = max(1e-6, (bs[2] - bs[0]) / max(1, len(ss)))
                ch = max(1e-6, bs[3] - bs[1])
                cells = ((x1 - x0) / cw) * ((y1 - y0) / ch)
                if (x1 - x0) * (y1 - y0) >= self.CELL_AREA and cells >= self.CELL_MIN:
                    bad.append(f"text/text overlap [{ti}] {si[:44]!r} x [{tj}] {sj[:44]!r} "
                               f"({cells:.1f} cells of the smaller label)")
        for ai, ti, si in self.text_boxes:
            for bj, tj in self.shape_boxes:
                ov = _inter(ai, bj)
                if ov <= 0:
                    continue
                # Same cell measure as text-vs-text: a long label overlapping a shape by a sliver must
                # still be caught, which a "% of the label's area" rule cannot do.
                x0, x1 = max(ai[0], bj[0]), min(ai[2], bj[2])
                y0, y1 = max(ai[1], bj[1]), min(ai[3], bj[3])
                cw = max(1e-6, (ai[2] - ai[0]) / max(1, len(si)))
                ch = max(1e-6, ai[3] - ai[1])
                if ov >= self.CELL_AREA and ((x1 - x0) / cw) * ((y1 - y0) / ch) >= self.CELL_MIN:
                    bad.append(f"text on shape [{ti}] {si[:44]!r} over [{tj}] ({ov:.0f} u^2)")
        for ai, ti, si in self.text_boxes:
            if ai[0] < -0.5 or ai[1] < -0.5 or ai[2] > self.w + 0.5 or ai[3] > self.h + 0.5:
                bad.append(f"clipped [{ti}] {si[:44]!r} box={tuple(round(v, 1) for v in ai)} "
                           f"outside 0,0,{self.w},{self.h}")
        return bad


def _fmt(kw):
    """SVG attributes from python kwargs; underscores become hyphens, floats are formatted."""
    out = []
    for k, v in kw.items():
        if isinstance(v, float):
            v = f"{v:g}"
        out.append(f'{k.replace("_", "-")}="{v}"')
    return " ".join(out)


def audit_svg(path):
    """Re-derive the text boxes from the WRITTEN svg and report collisions. Independent of the canvas
    object, so it also proves the escape/serialise step did not move anything."""
    root = ET.parse(path).getroot()
    ns = "{http://www.w3.org/2000/svg}"
    c = Canvas(int(float(root.get("width"))), int(float(root.get("height"))))
    for el in root.iter(f"{ns}text"):
        s = "".join(el.itertext())
        if not s.strip():
            continue
        c.text(float(el.get("x", 0)), float(el.get("y", 0)), s,
               size=float(el.get("font-size", 14)), weight=el.get("font-weight", "normal"),
               anchor=el.get("text-anchor", "start"), tag="text", collide=True)
    return c.check()


# ---------------------------------------------------------------------------------------------------
# DRAWING HELPERS
# ---------------------------------------------------------------------------------------------------
def dim_h(c, x1, x2, y, label, feat_y=None, above=True, color=INK, size=13, label_dx=0.0):
    """Horizontal dimension: extension lines, opposed heads with APEX ON the extension lines.

    `feat_y` draws extension lines from the measured feature (feat_y) to just past the dimension line.
    Where the span is narrower than 34 units there is no room for two heads inside it, so they move
    OUTSIDE and still point inward -- the standard narrow-span case, not a reversed arrow. `label_dx`
    slides the text off the span's midpoint when another dimension's extension line passes through it.
    """
    lo, hi = (x1, x2) if x1 <= x2 else (x2, x1)
    if feat_y is not None:
        c.line(lo, min(feat_y, y) - 4, lo, max(feat_y, y) + 6, stroke=color, stroke_width="1")
        c.line(hi, min(feat_y, y) - 4, hi, max(feat_y, y) + 6, stroke=color, stroke_width="1")
    narrow = (hi - lo) < 34
    x_lo, x_hi = (lo - 16, hi + 16) if narrow else (lo, hi)
    c.line(x_lo, y, x_hi, y, stroke=color, stroke_width="1.3")
    if narrow:
        c.path(f"M{lo:g},{y:g} L{lo-14:g},{y-5:g} L{lo-14:g},{y+5:g} z", fill=color)
        c.path(f"M{hi:g},{y:g} L{hi+14:g},{y-5:g} L{hi+14:g},{y+5:g} z", fill=color)
    else:
        c.path(f"M{lo:g},{y:g} L{lo+13:g},{y-5:g} L{lo+13:g},{y+5:g} z", fill=color)
        c.path(f"M{hi:g},{y:g} L{hi-13:g},{y-5:g} L{hi-13:g},{y+5:g} z", fill=color)
    ly = y - 9 if above else y + 20
    c.text((lo + hi) / 2 + label_dx, ly, label, size=size, anchor="middle", fill=color, tag="dim_h")


def dim_v(c, y1, y2, x, label, feat_x=None, color=INK, size=13, side="left"):
    """Vertical dimension. Same convention as dim_h: apex on the extension line, base inside the span."""
    lo, hi = (y1, y2) if y1 <= y2 else (y2, y1)
    if feat_x is not None:
        c.line(min(feat_x, x) - 4, lo, max(feat_x, x) + 6, lo, stroke=color, stroke_width="1")
        c.line(min(feat_x, x) - 4, hi, max(feat_x, x) + 6, hi, stroke=color, stroke_width="1")
    narrow = (hi - lo) < 34
    y_lo, y_hi = (lo - 16, hi + 16) if narrow else (lo, hi)
    c.line(x, y_lo, x, y_hi, stroke=color, stroke_width="1.3")
    if narrow:
        c.path(f"M{x:g},{lo:g} L{x-5:g},{lo-14:g} L{x+5:g},{lo-14:g} z", fill=color)
        c.path(f"M{x:g},{hi:g} L{x-5:g},{hi+14:g} L{x+5:g},{hi+14:g} z", fill=color)
    else:
        c.path(f"M{x:g},{lo:g} L{x-5:g},{lo+13:g} L{x+5:g},{lo+13:g} z", fill=color)
        c.path(f"M{x:g},{hi:g} L{x-5:g},{hi-13:g} L{x+5:g},{hi-13:g} z", fill=color)
    ly = (lo + hi) / 2 + 4
    if not label:                     # an empty label is legal: the caller may place the text itself
        return
    if side == "left":
        c.text(x - 9, ly, label, size=size, anchor="end", fill=color, tag="dim_v")
    else:
        c.text(x + 9, ly, label, size=size, anchor="start", fill=color, tag="dim_v")


def load_arrow(c, x_tail, x_tip, y, color=RED, width=3.5, head=18, headw=5.5):
    """A force arrow whose head is an EXPLICIT POLYGON: the apex is the load direction.

    No <marker>: on the sibling drawing an `orient="auto"` marker with a custom refX/refY rotated the head
    about a point offset from the shaft centre and rendered it sideways, and a marker cannot point a head
    back along its own path. Coordinates cannot make that mistake.
    """
    s = 1 if x_tip > x_tail else -1
    base = x_tip - s * head
    c.line(x_tail, y, base + s, y, stroke=color, stroke_width=width)
    c.path(f"M{x_tip:g},{y:g} L{base:g},{y-headw:g} L{base:g},{y+headw:g} z", fill=color)


def balloon(c, x, y, n, r=11, color=INK):
    """A numbered callout on or beside the feature it names. The digit is a MARKER (collide=False): a
    deliberate callout on a feature is the convention, not a text-on-shape collision."""
    c.raw(f'<circle cx="{x:g}" cy="{y:g}" r="{r:g}" fill="#ffffff" stroke="{color}" '
          f'stroke-width="1.3"/>')
    c.text(x, y + 4.5, str(n), size=13, weight="bold", anchor="middle", tag="balloon", collide=False)


def stub(c, x1, y1, x2, y2, color=INK):
    c.line(x1, y1, x2, y2, stroke=color, stroke_width="1.1")


def panel(c, x, y, w, h, fill="#f7f9f7", stroke="#cfd8cf"):
    """A region background. Emitted as RAW markup: a tint behind a label is not a collision."""
    c.raw(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" fill="{fill}" stroke="{stroke}"/>')


def legend(c, x, y, heading, entries, wrap_w):
    """A legend in its own band: heading, then numbered entries with the number in the left gutter."""
    c.text(x, y, heading, size=14, weight="bold")
    y += 26
    for n, txt in entries:
        lines = wrap(txt, 13, wrap_w)
        c.text(x + 20, y, str(n), size=13, weight="bold")
        for k, ln in enumerate(lines):
            c.text(x + 46, y + k * 17, ln, size=13, fill="#333")
        y += len(lines) * 17 + 7
    return y


def legend_height(entries, wrap_w):
    h = 26
    for _, txt in entries:
        h += len(wrap(txt, 13, wrap_w)) * 17 + 7
    return h


# ---------------------------------------------------------------------------------------------------
# VIEW A -- section ALONG the insertion axis, through the joint
# ---------------------------------------------------------------------------------------------------
A_LEGEND = [
    (1, "hub material — the board either side of, and beyond, the slot. Its LATERAL extent is SCHEMATIC: "
        "no record we hold fixes it, and the hub's own thickness is TODO(unverified) (ADR-048 §5). See the "
        "sheet-scope row"),
    (2, "the ROUTED FACE of the slot — a CUT face. The pad-face ENIG (F.Cu / B.Cu at the hub's outer "
        "faces) does not establish a finish on copper newly exposed by routing. Asked as Q1; NOT answered "
        "on this sheet"),
    (3, "the lands on the slot's faces — 4 per face, 4.0 mm along the insertion axis, 1.2 mm across at "
        "1.8 mm pitch (ADR-048 §2.2). Copper is drawn a little thicker than scale (it is 35 µm, 1 oz, on a "
        "0.6 mm board) so the section reads. NO construction that produces broad copper on an internal "
        "routed face is established by any record we hold — the lands are drawn UNVERIFIED; asked as Q6"),
    (4, "the solder fillets — the gap between a slot face and the tab's copper on that face. ADR-046 §4.1's "
        "0.30 mm total (slot 0.9 − tab 0.6) is NOMINAL, computed on BARE substrate; the tab's copper on "
        "each face narrows the FINISHED gap, and the finished gap is what is DRAWN here. Loaded in SHEAR "
        "on both faces, which is why Option A's capacity is the joint's anchor (ADR-046 §4.2.2)"),
    (5, "the wing tab — 0.6 mm FR4 SUBSTRATE (ADR-046 §4.1), 8.0 mm long, seated 6.0 mm into the slot so "
        "2.0 mm stays outside. Its tip is relieved to match the slot's routed end, so it seats to the full "
        "6.0 mm — but that relief and the slot's end radius are NOT fixed by any record we hold, and the "
        "semicircle drawn here is an ILLUSTRATION, not a specification: the full 6.0 mm seating is a "
        "REQUIREMENT, not a verified fit. Asked as Q7. The tab carries COPPER on each face (35 µm, 1 oz), "
        "drawn on the substrate's OUTER faces here; the tab's FINISH is not fixed by a record we hold (Q1). "
        "The FINISHED tab is thicker than 0.6 mm — see the tab-stack-up row"),
    (6, "the slot's mouth reaches the outline ON THE SLOT'S CENTRE LINE (ADR-048 §2.5: \"the land IS the "
        "interface\"). The land copper runs 1.0 … 5.0 mm inboard of that edge (ADR-048 D-1). The slot's "
        "inner end is ROUNDED — a cutter radius, not a square end; see Q7"),
]


def view_a(c):
    xe, yc = A_XE, A_YC
    sw, tw = SLOT_W_MM * S_A, TAB_T_MM * S_A          # 54.0, 36.0
    wall_u, wall_l = yc - sw / 2, yc + sw / 2         # 443.0, 497.0
    face_u, face_l = yc - tw / 2, yc + tw / 2         # 452.0, 488.0
    depth = SLOT_DEPTH_MM * S_A                       # 360
    sx_end = xe + depth                               # 690 -- the slot's deepest point
    r = sw / 2.0                                      # 27.0 -- the drawn cutter radius at the slot's end
    tx0 = xe - (TAB_LEN_MM - SLOT_DEPTH_MM) * S_A     # 210 -- the tab's outer end (2.0 mm proud)
    lx0, lx1 = xe + LAND_EDGE_MM * S_A, xe + (LAND_EDGE_MM + LAND_LEN_MM) * S_A   # 390, 630
    cu = CU_DRAWN_MM * S_A                            # 3.0 -- drawn copper thickness (see CU_DRAWN_MM)
    hub_top, hub_bot = wall_u - A_BLOCK, wall_l + A_BLOCK

    c.text(A_PANEL_X0 + 16, 200, "VIEW A — section ALONG the insertion axis, through the joint",
           size=18, weight="bold")
    c.text(A_PANEL_X0 + 16, 222, "the hub edge is on the right; the wing tab enters from the left and is "
                                 "seated 6.0 mm in · lateral extents SCHEMATIC", size=13.5, fill=GREY)

    # the hub, then the ROUTED SLOT as a void cut into it. The void is drawn as a path with a SEMICIRCULAR
    # inner end, because a routed slot's end carries the cutter's radius -- a square end would be a claim
    # no process makes. Its grey stroke IS the cut face (requirement row "Surface finish -- routed faces").
    c.rect(xe, hub_top, A_HUB_R - xe, hub_bot - hub_top, tag="hub material", fill=GREEN,
           stroke=GREEN_DK, stroke_width="1.5")
    for ly in (hub_top + A_BLOCK * 0.5, wall_l + A_BLOCK * 0.5):
        c.line(xe, ly, A_HUB_R, ly, stroke=GREEN_DK, stroke_width="0.8", opacity="0.5")
    void = (f"M{xe:g},{wall_u:g} L{sx_end-r:g},{wall_u:g} A{r:g},{r:g} 0 0 1 {sx_end-r:g},{wall_l:g} "
            f"L{xe:g},{wall_l:g} Z")
    c.path(void, tag="slot void", fill=VOID, stroke=CUT, stroke_width="5",
           collide_box=(xe, wall_u - 3, sx_end, wall_l + 3))

    # the wing tab. Its TIP is drawn with the SAME radius as the slot's routed end (a matched pair), so
    # the tab seats to the full 6.0 mm depth at the centreline and "seated 6.0 mm = slot depth 6.0 mm"
    # is true of the drawn geometry. The radius itself is ASKED (Q7), not specified here.
    # The tab's tip arc shares the SLOT END ARC's centre (sx_end-r, yc) and radius r, so the two coincide
    # exactly and the tab's apex reaches the slot's deepest point -- which is what makes "seated 6.0 mm =
    # slot depth 6.0 mm" true of the drawn geometry. (A semicircle of radius tw/2 would fall short by
    # (r - sqrt(r^2 - (tw/2)^2)); using the shared arc removes that gap.)
    tip_x = sx_end - (r - (r * r - (tw / 2.0) ** 2) ** 0.5)      # 683.12 -- where the tip arc starts
    tab = (f"M{tx0:g},{face_u:g} L{tip_x:.3f},{face_u:g} A{r:g},{r:g} 0 0 1 {tip_x:.3f},{face_l:g} "
           f"L{tx0:g},{face_l:g} Z")
    c.path(tab, tag="tab", fill=STEEL, stroke=STEEL_DK, stroke_width="1.6",
           collide_box=(tx0, face_u, sx_end, face_l))
    # the tab's own copper, one layer per face (35 um, 1 oz), drawn on the substrate's OUTER face --
    # OUTSIDE the 0.6 mm span -- so the substrate boundaries stay clean (review r4 defect 1)
    c.rect(tx0, face_u - cu, (sx_end - r) - tx0, cu, tag="tab copper upper", fill=COPPER,
           stroke=COPPER_DK, stroke_width="0.6", opacity="0.5")
    c.rect(tx0, face_l, (sx_end - r) - tx0, cu, tag="tab copper lower", fill=COPPER,
           stroke=COPPER_DK, stroke_width="0.6", opacity="0.5")

    # lands: on the slot's faces (hub side -- part of the hub's own stack-up) and on the tab's two faces
    # (a patch of the tab's own copper, drawn over it)
    c.rect(lx0, wall_u - cu, lx1 - lx0, cu, tag="hub land upper", fill=COPPER, stroke=COPPER_DK,
           stroke_width="1")
    c.rect(lx0, wall_l, lx1 - lx0, cu, tag="hub land lower", fill=COPPER, stroke=COPPER_DK,
           stroke_width="1")
    c.rect(lx0, face_u - cu, lx1 - lx0, cu, tag="tab land upper", fill=COPPER, stroke=COPPER_DK,
           stroke_width="1")
    c.rect(lx0, face_l, lx1 - lx0, cu, tag="tab land lower", fill=COPPER, stroke=COPPER_DK,
           stroke_width="1")
    # the fillets fill the lane between a slot face and the tab's copper on that face
    c.rect(lx0, wall_u, lx1 - lx0, (face_u - cu) - wall_u, tag="fillet shear face 1", fill=GOLD,
           stroke=COPPER_DK, stroke_width="0.7")
    c.rect(lx0, face_l + cu, lx1 - lx0, wall_l - (face_l + cu), tag="fillet shear face 2", fill=GOLD,
           stroke=COPPER_DK, stroke_width="0.7")

    # the interface edge: the plane the board outline lies in
    c.line(xe, hub_top - 40, xe, hub_bot + 40, stroke=RED, stroke_width="3", stroke_dasharray="10,5")
    c.text(xe - 44, hub_top - 68, "interface edge (routed)", size=13, anchor="end", fill=RED)

    # THE PULL: along the insertion axis, one arrow per fillet face, so both fillets load in shear.
    load_arrow(c, xe - 10, tx0 + 10, (wall_u + face_u) / 2)
    load_arrow(c, xe - 10, tx0 + 10, (face_l + wall_l) / 2)
    c.text(A_PANEL_X0 + 34, 250, "F — pull along the insertion axis, out of the slot:",
           size=13.5, weight="bold", fill=RED)
    c.text(A_PANEL_X0 + 34, 270, "BOTH fillets loaded in SHEAR, one per face", size=13.5,
           weight="bold", fill=RED)

    # dimensions. The slot's own 0.9 mm, drawn at last: extension lines reach back to the interface edge
    # and the label sits LEFT of the tab's outer end so it cannot land on the tab.
    dim_v(c, wall_u, wall_l, 200, f"slot {SLOT_W_MM:.1f} mm (±{SLOT_TOL_MM:.2f})", feat_x=xe,
          side="left")
    dim_h(c, lx0, lx1, hub_top - 14, f"land {LAND_LEN_MM:.1f} mm along the insertion axis",
          feat_y=wall_u - cu)
    # the tab-outside label is slid left of its span's midpoint: the seated-depth dimension's extension
    # line rises through x = A_XE, and a centred label would have its right end on that line.
    dim_h(c, tx0, xe, hub_bot + 46, "tab outside 2.0 mm", feat_y=hub_bot, above=False, label_dx=-46)
    dim_h(c, xe, sx_end, hub_bot + 96,
          f"seated {SLOT_DEPTH_MM:.1f} mm = slot depth {SLOT_DEPTH_MM:.1f} mm",
          feat_y=hub_bot, above=False)

    # balloons. Short leaders only, and every one lands on or beside its feature.
    balloon(c, 760, hub_top + 17, 1)
    stub(c, 751, 396, 704, 429)
    balloon(c, 345, wall_u - 42, 2)
    stub(c, 345, wall_u - 31, 345, wall_u - 12)
    balloon(c, 425, wall_u - 42, 3)
    stub(c, 425, wall_u - 31, 425, wall_u - 10)
    balloon(c, 300, 352, 6)
    stub(c, 310, 358, xe - 6, wall_u - 10)
    balloon(c, 520, face_u + tw / 2, 5)
    balloon(c, 620, wall_u + (face_u - wall_u) / 2, 4)


# ---------------------------------------------------------------------------------------------------
# VIEW B -- section ACROSS the tab, normal to the insertion axis
# ---------------------------------------------------------------------------------------------------
B_LEGEND = [
    (7, "the four lands, seen END-ON: 1.2 mm across at 1.8 mm pitch, 0.6 mm clear between lands. Their "
        "4.0 mm extent runs NORMAL to this view — dimensioned in View A. Each is a SEPARATE conductor: the "
        "tab-face copper is broken at every 0.6 mm gap, so W1_SOLAR_P, GND, W1_RF and W1_SOLAR_N are NOT "
        "connected to one another on either face"),
    (8, "one fillet per land per face, wetting that land's 4.0 mm. The 4.0 mm runs along the insertion "
        "axis, i.e. NORMAL to this view. The lane DRAWN is the FINISHED gap: slot 0.9 − (0.6 mm substrate "
        "+ a copper layer on each face). ADR-046 §4.1's 0.15 mm per face is NOMINAL on bare substrate and "
        "is wider — see the tab-stack-up row"),
    (9, "the hub material either side of the slot. Its extent is SCHEMATIC — no record we hold fixes how "
        "far the slot runs along the hub edge, only its 0.9 mm width and 6.0 mm depth"),
    (10, "the 9.0 mm tab: 4 × 1.2 mm lands + 3 × 0.6 mm gaps + 2 × 1.2 mm of tab beyond the outer lands "
         "(ADR-048 §2.2). That 1.2 mm is the TAB's own margin, NOT a tab-to-slot-wall clearance — no "
         "record fixes that clearance, so none is drawn or claimed here"),
]

B_LABELS = ["W1_SOLAR_P", "GND", "W1_RF", "W1_SOLAR_N"]


def view_b(c):
    yc = B_YC
    sw, tw = SLOT_W_MM * S_B, TAB_T_MM * S_B            # 39.6, 26.4
    wall_u, wall_l = yc - sw / 2, yc + sw / 2           # 450.2, 489.8
    face_u, face_l = yc - tw / 2, yc + tw / 2           # 456.8, 483.2
    tabw = TAB_WID_MM * S_B                             # 396
    tx0, tx1 = B_TAB_X0, B_TAB_X0 + tabw
    lx_l, lx_r = tx0 - B_BLOCK, tx1 + B_BLOCK
    wall_top, wall_bot = wall_u - B_SLOT_MARGIN, wall_l + B_SLOT_MARGIN
    cu = CU_DRAWN_MM * S_B                              # 2.2 -- drawn copper thickness (see CU_DRAWN_MM)

    c.text(B_PANEL_X0 + 16, 200, "VIEW B — section ACROSS the tab, normal to the insertion axis",
           size=18, weight="bold")
    c.text(B_PANEL_X0 + 16, 222, "through the land row: the four lands at 1.8 mm pitch and the two "
                                 "shear-loaded fillets · SCHEMATIC laterally", size=13.5, fill=GREY)

    # hub material above and below the slot, spanning past the tab's ends
    c.rect(lx_l, wall_top, lx_r - lx_l, B_SLOT_MARGIN, tag="wall upper", fill=GREEN, stroke=GREEN_DK,
           stroke_width="1.5")
    c.rect(lx_l, wall_l, lx_r - lx_l, B_SLOT_MARGIN, tag="wall lower", fill=GREEN, stroke=GREEN_DK,
           stroke_width="1.5")
    # the cut faces of the slot
    c.rect(lx_l, wall_u, lx_r - lx_l, 6, tag="cut face upper", fill=CUT, stroke="none")
    c.rect(lx_l, wall_l - 6, lx_r - lx_l, 6, tag="cut face lower", fill=CUT, stroke="none")
    # the tab, end-on. Its own copper is drawn per land, below, as FOUR SEPARATE CONDUCTORS on each face:
    # there is NO continuous strip across the tab. A single strip would connect W1_SOLAR_P, GND, W1_RF and
    # W1_SOLAR_N -- i.e. depict four nets shorted (review r4 defect 3).
    c.rect(tx0, face_u, tabw, tw, tag="tab end-on", fill=STEEL, stroke=STEEL_DK, stroke_width="1.6")

    # the four lands in one row across the tab: 1.2 mm land, 0.6 mm gap, 1.2 mm tab margin at each end
    land_w = LAND_WID_MM * S_B                          # 52.8
    gap_w = (LAND_PITCH_MM - LAND_WID_MM) * S_B         # 26.4
    x = tx0 + LAND_WID_MM * S_B
    land_xs = []
    for _ in range(4):
        land_xs.append((x, x + land_w))
        x += land_w + gap_w
    for k, (x0, x1) in enumerate(land_xs):
        c.rect(x0, wall_u - cu, x1 - x0, cu, tag=f"hub land {k+1}", fill=COPPER, stroke=COPPER_DK,
               stroke_width="0.9")
        c.rect(x0, wall_l, x1 - x0, cu, tag=f"hub land {k+1}b", fill=COPPER, stroke=COPPER_DK,
               stroke_width="0.9")
        # ONE CONDUCTOR PER NET on each face, on the substrate's OUTER face, with bare substrate in the
        # 0.6 mm gap between conductors -- the insulating gap is drawn, not implied
        c.rect(x0, face_u - cu, x1 - x0, cu, tag=f"tab conductor {k+1}", fill=COPPER,
               stroke=COPPER_DK, stroke_width="0.9")
        c.rect(x0, face_l, x1 - x0, cu, tag=f"tab conductor {k+1}b", fill=COPPER,
               stroke=COPPER_DK, stroke_width="0.9")
        c.rect(x0, wall_u, x1 - x0, (face_u - cu) - wall_u, tag=f"fillet {k+1} f1", fill=GOLD,
               stroke=COPPER_DK, stroke_width="0.6")
        c.rect(x0, face_l + cu, x1 - x0, wall_l - (face_l + cu), tag=f"fillet {k+1} f2", fill=GOLD,
               stroke=COPPER_DK, stroke_width="0.6")
        c.text((x0 + x1) / 2, wall_bot + 34, B_LABELS[k], size=12.5, anchor="middle", fill=COPPER_DK)

    # dimensions on THIS view's axes. The slot-width dimension sits to the RIGHT of the geometry and the
    # tab-thickness dimension to the LEFT: put both on the same side and their extension-line pairs start
    # at the same x, so a reader cannot tell which pair bounds which span (review r1 read them reversed).
    dim_h(c, land_xs[0][0], land_xs[1][0], wall_top - 52, f"pitch {LAND_PITCH_MM:.1f} mm",
          feat_y=wall_u - cu, label_dx=-83.4)
    dim_h(c, land_xs[0][0], land_xs[0][1], wall_top - 98, f"land {LAND_WID_MM:.1f} mm",
          feat_y=wall_u - cu, label_dx=92.4)
    dim_h(c, tx0, tx1, wall_bot + 74, f"tab {TAB_WID_MM:.1f} mm wide", feat_y=wall_bot, above=False)
    dim_v(c, wall_u, wall_l, lx_r + 40, f"slot {SLOT_W_MM:.1f} mm", feat_x=lx_r, side="right")

    # THE TAB-THICKNESS DIMENSION, corrected (review r4 defect 1). Its extension lines attach to the FR4
    # substrate's own boundaries at face_u / face_l -- the tab's copper is drawn OUTSIDE them, so the span
    # excludes both copper layers -- and it is labelled for the SUBSTRATE, not for the tab. The phrase is
    # wider than the margin available at the dimension line, so a short leader carries it into the free
    # area left of the hub block, stacked on two lines.
    mid_b = (face_u + face_l) / 2.0
    tx_dim_x = lx_l - 40
    dim_v(c, face_u, face_l, tx_dim_x, "", feat_x=tx0, side="left")
    c.line(tx_dim_x, face_l + 16, tx_dim_x, mid_b + 42, stroke=INK, stroke_width="1")
    c.text(lx_l - 36, mid_b + 56, "FR4 substrate", size=13, anchor="end")
    c.text(lx_l - 36, mid_b + 72, "0.6 mm", size=13, anchor="end")

    # balloons
    balloon(c, land_xs[3][1], wall_top - 24, 7)
    stub(c, land_xs[3][1], wall_top - 13, land_xs[3][1], wall_u - 10)
    balloon(c, lx_l - 34, wall_top + 30, 8)
    stub(c, lx_l - 34, wall_top + 39, land_xs[0][0] + 12, (wall_u + face_u) / 2)
    balloon(c, lx_r - 26, wall_bot - 26, 9)
    # balloon 10 names the tab, so it carries a LEADER to the tab (review r4 defect 2): without one it sat
    # in the hub material with nothing connecting it to what it names.
    balloon(c, tx0 + 40, wall_bot - 26, 10)
    stub(c, tx0 + 40, wall_bot - 26 - 11, tx0 + 40, face_l - 4)


# ---------------------------------------------------------------------------------------------------
# THE REQUIREMENT / QUESTION TABLE. One list, so a typo is visible in one place.
# ---------------------------------------------------------------------------------------------------
TABLE_ROWS = [
    ("Sheet scope",
     "This sheet depicts the COMMITTED hub-side interface geometry for fabrication review. It is TWO "
     "SECTIONS: nothing outside them is drawn — no solder-mask geometry, no plan view, no keep-out "
     "outline. It does NOT fix the hub's outline, thickness or layer count, the component keep-out at the "
     "slot, the slot's extent along the hub edge, or any price — none of those is fixed by a record we "
     "hold, and none is asserted here."),
    ("Committed geometry",
     "Routed slot 0.9 x 6.0 mm in the hub edge, 0.6 mm tab seated 6.0 mm into it, the four lands on the "
     "slot's faces, the fillet loaded in SHEAR on BOTH faces. This is ADR-048 §2.2 / ADR-046 §4.2.2 — the "
     "COMMITTED geometry for this interface."),
    ("Slot tolerance",
     "±0.10 mm is PROPOSED, not a cited figure (ADR-046 §4.3 records it as an assumption). ADR-048 §2.2 "
     "states it alongside \"0.9 mm wide × 6.0 mm deep\"; whether it applies to the depth as well as the "
     "width is not fixed by any record we hold. QUESTION Q3."),
    ("State of the board",
     "The board as built implements Option B: NO slot, J_W1…J_W4 lands on F.Cu only, fillet in peel "
     "(ADR-046 §4.2.1, measured with tracker/hardware/introspect_edge_interface.py). The change to the "
     "slot is PENDING. This sheet is not a statement that the board is already slotted."),
    ("Surface finish — pad faces",
     "ENIG preferred on F.Cu / B.Cu: flat and solderable after assembly. HASL is acceptable. This is the "
     "finish on the LAND, at the hub's outer faces."),
    ("Surface finish — routed faces",
     "NOT established by the pad-face finish. Copper newly exposed by routing the slot is on a CUT face, "
     "which the pad's mask opening and finish do not cover. We are asking, not asserting — QUESTION Q1."),
    ("Solder mask",
     "The four lands are drawn as bare copper, so NO solder-mask geometry is drawn on this sheet at all: "
     "whether a mask opening is required on the routed faces is part of the same open question as their "
     "finish (Q1), and the sheet does not assert a mask either way. The component keep-out is a PLACEMENT "
     "constraint, not interface geometry, and is not drawn — see the sheet-scope row."),
    ("Copper at the interface",
     "The slot's MOUTH reaches the outline ON THE SLOT'S CENTRE LINE — ADR-048 §2.5: \"the land IS the "
     "interface\". The land copper runs 1.0 … 5.0 mm inboard of that edge (ADR-048 D-1, as in the "
     "committed footprint), so on this geometry the copper is NOT flush with the routed edge. On the "
     "Option-B board as built it is flush at the edge — that is the as-built state, not this one."),
    ("NOT wanted",
     "No castellation, no edge plating, no plated slot barrel — a plated slot would short the lands around "
     "the tab. Plain exposed copper on a plain routed cut."),
    ("Land construction — UNVERIFIED",
     "The four lands on the slot's faces are drawn as copper because ADR-048 §2.2 places them there, but "
     "HOW they are produced, and which copper layer they are part of, is NOT established by any record we "
     "hold. No plating is wanted. UNVERIFIED — do not treat the drawn lands as a fabricable construction. "
     "QUESTION Q6."),
    ("Tab stack-up",
     "The 0.6 mm is the tab's FR4 SUBSTRATE thickness (ADR-046 §4.1) and it is what the View B dimension "
     "measures — the tab's copper is drawn on the substrate's OUTER faces, outside that span. The tab "
     "carries a copper layer on each face, drawn on both sections at 35 µm (1 oz) per the board stack-up, "
     "of which the four 4.0 × 1.2 mm lands are the solderable patches. The FINISHED tab is thicker by that "
     "copper and its finish, so the finished solder gap is narrower than the 0.30 mm nominal. The tab's "
     "FINISH is not fixed by a record we hold — the same class of question as the routed face, so it is "
     "included in QUESTION Q1."),
    ("Mating fit — UNVERIFIED",
     "The finished tab thickness, the slot's width and depth tolerances, the finished solder clearances, "
     "the slot-end radius and the tab-tip relief are NOT fixed by any record we hold — they are design "
     "decisions. They are shown UNVERIFIED — under query (Q7); no value for any of them is invented here."),
    ("Routed edge positional tolerance",
     "Routed edge and slot relative to copper — please advise your capability. QUESTION Q2."),
    ("Minimum routable slot",
     "A repo note records a minimum non-plated slot of ~1.0 mm, i.e. above our 0.9 mm (placement freeze, "
     "§4). We do not know whether that is current or correct for this build — please confirm, since a "
     "0.9 mm slot is the committed geometry. QUESTION Q4."),
    ("Routed cut-out cost",
     "The slot adds a routing line item. We hold no price and ask for yours; nothing here is a claim about "
     "your pricing. QUESTION Q5."),
    ("Panel tabs",
     "Keep tabs clear of these edges. They are mating surfaces and a tab there would ruin the contact."),
    ("Burrs / peeling",
     "Please advise mitigation if the cut produces them at the interface, and whether a finish on the cut "
     "face changes that."),
    ("Alignment caveat (design)",
     "The slot BOUNDS the attach angle; it does NOT key it. ADR-046 §4.2.2's figure is BARE-SUBSTRATE: "
     "0.30 mm of play over a 6.0 mm insertion is 2.86°, i.e. 8.79 mm of wing-tip movement at 176 mm. With "
     "the tab's copper on each face the finished play is narrower — 0.30 − 2 × 0.035 ≈ 0.23 mm, ≈ 2.20° / "
     "6.74 mm — and finish and tolerances narrow it further. The 90° angle is a FIXTURING requirement, and "
     "this sheet does not claim otherwise."),
]

QUESTION_ROWS = [
    ("Q1  routed-face finish",
     "Routing the slot exposes copper on a cut face. Does your process put any finish on that face? If the "
     "pad faces are ENIG, is the copper at the routed face (a) covered by the same finish, (b) bare "
     "copper, or (c) something else? Please say which, and how we must specify it to get what you "
     "describe. The wing TAB carries copper on its faces too and its finish is likewise not fixed by a "
     "record we hold — please answer for the tab's faces as well."),
    ("Q2  tolerance",
     "What positional tolerance can you hold between the routed edge/slot and the copper lands?"),
    ("Q3  slot tolerance",
     "What width tolerance can you hold on a 0.9 mm routed slot? Does the same tolerance apply to its "
     "6.0 mm depth?"),
    ("Q4  minimum slot",
     "What is your minimum routable non-plated slot width? If 0.9 mm is below it, what is the smallest you "
     "will rout, and does that change if the slot is plated?"),
    ("Q5  cost",
     "What is the additional cost of an internal routed cut-out on this order, as a line item?"),
    ("Q6  copper on the slot faces",
     "Our lands sit on the two OPPOSED INTERNAL ROUTED-SLOT FACES (4.0 × 1.2 mm per face). We are NOT "
     "identifying them as outer-layer F.Cu / B.Cu — those are the hub's EXTERNAL copper layers, a different "
     "surface. HOW that copper is produced and WHICH layer it connects to is UNRESOLVED by any record we "
     "hold, so we assert no construction. We do NOT want a plated slot barrel. Please tell us what to "
     "specify, and say if what we have drawn is not producible."),
    ("Q7  slot end radius",
     "A routed slot's inner end carries the cutter's radius. What radius will our 0.9 mm slot end have, and "
     "what relief or clearance must the mating tab's tip have to seat against it? We have drawn a "
     "semicircular end as an illustration, not as a specification."),
]

TABLE_X0, TABLE_X1 = 72, 1628
TABLE_COL = 400        # the description column starts here


def table_rows_with_wrap():
    out = []
    for k, v in TABLE_ROWS:
        out.append((k, wrap(v, 13.5, TABLE_X1 - TABLE_COL - 10), False))
    for k, v in QUESTION_ROWS:
        out.append((k, wrap(v, 13.5, TABLE_X1 - TABLE_COL - 10), True))
    return out


def table_height(rows):
    h = 20
    for _, lines, _ in rows:
        h += 16 + len(lines) * 17 + 10
    return h


def table(c, rows, y0):
    c.text(TABLE_X0, y0 - 12, "Requirements and questions for the fabricator", size=17, weight="bold")
    c.line(TABLE_X0, y0 + 4, TABLE_X1, y0 + 4, stroke="#bbb", stroke_width="1.2")
    y = y0 + 4
    for k, lines, is_q in rows:
        y += 16
        c.text(TABLE_X0 + 8, y + 12, k, size=13.5, weight="bold", fill=RED if is_q else INK)
        for ln in lines:
            c.text(TABLE_COL, y + 12, ln, size=13.5, fill=RED if is_q else "#333")
            y += 17
        y += 10
        c.line(TABLE_X0, y, TABLE_X1, y, stroke="#e6e6e6", stroke_width="1")
    return y


def header(c):
    banner = [
        ("COMMITTED GEOMETRY — ADR-048: a routed slot 0.9 × 6.0 mm in the hub edge (0.9 mm wide, 6.0 mm "
         "deep), the 0.6 mm tab seated 6.0 mm into it, the four lands on the slot's faces, the fillet "
         "loaded in SHEAR. The ±0.10 mm tolerance is PROPOSED (see Q3) and the CONSTRUCTION of the "
         "slot-face lands is UNVERIFIED (see Q6).", 14, "bold",
         "#8a2b12"),
        ("ADR-046 §4.2.2: \"Option A is the committed geometry\". The BOARD AS BUILT implements Option B — "
         "no slot, J_W* lands on F.Cu only (ADR-046 §4.2.1, measured). THE BOARD CHANGE IS PENDING: this "
         "sheet depicts the committed geometry and must not be read as the built state.", 13.5, "normal",
         "#333"),
    ]
    panel(c, 56, 26, 1588, 128, fill="#fdf7f0", stroke="#e6d6c4")
    c.text(72, 52, "Edge-launch wing socket — hub_board_v9, J_W1…J_W4", size=25, weight="bold")
    y = 76
    for t, size, weight, fill in banner:
        for ln in wrap(t, size, 1550, weight):
            c.text(72, y, ln, size=size, weight=weight, fill=fill)
            y += 18


def build(svg_path):
    rows = table_rows_with_wrap()
    a_leg_h = legend_height(A_LEGEND, A_PANEL_X1 - A_PANEL_X0 - 62)
    b_leg_h = legend_height(B_LEGEND, B_PANEL_X1 - B_PANEL_X0 - 62)
    table_y0 = LEG_Y + max(a_leg_h, b_leg_h) + 34
    H = int(table_y0 + table_height(rows) + 60)

    c = Canvas(W, H)
    header(c)
    panel(c, A_PANEL_X0, PANEL_Y0, A_PANEL_X1 - A_PANEL_X0, PANEL_Y1 - PANEL_Y0)
    panel(c, B_PANEL_X0, PANEL_Y0, B_PANEL_X1 - B_PANEL_X0, PANEL_Y1 - PANEL_Y0)
    view_a(c)
    view_b(c)
    legend(c, A_PANEL_X0 + 16, LEG_Y, "View A — what the numbers on this view are", A_LEGEND,
           A_PANEL_X1 - A_PANEL_X0 - 62)
    legend(c, B_PANEL_X0 + 16, LEG_Y, "View B — what the numbers on this view are", B_LEGEND,
           B_PANEL_X1 - B_PANEL_X0 - 62)
    y = table(c, rows, table_y0)
    footer = ("Committed geometry: docs/adr/048-v9-hub-wing-interfaces.md §2.2 (slot 0.9 × 6.0 mm, keep-out "
              "slot outline + 1.0 mm) and docs/adr/046-wing-board-interface.md §4.1/§4.2.2. Board state "
              "measured by tracker/hardware/introspect_edge_interface.py. Generated by "
              "tracker/hardware/make_edge_section.py.")
    fy = y + 30
    for ln in wrap(footer, 12, W - 144):
        c.text(72, fy, ln, size=12, fill="#777")
        fy += 16

    problems = c.check()
    if problems:
        print(f"LAYOUT GUARD REFUSED to write {svg_path}: {len(problems)} collision(s)")
        for p in problems:
            print(f"  - {p}")
        raise OverlapError(f"{len(problems)} layout problem(s)")

    c.parts.append("</svg>")
    return "\n".join(c.parts) + "\n"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="docs/fab/jlc-query/edge-launch-cross-section.svg",
                    help="SVG output path")
    ap.add_argument("--check", action="store_true",
                    help="do not write; exit 1 if the committed artefacts differ from the generated")
    a = ap.parse_args()

    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "scripts"))
    from artefact import DeterministicWriter

    try:
        svg_text = build(a.out)
    except OverlapError:
        return 1

    # belt and braces: re-derive the boxes from the emitted text and check again
    fd, tmp_svg = tempfile.mkstemp(suffix=".svg")
    os.close(fd)
    with open(tmp_svg, "w") as fh:
        fh.write(svg_text)
    post = audit_svg(tmp_svg)
    if post:
        print(f"LAYOUT GUARD (post-serialise) found {len(post)} collision(s) -- not writing")
        for p in post:
            print(f"  - {p}")
        os.unlink(tmp_svg)
        return 1

    writer = DeterministicWriter(__file__)
    writer.add(a.out, svg_text)
    png = a.out.replace(".svg", ".png")
    if shutil.which("rsvg-convert"):
        fd2, tmp_png = tempfile.mkstemp(suffix=".png")
        os.close(fd2)
        r = subprocess.run(["rsvg-convert", "-w", "2000", tmp_svg, "-o", tmp_png],
                           capture_output=True, text=True)
        # A RENDER THAT PRODUCED NO FILE MUST FAIL LOUDLY. v1 printed nothing when rsvg rejected the SVG (a
        # literal '<' made it unparseable) and a stale PNG was reviewed as if it were this one.
        if r.returncode != 0 or not os.path.exists(tmp_png) or os.path.getsize(tmp_png) == 0:
            print(f"RENDER FAILED: rsvg-convert rc={r.returncode}")
            print(f"  stderr: {(r.stderr or r.stdout or '(none)').strip()[:400]}")
            os.unlink(tmp_svg)
            os.unlink(tmp_png)
            return 1
        writer.add_file(png, tmp_png)
        os.unlink(tmp_png)
    else:
        print("rsvg-convert NOT FOUND -- the PNG cannot be produced")
        os.unlink(tmp_svg)
        return 1
    os.unlink(tmp_svg)

    rc = writer.finish(check=a.check)
    if rc == 0 and not a.check:
        print(f"  png      {png}  sha256 {hashlib.sha256(open(png, 'rb').read()).hexdigest()}")
        print("  layout   guard passed (text measured with DejaVuSans.ttf, verified against this host's "
              "renderer)")
    return rc


if __name__ == "__main__":
    sys.exit(main())
