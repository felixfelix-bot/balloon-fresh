import json

from conftest import load_telemetry_to_nostr

tn = load_telemetry_to_nostr()


class TestEventSerialization:
    def test_serialize_event_deterministic(self):
        evt = {
            "pubkey": "00" * 32,
            "created_at": 1700000000,
            "kind": 30023,
            "tags": [["d", "test"]],
            "content": "hello",
        }
        s1 = tn.serialize_event(evt)
        s2 = tn.serialize_event(evt)
        assert s1 == s2

    def test_event_id_deterministic(self):
        evt = {
            "pubkey": "00" * 32,
            "created_at": 1700000000,
            "kind": 30023,
            "tags": [["d", "test"]],
            "content": "hello",
        }
        id1 = tn.event_id(evt)
        id2 = tn.event_id(evt)
        assert id1 == id2
        assert len(id1) == 64

    def test_different_events_different_ids(self):
        evt1 = {
            "pubkey": "00" * 32,
            "created_at": 1700000000,
            "kind": 30023,
            "tags": [["d", "test1"]],
            "content": "hello",
        }
        evt2 = {
            "pubkey": "00" * 32,
            "created_at": 1700000001,
            "kind": 30023,
            "tags": [["d", "test2"]],
            "content": "hello",
        }
        assert tn.event_id(evt1) != tn.event_id(evt2)


class TestTelemetryParsing:
    def test_parse_valid_json(self):
        line = '{"callsign_hash": 12345, "seq": 1, "latitude": 5200000, "longitude": 1300000, "altitude": 12000, "voltage_mv": 3300, "sats": 8}'
        result = tn.parse_json_telemetry(line)
        assert result is not None
        assert result["callsign_hash"] == 12345
        assert result["sats"] == 8

    def test_parse_invalid_json(self):
        result = tn.parse_json_telemetry("not json")
        assert result == {}

    def test_parse_empty_string(self):
        result = tn.parse_json_telemetry("")
        assert result == {}


class TestCreateTelemetryEvent:
    def test_creates_kind_30023(self):
        pubkey = "ab" * 32
        telemetry = {
            "callsign_hash": 12345,
            "seq": 1,
            "latitude": 5200000,
            "longitude": 1300000,
            "altitude": 12000,
            "voltage_mv": 3300,
            "sats": 8,
            "timestamp": 1700000000,
        }
        evt = tn.create_telemetry_event(pubkey, telemetry)
        assert evt["kind"] == 30023
        assert evt["pubkey"] == pubkey
        assert "id" in evt
        assert len(evt["id"]) == 64

    def test_geo_tag_with_position(self):
        pubkey = "ab" * 32
        telemetry = {
            "callsign_hash": 1,
            "seq": 1,
            "latitude": 5200000,
            "longitude": 1300000,
            "altitude": 12000,
            "voltage_mv": 3300,
            "sats": 8,
        }
        evt = tn.create_telemetry_event(pubkey, telemetry)
        geo_tags = [t for t in evt["tags"] if t[0] == "geo"]
        assert len(geo_tags) == 1
        lat_val = 5200000 / 1e5
        lon_val = 1300000 / 1e5
        assert geo_tags[0][1] == f"{lat_val:.5f},{lon_val:.5f}"

    def test_no_geo_tag_without_position(self):
        pubkey = "ab" * 32
        telemetry = {
            "callsign_hash": 1,
            "seq": 1,
            "latitude": 0,
            "longitude": 0,
            "altitude": 12000,
            "voltage_mv": 3300,
            "sats": 8,
        }
        evt = tn.create_telemetry_event(pubkey, telemetry)
        geo_tags = [t for t in evt["tags"] if t[0] == "geo"]
        assert len(geo_tags) == 0

    def test_content_is_valid_json(self):
        pubkey = "ab" * 32
        telemetry = {
            "callsign_hash": 1,
            "seq": 1,
            "latitude": 5200000,
            "longitude": 1300000,
            "altitude": 12000,
            "voltage_mv": 3300,
            "sats": 8,
        }
        evt = tn.create_telemetry_event(pubkey, telemetry)
        content = json.loads(evt["content"])
        assert content["seq"] == 1
        assert content["voltage_mv"] == 3300

    def test_d_tag_uses_callsign(self):
        pubkey = "ab" * 32
        telemetry = {
            "callsign_hash": "testhash",
            "seq": 1,
            "latitude": 0,
            "longitude": 0,
            "altitude": 0,
            "voltage_mv": 0,
            "sats": 0,
        }
        evt = tn.create_telemetry_event(pubkey, telemetry)
        d_tags = [t for t in evt["tags"] if t[0] == "d"]
        assert len(d_tags) == 1
        assert "testhash" in d_tags[0][1]


class TestSignEvent:
    def test_sign_adds_sig_field(self):
        evt = {"id": "00" * 32, "pubkey": "00" * 32}
        signed = tn.sign_event(evt, "00" * 32)
        assert "sig" in signed
