"""Tests for 23-field PKT line parser."""

from tools.pkt_parser import parse_pkt_line, PKT_FIELDS


class TestParsePktLine:
    """Verify 23-field PKT parser handles all field types."""

    def test_parse_23_field_line(self):
        line = "PKT,test-sess,F2600-868,1,42,12345,-87,5,1,0,0,868000000,FLRC,0,0,1,10,64,0,0,0,0,0,0"
        result = parse_pkt_line(line)
        assert result is not None
        assert result['session_id'] == "test-sess"
        assert result['config_id'] == "F2600-868"
        assert result['replicate'] == 1
        assert result['seq'] == 42
        assert result['ts_ms'] == 12345
        assert result['rssi_dbm'] == -87
        assert result['snr_db'] == 5
        assert result['crc_ok'] == 1
        assert result['freq_hz'] == 868000000
        assert result['mod'] == "FLRC"

    def test_parse_crc_fail(self):
        line = "PKT,sess,cfg,0,99,5000,-100,0,0,0,0,868000000,LORA,7,125,5,10,64,0,0,0,0,0,0"
        result = parse_pkt_line(line)
        assert result['crc_ok'] == 0
        assert result['rssi_dbm'] == -100

    def test_parse_empty_session_id(self):
        line = "PKT,,cfg,0,1,100,-80,0,1,0,0,868000000,FLRC,0,0,1,10,64,0,0,0,0,0,0"
        result = parse_pkt_line(line)
        assert result['session_id'] == ""

    def test_parse_invalid_line_returns_none(self):
        assert parse_pkt_line("NOT A PKT LINE") is None
        assert parse_pkt_line("") is None

    def test_pkt_fields_count(self):
        assert len(PKT_FIELDS) == 23

    def test_parse_gps_fields(self):
        line = "PKT,sess,cfg,0,1,100,-80,15,1,0,0,2440000000,LORA,7,125,5,10,64,3,52.5200,13.4050,35.0,12,0.8"
        result = parse_pkt_line(line)
        assert result is not None
        assert result['gps_fix'] == 3
        assert result['gps_lat'] == 52.52
        assert result['gps_lon'] == 13.405
        assert result['gps_alt'] == 35.0
        assert result['gps_sats'] == 12
        assert result['gps_hdop'] == 0.8

    def test_parse_wrong_field_count_returns_none(self):
        line = "PKT,too,few,fields"
        assert parse_pkt_line(line) is None
        line2 = "PKT," + ",".join(str(i) for i in range(30))
        assert parse_pkt_line(line2) is None