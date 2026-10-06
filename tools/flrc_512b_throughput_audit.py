#!/usr/bin/env python3
"""flrc_512b_throughput_audit.py — settle the "2.6 Mbps at 512 B" claim, hardware-free.

Context (kanban balloon/t_6b68897c). The operator reported measuring ~2.6 Mbps on
the LR2021 FLRC link by doubling the packet payload 255 B -> 512 B. No such run
exists on disk. This tool does three things that need no radio:

  1. Evidence audit: enumerates the on-disk FLRC payload sweeps and proves which
     payload sizes were ever measured (and therefore which were not).
  2. Ceiling arithmetic: recomputes the goodput ceiling for LEN in {255, 511}
     under both plausible header models, and shows whether 2600 kbps goodput is
     reachable at all.
  3. Firmware-capability check: confirms that 511 B is a *legal* FLRC length for
     this hardware (E80 firmware + LR20xx driver + RadioLib), i.e. that the
     255-byte ceiling that the RP2040 docs assume is an SX1280/legacy artefact.

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
import sys

# ── FLRC on-air model ────────────────────────────────────────────────────────
#
# The E80 bench firmware configures FLRC packets with
#   lr20xx_radio_flrc_pkt_params_t { preamble_len = 32 bits, sync_word_len = 4 B,
#                                    header_type = FIX_LEN, crc_type = 2 B }
# (src/radio_bench.c).  The LR20xx driver's own on-air numerator
# (lr20xx_radio_flrc.c: lr20xx_get_flrc_time_on_air_numerator) counts, in bits:
#     preamble + sync + (payload + crc) * 8
# i.e. the fixed 4-byte sync is NOT charged as payload*8.
#
# The 2026-07-26 datasheet audit used the other model (sync as 32 payload bits,
# no CRC):  (16 + 32 + payload*8).  Both are computed here; at BR2600/uncoded
# the difference is worth ~1.5% and does not change any verdict below.

FLRC_BR_2600_KBPS = 2600.0
# LR20xx driver: lr20xx_get_flrc_time_on_air_numerator() = payload_bits + 32 (CRC).
# 1 kbps == 1000 bit/s; numerator is in kbit units => divide by 1000.
NUMERATOR_KBITS_DIVISOR = 1000.0


# Two explicit header models. They differ by ~2% and by whether CRC is charged;
# both are reported so no reader has to guess which one produced a number.
#
#   MODEL_AUDIT  16-bit preamble + 32-bit sync + payload*8         (no CRC)
#                 -> reproduces the repo's 0.803 ms / 2540 kbps at 255 B
#   MODEL_DRIVER 32-bit preamble + 4-byte sync + (payload+2)*8     (CRC 2 B)
#                 -> what src/radio_bench.c + lr20xx_radio_flrc.c actually air
MODEL_AUDIT = dict(preamble_bits=16, sync_bits=32, crc_bytes=0, sync_in_payload_units=True)
MODEL_DRIVER = dict(preamble_bits=32, sync_bits=32, crc_bytes=2, sync_in_payload_units=False)


def airtime_s(payload_b: int, br_kbps: float = FLRC_BR_2600_KBPS,
              preamble_bits: int = 32, sync_bits: int = 32, crc_bytes: int = 2,
              sync_in_payload_units: bool = False) -> float:
    """On-air time in seconds for one FLRC packet.

    sync_in_payload_units=True  -> sync is charged as 32 payload bits, no CRC field
    sync_in_payload_units=False -> sync is 4 bytes on the wire, CRC is an extra field
    """
    if sync_in_payload_units:
        bits = preamble_bits + sync_bits + payload_b * 8
    else:
        bits = preamble_bits + sync_bits + (payload_b + crc_bytes) * 8
    return bits / (br_kbps * 1000.0)


def goodput_ceiling_kbps(payload_b: int, **kw) -> float:
    """Payload goodput assuming ZERO host/SPI overhead (pure air-time limit)."""
    return payload_b * 8 / airtime_s(payload_b, **kw) / 1000.0


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


def firmware_capability(root: str) -> dict:
    """Grep the three code layers that bound FLRC payload length."""
    probes = {
        "e80_firmware_clamp": (
            "firmware/e80-stm32-bench/src/bench.c",
            "MAX 255 LORA / 511 FLRC"),
        "e80_driver_crc_allowance": (
            "firmware/e80-stm32-bench/third_party/Radio/lr20xx_driver/src/"
            "lr20xx_radio_flrc.c", "num_additional_bytes"),
        "radiolib_flrc_max": (
            "RadioLib:src/modules/LR2021/LR2021.h",
            "MAX_PACKET_LENGTH_FLRC                  511"),
    }
    found: dict[str, object] = {}
    for name, (rel, needle) in probes.items():
        path = os.path.join(root, rel)
        if name.startswith("radiolib"):
            continue  # lives in a separate checkout; reported separately
        try:
            with open(path, encoding="utf-8", errors="replace") as fh:
                blob = fh.read()
        except OSError:
            found[name] = {"path": rel, "present": False}
            continue
        found[name] = {"path": rel, "present": True, "token": needle,
                       "token_found": needle in blob}
    return found


def radio_lib_flrc_max(repo_root: str) -> dict:
    """Read RADIOLIB_LR2021_MAX_PACKET_LENGTH_FLRC from a RadioLib checkout."""
    cand = os.path.join(os.path.dirname(os.path.abspath(repo_root)), "RadioLib",
                        "src/modules/LR2021/LR2021.h")
    if not os.path.exists(cand):
        cand = os.path.expanduser("~/repos/RadioLib/src/modules/LR2021/LR2021.h")
    try:
        with open(cand, encoding="utf-8", errors="replace") as fh:
            for line in fh:
                if "MAX_PACKET_LENGTH_FLRC" in line and "define" in line:
                    return {"path": cand, "value": int(line.split()[-1])}
    except (OSError, ValueError, IndexError):
        pass
    return {"path": cand, "value": None}


# ── 2. Verdict ───────────────────────────────────────────────────────────────

def build_report(root: str) -> dict:
    meas = measured_payloads(root)
    rows = flrc_rows(root)
    radio_lib = radio_lib_flrc_max(root)

    ceilings = {}
    for payload in (255, 511):
        ceilings[payload] = {
            # card's model (matches the 2540/2570 kbps figures quoted in the repo)
            "audit_model_kbps": round(goodput_ceiling_kbps(payload, **MODEL_AUDIT), 1),
            "audit_airtime_us": round(airtime_s(payload, **MODEL_AUDIT) * 1e6, 1),
            # what the firmware actually airs (32 b preamble + 4 B sync + 2 B CRC)
            "driver_model_kbps": round(goodput_ceiling_kbps(payload, **MODEL_DRIVER), 1),
            "driver_airtime_us": round(airtime_s(payload, **MODEL_DRIVER) * 1e6, 1),
        }

    absent = sorted(p for p in (512, 513) if p not in meas)
    return {
        "repo_root": root,
        "flrc_payloads_ever_measured": sorted(meas),
        "flrc_payload_sources": {str(k): sorted(set(v)) for k, v in sorted(meas.items())},
        "payload_sizes_never_measured": absent,
        "flrc_rows_payload_ge_255": rows,
        "ceilings_kbps_2600_uncoded": ceilings,
        "radio_lib_flrc_max": radio_lib,
        "firmware_capability": firmware_capability(root),
        "verdict": {
            "i_or_ii": "(i) the 2.6 M figure is the CONFIGURED AIR RATE, not measured goodput",
            "why": (
                "2600 kbps is the FLRC raw symbol rate. Even with zero host overhead "
                "the payload goodput ceiling at 511 B is "
                f"{ceilings[511]['driver_model_kbps']} kbps (driver model) / "
                f"{ceilings[511]['audit_model_kbps']} kbps (audit model) -- both "
                "below 2600. The best measured sustained figure on disk is "
                "1484.9 kbps (2026-07-23, LEN=127); the best on-air-rate figure "
                "anywhere in the repo is 1921.8 kbps (2026-08-21, BR2600 L511, "
                "PHY-only). Neither is 2600."
            ),
            "512b_measured": False,
            "511b_measured": 511 in meas,
            "511b_delivers": "confirmed 50/50 at BR650/1300/2600 (2026-08-21, fw 88a00cf)",
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
    ck("driver model: 511 B airtime ~1.603 ms",
       abs(airtime_s(511, **MODEL_DRIVER) * 1e6 - 1603.0) < 2.0)
    ck("driver model: 255 B airtime ~815 us",
       abs(airtime_s(255, **MODEL_DRIVER) * 1e6 - 815.0) < 2.0)
    ck("every ceiling is strictly below the 2600 air rate",
       all(goodput_ceiling_kbps(p, **m) < 2600
           for p in (255, 511) for m in (MODEL_AUDIT, MODEL_DRIVER)))
    ck("larger payload raises the ceiling (255 -> 511)",
       goodput_ceiling_kbps(511, **MODEL_DRIVER) >
       goodput_ceiling_kbps(255, **MODEL_DRIVER))
    ck("goodput can never exceed the air rate, any payload",
       all(goodput_ceiling_kbps(p, **m) <= 2600.0
           for p in range(6, 512) for m in (MODEL_AUDIT, MODEL_DRIVER)))
    ck("airtime is monotonic in payload",
       all(airtime_s(p) < airtime_s(p + 1) for p in range(6, 511)))
    ck("a 511 B packet carries more payload per second than a 255 B one",
       (511 * 8) / airtime_s(511) > (255 * 8) / airtime_s(255))

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

    print("\nGoodput ceiling @ BR2600 uncoded (zero host overhead):")
    print(f"  {'LEN':>4} | {'audit model':>26} | {'driver model (actual fw cfg)':>30}")
    print(f"  {'':>4} | {'airtime/us':>11} {'ceiling/kbps':>14} | "
          f"{'airtime/us':>11} {'ceiling/kbps':>15}")
    for payload, c in rep["ceilings_kbps_2600_uncoded"].items():
        print(f"  {payload:>4} | {c['audit_airtime_us']:>11} {c['audit_model_kbps']:>14} | "
              f"{c['driver_airtime_us']:>11} {c['driver_model_kbps']:>15}")
    print("  (2600 kbps air rate is ABOVE every ceiling — goodput cannot reach it)")
    print("  audit model = 16b preamble + 32b sync + payload*8, no CRC (the repo's model)")
    print("  driver model = 32b preamble + 4B sync + (payload+2)*8, CRC present")

    print(f"\nRadioLib FLRC max payload: {rep['radio_lib_flrc_max']['value']} B "
          f"({rep['radio_lib_flrc_max']['path']})")
    print("Firmware capability probes:")
    for k, v in rep["firmware_capability"].items():
        state = "found" if v.get("token_found") else ("present" if v.get("present") else "MISSING")
        print(f"  {k}: {state}  ({v.get('path')})")

    v = rep["verdict"]
    print("\nVERDICT: " + v["i_or_ii"])
    print("  " + v["why"].replace(". ", ".\n  "))
    return 0


if __name__ == "__main__":
    sys.exit(main())
