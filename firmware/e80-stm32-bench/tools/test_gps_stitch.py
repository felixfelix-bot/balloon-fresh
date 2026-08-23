#!/usr/bin/env python3
"""Host tests for gps_stitch.py — no hardware required.

Run:  python3 -m pytest test_gps_stitch.py -v
  or: python3 -m unittest test_gps_stitch -v

Covers:
  - GPX (XML) parsing with namespaces + <ele>/<time> elements
  - GPS CSV column auto-detection (lat/lon/time aliases)
  - Nearest-timestamp join (bisect) including boundary cases
  - Haversine distance formula (known vectors)
  - RX timestamp column selection (captured_ts vs ts_ms + t0_epoch)
  - Output CSV format and columns
  - ISO-8601 timestamp parser robustness
"""
import csv
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import gps_stitch as gs  # noqa: E402


# ---------------------------------------------------------------------------
# Sample data builders
# ---------------------------------------------------------------------------

SAMPLE_GPX = """<?xml version="1.0" encoding="UTF-8"?>
<gpx version="1.1" creator="OsmAnd" xmlns="http://www.topografix.com/GPX/1/1">
  <metadata><name>walk</name></metadata>
  <trk>
    <name>walk</name>
    <trkseg>
      <trkpt lat="52.0123" lon="4.0456">
        <ele>5.2</ele>
        <time>2026-08-23T20:06:00Z</time>
      </trkpt>
      <trkpt lat="52.0124" lon="4.0457">
        <ele>5.4</ele>
        <time>2026-08-23T20:06:05Z</time>
      </trkpt>
      <trkpt lat="52.0126" lon="4.0459">
        <ele>5.6</ele>
        <time>2026-08-23T20:06:10Z</time>
      </trkpt>
      <trkpt lat="52.0130" lon="4.0463">
        <ele>6.0</ele>
        <time>2026-08-23T20:06:15Z</time>
      </trkpt>
    </trkseg>
  </trk>
</gpx>
"""

SAMPLE_GPX_NO_NS = """<?xml version="1.0"?>
<gpx version="1.1">
  <trk><trkseg>
    <trkpt lat="10.0" lon="20.0">
      <ele>100.0</ele>
      <time>2026-08-23T20:00:00Z</time>
    </trkpt>
    <trkpt lat="10.1" lon="20.1">
      <ele>101.0</ele>
      <time>2026-08-23T20:00:10Z</time>
    </trkpt>
  </trkseg></trk>
</gpx>
"""

# ---------------------------------------------------------------------------
# KML sample — BasicAirData GPS Logger (Android) export shape:
#   - <name>GPS Logger YYYYMMDD-HHMMSS</name>      → start time
#   - <description>... Duration = MM:SS | MM:SS ... → total | moving duration
#   - <Placemark><LineString><coordinates>          → lon,lat,alt triples
# KML coordinates carry NO per-point timestamps — they must be synthesised
# by distributing N points evenly across the total duration starting at the
# start time.
# ---------------------------------------------------------------------------

SAMPLE_KML = """<?xml version="1.0" encoding="UTF-8"?>
<!-- Created with BasicAirData GPS Logger for Android - ver. 3.3.0 -->
<!-- Track 3 = 3 TrackPoints + 0 Placemarks -->
<kml xmlns="http://www.opengis.net/kml/2.2">
 <Document>
  <name>GPS Logger 20260823-184605</name>
  <description><![CDATA[Test track
3 Trackpoints + 0 Placemarks]]></description>
  <Style id="TrackStyle">
   <LineStyle>
    <color>ff0000ff</color>
    <width>3</width>
   </LineStyle>
  </Style>

  <Placemark id="20260823-184605">
   <name>Track 20260823-184605</name>
   <description><![CDATA[<b>Test track</b><br><br>Distance = 25 m<br>Duration = 00:15 | 00:02<br>Altitude Gap = 3 m<br>Max Speed = 2 km/h<br>Direction = W <br><br><i>3 Trackpoints</i>]]></description>
   <styleUrl>#TrackStyle</styleUrl>
   <LineString>
    <extrude>0</extrude>
    <tessellate>0</tessellate>
    <altitudeMode>absolute</altitudeMode>
    <coordinates>
     -16.94707431,32.63487728,76.231
     -16.94717201,32.63486183,78.954
     -16.94720912,32.63486070,79.323
    </coordinates>
   </LineString>
  </Placemark>

 </Document>
</kml>
"""


def write_temp(content, suffix=".gpx"):
    fd, path = tempfile.mkstemp(suffix=suffix)
    with os.fdopen(fd, "w") as f:
        f.write(content)
    return path


def write_rx_log(rows):
    cols = ["session", "config", "pkt_idx", "ts_ms", "rssi_dbm", "snr_db",
            "crc_ok", "bit_err", "freq_hz", "mod", "sf_or_br", "bw",
            "pa_dbm", "len", "pcrc16", "captured_ts"]
    path = tempfile.mktemp(suffix=".csv")
    with open(path, "w", newline="") as f:
        f.write(",".join(cols) + "\n")
        for r in rows:
            f.write(",".join(str(r.get(c, "")) for c in cols) + "\n")
    return path


# ---------------------------------------------------------------------------
# Haversine formula
# ---------------------------------------------------------------------------

