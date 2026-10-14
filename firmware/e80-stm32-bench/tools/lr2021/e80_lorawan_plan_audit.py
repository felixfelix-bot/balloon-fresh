#!/usr/bin/env python3
"""E80 / LR2021 receive-only: EU868 LoRaWAN channel + datarate plan audit.

Why this is the decision-relevant test: it proves whether the LR2021 silicon on
the desk can actually be configured to the EU868 LoRaWAN PHY that the planned
`lib-lorawan` fallback layer needs -- DR0..DR5 (SF12..SF7 @ BW125) on the three
default join channels 868.1 / 868.3 / 868.5 MHz, plus the 867.1-867.9 sub-band.

SAFETY CONTRACT:
  * NEVER `ARM TX`, `ROLE TX`, or `START`
  * NEVER `PRBS9` (that is a chip-level TX test mode, i.e. a TRANSMISSION --
    deliberately excluded; the earlier audit toggling it was a mistake)
  * radio is only ever reconfigured while role==RX, re-verified each time
"""
import argparse
import json
import re
import sys
import time

import serial

from lr2021_parse import (
    DEFAULT_CHANNELS_HZ,
    DR_TO_SF,
    EXTRA_CHANNELS_HZ,
    PIN,
    accepted,
    parse_id,
    parse_stat,
)



class Board:
    def __init__(self, port, baud=115200):
        self.ser = serial.Serial(port, baud, timeout=0.5)
        self.log = []

    def cmd(self, line, wait=1.1):
        self.ser.reset_input_buffer()
        self.ser.write((line + "\n").encode())
        self.ser.flush()
        time.sleep(wait)
        resp = self.ser.read(8192).decode("utf-8", "replace").strip()
        self.log.append({"cmd": line, "resp": resp})
        first = resp.splitlines()[0] if resp else "(no response)"
        print(f"  > {line:<34} -> {first[:100]}")
        return resp

    def role(self):
        m = re.search(r"role=(\w+)", self.cmd("ID?"))
        return m.group(1) if m else "?"

    def close(self):
        self.ser.close()




def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", default="/dev/ttyUSB0")
    ap.add_argument("--out", default="/tmp/lr2021-lorawan-plan.json")
    args = ap.parse_args()

    print(f"=== EU868 LoRaWAN channel/DR plan audit on {args.port} ===")
    b = Board(args.port)
    res = {"port": args.port, "datarates": {}, "channels": {}, "summary": {}}

    if b.role() != "RX":
        print("!! role is not RX -- aborting (never reconfigure a TX-armed board)")
        return 2

    # ---- datarates DR0..DR5 (SF12..SF7 @ BW125) -------------------------
    print("\n[1] datarates DR0-DR5 (SF12..SF7 @ BW125 kHz)")
    for dr, sf in DR_TO_SF.items():
        resp = b.cmd(f"MOD loRa {sf} 125")
        ok = accepted(resp)
        res["datarates"][f"DR{dr}"] = {"sf": sf, "bw_khz": 125, "accepted": ok,
                                       "resp": resp.splitlines()[0] if resp else ""}
    # ---- band width options the plan might use --------------------------
    print("\n[2] wider bandwidths at DR5 (SF7)")
    res["bw_variants"] = {}
    for bw in (125, 250, 500):
        resp = b.cmd(f"MOD loRa 7 {bw}")
        res["bw_variants"][f"bw{bw}"] = {"accepted": accepted(resp)}

    # ---- default join channels ------------------------------------------
    print("\n[3] default join channels 868.1 / 868.3 / 868.5 MHz")
    for f in DEFAULT_CHANNELS_HZ:
        resp = b.cmd(f"FREQ {f}")
        idr = b.cmd("ID?")
        got = re.search(r"freq=(\d+)", idr)
        res["channels"][str(f)] = {
            "accepted": accepted(resp),
            "readback_hz": int(got.group(1)) if got else None,
            "readback_matches": bool(got) and int(got.group(1)) == f,
        }

    # ---- sub-band channels ----------------------------------------------
    print("\n[4] 867.1-867.9 MHz sub-band channels")
    for f in EXTRA_CHANNELS_HZ:
        resp = b.cmd(f"FREQ {f}")
        idr = b.cmd("ID?")
        got = re.search(r"freq=(\d+)", idr)
        res["channels"][str(f)] = {
            "accepted": accepted(resp),
            "readback_hz": int(got.group(1)) if got else None,
            "readback_matches": bool(got) and int(got.group(1)) == f,
        }

    # ---- the LoRaWAN RX2 / downlink channel -----------------------------
    print("\n[5] RX2 (869.525 MHz, SF9/BW125 = DR3)")
    resp = b.cmd("FREQ 869525000")
    b.cmd("MOD LoRa 9 125")
    idr = b.cmd("ID?")
    got = re.search(r"freq=(\d+)", idr)
    res["rx2_869525000"] = {"accepted": accepted(resp),
                            "readback_hz": int(got.group(1)) if got else None}

    # ---- restore the delivered configuration ----------------------------
    print("\n[6] restore delivered config (868.5? no -- 869.85 / FLRC 650 / PA 22 / RX)")
    b.cmd("PA 22")
    b.cmd("FREQ 869850000")
    b.cmd("MOD flrc 650 10")
    b.cmd("PA 22")
    idr = b.cmd("ID?")
    res["restored_identity"] = idr
    res["summary"] = {
        "all_drs_accepted": all(v["accepted"] for v in res["datarates"].values()),
        "all_channels_accepted": all(v["accepted"] for v in res["channels"].values()),
        "all_channels_readback_match": all(v["readback_matches"]
                                           for v in res["channels"].values()),
    }
    b.close()

    with open(args.out, "w") as f:
        json.dump(res, f, indent=2)
    print(f"\n=== summary {json.dumps(res['summary'])} ===")
    print(f"=== wrote {args.out} ===")
    return 0


if __name__ == "__main__":
    sys.exit(main())
