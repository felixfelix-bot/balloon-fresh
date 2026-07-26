// ============================================================
// Balloon Field-Test Enclosure v2
// Waterproof clamshell for 4 boards:
//   ESP32-C3 SuperMini + RP2040-Zero + LR2021 + u-blox MAX-M10S GPS
// Designed for: outdoor pole mount, solar charging, rain/sun exposure
// Material: PETG or ASA (NOT PLA — UV/heat will destroy PLA outdoors)
// ============================================================

// ---- MEASURE YOUR BOARDS AND ADJUST THESE ----
// Use digital calipers. Accuracy = ±0.5mm is fine.
// These are from AGENTS.md + BOM.md inventory. VERIFY with calipers!

// Board 1: ESP32-C3 SuperMini (Maker Go ESP32-C3_Mini_V1)
esp32_length = 22.52;    // PCB length (X)
esp32_width  = 18.0;     // PCB width  (Y)
esp32_thick  = 3.5;      // Thickness including USB-C + components

// Board 2: RP2040-Zero
rp2040_length = 23.0;    // PCB length
rp2040_width  = 18.0;    // PCB width
rp2040_thick  = 3.2;     // Thickness including USB + components

// Board 3: NiceRF LoRa2021 (LR2021 module)
lr2021_length = 19.72;   // Module length
lr2021_width  = 15.0;    // Module width
lr2021_thick  = 2.2;     // Module PCB thickness

// Board 4: u-blox MAX-M10S GPS
// Bare LCC module: 15.5x15.5x2.6mm
// Common breakout: ~22x20mm with ceramic antenna, ~4mm thick
// ADJUST if your breakout differs!
gps_length = 22.0;       // GPS breakout board length (X)
gps_width  = 20.0;       // GPS breakout board width  (Y)
gps_thick  = 4.0;        // Thickness incl. ceramic patch antenna + module

// ---- CASE PARAMETERS ----
wall          = 2.0;     // Wall thickness (2mm = waterproof + strong)
inner_clear   = 2.0;     // Clearance around boards for wiring
floor_thick   = 2.5;     // Bottom wall thickness
lid_thick     = 2.5;     // Top wall thickness
board_gap     = 3.0;     // Gap between boards for airflow/wiring

// O-ring seal
oring_d    = 2.0;
oring_groove_depth = 1.5;

// Screws
screw_d    = 3.2;        // M3 clearance
screw_head_d = 6.0;      // M3 countersink head
screw_boss_d = 7.0;

// Cable glands
gland_d = 6.0;           // Antenna + solar cable feedthrough

// Pole mount
strap_width  = 22.0;     // Zip-tie / hose clamp width slot
strap_depth  = 3.0;
strap_count  = 2;

// Solar panel recess (top lid)
solar_recess_x = 40.0;
solar_recess_y = 40.0;
solar_recess_depth = 2.0;

$fn = 60;

// ---- CALCULATED ----
// Layout: ESP32 | LR2021 | RP2040 stacked in row
// GPS module goes on a second layer or side pocket
// Row layout: ESP32 -- gap -- LR2021 -- gap -- RP2040
row1_length = esp32_length + board_gap + lr2021_length + board_gap + rp2040_length;
row1_width  = max(esp32_width, lr2021_width, rp2040_width);

// GPS alongside, parallel
total_x = row1_length + gps_length + board_gap*2 + inner_clear*2;
total_y = max(row1_width, gps_width + board_gap*2) + inner_clear*2;

interior_x = max(total_x, total_y);  // make roughly square
interior_y = max(total_x, total_y);
interior_z = max(esp32_thick, rp2040_thick) + gps_thick + board_gap*3 + 8;

ext_x = interior_x + wall*2;
ext_y = interior_y + wall*2;
ext_z = interior_z + floor_thick + lid_thick;

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
        
        // Cable gland holes (antenna + solar)
        translate([ext_x/2, 0, floor_thick + interior_z/2])
            rotate([-90, 0, 0])
            cylinder(d=gland_d, h=wall*2, center=true);
        translate([-ext_x/2, 0, floor_thick + interior_z/2])
            rotate([-90, 0, 0])
            cylinder(d=gland_d, h=wall*2, center=true);
        
        // GPS antenna window — needs sky view!
        // Cut thin slot in bottom for GPS patch antenna
        gps_window_x = gps_length - 2;
        gps_window_y = gps_width - 2;
        translate([gps_offset_x(), gps_offset_y(), -0.1])
            rounded_box(gps_window_x, gps_window_y, floor_thick + 0.3, r=1);
        
        // Pole mount strap grooves
        for (i = [0:strap_count-1]) {
            pos = (i - (strap_count-1)/2) * (ext_y / strap_count);
            translate([0, pos, -0.1])
                strap_groove();
        }
    }
    
    board_standoffs();
}

// GPS position helper — placed in a corner
function gps_offset_x() = -(interior_x/2 - gps_length/2 - inner_clear);
function gps_offset_y() = -(interior_y/2 - gps_width/2 - inner_clear);

// ============================================================
// TOP LID
// ============================================================
module top_lid() {
    difference() {
        translate([0, 0, interior_z + floor_thick])
            rounded_box(ext_x, ext_y, lid_thick, r=3);
        
        // Solar panel recess
        translate([0, 0, interior_z + floor_thick + lid_thick - solar_recess_depth])
            rounded_box(solar_recess_x, solar_recess_y, solar_recess_depth + 1, r=2);
        
        screw_holes_top();
        
        // Vent hole (cover with Gore patch)
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
            cylinder(d=6.5, h=2.5, $fn=6); // M3 nut trap
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
    
    // Layout: ESP32 and RP2040 side by side, LR2021 between them
    // ESP32 left third
    esp32_cx = -(lr2021_length/2 + board_gap + esp32_length/2);
    for (sx = [-1,1], sy = [-1,1]) {
        translate([esp32_cx + sx*(esp32_length/2 - 1.5),
                   sy*(esp32_width/2 - 1.5),
                   floor_thick])
            standoff(standoff_h, standoff_d, hole_d);
    }
    
    // RP2040 right third
    rp2040_cx = (lr2021_length/2 + board_gap + rp2040_length/2);
    for (sx = [-1,1], sy = [-1,1]) {
        translate([rp2040_cx + sx*(rp2040_length/2 - 1.5),
                   sy*(rp2040_width/2 - 1.5),
                   floor_thick])
            standoff(standoff_h, standoff_d, hole_d);
    }
    
    // LR2021 center, lower standoffs (sits on floor or low)
    for (sx = [-1,1], sy = [-1,1]) {
        translate([sx*(lr2021_length/2 - 1.5),
                   sy*(lr2021_width/2 - 1.5),
                   floor_thick])
            standoff(1.5, 3.0, 2.0);
    }
    
    // GPS module — offset corner, needs sky-facing antenna
    // Placed near edge with antenna window in bottom shell
    gx = gps_offset_x();
    gy = gps_offset_y();
    for (sx = [-1,1], sy = [-1,1]) {
        translate([gx + sx*(gps_length/2 - 1.5),
                   gy + sy*(gps_width/2 - 1.5),
                   floor_thick])
            standoff(2.0, 3.0, 2.0);
    }
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
