#!/usr/bin/env python3
"""Re-runnable acceptance gates for the DERIVED flight schematic (ADR-028 / PCB-S5a).

The PCB netlist is the source of truth; this script proves the schematic mirrors
it, and that nothing in the schematic is invented.  Every gate prints its own
numbers and the script exits non-zero if any gate fails.

  GATE 0  schematic LOADS:      kicad-cli sch erc            (exit 0)
  GATE 1  ERC has 0 errors:     kicad-cli sch erc --exit-code-violations
                                (warnings parsed out of the report, listed)
  GATE 2  net parity BOTH WAYS: every schematic net exists in the PCB netlist
                                and every PCB net exists in the schematic
  GATE 3  node parity BOTH WAYS: per net, the (ref,pin) sets are equal
  GATE 4  netless pads:         27 netless pads, each classified
                                INTENTIONAL_NC / DECLARED_GAP / unnamed
                                mechanical, 0 unclassified (ties into PCB-S0b)
  GATE 5  pad coverage:         every numbered PCB pad has a symbol pin
                                (build_flight_sch.py exits 2 otherwise)

Run:  python3 check_sch_gates.py
"""
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import build_flight_sch as B  # noqa: E402

SCH = B.OUT_SCH
NETLIST = os.path.join(HERE, "v_c3_flight.net")
ERC_RPT = os.path.join(HERE, "v_c3_flight-erc.rpt")

fails = []


def sh(cmd):
    return subprocess.run(cmd, cwd=HERE, capture_output=True, text=True)


def blocks(text, prefix):
    i = 0
    while True:
        i = text.find(prefix, i)
        if i < 0:
            return
        d, j = 0, i
        while j < len(text):
            if text[j] == "(":
                d += 1
            elif text[j] == ")":
                d -= 1
                if d == 0:
                    yield text[i:j + 1]
                    break
            j += 1
        i = j + 1


def nodes(block):
    return set(re.findall(r'\(ref "([^"]+)"\) \(pin "([^"]+)"\)', block))


# ---------------------------------------------------------------- GATE 0 + 1
print("== GATE 0: schematic loads (kicad-cli sch erc) ==")
r0 = sh(["kicad-cli", "sch", "erc", SCH])
print("   exit=%d  %s" % (r0.returncode,
                         (r0.stdout or r0.stderr).strip().splitlines()[-1]
                         if (r0.stdout or r0.stderr).strip() else ""))
if r0.returncode != 0:
    fails.append("GATE 0: erc failed to load the schematic (exit %d)" % r0.returncode)

r1 = sh(["kicad-cli", "sch", "erc", "--exit-code-violations", SCH])
report = open(ERC_RPT, errors="replace").read() if os.path.exists(ERC_RPT) else ""
kinds = re.findall(r"^\[([a-z_]+)\]", report, re.M)
sev = re.findall(r"^\s*; (error|warning)$", report, re.M)
errors = sev.count("error")
warnings = sev.count("warning")
print("== GATE 1: ERC severity ==")
print("   strict exit=%d  errors=%d warnings=%d  kinds=%s"
      % (r1.returncode, errors, warnings, sorted(set(kinds))))
if errors:
    fails.append("GATE 1: %d ERC errors" % errors)
if r1.returncode == 0:
    print("   (strict exit 0 = zero violations of any severity)")
elif warnings:
    print("   NOTE: %d warning(s) only: %s" % (warnings, sorted(set(kinds))))

# ---------------------------------------------------------------- netlist
rl = sh(["kicad-cli", "sch", "export", "netlist", "-o", NETLIST, SCH])
if rl.returncode != 0:
    fails.append("netlist export failed (exit %d): %s" % (rl.returncode, rl.stderr))
    print("\n".join(fails))
    sys.exit(1)
net_txt = open(NETLIST, errors="replace").read()

sch_nets = {}
for blk in blocks(net_txt, "    (net "):
    nm = re.search(r'\(name "([^"]+)"\)', blk)
    if not nm:
        continue
    # KiCad prefixes local-label nets with the sheet path ("/EN"); the PCB stores
    # the bare name.  Normalise the prefix away before comparing.
    sch_nets[nm.group(1).lstrip("/")] = {n for n in nodes(blk)
                                         if not n[0].startswith("#")}

pcb_nets = {}
for fp in B.parse_pcb(B.PCB):
    for pad in fp["pads"]:
        if pad["num"] and pad["net"]:
            pcb_nets.setdefault(pad["net"], set()).add((fp["ref"], pad["num"]))

only_sch = {n: sch_nets[n] for n in sorted(set(sch_nets) - set(pcb_nets))}
only_pcb = {n: pcb_nets[n] for n in sorted(set(pcb_nets) - set(sch_nets))}
print("== GATE 2: net parity ==")
print("   nets: schematic=%d pcb=%d  only-in-schematic=%s  only-in-pcb=%s"
      % (len(sch_nets), len(pcb_nets), sorted(only_sch) or "none",
         sorted(only_pcb) or "none"))
if only_sch or only_pcb:
    fails.append("GATE 2: net sets differ (sch-only=%s pcb-only=%s)"
                 % (sorted(only_sch), sorted(only_pcb)))

mismatch = []
for net in sorted(set(sch_nets) & set(pcb_nets)):
    if sch_nets[net] != pcb_nets[net]:
        mismatch.append((net, sorted(pcb_nets[net] - sch_nets[net]),
                         sorted(sch_nets[net] - pcb_nets[net])))
sch_nodes = sum(len(v) for v in sch_nets.values())
pcb_nodes = sum(len(v) for v in pcb_nets.values())
print("== GATE 3: node (ref,pin) parity ==")
print("   nodes: schematic=%d pcb=%d  nets-with-differing-nodes=%d"
      % (sch_nodes, pcb_nodes, len(mismatch)))
for net, miss, extra in mismatch[:10]:
    print("     %s: pcb-only=%s sch-only=%s" % (net, miss, extra))
if mismatch:
    fails.append("GATE 3: node mismatch on %d net(s)" % len(mismatch))

# ---------------------------------------------------------------- netless pads
netless = []
for fp in B.parse_pcb(B.PCB):
    for pad in fp["pads"]:
        if not pad["net"]:
            netless.append((fp["ref"], pad["num"]))
unnamed = [k for k in netless if k[1] == ""]
intentional = [k for k in netless if k in B.INTENTIONAL_NC]
declared = [k for k in netless if k in B.DECLARED_GAP]
unclassified = [k for k in netless if k[1] and k not in B.INTENTIONAL_NC
                and k not in B.DECLARED_GAP]
print("== GATE 4: netless pads classified ==")
print("   total=%d  unnamed-mechanical=%d  INTENTIONAL=%d  DECLARED_GAP=%d"
      "  unclassified=%d" % (len(netless), len(unnamed), len(intentional),
                             len(declared), len(unclassified)))
if unclassified:
    print("   UNCLASSIFIED:", unclassified)
    fails.append("GATE 4: %d unclassified netless pads" % len(unclassified))

print("== GATE 5: pad coverage ==")
r5 = subprocess.run([sys.executable, os.path.join(HERE, "build_flight_sch.py")],
                    cwd=HERE, capture_output=True, text=True)
print("   build_flight_sch.py exit=%d (2 = a pad has no symbol pin)"
      % r5.returncode)
if r5.returncode != 0:
    fails.append("GATE 5: pad coverage failure:\n" + r5.stdout[-500:])

print()
if fails:
    print("GATES FAILED:")
    for f in fails:
        print("  -", f)
    sys.exit(1)
print("ALL GATES PASS")