class TestHaversine(unittest.TestCase):
    """Haversine distance — known reference vectors."""

    def test_same_point_zero(self):
        self.assertAlmostEqual(gs.haversine(52, 4, 52, 4), 0.0, places=6)

    def test_one_degree_latitude(self):
        # ~111 km per degree latitude
        d = gs.haversine(0.0, 0.0, 1.0, 0.0)
        self.assertAlmostEqual(d, 111_194.9, places=0)

    def test_one_degree_longitude_at_equator(self):
        # ~111 km at equator
        d = gs.haversine(0.0, 0.0, 0.0, 1.0)
        self.assertAlmostEqual(d, 111_194.9, places=0)

    def test_one_degree_longitude_at_60_lat(self):
        # ~55.6 km at 60 degrees latitude
        d = gs.haversine(60.0, 0.0, 60.0, 1.0)
        self.assertAlmostEqual(d, 55_597.5, delta=2.0)

    def test_antipodal_distance(self):
        # Antipodal points → ~20015 km (half circumference)
        d = gs.haversine(0.0, 0.0, -0.0, 180.0)
        # ~20015.09 km
        self.assertGreater(d, 20_000_000)
        self.assertLess(d, 20_030_000)

    def test_symmetry(self):
        d1 = gs.haversine(52.01, 4.04, 52.03, 4.10)
        d2 = gs.haversine(52.03, 4.10, 52.01, 4.04)
        self.assertAlmostEqual(d1, d2, places=3)

    def test_known_route(self):
        # Amsterdam to Utrecht — roughly 35 km (great circle)
        d = gs.haversine(52.3702, 4.8952, 52.0907, 5.1214)
        self.assertGreater(d, 33_000)
        self.assertLess(d, 36_000)


# ---------------------------------------------------------------------------
# ISO timestamp parser
# ---------------------------------------------------------------------------

class TestParseIsoToEpoch(unittest.TestCase):

    def test_iso_with_z(self):
        e = gs.parse_iso_to_epoch("2026-08-23T20:06:09Z")
        assert e is not None
        self.assertGreater(e, 1.78e9)

    def test_iso_with_ms_z(self):
        e1 = gs.parse_iso_to_epoch("2026-08-23T20:06:09Z")
        e2 = gs.parse_iso_to_epoch("2026-08-23T20:06:09.500Z")
        assert e1 is not None and e2 is not None
        self.assertAlmostEqual(e2 - e1, 0.500, places=2)

    def test_iso_no_tz_treated_as_utc(self):
        e1 = gs.parse_iso_to_epoch("2026-08-23T20:06:09Z")
        e2 = gs.parse_iso_to_epoch("2026-08-23T20:06:09")
        assert e1 is not None and e2 is not None
        self.assertAlmostEqual(e1, e2, places=3)

    def test_space_separator(self):
        e1 = gs.parse_iso_to_epoch("2026-08-23T20:06:09Z")
        e2 = gs.parse_iso_to_epoch("2026-08-23 20:06:09")
        assert e1 is not None and e2 is not None
        self.assertAlmostEqual(e1, e2, places=3)

    def test_offset(self):
        # 20:06:09+02:00 == 18:06:09Z
        e1 = gs.parse_iso_to_epoch("2026-08-23T18:06:09Z")
        e2 = gs.parse_iso_to_epoch("2026-08-23T20:06:09+02:00")
        assert e1 is not None and e2 is not None
        self.assertAlmostEqual(e1, e2, places=3)

    def test_integer_epoch_pass_through(self):
        e = gs.parse_iso_to_epoch("1724438769")
        assert e is not None
        self.assertAlmostEqual(e, 1724438769.0, places=3)

    def test_float_epoch_pass_through(self):
        e = gs.parse_iso_to_epoch("1724438769.5")
        assert e is not None
        self.assertAlmostEqual(e, 1724438769.5, places=3)

    def test_empty_and_none(self):
        self.assertIsNone(gs.parse_iso_to_epoch(""))
        self.assertIsNone(gs.parse_iso_to_epoch(None))
        self.assertIsNone(gs.parse_iso_to_epoch("garbage"))

    def test_round_trip_consistent(self):
        # Two points 5s apart in any format should be 5s apart when parsed
        pts = [
            ("2026-08-23T20:06:00Z", "2026-08-23T20:06:05Z"),
            ("2026-08-23T20:06:00", "2026-08-23T20:06:05"),
            ("2026-08-23 20:06:00", "2026-08-23 20:06:05"),
        ]
        for a, b in pts:
            ea = gs.parse_iso_to_epoch(a)
            eb = gs.parse_iso_to_epoch(b)
            assert ea is not None and eb is not None
            self.assertAlmostEqual(eb - ea, 5.0, places=3,
                                   msg="failed for {} / {}".format(a, b))


# ---------------------------------------------------------------------------
# GPX parsing
# ---------------------------------------------------------------------------

