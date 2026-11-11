"""Independent oracle: Raspberry Pi RP2040 datasheet Figure 3, §§1.4,2.9.
Not imported from generator/spec/KiCad library. Executes generator only in a copy.
"""
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import unittest

HERE = Path(__file__).resolve().parent


def parse(text):
    owners = {}
    for block in re.split(r'\n    \(net ', text)[1:]:
        match = re.search(r'\(name "([^"]+)"\)', block)
        assert match is not None, "missing net name"
        net = match.group(1)
        for ref, pin in re.findall(r'\(node \(ref "([^"]+)"\) \(pin "([^"]+)"\)', block):
            if (ref, pin) in owners:
                raise ValueError(f'duplicate pad ownership: {ref}.{pin}')
            owners[ref, pin] = net
    return owners


class RP2040Pinout(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls.tmp.cleanup)
        directory = Path(cls.tmp.name)
        for name in ('gen_base_station_netlist.py', 'spec.json'):
            shutil.copy2(HERE / name, directory / name)
        subprocess.run([sys.executable, str(directory / 'gen_base_station_netlist.py')],
                       check=True, capture_output=True)
        cls.text = (directory / 'base_station_v1.net').read_text()
        cls.pads = parse(cls.text)

    def test_dedicated_pin_functions_and_gpio_adc(self):
        expected = {1: '+3V3_MCU', 10: '+3V3_MCU', 22: '+3V3_MCU',
                    33: '+3V3_MCU', 42: '+3V3_MCU', 49: '+3V3_MCU',
                    23: '+1V1_MCU', 50: '+1V1_MCU', 43: '+3V3_MCU',
                    44: '+3V3_MCU', 45: '+1V1_MCU', 48: '+3V3_MCU',
                    19: 'GND', 57: 'GND', 20: 'XIN', 21: 'XOUT',
                    24: 'SWCLK', 25: 'SWDIO', 26: 'RUN',
                    46: 'USB_DM', 47: 'USB_DP', 51: 'QSPI_SD3',
                    52: 'QSPI_SCLK', 53: 'QSPI_SD0', 54: 'QSPI_SD2',
                    55: 'QSPI_SD1', 56: 'QSPI_SS', 38: 'DET_VOUT'}
        for pin, net in expected.items():
            with self.subTest(pin=pin):
                self.assertEqual(self.pads.get(('U_MCU', str(pin))), net)
        # Unused GPIOs must not be fabricated ground pins; no extra supply shorts.
        self.assertEqual({p for (r, p), n in self.pads.items() if r == 'U_MCU' and n == 'GND'}, {'19', '57'})

    def test_supply_decoupling_and_usb_series(self):
        values = dict(re.findall(r'\(comp \(ref "([^"]+)"\)\s*\(value "([^"]*)"\)', self.text))
        # Each physical supply pin gets its own capacitor, not one shared count.
        for pin in (1, 10, 22, 33, 42, 49, 23, 50, 43, 48, 44, 45):
            ref = f'C_RP_{pin}'
            with self.subTest(capacitor=ref):
                self.assertEqual(values.get(ref), '1uF' if pin in (44, 45) else '100nF')
                self.assertEqual(self.pads.get((ref, '1')), self.pads['U_MCU', str(pin)])
                self.assertEqual(self.pads.get((ref, '2')), 'GND')
        for signal in ('DM', 'DP'):
            ref = f'R_USB_{signal}'
            with self.subTest(resistor=ref):
                self.assertEqual(values.get(ref), '27R')
                self.assertEqual(self.pads.get((ref, '1')), f'USB_{signal}')
                self.assertEqual(self.pads.get((ref, '2')), f'USB_{signal}_PORT')

    def test_duplicate_pad_control(self):
        with self.assertRaisesRegex(ValueError, 'duplicate pad'):
            parse(self.text.replace('(node (ref "U_MCU") (pin "1"))',
                  '(node (ref "U_MCU") (pin "1"))\n      (node (ref "U_MCU") (pin "1"))'))


if __name__ == '__main__':
    unittest.main()
