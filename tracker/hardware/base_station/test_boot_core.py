"""Far-end oracle from Winbond Rev J, Abracon drawing B, TI SBVS320D.
Runs the real generator in isolation, not against the stale placed-board netlist.
"""
import re
import unittest
import test_rp2040_pinout as rp


class BootCore(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Reuse isolated-generation fixture, not its three tests.
        rp.RP2040Pinout.setUpClass.__func__(cls)
        cls.parts = {r: (v, f) for r, v, f in re.findall(
            r'\(comp \(ref "([^"]+)"\)\s*\(value "([^"]*)"\)\s*\(footprint "([^"]*)"\)', cls.text)}

    def pins(self, ref):
        return {p: n for (r, p), n in self.pads.items() if r == ref}

    def test_single_fault_controls(self):
        # Oracle rejects each original far-end defect without touching live source.
        original = self.pads
        for ref, pin, wrong, check in [
            ('U_FLASH', '2', 'QSPI_SD0', self.test_flash),
            ('Y1', '3', 'XOUT', self.test_crystal),
            ('U_LDO', '3', 'LDO_EN', self.test_ldo),
        ]:
            with self.subTest(ref=ref):
                self.pads = dict(original)
                self.pads[ref, pin] = wrong
                with self.assertRaises(AssertionError):
                    check()
        self.pads = original

    def test_ldo(self):
        self.assertEqual(self.parts['U_LDO'], ('TLV75533PDBVR', 'Package_TO_SOT_SMD:SOT-23-5'))
        self.assertEqual(self.pins('U_LDO'), {'1':'+5V_PCBA', '2':'GND', '3':'+5V_PCBA', '5':'+3V3_MCU'})
        self.assertNotIn('LDO_EN', self.pads.values())
        for ref, net in [('C_LDO1','+3V3_MCU'), ('C_LDO2','+5V_PCBA')]:
            self.assertEqual(self.parts[ref][0], '2.2uF X7R 10V; effective >= 1uF')
            self.assertEqual(self.pins(ref), {'1':net, '2':'GND'})

    def test_crystal(self):
        self.assertEqual(self.parts['Y1'], ('ABM8-272-T3', 'Crystal:Crystal_SMD_3225-4Pin_3.2x2.5mm'))
        self.assertEqual(self.pins('Y1'), {'1':'XIN', '2':'GND', '3':'XOUT_XTAL', '4':'GND'})
        self.assertEqual(self.parts['R_XOUT'][0], '1k')
        self.assertEqual(self.pins('R_XOUT'), {'1':'XOUT', '2':'XOUT_XTAL'})
        for ref, net in [('C_X1','XIN'), ('C_X2','XOUT_XTAL')]:
            self.assertEqual(self.parts[ref][0], '15pF C0G 1% 50V')
            self.assertEqual(self.pins(ref), {'1':net, '2':'GND'})

    def test_flash(self):
        self.assertEqual(self.parts['U_FLASH'], ('W25Q16JVSSIQ', 'Package_SO:SOIC-8_5.3x5.3mm_P1.27mm'))
        self.assertEqual(self.pins('U_FLASH'), {'1':'QSPI_SS', '2':'QSPI_SD1', '3':'QSPI_SD2', '4':'GND', '5':'QSPI_SD0', '6':'QSPI_SCLK', '7':'QSPI_SD3', '8':'+3V3_MCU'})
        self.assertEqual(self.parts['C_FLASH'][0], '100nF')
        self.assertEqual(self.pins('C_FLASH'), {'1':'+3V3_MCU', '2':'GND'})
        for ref, net in [('R_FLASH_CS','QSPI_SS'), ('R_FLASH_WP','QSPI_SD2'), ('R_FLASH_HOLD','QSPI_SD3')]:
            self.assertEqual(self.parts[ref][0], '10k')
            self.assertEqual(self.pins(ref), {'1':'+3V3_MCU', '2':net})


if __name__ == '__main__':
    unittest.main()
