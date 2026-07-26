// ============================================================
// Balloon Field-Test Enclosure v3-BIGRADIO
// Variant: Large radio module with board-mounted SMA connectors
//
// Waterproof clamshell for:
//   ESP32-C3 SuperMini + RP2040-Zero + LoRa2021F33-2G4 (or E28) + GPS
//
// Key difference from standard v3:
//   - Small NiceRF LR2021 (20x15mm) replaced by large radio bay (42x32mm)
//   - 2x SMA bulkhead connectors through case wall (board-mounted SMA)
//   - Antennas screw on from OUTSIDE the box
//   - Radio board: LoRa2021F33-2G4 V1.0 (2W/+33dBm, AliExpress)
//     or EBYTE E28-2G4M27S (+27dBm) — both fit
//
// Radio bay fits:
//   - LoRa2021F33-2G4 V1.0 (~40x25mm, 2W, dual SMA, LR2021-based)
//   - EBYTE E28-2G4M27S (~28x24mm, SX1281 +27dBm)
//   - Any similar large RF module with edge SMA connectors
//
// Material: PETG or ASA (NOT PLA — UV/heat will destroy PLA outdoors)
// ============================================================

// ---- BOARD DIMENSIONS ----

// Board 1: ESP32-C3 SuperMini
esp32_length = 22.52;
esp32_width  = 18.0;
esp32_thick  = 3.5;

// Board 2: RP2040-Zero
rp2040_length = 23.0;
rp2040_width  = 18.0;
rp2040_thick  = 3.2;

// Board 3: LARGE RADIO MODULE — CALIPER MEASURED 2026-07-26
// LoRa2021F33-2G4 V1.0: 24.05x24.11x3.34mm + pigtail cables + 2x SMA
radio_length = 24.5;      // Measured: 24.05mm (rounded up)
radio_width  = 24.5;      // Measured: 24.11mm
radio_thick  = 3.5;       // Measured: 3.34mm + 0.16 clearance
radio_pin_pitch = 4.17;   // Measured pin pitch

// Radio bay — board + clearance for SMA pigtails + wiring
radio_bay_length = radio_length + 8;   // 32.5mm bay for 24.5mm board
radio_bay_width  = radio_width + 8;    // 32.5mm bay for 24.5mm board
radio_bay_thick  = radio_thick + 4;    // 7.5mm for board + SMA pigtail clearance

// Board 4: GPS MAX-M10S — CALIPER MEASURED 2026-07-26
// 15.16x15.22x8.05mm bare module, wire antenna
gps_length = 15.5;
gps_width  = 15.5;
gps_thick  = 8.5;

// GPS bay — measured module + clearance for tape/wire
gps_bay_length = gps_length + 6;   // 21.5mm
gps_bay_width  = gps_width + 6;    // 21.5mm
gps_bay_thick  = gps_thick + 2;    // 10.5mm

// ---- SMA CONNECTOR PARAMETERS ----
// Board-mounted SMA bulkhead connectors (LoRa2021F33-2G4 has SMA on short edge)
sma_hole_d = 6.5;          // SMA bulkhead clearance hole
sma_nut_d  = 10.0;         // SMA nut diameter (for recess on inside)
sma_nut_depth = 2.0;       // How deep the nut recess goes
sma_spacing = 13.0;        // Measured pigtail outer: 15.06mm
                              // SMA connector OD ~6mm, so center-to-center ~12-13mm
                              // Adjust if inner distance measurement differs
num_sma = 2;               // 2 SMA connectors (Sub-GHz ANT + 2.4GHz ANT_2G4)

// ---- CASE PARAMETERS ----
wall          = 2.0;
inner_clear   = 2.0;
floor_thick   = 2.5;
lid_thick     = 2.5;
board_gap     = 3.0;

// O-ring seal
oring_d    = 2.0;
oring_groove_depth = 1.5;

// Screws
screw_d    = 3.2;
screw_head_d = 6.0;

// Cable glands (for solar + non-SMA cables)
gland_d = 6.0;

// Pole mount
strap_width  = 22.0;
strap_depth  = 3.0;
strap_count  = 2;

// Solar panel recess (top lid)
solar_recess_x = 40.0;
solar_recess_y = 40.0;
solar_recess_depth = 2.0;

$fn = 60;

// ---- CALCULATED ----
// Layout: ESP32 + RP2040 side by side
// Radio bay alongside
// GPS bay in corner
esp_rp_row = esp32_length + board_gap + rp2040_length;
row_width  = max(esp32_width, rp2040_width);

