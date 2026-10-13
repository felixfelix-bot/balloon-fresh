#!/usr/bin/env python3
"""e80_seq_diag.py — bisect why sweep gets 0 pkts but manual sequence works.
Runs sweep-exact sequence with full response logging, then the manual-exact
sequence, on SF8 BW125 PA=10."""
import serial, time, sys

TX='/dev/ttyUSB3'; RX='/dev/ttyUSB4'; BAUD=2000000

def mk(port):
    s=serial.Serial(port,BAUD,timeout=0.2)
    time.sleep(0.2)
    s.reset_input_buffer()
    return s

def cmd(s,m,w=0.15,tag=""):
    s.reset_input_buffer()
    s.write((m+'\r\n').encode())
    time.sleep(w)
    r=s.read(500).decode(errors='replace').strip().replace('\r\n',' | ')
    print(f"  [{tag}] {m!r:35} -> {r[:90]}")
    return r

def capture(rx, dur, label):
    print(f"  [{label}] capturing {dur}s...")
    rx.reset_input_buffer()
    t=time.time(); pkts=0; first=None; last=None
    buf=""
    while time.time()-t<dur:
        buf+=rx.read(rx.in_waiting or 1).decode(errors='replace')
        while '\n' in buf:
            line,buf=buf.split('\n',1)
            line=line.strip()
            if line.startswith('PKT,'):
                pkts+=1
                first=first or line
                last=line
    print(f"  [{label}] PKTs={pkts}" + (f" first={first[:70]}" if first else ""))
    return pkts

def main():
    mode = sys.argv[1] if len(sys.argv)>1 else "sweep"
    tx=mk(TX); rx=mk(RX)
    print(f"=== MODE: {mode} (SF8 BW125 PA10) ===")

    if mode=="sweep":
        # EXACT sweep sequence
        cmd(tx,"STOP",0.5,"tx"); cmd(rx,"STOP",0.5,"rx"); time.sleep(0.3)
        cmd(rx,"ROLE RX",0.3,"rx"); cmd(rx,"MOD loRa 8 125",0.3,"rx")
        cmd(rx,"FREQ 868000000",0.3,"rx"); cmd(rx,"PA 10",0.3,"rx")
        cmd(rx,"PRBS ON",0.3,"rx"); cmd(rx,"SESSION 0",0.3,"rx")
        cmd(rx,"CONFIG 0 0",0.3,"rx")
        cmd(tx,"ROLE TX",0.15,"tx"); cmd(tx,"MOD loRa 8 125",0.15,"tx")
        cmd(tx,"FREQ 868000000",0.15,"tx"); cmd(tx,"PA 10",0.15,"tx")
        cmd(tx,"SESSION 0",0.15,"tx"); cmd(tx,"CONFIG 0 0",0.15,"tx")
        time.sleep(0.3)
        cmd(tx,"ARM TX",0.05,"tx")
        cmd(tx,"START N=20 LEN=64 GAP=10000",0.2,"tx")
        capture(rx,10,"sweep")
        cmd(tx,"STAT?",0.4,"tx"); cmd(rx,"STAT?",0.4,"rx")
    else:
        # EXACT working manual sequence (no STOP, no SESSION/CONFIG, no PA on RX)
        cmd(rx,'ROLE RX',0.15,"rx"); cmd(rx,'MOD loRa 8 125',0.15,"rx")
        cmd(rx,'FREQ 868000000',0.15,"rx"); cmd(rx,'PRBS ON',0.15,"rx")
        cmd(tx,'ROLE TX',0.15,"tx"); cmd(tx,'MOD loRa 8 125',0.15,"tx")
        cmd(tx,'FREQ 868000000',0.15,"tx"); cmd(tx,'PA 10',0.15,"tx")
        print("  TX ID:",cmd(tx,'ID?',0.3,"tx")[:90])
        print("  RX ID:",cmd(rx,'ID?',0.3,"rx")[:90])
        t0=time.time()
        cmd(tx,'ARM TX',0.1,"tx")
        cmd(tx,'START N=20 LEN=64 GAP=10000',0.1,"tx")
        print(f"  ARM->START {time.time()-t0:.2f}s")
        capture(rx,10,"manual")
        cmd(tx,"STAT?",0.4,"tx")
    tx.close(); rx.close()

if __name__=="__main__":
    main()