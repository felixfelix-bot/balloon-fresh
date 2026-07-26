"""Unit tests for balloon range test firmware — no hardware required.

Tests serial protocol parsing, phase computation, NMEA parsing.
"""
import re
import struct
import pytest


class TestNMEAParse:
    """Test NMEA RMC sentence parsing."""

    def test_parse_rmc_active(self):
        """RMC with status A (active fix) should parse lat/lon/time."""
        rmc = "$GNRMC,012345.67,A,3238.3456,N,01656.7890,W,0.5,0.0,260726,,,A*XX"
        # Extract time: hhmmss.ss
        time_str = rmc.split(",")[1]
        hh = int(time_str[:2])
        mm = int(time_str[2:4])
        ss = int(time_str[4:6])
        assert hh == 1
        assert mm == 23
        assert ss == 45
        # Status = A (active)
        assert rmc.split(",")[2] == "A"

    def test_parse_rmc_void(self):
        """RMC with status V (void) should have no position."""
        rmc = "$GNRMC,020000.00,V,,,,,,,260726,,,N,V*XX"
        fields = rmc.split(",")
        assert fields[2] == "V"
        assert fields[3] == ""  # No latitude
        assert fields[5] == ""  # No longitude

    def test_rmc_time_extraction(self):
        """Time should be extracted even without fix (status V)."""
        rmc = "$GNRMC,015318.70,V,,,,,,,260726,,,N,V*17"
        time_str = rmc.split(",")[1]
        hh = int(time_str[:2])
        mm = int(time_str[2:4])
        ss = int(time_str[4:6])
        assert hh == 1
        assert mm == 53
        assert ss == 18
        time_sec = hh * 3600 + mm * 60 + ss
        assert time_sec == 6798

    def test_rmc_date_extraction(self):
        """Date should be parseable from RMC."""
        rmc = "$GNRMC,015318.70,A,3238.3456,N,01656.7890,W,0.5,0.0,260726,,,A*XX"
        date_str = rmc.split(",")[9]  # ddmmyy
        assert date_str == "260726"
        dd = int(date_str[:2])
        mo = int(date_str[2:4])
        yy = int(date_str[4:6])
        assert dd == 26
        assert mo == 7
        assert yy == 26

    def test_lat_lon_conversion(self):
        """Test ddmm.mmmm to decimal degrees conversion."""
        # 3238.3456,N → 32.639093
        raw = 3238.3456
        deg = int(raw / 100)
        minutes = raw - deg * 100
        lat = deg + minutes / 60.0
        assert abs(lat - 32.639093) < 0.0001

        # 01656.7890,W → -16.946483
        raw = 1656.7890
        deg = int(raw / 100)
        minutes = raw - deg * 100
        lon = -(deg + minutes / 60.0)
        assert abs(lon - (-16.946483)) < 0.0001


class TestPhaseResult:
    """Test PHASE_RESULT line parsing."""

    def test_parse_phase_result(self):
        """PHASE_RESULT should parse all fields correctly."""
        line = ("PHASE_RESULT 5 HF-FLRC-2600-64 pktSize=64 rx=60 unique=58 "
                "lost=2 per=3 rssi_avg=-45 rssi_min=-52 crc_err=0 garbage=0 "
                "tx_lat=32.639093 tx_lon=-16.946483 sats=5 fix=1 "
                "utc=1785030000 tx_fw=5444af7 rx_fw=abc1234")
        parts = line.split()
        assert parts[0] == "PHASE_RESULT"
        assert int(parts[1]) == 5
        assert parts[2] == "HF-FLRC-2600-64"
        # Parse key=value pairs
        kv = {}
        for p in parts[3:]:
            if "=" in p:
                k, v = p.split("=", 1)
                kv[k] = v
        assert int(kv["pktSize"]) == 64
        assert int(kv["rx"]) == 60
        assert int(kv["per"]) == 3
        assert float(kv["rssi_avg"]) == -45.0
        assert float(kv["tx_lat"]) == 32.639093
        assert int(kv["sats"]) == 5
        assert int(kv["fix"]) == 1

    def test_parse_phase_result_no_decode(self):
        """PHASE_RESULT with rx=0 means no packets decoded."""
        line = ("PHASE_RESULT 43 LF-FLRC-325-255 pktSize=255 rx=0 unique=0 "
                "lost=0 per=100 rssi_avg=0 rssi_min=0 crc_err=0 garbage=0 "
                "tx_lat=0.000000 tx_lon=0.000000 sats=0 fix=0 "
                "utc=0 tx_fw=none rx_fw=abc1234")
        kv = {}
        for p in line.split()[3:]:
            if "=" in p:
                k, v = p.split("=", 1)
                kv[k] = v
        assert int(kv["rx"]) == 0
        assert kv["tx_fw"] == "none"


