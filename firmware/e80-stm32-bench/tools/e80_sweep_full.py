#!/usr/bin/env python3
"""e80_sweep_full.py — E80-to-E80 FULL parameter sweep (LoRa + FLRC + PA + LEN + FREQ).

Both boards: E80 STM32 bench, fw=0561b29 (2.4 GHz band support: HF PA/RX
path >= 1.6 GHz, BAND OVERRIDE range 410-2483.5 MHz, console 2,000,000 8N1).
PKT format (25 fields): [0]PKT [1]session [2]config [3]replicate [4]pkt_idx
[5]ts_ms [6]rssi_dbm [7]snr_db [8]crc_ok [9]bit_err [10]? [11]freq_hz [12]mod
[13]sf/br [14]bw [15]cr [16]pa_dbm [17]len [18-23]0 [24]pcrc16

Firmware parameter space (probed 2026-08-21/22):
  LoRa: SF5-12 x BW125/250/500, PA 0-10 dBm (indoor cap)
  FLRC: BR {260,325,520,650,1040,1300,2080,2600} kbps x pa 0-10
  FREQ: 863-870 MHz (868 default); 2400-2483.5 MHz with BAND OVERRIDE
  LEN: 6-255 LoRa / 6-511 FLRC, GAP us, SESSION/CONFIG tagging
Bands: dual-band sweep — 868 MHz sections (A..G2) + 2.4 GHz sections
  (2G4 matrix/PA/LEN/BR/PA/FREQ @ 2440 MHz center, HF radio path).

Robustness:
  - Auto-detect CH340 UART ports (they swap between reboots)
  - Radio-based TX/RX identification handshake
  - SWD reset via 'reset halt; resume' (reset run leaves UART dead)
  - SWD reset retry up to 2x on unresponsive board
  - Adaptive GAP = max(10ms, 1.2*airtime + 5ms)
  - Incremental CSV append after every config (partial data survives)
"""

try:
    import serial                # only needed for board I/O: the config/baud/
except ImportError:              # preflight logic must import in a bare
    serial = None                # host-test environment (no pyserial)
import time, math, os, re, sys, subprocess, csv, glob
from datetime import datetime

# ---- Static config ----
PROBE_TX = "148757200D2D1425"   # SWD probe of TX board
PROBE_RX = "203584200D2D0D42"   # SWD probe of RX board
PROBE_SERIALS = {"TX": PROBE_TX, "RX": PROBE_RX}
NPKTS = 50
FW_DIR = os.path.expanduser("~/repos/balloon-e80bench/firmware/e80-stm32-bench")
OUT_DIR = os.path.abspath(os.path.join(FW_DIR, "..", ".."))
OUT_STEM = "full-sweep-results-2g4"  # dual-band output file stem

# ---- Console baud: single source of truth = the firmware header ----
# The console baud MUST equal the firmware's compiled E80_BENCH_BAUD_DEFAULT.
# A mismatch is a SILENT failure: every command is dropped, the rows come back
# "no reply" and the CSV reads as RF death instead of a wrong baud. History
# (2026-09-16): main's tool was pinned to 2 Mbaud for the unmerged 2g4-sweep fw
# while main's firmware default is 115200 — the tool could not talk to any
# board flashed from main.
FW_HEADER = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                         "..", "src", "main.h")
LEGACY_BAUD = 2000000           # fw 0561b29 / feat/2g4-sweep console default


def fw_default_baud(header_path=None):
    """Parse `E80_BENCH_BAUD_DEFAULT` out of the firmware header (or None)."""
    path = header_path or FW_HEADER
    try:
        with open(path) as fh:
            text = fh.read()
    except OSError:
        return None
    m = re.search(r"#define\s+E80_BENCH_BAUD_DEFAULT\s+(\d+)U?", text)
    return int(m.group(1)) if m else None


def resolve_baud(env=None, header_path=None):
    """E80_BAUD override > firmware header default > legacy 2 Mbaud."""
    environ = os.environ if env is None else env
    raw = environ.get("E80_BAUD")
    if raw:
        try:
            return int(raw)
        except (TypeError, ValueError):
            raise ValueError(f"E80_BAUD must be an integer (got {raw!r})")
    return fw_default_baud(header_path) or LEGACY_BAUD


BAUD = resolve_baud()

LORA_SFS = [5, 6, 7, 8, 9, 10, 11, 12]
LORA_BWS = [125, 250, 500]
FLRC_BRS = [260, 325, 520, 650, 1040, 1300, 2080, 2600]  # kbps (1000 invalid)
FLRC_PAS = [0, 1, 3, 5, 7, 10]
PA_SWEEP = [0, 3, 6, 10]
LEN_SWEEP = [16, 64, 128, 255, 511]
FREQ_SWEEP = [863000000, 865000000, 868000000, 869525000, 870000000]
DEFAULT_FREQ = 868000000

# 2.4 GHz ISM band (fw 0561b29: HF PA/RX path, needs BAND OVERRIDE).
FREQ_2G4_SWEEP = [2400000000, 2420000000, 2440000000, 2460000000, 2480000000]
DEFAULT_FREQ_2G4 = 2440000000

