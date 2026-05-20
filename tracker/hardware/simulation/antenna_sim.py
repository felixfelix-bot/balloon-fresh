"""
Antenna Simulation Helpers
Simple calculations for PCB Yagi at 2.4 GHz.
"""

import math

def yagi_dimensions(freq_hz=2.4e9, num_directors=2):
    c = 3e8
    wavelength = c / freq_hz
    lambda_mm = wavelength * 1000

    driven_len = 0.47 * lambda_mm
    reflector_len = 0.495 * lambda_mm
    director_len = 0.44 * lambda_mm

    driven_to_reflector = 0.125 * lambda_mm
    director_spacing = 0.34 * lambda_mm

    boom_length = driven_to_reflector + num_directors * director_spacing

    gain_dbi = 5.5 + 1.5 * num_directors

    return {
        "wavelength_mm": round(lambda_mm, 1),
        "driven_element_mm": round(driven_len, 1),
        "reflector_mm": round(reflector_len, 1),
        "director_mm": round(director_len, 1),
        "driven_to_reflector_mm": round(driven_to_reflector, 1),
        "director_spacing_mm": round(director_spacing, 1),
        "boom_length_mm": round(boom_length, 1),
        "estimated_gain_dbi": round(gain_dbi, 1),
        "freq_ghz": freq_hz / 1e9,
    }

def print_yagi_design():
    dims = yagi_dimensions()
    print(f"=== PCB Yagi Antenna Design ({dims['freq_ghz']} GHz) ===")
    print(f"Wavelength:        {dims['wavelength_mm']} mm")
    print(f"Driven element:    {dims['driven_element_mm']} mm")
    print(f"Reflector:         {dims['reflector_mm']} mm")
    print(f"Director:          {dims['director_mm']} mm")
    print(f"Driven→Reflector:  {dims['driven_to_reflector_mm']} mm")
    print(f"Director spacing:  {dims['director_spacing_mm']} mm")
    print(f"Boom length:       {dims['boom_length_mm']} mm")
    print(f"Est. gain:         {dims['estimated_gain_dbi']} dBi")

if __name__ == "__main__":
    print_yagi_design()
