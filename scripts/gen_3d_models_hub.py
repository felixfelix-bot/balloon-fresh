#!/usr/bin/env python3
"""Parametric 3D (VRML) models for the v9 HUB board's parts -> tracker/hardware/3dmodels/hub/

WHY THIS FILE EXISTS
--------------------
Measured 2026-10-11 with `scripts/model_resolution_census.py`: the v9 hub board carries
39 footprints, makes **32 model references and resolves 25**, and **7 footprints carry no
`(model ...)` block at all**:

    no model block : J_VCC, J_W1, J_W2, J_W3, J_W4, U2, U4
    unresolved     : NiceRF_LoRa2021.wrl (U3), U.FL_Molex_MCRF_73412-0110_Vertical.step
                     (ANT1-ANT4), ublox_MAX.step (U5), ESP32-S3-WROOM-1U.step (U1)

U2 is the `LoRa2021F33-2G4` -- the **largest part on the board** (39.0 x 21.0 mm F.Fab) and the
433 MHz bent-pipe downlink radio the whole balloon exists to carry. U4 is the `SX1280` range
radio. Neither had a model at all; the rest pointed at files the installed `kicad-packages3d`
package does not ship (it has `ESP-WROOM-02`, not `ESP32-S3-WROOM-1U`; `RF_GPS.3dshapes` is
empty; there is no LoRa2021 and no U.FL/MCRF).

`kicad-cli pcb render` accepts all of that in silence -- exit 0, no warning, parts simply
absent from the image -- so a render of this board *looked* populated while the two radios
were invisible, and the operator's spatial-review gate would have been judging a board whose
RF bodies could not be seen.  This generator emits **plain-text VRML 2.0 committed in-repo**,
so every reference resolves with nothing installed and the census can assert it.

WHERE THE DIMENSIONS COME FROM
------------------------------
**X and Y are measured, not authored**: each part's envelope is read from the footprint's own
`F.Fab` outline (falling back to `F.CrtYd` where the library ships no F.Fab, which is stated in
that model's header) inside `tracker/hardware/hub_board_v9.kicad_pcb`.  Those are the numbers
`scripts/footprint_envelope_probe.py` prints, and they are the same numbers the placer used, so
a model can never silently disagree with the land pattern it sits on.

**Z is NOT measured for any of these parts**, and the repo carries no cited height for them.
Every model therefore states its height as a nominal placeholder flagged `TODO(unverified)` in
its own header, is drawn **translucent** so a render cannot be mistaken for a measured body, and
is titled `..._envelope` in the VRML to say so out loud.  The gate these models serve is a
*spatial* review --- placement, orientation, clearance in the board plane --- which X/Y settles;
inventing a Z would fake evidence for the one axis nothing here measures.

MEASURED MODEL CONVENTIONS
--------------------------
Inherited from the wing generator (which measured them, twice, independently -- see its module
docstring): **X = footprint-local +x, Y = -(footprint-local +y), Z = up with Z = 0 at the board
TOP face**, and **1 VRML unit = 2.54 mm**.  The primitives are imported from that module rather
than re-implemented, so the two trees cannot drift.

RUN
---
    python3 scripts/gen_3d_models_hub.py            # write/refresh the models
    python3 scripts/gen_3d_models_hub.py --check    # exit 1 if the tree is stale (CI mode)
"""
from __future__ import annotations

import argparse
import importlib.util
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
MODEL_DIR = os.path.join(REPO, "tracker", "hardware", "3dmodels")
GEN_REL = "scripts/gen_3d_models_hub.py"


def _load_wing():
    """Import the wing generator for its measured primitives.

    Same unit convention, same winding, same frame -- re-implementing them here is how two
    model trees drift apart and one of them ends up rotated 90 degrees.
    """
    path = os.path.join(HERE, "gen_3d_models_wing.py")
    spec = importlib.util.spec_from_file_location("gen_3d_models_wing", path)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules["gen_3d_models_wing"] = mod
    spec.loader.exec_module(mod)
    return mod


wing = _load_wing()
_u = wing._u
_box = wing._box
_wrl = wing._wrl
_todo = wing._todo

BOARD = "tracker/hardware/hub_board_v9.kicad_pcb"
PROBE = "scripts/footprint_envelope_probe.py"
ADR029 = "docs/adr/029-dual-band-flight-board.md"
ADR048 = "docs/adr/048-v9-hub-wing-interfaces.md"
F33_PLAN = "docs/F33-MODULE-PLAN.md"