total_x = esp_rp_row + radio_bay_length + board_gap*3 + inner_clear*2;
total_y = max(row_width, radio_bay_width, gps_bay_width) + inner_clear*2;

interior_x = max(total_x, total_y) + 4;  // extra room for SMA cables inside
interior_y = max(total_x, total_y) + 4;
interior_z = max(esp32_thick, rp2040_thick, radio_bay_thick) + gps_bay_thick + board_gap*3 + 6;

ext_x = interior_x + wall*2;
ext_y = interior_y + wall*2;
ext_z = interior_z + floor_thick + lid_thick;

// Radio bay position — near edge where SMA holes go
function radio_cx() = interior_x/2 - radio_bay_length/2 - inner_clear;
function radio_cy() = radio_bay_width/2 + inner_clear;

// GPS bay position — opposite corner
function gps_cx() = -(interior_x/2 - gps_bay_length/2 - inner_clear);
function gps_cy() = -(interior_y/2 - gps_bay_width/2 - inner_clear);

// ============================================================
// BOTTOM SHELL
// ============================================================
module bottom_shell() {
    difference() {
        rounded_box(ext_x, ext_y, interior_z + floor_thick, r=3);
        translate([0, 0, floor_thick])
            rounded_box(interior_x, interior_y, interior_z + 1, r=2);
        oring_groove();
        screw_holes_bottom();
        
        // SMA bulkhead holes — through the wall nearest radio bay
        // Two holes: 2.4GHz + Sub-GHz
        sma_connectors();
        
        // Cable gland holes (opposite side from SMA — for solar/power)
        translate([-ext_x/2, 0, floor_thick + interior_z/2])
            rotate([-90, 0, 0])
            cylinder(d=gland_d, h=wall*2, center=true);
        
        // GPS antenna window
        gps_window_x = gps_bay_length - 4;
        gps_window_y = gps_bay_width - 4;
        translate([gps_cx(), gps_cy(), -0.1])
            rounded_box(gps_window_x, gps_window_y, floor_thick + 0.3, r=1);
        
        // Pole mount strap grooves
        for (i = [0:strap_count-1]) {
            pos = (i - (strap_count-1)/2) * (ext_y / strap_count);
            translate([0, pos, -0.1])
                strap_groove();
        }
    }
    
    board_standoffs();
    gps_bay_walls();
    radio_bay_walls();
}

// ============================================================
// SMA CONNECTORS — through case wall
// ============================================================
module sma_connectors() {
    // SMA holes on the +X wall (same side as radio bay)
    // Board-mounted SMAs pass through wall, nut on outside
    // LoRa2021F33-2G4: ANT and ANT_2G4 on short edge, ~18mm apart
    sma_y_offset = radio_cy();  // Center on radio bay
    for (i = [0:num_sma-1]) {
        y_pos = sma_y_offset + (i - (num_sma-1)/2) * sma_spacing;
        z_pos = floor_thick + interior_z/2;
        // Clearance hole through wall
        translate([ext_x/2, y_pos, z_pos])
            rotate([0, 90, 0])
            cylinder(d=sma_hole_d, h=wall*3, center=true);
        // Nut recess on inside of wall (board SMA nut faces inward)
        translate([ext_x/2 - wall - 0.1, y_pos, z_pos])
            rotate([0, 90, 0])
            cylinder(d=sma_nut_d, h=sma_nut_depth + 0.1, $fn=6);
    }
}

// ============================================================
// BAY WALLS (GPS + Radio)
// ============================================================
module gps_bay_walls() {
    lip_h = 2.0;
    lip_t = 1.5;
    difference() {
        translate([gps_cx(), gps_cy(), floor_thick])
            rounded_box(gps_bay_length + lip_t*2, gps_bay_width + lip_t*2, lip_h, r=1);
        translate([gps_cx(), gps_cy(), floor_thick - 0.1])
            rounded_box(gps_bay_length, gps_bay_width, lip_h + 0.3, r=1);
    }
}

module radio_bay_walls() {
    lip_h = 2.0;
    lip_t = 1.5;
    difference() {
        translate([radio_cx(), radio_cy(), floor_thick])
            rounded_box(radio_bay_length + lip_t*2, radio_bay_width + lip_t*2, lip_h, r=1);
        translate([radio_cx(), radio_cy(), floor_thick - 0.1])
            rounded_box(radio_bay_length, radio_bay_width, lip_h + 0.3, r=1);
    }
}

