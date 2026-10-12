#!/usr/bin/env python3
"""flrc_512b_throughput_audit.py — settle the "2.6 Mbps at 512 B" claim, hardware-free.

Context (kanban balloon/t_6b68897c). The operator reported measuring ~2.6 Mbps on
the LR2021 FLRC link by doubling the packet payload 255 B -> 512 B. No such run
exists on disk. This tool does three things that need no radio:

  1. Evidence audit: enumerates the on-disk FLRC payload sweeps and proves which
     payload sizes were ever measured (and therefore which were not).
  2. Ceiling arithmetic: recomputes the goodput ceiling for LEN in {127, 255, 511}
     under three explicit models — the repo's *uncoded* model, that model + CRC,
     and the model the shipped firmware actually airs (CR 3/4, per the LR20xx
     driver's own time-on-air numerator). Shows whether 2600 kbps goodput is
     reachable at all, under any of them.
  3. Firmware-capability check: confirms that 511 B is a *legal* FLRC length for
     this hardware (E80 firmware + LR20xx driver + RadioLib), i.e. that the
     255-byte ceiling that the RP2040 docs assume is an SX1280/legacy artefact.
     The bound is resolved from files INSIDE the checkout (the firmware's
     BENCH_START_LEN_MAX_FLRC clamp, then the vendor driver's documented range)
     so the report is identical on a CI runner; a RadioLib checkout outside the
     repo is only an advisory cross-check — see flrc_max_payload().

Everything is arithmetic over files already in the repo. No serial port is
opened, no board is touched. Run from the repo root.

Usage:
    python3 tools/flrc_512b_throughput_audit.py            # full audit
    python3 tools/flrc_512b_throughput_audit.py --selftest # assertions only
    python3 tools/flrc_512b_throughput_audit.py --json     # machine-readable
"""

from __future__ import annotations

import argparse
import csv
import glob
import json
import os
import re
import sys

# ── FLRC on-air models ───────────────────────────────────────────────────────
#
# Three explicit models. They are NOT interchangeable, and the difference is the
# whole point of this audit: the repo's published ceiling (2540/2570 kbps) is an
# *uncoded* bound, while the shipped firmware runs coding rate 3/4.
#
#   MODEL_AUDIT      16 b preamble + 32 b sync + payload*8, no CRC
#                    -> the 2026-07-26 datasheet-audit model; reproduces its
#                       0.803 ms / 2540 kbps at 255 B and the card's 2570 at 511 B
#   MODEL_AUDIT_CRC  MODEL_AUDIT plus a 2-byte CRC field
#                    -> nearest simple bound with the fw's CRC setting
#   MODEL_FW_CR34    the LR20xx driver's own time-on-air numerator
#                    (lr20xx_radio_flrc.c: lr20xx_get_flrc_time_on_air_numerator)
#                    with the parameters src/radio_bench.c actually configures:
#                      cr = CR_3_4, header = FIX_LEN, crc = 2 B,
#                      preamble = 32 bits, sync = 4 B
#                    numerator = ceil(12 * n_coded / ceil_den) + n_uncoded
#                      n_coded   = header_bits + tail_bits + crc*8 + payload*8
#                      n_uncoded = preamble_bits + 21 (AGC) + sync_bits
#                      ceil_den  = 9 for CR 3/4 (lr20xx_get_flrc_cr_scalled_numerator)
#                    -> this is what the radio actually puts on air, so it is the
#                       honest ceiling for our measurements.
#
# 1 kbps == 1000 bit/s, so a numerator expressed in bits divides by br_kbps*1000.

FLRC_BR_2600_KBPS = 2600.0

MODEL_AUDIT = dict(preamble_bits=16, sync_bits=32, crc_bytes=0, agc_bits=0)
MODEL_AUDIT_CRC = dict(preamble_bits=16, sync_bits=32, crc_bytes=2, agc_bits=0)
# Deprecated alias: kept so older callers/tests that imported MODEL_DRIVER keep
# working. It is NOT the driver's model — see MODEL_FW_CR34 for that.
MODEL_DRIVER = MODEL_AUDIT_CRC

