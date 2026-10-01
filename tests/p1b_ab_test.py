#!/usr/bin/env python3
"""P1B comprehensive A/B test: RadioLib vs Raw SPI, DELAY sweep, bitrate sweep.
Auto-detects port assignment. Keeps ports open for entire test suite.
Usage: python3 -u tests/p1b_ab_test.py [--br 2600,1300,650,325] [--reset-between-tests | --no-reset-between-tests]

Reset strategy: with --reset-between-tests (recommended), the TX board is hard-reset
(DTR toggle) at every group boundary and both ports are re-opened. Port identity is
preserved across USB CDC re-enumeration via /dev/serial/by-id symlinks when present
(ESP32-C3 USB Serial/JTAG exposes a stable by-id), falling back to sorted ttyACM
ordering with a loud warning if by-id is unavailable.
"""
import serial, time, re, json, os, sys, glob, argparse

PYP = "/home/c03rad0r/.espressif/python_env/idf5.4_py3.13_env/bin/python3"
RESULTS_DIR = "tests/results/phase1b"
DEFAULT_BR_SWEEP = "2600,1300,650,325"


def detect_esp_ports():
    """Re-glob ESP32 ports (skip RP2040 at ACM1). Never reuses a stale node."""
    return sorted(f"/dev/ttyACM{i}" for i in range(2, 10) if os.path.exists(f"/dev/ttyACM{i}"))


ESP_PORTS = detect_esp_ports()

parser = argparse.ArgumentParser(description='P1B A/B Test Runner')
parser.add_argument('--reset-between-tests', dest='reset_between_tests',
                    action='store_true', default=False,
                    help='Reset TX device between test groups to survive USB CDC '
                         're-enumeration (default: off)')
parser.add_argument('--no-reset-between-tests', dest='reset_between_tests',
                    action='store_false',
                    help='Do not reset devices between test groups (explicit negative '
                         'form; a bare invocation behaves the same way)')
parser.add_argument('--br', default=DEFAULT_BR_SWEEP, metavar='LIST',
                    help=f'comma-separated FLRC bitrate sweep for groups 3/4 '
                         f'(default: {DEFAULT_BR_SWEEP})')
args = None  # set in main()


def parse_br_list(s):
    """'2600,1300' -> [2600, 1300]. Raises ValueError on junk."""
    vals = [int(x.strip()) for x in s.split(',') if x.strip()]
    if not vals:
        raise ValueError("empty --br list")
    return vals


def by_id_map():
    """Map realpath(tty node) -> stable /dev/serial/by-id symlink, best effort."""
    m = {}
    for p in glob.glob('/dev/serial/by-id/*'):
        try:
            m[os.path.realpath(p)] = p
        except OSError:
            pass
    return m


def resolve_role_ports(old_tx, old_rx, ports, idmap):
    """Resolve (new_tx, new_rx, how) after re-enumeration.

    Identity is the /dev/serial/by-id symlink captured for the OLD paths. If the
    boards kept their nodes, keep them. If by-id is unavailable, fall back to
    positional ordering and say so.
    """
    if old_tx in ports and old_rx in ports:
        return old_tx, old_rx, 'nodes-stable'
    tx_id = idmap.get(os.path.realpath(old_tx))
    rx_id = idmap.get(os.path.realpath(old_rx))
    if tx_id and rx_id:
        # Prefer the candidate node that actually exists now — during
        # re-enumeration a by-id may transiently match stale + new nodes.
        tx_cand = [n for n, sid in idmap.items() if sid == tx_id and n in ports]
        rx_cand = [n for n, sid in idmap.items() if sid == rx_id and n in ports]
        if tx_cand and rx_cand and tx_cand[0] != rx_cand[0]:
            return tx_cand[0], rx_cand[0], 'by-id'
    if len(ports) >= 2:
        return ports[0], ports[1], 'ORDERING-FALLBACK (roles may have swapped!)'
    raise RuntimeError(f"Need 2 ESP32 serial ports after reset. Found: {ports}")