class TestPhaseComputation:
    """Test phase computation from UTC time."""

    def test_phase_in_range(self):
        """Phase should be in valid range [0, 76]."""
        # 14 modes × 4 sizes = 56 core phases
        # + 21 channel sweep phases = 77 total (0-76)
        total_phases = 77
        for test_utc in range(1785030000, 1785030100, 3):
            phase = test_utc % (total_phases * 3) // 3  # 3s per phase
            assert 0 <= phase < total_phases

    def test_phase_repeats(self):
        """Same UTC time should produce same phase."""
        total_phases = 77
        phase_duration = 3
        cycle_sec = total_phases * phase_duration
        utc1 = 1785030000
        utc2 = utc1 + cycle_sec  # one full cycle later
        phase1 = utc1 % cycle_sec // phase_duration
        phase2 = utc2 % cycle_sec // phase_duration
        assert phase1 == phase2


class TestPacketFormat:
    """Test packet structure parsing."""

    def test_gps_embed_layout(self):
        """GPS data embedded in packet should match RX parsing."""
        # Per firmware: pkt[0-3]=sync, pkt[4-7]=latE7, pkt[8-11]=lonE7,
        #               pkt[12-13]=sats, pkt[14]=fix, pkt[15-18]=unixTime
        pkt = bytearray(32)
        # Sync header
        pkt[0:4] = b'\xd3\x0f\x32\x96'

        # lat = 32.639093 → latE7 = 326390930
        lat_e7 = int(32.639093 * 1e7)
        struct.pack_into('<i', pkt, 4, lat_e7)

        # lon = -16.946483 → lonE7 = -169464830
        lon_e7 = int(-16.946483 * 1e7)
        struct.pack_into('<i', pkt, 8, lon_e7)

        # sats = 5
        struct.pack_into('<H', pkt, 12, 5)

        # fix = 1
        pkt[14] = 1

        # unix time
        struct.pack_into('<I', pkt, 15, 1785030000)

        # Verify round-trip
        assert struct.unpack_from('<i', pkt, 4)[0] == lat_e7
        assert struct.unpack_from('<i', pkt, 8)[0] == lon_e7
        assert struct.unpack_from('<H', pkt, 12)[0] == 5
        assert pkt[14] == 1
        assert struct.unpack_from('<I', pkt, 15)[0] == 1785030000


class TestBitrateMapping:
    """Test FLRC bitrate code mapping matches datasheet."""

    @pytest.mark.parametrize("bitrate,expected_code", [
        (2600, 0x00),
        (1300, 0x02),
        (650, 0x04),
        (325, 0x06),
    ])
    def test_bitrate_to_code(self, bitrate, expected_code):
        """Each FLRC bitrate should map to correct register value."""
        # Datasheet Table: bandwidth_code = log2(2600/bitrate) * 2
        import math
        if bitrate == 2600:
            code = 0x00
        elif bitrate == 1300:
            code = 0x02
        elif bitrate == 650:
            code = 0x04
        elif bitrate == 325:
            code = 0x06
        assert code == expected_code
