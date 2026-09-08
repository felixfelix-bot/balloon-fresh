#!/usr/bin/env python3
"""Ground-station validation for the E80 bench toolchain (log-don't-tune).

The GS compares the measured frequency offset against the cryo-predicted
offset (from the balloon's reported die temp + stored {k, T0} curve) in real
time and flags anomalies. It NEVER writes a tuned curve back to the balloon —
the whole point is to log everything in-flight and refine the curve
post-flight.

Design (consultant deleg_ed10cabb, source-verified):
  - The GS reference error is a CONSTANT BIAS that shifts the intercept of
    measured-offset-vs-die-temp but does NOT change the slope k. So the true
    slope is recoverable post-flight IF the balloon is never tuned in-flight.
  - Thermal lag smears the curve; GPS altitude/temp + ascent rate lets you
    model/deconvolve it. This module only flags anomalies; deconvolution is
    a post-flight analysis step.

Wire format (see RANGE-TEST-GUIDE.md):
  - Balloon TEMP line (extended): TEMP,<ts_ms>,<die_temp_raw>,<offset_hz>,
    <curve_ver>,<k_mhz_per_c>,<t0_mc>,<vcc_mv>,<gps_alt_m>,<gps_temp_c>,
    <sync_epoch_ms>
  - GS observation line: GSOBS,<ts_ms>,<measured_offset_hz>,<rssi_dbm>,
    <gs_ref_stable>,<gs_ambient_c>,<gs_lat>,<gs_lon>,<gs_alt_m>,
    <gs_vx>,<gs_vy>,<gs_vz>
"""
from __future__ import annotations

# Fixed-point scaling for the {k, T0} curve parameters logged on the wire.
# Firmware stays float-free; k is logged in mHz/°C and T0 in m°C.
K_FIXED_SCALE = 1000.0   # k: 1 Hz/°C == 1000 mHz/°C
T0_FIXED_SCALE = 1000.0  # T0: 1 °C == 1000 m°C


def k_fixed_to_float(k_mhz_per_c: int) -> float:
    """Convert a fixed-point k (mHz/°C) to Hz/°C."""
    return k_mhz_per_c / K_FIXED_SCALE


def t0_fixed_to_float(t0_mc: int) -> float:
    """Convert a fixed-point T0 (m°C) to °C."""
    return t0_mc / T0_FIXED_SCALE


def k_float_to_fixed(k_hz_per_c: float) -> int:
    """Convert a float k (Hz/°C) to fixed-point mHz/°C."""
    return int(round(k_hz_per_c * K_FIXED_SCALE))


def t0_float_to_fixed(t0_c: float) -> int:
    """Convert a float T0 (°C) to fixed-point m°C."""
    return int(round(t0_c * T0_FIXED_SCALE))


def cryo_predict_offset(die_temp_c: float, k_hz_per_c: float, t0_c: float) -> float:
    """Cryo-predicted frequency offset (Hz) from the stored {k, T0} curve.

    offset = k * (T - T0). The GS compares this against the measured offset
    in real time. A constant GS reference bias shifts the intercept but not
    the slope k, so the true slope is recoverable post-flight.
    """
    return k_hz_per_c * (die_temp_c - t0_c)


class GsValidator:
    """Real-time anomaly flagging for the log-don't-tune design.

    Compares measured offset vs cryo-predicted offset and flags anomalies.
    Validation-only: never writes a tuned curve back to the balloon.
    """

    def __init__(self, k_hz_per_c: float = 2.0, t0_c: float = 25.0,
                 curve_ver: int = 0,
                 die_temp_range: tuple[float, float] = (-40.0, 125.0),
                 offset_tol_hz: float = 500.0,
                 frozen_die_temp_delta_c: float = 0.5,
                 frozen_offset_delta_hz: float = 100.0,
                 frozen_samples: int = 3):
        self.k_hz_per_c = k_hz_per_c
        self.t0_c = t0_c
        self.curve_ver = curve_ver
        self.die_temp_min, self.die_temp_max = die_temp_range
        self.offset_tol_hz = offset_tol_hz
        self.frozen_die_temp_delta_c = frozen_die_temp_delta_c
        self.frozen_offset_delta_hz = frozen_offset_delta_hz
        self.frozen_samples = frozen_samples
        self._die_temp_history: list[float] = []
        self._offset_history: list[float] = []

    def validate_sample(self, measured_offset_hz: float, die_temp_c: float,
                        gs_ref_stable: bool = True) -> dict:
        """Validate one (measured_offset, die_temp) sample.

        Returns a dict of flags plus the predicted offset. Flags:
          - die_temp_out_of_range: die temp outside the sensor's valid range
          - die_temp_frozen: die temp stuck while measured offset changes
          - gross_curve_error: |measured - predicted| > offset_tol_hz
          - gs_reference_loss: the GS reference was not stable
        """
        flags = {
            "die_temp_out_of_range": False,
            "die_temp_frozen": False,
            "gross_curve_error": False,
            "gs_reference_loss": False,
            "predicted_offset_hz": cryo_predict_offset(
                die_temp_c, self.k_hz_per_c, self.t0_c),
        }

        if not (self.die_temp_min <= die_temp_c <= self.die_temp_max):
            flags["die_temp_out_of_range"] = True

        # Frozen die-temp detection: if the die temp has not moved by more
        # than frozen_die_temp_delta_c over the last frozen_samples samples
        # WHILE the measured offset HAS moved by more than
        # frozen_offset_delta_hz over the same window, the sensor is likely
        # dead / reading is stale. Requires both: a dead sensor alone (temp
        # frozen AND offset steady) is not enough to flag — an in-range but
        # plateaud temp is plausible when the radio/chassis is at thermal
        # equilibrium.
        self._die_temp_history.append(die_temp_c)
        self._offset_history.append(measured_offset_hz)
        if len(self._die_temp_history) > self.frozen_samples:
            self._die_temp_history.pop(0)
            self._offset_history.pop(0)
        if len(self._die_temp_history) >= self.frozen_samples:
            temp_spread = max(self._die_temp_history) - min(self._die_temp_history)
            offset_spread = max(self._offset_history) - min(self._offset_history)
            if (temp_spread <= self.frozen_die_temp_delta_c and
                    offset_spread > self.frozen_offset_delta_hz):
                flags["die_temp_frozen"] = True

        if abs(measured_offset_hz - flags["predicted_offset_hz"]) > self.offset_tol_hz:
            flags["gross_curve_error"] = True

        if not gs_ref_stable:
            flags["gs_reference_loss"] = True

        return flags

    def validate_series(self, samples: list[dict]) -> dict:
        """Validate a series of samples.

        Each sample dict: {'measured_offset_hz': float, 'die_temp_c': float,
        'gs_ref_stable': bool (optional)}. Returns a summary dict with the
        per-sample flags and an anomaly count.
        """
        out_samples = []
        anomaly_count = 0
        for s in samples:
            flags = self.validate_sample(
                measured_offset_hz=s["measured_offset_hz"],
                die_temp_c=s["die_temp_c"],
                gs_ref_stable=s.get("gs_ref_stable", True),
            )
            if any(v for k, v in flags.items() if k != "predicted_offset_hz"):
                anomaly_count += 1
            out_samples.append(flags)
        return {"samples": out_samples, "anomaly_count": anomaly_count}