def open_port(port):
    s = serial.Serial()
    s.port = port; s.baudrate = 115200; s.dtr = False; s.rts = False; s.timeout = 0.5
    s.open()
    return s

def open_port_with_retry(port, max_retries=3):
    """Open serial port with retry logic for USB CDC re-enumeration issues"""
    for attempt in range(max_retries):
        try:
            s = serial.Serial()
            s.port = port; s.baudrate = 115200; s.dtr = False; s.rts = False; s.timeout = 0.5
            s.open()
            return s
        except serial.SerialException as e:
            if "tcsetattr" in str(e) or "device disconnected" in str(e):
                print(f"  Serial open failed (attempt {attempt + 1}/{max_retries}): {e}", flush=True)
                if attempt < max_retries - 1:
                    time.sleep(2)  # Wait for USB to re-enumerate
                    continue
            else:
                raise  # Re-raise other serial exceptions immediately
    raise serial.SerialException(f"Failed to open port {port} after {max_retries} attempts")

def reset_device(port):
    """Reset device using DTR toggle"""
    try:
        s = serial.Serial()
        s.port = port; s.baudrate = 115200; s.timeout = 0.5
        s.open()
        print(f"  Resetting device on {port} using DTR toggle...", flush=True)
        s.dtr = True  # Assert DTR (typically causes reset)
        time.sleep(0.1)
        s.dtr = False  # Deassert DTR
        s.close()
        time.sleep(2)  # Wait for device to reboot and USB to re-enumerate
    except Exception as e:
        print(f"  Reset failed: {e}", flush=True)

def re_detect_ports():
    """Re-detect ESP32 ports after reset"""
    print("  Re-detecting ESP32 ports after reset...", flush=True)
    global ESP_PORTS
    ESP_PORTS = detect_esp_ports()
    if len(ESP_PORTS) < 2:
        raise RuntimeError(f"Need 2 ESP32 serial ports after reset. Found: {ESP_PORTS}")
    return ESP_PORTS

def cmd(s, c, w=0.3):
    s.write((c + "\n").encode()); time.sleep(w)
    r = b""
    for _ in range(10):
        d = s.read(4096)
        if d: r += d
        else: break
    return r.decode(errors='replace')

def drain(s, t):
    s.timeout = 0.3; end = time.time() + t; chunks = []
    while time.time() < end:
        d = s.read(4096)
        if d: chunks.append(d)
    return b"".join(chunks).decode(errors='replace')

def parse(text):
    r = {}
    for key in ['received','crc_errors','lost','total_sent_by_tx','elapsed_ms']:
        m = re.search(key + r',(\d+)', text)
        r[key] = int(m.group(1)) if m else 0
    m = re.search(r'throughput_kbps,([\d.]+)', text)
    r['throughput'] = float(m.group(1)) if m else 0
    m = re.search(r'per_pct,([\d.]+)', text)
    r['per'] = float(m.group(1)) if m else 100
    m = re.search(r'avg_rssi,([\d.-]+)', text)
    r['rssi'] = float(m.group(1)) if m else 0
    m = re.search(r'time_per_pkt_ms,([\d.]+)', text)
    r['ms_per_pkt'] = float(m.group(1)) if m else 0
    return r

def run_single_test(sa, sb, mode_cmd, trigger_cmd, br, size, delay, count=100):
    """Run one test. sa=TX port, sb=RX port. Both already open."""
    # Configure RX (must set PWR 12 — default 22 is invalid on 2.4GHz)
    for c in ['ROLE RX', mode_cmd, 'FREQ 2450', f'BR {br}', 'PWR 12', f'SIZE {size}', 'RUN']:
        cmd(sb, c, 0.2)
    # Configure TX
    for c in ['ROLE TX', mode_cmd, 'FREQ 2450', f'BR {br}', 'PWR 12',
              f'SIZE {size}', f'COUNT {count}', f'DELAY {delay}']:
        cmd(sa, c, 0.2)
    # Trigger
    cmd(sa, trigger_cmd, 0.2)
    # Wait for results
    wait = max(5 + delay * count / 1000 + 3, 10)
    rx_data = drain(sb, wait)
    return parse(rx_data)


