#!/usr/bin/env python3.14
"""v8j step (deterministic, zero-inference): set U5's MS5611 I2C pad->net map.

Root cause of the 11 remaining unconnected_items on the salvaged v8j board: it
still carried the *BMP280* pad->net assignment (pad3=SDA, pad4=SCL,
pads 2/3/6/7/8=GND) on the MS5611 footprint.  On the MS5611-01BA the correct
I2C mapping is (pin names from the official KiCad Sensor_Pressure:MS5611-01BA
symbol, which `extends` MS5607-02BA and matches footprint
Package_LGA:LGA-8_3x5mm_P1.25mm pad-for-pad):

    pin 1  VDD          -> +3V3
    pin 2  PS           -> GND    (low selects I2C)
    pin 3  GND          -> GND
    pin 4  CSB          -> +3V3   (high selects I2C)
    pin 5  CSB          -> +3V3   (same physical net as pin 4; MUST match it)
    pin 6  SDO          -> GND    (address LSB = 0 -> 0x76)
    pin 7  SDI/SDA      -> I2C_SDA
    pin 8  SCLK/SCL     -> I2C_SCL

NOTE the salvaged build_v8j.py had pin 4 -> GND while pin 5 -> +3V3.  Pins 4
and 5 are the SAME CSB net, so that assignment shorts GND to +3V3 through the
part.  Fixed here.

Writes output/v8j_u5net.kicad_pcb plus the FROZEN sibling rule files (byte
copies of the PASSING v8i siblings) so the KRT re-route and kicad-cli DRC both
resolve the same frozen rule set the reference board passed with.
"""
import sys, json, shutil
sys.path.insert(0, '/usr/lib/python3/dist-packages')
import pcbnew  # noqa: E402

HW = 'tracker/hardware/output'
SRC = f'{HW}/v8j_krt_ms5611.kicad_pcb'
DST = f'{HW}/v8j_u5net.kicad_pcb'

U5_NETS = {'1': '+3V3', '2': 'GND', '3': 'GND', '4': '+3V3',
           '5': '+3V3', '6': 'GND', '7': 'I2C_SDA', '8': 'I2C_SCL'}
FPID = 'Package_LGA:LGA-8_3x5mm_P1.25mm'

b = pcbnew.LoadBoard(SRC)
u5 = b.FindFootprintByReference('U5')
assert u5 is not None, 'U5 not found'
print('U5', str(u5.GetFPID()), 'value=', u5.GetValue())
print('  before:', {p.GetNumber(): p.GetNetname() for p in u5.Pads()})
for p in u5.Pads():
    nn = U5_NETS[p.GetNumber()]
    net = b.FindNet(nn)
    assert net is not None, f'net {nn!r} absent from board'
    p.SetNet(net)
u5.SetFPID(pcbnew.LIB_ID('Package_LGA', 'LGA-8_3x5mm_P1.25mm'))
print('  after :', {p.GetNumber(): p.GetNetname() for p in u5.Pads()})
pcbnew.SaveBoard(DST, b)

shutil.copy(f'{HW}/v8i_krt_gnss.kicad_dru', f'{HW}/v8j_u5net.kicad_dru')
d = json.load(open(f'{HW}/v8i_krt_gnss.kicad_pro'))
d.setdefault('meta', {})['filename'] = 'v8j_u5net.kicad_pro'
json.dump(d, open(f'{HW}/v8j_u5net.kicad_pro', 'w'), indent=2)
print('wrote', DST)