# EU SRD band without override (fw bench.c BENCH_CMD_FREQ gate).
BAND_MIN_HZ = 863000000
BAND_MAX_HZ = 870000000
# 'BAND OVERRIDE <pin>' widens FREQ acceptance to 410-2483.5 MHz (fw main.h).
BAND_OVERRIDE_PIN = 2026

# FLRC large-packet coverage — the FIX-T6 acceptance set. 511 = FLRC fw max
# (legal ONLY in FLRC; the LR2021 LoRa length field is uint8 -> 255).
FLRC_LEN_MATRIX = [16, 64, 128, 192, 255, 256, 300, 384, 448, 511]
# G2 interaction rows: does a 384/511 B payload hold at higher bit rates?
FLRC_LEN_BR_INTERACTIONS = ((1300, 384), (1300, 511), (2600, 511))
# FIX-T6 phase (b): the BUG 3 boundary bisect around the 255 B FLRC CRC failure.
FLRC_BISECT_BR = 1300
FLRC_BISECT_PA = 10
FLRC_BISECT_LENS = [253, 254, 255, 256, 257]


def open_serial(port, baud=None, timeout=0.1):
    """Open a console port — the ONE seam tests patch to fake a board."""
    if serial is None:
        raise RuntimeError("pyserial is required for board I/O "
                           "(python3 -m pip install pyserial)")
    return serial.Serial(port, baud or BAUD, timeout=timeout)


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
    a, b = open_serial(ports[0]), open_serial(ports[1])

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
    a, b = open_serial(ports[0]), open_serial(ports[1])
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
    return tx_port, rx_port, open_serial(tx_port), open_serial(rx_port)


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


def arm_and_stream(tx, rx, cfg, npkts, toa=None, wait_extra=8):
    """Reusable arm+stream burst phase — shared by run_config and campaign.

    Sends START, waits for burst completion, drains TX+RX lines.
    Returns dict: start_reply, tx_lines, rx_lines, toa, wait_s.

    If toa is None, computes it from cfg (mod/sf/br/bw/plen).
    """
    mod = cfg["mod"]
    if toa is None:
        if mod == "lora":
            toa = lora_airtime_s(cfg["sf"], cfg["bw"], cfg["plen"])
        else:
            toa = flrc_airtime_s(cfg["br"], cfg["plen"])
    wait_s = npkts * (toa + cfg["gap"] / 1e6) + wait_extra
    rx.reset_input_buffer()
    tx.write(f"START N={npkts} LEN={cfg['plen']} GAP={cfg['gap']}\r\n".encode())
    start_reply = readline(tx, 3.0)
    tx_lines = drain_lines(tx, wait_s)
    rx_lines = drain_lines(rx, 5)
    return {
        "start_reply": start_reply,
        "tx_lines": tx_lines,
        "rx_lines": rx_lines,
        "toa": toa,
        "wait_s": wait_s,
    }


def run_config(idx, cfg, tx, rx, session_id, tx_port, rx_port, npkts=NPKTS):
    """cfg: dict with keys: mod, sf|br, bw, pa, freq, plen, gap, label

    npkts: packets per burst (default NPKTS=50; adaptive campaign passes
    SPRT n_cap for early-stop capable bursts).
    """
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
            "dur_s": 0, "cfg_t_start": "", "cfg_t_end": "",
        }
    # SWD reset both to clear state
    swd_reset(PROBE_TX)
    swd_reset(PROBE_RX)
    # Wall-clock timing: from SWD reset done to last packet drain
    t_cfg_start = time.monotonic()
    cfg_t_start_iso = datetime.now().isoformat()
    # Re-open ports (SWD reset can invalidate USB state? no — ports stay, but reopen to be safe)
    tx.port, rx.port = tx_port, rx_port

    if not ensure_alive(tx, PROBE_TX, "TX") or not ensure_alive(rx, PROBE_RX, "RX"):
        raise RuntimeError("board unresponsive after retries")

    # Tag session/config in firmware
    cmd(tx, f"SESSION {session_id}")
    cmd(rx, f"SESSION {session_id}")
    cmd(tx, f"CONFIG {idx} 1")
    cmd(rx, f"CONFIG {idx} 1")

    # Band override for out-of-EU-SRD frequencies (2.4 GHz ISM sections).
    # band_override is RAM-resident in the fw and every config starts with a
    # SWD reset of both boards, so it must be (re-)armed per config — sending
    # it "once at the start of the section" would NOT survive the next reset.
    needs_override = not (BAND_MIN_HZ <= cfg["freq"] <= BAND_MAX_HZ)
    if needs_override:
        for s, label in [(rx, "RX"), (tx, "TX")]:
            r = cmd(s, f"BAND OVERRIDE {BAND_OVERRIDE_PIN}")
            if not r or not r.startswith("OK BAND OVERRIDE"):
                raise RuntimeError(f"{label} BAND OVERRIDE: {r!r}")

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

    # Burst — arm_and_stream lets campaign controller reuse this phase
    burst = arm_and_stream(tx, rx, cfg, npkts, toa=None)
    tx_lines = burst["tx_lines"]
    rx_lines = burst["rx_lines"]
    start_reply = burst["start_reply"]
    toa = burst["toa"]
    t_cfg_end = time.monotonic()
    cfg_t_end_iso = datetime.now().isoformat()
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
        "dur_s": round(t_cfg_end - t_cfg_start, 3),
        "cfg_t_start": cfg_t_start_iso, "cfg_t_end": cfg_t_end_iso,
        "rx_pkts": len(pkts), "crc_err": sd.get("crc_err", 0),
        "rssi_avg": round(sum(rssi)/len(rssi), 1) if rssi else None,
        "rssi_min": round(min(rssi), 1) if rssi else None,
        "rssi_max": round(max(rssi), 1) if rssi else None,
        "snr_avg": round(sum(snr)/len(snr), 1) if snr else None,
        "snr_min": round(min(snr), 1) if snr else None,
        "bit_err_total": sum(p["bit_err"] for p in pkts),
        "tx_done": tx_done, "start_reply": start_reply, "pkts": pkts,
    }