def reopen_ports_after_reset(state):
    """Group boundary: hard-reset TX, re-detect, re-open both ports keeping roles.

    state is a dict {'tx': path, 'rx': path, 'sa': handle, 'sb': handle};
    it is updated in place and returned.
    """
    print("\n--- Resetting devices between test groups ---", flush=True)
    state['sa'].close(); state['sb'].close()
    reset_device(state['tx'])
    ports = re_detect_ports()
    new_tx, new_rx, how = resolve_role_ports(state['tx'], state['rx'], ports, by_id_map())
    print(f"  REOPEN: TX={new_tx} RX={new_rx} resolved via {how}", flush=True)
    state['tx'], state['rx'] = new_tx, new_rx
    state['sa'] = open_port_with_retry(new_tx)
    state['sb'] = open_port_with_retry(new_rx)
    time.sleep(5)
    state['sa'].read(65536); state['sb'].read(65536)
    print(f"  Reopened ports: TX={new_tx}, RX={new_rx}", flush=True)
    return state


def main():
    global args
    args = parser.parse_args()
    try:
        br_sweep = parse_br_list(args.br)
    except ValueError as e:
        print(f"ERROR: bad --br value {args.br!r}: {e}")
        sys.exit(2)

    global ESP_PORTS
    ESP_PORTS = detect_esp_ports()
    if len(ESP_PORTS) < 2:
        print("ERROR: Need 2 ESP32 serial ports. Found:", ESP_PORTS)
        sys.exit(1)
    os.makedirs(RESULTS_DIR, exist_ok=True)

    # ============================================================
    print("=" * 70, flush=True)
    print("P1B COMPREHENSIVE A/B TEST", flush=True)
    print(f"Time: {time.strftime('%Y-%m-%d %H:%M:%S UTC', time.gmtime())}", flush=True)
    print(f"Ports: {ESP_PORTS}", flush=True)
    print(f"BR sweep: {br_sweep}", flush=True)
    print(f"Reset between tests: {'Enabled' if args.reset_between_tests else 'Disabled'}", flush=True)
    print("=" * 70, flush=True)

    # === AUTO-DETECT PORT ASSIGNMENT ===
    print("\n--- Detecting TX/RX assignment ---", flush=True)
    port_a, port_b = ESP_PORTS[0], ESP_PORTS[1]
    state = {'tx': None, 'rx': None, 'sa': None, 'sb': None}

    # Try A=TX, B=RX first
    sa = open_port_with_retry(port_a)
    sb = open_port_with_retry(port_b)
    time.sleep(5)  # Wait for boot
    sa.read(65536); sb.read(65536)
    state.update(sa=sa, sb=sb)

    print(f"  Trying {port_a}=TX, {port_b}=RX...", flush=True)
    r = run_single_test(sa, sb, 'MODE FLRC', 'RUN', 2600, 64, 10, 20)
    if r['received'] > 0:
        print(f"  ✅ Works! {r['received']}/{r['total_sent_by_tx']} pkts received", flush=True)
        state['tx'], state['rx'] = port_a, port_b
    else:
        print(f"  ❌ No packets. Trying reversed...", flush=True)
        sa.close(); sb.close()
        time.sleep(1)
        sa = open_port_with_retry(port_b)
        sb = open_port_with_retry(port_a)
        time.sleep(5)
        sa.read(65536); sb.read(65536)
        state.update(sa=sa, sb=sb)
        r = run_single_test(sa, sb, 'MODE FLRC', 'RUN', 2600, 64, 10, 20)
        if r['received'] > 0:
            print(f"  ✅ Reversed works! {r['received']}/{r['total_sent_by_tx']} pkts", flush=True)
            state['tx'], state['rx'] = port_b, port_a
        else:
            print(f"  ❌ Neither direction works. Check hardware.", flush=True)
            sa.close(); sb.close()
            sys.exit(1)

    print(f"  Assignment: TX={state['tx']}, RX={state['rx']}", flush=True)
    sa, sb = state['sa'], state['sb']

    # ============================================================
    # GROUP 1: RadioLib DELAY sweep (baseline)
    # ============================================================
    print("\n--- GROUP 1: RadioLib DELAY sweep (FLRC 2600, 255B) ---", flush=True)
    group1 = []
    for delay in [10, 5, 2, 1, 0]:
        r = run_single_test(sa, sb, 'MODE FLRC', 'RUN', 2600, 255, delay, 100)
        r['test'] = f'RadioLib DELAY={delay}'
        r['group'] = 'radiolib_delay'
        r['delay'] = delay
        r['mode'] = 'RadioLib'
        group1.append(r)
        status = '✅' if r['received'] > 0 else '❌'
        print(f"  {status} DELAY={delay}ms: {r['received']}/{r['total_sent_by_tx']} pkts, " \
              f"{r['throughput']:.1f} kbps, PER={r['per']:.1f}%, {r['ms_per_pkt']:.2f}ms/pkt", flush=True)
        time.sleep(1)

    if args.reset_between_tests:
        reopen_ports_after_reset(state)
        sa, sb = state['sa'], state['sb']

    # ============================================================
    # GROUP 2: Raw SPI DELAY sweep (bypass)
    # ============================================================
    print("\n--- GROUP 2: Raw SPI DELAY sweep (FLRC 2600, 255B) ---", flush=True)
    group2 = []
    for delay in [10, 5, 2, 1, 0]:
        r = run_single_test(sa, sb, 'MODE FLRC', 'RAWTX', 2600, 255, delay, 100)
        r['test'] = f'RawSPI DELAY={delay}'
        r['group'] = 'rawspi_delay'
        r['delay'] = delay
        r['mode'] = 'RawSPI'
        group2.append(r)
        status = '✅' if r['received'] > 0 else '❌'
        print(f"  {status} DELAY={delay}ms: {r['received']}/{r['total_sent_by_tx']} pkts, " \
              f"{r['throughput']:.1f} kbps, PER={r['per']:.1f}%, {r['ms_per_pkt']:.2f}ms/pkt", flush=True)
        time.sleep(1)

    if args.reset_between_tests:
        reopen_ports_after_reset(state)
        sa, sb = state['sa'], state['sb']

    # ============================================================
    # GROUP 3: RadioLib bitrate sweep (DELAY=0, 255B)
    # ============================================================
    print(f"\n--- GROUP 3: RadioLib bitrate sweep (DELAY 0, 255B) ---", flush=True)
    group3 = []
    for br in br_sweep:
        r = run_single_test(sa, sb, 'MODE FLRC', 'RUN', br, 255, 0, 100)
        r['test'] = f'RadioLib BR={br}'
        r['group'] = 'radiolib_bitrate'
        r['br'] = br
        r['mode'] = 'RadioLib'
        group3.append(r)
        status = '✅' if r['received'] > 0 else '❌'
        print(f"  {status} BR={br}: {r['received']}/{r['total_sent_by_tx']} pkts, " \
              f"{r['throughput']:.1f} kbps, PER={r['per']:.1f}%", flush=True)
        time.sleep(1)

    if args.reset_between_tests:
        reopen_ports_after_reset(state)
        sa, sb = state['sa'], state['sb']

    # ============================================================
    # GROUP 4: Raw SPI bitrate sweep (DELAY=0, 255B)
    # ============================================================
    print(f"\n--- GROUP 4: Raw SPI bitrate sweep (DELAY 0, 255B) ---", flush=True)
    group4 = []
    for br in br_sweep:
        r = run_single_test(sa, sb, 'MODE FLRC', 'RAWTX', br, 255, 0, 100)
        r['test'] = f'RawSPI BR={br}'
        r['group'] = 'rawspi_bitrate'
        r['br'] = br
        r['mode'] = 'RawSPI'
        group4.append(r)
        status = '✅' if r['received'] > 0 else '❌'
        print(f"  {status} BR={br}: {r['received']}/{r['total_sent_by_tx']} pkts, " \
              f"{r['throughput']:.1f} kbps, PER={r['per']:.1f}%", flush=True)
        time.sleep(1)

    if args.reset_between_tests:
        reopen_ports_after_reset(state)
        sa, sb = state['sa'], state['sb']

    # ============================================================
    # GROUP 5: Payload size sweep (RadioLib vs RawSPI, DELAY=0, BR=2600)
    # ============================================================
    print("\n--- GROUP 5: Payload size sweep (FLRC 2600, DELAY 0) ---", flush=True)
    group5 = []
    for size in [20, 64, 128, 255]:
        for mode_cmd, trigger, label in [('MODE FLRC', 'RUN', 'RadioLib'), ('MODE FLRC', 'RAWTX', 'RawSPI')]:
            r = run_single_test(sa, sb, mode_cmd, trigger, 2600, size, 0, 100)
            r['test'] = f'{label} SIZE={size}'
            r['group'] = 'size_sweep'
            r['size'] = size
            r['mode'] = label
            group5.append(r)
            status = '✅' if r['received'] > 0 else '❌'
            print(f"  {status} {label} SIZE={size}: {r['received']}/{r['total_sent_by_tx']} pkts, " \
                  f"{r['throughput']:.1f} kbps", flush=True)
            time.sleep(1)

    # Final reset (leave boards in a clean booted state)
    if args.reset_between_tests:
        print("\n--- Final device reset ---", flush=True)
        state['sa'].close(); state['sb'].close()
        reset_device(state['tx'])

    sa.close(); sb.close()

    # ============================================================
    # SUMMARY
    # ============================================================
    all_results = group1 + group2 + group3 + group4 + group5

    print("\n" + "=" * 70, flush=True)
    print("A/B COMPARISON SUMMARY", flush=True)
    print("=" * 70, flush=True)

    # Delay comparison
    print("\nDELAY SWEEP (FLRC 2600, 255B):", flush=True)
    print(f"{'DELAY':<8} {'RadioLib kbps':<15} {'RawSPI kbps':<15} {'Speedup'}", flush=True)
    print("-" * 50, flush=True)
    for i in range(len(group1)):
        rl = group1[i]
        rs = group2[i] if i < len(group2) else {}
        rl_kbps = rl.get('throughput', 0)
        rs_kbps = rs.get('throughput', 0)
        speedup = f"{rs_kbps/rl_kbps:.1f}x" if rl_kbps > 0 else "N/A"
        print(f"{rl['delay']}ms     {rl_kbps:<15.1f} {rs_kbps:<15.1f} {speedup}", flush=True)

    # Bitrate comparison
    print("\nBITRATE SWEEP (DELAY 0, 255B):", flush=True)
    print(f"{'BR':<8} {'RadioLib kbps':<15} {'RawSPI kbps':<15} {'Speedup'}", flush=True)
    print("-" * 50, flush=True)
    for i in range(len(group3)):
        rl = group3[i]
        rs = group4[i] if i < len(group4) else {}
        rl_kbps = rl.get('throughput', 0)
        rs_kbps = rs.get('throughput', 0)
        speedup = f"{rs_kbps/rl_kbps:.1f}x" if rl_kbps > 0 else "N/A"
        print(f"{rl['br']:<8} {rl_kbps:<15.1f} {rs_kbps:<15.1f} {speedup}", flush=True)

    # Best result
    best = max(all_results, key=lambda x: x.get('throughput', 0))
    print(f"\n🏆 BEST: {best['test']} = {best.get('throughput', 0):.1f} kbps "
          f"({best.get('received',0)}/{best.get('total_sent_by_tx',0)} pkts, "
          f"PER={best.get('per',0):.1f}%)", flush=True)

    # Save
    with open(f"{RESULTS_DIR}/ab_comparison.json", "w") as f:
        json.dump(all_results, f, indent=2, default=str)
    print(f"\nResults saved to {RESULTS_DIR}/ab_comparison.json", flush=True)
    print("=== DONE ===", flush=True)


if __name__ == "__main__":
    main()