class TestParseGPX(unittest.TestCase):

    def test_parse_with_namespace(self):
        path = write_temp(SAMPLE_GPX, ".gpx")
        try:
            pts = gs.parse_gpx(path)
        finally:
            os.unlink(path)
        self.assertEqual(len(pts), 4)
        self.assertAlmostEqual(pts[0].lat, 52.0123, places=4)
        self.assertAlmostEqual(pts[0].lon, 4.0456, places=4)
        self.assertAlmostEqual(pts[0].ele, 5.2, places=2)
        self.assertEqual(pts[0].time_str, "2026-08-23T20:06:00Z")

    def test_parse_without_namespace(self):
        path = write_temp(SAMPLE_GPX_NO_NS, ".gpx")
        try:
            pts = gs.parse_gpx(path)
        finally:
            os.unlink(path)
        self.assertEqual(len(pts), 2)
        self.assertAlmostEqual(pts[0].lat, 10.0, places=4)

    def test_sorted_by_time(self):
        # Build a GPX with out-of-order points
        gpx = """<?xml version="1.0"?>
<gpx><trk><trkseg>
<trkpt lat="3.0" lon="3.0"><time>2026-08-23T20:06:30Z</time></trkpt>
<trkpt lat="1.0" lon="1.0"><time>2026-08-23T20:06:00Z</time></trkpt>
<trkpt lat="2.0" lon="2.0"><time>2026-08-23T20:06:15Z</time></trkpt>
</trkseg></trk></gpx>
"""
        path = write_temp(gpx, ".gpx")
        try:
            pts = gs.parse_gpx(path)
        finally:
            os.unlink(path)
        self.assertEqual(len(pts), 3)
        self.assertListEqual([p.lat for p in pts], [1.0, 2.0, 3.0])

    def test_skips_missing_time(self):
        # trkpt without <time> cannot be used for time-based join
        gpx = """<?xml version="1.0"?>
<gpx><trk><trkseg>
<trkpt lat="1.0" lon="1.0"><time>2026-08-23T20:06:00Z</time></trkpt>
<trkpt lat="2.0" lon="2.0"><ele>10.0</ele></trkpt>
</trkseg></trk></gpx>"""
        path = write_temp(gpx, ".gpx")
        try:
            pts = gs.parse_gpx(path)
        finally:
            os.unlink(path)
        self.assertEqual(len(pts), 1)
        self.assertAlmostEqual(pts[0].lat, 1.0)

    def test_includes_waypoints(self):
        # <wpt> elements outside <trk> should also be included
        gpx = """<?xml version="1.0"?>
<gpx>
<wpt lat="51.0" lon="3.0"><ele>1.0</ele><time>2026-08-23T20:06:00Z</time></wpt>
<trk><trkseg>
<trkpt lat="52.0" lon="4.0"><time>2026-08-23T20:06:05Z</time></trkpt>
</trkseg></trk>
</gpx>"""
        path = write_temp(gpx, ".gpx")
        try:
            pts = gs.parse_gpx(path)
        finally:
            os.unlink(path)
        self.assertEqual(len(pts), 2)
        lats = sorted(p.lat for p in pts)
        self.assertListEqual(lats, [51.0, 52.0])

    def test_no_trkpt(self):
        path = write_temp("<gpx></gpx>", ".gpx")
        try:
            pts = gs.parse_gpx(path)
        finally:
            os.unlink(path)
        self.assertEqual(pts, [])

    def test_invalid_xml_raises(self):
        path = write_temp("<gpx><trk><oops></gpx>", ".gpx")
        try:
            with self.assertRaises(ValueError):
                gs.parse_gpx(path)
        finally:
            os.unlink(path)


# ---------------------------------------------------------------------------
# KML parsing (BasicAirData GPS Logger for Android)
# ---------------------------------------------------------------------------