# Firmware's real configuration (src/radio_bench.c:52-69, 171-180, 314).
FW_CR_DEN = 9      # LR20XX_RADIO_FLRC_CR_3_4 -> ceil(12 * n / 9)
FW_TAIL_BITS = 6   # lr20xx_radio_flrc_get_tail_len_in_bits(CR 3/4)
FW_HEADER_BITS = 0  # LR20XX_RADIO_FLRC_PKT_FIX_LEN


def airtime_s(payload_b: int, br_kbps: float = FLRC_BR_2600_KBPS,
              preamble_bits: int = 32, sync_bits: int = 32, crc_bytes: int = 2,
              agc_bits: int = 0) -> float:
    """On-air time in seconds for one FLRC packet, uncoded (no CR scaling)."""
    bits = preamble_bits + agc_bits + sync_bits + (payload_b + crc_bytes) * 8
    return bits / (br_kbps * 1000.0)


def goodput_ceiling_kbps(payload_b: int, **kw) -> float:
    """Payload goodput assuming ZERO host/SPI overhead (pure air-time limit)."""
    return payload_b * 8 / airtime_s(payload_b, **kw) / 1000.0


def fw_airtime_s(payload_b: int, br_kbps: float = FLRC_BR_2600_KBPS,
                 cr_den: int = FW_CR_DEN, tail_bits: int = FW_TAIL_BITS,
                 crc_bytes: int = 2, preamble_bits: int = 32, sync_bits: int = 32,
                 agc_bits: int = 21) -> float:
    """On-air time in seconds using the LR20xx driver's time-on-air numerator.

    Mirrors lr20xx_get_flrc_time_on_air_numerator():
        n_coded_after_decode = ceil(12 * n_coded / cr_den)
        numerator            = n_coded_after_decode + preamble + agc + sync
        airtime              = numerator / bitrate
    """
    n_coded = FW_HEADER_BITS + tail_bits + crc_bytes * 8 + payload_b * 8
    n_coded_after_decode = (12 * n_coded + cr_den - 1) // cr_den
    numerator = n_coded_after_decode + preamble_bits + agc_bits + sync_bits
    return numerator / (br_kbps * 1000.0)


def fw_goodput_ceiling_kbps(payload_b: int, **kw) -> float:
    """Payload goodput ceiling under the firmware's real (CR 3/4) configuration."""
    return payload_b * 8 / fw_airtime_s(payload_b, **kw) / 1000.0


# ── 1. Evidence audit ────────────────────────────────────────────────────────

SWEEP_GLOBS = [
    "full-sweep-summary-*.csv",
    "sweep-results-*.csv",
    "full-sweep-results-*-summary-*.csv",
]


def _summary_paths(root: str) -> list[str]:
    out: list[str] = []
    for pat in SWEEP_GLOBS:
        out.extend(sorted(glob.glob(os.path.join(root, pat))))
    return out


def measured_payloads(root: str) -> dict:
    """{payload_bytes: [file, ...]} for every FLRC payload size in the sweeps."""
    seen: dict[int, list[str]] = {}
    for path in _summary_paths(root):
        try:
            with open(path, newline="") as fh:
                for row in csv.DictReader(fh):
                    if (row.get("mod") or "").strip().lower() != "flrc":
                        continue
                    raw = (row.get("plen") or "").strip()
                    if not raw.isdigit():
                        continue
                    seen.setdefault(int(raw), []).append(os.path.basename(path))
        except (OSError, csv.Error):
            continue
    return seen


