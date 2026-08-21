#!/usr/bin/env python3
"""e80_sweep_full.py — E80-to-E80 FULL parameter sweep (LoRa + FLRC + PA + LEN + FREQ).

Both boards: E80 STM32 bench, fw=88a00cf (T5a tip: pcrc16 24th PKT field).
PKT format (25 fields): [0]PKT [1]session [2]config [3]replicate [4]pkt_idx
[5]ts_ms [6]rssi_dbm [7]snr_db [8]crc_ok [9]bit_err [10]? [11]freq_hz [12]mod
[13]sf/br [14]bw [15]cr [16]pa_dbm [17]len [18-23]0 [24]pcrc16

Firmware parameter space (probed 2026-08-21):
  LoRa: SF5-12 x BW125/250/500, PA 0-10 dBm (indoor cap)
  FLRC: BR {260,325,520,650,1040,1300,2080,2600} kbps x pa 0-10
  FREQ: 863-870 MHz
  LEN: 6-511 bytes, GAP us, SESSION/CONFIG tagging

Robustness:
  - Auto-detect CH340 UART ports (they swap between reboots)
  - Radio-based TX/RX identification handshake
  - SWD reset via 'reset halt; resume' (reset run leaves UART dead)
  - SWD reset retry up to 2x on unresponsive board
  - Adaptive GAP = max(10ms, 1.2*airtime + 5ms)
  - Incremental CSV append after every config (partial data survives)
"""

import serial, time, math, os, sys, subprocess, csv, glob
from datetime import datetime

# ---- Static config ----
PROBE_TX = "148757200D2D1425"   # SWD probe of TX board
PROBE_RX = "203584200D2D0D42"   # SWD probe of RX board
BAUD = 115200
NPKTS = 50
FW_DIR = os.path.expanduser("~/repos/balloon-e80bench/firmware/e80-stm32-bench")
OUT_DIR = os.path.abspath(os.path.join(FW_DIR, "..", ".."))

LORA_SFS = [5, 6, 7, 8, 9, 10, 11, 12]
LORA_BWS = [125, 250, 500]
FLRC_BRS = [260, 325, 520, 650, 1040, 1300, 2080, 2600]  # kbps (1000 invalid)
FLRC_PAS = [0, 1, 3, 5, 7, 10]
PA_SWEEP = [0, 3, 6, 10]
LEN_SWEEP = [16, 64, 128, 255, 511]
FREQ_SWEEP = [863000000, 865000000, 868000000, 869525000, 870000000]
DEFAULT_FREQ = 868000000


def lora_airtime_s(sf, bw_khz, plen):
    """Standard LoRa airtime: preamble 8, CR 4/5, explicit hdr, CRC on."""
    bw = bw_khz * 1000
    t_sym = (2 ** sf) / bw
    num = 8 * plen - 4 * sf + 28 + 16
    den = 4 * (sf - 2 * 0)
    payload_symb = 8 + max(math.ceil(num / den) * (1 + 4), 0)
    return (8 + 4.25 + payload_symb) * t_sym


def flrc_airtime_s(br_kbps, plen):
    """FLRC rough airtime: preamble+sync ~7B, 4/5 FEC, CRC."""
    return (plen + 7) * 8 / (br_kbps * 1000) * 1.5 + 0.001