def build_flrc_br_configs():
    """Section D — FLRC BR sweep @pa5 plen64 868 MHz (the 8 accepted bit rates)."""
    return [dict(mod="flrc", br=br, pa=5, freq=DEFAULT_FREQ, plen=64, gap=10000,
                 label=f"FLRC {br}k pa5") for br in FLRC_BRS]


def build_flrc_len_configs():
    """Section G — FLRC large-packet LEN matrix @BR650 pa5 (gap 40 ms: console
    headroom for 511 B PKT lines @115200 baud, drops watch item)."""
    return [dict(mod="flrc", br=650, pa=5, freq=DEFAULT_FREQ, plen=plen, gap=40000,
                 label=f"FLRC 650k pa5 L{plen}") for plen in FLRC_LEN_MATRIX]


def build_flrc_len_br_configs():
    """Section G2 — large-packet x BR interaction (does 384/511 hold at higher BR?)."""
    return [dict(mod="flrc", br=br, pa=5, freq=DEFAULT_FREQ, plen=plen, gap=40000,
                 label=f"FLRC {br}k pa5 L{plen}") for br, plen in FLRC_LEN_BR_INTERACTIONS]


def _build_all_configs():
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
    # C. LEN sweep @ SF8 BW125 PA10
    for plen in LEN_SWEEP:
        if plen == 64:
            continue  # in matrix
        if plen > LEN_CAP["lora"]:
            continue  # LR2021 LoRa 8-bit length field: max 255 (L511 is
                      # FLRC-only; generates misleading 100% PER in LoRa)
        toa = lora_airtime_s(8, 125, plen)
        gap = max(10000, int(1.2 * toa * 1e6) + 5000)
        cfgs.append(dict(mod="lora", sf=8, bw=125, pa=10, freq=DEFAULT_FREQ,
                         plen=plen, gap=gap, label=f"SF8 BW125 PA10 L{plen}"))
    # D. FLRC BR sweep @ pa5
    cfgs.extend(build_flrc_br_configs())
    # E. FLRC pa sweep @ BR650
    for pa in FLRC_PAS:
        if pa == 5:
            continue  # in D
        cfgs.append(dict(mod="flrc", br=650, pa=pa, freq=DEFAULT_FREQ,
                         plen=64, gap=10000, label=f"FLRC 650k pa{pa}"))
    # F. FREQ sweep @ SF8 BW125 PA10 (868 in matrix)
    for f in FREQ_SWEEP:
        if f == DEFAULT_FREQ:
            continue
        toa = lora_airtime_s(8, 125, 64)
        gap = max(10000, int(1.2 * toa * 1e6) + 5000)
        cfgs.append(dict(mod="lora", sf=8, bw=125, pa=10, freq=f,
                         plen=64, gap=gap, label=f"SF8 BW125 @ {f/1e6:.3f}MHz"))
    # G. FLRC LEN matrix @ BR650 pa5 — large-packet coverage (operator priority
    #    2026-08-21: >256 B sizes thoroughly covered; 511 = FLRC fw max, legal
    #    ONLY in FLRC — LoRa silicon cap is 255). gap 40 ms: console pressure
    #    headroom for 511 B PKT lines @ 115200 baud (drops watch item).
    cfgs.extend(build_flrc_len_configs())
    # G2. large-packet x BR interaction (does 511 hold at higher BR?)
    cfgs.extend(build_flrc_len_br_configs())
    # ================= 2.4 GHz ISM band (fw 0561b29, BAND OVERRIDE) =================
    # HF PA/RX radio path (fw switches at >= 1.6 GHz). run_config arms
    # 'BAND OVERRIDE 2026' on both boards per config (flag dies on SWD reset).
    # G-2G4. LoRa SF x BW matrix @ 2440 MHz PA10 LEN64 (24 configs)
    for bw in LORA_BWS:
        for sf in LORA_SFS:
            toa = lora_airtime_s(sf, bw, 64)
            gap = max(10000, int(1.2 * toa * 1e6) + 5000)
            cfgs.append(dict(mod="lora", sf=sf, bw=bw, pa=10,
                             freq=DEFAULT_FREQ_2G4, plen=64, gap=gap,
                             label=f"2G4 SF{sf} BW{bw} PA10"))
    # H-2G4. LoRa PA sweep @ SF8 BW125 2440 MHz (4 configs; PA10 replicates
    # the matrix center for cross-section consistency check)
    for pa in PA_SWEEP:
        toa = lora_airtime_s(8, 125, 64)
        gap = max(10000, int(1.2 * toa * 1e6) + 5000)
        cfgs.append(dict(mod="lora", sf=8, bw=125, pa=pa,
                         freq=DEFAULT_FREQ_2G4, plen=64, gap=gap,
                         label=f"2G4 SF8 BW125 PA{pa}"))
    # I-2G4. LoRa LEN sweep @ SF8 BW125 PA10 2440 MHz. L511 filtered: the
    # LR2021 LoRa 8-bit length field caps at 255 bytes — L511 in LoRa is
    # untestable and was previously showing as misleading 100% PER.
    for plen in LEN_SWEEP:
        if plen > LEN_CAP["lora"]:
            continue
        toa = lora_airtime_s(8, 125, plen)
        gap = max(10000, int(1.2 * toa * 1e6) + 5000)
        cfgs.append(dict(mod="lora", sf=8, bw=125, pa=10,
                         freq=DEFAULT_FREQ_2G4, plen=plen, gap=gap,
                         label=f"2G4 SF8 BW125 PA10 L{plen}"))
    # J-2G4. FLRC BR sweep @ 2440 MHz pa5 (8 configs). gap floor 10 ms holds
    # for the shortest airtime (2600k: ~1.3 ms for 64 B) — min gap is the
    # binding constraint, exactly as on 868 MHz.
    for br in FLRC_BRS:
        cfgs.append(dict(mod="flrc", br=br, pa=5, freq=DEFAULT_FREQ_2G4,
                         plen=64, gap=10000, label=f"2G4 FLRC {br}k pa5"))
    # K-2G4. FLRC PA sweep @ 650k 2440 MHz (6 configs; pa5 replicates J)
    for pa in FLRC_PAS:
        cfgs.append(dict(mod="flrc", br=650, pa=pa, freq=DEFAULT_FREQ_2G4,
                         plen=64, gap=10000, label=f"2G4 FLRC 650k pa{pa}"))
    # L-2G4. FREQ sweep @ SF8 BW125 PA10 across 2.4 GHz points (5 configs;
    # 2440 replicates the matrix center)
    for f in FREQ_2G4_SWEEP:
        toa = lora_airtime_s(8, 125, 64)
        gap = max(10000, int(1.2 * toa * 1e6) + 5000)
        cfgs.append(dict(mod="lora", sf=8, bw=125, pa=10, freq=f,
                         plen=64, gap=gap, label=f"2G4 SF8 BW125 @ {f/1e6:.0f}MHz"))
    return cfgs