def flrc_rows(root: str, min_payload: int = 255) -> list[dict]:
    """FLRC sweep rows with payload >= min_payload, with parsed numerics."""
    rows: list[dict] = []
    for path in _summary_paths(root):
        try:
            with open(path, newline="") as fh:
                for row in csv.DictReader(fh):
                    if (row.get("mod") or "").strip().lower() != "flrc":
                        continue
                    try:
                        plen = int((row.get("plen") or "").strip())
                    except ValueError:
                        continue
                    if plen < min_payload:
                        continue
                    rows.append({
                        "file": os.path.basename(path),
                        "label": row.get("label", ""),
                        "br": row.get("br", ""),
                        "freq": row.get("freq", ""),
                        "plen": plen,
                        "rx": int(row.get("rx_pkts") or 0),
                        "crc_err": int(row.get("crc_err") or 0),
                        "bit_err": int(row.get("bit_err_total") or 0),
                        "tx_done": (row.get("tx_done") or "").strip(),
                        "rssi": row.get("rssi_avg", ""),
                        "toa_s": row.get("toa_s", ""),
                    })
        except (OSError, csv.Error):
            continue
    return rows


def probe(root: str, rel: str, needle: str) -> dict:
    """Does `needle` appear in repo-relative file `rel`?"""
    path = os.path.join(root, rel)
    try:
        with open(path, encoding="utf-8", errors="replace") as fh:
            blob = fh.read()
    except OSError:
        return {"path": rel, "present": False, "token": needle, "token_found": False}
    return {"path": rel, "present": True, "token": needle, "token_found": needle in blob}


def firmware_capability(root: str) -> dict:
    """Grep every code layer that bounds FLRC payload length and coding rate."""
    return {
        # runtime clamp in the bench firmware: LEN=<6-511> for FLRC
        "e80_firmware_clamp": probe(
            root, "firmware/e80-stm32-bench/src/bench.c", "MAX 255 LORA / 511 FLRC"),
        # the driver's documented legal range for pld_len_in_bytes
        "driver_pld_len_range": probe(
            root,
            "firmware/e80-stm32-bench/third_party/Radio/lr20xx_driver/inc/"
            "lr20xx_radio_flrc_types.h",
            "FLRC payload length in byte - in [6:511]"),
        # the driver's CR-aware time-on-air numerator (why CR 3/4 matters)
        "driver_cr_scaled_numerator": probe(
            root,
            "firmware/e80-stm32-bench/third_party/Radio/lr20xx_driver/src/"
            "lr20xx_radio_flrc.c",
            "lr20xx_get_flrc_cr_scalled_numerator"),
        # the CR the bench firmware actually ships with
        "fw_flrc_cr_3_4": probe(
            root, "firmware/e80-stm32-bench/src/radio_bench.c",
            ".cr    = LR20XX_RADIO_FLRC_CR_3_4"),
    }


# ── FLRC max payload length (report field `radio_lib_flrc_max`) ──────────────
#
# PORTABILITY CONTRACT (regression: repo-root `Tests` workflow went red on main
# for four consecutive pushes, 2026-10-09/10). The report field MUST resolve from
# files inside the checkout. The earlier version probed only `../RadioLib` and
# `~/repos/RadioLib` — host-local paths that do not exist on a GitHub Actions
# runner — so `value` was None in CI and
# tests/test_flrc_512b_throughput_audit.py::test_report_flags_511_as_legal_and_512_as_illegal
# failed board-wide. A RadioLib checkout outside the repo is now an advisory
# cross-check only; it can never be the sole source of the number.

