
#!/usr/bin/env python3
"""Ground-station RF link-budget model for 2.4 GHz uplink and 433 MHz downlink.
Run standalone: python3 docs/analysis/ground_station_rf_model.py
"""
import math, json, sys

C = 299.792458e6  # m/s

# --- Antenna helpers ---
def dish_gain_dbi(diameter_m, freq_hz, efficiency=0.55):
    """Parabolic dish gain from aperture efficiency."""
    lam = C / freq_hz
    return 10.0 * math.log10(efficiency * (math.pi * diameter_m / lam) ** 2)

def dish_hpbw_deg(diameter_m, freq_hz):
    """Approximate half-power beamwidth (deg) for a uniformly illuminated circular aperture."""
    lam = C / freq_hz
    return 70.0 * lam / diameter_m

# --- Propagation ---
def fspl_db(dist_km, freq_mhz):
    return 20.0 * math.log10(dist_km) + 20.0 * math.log10(freq_mhz) + 32.45

# --- Links ---
def uplink_margin(dist_km, tx_dbm, tx_ant_dbi, tx_feed_loss, point_loss, extra_loss,
                  rx_ant_dbi, rx_cable_loss, sens_dbm):
    eirp = tx_dbm - tx_feed_loss + tx_ant_dbi
    rx_power = eirp - fspl_db(dist_km, 2400) - extra_loss - point_loss + rx_ant_dbi - rx_cable_loss
    return {"eirp_dbm": eirp, "rx_dbm": rx_power, "margin_db": rx_power - sens_dbm}

def downlink_margin(dist_km, tx_dbm, tx_ant_dbi, tx_feed_loss,
                    rx_ant_dbi, rx_cable_loss, sens_dbm):
    eirp = tx_dbm + tx_ant_dbi - tx_feed_loss
    rx_power = eirp - fspl_db(dist_km, 433) + rx_ant_dbi - rx_cable_loss
    return {"eirp_dbm": eirp, "rx_dbm": rx_power, "margin_db": rx_power - sens_dbm}

def pointing_error_from_gps_uncertainty(ground_gps_m, balloon_gps_m, slant_range_m):
    """Worst-case pointing error if both GPS fixes have independent error circles."""
    return math.degrees(math.sqrt(ground_gps_m**2 + balloon_gps_m**2) / slant_range_m)

def azimuth_rate_required(track_rate_elev_deg_per_s, elevation_deg):
    """Azimuth rate = azimuth velocity / cos(elevation) for constant line-of-sight motion."""
    return track_rate_elev_deg_per_s / math.cos(math.radians(elevation_deg))

def coax_loss_db(loss_db_per_m, length_m):
    return loss_db_per_m * length_m

if __name__ == "__main__":
    print("Dish gain / HPBW table")
    for d in [0.6, 0.9, 1.2, 1.5]:
        print(f"D={d:.1f}m  433MHz G={dish_gain_dbi(d,433e6):.1f} dBi HPBW={dish_hpbw_deg(d,433e6):.1f} deg | "
              f"2400MHz G={dish_gain_dbi(d,2400e6):.1f} dBi HPBW={dish_hpbw_deg(d,2400e6):.1f} deg")

    print("\nFSPL:")
    for dist in [50, 100, 200, 500, 650]:
        print(f"  {dist}km  433MHz={fspl_db(dist,433):.1f} dB  2400MHz={fspl_db(dist,2400):.1f} dB")
