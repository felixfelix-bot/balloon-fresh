// ============================================================
// Balloon Field-Test Enclosure v3-BIGRADIO
// Variant: Large radio module (EBYTE E28-2G4M27S or AliExpress LR2021 dev board)
//
// Waterproof clamshell for:
//   ESP32-C3 SuperMini + RP2040-Zero + LARGE LR2021/E28 + u-blox MAX-M10S GPS
//
// Key difference from standard v3:
//   - Small NiceRF LR2021 (20x15mm) replaced by large radio bay (42x32mm)
//   - SMA bulkhead connectors through case wall (external antennas)
//   - Antennas mount OUTSIDE the box
//
// Radio bay fits:
//   - EBYTE E28-2G4M27S (~28x24mm, SX1281 +27dBm)
//   - AliExpress LR2021 dev board (~40x30mm with PA)
//   - Any similar large RF module
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

// Board 3: LARGE RADIO MODULE (replaces small NiceRF LR2021)
// EBYTE E28-2G4M27S: ~28x24mm
// AliExpress LR2021 dev board: ~40x30mm
// Bay is oversized for universal fit
radio_bay_length = 42.0;   // Fits up to 42mm board
radio_bay_width  = 32.0;   // Fits up to 32mm board
radio_bay_thick  = 8.0;    // Fits PA + shielding + SMA connectors

// Board 4: GPS MAX-M10S — universal bay (same as v3)
gps_bay_length = 32.0;
gps_bay_width  = 32.0;
gps_bay_thick  = 7.0;

// ---- SMA CONNECTOR PARAMETERS ----
sma_hole_d = 6.5;          // SMA bulkhead clearance hole
sma_nut_d  = 10.0;         // SMA nut diameter (for recess on inside)
sma_nut_depth = 2.0;       // How deep the nut recess goes
num_sma = 2;               // 2 SMA connectors (2.4GHz + Sub-GHz)

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
    // Two holes stacked vertically: 2.4GHz on top, Sub-GHz below
    sma_spacing = 15.0;
    for (i = [0:num_sma-1]) {
        z_pos = floor_thick + interior_z/2 + (i - (num_sma-1)/2) * sma_spacing;
        // Clearance hole through wall
        translate([ext_x/2, radio_cy(), z_pos])
            rotate([0, 90, 0])
            cylinder(d=sma_hole_d, h=wall*3, center=true);
        // Nut recess on inside of wall
        translate([ext_x/2 - wall - 0.1, radio_cy(), z_pos])
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
