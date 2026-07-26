// ============================================================
// Balloon Field-Test Enclosure v3 — UNIVERSAL GPS BAY
// Waterproof clamshell for 4 boards:
//   ESP32-C3 SuperMini + RP2040-Zero + LR2021 + ANY MAX-M10S GPS breakout
//
// GPS bay is oversized (32x32mm) to fit ANY common M10S breakout:
//   - Bare module (15.5x15.5mm)
//   - Pimoroni/UK hobbyist (~22x20mm with blue LED)
//   - Adafruit (~25x35mm)
//   - SparkFun SPX-19281 (~30x25mm)
//   - AliExpress generic (25x25mm with patch antenna)
// Board held by friction fit + double-sided tape, not screws.
//
// Material: PETG or ASA (NOT PLA — UV/heat will destroy PLA outdoors)
// ============================================================

// ---- BOARD DIMENSIONS (from AGENTS.md inventory) ----
// These are well-known. Caliper verify if you have them handy.

// Board 1: ESP32-C3 SuperMini (Maker Go ESP32-C3_Mini_V1)
esp32_length = 22.52;
esp32_width  = 18.0;
esp32_thick  = 3.5;

// Board 2: RP2040-Zero
rp2040_length = 23.0;
rp2040_width  = 18.0;
rp2040_thick  = 3.2;

// Board 3: NiceRF LoRa2021 (LR2021 module)
lr2021_length = 19.72;
lr2021_width  = 15.0;
lr2021_thick  = 2.2;

// Board 4: GPS MAX-M10S — UNIVERSAL BAY
// Oversized to fit any breakout. Tape/sticky-pad mount.
gps_bay_length = 32.0;   // Fits up to 32mm board (SparkFun, Adafruit, Pimoroni)
gps_bay_width  = 32.0;   // Fits up to 32mm board
gps_bay_thick  = 7.0;    // Fits ceramic patch antenna + board + LED

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

// Cable glands
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
// Row 1: ESP32 | gap | LR2021 | gap | RP2040
row1_length = esp32_length + board_gap + lr2021_length + board_gap + rp2040_length;
row1_width  = max(esp32_width, lr2021_width, rp2040_width);

// GPS bay sits alongside the board row
total_x = row1_length + gps_bay_length + board_gap*2 + inner_clear*2;
total_y = max(row1_width, gps_bay_width) + inner_clear*2;

interior_x = max(total_x, total_y);
interior_y = max(total_x, total_y);
interior_z = max(esp32_thick, rp2040_thick) + gps_bay_thick + board_gap*3 + 6;

ext_x = interior_x + wall*2;
ext_y = interior_y + wall*2;
ext_z = interior_z + floor_thick + lid_thick;

// GPS bay position — corner, antenna faces down through window
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
        
        // Cable gland holes
        translate([ext_x/2, 0, floor_thick + interior_z/2])
            rotate([-90, 0, 0])
            cylinder(d=gland_d, h=wall*2, center=true);
        translate([-ext_x/2, 0, floor_thick + interior_z/2])
            rotate([-90, 0, 0])
            cylinder(d=gland_d, h=wall*2, center=true);
        
        // GPS antenna window — oversized for any patch antenna
        // 28x28mm covers all common patch antennas (15-25mm)
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
}

// ============================================================
// GPS BAY — friction fit pocket with raised lip
// ============================================================
module gps_bay_walls() {
    // Low retaining wall around GPS bay to hold board in place
    // Board sits on floor of case, held by wall + tape
    lip_h = 2.0;
    lip_t = 1.5;
    
    difference() {
        // Outer wall of GPS bay pocket
        translate([gps_cx(), gps_cy(), floor_thick])
            rounded_box(gps_bay_length + lip_t*2, gps_bay_width + lip_t*2, lip_h, r=1);
        // Inner cutout (where board sits)
        translate([gps_cx(), gps_cy(), floor_thick - 0.1])
            rounded_box(gps_bay_length, gps_bay_width, lip_h + 0.3, r=1);
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
    esp32_cx = -(lr2021_length/2 + board_gap + esp32_length/2);
    for (sx = [-1,1], sy = [-1,1]) {
        translate([esp32_cx + sx*(esp32_length/2 - 1.5),
                   sy*(esp32_width/2 - 1.5),
                   floor_thick])
            standoff(standoff_h, standoff_d, hole_d);
    }
    
    // RP2040 — right section
    rp2040_cx = (lr2021_length/2 + board_gap + rp2040_length/2);
    for (sx = [-1,1], sy = [-1,1]) {
        translate([rp2040_cx + sx*(rp2040_length/2 - 1.5),
                   sy*(rp2040_width/2 - 1.5),
                   floor_thick])
            standoff(standoff_h, standoff_d, hole_d);
    }
    
    // LR2021 — center, low standoffs
    for (sx = [-1,1], sy = [-1,1]) {
        translate([sx*(lr2021_length/2 - 1.5),
                   sy*(lr2021_width/2 - 1.5),
                   floor_thick])
            standoff(1.5, 3.0, 2.0);
    }
    
    // GPS: NO standoffs — uses friction-fit bay with retaining lip
    // Board sits flat on case floor, held by raised lip + double-sided tape
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