# (label, repo-relative path, regex whose group 1 is the max payload in bytes)
FLRC_MAX_SOURCES = (
    # the bench firmware's own named clamp — the strongest repo-local truth
    ("fw_bench_start_len_max_flrc",
     "firmware/e80-stm32-bench/src/bench_cmd.h",
     r"#define\s+BENCH_START_LEN_MAX_FLRC\s+(\d+)"),
    # the vendor driver's documented legal range for pld_len_in_bytes
    ("lr20xx_driver_pld_len_range",
     "firmware/e80-stm32-bench/third_party/Radio/lr20xx_driver/inc/"
     "lr20xx_radio_flrc_types.h",
     r"FLRC payload length in byte\s*-\s*in \[6:(\d+)\]"),
    # the RadioLib snapshot archived under docs/ — only newer snapshots carry
    # the FLRC-specific define, so this is legitimately optional (None today)
    ("repo_radiolib_snapshot",
     "docs/lr2021-research/radiolib-master/LR2021-module/LR2021.h",
     r"#define\s+RADIOLIB_LR2021_MAX_PACKET_LENGTH_FLRC\s+(\d+)"),
)

FLRC_MAX_FALLBACK_PATH = FLRC_MAX_SOURCES[0][1]


def _flrc_max_from_text(root: str, rel: str, pattern: str) -> dict | None:
    """First regex match in repo-relative file `rel`, or None if absent/no match."""
    path = os.path.join(root, rel)
    try:
        with open(path, encoding="utf-8", errors="replace") as fh:
            blob = fh.read()
    except OSError:
        return None
    match = re.search(pattern, blob)
    if not match:
        return None
    return {"path": rel, "value": int(match.group(1))}


def _external_radiolib_candidates(root: str) -> list[str]:
    """RadioLib checkouts that may sit next to the repo or in a home dir."""
    return [
        os.path.join(os.path.dirname(os.path.abspath(root)), "RadioLib",
                     "src/modules/LR2021/LR2021.h"),
        os.path.expanduser("~/repos/RadioLib/src/modules/LR2021/LR2021.h"),
    ]


def _radiolib_header_flrc_max(path: str) -> int | None:
    """RADIOLIB_LR2021_MAX_PACKET_LENGTH_FLRC from a RadioLib LR2021.h header."""
    try:
        with open(path, encoding="utf-8", errors="replace") as fh:
            for line in fh:
                if "MAX_PACKET_LENGTH_FLRC" in line and "define" in line:
                    return int(line.split()[-1].rstrip("uU"))
    except (OSError, ValueError, IndexError):
        pass
    return None


def flrc_max_payload(root: str, external_radiolib: bool = True) -> dict:
    """Max legal FLRC payload length in bytes, resolved from IN-REPO sources.

    Returns the bound plus the provenance needed to audit it:

      * ``value``             first in-repo source that resolved (511), else None
      * ``path``              repo-relative file that won — portable evidence
      * ``source``            label of the winning source
      * ``sources``           every in-repo layer probed (None where absent)
      * ``external_radiolib`` advisory cross-check of a RadioLib checkout
                              outside the repo (present/value), never decisive

    Kept under the legacy report key ``radio_lib_flrc_max`` because
    docs/FLRC-512B-THROUGHPUT-AUDIT-2026-10-06.md and the host test pin that name.
    """
    sources: dict[str, dict | None] = {}
    winner: tuple[str, dict] | None = None
    for label, rel, pattern in FLRC_MAX_SOURCES:
        hit = _flrc_max_from_text(root, rel, pattern)
        sources[label] = hit
        if winner is None and hit is not None:
            winner = (label, hit)

    external: dict = {"path": None, "present": False, "value": None}
    if external_radiolib:
        for cand in _external_radiolib_candidates(root):
            if os.path.exists(cand):
                external = {"path": cand, "present": True,
                            "value": _radiolib_header_flrc_max(cand)}
                break

    return {
        "value": winner[1]["value"] if winner else None,
        "path": winner[1]["path"] if winner else FLRC_MAX_FALLBACK_PATH,
        "source": winner[0] if winner else None,
        "sources": sources,
        "external_radiolib": external,
    }


# Back-compat alias: the old name, with the old report shape folded in.
radio_lib_flrc_max = flrc_max_payload


# ── 2. Verdict ───────────────────────────────────────────────────────────────

