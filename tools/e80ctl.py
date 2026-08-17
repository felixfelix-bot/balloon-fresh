#!/usr/bin/env python3
"""e80ctl — host control for EBYTE E80-900MBL-02 stock demo firmware (STM32F103C8T6 + LR2021).

Protocol source-verified from vendor demo main.c (doc id 4393, mbl02demo):
  C1 00 <freq:4 BE>            set RF frequency (RF-silent, re-enters RX, echoes frame)
  C1 02 00 / C1 02 01          CW stop (prints 'stop tx cw') / CW start (RF!)
  C1 03 00 / C1 03 01          exit / enter RF sleep
  C1 C1 C1                     auto-TX 20-byte test payload (RF!)
  C2 <pa><pow><sf><bw><cr><ppm><sync><freq:4>  one-shot full param config (12B)
  C3 C3 00 <freq:4>            VENDOR LONG-RANGE TEST preset: SF12/BW125/CR4-5/LDRO/sync0x12
  C3 C3 02 <freq:4>            2.4G comparison preset (SF11/BW500)
  C4 C4 00 <freq:4>            sensitivity preset: SF9/BW125/CR4-5/LDRO-off/sync0x12
  anything else                TRANSPARENT TX over LoRa (RF!)

RAM-only: power cycle reverts to 850 MHz / SF8 / +22 dBm (illegal in EU — re-set after every boot).

ETSI guardrail: EU 863-870 only; TX commands require --antenna-on (no-antenna TX damages PA).
"""
import argparse, sys, time

try:
    import serial
except ImportError:
    sys.exit("pyserial missing: pip install pyserial")

DEF_PORT = "/dev/ttyUSB3"  # board A CH340
EU_LO, EU_HI = 863_000_000, 870_000_000


def cmd_freq(freq):
    return bytes([0xC1, 0x00]) + freq.to_bytes(4, "big")


def cmd_longrange(freq):
    return bytes([0xC3, 0xC3, 0x00]) + freq.to_bytes(4, "big")


def cmd_sens(freq):
    return bytes([0xC4, 0xC4, 0x00]) + freq.to_bytes(4, "big")


def cw_stop():
    return bytes([0xC1, 0x02, 0x00])


def cw_start():
    return bytes([0xC1, 0x02, 0x01])


def sleep_enter():
    return bytes([0xC1, 0x03, 0x01])


def sleep_exit():
    return bytes([0xC1, 0x03, 0x00])


def send(port, frame, expect_echo=True, timeout=1.0, baud=115200):
    s = serial.Serial(port, baud, timeout=timeout)
    try:
        s.reset_input_buffer()
        s.write(frame)
        s.flush()
        time.sleep(0.4)
        resp = s.read(128)
        return resp
    finally:
        s.close()


def check_eu(freq, force):
    if not (EU_LO <= freq <= EU_HI) and not force:
        sys.exit(f"REFUSED: {freq} Hz outside EU 863-870. Use --force to override.")


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--port", default=DEF_PORT)
    p.add_argument("--force", action="store_true", help="allow non-EU freq")
    p.add_argument("--antenna-on", action="store_true",
                   help="CONFIRM antenna attached — required for any RF-emitting command")
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("alive", help="RF-silent alive check (C1 02 00 → 'stop tx cw')")
    g = sub.add_parser("freq", help="set frequency (RF-silent)")
    g.add_argument("mhz", type=float)
    g = sub.add_parser("longrange", help="vendor SF12/BW125 long-range preset (RF-silent config)")
    g.add_argument("mhz", type=float)
    g = sub.add_parser("sens", help="vendor SF9 sensitivity preset (RF-silent config)")
    g.add_argument("mhz", type=float)
    sub.add_parser("sleep", help="enter RF sleep")
    sub.add_parser("wake", help="exit RF sleep")
    sub.add_parser("cw-stop", help="stop CW (RF-silent)")
    g = sub.add_parser("cw-start", help="start CW carrier (RF!) — needs --antenna-on")
    g = sub.add_parser("tx", help="transparent TX payload hex (RF!) — needs --antenna-on")
    g.add_argument("hexdata")
    g = sub.add_parser("listen", help="print received LoRa packets (transparent RX→UART)")
    g.add_argument("--duration", type=float, default=60.0)

    a = p.parse_args()
    freq_hz = int(round(getattr(a, "mhz", 0) * 1e6))

    if a.cmd == "alive":
        r = send(a.port, cw_stop())
        ok = b"stop tx cw" in r
        print("ALIVE — firmware responded" if ok else f"NO RESPONSE (raw: {r!r})")
        sys.exit(0 if ok else 1)

    if a.cmd in ("freq", "longrange", "sens"):
        check_eu(freq_hz, a.force)
        frame = {"freq": cmd_freq, "longrange": cmd_longrange, "sens": cmd_sens}[a.cmd](freq_hz)
        r = send(a.port, frame)
        ok = frame in r  # response may carry prefix text (e.g. LR2021 version print)
        ver = r.split(b"\r\n")[0].decode("ascii", errors="replace").strip()
        print(f"OK echo ({a.cmd} {a.mhz} MHz)" + (f" | {ver}" if ver and not ver.startswith("\x00") and "Version" in ver else ""))
        if not ok:
            print(f"BAD ECHO: {r.hex(' ')}")
        sys.exit(0 if ok else 1)

    if a.cmd == "cw-stop":
        r = send(a.port, cw_stop())
        print(r.decode("ascii", errors="replace").strip() or "(silent)")
        return
    if a.cmd == "cw-start":
        if not a.antenna_on:
            sys.exit("REFUSED: CW without antenna damages PA. Pass --antenna-on")
        r = send(a.port, cw_start())
        print(r.decode("ascii", errors="replace").strip() or "(started)")
        return
    if a.cmd == "sleep":
        r = send(a.port, sleep_enter())
        print(r.decode("ascii", errors="replace").strip() or "(sleeping)")
        return
    if a.cmd == "wake":
        r = send(a.port, sleep_exit())
        print(r.decode("ascii", errors="replace").strip() or "(awake)")
        return
    if a.cmd == "tx":
        if not a.antenna_on:
            sys.exit("REFUSED: TX without antenna damages PA. Pass --antenna-on")
        data = bytes.fromhex(a.hexdata.replace(":", "").replace(" ", ""))
        r = send(a.port, data, expect_echo=False)
        print(f"sent {len(data)} bytes (transparent TX)")
        return
    if a.cmd == "listen":
        s = serial.Serial(a.port, 115200, timeout=1)
        print(f"listening {a.duration}s on {a.port} …")
        t0 = time.time()
        try:
            while time.time() - t0 < a.duration:
                line = s.readline()
                if line:
                    print(f"[{time.time()-t0:7.1f}s] {line.hex(' ')} | {line.decode('ascii', errors='replace').rstrip()}")
        except KeyboardInterrupt:
            pass
        finally:
            s.close()


if __name__ == "__main__":
    main()
