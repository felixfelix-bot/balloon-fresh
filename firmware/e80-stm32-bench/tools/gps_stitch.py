#!/usr/bin/env python3
"""gps_stitch.py — stitch GPS track points onto RX packet log by nearest timestamp.

Distributed range tests produce an rx-log.csv with one row per received packet
(see e80_bench_ctl.RxLogWriter). Each row has either:

  - ``captured_ts``  — ISO-8601 wall-clock timestamp written by the host when
    the packet row was emitted (e.g. ``2026-08-23T20:06:09``). This is the
    preferred join key because it is already in the same time frame as a GPS
    track recorded on a phone.
  - ``ts_ms``        — firmware uptime in milliseconds (since board boot).
    Not wall-clock aligned; only usable if ``--t0-epoch`` is supplied to map
    uptime onto absolute time.

GPS data may arrive as:

  - GPX (XML)  — produced by phone tracker apps (e.g. OsmAnd, GPX Tracker,
    Strava, Komoot). Parsed with stdlib xml.etree.
  - CSV        — columns auto-detected by header name. Recognised column
    names: ``timestamp``/``time``/``ts``/``datetime``, ``lat``/``latitude``,
    ``lon``/``lng``/``longitude``, ``ele``/``elevation``/``alt``.

Output: a combined CSV that preserves all RX columns and appends
``gps_lat``, ``gps_lon``, ``gps_ele``, ``gps_time``, ``gps_offset_s``
(seconds between packet timestamp and matched GPS fix), and if
``--tx-gps lat,lon`` is given, ``dist_m`` — haversine distance from the TX
reference to the matched GPS point.

Usage:
    python3 gps_stitch.py --rx rx-log.csv --gps track.gpx
    python3 gps_stitch.py --rx rx-log.csv --gps track.gpx --tx-gps 52.0123,4.0456
    python3 gps_stitch.py --rx rx-log.csv --gps gps.csv --out combined.csv
    python3 gps_stitch.py --rx rx-log.csv --gps track.gpx --t0-epoch 1724438400
"""
from __future__ import annotations

import argparse
import bisect
import csv
import math
import os
import sys
import xml.etree.ElementTree as ET
from datetime import datetime, timezone

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

EARTH_RADIUS_M = 6_371_000.0  # mean Earth radius (WGS84 approximate)

# RX CSV timestamp columns, in preference order. ``captured_ts`` is wall-clock
# (preferred). ``ts_ms`` is firmware-uptime ms (needs --t0-epoch).
RX_TS_COLS = ("captured_ts", "ts_ms")

# GPS CSV column-name aliases. First match in each group wins.
GPS_TIME_ALIASES = ("timestamp", "time", "ts", "datetime", "date_time", "utc")
GPS_LAT_ALIASES = ("lat", "latitude", "gps_lat")
GPS_LON_ALIASES = ("lon", "lng", "longitude", "gps_lon", "lng_deg", "long")
GPS_ELE_ALIASES = ("ele", "elevation", "alt", "altitude", "gps_ele")

# ---------------------------------------------------------------------------
# Haversine
# ---------------------------------------------------------------------------

def haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance between two lat/lon points, in metres."""
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlam = math.radians(lon2 - lon1)
    a = (
        math.sin(dphi / 2.0) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(dlam / 2.0) ** 2
    )
    return 2.0 * EARTH_RADIUS_M * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))


# ---------------------------------------------------------------------------
# Timestamp parsing — robust to ISO-8601 variants with/without Z/offset
# ---------------------------------------------------------------------------

def parse_iso_to_epoch(text: str) -> float | None:
    """Parse an ISO-8601 timestamp string to epoch seconds (UTC).

    Handles:
      - 2026-08-23T20:06:09Z
      - 2026-08-23T20:06:09.123Z
      - 2026-08-23T20:06:09+00:00
      - 2026-08-23T20:06:09
      - 2026-08-23 20:06:09  (space separator)
      - 1724438769  (integer epoch, pass-through)
      - 1724438769.5 (float epoch, pass-through)

    Returns None if the string cannot be parsed.
    """
    if text is None:
        return None
    s = text.strip()
    if not s:
        return None

    # Pure numeric → epoch seconds
    try:
        return float(s)
    except ValueError:
        pass

    # Normalise: replace space separator with 'T'
    if "T" not in s and " " in s:
        s = s.replace(" ", "T", 1)

    # Strip trailing 'Z' — fromisoformat() in 3.11+ handles 'Z' but older
    # Pythons (3.7-3.10) do not. Be safe.
    has_z = s.endswith("Z")
    if has_z:
        s = s[:-1]

    # Try with tz offset
    try:
        dt = datetime.fromisoformat(s)
    except ValueError:
        return None

    if has_z or dt.tzinfo is None:
        # Treat as UTC if there was a Z, or if naive (RX host writes local
        # time without tz — but the GPS phone clock and the host clock must
        # be in the same frame for the join to work). For naive timestamps
        # we assume both RX and GPS use the same frame so the offset cancels
        # out; tying both to UTC is the safest default.
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.timestamp()


# ---------------------------------------------------------------------------
# GPS parsers
# ---------------------------------------------------------------------------

class GpsPoint:
    """One GPS track fix."""
    __slots__ = ("epoch", "lat", "lon", "ele", "time_str")

    def __init__(self, epoch: float, lat: float, lon: float,
                 ele: float | None, time_str: str | None = None):
        self.epoch = epoch
        self.lat = lat
        self.lon = lon
        self.ele = ele
        self.time_str = time_str


def parse_gpx(path: str) -> list[GpsPoint]:
    """Parse a GPX 1.1 file and return track points sorted by time.

    Reads <trkpt> and <wpt> elements. Namespace-agnostic.
    """
    try:
        tree = ET.parse(path)
    except ET.ParseError as e:
        raise ValueError("GPX parse error: {}".format(e))
    root = tree.getroot()

    # GPX namespaces are usually xmlns="http://www.topografix.com/GPX/1/1"
    # but we don't depend on the exact URI — strip any namespace.
    def _localname(tag: str) -> str:
        return tag.rsplit("}", 1)[-1] if "}" in tag else tag

    pts: list[GpsPoint] = []
    for node in root.iter():
        if _localname(node.tag) not in ("trkpt", "wpt"):
            continue
        lat = node.get("lat")
        lon = node.get("lon")
        if lat is None or lon is None:
            continue
        try:
            lat_f = float(lat)
            lon_f = float(lon)
        except ValueError:
            continue
        ele = None
        time_str = None
        for child in node:
            ln = _localname(child.tag)
            if ln == "ele":
                try:
                    ele = float(child.text)  # type: ignore[arg-type]
                except (TypeError, ValueError):
                    pass
            elif ln == "time":
                time_str = (child.text or "").strip()
        if time_str is None:
            # Some GPX files omit <time> inside trkpt but carry it at
            # metadata level — skip those points for time-based join.
            continue
        epoch = parse_iso_to_epoch(time_str)
        if epoch is None:
            continue
        pts.append(GpsPoint(epoch, lat_f, lon_f, ele, time_str))

    pts.sort(key=lambda p: p.epoch)
    return pts


def parse_gps_csv(path: str) -> list[GpsPoint]:
    """Parse a GPS CSV file. Column names auto-detected from header row."""
    with open(path, newline="", errors="replace") as f:
        reader = csv.DictReader(f)
        if reader.fieldnames is None:
            raise ValueError("GPS CSV has no header row")
        names_lower = {n.lower(): n for n in reader.fieldnames}

        def find_col(aliases):
            for a in aliases:
                if a in names_lower:
                    return names_lower[a]
            return None

        tcol = find_col(GPS_TIME_ALIASES)
        latcol = find_col(GPS_LAT_ALIASES)
        loncol = find_col(GPS_LON_ALIASES)
        elecol = find_col(GPS_ELE_ALIASES)

        if not tcol:
            raise ValueError(
                "GPS CSV missing timestamp column. Looked for one of: "
                "{}".format(", ".join(GPS_TIME_ALIASES))
            )
        if not latcol or not loncol:
            raise ValueError(
                "GPS CSV missing lat/lon columns. Looked for lat aliases: "
                "{}, lon aliases: {}".format(
                    ", ".join(GPS_LAT_ALIASES), ", ".join(GPS_LON_ALIASES),
                )
            )

        pts: list[GpsPoint] = []
        for row in reader:
            epoch = parse_iso_to_epoch(row[tcol] or "")
            if epoch is None:
                continue
            try:
                lat = float(row[latcol])
                lon = float(row[loncol])
            except (TypeError, ValueError):
                continue
            ele = None
            if elecol:
                try:
                    ele = float(row[elecol])
                except (TypeError, ValueError):
                    pass
            pts.append(GpsPoint(epoch, lat, lon, ele, row[tcol]))

    pts.sort(key=lambda p: p.epoch)
    return pts


def load_gps(path: str) -> list[GpsPoint]:
    """Load a GPS file, auto-detecting format from extension/content."""
    ext = os.path.splitext(path)[1].lower()
    if ext == ".gpx":
        return parse_gpx(path)
    if ext in (".csv", ".tsv"):
        return parse_gps_csv(path)

    # .txt or unknown extension: sniff content. XML declaration or <gpx
    # root → GPX, else CSV.
    try:
        with open(path, "rb") as f:
            head = f.read(512).lstrip()
        if head.startswith(b"<?xml") or head.startswith(b"<gpx"):
            return parse_gpx(path)
    except OSError:
        pass
    return parse_gps_csv(path)


# ---------------------------------------------------------------------------
# RX log loading
# ---------------------------------------------------------------------------

def load_rx_log(path: str) -> list[dict]:
    """Load RX CSV log, skipping '#' metadata comments. Returns list of rows."""
    with open(path, newline="", errors="replace") as f:
        reader = csv.DictReader(ln for ln in f if not ln.lstrip().startswith("#"))
        rows = list(reader)
    return rows


def rx_timestamp_epoch(row: dict, ts_col: str,
                       t0_epoch: float | None) -> float | None:
    """Convert an RX row's timestamp column to epoch seconds.

    For ``captured_ts`` (ISO wall-clock) → parsed directly.
    For ``ts_ms`` (firmware uptime) → t0_epoch + ts_ms/1000.
    """
    raw = row.get(ts_col)
    if raw is None or raw == "":
        return None

    if ts_col == "ts_ms":
        # Firmware uptime in ms. Needs t0_epoch to anchor.
        if t0_epoch is None:
            return None
        try:
            return float(t0_epoch) + float(raw) / 1000.0
        except (TypeError, ValueError):
            return None

    # ISO timestamp path
    return parse_iso_to_epoch(raw)


def pick_rx_ts_col(rows: list[dict], t0_epoch: float | None,
                   explicit_col: str | None) -> str:
    """Decide which RX timestamp column to use.

    Preference: explicit override > captured_ts (wall-clock) > ts_ms
    (needs --t0-epoch).
    """
    if explicit_col:
        return explicit_col
    if not rows:
        # No data — assume captured_ts by default
        return "captured_ts"
    header = set(rows[0].keys())
    if "captured_ts" in header:
        return "captured_ts"
    if "ts_ms" in header and t0_epoch is not None:
        return "ts_ms"
    if "captured_ts" in RX_TS_COLS and "captured_ts" in header:
        return "captured_ts"
    if "ts_ms" in header:
        # Best effort: caller will see a warning later
        return "ts_ms"
    raise ValueError(
        "RX log has no recognised timestamp column. Expected one of: "
        "{}".format(", ".join(RX_TS_COLS))
    )


# ---------------------------------------------------------------------------
# Nearest-timestamp join (bisect)
# ---------------------------------------------------------------------------

def nearest_gps(epoch: float, gps_epochs: list[float],
               gps_pts: list[GpsPoint]) -> tuple[GpsPoint | None, float]:
    """Find the GPS point whose timestamp is nearest ``epoch``.

    Returns (point, offset_seconds) where offset = epoch - point.epoch.
    Returns (None, inf) if the GPS list is empty.
    """
    if not gps_pts:
        return None, float("inf")
    idx = bisect.bisect_left(gps_epochs, epoch)
    best = None
    best_off = float("inf")
    # Check idx-1 and idx (the two candidates that bracket epoch)
    for i in (idx - 1, idx):
        if 0 <= i < len(gps_pts):
            off = abs(epoch - gps_epochs[i])
            if off < best_off:
                best_off = off
                best = gps_pts[i]
    return best, (epoch - best.epoch if best is not None else float("inf"))


# ---------------------------------------------------------------------------
# Main stitch routine
# ---------------------------------------------------------------------------

OUTPUT_EXTRA_COLS = (
    "gps_lat", "gps_lon", "gps_ele", "gps_time", "gps_offset_s", "dist_m",
)


def stitch(rx_rows: list[dict], gps_pts: list[GpsPoint],
           ts_col: str, t0_epoch: float | None,
           tx_lat: float | None = None, tx_lon: float | None = None,
           max_gap_s: float = 30.0,
           ) -> list[dict]:
    """Join RX rows with nearest GPS points by timestamp.

    Returns a new list of dicts: original RX columns + OUTPUT_EXTRA_COLS.
    GPS columns are empty strings when no GPS data is available or the
    nearest point is farther than ``max_gap_s`` seconds away (a warning is
    emitted once per row in that case).
    """
    gps_epochs = [p.epoch for p in gps_pts]
    warned_gap = False
    out: list[dict] = []

    for row in rx_rows:
        epoch = rx_timestamp_epoch(row, ts_col, t0_epoch)
        new = dict(row)
        if epoch is None:
            for c in OUTPUT_EXTRA_COLS:
                new[c] = ""
            out.append(new)
            continue
        pt, off = nearest_gps(epoch, gps_epochs, gps_pts)
        if pt is None:
            for c in OUTPUT_EXTRA_COLS:
                new[c] = ""
            out.append(new)
            continue
        if abs(off) > max_gap_s and not warned_gap:
            sys.stderr.write(
                "WARNING: nearest GPS point is {:.0f}s away from packet "
                "(col={}, value={}). Consider --max-gap-s or check clock "
                "sync.\n".format(off, ts_col, row.get(ts_col))
            )
            warned_gap = True
        new["gps_lat"] = "{:.6f}".format(pt.lat)
        new["gps_lon"] = "{:.6f}".format(pt.lon)
        new["gps_ele"] = "" if pt.ele is None else "{:.2f}".format(pt.ele)
        new["gps_time"] = pt.time_str or ""
        new["gps_offset_s"] = "{:.3f}".format(off)
        if tx_lat is not None and tx_lon is not None and pt is not None:
            d = haversine(tx_lat, tx_lon, pt.lat, pt.lon)
            new["dist_m"] = "{:.1f}".format(d)
        else:
            new["dist_m"] = ""
        out.append(new)
    return out


def write_combined_csv(rows: list[dict], out_path: str) -> None:
    """Write rows to CSV. Columns = original RX columns + OUTPUT_EXTRA_COLS."""
    if not rows:
        # Empty — still write a header
        with open(out_path, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(OUTPUT_EXTRA_COLS)
        return
    # Preserve RX column order; append extras (de-dup if RX already had them)
    base_cols = list(rows[0].keys())
    extra = [c for c in OUTPUT_EXTRA_COLS if c not in base_cols]
    fieldnames = base_cols + extra
    with open(out_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames,
                                extrasaction="ignore")
        writer.writeheader()
        for r in rows:
            writer.writerow(r)


def parse_latlon(s: str) -> tuple[float, float]:
    """Parse 'lat,lon' string."""
    parts = s.split(",")
    if len(parts) != 2:
        raise argparse.ArgumentTypeError(
            "expected 'lat,lon' (two numbers separated by comma)"
        )
    try:
        return float(parts[0].strip()), float(parts[1].strip())
    except ValueError:
        raise argparse.ArgumentTypeError(
            "expected 'lat,lon' (two numbers separated by comma)"
        )


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        prog="gps_stitch.py",
        description="Stitch GPS track points onto RX packet log by nearest "
                    "timestamp.",
    )
    parser.add_argument("--rx", required=True,
                        help="RX packet CSV log (rx-log.csv format)")
    parser.add_argument("--gps", required=True,
                        help="GPS file: GPX (XML) or CSV with lat/lon/time "
                             "columns")
    parser.add_argument("--out", default=None,
                        help="Output combined CSV path (default: "
                             "<rx-stem>_gps.csv)")
    parser.add_argument("--tx-gps", type=parse_latlon, default=None,
                        metavar="LAT,LON",
                        help="TX reference location for distance calculation "
                             "(e.g. 52.0123,4.0456). Adds dist_m column.")
    parser.add_argument("--t0-epoch", type=float, default=None,
                        metavar="EPOCH",
                        help="If RX log only has ts_ms (firmware uptime), "
                             "supply T0 as unix epoch seconds to map uptime "
                             "to wall-clock.")
    parser.add_argument("--ts-col", default=None,
                        help="Explicit RX timestamp column to use "
                             "(default: captured_ts if present, else ts_ms "
                             "with --t0-epoch)")
    parser.add_argument("--max-gap-s", type=float, default=30.0,
                        metavar="SECONDS",
                        help="Warn if nearest GPS point is farther than this "
                             "many seconds from a packet's timestamp "
                             "(default: 30)")
    args = parser.parse_args(argv)

    if not os.path.exists(args.rx):
        print("ERROR: RX log not found: {}".format(args.rx), file=sys.stderr)
        return 1
    if not os.path.exists(args.gps):
        print("ERROR: GPS file not found: {}".format(args.gps),
              file=sys.stderr)
        return 1

    # --- Load RX ---
    rx_rows = load_rx_log(args.rx)
    if not rx_rows:
        print("ERROR: RX log {} has no data rows".format(args.rx),
              file=sys.stderr)
        return 1
    print("[gps_stitch] Loaded {} RX packet rows from {}".format(
        len(rx_rows), args.rx))

    # --- Decide timestamp column ---
    try:
        ts_col = pick_rx_ts_col(rx_rows, args.t0_epoch, args.ts_col)
    except ValueError as e:
        print("ERROR: {}".format(e), file=sys.stderr)
        return 1
    if ts_col == "ts_ms" and args.t0_epoch is None:
        print("ERROR: RX log only has ts_ms (firmware uptime); pass "
              "--t0-epoch EPOCH to map to wall-clock time.", file=sys.stderr)
        return 1
    print("[gps_stitch] Using RX timestamp column: {}".format(ts_col))

    # --- Load GPS ---
    gps_pts = load_gps(args.gps)
    if not gps_pts:
        print("ERROR: No GPS track points found in {}".format(args.gps),
              file=sys.stderr)
        return 1
    print("[gps_stitch] Loaded {} GPS track points from {}".format(
        len(gps_pts), args.gps))

    # --- Stitch ---
    tx_lat = args.tx_gps[0] if args.tx_gps else None
    tx_lon = args.tx_gps[1] if args.tx_gps else None
    combined = stitch(rx_rows, gps_pts, ts_col, args.t0_epoch,
                      tx_lat=tx_lat, tx_lon=tx_lon,
                      max_gap_s=args.max_gap_s)

    # --- Write ---
    if args.out is None:
        stem = os.path.splitext(args.rx)[0]
        args.out = "{}_gps.csv".format(stem)
    write_combined_csv(combined, args.out)
    print("[gps_stitch] Wrote {} rows to {}".format(len(combined), args.out))

    # --- Summary ---
    n_with_gps = sum(1 for r in combined if r.get("gps_lat"))
    if tx_lat is not None:
        dists = [float(r["dist_m"]) for r in combined
                 if r.get("dist_m") not in (None, "")]
        if dists:
            print("[gps_stitch] Distance from TX: min={:.0f}m "
                  "max={:.0f}m mean={:.0f}m".format(
                      min(dists), max(dists),
                      sum(dists) / len(dists)))
    print("[gps_stitch] {} / {} rows matched to GPS".format(
        n_with_gps, len(combined)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