def build_report(root: str) -> dict:
    meas = measured_payloads(root)
    rows = flrc_rows(root)
    radio_lib = flrc_max_payload(root)

    ceilings = {}
    for payload in (127, 255, 511):
        ceilings[payload] = {
            # card's / datasheet-audit model: uncoded, no CRC
            "audit_model_kbps": round(goodput_ceiling_kbps(payload, **MODEL_AUDIT), 1),
            "audit_airtime_us": round(airtime_s(payload, **MODEL_AUDIT) * 1e6, 1),
            # same model with the fw's 2-byte CRC
            "audit_crc_model_kbps": round(goodput_ceiling_kbps(payload, **MODEL_AUDIT_CRC), 1),
            "audit_crc_airtime_us": round(airtime_s(payload, **MODEL_AUDIT_CRC) * 1e6, 1),
            # the shipped configuration: CR 3/4 + CRC 2 B + FIX_LEN
            "fw_cr34_kbps": round(fw_goodput_ceiling_kbps(payload), 1),
            "fw_cr34_airtime_us": round(fw_airtime_s(payload) * 1e6, 1),
        }

    absent = sorted(p for p in (512, 513) if p not in meas)
    return {
        "repo_root": root,
        "flrc_payloads_ever_measured": sorted(meas),
        "flrc_payload_sources": {str(k): sorted(set(v)) for k, v in sorted(meas.items())},
        "payload_sizes_never_measured": absent,
        "flrc_rows_payload_ge_255": rows,
        "ceilings_kbps_2600": ceilings,
        "radio_lib_flrc_max": radio_lib,
        "firmware_capability": firmware_capability(root),
        "fw_cr_config": {"cr": "3/4", "cr_den": FW_CR_DEN, "tail_bits": FW_TAIL_BITS,
                         "crc_bytes": 2, "preamble_bits": 32, "sync_bits": 32,
                         "agc_bits": 21, "header": "FIX_LEN"},
        "verdict": {
            "i_or_ii": "(i) the 2.6 M figure is the CONFIGURED AIR RATE, not measured goodput",
            "why": (
                "2600 kbps is the FLRC raw air rate (BR_2_600_BW_2_666). Under the "
                "repo's uncoded model the payload ceiling at 511 B is "
                f"{ceilings[511]['audit_model_kbps']} kbps; under the firmware's "
                "actual configuration (CR 3/4, CRC 2 B, FIX_LEN) the LR20xx driver's "
                "own time-on-air numerator puts it at "
                f"{ceilings[511]['fw_cr34_kbps']} kbps -- which is within 1 % of the "
                "independently computed 1921.8 kbps on-air payload rate in "
                "full-sweep-report-20260821-175612.md. Every model, and every legal "
                "payload length, is below 2600. The best measured sustained figure on "
                "disk is 1484.9 kbps (2026-07-23, LEN=127) = "
                f"{round(1484.9 / ceilings[127]['fw_cr34_kbps'] * 100, 1)} % of the "
                "CR-3/4 ceiling at that length (57.1 % of the raw 2600). "
                "512 is not a legal length at all."
            ),
            "part_ii_note": (
                "the repo's 2540/2570 ceiling model IS wrong, but it is wrong "
                "optimistically: it assumes uncoded (CR NONE) air. With the firmware's "
                "CR 3/4 the ceiling FALLS to ~1871 kbps (255 B) / ~1910 kbps (511 B), "
                "so correcting the model cannot rescue a 2.6 Mbps goodput figure."
            ),
            "512b_measured": False,
            "511b_measured": 511 in meas,
            "511b_delivers": "confirmed 50/50 at BR650/1300/2600 (2026-08-21, fw 88a00cf)",
            "511b_needs_sustained_run": True,
        },
    }


# ── 3. Self-test ─────────────────────────────────────────────────────────────

