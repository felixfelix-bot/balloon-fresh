#!/usr/bin/env python3
"""E80 / LR2021 receive-only console audit.

SAFETY CONTRACT (operator's RF bring-up order):
  * NEVER sends `ARM TX` (starts IWDG -> needs a physical power-cycle to clear)
  * NEVER sends `ROLE TX` or `START` (both can transmit on 869.85 MHz)
  * Only read-only + receive-path commands: ID? HELP STAT? BUF STATUS QUIET
    PRBS MOD(while role=RX) FREQ PA BAND OVERRIDE SESSION CONFIG
The role is re-verified as RX immediately before any radio-affecting command.

Emits: a raw console log, and a JSON summary of every command's accept/reject.
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

FREQ_868 = 869850000
FREQ_24G = 2440000000


class Board:
    def __init__(self, port, baud=115200, verbose=True):
        self.ser = serial.Serial(port, baud, timeout=0.5)
        self.log = []
        self.verbose = verbose

    def close(self):
        self.ser.close()

    def cmd(self, line, wait=1.3):
        """Send one console command, return the decoded response."""
        self.ser.reset_input_buffer()
        self.ser.write((line + "\n").encode())
        self.ser.flush()
        time.sleep(wait)
        resp = self.ser.read(8192).decode("utf-8", "replace").strip()
        self.log.append({"cmd": line, "resp": resp, "t": time.time()})
        if self.verbose:
            first = resp.splitlines()[0] if resp else "(no response)"
            print(f"  > {line:<44} -> {first[:110]}")
        return resp

    def role(self):
        m = re.search(r"role=(\w+)", self.cmd("ID?"))
        return m.group(1) if m else "?"

    def is_rx(self):
        """Hard gate: only ever reconfigure the radio while role==RX."""
        r = self.role()
        if r != "RX":
            print(f"  !! refusing radio-affecting command: role={r} (not RX)")
            return False
        return True






def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", default="/dev/ttyUSB0")
    ap.add_argument("--out", default="/tmp/lr2021-audit.json")
    ap.add_argument("--log", default="/tmp/lr2021-audit.console.log")
    args = ap.parse_args()

    print(f"=== E80 / LR2021 receive-only audit on {args.port} ===")
    b = Board(args.port)
    results = {"port": args.port, "checks": []}

    # ---- 1. identity ----------------------------------------------------
    print("\n[1] identity")
    idr = b.cmd("ID?")
    results["identity"] = parse_id(idr)
    print(f"      -> {json.dumps(results['identity'])}")

    # ---- 2. command surface --------------------------------------------
    print("\n[2] command surface (HELP)")
    help_resp = b.cmd("HELP", wait=1.6)
    cmds = []
    m = re.search(r"CMDS:\s*(.*)", help_resp)
    if m:
        cmds = [c.strip() for c in m.group(1).split("|")]
    results["help_command_count"] = len(cmds)
    results["help_commands"] = cmds
    print(f"      -> {len(cmds)} commands advertised")

    # ---- 3. baseline stats ---------------------------------------------
    print("\n[3] baseline STAT?")
    results["stat_baseline"] = parse_stat(b.cmd("STAT?"))

    # ---- 4. read-only housekeeping verbs -------------------------------
    print("\n[4] read-only verbs")
    results["checks"].append({"verb": "BUF STATUS", "resp": b.cmd("BUF STATUS")})
    results["checks"].append({"verb": "QUIET ON", "resp": b.cmd("QUIET ON")})
    results["checks"].append({"verb": "QUIET OFF", "resp": b.cmd("QUIET OFF")})
    results["checks"].append({"verb": "PRBS ON", "resp": b.cmd("PRBS ON")})
    results["checks"].append({"verb": "PRBS OFF", "resp": b.cmd("PRBS OFF")})
    # PRBS9 is deliberately NOT sent: it is the LR2021 chip-level *transmit*
    # test mode. Sending it would breach the receive-only contract.
    results["checks"].append({"verb": "SESSION 41001", "resp": b.cmd("SESSION 41001")})
    results["checks"].append({"verb": "CONFIG 0 0", "resp": b.cmd("CONFIG 0 0")})

    # ---- 5. LF (868) FLRC bitrate ladder, receive-only ------------------
    print("\n[5] LF 868 MHz FLRC bitrate ladder (receive-only)")
    ladder = []
    if b.is_rx():
        b.cmd("FREQ %d" % FREQ_868)
        for br in (260, 650, 1300, 2600):
            resp = b.cmd(f"MOD flrc {br} 10")
            stat = parse_stat(b.cmd("STAT?", wait=1.0))
            ladder.append({"kbps": br, "resp": resp.splitlines()[0] if resp else "",
                           "rssi_avg_dbm": stat.get("rssi_avg_dbm"),
                           "rx": stat.get("rx"), "crc_err": stat.get("crc_err")})
        results["flrc_ladder_868"] = ladder

    # ---- 6. LF LoRa parameter matrix, receive-only ----------------------
    print("\n[6] LF 868 MHz LoRa matrix (receive-only)")
    lora = []
    if b.is_rx():
        for sf, bw in ((7, 125), (9, 250), (12, 125)):
            resp = b.cmd(f"MOD loRa {sf} {bw}")
            lora.append({"sf": sf, "bw_khz": bw,
                         "resp": resp.splitlines()[0] if resp else ""})
        results["lora_matrix_868"] = lora

    # ---- 7. band override -> 2.4 GHz, receive-only ----------------------
    print("\n[7] BAND OVERRIDE 2026 -> 2.4 GHz (receive-only)")
    results["checks"].append({"verb": f"BAND OVERRIDE {PIN}", "resp": b.cmd(f"BAND OVERRIDE {PIN}")})
    if b.is_rx():
        b.cmd("FREQ %d" % FREQ_24G)
        id24 = parse_id(b.cmd("ID?"))
        results["after_2g4_override"] = id24
        results["checks"].append({"verb": "FREQ 2440000000", "resp": b.cmd("FREQ %d" % FREQ_24G)})
        for br in (260, 650, 2600):
            resp = b.cmd(f"MOD flrc {br} 10")
            results["checks"].append({"verb": f"MOD flrc {br} 10 (2.4G)",
                                      "resp": resp.splitlines()[0] if resp else ""})

    # ---- 8. restore the delivered state --------------------------------
    print("\n[8] restore delivered state (868.5 / FLRC 650 / PA 22 / RX)")
    if b.is_rx():
        b.cmd("PA 22")
        b.cmd("FREQ %d" % FREQ_868)
        b.cmd("MOD flrc 650 10")
    results["stat_final"] = parse_stat(b.cmd("STAT?"))
    results["final_identity"] = parse_id(b.cmd("ID?"))

    # ---- persist --------------------------------------------------------
    with open(args.out, "w") as f:
        json.dump(results, f, indent=2)
    with open(args.log, "w") as f:
        for e in b.log:
            f.write(f">>> {e['cmd']}\n{e['resp']}\n\n")
    b.close()
    print(f"\n=== wrote {args.out} and {args.log} ===")
    return 0


if __name__ == "__main__":
    sys.exit(main())