class TestParseKML(unittest.TestCase):
    """KML parsing — coordinates + synthesised timestamps.

    KML tracks from BasicAirData GPS Logger have NO per-point timestamps:
      - start time is in the <name> element: "GPS Logger YYYYMMDD-HHMMSS"
      - total duration in the Placemark <description>:
        "Duration = MM:SS | MM:SS"  (total | moving)
      - trackpoints are lon,lat,alt triples inside <LineString>/<coordinates>
    """

    def test_parse_kml_basic(self):
        """Parse a simple KML — coordinate order preserves lon,lat,alt."""
        path = write_temp(SAMPLE_KML, ".kml")
        try:
            pts = gs.parse_kml(path)
        finally:
            os.unlink(path)
        self.assertEqual(len(pts), 3)
        # KML order is lon,lat,alt — verify no swap with GPX lat-first order
        self.assertAlmostEqual(pts[0].lon, -16.94707431, places=5)
        self.assertAlmostEqual(pts[0].lat, 32.63487728, places=5)
        self.assertAlmostEqual(pts[0].ele, 76.231, places=3)
        self.assertAlmostEqual(pts[1].lon, -16.94717201, places=5)
        self.assertAlmostEqual(pts[2].lon, -16.94720912, places=5)
        # Each synthesised point carries an ISO time_str like GPX
        for p in pts:
            self.assertIsNotNone(p.time_str)
            self.assertRegex(p.time_str, r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")

    def test_parse_kml_synthesizes_timestamps(self):
        """Verify synthesised timestamps are evenly distributed."""
        path = write_temp(SAMPLE_KML, ".kml")
        try:
            pts = gs.parse_kml(path)
        finally:
            os.unlink(path)
        # Total duration 00:15 = 15 s; 3 points → step = 15/(3-1) = 7.5 s
        # Both gaps must be exactly equal (even distribution).
        self.assertAlmostEqual(pts[1].epoch - pts[0].epoch, 7.5, places=2)
        self.assertAlmostEqual(pts[2].epoch - pts[1].epoch, 7.5, places=2)
        # First point falls exactly on the start time
        expected_start = gs.parse_iso_to_epoch("2026-08-23T18:46:05Z")
        assert expected_start is not None
        self.assertAlmostEqual(pts[0].epoch, expected_start, places=2)
        # Last point falls on start + duration
        self.assertAlmostEqual(pts[-1].epoch,
                               expected_start + 15.0, places=2)

    def test_parse_kml_name_timestamp(self):
        """Verify start time extraction from "GPS Logger 20260823-184605"."""
        path = write_temp(SAMPLE_KML, ".kml")
        try:
            pts = gs.parse_kml(path)
        finally:
            os.unlink(path)
        expected_start = gs.parse_iso_to_epoch("2026-08-23T18:46:05Z")
        assert expected_start is not None
        self.assertAlmostEqual(pts[0].epoch, expected_start, places=2)
        # The Placemark <name> "Track 20260823-184605" must NOT win — only
        # "GPS Logger ..." is a valid start-time anchor.
        wrong_start = gs.parse_iso_to_epoch("2026-08-23T20:46:05Z")
        assert wrong_start is not None
        self.assertNotAlmostEqual(pts[0].epoch, wrong_start, places=1)

    def test_parse_kml_duration(self):
        """Verify duration parsing from "Duration = 00:15 | 00:02".

        Format is "MM:SS | MM:SS" = total | moving. We use the total
        (first) value to span the N synthesised points.
        """
        path = write_temp(SAMPLE_KML, ".kml")
        try:
            pts = gs.parse_kml(path)
        finally:
            os.unlink(path)
        # Total = 00:15 = 15 s; full range = pts[-1] - pts[0]
        self.assertAlmostEqual(pts[-1].epoch - pts[0].epoch, 15.0, places=2)
        # Moving-only = 2 s would give step 1 s; verify we did NOT pick that
        # (would be range 2.0, not 15.0).
        self.assertNotAlmostEqual(pts[-1].epoch - pts[0].epoch, 2.0, places=1)

    def test_parse_kml_no_coordinates_returns_empty(self):
        """A KML with valid metadata but no coordinates yields []."""
        empty_kml = """<?xml version="1.0"?>
<kml xmlns="http://www.opengis.net/kml/2.2">
 <Document>
  <name>GPS Logger 20260823-184605</name>
  <description>no trackpoints yet</description>
 </Document>
</kml>"""
        path = write_temp(empty_kml, ".kml")
        try:
            pts = gs.parse_kml(path)
        finally:
            os.unlink(path)
        self.assertEqual(pts, [])

    def test_parse_kml_invalid_xml_raises(self):
        path = write_temp("<kml><Placemark><oops></kml>", ".kml")
        try:
            with self.assertRaises(ValueError):
                gs.parse_kml(path)
        finally:
            os.unlink(path)

    def test_parse_kml_with_real_sample(self):
        """Round-trip on the real BasicAirData export we were given.

        File lives at ~/.hermes/profiles/manager/cache/documents/ and has
        a .bin extension despite being KML. This exercises auto-detection
        via XML root-tag sniffing AND verifies real-world parsing.
        """
        sample_path = os.path.join(
            os.path.expanduser("~"),
            ".hermes/profiles/manager/cache/documents/"
            "doc_28c1ff25f72f_.bin",
        )
        if not os.path.exists(sample_path):
            self.skipTest("Real KML sample not available: " + sample_path)
        # Explicit format hint forces KML parser despite .bin extension
        pts = gs.parse_kml(sample_path)
        self.assertEqual(len(pts), 30)
        # Verify lon,lat,alt come through for the first point
        self.assertAlmostEqual(pts[0].lon, -16.94707431, places=5)
        self.assertAlmostEqual(pts[0].lat, 32.63487728, places=5)
        self.assertAlmostEqual(pts[0].ele, 76.231, places=3)
        # Timestamps must be strictly increasing
        for i in range(len(pts) - 1):
            self.assertGreater(pts[i + 1].epoch, pts[i].epoch)
        # Total duration 00:29 = 29 s; spread across 30 points
        self.assertAlmostEqual(pts[-1].epoch - pts[0].epoch,
                              29.0, places=1)
        # All timestamps are in 2026 (epoch > 1.7e9)
        for p in pts:
            self.assertGreater(p.epoch, 1.7e9)

    def test_stitch_kml_with_rx(self):
        """End-to-end: KML GPS joined to RX packet log by timestamp."""
        tmpdir = tempfile.mkdtemp()
        rx_path = None
        try:
            rx_path = write_rx_log([
                {"pkt_idx": 0, "ts_ms": 0, "rssi_dbm": -80,
                 "captured_ts": "2026-08-23T18:46:05Z"},
                {"pkt_idx": 1, "ts_ms": 5000, "rssi_dbm": -82,
                 "captured_ts": "2026-08-23T18:46:13Z"},
                {"pkt_idx": 2, "ts_ms": 8000, "rssi_dbm": -85,
                 "captured_ts": "2026-08-23T18:46:20Z"},
            ])
            gps_path = os.path.join(tmpdir, "track.kml")
            with open(gps_path, "w") as f:
                f.write(SAMPLE_KML)
            rx_rows = gs.load_rx_log(rx_path)
            gps_pts = gs.load_gps(gps_path)
            combined = gs.stitch(rx_rows, gps_pts, "captured_ts", None)
            self.assertEqual(len(combined), 3)
            for r in combined:
                self.assertTrue(r["gps_lat"])
            # First packet lands exactly on the first synthesised GPS point
            self.assertAlmostEqual(
                float(combined[0]["gps_lat"]), 32.63487728, places=3)
            self.assertAlmostEqual(
                float(combined[0]["gps_offset_s"]), 0.0, places=1)
            # Middle packet at +13 s falls between pt1 (+7.5s) and pt2 (+15s)
            # → nearest is pt2 (off = -2.0s)
            self.assertAlmostEqual(
                float(combined[1]["gps_lat"]), 32.63486070, places=3)
        finally:
            import shutil
            shutil.rmtree(tmpdir, ignore_errors=True)
            if rx_path and os.path.exists(rx_path):
                os.unlink(rx_path)


# ---------------------------------------------------------------------------
# GPS CSV parsing
# ---------------------------------------------------------------------------

class TestParseGpsCSV(unittest.TestCase):
    """GPS CSV column auto-detection."""

    def _write(self, header, rows):
        path = tempfile.mktemp(suffix=".csv")
        with open(path, "w", newline="") as f:
            f.write(",".join(header) + "\n")
            for r in rows:
                f.write(",".join(str(c) for c in r) + "\n")
        return path

    def test_basic_parse(self):
        header = ["timestamp", "lat", "lon", "ele"]
        rows = [
            ["2026-08-23T20:06:00Z", "52.0", "4.0", "5.0"],
            ["2026-08-23T20:06:05Z", "52.1", "4.1", "6.0"],
        ]
        path = self._write(header, rows)
        try:
            pts = gs.parse_gps_csv(path)
        finally:
            os.unlink(path)
        self.assertEqual(len(pts), 2)
        self.assertAlmostEqual(pts[0].lat, 52.0)
        self.assertAlmostEqual(pts[0].ele, 5.0)

    def test_alias_columns(self):
        # Use a mix of aliases (latitude, longitude, elevation, time)
        header = ["time", "latitude", "longitude", "elevation"]
        rows = [
            ["2026-08-23T20:06:00Z", "1.0", "2.0", "10.0"],
        ]
        path = self._write(header, rows)
        try:
            pts = gs.parse_gps_csv(path)
        finally:
            os.unlink(path)
        self.assertEqual(len(pts), 1)
        self.assertAlmostEqual(pts[0].lat, 1.0)
        self.assertAlmostEqual(pts[0].lon, 2.0)
        self.assertAlmostEqual(pts[0].ele, 10.0)

    def test_lng_alias(self):
        header = ["timestamp", "lat", "lng"]
        rows = [["2026-08-23T20:06:00Z", "1.0", "2.0"]]
        path = self._write(header, rows)
        try:
            pts = gs.parse_gps_csv(path)
        finally:
            os.unlink(path)
        self.assertEqual(len(pts), 1)
        self.assertAlmostEqual(pts[0].lon, 2.0)

    def test_sorted_by_time(self):
        header = ["time", "lat", "lon"]
        rows = [
            ["2026-08-23T20:06:30Z", "3.0", "3.0"],
            ["2026-08-23T20:06:00Z", "1.0", "1.0"],
            ["2026-08-23T20:06:15Z", "2.0", "2.0"],
        ]
        path = self._write(header, rows)
        try:
            pts = gs.parse_gps_csv(path)
        finally:
            os.unlink(path)
        self.assertListEqual([p.lat for p in pts], [1.0, 2.0, 3.0])

    def test_skips_bad_lat(self):
        header = ["timestamp", "lat", "lon"]
        rows = [
            ["2026-08-23T20:06:00Z", "1.0", "2.0"],
            ["2026-08-23T20:06:05Z", "nope", "3.0"],
        ]
        path = self._write(header, rows)
        try:
            pts = gs.parse_gps_csv(path)
        finally:
            os.unlink(path)
        self.assertEqual(len(pts), 1)

    def test_skips_bad_timestamp(self):
        header = ["timestamp", "lat", "lon"]
        rows = [
            ["2026-08-23T20:06:00Z", "1.0", "2.0"],
            ["not_a_time", "5.0", "6.0"],
        ]
        path = self._write(header, rows)
        try:
            pts = gs.parse_gps_csv(path)
        finally:
            os.unlink(path)
        self.assertEqual(len(pts), 1)

    def test_missing_timestamp_col_raises(self):
        path = self._write(["lat", "lon"], [["1.0", "2.0"]])
        try:
            with self.assertRaises(ValueError):
                gs.parse_gps_csv(path)
        finally:
            os.unlink(path)

    def test_missing_lat_col_raises(self):
        path = self._write(["timestamp", "lon"], [["2026-08-23T20:06:00Z", "2.0"]])
        try:
            with self.assertRaises(ValueError):
                gs.parse_gps_csv(path)
        finally:
            os.unlink(path)

    def test_no_ele_col_gives_none(self):
        path = self._write(["time", "lat", "lon"],
                           [["2026-08-23T20:06:00Z", "1.0", "2.0"]])
        try:
            pts = gs.parse_gps_csv(path)
        finally:
            os.unlink(path)
        self.assertEqual(len(pts), 1)
        self.assertIsNone(pts[0].ele)

    def test_epoch_timestamp(self):
        path = self._write(["timestamp", "lat", "lon"],
                           [["1724438769", "1.0", "2.0"]])
        try:
            pts = gs.parse_gps_csv(path)
        finally:
            os.unlink(path)
        self.assertEqual(len(pts), 1)
        self.assertAlmostEqual(pts[0].epoch, 1724438769.0, places=3)


class TestLoadGpsAutoDetect(unittest.TestCase):

    def test_gpx_extension(self):
        path = write_temp(SAMPLE_GPX_NO_NS, ".gpx")
        try:
            pts = gs.load_gps(path)
        finally:
            os.unlink(path)
        self.assertEqual(len(pts), 2)

    def test_csv_extension(self):
        path = tempfile.mktemp(suffix=".csv")
        with open(path, "w", newline="") as f:
            f.write("timestamp,lat,lon\n")
            f.write("2026-08-23T20:06:00Z,1.0,2.0\n")
        try:
            pts = gs.load_gps(path)
        finally:
            os.unlink(path)
        self.assertEqual(len(pts), 1)
        self.assertAlmostEqual(pts[0].lat, 1.0)

    def test_unknown_extension_sniffs_xml(self):
        path = write_temp(SAMPLE_GPX_NO_NS, ".txt")
        try:
            pts = gs.load_gps(path)
        finally:
            os.unlink(path)
        self.assertEqual(len(pts), 2)

    def test_auto_detect_kml(self):
        """A .kml extension triggers the KML parser (3 points/15 s)."""
        path = write_temp(SAMPLE_KML, ".kml")
        try:
            pts = gs.load_gps(path)
        finally:
            os.unlink(path)
        self.assertEqual(len(pts), 3)
        # KML-specific signature: synthesised timestamps evenly spaced
        self.assertAlmostEqual(pts[1].epoch - pts[0].epoch, 7.5, places=2)
        # First point is at the "GPS Logger 20260823-184605" start time
        expected = gs.parse_iso_to_epoch("2026-08-23T18:46:05Z")
        assert expected is not None
        self.assertAlmostEqual(pts[0].epoch, expected, places=2)

    def test_auto_detect_gpx(self):
        """A .gpx extension still triggers the GPX parser (unchanged)."""
        path = write_temp(SAMPLE_GPX_NO_NS, ".gpx")
        try:
            pts = gs.load_gps(path)
        finally:
            os.unlink(path)
        # GPX returns time_str from the file verbatim; KML synthesises a
        # "Z"-suffixed string. Verify the GPX timestamp round-trips.
        self.assertEqual(len(pts), 2)
        self.assertEqual(pts[0].time_str, "2026-08-23T20:00:00Z")

    def test_unknown_extension_kml_sniffs_xml_root(self):
        """No extension hint — fall back to XML root-tag sniffing for KML."""
        path = write_temp(SAMPLE_KML, ".bin")
        try:
            pts = gs.load_gps(path)
        finally:
            os.unlink(path)
        self.assertEqual(len(pts), 3)
        expected = gs.parse_iso_to_epoch("2026-08-23T18:46:05Z")
        assert expected is not None
        self.assertAlmostEqual(pts[0].epoch, expected, places=2)


# ---------------------------------------------------------------------------
# Nearest-timestamp join
# ---------------------------------------------------------------------------

class TestNearestGps(unittest.TestCase):
    """Bisect-based nearest neighbour lookup."""

    def setUp(self):
        # 4 GPS points at 0, 5, 10, 15 seconds past epoch 1000
        self.pts = [
            gs.GpsPoint(1000.0, 52.0, 4.0, 5.0, "t0"),
            gs.GpsPoint(1005.0, 52.1, 4.1, 6.0, "t1"),
            gs.GpsPoint(1010.0, 52.2, 4.2, 7.0, "t2"),
            gs.GpsPoint(1015.0, 52.3, 4.3, 8.0, "t3"),
        ]
        self.epochs = [p.epoch for p in self.pts]

    def test_exact_match(self):
        pt, off = gs.nearest_gps(1005.0, self.epochs, self.pts)
        self.assertIsNotNone(pt)
        self.assertEqual(pt.lat, 52.1)
        self.assertAlmostEqual(off, 0.0)

    def test_between_two_points(self):
        # Exactly mid-way — should pick the earlier (bisect_left)
        pt, off = gs.nearest_gps(1007.5, self.epochs, self.pts)
        self.assertIsNotNone(pt)
        # Midway: equal distance to 1005 (off=+2.5) and 1010 (off=-2.5)
        # Both are equidistant — implementation may pick either
        self.assertIn(pt.lat, (52.1, 52.2))
        self.assertAlmostEqual(abs(off), 2.5, places=2)

    def test_just_before_first(self):
        pt, off = gs.nearest_gps(998.0, self.epochs, self.pts)
        self.assertIsNotNone(pt)
        self.assertEqual(pt.lat, 52.0)
        self.assertAlmostEqual(off, 998.0 - 1000.0)

    def test_just_after_last(self):
        pt, off = gs.nearest_gps(1020.0, self.epochs, self.pts)
        self.assertIsNotNone(pt)
        self.assertEqual(pt.lat, 52.3)
        self.assertAlmostEqual(off, 1020.0 - 1015.0)

    def test_closer_to_later(self):
        pt, off = gs.nearest_gps(1009.0, self.epochs, self.pts)
        self.assertIsNotNone(pt)
        self.assertEqual(pt.lat, 52.2)
        self.assertAlmostEqual(off, 1009.0 - 1010.0)

    def test_empty_gps_returns_none(self):
        pt, off = gs.nearest_gps(1000.0, [], [])
        self.assertIsNone(pt)
        self.assertEqual(off, float("inf"))


# ---------------------------------------------------------------------------
# RX timestamp column selection
# ---------------------------------------------------------------------------

class TestPickRxTsCol(unittest.TestCase):

    def test_prefers_captured_ts(self):
        rows = [{"captured_ts": "2026-08-23T20:06:09", "ts_ms": "100"}]
        col = gs.pick_rx_ts_col(rows, t0_epoch=None, explicit_col=None)
        self.assertEqual(col, "captured_ts")

    def test_uses_ts_ms_with_t0(self):
        rows = [{"ts_ms": "100"}]
        col = gs.pick_rx_ts_col(rows, t0_epoch=1000.0, explicit_col=None)
        self.assertEqual(col, "ts_ms")

    def test_explicit_override(self):
        rows = [{"captured_ts": "x", "ts_ms": "y"}]
        col = gs.pick_rx_ts_col(rows, t0_epoch=None, explicit_col="ts_ms")
        self.assertEqual(col, "ts_ms")

    def test_no_ts_col_raises(self):
        rows = [{"rssi": "-80"}]
        with self.assertRaises(ValueError):
            gs.pick_rx_ts_col(rows, t0_epoch=None, explicit_col=None)

    def test_empty_rows_defaults_to_captured_ts(self):
        col = gs.pick_rx_ts_col([], t0_epoch=None, explicit_col=None)
        self.assertEqual(col, "captured_ts")

    def test_ts_ms_without_t0_still_returned_with_warning(self):
        # When captured_ts is missing and no t0_epoch, we return ts_ms so the
        # caller can produce the "needs --t0-epoch" error
        rows = [{"ts_ms": "100"}]
        col = gs.pick_rx_ts_col(rows, t0_epoch=None, explicit_col=None)
        self.assertEqual(col, "ts_ms")


class TestRxTimestampEpoch(unittest.TestCase):

    def test_captured_ts_iso(self):
        e = gs.rx_timestamp_epoch(
            {"captured_ts": "2026-08-23T20:06:09Z"},
            "captured_ts", t0_epoch=None,
        )
        self.assertIsNotNone(e)
        self.assertGreater(e, 1.78e9)

    def test_ms_with_t0(self):
        e = gs.rx_timestamp_epoch({"ts_ms": "5000"}, "ts_ms", t0_epoch=1000.0)
        self.assertAlmostEqual(e, 1000.0 + 5.0, places=3)

    def test_ms_without_t0(self):
        e = gs.rx_timestamp_epoch({"ts_ms": "5000"}, "ts_ms", t0_epoch=None)
        self.assertIsNone(e)

    def test_missing_value(self):
        self.assertIsNone(gs.rx_timestamp_epoch({}, "captured_ts", None))

    def test_empty_value(self):
        self.assertIsNone(
            gs.rx_timestamp_epoch({"captured_ts": ""}, "captured_ts", None))


# ---------------------------------------------------------------------------
# Stitch integration
# ---------------------------------------------------------------------------

class TestStitch(unittest.TestCase):
    """End-to-end stitch + output CSV shape."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        # RX log: 3 packets at 20:06:02, 20:06:07, 20:06:12 wall-clock
        self.rx_path = write_rx_log([
            {"session": 1, "config": 0, "pkt_idx": 0, "ts_ms": 100,
             "rssi_dbm": -80.0, "captured_ts": "2026-08-23T20:06:02Z"},
            {"session": 1, "config": 0, "pkt_idx": 1, "ts_ms": 200,
             "rssi_dbm": -82.0, "captured_ts": "2026-08-23T20:06:07Z"},
            {"session": 1, "config": 0, "pkt_idx": 2, "ts_ms": 300,
             "rssi_dbm": -85.0, "captured_ts": "2026-08-23T20:06:12Z"},
        ])
        # GPS GPX: points at 20:06:00, 20:06:05, 20:06:10, 20:06:15
        self.gpx_path = os.path.join(self.tmpdir, "track.gpx")
        with open(self.gpx_path, "w") as f:
            f.write(SAMPLE_GPX)

    def tearDown(self):
        import shutil
        for p in (self.rx_path, self.gpx_path):
            if os.path.exists(p):
                pass  # will be removed by rmtree below
        shutil.rmtree(self.tmpdir, ignore_errors=True)
        # rx_path lives outside tmpdir
        if os.path.exists(self.rx_path) and os.path.dirname(self.rx_path) != self.tmpdir:
            os.unlink(self.rx_path)

    def test_stitch_adds_gps_columns(self):
        rx_rows = gs.load_rx_log(self.rx_path)
        gps_pts = gs.load_gps(self.gpx_path)
        combined = gs.stitch(rx_rows, gps_pts, "captured_ts", None)
        self.assertEqual(len(combined), 3)
        for r in combined:
            self.assertIn("gps_lat", r)
            self.assertIn("gps_lon", r)
            self.assertIn("gps_ele", r)
            self.assertIn("gps_time", r)
            self.assertIn("gps_offset_s", r)
        # Latitudes from the 4-point GPX (20:06:00, 20:06:05, 20:06:10, 20:06:15
        # at lat 52.0123, 52.0124, 52.0126, 52.0130). The three RX packets at
        # 02, 07, 12 should match 00 (off +2s), 05 (off +2s), 10 (off +2s).
        self.assertAlmostEqual(float(combined[0]["gps_lat"]), 52.0123,
                               places=3)
        self.assertAlmostEqual(float(combined[1]["gps_lat"]), 52.0124,
                               places=3)
        self.assertAlmostEqual(float(combined[2]["gps_lat"]), 52.0126,
                               places=3)
        for r in combined:
            self.assertAlmostEqual(float(r["gps_offset_s"]), 2.0, places=2)

    def test_stitch_with_tx_distance(self):
        rx_rows = gs.load_rx_log(self.rx_path)
        gps_pts = gs.load_gps(self.gpx_path)
        combined = gs.stitch(rx_rows, gps_pts, "captured_ts", None,
                             tx_lat=52.0, tx_lon=4.0)
        for r in combined:
            self.assertTrue(r["dist_m"])
            d = float(r["dist_m"])
            # TX at (52.0, 4.0); GPS at ~(52.0123, 4.0456). Haversine
            # ≈ sqrt((0.0123*111195)^2 + (0.0456*111195*cos(52))^2) ≈ 3400m
            self.assertGreater(d, 3000)
            self.assertLess(d, 3600)

    def test_stitch_ts_ms_with_t0_epoch(self):
        # Build an RX log with ts_ms only anchored at the first GPS fix epoch
        gps_pts = gs.load_gps(self.gpx_path)
        t0 = gps_pts[0].epoch  # = 20:06:00 UTC
        rx_path = write_rx_log([
            {"pkt_idx": 0, "ts_ms": "0", "captured_ts": "",
             "rssi_dbm": -80},
            {"pkt_idx": 1, "ts_ms": "5000", "captured_ts": "",
             "rssi_dbm": -82},
            {"pkt_idx": 2, "ts_ms": "15000", "captured_ts": "",
             "rssi_dbm": -85},
        ])
        try:
            rx_rows = gs.load_rx_log(rx_path)
            # Force ts_ms column
            combined = gs.stitch(rx_rows, gps_pts, "ts_ms", t0_epoch=t0)
            self.assertAlmostEqual(float(combined[0]["gps_lat"]), 52.0123,
                                  places=3)
            # ts_ms=15000 → 20:06:15 → matches the 4th point
            self.assertAlmostEqual(float(combined[2]["gps_lat"]), 52.0130,
                                  places=3)
            self.assertAlmostEqual(float(combined[2]["gps_offset_s"]), 0.0,
                                   places=2)
        finally:
            os.unlink(rx_path)

    def test_stitch_empty_gps_gives_blank(self):
        rx_rows = gs.load_rx_log(self.rx_path)
        combined = gs.stitch(rx_rows, [], "captured_ts", None)
        for r in combined:
            self.assertEqual(r.get("gps_lat", ""), "")
            self.assertEqual(r.get("dist_m", ""), "")

    def test_output_csv_format(self):
        rx_rows = gs.load_rx_log(self.rx_path)
        gps_pts = gs.load_gps(self.gpx_path)
        combined = gs.stitch(rx_rows, gps_pts, "captured_ts", None,
                             tx_lat=52.0, tx_lon=4.0)
        out_path = os.path.join(self.tmpdir, "combined.csv")
        gs.write_combined_csv(combined, out_path)
        with open(out_path, newline="") as f:
            reader = csv.DictReader(f)
            rows = list(reader)
        self.assertEqual(len(rows), 3)
        # All original + GPS columns present in header
        for col in ("session", "config", "pkt_idx", "ts_ms", "rssi_dbm",
                    "captured_ts", "gps_lat", "gps_lon", "gps_ele",
                    "gps_time", "gps_offset_s", "dist_m"):
            self.assertIn(col, reader.fieldnames)
        # Values preserved
        self.assertEqual(rows[0]["pkt_idx"], "0")
        self.assertEqual(rows[0]["rssi_dbm"], "-80.0")
        # GPS added
        self.assertNotEqual(rows[0]["gps_lat"], "")
        self.assertNotEqual(rows[0]["dist_m"], "")

    def test_output_csv_preserves_order(self):
        # Column order: RX cols first, then GPS extras
        rx_rows = gs.load_rx_log(self.rx_path)
        gps_pts = gs.load_gps(self.gpx_path)
        combined = gs.stitch(rx_rows, gps_pts, "captured_ts", None)
        out_path = os.path.join(self.tmpdir, "out.csv")
        gs.write_combined_csv(combined, out_path)
        with open(out_path) as f:
            header = f.readline().strip().split(",")
        # RX columns come before GPS extras
        rx_idx = header.index("captured_ts")
        gps_idx = header.index("gps_lat")
        self.assertLess(rx_idx, gps_idx)

    def test_empty_output_writes_header(self):
        out_path = os.path.join(self.tmpdir, "empty.csv")
        gs.write_combined_csv([], out_path)
        with open(out_path) as f:
            header = f.readline().strip()
        self.assertIn("gps_lat", header)


# ---------------------------------------------------------------------------
# Lat/lon arg parser
# ---------------------------------------------------------------------------

class TestParseLatLon(unittest.TestCase):

    def test_basic(self):
        lat, lon = gs.parse_latlon("52.0123,4.0456")
        self.assertAlmostEqual(lat, 52.0123)
        self.assertAlmostEqual(lon, 4.0456)

    def test_with_spaces(self):
        lat, lon = gs.parse_latlon("52.0123, 4.0456")
        self.assertAlmostEqual(lat, 52.0123)
        self.assertAlmostEqual(lon, 4.0456)

    def test_negative(self):
        lat, lon = gs.parse_latlon("-33.8688,-151.2093")
        self.assertAlmostEqual(lat, -33.8688)
        self.assertAlmostEqual(lon, -151.2093)

    def test_rejects_git_style(self):
        import argparse
        with self.assertRaises(argparse.ArgumentTypeError):
            gs.parse_latlon("52.0.4")

    def test_rejects_single_number(self):
        import argparse
        with self.assertRaises(argparse.ArgumentTypeError):
            gs.parse_latlon("52.0")


# ---------------------------------------------------------------------------
# CLI end-to-end (main)
# ---------------------------------------------------------------------------

class TestCLI(unittest.TestCase):
    """Smoke test gps_stitch.main() with temp files."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.rx_path = write_rx_log([
            {"pkt_idx": 0, "ts_ms": 100, "rssi_dbm": -80,
             "captured_ts": "2026-08-23T20:06:02Z"},
            {"pkt_idx": 1, "ts_ms": 200, "rssi_dbm": -82,
             "captured_ts": "2026-08-23T20:06:07Z"},
        ])
        self.gpx_path = os.path.join(self.tmpdir, "track.gpx")
        with open(self.gpx_path, "w") as f:
            f.write(SAMPLE_GPX)
        self.out_path = os.path.join(self.tmpdir, "combined.csv")

    def tearDown(self):
        for p in (self.rx_path, self.gpx_path, self.out_path):
            if os.path.exists(p):
                os.unlink(p)
        if os.path.isdir(self.tmpdir):
            os.rmdir(self.tmpdir)

    def test_main_runs(self):
        rc = gs.main(["--rx", self.rx_path, "--gps", self.gpx_path,
                      "--out", self.out_path,
                      "--tx-gps", "52.0,4.0"])
        self.assertEqual(rc, 0)
        self.assertTrue(os.path.exists(self.out_path))

    def test_main_auto_out_path(self):
        # Out path defaults to <rx-stem>_gps.csv
        rc = gs.main(["--rx", self.rx_path, "--gps", self.gpx_path])
        self.assertEqual(rc, 0)
        expected_default = self.rx_path.replace(".csv", "") + "_gps.csv"
        self.assertTrue(os.path.exists(expected_default))
        os.unlink(expected_default)

    def test_main_missing_rx_file(self):
        rc = gs.main(["--rx", "/nonexistent/rx.csv", "--gps", self.gpx_path])
        self.assertEqual(rc, 1)

    def test_main_missing_gps_file(self):
        rc = gs.main(["--rx", self.rx_path, "--gps", "/nonexistent/track.gpx"])
        self.assertEqual(rc, 1)


if __name__ == "__main__":
    unittest.main()