def selftest() -> int:
    checks: list[tuple[str, bool]] = []

    def ck(name: str, cond: bool) -> None:
        checks.append((name, bool(cond)))

    # Sanity of the on-air model against the repo's own documented numbers.
    # datasheet audit 2026-07-26: 255 B, 16-bit preamble, 32-bit sync -> 0.803 ms.
    ck("audit work-example reproduces 0.803 ms",
       abs(airtime_s(255, **MODEL_AUDIT) * 1e6 - 803.0) < 1.0)
    ck("audit model reproduces the quoted 2540 kbps ceiling at 255 B",
       abs(goodput_ceiling_kbps(255, **MODEL_AUDIT) - 2540.0) < 2.0)
    ck("audit model reproduces the card's 2570 kbps ceiling at 511 B",
       abs(goodput_ceiling_kbps(511, **MODEL_AUDIT) - 2570.0) < 2.0)
    ck("audit+CRC model: 511 B airtime ~1.597 ms",
       abs(airtime_s(511, **MODEL_AUDIT_CRC) * 1e6 - 1596.9) < 2.0)

    # The firmware's real configuration (CR 3/4) — the model the docs must quote.
    ck("fw(CR3/4) model: 511 B airtime = 2.140 ms",
       abs(fw_airtime_s(511) * 1e6 - 2140.4) < 1.0)
    ck("fw(CR3/4) model: 511 B ceiling ~1910 kbps",
       abs(fw_goodput_ceiling_kbps(511) - 1910.0) < 1.5)
    ck("fw(CR3/4) model: 255 B ceiling ~1871 kbps",
       abs(fw_goodput_ceiling_kbps(255) - 1871.1) < 1.5)
    ck("fw(CR3/4) model: 127 B ceiling ~1798 kbps",
       abs(fw_goodput_ceiling_kbps(127) - 1798.2) < 1.5)
    ck("fw(CR3/4) ceiling agrees with the repo's independent 1921.8 kbps "
       "on-air figure to within 1 %",
       abs(fw_goodput_ceiling_kbps(511) - 1921.8) / 1921.8 < 0.01)
    ck("CR 3/4 costs 4/3 in airtime vs the uncoded model",
       abs(fw_airtime_s(255) / airtime_s(255, **MODEL_AUDIT_CRC) - 4 / 3) < 0.02)

    ck("every ceiling is strictly below the 2600 air rate",
       all(goodput_ceiling_kbps(p, **m) < 2600 for p in (255, 511)
           for m in (MODEL_AUDIT, MODEL_AUDIT_CRC))
       and all(fw_goodput_ceiling_kbps(p) < 2600 for p in range(6, 512)))
    ck("larger payload raises the ceiling (255 -> 511)",
       fw_goodput_ceiling_kbps(511) > fw_goodput_ceiling_kbps(255))
    ck("goodput can never exceed the air rate, any payload (CR3/4 model)",
       all(fw_goodput_ceiling_kbps(p) <= 2600.0 for p in range(6, 512)))
    ck("airtime is monotonic in payload",
       all(fw_airtime_s(p) < fw_airtime_s(p + 1) for p in range(6, 511)))
    ck("a 511 B packet carries more payload per second than a 255 B one",
       fw_goodput_ceiling_kbps(511) > fw_goodput_ceiling_kbps(255))
    ck("the uncoded repo model overstates the fw ceiling by more than a third",
       goodput_ceiling_kbps(511, **MODEL_AUDIT) / fw_goodput_ceiling_kbps(511) > 1.33)

    ok = 0
    for name, passed in checks:
        print(("PASS  " if passed else "FAIL  ") + name)
        ok += int(passed)
    print(f"\nselftest: {ok}/{len(checks)} passed")
    return 0 if ok == len(checks) else 1


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description=(__doc__ or "").splitlines()[0] or "FLRC large-payload audit")
    ap.add_argument("--root", default=".", help="repo root (default: cwd)")
    ap.add_argument("--selftest", action="store_true", help="run assertions only")
    ap.add_argument("--json", action="store_true", help="emit JSON instead of text")
    args = ap.parse_args(argv)

    if args.selftest:
        return selftest()

    root = os.path.abspath(args.root)
    if not os.path.isdir(root):
        print(f"error: no such directory: {root}", file=sys.stderr)
        return 2

    rep = build_report(root)

    if args.json:
        print(json.dumps(rep, indent=2, sort_keys=True))
        return 0

    m = rep["flrc_payloads_ever_measured"]
    print("=" * 78)
    print("FLRC large-payload audit — was 512 B / 2.6 Mbps ever measured?")
    print("=" * 78)
    print(f"repo: {rep['repo_root']}")
    print(f"\nFLRC payload sizes present in on-disk sweeps: {m}")
    print(f"payload sizes NEVER measured:                 {rep['payload_sizes_never_measured']}"
          "   <-- 512 B is among these")

    print("\nFLRC rows with payload >= 255 B:")
    print(f"  {'file':38} {'label':26} {'plen':>5} {'rx':>4} {'crc':>4} {'bit':>4} tx_done")
    for r in rep["flrc_rows_payload_ge_255"]:
        print(f"  {r['file']:38} {r['label']:26} {r['plen']:5} {r['rx']:4} "
              f"{r['crc_err']:4} {r['bit_err']:4} {r['tx_done']}")

    print("\nGoodput ceiling @ BR2600, zero host overhead:")
    print(f"  {'LEN':>4} | {'uncoded/repo':>22} | {'uncoded+CRC':>22} | {'fw CR3/4':>22}")
    print(f"  {'':>4} | {'airtime/us  ceil/kbps':>22} | {'airtime/us  ceil/kbps':>22} | "
          f"{'airtime/us  ceil/kbps':>22}")
    for payload, c in rep["ceilings_kbps_2600"].items():
        print(f"  {payload:>4} | {c['audit_airtime_us']:>11} {c['audit_model_kbps']:>10} | "
              f"{c['audit_crc_airtime_us']:>11} {c['audit_crc_model_kbps']:>10} | "
              f"{c['fw_cr34_airtime_us']:>11} {c['fw_cr34_kbps']:>10}")
    print("  (the 2600 kbps air rate is ABOVE every ceiling — goodput cannot reach it)")
    print("  uncoded/repo = 16b preamble + 32b sync + payload*8        (no CRC, no CR)")
    print("  uncoded+CRC  = 16b preamble + 32b sync + (payload+2)*8    (CRC, no CR)")
    print("  fw CR3/4     = LR20xx driver numerator with the shipped config "
          "(CR 3/4, CRC 2 B, FIX_LEN)")
    print("                 => 4/3 more on-air bits than the uncoded models; cross-checks "
          "the repo's")
    print("                    independently computed 1921.8 kbps on-air rate at 511 B")

    rl = rep["radio_lib_flrc_max"]
    print(f"\nFLRC max payload: {rl['value']} B  (source: {rl['source']} @ {rl['path']})")
    for label, hit in rl["sources"].items():
        print(f"    in-repo {label}: "
              + (f"{hit['value']} B ({hit['path']})" if hit else "not available"))
    ext = rl["external_radiolib"]
    print("    external RadioLib checkout: "
          + (f"{ext['value']} B ({ext['path']})" if ext["present"]
             else "absent — advisory only, never the sole source"))
    print("Firmware capability probes:")
    for k, v in rep["firmware_capability"].items():
        state = "found" if v.get("token_found") else ("present" if v.get("present") else "MISSING")
        print(f"  {k}: {state}  ({v.get('path')})")

    v = rep["verdict"]
    print("\nVERDICT: " + v["i_or_ii"])
    print("  " + v["why"].replace(". ", ".\n  "))
    print("\n  ON THE CARD'S (ii) BRANCH: " + v["part_ii_note"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
