"""Independent physical pin oracle; isolated real generator (no source netlist writes)."""
import unittest
import test_boot_core as core


class USBProgramming(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        core.BootCore.setUpClass.__func__(cls)

    pins = core.BootCore.pins

    def test_connector_esd(self):
        self.assertEqual(self.pins('J_USB'), {'1':'USB_VBUS', '2':'USB_DM_PORT', '3':'USB_DP_PORT', '5':'GND', '6':'GND'})
        self.assertEqual(self.parts['J_USB'], ('1050170001', 'Connector_USB:USB_Micro-B_Molex-105017-0001'))
        self.assertEqual(self.pins('U_USB_ESD'), {'1':'USB_DM_PORT', '6':'USB_DM_PORT', '3':'USB_DP_PORT', '4':'USB_DP_PORT', '2':'GND', '5':'USB_VBUS'})
        self.assertEqual(self.parts['U_USB_ESD'], ('USBLC6-2SC6', 'Package_TO_SOT_SMD:SOT-23-6'))
        for signal, pad in [('DM','46'), ('DP','47')]:
            self.assertEqual(self.pads['U_MCU',pad], 'USB_'+signal)
            self.assertEqual(self.pins('R_USB_'+signal), {'1':'USB_'+signal, '2':'USB_'+signal+'_PORT'})
            self.assertEqual(self.parts['R_USB_'+signal][0], '27R')

    def test_boot_reset(self):
        self.assertEqual(self.pins('R_BOOTSEL'), {'1':'QSPI_SS', '2':'BOOTSEL_SW'})
        self.assertEqual(self.parts['R_BOOTSEL'][0], '1k')
        for ref, net in [('SW_BOOTSEL','BOOTSEL_SW'), ('SW_RESET','RUN')]:
            self.assertEqual(self.pins(ref), {'1':net, '2':'GND'})
            self.assertEqual(self.parts[ref], ('PTS636 SK25 SMTR LFS', 'Button_Switch_SMD:SW_Tactile_SPST_NO_Straight_CK_PTS636Sx25SMTRLFS'))
        self.assertEqual(self.pads['U_MCU','56'], 'QSPI_SS')
        self.assertEqual(self.pads['U_MCU','26'], 'RUN')
        self.assertEqual(self.pins('R_RUN'), {'1':'+3V3_MCU', '2':'RUN'})

    def test_power_isolation(self):
        # Exact ownership prevents VBUS being attached to buck/LDO or GPIO clamps.
        self.assertEqual({rp for rp,n in self.pads.items() if n == 'USB_VBUS'}, {('J_USB','1'), ('U_USB_ESD','5')})
        self.assertEqual(self.pins('U_LDO'), {'1':'+5V_PCBA','2':'GND','3':'+5V_PCBA','5':'+3V3_MCU'})

    def test_fault_controls(self):
        original = self.pads
        for ref,pin,wrong,check in [
            ('J_USB','2','USB_DP_PORT',self.test_connector_esd),
            ('J_USB','5','USB_VBUS',self.test_connector_esd),
            ('J_USB','6','USB_VBUS',self.test_connector_esd),
            ('U_USB_ESD','2','USB_VBUS',self.test_connector_esd),
            ('U_USB_ESD','6','USB_DP_PORT',self.test_connector_esd),
            ('R_BOOTSEL','1','RUN',self.test_boot_reset),
            ('SW_BOOTSEL','1','QSPI_SS',self.test_boot_reset),
            ('SW_RESET','2','+3V3_MCU',self.test_boot_reset),
            ('U_LDO','1','USB_VBUS',self.test_power_isolation),
            ('J_USB','1','+5V_PCBA',self.test_power_isolation),
        ]:
            with self.subTest(ref=ref,pin=pin):
                self.pads = dict(original)
                self.pads[ref,pin] = wrong
                with self.assertRaises(AssertionError):
                    check()
        self.pads = original

if __name__ == '__main__':
    unittest.main()
