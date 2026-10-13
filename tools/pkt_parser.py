"""Parse 23-field PKT lines from firmware harmonization format.

Format (23 comma-separated fields after 'PKT,' prefix):
  PKT,<session_id>,<config_id>,<replicate>,<seq>,<ts_ms>,
      <rssi_dbm>,<snr_db>,<crc_ok>,<bit_err>,<bytes_bad>,
      <freq_hz>,<mod>,<sf>,<bw_khz>,<cr>,<power_dbm>,<pkt_size>,
      <gps_fix>,<gps_lat>,<gps_lon>,<gps_alt>,<gps_sats>,<gps_hdop>

Usage:
    from tools.pkt_parser import parse_pkt_line, PKT_FIELDS, PKT_CSV_HEADER
    pkt = parse_pkt_line("PKT,sess,cfg,0,1,100,-80,5,1,0,0,868000000,...")
    if pkt:
        print(pkt['seq'], pkt['rssi_dbm'])
"""

PKT_FIELDS = [
    'session_id', 'config_id', 'replicate', 'seq', 'ts_ms',
    'rssi_dbm', 'snr_db', 'crc_ok', 'bit_err', 'bytes_bad',
    'freq_hz', 'mod', 'sf', 'bw_khz', 'cr', 'power_dbm', 'pkt_size',
    'gps_fix', 'gps_lat', 'gps_lon', 'gps_alt', 'gps_sats', 'gps_hdop',
]

PKT_CSV_HEADER = ','.join(['timestamp_iso'] + PKT_FIELDS)

# Fields that parse to int
_INT_FIELDS = frozenset({
    'replicate', 'seq', 'ts_ms', 'freq_hz', 'sf',
    'bw_khz', 'cr', 'pkt_size', 'gps_fix', 'gps_sats',
})

# Fields that parse to int (signed)
_SINT_FIELDS = frozenset({
    'rssi_dbm', 'snr_db', 'power_dbm',
})

# Fields that parse to int (flags / counters)
_UINT_FIELDS = frozenset({
    'crc_ok', 'bit_err', 'bytes_bad',
})

# Fields that parse to float
_FLOAT_FIELDS = frozenset({
    'gps_lat', 'gps_lon', 'gps_alt', 'gps_hdop',
})


def parse_pkt_line(line: str) -> dict | None:
    """Parse a 23-field PKT line into a dictionary.

    Args:
        line: A raw line from serial output, e.g.
              "PKT,test-sess,F2600-868,1,42,12345,-87,5,1,0,0,..."

    Returns:
        dict with all 23 PKT_FIELDS keys, or None if the line
        is not a valid PKT line.
    """
    if not line or not line.startswith('PKT,'):
        return None

    parts = line[4:].strip().split(',')
    if len(parts) != 23:
        return None

    result = {}
    for i, field in enumerate(PKT_FIELDS):
        val = parts[i]

        if field in _INT_FIELDS:
            try:
                result[field] = int(val) if val else 0
            except (ValueError, TypeError):
                result[field] = 0
        elif field in _SINT_FIELDS:
            try:
                result[field] = int(val) if val else 0
            except (ValueError, TypeError):
                result[field] = 0
        elif field in _UINT_FIELDS:
            try:
                result[field] = int(val) if val else 0
            except (ValueError, TypeError):
                result[field] = 0
        elif field in _FLOAT_FIELDS:
            try:
                result[field] = float(val) if val else 0.0
            except (ValueError, TypeError):
                result[field] = 0.0
        else:
            # String fields: session_id, config_id, mod
            result[field] = val

    return result