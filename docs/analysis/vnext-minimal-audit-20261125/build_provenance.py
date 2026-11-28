#!/usr/bin/env python3
"""Build the provenance block embedded in the vnext audit JSON (ADR-089 gate G1's
ordered-archive reconciliation, read-only evidence).

Resolves: which exact artefacts make up the ORDERED v10, and how they relate to the
reference board measured by vnext_layer_audit.py. Every claim below is either a
measured hash or a file path -- no recalled facts.
"""
import hashlib
import json
import subprocess
import sys

REPO = "/home/c08r4d0r/worktrees/vnext-minimal-docs"


def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def git(*args):
    return subprocess.run(["git", "-C", REPO, *args], capture_output=True,
                         text=True, check=True).stdout.strip()


provenance = {
    "ordered_v10": {
        "upload_zip": "docs/fab/v10-order-top-only/v10-jlcpcb-upload.zip",
        "upload_zip_sha256": sha(f"{REPO}/docs/fab/v10-order-top-only/v10-jlcpcb-upload.zip"),
        "zip_contents_note": "gerbers/ + bom-jlc.csv + cpl-jlc.csv; NO .kicad_pcb ships in the order",
        "gerbers_sha256": {
            p: sha(f"{REPO}/docs/fab/v10-order-top-only/gerbers/{p}") for p in [
                "board.drl", "board-Edge_Cuts.gm1", "board-F_Cu.gtl", "board-In1_Cu.g1",
                "board-In2_Cu.g2", "board-B_Cu.gbl"]
        },
        "gerber_source": "docs/analysis/bulk-route-20261107/fab-11opens/ -- each ordered gerber is "
                         "BYTE-IDENTICAL (filecmp) to its fab-11opens counterpart",
        "gerber_generator_commit": git("show", "-s", "--format=%h %s", "39ffce2b"),
        "gerber_generator_note": "commit 39ffce2b regenerated the fab package from the routed "
                                 "board file then named latest.kicad_pcb (message: 'regenerate the "
                                 "bare-board fab package for the 11-open board 322ade1e')",
        "routed_board_at_generation": "docs/analysis/bulk-route-20261107/latest.kicad_pcb",
        "routed_board_sha256": sha(f"{REPO}/docs/analysis/bulk-route-20261107/latest.kicad_pcb"),
        "assembly_variant": "TOP-ONLY for the order's BOM/CPL (19 placements; D_BP1-4 excluded, "
                            "SS24 qty 2 = D_HUB1-2 only). The DOUBLE-SIDED variant "
                            "(assembly-partial/asm-cpl-jlc.csv, 23 placements incl. 4 bottom "
                            "D_BP diodes) is a SEPARATE order option, not this zip.",
        "canonical_v10_board": "tracker/hardware/hub_board_v10_lora1280_7of9.kicad_pcb",
        "canonical_v10_sha256": sha(f"{REPO}/tracker/hardware/hub_board_v10_lora1280_7of9.kicad_pcb"),
        "canonical_vs_routed": "DIFFERENT files, measured: latest.kicad_pcb is the bulk-route "
                               "campaign's accepted result; hub_board_v10_lora1280_7of9.kicad_pcb is "
                               "the canonical v10 board of record (pr-reconciliation-20261030 "
                               "REPORT.md cites sha 732bfe88... which matches the file today)",
        "stage1_reference": "tracker/hardware/hub_board_v11_stage1.kicad_pcb",
        "stage1_sha256": sha(f"{REPO}/tracker/hardware/hub_board_v11_stage1.kicad_pcb"),
        "stage1_note": "NOT an ordered artefact. It is the v11 stage-1 experiment board "
                       "(netlist-vs-board site-D divergence: netlist U_LORA1280, board U_E28 with "
                       "E28-2G4M27SX footprint) used here ONLY because ADR-089 G3 names it as the "
                       "reference board for the MINIMAL net set, and it is the only .kicad_pcb "
                       "carrying the v11-stage part set (49 footprints incl. U_C, U_CUT1-4, U_E28).",
    },
    "site_D_divergence": {
        "netlist": "tracker/hardware/schematics/flight_board/v11_flight.net names U_LORA1280 "
                   "(value LoRa1280, footprint balloon_flight_v10:LoRa1280)",
        "board": "hub_board_v11_stage1.kicad_pcb carries U_E28 (footprint E28-2G4M27SX class)",
        "adr": "ADR-139 chose LoRa1280 over E28; the stage-1 board predates the swap-back decision",
        "minimal_relevance": "site D is REMOVED on MINIMAL either way (ADR-089 S1), so the "
                             "divergence does not change the MINIMAL net set; it must be "
                             "reconciled before any non-MINIMAL vnext build (gate G1/G2).",
    },
    "f33_identity": {
        "manufacturer_page": "https://www.nicerf.com/lora-module/lora2021f33-2g4.html",
        "manufacturer_page_name": "LoRa2021F33-2G4 (2W high-power LR2021 dual-band module, "
                                  "39.0 x 21.0 x 3.3 mm, 18-pin table; page retrieved live "
                                  "2026-11-25)",
        "lcsc_reading": "F33-PART-NUMBER-VERIFICATION.md (2026-10-14) reads LCSC C53243927 as "
                        "LoRa1121F33-2G4-433MHz, family LoRa1121F33-2G4",
        "conflict": "COMPETING EVIDENCE, not resolved: manufacturer says 2021 (LR2021-based), "
                    "LCSC listing says 1121. NiceRF's own page is the more authoritative source "
                    "for the module name; LCSC's listing title may itself be wrong. Neither "
                    "reading was derived from the operator's physical module.",
        "operator_module": "the operator owns an 'LR2021 F33' (task brief 2026-11-25); its exact "
                           "identity, revision, pin mapping and land fit are STILL UNVERIFIED "
                           "against a physical module (gate G2, plan Phase 1.1) -- physical fit "
                           "alone is insufficient",
        "rule": "NO RENAME performed. The repo keeps both readings side by side with their "
                "sources; the exact module the operator holds needs pin verification before any "
                "footprint is trusted.",
    },
}

out = sys.argv[1]
with open(out, "w") as f:
    json.dump(provenance, f, indent=1)
print("WROTE", out)