def _hdr(part: str, dims: str, source: str, extra=()) -> str:
    """Same header contract as the wing generator, naming THIS generator."""
    lines = [
        "# balloon-fresh -- parametric 3D model (plain-text VRML 2.0)",
        f"# generator  : {GEN_REL}  (regenerate: python3 {GEN_REL})",
        f"# part       : {part}",
        f"# dims_mm    : {dims}",
        "# frame      : X = footprint-local +x, Y = -(footprint-local +y), Z = up, "
        "Z=0 at the board TOP face",
        "# units      : 1 VRML unit = 2.54 mm (0.1 in) -- KiCad VRML convention; "
        "assign with (scale (xyz 1 1 1))",
    ]
    for s in source.splitlines():
        lines.append("# source     : " + s)
    for e in extra:
        lines.append("# note       : " + e)
    return "\n".join(lines)


def _envelope(name, x, y, z, header, colour, transparency=0.35):
    """One centred slab, translucent: an envelope, deliberately not a body.

    Transparency is the point, not decoration -- nobody has measured these heights, so a
    render must not present them with the same visual authority as the wing's measured cell.
    """
    hx, hy = x / 2.0, y / 2.0
    return _wrl(header, [_box(name, -hx, hx, -hy, hy, 0.0, z, colour,
                              transparency=transparency, specular=0.15, shininess=0.1)])


def _nominal_z_note(mm: float, what: str) -> str:
    return (f"the {mm} mm height is TODO(unverified) -- a nominal {what} placeholder, NOT a "
            f"sourced figure; the body is drawn translucent at transparency 0.35 so a render "
            f"cannot read it as measured")


def _fabsrc(ref: str, fp: str, val: str, wxh) -> str:
    return (f"{BOARD} footprint \"{fp}\" (Reference {ref}, Value \"{val}\"): its own F.Fab "
            f"outline measures {wxh[0]} x {wxh[1]} mm.  Reproduce every envelope with "
            f"`/usr/bin/python3.14 {PROBE} {BOARD}`.")


def _crtydsrc(ref: str, fp: str, val: str, wxh) -> str:
    return (f"{BOARD} footprint \"{fp}\" (Reference {ref}, Value \"{val}\"): this library "
            f"footprint ships NO F.Fab outline, so the envelope is its F.CrtYd courtyard "
            f"{wxh[0]} x {wxh[1]} mm.  Reproduce with "
            f"`/usr/bin/python3.14 {PROBE} {BOARD}`.")


# --------------------------------------------------------------------------- the models
def f33_model() -> str:
    """U2 -- LoRa2021F33-2G4, the 433 MHz bent-pipe downlink radio.  Largest part on the board."""
    return _envelope(
        "u2_lora2021f33_envelope", 39.0, 21.0, 3.2,
        _hdr(
            "U2 -- LoRa2021F33-2G4 (433 MHz bent-pipe downlink radio) -- ENVELOPE, height unverified",
            "39.0 x 21.0 x 3.2(nominal) mm -- X/Y measured from F.Fab, Z a flagged placeholder",
            _fabsrc("U2", "balloon_flight_v9:LoRa2021F33_2G4", "LoRa2021F33-2G4",
                    (39.0, 21.0))
            + "\n"
            + f"{F33_PLAN} line 27: \"| Module dimensions | 39 x 21 mm |\" (from the NiceRF "
              "datasheet V1.1, confirmed against LCSC).\n"
            + f"{ADR029} line 199: \"- **39 x 21 mm on a 55 x 45 mm board** -- the module "
              "dominates the layout and constrains\".",
            extra=[
                "THIS IS THE PART THE SPATIAL REVIEW MOST NEEDS TO SEE: it is the largest body "
                "on the board, it carries the 433 MHz PA, and before this model existed the "
                "render showed an empty courtyard exactly where it sits.",
                "an 18-pin castellated module -- the castellated pad row, the pin-1 corner and "
                "the shield can are NOT modelled; only the body envelope is, because only the "
                "envelope is what the placement review consumes.",
                "F.CrtYd measured 39.6 x 21.6 mm, i.e. 0.3 mm clearance ring per side.",
                "the F33 and the bare LoRa2021 (U3) are selectable variants of one rail "
                "(kanban t_1b12a7ab, nested dual footprint) -- both envelopes are modelled so "
                "either selection is reviewable.",
            ] + _todo(_nominal_z_note(3.2, "castellated-module"),
                      "the exact PA/shield stack height and any keep-out above the module"),
        ),
        (0.16, 0.18, 0.22),
    )