def build_len_bisect_configs():
    """FIX-T6 phase (b): the LEN 253-257 boundary bisect @BR1300 pa10 868 MHz.

    BUG 3 / flrc-retest-20260821.md: LEN=255 was the ONE failing FLRC length
    (0/10 CRC at both BRs) with a +35 dB RSSI step at >= 255, while 254<= and
    256..511 were clean. 253-257 brackets that discontinuity; run it with
    N=20 (card) or N=50 (--npkts) so a single flake cannot decide the verdict.
    """
    cfgs = []
    for plen in FLRC_BISECT_LENS:
        cfgs.append(dict(mod="flrc", br=FLRC_BISECT_BR, pa=FLRC_BISECT_PA,
                         freq=DEFAULT_FREQ, plen=plen, gap=40000,
                         label=f"BISECT {FLRC_BISECT_BR}k pa{FLRC_BISECT_PA} L{plen}"))
    return cfgs


# Named sections so each FIX-T6 phase is ONE reproducible command instead of a
# hand-typed `--only` guess. Each section is a BUILDER, not a filter over the
# full matrix: (br650, pa5, plen64) is emitted by two different sections, and
# tagging the dicts with a section key breaks the dict-for-dict parity test in
# tools/test_balloon_sweep.py (E80ParityTests.test_build_configs_identical).
SECTION_BUILDERS = {
    "flrc-br": build_flrc_br_configs,          # (a) BR sweep
    "flrc-len": build_flrc_len_configs,        # (c) large-packet LEN matrix
    "flrc-len-br": build_flrc_len_br_configs,  # (c') large-packet x BR
    "flrc-bisect": build_len_bisect_configs,   # (b) LEN 253-257 boundary bisect
}


def select_configs(cfgs, section=None):
    """Full matrix for 'all', else the named section's own builder output."""
    key = (section or "all").lower()
    if key in ("all", "*"):
        return list(cfgs)
    if key not in SECTION_BUILDERS:
        raise ValueError(f"unknown sweep section {section!r} "
                         f"(known: {sorted(SECTION_BUILDERS) + ['all']})")
    return SECTION_BUILDERS[key]()