// ============================================================
// TOP LID
// ============================================================
module top_lid() {
    difference() {
        translate([0, 0, interior_z + floor_thick])
            rounded_box(ext_x, ext_y, lid_thick, r=3);
        translate([0, 0, interior_z + floor_thick + lid_thick - solar_recess_depth])
            rounded_box(solar_recess_x, solar_recess_y, solar_recess_depth + 1, r=2);
        screw_holes_top();
        // Vent hole
        translate([ext_x/2 - 8, ext_y/2 - 8, interior_z + floor_thick - 0.1])
            cylinder(d=2, h=lid_thick + 1);
    }
}

// ============================================================
// COMPONENTS
// ============================================================

module rounded_box(x, y, z, r=2) {
    hull() {
        for (sx = [-1, 1], sy = [-1, 1]) {
            translate([sx*(x/2 - r), sy*(y/2 - r), r])
                cylinder(r=r, h=z - r*2);
            translate([sx*(x/2 - r), sy*(y/2 - r), 0])
                cylinder(r=r, h=0.1);
        }
    }
}

module oring_groove() {
    groove_x = interior_x + wall;
    groove_y = interior_y + wall;
    translate([0, 0, floor_thick + interior_z - oring_groove_depth])
        difference() {
            rounded_box(groove_x + oring_d*2, groove_y + oring_d*2, oring_groove_depth + 1, r=3);
            rounded_box(groove_x, groove_y, oring_groove_depth + 2, r=2);
        }
}

function screw_positions() = let(
    px = interior_x/2 + wall/2,
    py = interior_y/2 + wall/2
) [
    [ px,  py], [-px,  py],
    [ px, -py], [-px, -py],
];

module screw_holes_bottom() {
    for (p = screw_positions()) {
        translate([p[0], p[1], floor_thick/2])
            cylinder(d=screw_d, h=floor_thick + 1, center=true, $fn=12);
        translate([p[0], p[1], -0.1])
            cylinder(d=6.5, h=2.5, $fn=6);
    }
}

module screw_holes_top() {
    for (p = screw_positions()) {
        translate([p[0], p[1], interior_z + floor_thick])
            union() {
                cylinder(d=screw_d, h=lid_thick + 1, center=false, $fn=12);
                translate([0, 0, lid_thick - 1.5])
                    cylinder(d1=screw_d, d2=screw_head_d, h=2, $fn=12);
            }
    }
}

module strap_groove() {
    rotate([0, 90, 0])
        difference() {
            cylinder(d=ext_z + strap_depth*2, h=strap_width, center=true, $fn=80);
            cylinder(d=ext_z, h=strap_width + 2, center=true, $fn=80);
        }
}

module board_standoffs() {
    standoff_h = 3.0;
    standoff_d = 3.0;
    hole_d = 2.0;
    
    // ESP32 — left section
    esp32_cx = -(interior_x/2 - esp32_length/2 - inner_clear - board_gap);
    esp32_cy = interior_y/2 - esp32_width/2 - inner_clear;
    for (sx = [-1,1], sy = [-1,1]) {
        translate([esp32_cx + sx*(esp32_length/2 - 1.5),
                   esp32_cy + sy*(esp32_width/2 - 1.5),
                   floor_thick])
            standoff(standoff_h, standoff_d, hole_d);
    }
    
    // RP2040 — next to ESP32
    rp2040_cx = esp32_cx + esp32_length/2 + board_gap + rp2040_length/2;
    for (sx = [-1,1], sy = [-1,1]) {
        translate([rp2040_cx + sx*(rp2040_length/2 - 1.5),
                   esp32_cy + sy*(rp2040_width/2 - 1.5),
                   floor_thick])
            standoff(standoff_h, standoff_d, hole_d);
    }
    
    // Radio: friction-fit bay, no standoffs
    // GPS: friction-fit bay, no standoffs
}

module standoff(h, od, id) {
    difference() {
        cylinder(d=od, h=h, $fn=16);
        translate([0,0,-0.1])
            cylinder(d=id, h=h+0.3, $fn=12);
    }
}

// ============================================================
// RENDER
// ============================================================
part = "both";

if (part == "bottom" || part == "both") {
    bottom_shell();
}
if (part == "top" || part == "both") {
    top_lid();
}