def lora2021_model() -> str:
    """U3 -- bare LoRa2021 castellated module (the 2.4 GHz variant of the same rail)."""
    return _envelope(
        "u3_lora2021_castellated_envelope", 19.81, 14.98, 3.2,
        _hdr(
            "U3 -- LoRa2021 (bare, castellated) -- ENVELOPE, height unverified",
            "19.81 x 14.98 x 3.2(nominal) mm -- X/Y measured from F.Fab, Z a flagged placeholder",
            _fabsrc("U3", "balloon_flight_v9:LoRa2021_Castellated", "LoRa2021_Castellated",
                    (19.81, 14.98))
            + "\n"
            + f"{ADR029} line 365: \"| Board area | 39 x 21 mm (dominates 55 x 45) | 19.81 x "
              "14.98 + SX1280 module |\".",
            extra=[
                "the hub's committed model reference pointed at "
                "`${KICAD8_3DMODEL_DIR}/RF_Module.3dshapes/NiceRF_LoRa2021.wrl`, which the "
                "installed package does not ship -- hence unresolved, hence invisible.",
                "U3 is the DNP alternative to U2 on the dual-footprint rail; a render shows "
                "which one is populated.",
            ] + _todo(_nominal_z_note(3.2, "castellated-module")),
        ),
        (0.16, 0.18, 0.22),
    )


def sx1280_model() -> str:
    """U4 -- SX1280 QFN24 range radio.  Had NO model block at all."""
    return _envelope(
        "u4_sx1280_qfn24_envelope", 4.4, 4.4, 0.9,
        _hdr(
            "U4 -- SX1280 (QFN24, 2.4 GHz FLRC range radio) -- ENVELOPE, height unverified",
            "4.4 x 4.4 x 0.9(nominal) mm -- X/Y from the F.CrtYd courtyard, Z a flagged placeholder",
            _crtydsrc("U4", "balloon_flight_v9:SX1280_QFN24", "SX1280", (4.4, 4.4)),
            extra=[
                "U4 carried NO `(model ...)` block at all -- the renderer drew nothing there, "
                "and the census classifies that separately from an unresolvable reference.",
                "the 4.4 x 4.4 courtyard is the PLACEMENT envelope, i.e. the body plus the "
                "assembly clearance ring; the QFN body itself is smaller, and the 24 "
                "perimeter lands are board copper that KiCad draws itself.",
                "0.9 mm is a nominal QFN body height, NOT a sourced figure -- this specific "
                "part number is not fixed in the repo.",
            ] + _todo(_nominal_z_note(0.9, "QFN"),
                      "the SX1280 body size within the 4.4 mm courtyard (no F.Fab to read)"),
        ),
        (0.14, 0.15, 0.17),
    )


def esp32_model() -> str:
    """U1 -- ESP32-S3-WROOM-1U-N8R8, the flight computer."""
    return _envelope(
        "u1_esp32s3_wroom1u_envelope", 18.0, 19.2, 3.2,
        _hdr(
            "U1 -- ESP32-S3-WROOM-1U-N8R8 -- ENVELOPE, height unverified",
            "18.0 x 19.2 x 3.2(nominal) mm -- X/Y measured from F.Fab, Z a flagged placeholder",
            _fabsrc("U1", "RF_Module:ESP32-S3-WROOM-1U", "ESP32-S3-WROOM-1U-N8R8",
                    (18.0, 19.2))
            + "\n"
            + f"{BOARD} carries 9 unnumbered 0.7 x 0.7 mm mechanical shield/thermal pads on "
              f"this footprint (recorded in tracker/hardware/PLACEMENT-S0-FREEZE-v9-hub.md "
              f"line 206); they are board copper and are drawn by KiCad, not here.",
            extra=[
                "the committed reference pointed at "
                "`${KICAD9_3DMODEL_DIR}/RF_Module.3dshapes/ESP32-S3-WROOM-1U.step`; the "
                "installed package ships `ESP-WROOM-02`, not this module, so it was unresolved.",
                "WROOM-1**U** is the connectorised variant: the U.FL/I-PEX antenna jack sits "
                "off-board via a pigtail, so no on-module antenna is drawn.",
                "F.CrtYd measured 19.5 x 20.15 mm.",
            ] + _todo(_nominal_z_note(3.2, "module-with-shield"),
                      "the shield-can top height and the 3.2 mm body thickness both rest on "
                      "the Espressif datasheet, which the repo does not carry"),
        ),
        (0.16, 0.18, 0.22),
    )