def build_configs(section=None):
    """Full dual-band sweep, or one named FIX-T6 section."""
    return select_configs(_build_all_configs(), section)


# ---- Pre-flight gate (hardware-free decision; no radio keying) --------------

def list_probe_serials(sysfs_root="/sys/bus/usb/devices"):
    """Serials of attached Raspberry-Pi CMSIS-DAP probes (vendor 2e8a)."""
    out = []
    for dev in sorted(glob.glob(os.path.join(sysfs_root, "*"))):
        try:
            with open(os.path.join(dev, "idVendor")) as fh:
                if fh.read().strip().lower() != "2e8a":
                    continue
            with open(os.path.join(dev, "serial")) as fh:
                sn = fh.read().strip()
        except OSError:
            continue
        if sn:
            out.append(sn)
    return out


def parse_fw_hash(id_line):
    """`fw=<hex>` out of an ID? reply, or None when unidentifiable."""
    m = re.search(r"\bfw=([0-9a-fA-F]+)", id_line or "")
    return m.group(1).lower() if m else None


def check_preconditions(probe_serials, id_replies, expected_fw=None,
                        tool_baud=None, fw_baud=None, expected_probes=None):
    """Decide go/no-go for a FIX-T6 sweep. Returns (ok, problems, warnings).

    `id_replies` is keyed by role ("TX"/"RX"); for the firmware check the roles
    are positional (one entry per attached console) since both boards are
    flashed from the same build. FATAL: a missing probe, a silent console, a
    firmware hash that differs from `expected_fw`, a console-baud contract
    violation. WARNING: firmware that cannot be identified when no expectation
    was given (old fw without an `fw=` field must not hard-block a bench run).
    """
    problems, warnings = [], []
    expected = expected_probes if expected_probes is not None else PROBE_SERIALS
    attached = {str(p).upper() for p in (probe_serials or []) if p}

    for role in ("TX", "RX"):
        sn = expected.get(role)
        if sn and sn.upper() not in attached:
            problems.append(f"{role} probe {sn} not attached to this host")

    for role in ("TX", "RX"):
        reply = (id_replies or {}).get(role) or ""
        if not reply.strip():
            problems.append(f"{role}: no console reply to ID?")
            continue
        fw = parse_fw_hash(reply)
        if fw is None:
            msg = (f"{role}: could not identify firmware "
                   f"(ID? -> {reply.strip()[:48]!r})")
            if expected_fw:
                problems.append(msg + " but --expected-fw was given")
            else:
                warnings.append(msg)
            continue
        if expected_fw:
            exp = str(expected_fw).lower()
            if not (fw.startswith(exp) or exp.startswith(fw)):
                problems.append(f"{role}: firmware mismatch board fw={fw} "
                                f"expected {expected_fw}")

    if tool_baud and fw_baud and int(tool_baud) != int(fw_baud):
        problems.append(f"console baud contract: tool {tool_baud} baud != "
                        f"firmware default {fw_baud} baud — every command "
                        f"would be dropped (silent empty CSVs)")

    return (not problems), problems, warnings


def run_preflight(expected_fw=None, npkts=NPKTS, section=None, ports=None,
                  timeout=2.0, expected_probes=None):
    """Board-facing half of the gate: probes on USB + ID? from each console.

    Read-only: sends ID? only. Never ROLE/ARM/START/FLASH.
    Returns the same (ok, problems, warnings) triple as check_preconditions.
    """
    probes = list_probe_serials()
    ports = find_ch340_ports() if ports is None else list(ports)
    fw_baud = fw_default_baud()
    replies, problems, warnings = {}, [], []

    if len(ports) != 2:
        problems.append(f"expected 2 CH340 console ports, found {ports} "
                        f"(a FIX-T6 sweep needs TX and RX simultaneously)")
    for role, port in zip(("TX", "RX"), ports):
        try:
            ser = open_serial(port, timeout=0.5)
        except Exception as exc:                       # noqa: BLE001
            problems.append(f"{role}: cannot open {port} @ {BAUD} ({exc})")
            continue
        try:
            ser.reset_input_buffer()
            ser.write(b"ID?\r\n")
            time.sleep(timeout)
            replies[role] = ser.read(1024).decode(errors="replace").strip()
        finally:
            ser.close()

    ok, extra_p, extra_w = check_preconditions(
        probes, replies, expected_fw=expected_fw, tool_baud=BAUD, fw_baud=fw_baud,
        expected_probes=expected_probes)
    problems += extra_p
    warnings += extra_w
    return (ok and not problems), problems, warnings, replies, probes


SUMMARY_FIELDS = ["idx", "label", "mod", "sf", "bw", "br", "pa", "freq", "plen",
                  "gap_us", "toa_s", "dur_s", "rx_pkts", "crc_err", "rssi_avg",
                  "rssi_min", "rssi_max", "snr_avg", "snr_min", "bit_err_total",
                  "tx_done", "error"]
