"""Independent TI SLVSD26C pin/startup oracle; real isolated generator output."""
import unittest
import re
import test_rp2040_pinout as rp


class Buck(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        rp.RP2040Pinout.setUpClass.__func__(cls)
        cls.parts = {r: (v, f) for r, v, f in re.findall(
            r'\(comp \(ref "([^"]+)"\)\s*\(value "([^"]*)"\)\s*\(footprint "([^"]*)"\)', cls.text)}

    def pins(self, ref):
        return {p: n for (r, p), n in self.pads.items() if r == ref}

    def test_pin_startup(self):
        self.assertEqual(self.parts['U_REG'], ('TPS54202DDCR', 'Package_TO_SOT_SMD:SOT-23-6'))
        # EN intentionally unconnected: TI internal pullup enables without output power.
        self.assertEqual(self.pins('U_REG'), {'1':'GND', '2':'REG_SW', '3':'VIN_GS', '4':'REG_FB', '6':'REG_BOOT'})
        self.assertNotIn('R_EN', self.parts)
        self.assertNotIn('REG_PG', self.pads.values())  # this chip has no PG output
        self.assertEqual(self.pins('C_BOOT'), {'1':'REG_BOOT', '2':'REG_SW'})
        self.assertEqual(self.parts['C_BOOT'][0], '100nF X7R 16V')

    def test_filter_ratings(self):
        expected = {'L1':'SRP6060FA-150M 15uH +/-20%; Isat typ 5.8A; Irms typ 4.5A (20C rise); DCR max 43mOhm',
                    'R_FB1':'100k 0.1%', 'R_FB2':'13.5k 0.1%',
                    'C_IN':'22uF X7R 50V; effective >= 10uF',
                    'C_OUT':'22uF X7R 25V; effective >= 15uF',
                    'C_OUT2':'22uF X7R 25V; effective >= 15uF',
                    'C_FF':'75pF C0G 50V'}
        for ref, val in expected.items():
            self.assertEqual(self.parts.get(ref, ('missing',))[0], val)
        for ref in ('C_IN', 'C_IN_HF'):
            self.assertEqual(self.pins(ref), {'1':'VIN_GS', '2':'GND'})
        self.assertNotIn('D_REV', self.parts)
        self.assertNotIn('D_TVS', self.parts)
        for ref in ('C_OUT', 'C_OUT2'):
            self.assertEqual(self.pins(ref), {'1':'+5V_PCBA', '2':'GND'})
        self.assertEqual(self.pins('C_FF'), {'1':'+5V_PCBA', '2':'REG_FB'})
        self.assertEqual(self.pins('R_FB1'), {'1':'+5V_PCBA', '2':'REG_FB'})
        self.assertEqual(self.pins('R_FB2'), {'1':'REG_FB', '2':'GND'})
        self.assertEqual(self.pins('L1'), {'1':'REG_SW', '2':'+5V_PCBA'})
        # Independent worst-case arithmetic: min L/f including -6% jitter.
        ripple = 5*(1-5/18)/(12e-6*390e3*0.94)
        self.assertLess(1+ripple/2, 2.5)  # minimum HS limit
        low = .581*(1+100*.999/(13.5*1.001))
        high = .611*(1+100*1.001/(13.5*.999))
        self.assertGreater(low, 4.75)
        self.assertLess(high, 5.25)

    def test_single_fault_controls(self):
        original = self.pads
        for key, wrong, check in [(('U_REG','3'), '+5V_PCBA', self.test_pin_startup),
                                   (('U_REG','5'), '+5V_PCBA', self.test_pin_startup),
                                   (('C_BOOT','2'), 'GND', self.test_pin_startup),
                                   (('R_FB2','2'), '+5V_PCBA', self.test_filter_ratings)]:
            self.pads = dict(original)
            self.pads[key] = wrong
            with self.assertRaises(AssertionError):
                check()
        self.pads = original


if __name__ == '__main__':
    unittest.main()