def gnss_model() -> str:
    """U5 -- u-blox MAX-M10S GNSS receiver."""
    return _envelope(
        "u5_ublox_max_m10s_envelope", 9.7, 10.1, 2.4,
        _hdr(
            "U5 -- u-blox MAX-M10S (GNSS receiver) -- ENVELOPE, height unverified",
            "9.7 x 10.1 x 2.4(nominal) mm -- X/Y measured from F.Fab, Z a flagged placeholder",
            _fabsrc("U5", "RF_GPS:ublox_MAX", "MAX-M10S", (9.7, 10.1)),
            extra=[
                "the committed reference pointed at "
                "`${KICAD9_3DMODEL_DIR}/RF_GPS.3dshapes/ublox_MAX.step`; the installed "
                "`RF_GPS.3dshapes` directory exists but is EMPTY, so it was unresolved.",
            ] + _todo(_nominal_z_note(2.4, "MAX-format GNSS module")),
        ),
        (0.16, 0.18, 0.22),
    )


def ufl_model() -> str:
    """ANT1-ANT4 -- U.FL / MCRF antenna jacks (433 TX, 2.4 RX, 2.4 range, GNSS L1)."""
    return _envelope(
        "ant_ufl_mcrf_envelope", 2.6, 2.6, 2.0,
        _hdr(
            "ANT1/ANT2/ANT3/ANT4 -- U.FL (Molex MCRF 73412-0110) vertical jack -- ENVELOPE, "
            "height unverified",
            "2.6 x 2.6 x 2.0(nominal) mm -- X/Y measured from F.Fab, Z a flagged placeholder",
            _fabsrc("ANT1..ANT4", "Connector_Coaxial:U.FL_Molex_MCRF_73412-0110_Vertical",
                    "U.FL_433_TX / U.FL_2G4_RANGE / U.FL_2G4_RX / U.FL_GNSS_L1", (2.6, 2.6))
            + "\n"
            + f"the committed references pointed at "
              f"`${{KICAD9_3DMODEL_DIR}}/Connector_Coaxial.3dshapes/"
              f"U.FL_Molex_MCRF_73412-0110_Vertical.step`, which the installed package does "
              f"not ship, so all four were unresolved.",
            extra=[
                "the 2.6 x 2.6 F.Fab figure is the jack's PAD-LAND envelope on the board; the "
                "physical connector body is taller and narrower than its land pattern, so this "
                "model over-states the body footprint in X/Y -- deliberately, because a spatial "
                "review should see the land it must keep clear, and under-stating it would hide "
                "a collision.",
                "four separate RF ports, one per antenna path; the census resolves all four "
                "through this one model.",
            ] + _todo(_nominal_z_note(2.0, "U.FL jack"),
                      "the MCRF 73412-0110 body height and the mating pigtail's swept volume"),
        ),
        (0.72, 0.74, 0.78),
    )


def wing_socket_model() -> str:
    """J_W1..J_W4 -- the hub-side wing-tab sockets.  Had NO model block at all."""
    return _envelope(
        "jw_wing_tab_socket_envelope", 7.0, 9.6, 3.0,
        _hdr(
            "J_W1..J_W4 -- hub-side WING_SOCKET_4P (receptacle for the wing tab) -- ENVELOPE, "
            "height unverified",
            "7.0 x 9.6 x 3.0(nominal) mm -- X/Y from the F.CrtYd courtyard, Z a flagged placeholder",
            _crtydsrc("J_W1..J_W4", "Tracker_Mechanical:Wing_Tab_4P",
                      "WING_SOCKET_4P (hub wing interface)", (7.0, 9.6))
            + "\n"
            + f"{ADR048} items 3/6 fix the hub-side socket as a 0.9 x 6.0 mm slot for the "
              f"0.6 mm tab, i.e. a 0.00 mm worst-case clearance, and ADR-048 files that "
              f"clearance as OPEN.",
            extra=[
                "these four footprints carried NO `(model ...)` block at all -- four of the "
                "seven census omissions.",
                "CRITICAL FOR THE REVIEW: the wing tab enters here, so this is the one place "
                "where the wing and the hub meet in space. A review that cannot see these "
                "cannot judge the interface at all.",
                "the 7.0 x 9.6 courtyard is the socket's keep-out, not its body; the 0.9 x 6.0 "
                "slot is NOT drawn as a slot because the model is a solid envelope and a "
                "hole would imply a measured bore the repo does not have.",
            ] + _todo(_nominal_z_note(3.0, "edge receptacle"),
                      "the socket body height, and whether the 0.9 x 6.0 mm slot is a real "
                      "fabricated feature or a board-edge cut (ADR-048 opens this)"),
        ),
        (0.30, 0.30, 0.32),
    )