PKT_FIELDS = ["idx", "label", "pkt_idx", "session", "config", "replicate",
              "ts_ms", "rssi_dbm", "snr_db", "crc_ok", "bit_err", "pcrc16"]
CONFIGS_FIELDS = ["idx", "label", "t_start", "t_end", "dur_s", "rxcnt"]


def parse_args(argv=None):
    """CLI for a FIX-T6 run.

    --section <name>   run one named section (flrc-br | flrc-len | flrc-len-br
                       | flrc-bisect | all) instead of the whole matrix
    --only <substr>    legacy label-substring filter (composes with --section)
    --npkts <n>        packets per config (BR sweep 50, LEN bisect 20)
    --expected-fw <sha>  the firmware hash the boards MUST report in ID?
    --preflight        run the board/baud/firmware gate, then exit (no radio)
    --force            run anyway after a FAILED preflight (evidence is then
                       explicitly "measured on an unverified board")
    """
    argv = list(sys.argv[1:] if argv is None else argv)
    opts = {"only": None, "section": None, "npkts": NPKTS, "expected_fw": None,
            "preflight_only": False, "force": False}
    keys = {"--only": "only", "--section": "section", "--expected-fw": "expected_fw"}
    i = 0
    while i < len(argv):
        arg = argv[i]
        if arg in keys or arg == "--npkts":
            if i + 1 >= len(argv):
                raise SystemExit(f"{arg} needs a value")
            val = argv[i + 1]
            if arg == "--npkts":
                try:
                    opts["npkts"] = int(val)
                except ValueError:
                    raise SystemExit(f"--npkts must be an integer (got {val!r})")
            else:
                opts[keys[arg]] = val
            i += 2
        elif arg == "--preflight":
            opts["preflight_only"] = True
            i += 1
        elif arg == "--force":
            opts["force"] = True
            i += 1
        elif arg in ("-h", "--help"):
            print(__doc__)
            raise SystemExit(0)
        else:
            raise SystemExit(f"unknown argument {arg!r} (see --help)")
    return opts


