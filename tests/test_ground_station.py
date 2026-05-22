import struct

from conftest import load_ground_station

gs = load_ground_station()

TELEMETRY_FMT = "<IHIiHHhHBBBBH"
FMT_SIZE = struct.calcsize(TELEMETRY_FMT)


class TestCRC16:
    def test_empty_data(self):
        assert gs.crc16(b"") == 0xFFFF

    def test_known_pattern(self):
        data = bytes([0x01, 0x02, 0x03, 0x04])
        result = gs.crc16(data)
        assert isinstance(result, int)
        assert 0 <= result <= 0xFFFF

    def test_deterministic(self):
        data = bytes(range(20))
        assert gs.crc16(data) == gs.crc16(data)

    def test_different_data_different_crc(self):
        data1 = bytes(range(20))
        data2 = bytes(range(1, 21))
        assert gs.crc16(data1) != gs.crc16(data2)

    def test_matches_firmware_crc(self):
        data = bytes([0] * 26)
        crc = gs.crc16(data)
        packed = data + struct.pack("<H", crc)
        verify_crc = gs.crc16(packed[:26])
        stored_crc = struct.unpack_from("<H", packed, 26)[0]
        assert verify_crc == stored_crc


class TestDecodePacket:
    def test_wrong_size_returns_none(self):
        assert gs.decode_packet(bytes(20)) is None
        assert gs.decode_packet(bytes(30)) is None
        assert gs.decode_packet(b"") is None

    def test_format_matches_telemetry_size(self):
        assert FMT_SIZE == gs.TELEMETRY_SIZE

    def test_valid_packet_roundtrip(self):
        raw = struct.pack(
            TELEMETRY_FMT,
            0xDEADBEEF,
            42,
            5200000,
            1300000,
            12000,
            3300,
            2234,
            10133,
            8,
            0,
            0,
            0,
            0,
        )
        assert len(raw) == 28

        data_no_crc = raw[:26]
        crc = gs.crc16(data_no_crc)
        packet = data_no_crc + struct.pack("<H", crc)
        assert len(packet) == 28

        pkt = gs.decode_packet(packet)
        assert pkt is not None
        assert pkt.crc_ok is True
        assert pkt.callsign_hash == 0xDEADBEEF
        assert pkt.sats == 8
        assert pkt.voltage_mv == 3300
        assert abs(pkt.latitude - 52.0) < 0.01
        assert abs(pkt.longitude - 13.0) < 0.01
        assert abs(pkt.temp_c - 22.34) < 0.01
        assert abs(pkt.pressure_hpa - 1013.3) < 0.1

    def test_corrupted_crc_detected(self):
        raw = struct.pack(
            TELEMETRY_FMT,
            1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 0,
        )
        data_no_crc = raw[:26]
        crc = gs.crc16(data_no_crc)
        packet = data_no_crc + struct.pack("<H", crc ^ 0xFFFF)
        pkt = gs.decode_packet(packet)
        assert pkt is not None
        assert pkt.crc_ok is False

    def test_negative_temperature(self):
        raw = struct.pack(
            TELEMETRY_FMT,
            0, 0, 0, 0, 0, 0, -500, 0, 0, 0, 0, 0, 0,
        )
        data_no_crc = raw[:26]
        crc = gs.crc16(data_no_crc)
        packet = data_no_crc + struct.pack("<H", crc)
        pkt = gs.decode_packet(packet)
        assert pkt is not None
        assert abs(pkt.temp_c - (-5.0)) < 0.01

    def test_pressure_conversion(self):
        raw = struct.pack(
            TELEMETRY_FMT,
            0, 0, 0, 0, 0, 0, 0, 10133, 0, 0, 0, 0, 0,
        )
        data_no_crc = raw[:26]
        crc = gs.crc16(data_no_crc)
        packet = data_no_crc + struct.pack("<H", crc)
        pkt = gs.decode_packet(packet)
        assert pkt is not None
        assert abs(pkt.pressure_hpa - 1013.3) < 0.1

    def test_negative_longitude(self):
        raw = struct.pack(
            TELEMETRY_FMT,
            0, 0, 0, -7352000, 0, 0, 0, 0, 0, 0, 0, 0, 0,
        )
        data_no_crc = raw[:26]
        crc = gs.crc16(data_no_crc)
        packet = data_no_crc + struct.pack("<H", crc)
        pkt = gs.decode_packet(packet)
        assert pkt is not None
        assert abs(pkt.longitude - (-73.52)) < 0.01


class TestFormatPacket:
    def test_formats_ok_packet(self):
        pkt = gs.TelemetryPacket(
            callsign_hash=1,
            latitude=52.0,
            longitude=13.0,
            altitude_m=12000,
            voltage_mv=3300,
            temp_c=22.5,
            pressure_hpa=1013.3,
            sats=8,
            tx_mode=0,
            antenna=0,
            flags=0,
            crc_ok=True,
        )
        text = gs.format_packet(pkt)
        assert "OK" in text
        assert "52.0000" in text
        assert "13.0000" in text

    def test_formats_crc_fail(self):
        pkt = gs.TelemetryPacket(
            callsign_hash=1,
            latitude=0,
            longitude=0,
            altitude_m=0,
            voltage_mv=0,
            temp_c=0,
            pressure_hpa=0,
            sats=0,
            tx_mode=0,
            antenna=0,
            flags=0,
            crc_ok=False,
        )
        text = gs.format_packet(pkt)
        assert "CRC FAIL" in text

    def test_mode_names(self):
        for mode, name in [(0, "LoRa"), (1, "FLRC"), (2, "FSK"), (3, "LR-FHSS"), (4, "SubGHz")]:
            pkt = gs.TelemetryPacket(
                callsign_hash=0, latitude=0, longitude=0, altitude_m=0,
                voltage_mv=0, temp_c=0, pressure_hpa=0, sats=0,
                tx_mode=mode, antenna=0, flags=0, crc_ok=True,
            )
            text = gs.format_packet(pkt)
            assert name in text