def swd_reset(probe_serial):
    subprocess.run(
        ["/usr/bin/openocd", "-f", "interface/cmsis-dap.cfg",
         "-f", "target/stm32f1x.cfg",
         "-c", f"transport select swd; adapter serial {probe_serial}; "
               f"init; reset halt; resume; exit"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        timeout=30, cwd=FW_DIR)
    time.sleep(2.0)


def find_ch340_ports():
    """Return /dev/ttyUSB* ports that are CH340 (E80 console bridges)."""
    ports = []
    for dev in sorted(glob.glob("/dev/ttyUSB*")):
        try:
            r = subprocess.run(["udevadm", "info", "-q", "property", "-n", dev],
                               capture_output=True, text=True, timeout=5)
            if "CH340" in r.stdout:
                ports.append(dev)
        except Exception:
            pass
    return ports


def readline(ser, timeout=3.0):
    deadline = time.monotonic() + timeout
    buf = bytearray()
    while time.monotonic() < deadline:
        chunk = ser.read(256)
        if chunk:
            buf += chunk
            while b"\n" in buf:
                line, buf = buf.split(b"\n", 1)
                txt = line.rstrip(b"\r").decode(errors="replace").strip()
                if txt:
                    return txt
    return None


def cmd(ser, line, timeout=5.0):
    for _ in range(2):
        ser.reset_input_buffer()
        ser.write((line + "\r\n").encode())
        r = readline(ser, timeout)
        if r:
            return r
        time.sleep(0.5)
    return None


def drain_lines(ser, seconds):
    out = []
    deadline = time.monotonic() + seconds
    leftover = bytearray()
    while time.monotonic() < deadline:
        chunk = ser.read(1024)
        if chunk:
            leftover += chunk
            while b"\n" in leftover:
                line, leftover = leftover.split(b"\n", 1)
                txt = line.rstrip(b"\r").decode(errors="replace").strip()
                if txt:
                    out.append(txt)
    return out


def identify_boards():
    """Find CH340 ports, then identify which is TX board (via probe reset)."""
    ports = find_ch340_ports()
    if len(ports) != 2:
        raise RuntimeError(f"expected 2 CH340 ports, found {ports}")
    a, b = serial.Serial(ports[0], BAUD, timeout=0.1), serial.Serial(ports[1], BAUD, timeout=0.1)

    # Radio handshake: A=RX, B=TX; whoever logs PKT is RX board
    for s in (a, b):
        cmd(s, "ROLE RX")
    cmd(b, "MOD LORA 8 125"); cmd(b, f"FREQ {DEFAULT_FREQ}"); cmd(b, "PA 10")
    cmd(a, "MOD LORA 8 125"); cmd(a, f"FREQ {DEFAULT_FREQ}"); cmd(a, "PA 10")
    cmd(b, "ROLE TX"); cmd(b, "ARM TX")
    a.reset_input_buffer()
    b.write(b"START N=2 LEN=32 GAP=10000\r\n")
    time.sleep(4)
    a_lines = drain_lines(a, 1)
    a.close(); b.close()
    if any(l.startswith("PKT,") for l in a_lines):
        return ports[0], ports[1]  # A=RX, B=TX
    # Try the other assignment
    a, b = serial.Serial(ports[0], BAUD, timeout=0.1), serial.Serial(ports[1], BAUD, timeout=0.1)
    for s in (a, b):
        cmd(s, "ROLE RX")
    cmd(a, "MOD LORA 8 125"); cmd(a, f"FREQ {DEFAULT_FREQ}"); cmd(a, "PA 10")
    cmd(b, "MOD LORA 8 125"); cmd(b, f"FREQ {DEFAULT_FREQ}"); cmd(b, "PA 10")
    cmd(a, "ROLE TX"); cmd(a, "ARM TX")
    b.reset_input_buffer()
    a.write(b"START N=2 LEN=32 GAP=10000\r\n")
    time.sleep(4)
    b_lines = drain_lines(b, 1)
    a.close(); b.close()
    if any(l.startswith("PKT,") for l in b_lines):
        return ports[1], ports[0]  # B=RX, A=TX
    raise RuntimeError("radio identification handshake failed on both assignments")


def open_boards():
    tx_port, rx_port = identify_boards()
    return tx_port, rx_port, serial.Serial(tx_port, BAUD, timeout=0.1), serial.Serial(rx_port, BAUD, timeout=0.1)


def parse_pkt(line):
    if not line.startswith("PKT,"):
        return None
    p = line.strip().split(",")
    if len(p) < 18:
        return None
    try:
        return {
            "session": int(p[1]), "config": int(p[2]), "replicate": int(p[3]),
            "idx": int(p[4]), "ts_ms": int(p[5]),
            "rssi": float(p[6]), "snr": float(p[7]), "crc_ok": int(p[8]),
            "bit_err": int(p[9]), "freq": int(p[11]), "mod": p[12],
            "sf": int(p[13]), "bw": int(p[14]), "pa": int(p[16]),
            "pkt_len": int(p[17]),
            "pcrc16": int(p[24]) if len(p) > 24 else None,
        }
    except (ValueError, IndexError):
        return None


def parse_stat(stat):
    d = {}
    for tok in stat.split()[1:]:
        if "=" in tok:
            k, v = tok.split("=", 1)
            try:
                d[k] = float(v) if "." in v else int(v)
            except ValueError:
                d[k] = v
    return d


def ensure_alive(ser, probe, label):
    """If board unresponsive, SWD-reset it (up to 2 retries)."""
    for attempt in range(3):
        r = cmd(ser, "ID?")
        if r and "E80BENCH" in r:
            return True
        print(f"    {label} unresponsive (attempt {attempt+1}), SWD reset", flush=True)
        swd_reset(probe)
        time.sleep(1.0)
    return False


# Firmware caps (ERR LEN): 255 B max in LoRa (SX1262 limit), 511 B max in FLRC
LEN_CAP = {"lora": 255, "flrc": 511}


def run_config(idx, cfg, tx, rx, session_id, tx_port, rx_port):
    """cfg: dict with keys: mod, sf|br, bw, pa, freq, plen, gap, label"""
    mod = cfg["mod"]
    if cfg["plen"] > LEN_CAP.get(mod, 255):
        return {
            "idx": idx, "label": cfg["label"], "mod": mod,
            "sf": cfg.get("sf", ""), "bw": cfg.get("bw", ""),
            "br": cfg.get("br", ""), "pa": cfg["pa"], "freq": cfg["freq"],
            "plen": cfg["plen"], "gap_us": cfg["gap"], "toa_s": 0,
            "rx_pkts": 0, "crc_err": 0, "rssi_avg": None, "rssi_min": None,
            "rssi_max": None, "snr_avg": None, "snr_min": None,
            "bit_err_total": 0, "tx_done": False,
            "start_reply": f"INVALID CONFIG: LEN>{LEN_CAP[mod]} for {mod}",
            "pkts": [], "invalid": True,
        }
    # SWD reset both to clear state
    swd_reset(PROBE_TX)
    swd_reset(PROBE_RX)
    # Re-open ports (SWD reset can invalidate USB state? no — ports stay, but reopen to be safe)
    tx.port, rx.port = tx_port, rx_port

    if not ensure_alive(tx, PROBE_TX, "TX") or not ensure_alive(rx, PROBE_RX, "RX"):
        raise RuntimeError("board unresponsive after retries")

    # Tag session/config in firmware
    cmd(tx, f"SESSION {session_id}")
    cmd(rx, f"SESSION {session_id}")
    cmd(tx, f"CONFIG {idx} 1")
    cmd(rx, f"CONFIG {idx} 1")

    # Radio config — RX first
    if mod == "lora":
        m = f"MOD LORA {cfg['sf']} {cfg['bw']}"
    else:
        m = f"MOD FLRC {cfg['br']} {cfg['pa']}"
    for s, label in [(rx, "RX"), (tx, "TX")]:
        r = cmd(s, m)
        if not r or not r.startswith("OK MOD"):
            raise RuntimeError(f"{label} MOD: {r!r}")
        if mod == "lora":
            r = cmd(s, f"PA {cfg['pa']}")
            if not r or not r.startswith("OK PA"):
                raise RuntimeError(f"{label} PA: {r!r}")
        r = cmd(s, f"FREQ {cfg['freq']}")
        if not r or not r.startswith("OK FREQ"):
            raise RuntimeError(f"{label} FREQ: {r!r}")

    r = cmd(rx, "ROLE RX")
    if not r or not r.startswith("OK ROLE RX"):
        raise RuntimeError(f"RX ROLE: {r!r}")
    r = cmd(tx, "ROLE TX")
    if not r or not r.startswith("OK ROLE TX"):
        raise RuntimeError(f"TX ROLE: {r!r}")
    r = cmd(tx, "ARM TX")
    if not r or not r.startswith("OK ARMED"):
        raise RuntimeError(f"TX ARM: {r!r}")

    # Burst
    rx.reset_input_buffer()
    tx.write(f"START N={NPKTS} LEN={cfg['plen']} GAP={cfg['gap']}\r\n".encode())
    start_reply = readline(tx, 3.0)

    # FIX-T1: validate the START reply before waiting on the burst. The
    # firmware refuses illegal configs synchronously (e.g. 'ERR LEN (MAX 255
    # LORA / 511 FLRC)', 'ERR NOT ARMED ...'); a None reply means the board
    # never answered. Record the refusal in error= and move on to the next
    # config instead of stalling in drain_lines() for the full burst window.
    if not start_reply or not start_reply.startswith("OK START"):
        err = start_reply if start_reply else "no reply to START (timeout)"
        return {
            "idx": idx, "label": cfg["label"], "mod": mod,
            "sf": cfg.get("sf", ""), "bw": cfg.get("bw", ""),
            "br": cfg.get("br", ""), "pa": cfg["pa"], "freq": cfg["freq"],
            "plen": cfg["plen"], "gap_us": cfg["gap"], "toa_s": 0,
            "rx_pkts": 0, "crc_err": 0,
            "rssi_avg": None, "rssi_min": None, "rssi_max": None,
            "snr_avg": None, "snr_min": None,
            "bit_err_total": 0, "tx_done": False,
            "start_reply": start_reply, "pkts": [], "error": err,
        }

    if mod == "lora":
        toa = lora_airtime_s(cfg["sf"], cfg["bw"], cfg["plen"])
    else:
        toa = flrc_airtime_s(cfg["br"], cfg["plen"])
    wait_s = NPKTS * (toa + cfg["gap"] / 1e6) + 8

    tx_lines = drain_lines(tx, wait_s)
    rx_lines = drain_lines(rx, 5)
    tx_done = any("TX DONE" in l for l in tx_lines)

    stat = cmd(rx, "STAT?")
    sd = parse_stat(stat) if stat else {}

    pkts = [p for p in (parse_pkt(l) for l in rx_lines) if p is not None]
    rssi = [p["rssi"] for p in pkts]
    snr = [p["snr"] for p in pkts]

    return {
        "idx": idx, "label": cfg["label"], "mod": mod,
        "sf": cfg.get("sf", ""), "bw": cfg.get("bw", ""),
        "br": cfg.get("br", ""), "pa": cfg["pa"], "freq": cfg["freq"],
        "plen": cfg["plen"], "gap_us": cfg["gap"], "toa_s": round(toa, 3),
        "rx_pkts": len(pkts), "crc_err": sd.get("crc_err", 0),
        "rssi_avg": round(sum(rssi)/len(rssi), 1) if rssi else None,
        "rssi_min": round(min(rssi), 1) if rssi else None,
        "rssi_max": round(max(rssi), 1) if rssi else None,
        "snr_avg": round(sum(snr)/len(snr), 1) if snr else None,
        "snr_min": round(min(snr), 1) if snr else None,
        "bit_err_total": sum(p["bit_err"] for p in pkts),
        "tx_done": tx_done, "start_reply": start_reply, "pkts": pkts,
    }


def build_configs():
    cfgs = []
    # A. LoRa SF x BW matrix @ PA10, LEN64, 868MHz
    for bw in LORA_BWS:
        for sf in LORA_SFS:
            toa = lora_airtime_s(sf, bw, 64)
            gap = max(10000, int(1.2 * toa * 1e6) + 5000)
            cfgs.append(dict(mod="lora", sf=sf, bw=bw, pa=10, freq=DEFAULT_FREQ,
                             plen=64, gap=gap, label=f"SF{sf} BW{bw} PA10"))
    # B. LoRa PA sweep @ SF8 BW125 LEN64
    for pa in PA_SWEEP:
        if pa == 10:
            continue  # in matrix
        toa = lora_airtime_s(8, 125, 64)
        gap = max(10000, int(1.2 * toa * 1e6) + 5000)
        cfgs.append(dict(mod="lora", sf=8, bw=125, pa=pa, freq=DEFAULT_FREQ,
                         plen=64, gap=gap, label=f"SF8 BW125 PA{pa}"))
    # C. LEN sweep @ SF8 BW125 PA10 (LoRa firmware cap: 255 B — LEN_SWEEP's
    # 511 entry is FLRC-only, skip it here rather than rely on run_config's
    # ERR-LEN fail-fast to catch it at bench time)
    for plen in LEN_SWEEP:
        if plen == 64:
            continue  # in matrix
        if plen > LEN_CAP["lora"]:
            continue  # firmware refuses LEN>255 in LoRa (uint8 pkt param)
        toa = lora_airtime_s(8, 125, plen)
        gap = max(10000, int(1.2 * toa * 1e6) + 5000)
        cfgs.append(dict(mod="lora", sf=8, bw=125, pa=10, freq=DEFAULT_FREQ,
                         plen=plen, gap=gap, label=f"SF8 BW125 PA10 L{plen}"))
    # D. FLRC BR sweep @ pa5
    for br in FLRC_BRS:
        cfgs.append(dict(mod="flrc", br=br, pa=5, freq=DEFAULT_FREQ,
                         plen=64, gap=10000, label=f"FLRC {br}k pa5"))
    # E. FLRC pa sweep @ BR650
    for pa in FLRC_PAS:
        if pa == 5:
            continue  # in D
        cfgs.append(dict(mod="flrc", br=650, pa=pa, freq=DEFAULT_FREQ,
                         plen=64, gap=10000, label=f"FLRC 650k pa{pa}"))
    # G. FLRC LEN sweep @ BR650 pa5 868 MHz — 511 B is legal in FLRC only
    #    (fw cap 'ERR LEN (MAX 255 LORA / 511 FLRC)'); probes the L255
    #    boundary region flagged in docs/rca-fix-plan-20260821.md
    for plen in LEN_SWEEP:
        if plen == 64:
            continue  # in D (FLRC BR sweep row br=650)
        toa = flrc_airtime_s(650, plen)
        gap = max(10000, int(1.2 * toa * 1e6) + 5000)
        cfgs.append(dict(mod="flrc", br=650, pa=5, freq=DEFAULT_FREQ,
                         plen=plen, gap=gap, label=f"FLRC 650k pa5 L{plen}"))
    # F. FREQ sweep @ SF8 BW125 PA10 (868 in matrix)
    for f in FREQ_SWEEP:
        if f == DEFAULT_FREQ:
            continue
        toa = lora_airtime_s(8, 125, 64)
        gap = max(10000, int(1.2 * toa * 1e6) + 5000)
        cfgs.append(dict(mod="lora", sf=8, bw=125, pa=10, freq=f,
                         plen=64, gap=gap, label=f"SF8 BW125 @ {f/1e6:.3f}MHz"))
    return cfgs


SUMMARY_FIELDS = ["idx", "label", "mod", "sf", "bw", "br", "pa", "freq", "plen",
                  "gap_us", "toa_s", "rx_pkts", "crc_err", "rssi_avg", "rssi_min",
                  "rssi_max", "snr_avg", "snr_min", "bit_err_total", "tx_done", "error"]
PKT_FIELDS = ["idx", "label", "pkt_idx", "session", "config", "replicate",
              "ts_ms", "rssi_dbm", "snr_db", "crc_ok", "bit_err", "pcrc16"]


def main():
    ts = datetime.now()
    session_id = int(ts.strftime("%y%m%d%H%M"))
    print(f"E80 FULL Sweep — {ts.isoformat()}  session={session_id}", flush=True)
    print(f"Probes: TX={PROBE_TX} RX={PROBE_RX}  {NPKTS} pkts/config", flush=True)

    tx_port, rx_port, tx, rx = open_boards()
    print(f"Ports: TX={tx_port} RX={rx_port}", flush=True)

    cfgs = build_configs()
    print(f"Configs: {len(cfgs)}", flush=True)
    print("=" * 90, flush=True)

    ts_str = ts.strftime("%Y%m%d-%H%M%S")
    sum_path = os.path.join(OUT_DIR, f"full-sweep-summary-{ts_str}.csv")
    pkt_path = os.path.join(OUT_DIR, f"full-sweep-pkts-{ts_str}.csv")
    sum_f = open(sum_path, "w", newline="")
    sum_w = csv.writer(sum_f); sum_w.writerow(SUMMARY_FIELDS); sum_f.flush()
    pkt_f = open(pkt_path, "w", newline="")
    pkt_w = csv.writer(pkt_f); pkt_w.writerow(PKT_FIELDS); pkt_f.flush()

    results = []
    for i, cfg in enumerate(cfgs):
        print(f"[{i+1}/{len(cfgs)}] {cfg['label']} ...", end=" ", flush=True)
        rec = {k: cfg.get(k, "") for k in ("mod", "sf", "bw", "br", "pa", "freq",
                                           "plen", "gap", "label")}
        rec.update(idx=i, error="")
        try:
            r = run_config(i, cfg, tx, rx, session_id, tx_port, rx_port)
            results.append(r)
            row = [r.get(k, "") for k in SUMMARY_FIELDS[:-1]] + [r.get("error", "")]
            print(f"rx={r['rx_pkts']}/{NPKTS} rssi={r['rssi_avg']} snr={r['snr_avg']} "
                  f"crc={r['crc_err']} done={r['tx_done']}", flush=True)
            for p in r["pkts"]:
                pkt_w.writerow([i, cfg["label"], p["idx"], p["session"], p["config"],
                                p["replicate"], p["ts_ms"], p["rssi"], p["snr"],
                                p["crc_ok"], p["bit_err"], p["pcrc16"]])
            pkt_f.flush()
        except Exception as e:
            print(f"FAIL: {e}", flush=True)
            row = [rec.get(k, "") for k in SUMMARY_FIELDS[:-1]] + [str(e)[:60]]
        sum_w.writerow(row)
        sum_f.flush()

    sum_f.close(); pkt_f.close()

    # Markdown report
    md_path = os.path.join(OUT_DIR, f"full-sweep-report-{ts_str}.md")
    with open(md_path, "w") as f:
        f.write(f"# E80-to-E80 FULL Parameter Sweep — {ts.date()}\n\n")
        f.write(f"**Date:** {ts.isoformat()}\n\n")
        f.write(f"**Firmware:** 88a00cf (T5a: pcrc16 + NVIC race fix) — both boards\n\n")
        f.write(f"**Session tag:** {session_id}  \n**Packets per config:** {NPKTS}  ")
        f.write(f"**Setup:** bench, boards ~30 cm apart, whip antennas\n\n")
        f.write(f"**SWD probes:** TX {PROBE_TX}, RX {PROBE_RX}\n\n")
        f.write(f"**Serial ports (this run):** TX {tx_port}, RX {rx_port} ")
        f.write("(CH340 USB bridges swap between reboots — auto-detected at runtime)\n\n")
        f.write("## Results\n\n")
        f.write("| # | Config | Mod | RX | % | RSSI avg (dBm) | SNR avg (dB) | CRC err | Bit err | TX done |\n")
        f.write("|---|---|---|---|---|---|---|---|---|---|\n")
        for r in results:
            pct = 100 * r["rx_pkts"] / NPKTS
            f.write(f"| {r['idx']+1} | {r['label']} | {r['mod']} | {r['rx_pkts']}/{NPKTS} "
                    f"| {pct:.0f}% | {r['rssi_avg'] if r['rssi_avg'] is not None else '-'} "
                    f"| {r['snr_avg'] if r['snr_avg'] is not None else '-'} "
                    f"| {r['crc_err']} | {r['bit_err_total']} | {'✓' if r['tx_done'] else '✗'} |\n")
        f.write(f"\n## Parameter space covered\n\n")
        f.write(f"- LoRa: SF{min(LORA_SFS)}-{max(LORA_SFS)} x BW{LORA_BWS} (PA 10 dBm)\n")
        f.write(f"- LoRa PA: {PA_SWEEP} dBm @ SF8 BW125 (indoor cap 0-10 dBm)\n")
        f.write(f"- Payload: {LEN_SWEEP} B @ SF8 BW125 (LoRa capped at 255 B by fw)\n")
        f.write(f"- FLRC BR: {FLRC_BRS} kbps @ pa 5\n")
        f.write(f"- FLRC pa: {FLRC_PAS} @ BR 650 kbps\n")
        f.write("- FLRC payload: 16/64/128/255/511 B @ BR650 pa5 (511 legal in FLRC only)\n")
        f.write(f"- Frequency: {[f/1e6 for f in FREQ_SWEEP]} MHz @ SF8 BW125\n\n")
        f.write("## Files\n\n")
        f.write(f"- Summary CSV: `full-sweep-summary-{ts_str}.csv`\n")
        f.write(f"- Per-packet CSV: `full-sweep-pkts-{ts_str}.csv`\n")
        f.write(f"- Script: `firmware/e80-stm32-bench/tools/e80_sweep_full.py`\n\n")
        f.write("## Notes\n\n")
        f.write("- GAP adaptive: max(10 ms, 1.2×airtime + 5 ms) — prevents RX overrun at SF11/12\n")
        f.write("- SWD reset (`reset halt; resume`) between configs clears all radio state\n")
        f.write("- PA capped 0–10 dBm by firmware (EU indoor); `POWER MODE OUTDOOR <pin>` unlock exists\n")
        f.write("- LEN 6–511 enforced; FREQ 863–870 MHz enforced (EU SRD)\n")
    print(f"\nSummary CSV: {sum_path}")
    print(f"Per-packet CSV: {pkt_path}")
    print(f"Markdown report: {md_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