def main():
    global NPKTS
    opts = parse_args()
    only, section = opts["only"], opts["section"]
    expected_fw = opts["expected_fw"]
    NPKTS = opts["npkts"]
    ts = datetime.now()
    session_id = int(ts.strftime("%y%m%d%H%M"))
    print(f"E80 FULL Sweep — {ts.isoformat()}  session={session_id}", flush=True)
    print(f"Probes: TX={PROBE_TX} RX={PROBE_RX}  {NPKTS} pkts/config  "
          f"console={BAUD} baud (fw default {fw_default_baud()})", flush=True)

    # --- PRE-FLIGHT GATE -------------------------------------------------
    # Refuse to key the radio unless both boards are attached and (when
    # --expected-fw is given) carry the firmware under test. This is the guard
    # against measuring an unknown binary: FIX-T5 was marked done while
    # flashing nothing, so an unguarded sweep would have reported RF results
    # for the wrong firmware (t_4e225809 / t_52ede356).
    ok, problems, warnings, id_replies, probes = run_preflight(
        expected_fw=expected_fw)
    for warn in warnings:
        print(f"PREFLIGHT WARN: {warn}", flush=True)
    print(f"Preflight: {'PASS' if ok else 'FAIL'}  "
          f"probes={probes} ids={ {k: v[:60] for k, v in id_replies.items()} }",
          flush=True)
    if not ok:
        for prob in problems:
            print(f"PREFLIGHT FAIL: {prob}", flush=True)
    if opts["preflight_only"]:
        return 0 if ok else 2
    if not ok and not opts["force"]:
        print("ABORT: refusing to run the sweep on unverified boards "
              "(use --force to override; the run is then explicitly "
              "unverified).", flush=True)
        return 2

    tx_port, rx_port, tx, rx = open_boards()
    print(f"Ports: TX={tx_port} RX={rx_port}", flush=True)

    cfgs = build_configs(section)
    if only:
        cfgs = [c for c in cfgs if only.lower() in c["label"].lower()]
    print(f"Configs: {len(cfgs)}{f' (section={section!r})' if section else ''}"
          f"{f' (filter={only!r})' if only else ''}", flush=True)
    print("=" * 90, flush=True)

    ts_str = ts.strftime("%Y%m%d-%H%M%S")
    # Section runs get their own stem so a bisect CSV can never be mistaken
    # for the BR sweep (verdict attribution).
    stem = OUT_STEM + (f"-{section}" if section and section.lower() != "all" else "")
    sum_path = os.path.join(OUT_DIR, f"{stem}-summary-{ts_str}.csv")
    pkt_path = os.path.join(OUT_DIR, f"{stem}-pkts-{ts_str}.csv")
    sum_f = open(sum_path, "w", newline="")
    sum_w = csv.writer(sum_f); sum_w.writerow(SUMMARY_FIELDS); sum_f.flush()
    pkt_f = open(pkt_path, "w", newline="")
    pkt_w = csv.writer(pkt_f); pkt_f_flush = None
    pkt_w.writerow(PKT_FIELDS); pkt_f.flush()

    # Per-config timing CSV (keeps pkt schema stable)
    cfg_path = os.path.join(OUT_DIR, f"{stem}-configs-{ts_str}.csv")
    cfg_f = open(cfg_path, "w", newline="")
    cfg_w = csv.writer(cfg_f); cfg_w.writerow(CONFIGS_FIELDS); cfg_f.flush()
    t_total_start = time.monotonic()

    # session metadata sidecar — lets downstream tools (e.g. Bloons) fill
    # Operator / Firmware / HW fields instead of "unknown/unrecoverable"
    import json as _json, subprocess as _sp
    try:
        fw_commit = _sp.run(["git", "log", "-1", "--format=%h %s", "--",
                             "firmware/e80-stm32-bench"],
                            capture_output=True, text=True, timeout=5).stdout.strip()
    except Exception:
        fw_commit = ""
    meta = {
        "session": session_id, "started": ts.isoformat(), "operator": "Felix",
        "rig": "e80-stm32", "env": "bench",
        "section": section, "npkts": NPKTS, "console_baud": BAUD,
        "fw_expected": expected_fw,
        "fw_measured": {role: parse_fw_hash(reply) for role, reply in id_replies.items()},
        "preflight": {"ok": ok, "problems": problems, "warnings": warnings},
        "fw_flashed_on_boards": "0561b29 (feat/2g4-sweep: BAND OVERRIDE + HF path, console 2 Mbaud)",
        "fw_source_commit": fw_commit,
        "tx": {"hw": "E80 STM32F103 + LR2021-class module", "port": tx_port},
        "rx": {"hw": "E80 STM32F103 + LR2021-class module", "port": rx_port},
        "band": "dual-band: 863-870 MHz + 2400-2483.5 MHz ISM (BAND OVERRIDE 2026, HF path >= 1.6 GHz)",
        "antennas": "SMA, ~30 cm apart",
        "packets_per_config": NPKTS,
        "integrity_note": "pre-Match123-fix fw: trust bit_err (PRBS-15), not crc_ok, for FLRC",
    }
    meta_path = os.path.join(OUT_DIR, f"{OUT_STEM}-meta-{ts_str}.json")
    with open(meta_path, "w") as mf:
        _json.dump(meta, mf, indent=1)
    print(f"meta -> {meta_path}", flush=True)
    results = []
    for i, cfg in enumerate(cfgs):
        print(f"[{i+1}/{len(cfgs)}] {cfg['label']} ...", end=" ", flush=True)
        rec = {k: cfg.get(k, "") for k in ("mod", "sf", "bw", "br", "pa", "freq",
                                           "plen", "gap", "label")}
        rec.update(idx=i, error="")
        try:
            r = run_config(i, cfg, tx, rx, session_id, tx_port, rx_port)
            results.append(r)
            # Surface invalid configs (e.g. LEN > chip cap) in the error column
            err_msg = r.get("start_reply", "") if r.get("invalid") else ""
            row = [r.get(k, "") for k in SUMMARY_FIELDS[:-1]] + [err_msg[:60]]
            print(f"rx={r['rx_pkts']}/{NPKTS} rssi={r['rssi_avg']} snr={r['snr_avg']} "
                  f"crc={r['crc_err']} done={r['tx_done']}", flush=True)
            for p in r["pkts"]:
                pkt_w.writerow([i, cfg["label"], p["idx"], p["session"], p["config"],
                                p["replicate"], p["ts_ms"], p["rssi"], p["snr"],
                                p["crc_ok"], p["bit_err"], p["pcrc16"]])
            pkt_f.flush()
            cfg_w.writerow([i, cfg["label"], r.get("cfg_t_start", ""),
                           r.get("cfg_t_end", ""), r.get("dur_s", 0),
                           r.get("rx_pkts", 0)])
            cfg_f.flush()
        except Exception as e:
            print(f"FAIL: {e}", flush=True)
            row = [rec.get(k, "") for k in SUMMARY_FIELDS[:-1]] + [str(e)[:60]]
            cfg_w.writerow([i, cfg["label"], "", "", 0, 0])
            cfg_f.flush()
        sum_w.writerow(row)
        sum_f.flush()

    sum_f.close(); pkt_f.close()
    cfg_f.close()

    # Update meta JSON with finished timestamp + timing stats
    t_total_end = time.monotonic()
    total_elapsed = round(t_total_end - t_total_start, 3)
    finished_ts = datetime.now()
    configs_completed = len(results)
    configs_planned = len(cfgs)
    avg_s = round(total_elapsed / configs_completed, 3) if configs_completed else 0
    meta["finished"] = finished_ts.isoformat()
    meta["total_elapsed_s"] = total_elapsed
    meta["configs_planned"] = configs_planned
    meta["configs_completed"] = configs_completed
    meta["avg_s_per_config"] = avg_s
    with open(meta_path, "w") as mf:
        _json.dump(meta, mf, indent=1)
    print(f"configs CSV: {cfg_path}", flush=True)
    print(f"Total elapsed: {total_elapsed}s  avg/config: {avg_s}s  "
          f"({configs_completed}/{configs_planned} configs)", flush=True)

    # Markdown report
    md_path = os.path.join(OUT_DIR, f"{OUT_STEM}-report-{ts_str}.md")
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

        # Timing section — wall-clock instrumentation for planning
        valid = [r for r in results if r.get("dur_s", 0) > 0 and not r.get("invalid")]
        if valid:
            sorted_by_dur = sorted(valid, key=lambda r: r["dur_s"], reverse=True)
            top10 = sorted_by_dur[:10]
            f.write("\n## Timing\n\n")
            f.write(f"**Total wall time:** {total_elapsed} s  \n")
            f.write(f"**Avg per config:** {avg_s} s  \n")
            f.write(f"**Configs completed:** {configs_completed}/{configs_planned}\n\n")
            f.write("### Top-10 slowest configs\n\n")
            f.write("| # | Config | dur_s | toa_s | gap_us | RX |\n")
            f.write("|---|---|---|---|---|---|\n")
            for r in top10:
                f.write(f"| {r['idx']+1} | {r['label']} | {r['dur_s']} | "
                        f"{r.get('toa_s', '-')} | {r.get('gap_us', '-')} | "
                        f"{r['rx_pkts']}/{NPKTS} |\n")
            # Planning formula: calibrate reset_overhead from measured data.
            # est_s(config) = NPKTS * (toa_s + gap_us/1e6) + reset_overhead_s
            residuals = [r["dur_s"] - NPKTS * (r.get("toa_s", 0) + r.get("gap_us", 0)/1e6)
                         for r in valid if r.get("toa_s")]
            if residuals:
                reset_overhead = round(sum(residuals) / len(residuals), 3)
            else:
                reset_overhead = 0
            f.write(f"\n### Planning formula\n\n")
            f.write(f"```\n")
            f.write(f"est_s(config) = {NPKTS} * (toa_s + gap_us/1e6) + {reset_overhead}\n")
            f.write(f"  where toa_s = LoRa airtime or FLRC airtime for the config\n")
            f.write(f"  reset_overhead_s = {reset_overhead} (calibrated from {len(residuals)} configs)\n")
            f.write(f"  total_s(n_configs) = n_configs * est_s(config)  [worst case]\n")
            f.write(f"```\n")
            f.write(f"  Airtime-bound configs: large toa_s (SF11/12, large payloads)\n")
            f.write(f"  Reset-bound configs: dur_s ≈ reset_overhead regardless of toa\n\n")

        f.write(f"\n## Parameter space covered\n\n")
        f.write(f"- LoRa: SF{min(LORA_SFS)}-{max(LORA_SFS)} x BW{LORA_BWS} (PA 10 dBm)\n")
        f.write(f"- LoRa PA: {PA_SWEEP} dBm @ SF8 BW125 (indoor cap 0-10 dBm)\n")
        f.write(f"- Payload: {LEN_SWEEP} B @ SF8 BW125\n")
        f.write(f"- FLRC BR: {FLRC_BRS} kbps @ pa 5\n")
        f.write(f"- FLRC pa: {FLRC_PAS} @ BR 650 kbps\n")
        f.write(f"- Frequency: {[f/1e6 for f in FREQ_SWEEP]} MHz @ SF8 BW125\n")
        f.write(f"- 2.4 GHz ISM (BAND OVERRIDE 2026, HF path): SF matrix/PA/LEN + "
                f"FLRC BR/PA @ 2440 MHz, FREQ {[f/1e6 for f in FREQ_2G4_SWEEP]} MHz\n\n")
        f.write("## Files\n\n")
        f.write(f"- Summary CSV: `{OUT_STEM}-summary-{ts_str}.csv`\n")
        f.write(f"- Per-packet CSV: `{OUT_STEM}-pkts-{ts_str}.csv`\n")
        f.write(f"- Per-config timing CSV: `{OUT_STEM}-configs-{ts_str}.csv`\n")
        f.write(f"- Meta JSON: `{OUT_STEM}-meta-{ts_str}.json`\n")
        f.write(f"- Script: `firmware/e80-stm32-bench/tools/e80_sweep_full.py`\n\n")
        f.write("## Notes\n\n")
        f.write("- GAP adaptive: max(10 ms, 1.2×airtime + 5 ms) — prevents RX overrun at SF11/12\n")
        f.write("- SWD reset (`reset halt; resume`) between configs clears all radio state\n")
        f.write("- PA capped 0–10 dBm by firmware (EU indoor); `POWER MODE OUTDOOR <pin>` unlock exists\n")
        f.write("- LEN 6–511 enforced; FREQ 863–870 MHz enforced (EU SRD)\n")
    print(f"\nSummary CSV: {sum_path}")
    print(f"Per-packet CSV: {pkt_path}")
    print(f"Per-config CSV: {cfg_path}")
    print(f"Meta JSON: {meta_path}")
    print(f"Markdown report: {md_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