def solder_jumper_model() -> str:
    """J_VCC -- 3-way solder jumper selecting 5 V raw / 3V3.  Had NO model block at all."""
    return _envelope(
        "jvcc_solder_jumper_3p_envelope", 4.6, 2.5, 1.0,
        _hdr(
            "J_VCC -- SolderJumper-3, F33_VCC_SEL (5V raw | 3V3) -- ENVELOPE, height unverified",
            "4.6 x 2.5 x 1.0(nominal) mm -- X/Y from the F.CrtYd courtyard, Z a flagged placeholder",
            _crtydsrc("J_VCC", "Jumper:SolderJumper-3_P1.3mm_Open_",
                      "F33_VCC_SEL (5V raw | 3V3)", (4.6, 2.5))
            + "\n"
            + "the 1.3 mm pad pitch is in the footprint NAME "
              "(`SolderJumper-3_P1.3mm_Open_`), which is an in-repo record; the courtyard "
              "width follows from it.",
            extra=[
                "carried NO `(model ...)` block at all -- one of the seven census omissions.",
                "this jumper selects the F33's supply rail, so its position matters to the "
                "power review even though it has no body: a bridged jumper is a fitted part.",
            ] + _todo(_nominal_z_note(1.0, "solder blob / open-jumper"),
                      "whether the open-3-jumper ships bridged or open, and the solder blob's "
                      "swept volume -- `VCC_SEL` records the intent, not the fitted state"),
        ),
        (0.87, 0.72, 0.25),
    )


MODELS = {
    "hub/u2_lora2021f33_2g4_envelope.wrl": f33_model(),
    "hub/u3_lora2021_castellated_envelope.wrl": lora2021_model(),
    "hub/u4_sx1280_qfn24_envelope.wrl": sx1280_model(),
    "hub/u1_esp32s3_wroom1u_envelope.wrl": esp32_model(),
    "hub/u5_ublox_max_m10s_envelope.wrl": gnss_model(),
    "hub/ant_ufl_mcrf_envelope.wrl": ufl_model(),
    "hub/jw_wing_tab_socket_envelope.wrl": wing_socket_model(),
    "hub/jvcc_solder_jumper_3p_envelope.wrl": solder_jumper_model(),
}

# The designators each model must cover, so that a caller can assert the whole board is
# covered without re-deriving the mapping from the board file.
PART_MODELS = {
    "U1": "hub/u1_esp32s3_wroom1u_envelope.wrl",
    "U2": "hub/u2_lora2021f33_2g4_envelope.wrl",
    "U3": "hub/u3_lora2021_castellated_envelope.wrl",
    "U4": "hub/u4_sx1280_qfn24_envelope.wrl",
    "U5": "hub/u5_ublox_max_m10s_envelope.wrl",
    "ANT1": "hub/ant_ufl_mcrf_envelope.wrl",
    "ANT2": "hub/ant_ufl_mcrf_envelope.wrl",
    "ANT3": "hub/ant_ufl_mcrf_envelope.wrl",
    "ANT4": "hub/ant_ufl_mcrf_envelope.wrl",
    "J_W1": "hub/jw_wing_tab_socket_envelope.wrl",
    "J_W2": "hub/jw_wing_tab_socket_envelope.wrl",
    "J_W3": "hub/jw_wing_tab_socket_envelope.wrl",
    "J_W4": "hub/jw_wing_tab_socket_envelope.wrl",
    "J_VCC": "hub/jvcc_solder_jumper_3p_envelope.wrl",
}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    ap.add_argument("--check", action="store_true",
                    help="do not write; exit 1 if the committed models differ from the generator")
    ap.add_argument("--out", default=MODEL_DIR, help=f"model tree (default {MODEL_DIR})")
    args = ap.parse_args(argv)

    stale, wrote = [], []
    for rel, text in MODELS.items():
        path = os.path.join(args.out, rel)
        old = open(path).read() if os.path.exists(path) else None
        if old == text:
            print(f"  ok      {rel}")
            continue
        stale.append(rel)
        if args.check:
            print(f"  STALE   {rel}")
            continue
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as fh:
            fh.write(text)
        wrote.append(rel)
        print(f"  wrote   {rel}  ({len(text)} bytes)")

    print(f"\nmodels: {len(MODELS)}  written: {len(wrote)}  stale: {len(stale)}")
    if args.check and stale:
        print(f"STALE MODEL TREE -- run: python3 {GEN_REL}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
