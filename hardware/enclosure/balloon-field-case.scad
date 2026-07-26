// ============================================================
// Balloon Field-Test Enclosure v1
// Waterproof clamshell for: ESP32-C3 SuperMini + RP2040-Zero + LR2021
// Designed for: outdoor pole mount, solar charging, rain/sun exposure
// Material: PETG or ASA (NOT PLA — UV/heat will destroy PLA outdoors)
// ============================================================

// ---- MEASURE YOUR BOARDS AND ADJUST THESE ----
// Use digital calipers. Accuracy = ±0.5mm is fine.
esp32_length = 22.52;    // ESP32-C3 SuperMini PCB length (X)
esp32_width  = 18.0;     // ESP32-C3 SuperMini PCB width  (Y)
esp32_thick  = 3.5;      // Thickness including USB-C + components

rp2040_length = 23.0;    // RP2040-Zero PCB length
rp2040_width  = 18.0;    // RP2040-Zero PCB width
rp2040_thick  = 3.2;     // Thickness including USB + components

lr2021_length = 19.72;   // NiceRF LoRa2021 module length
lr2021_width  = 15.0;    // NiceRF LoRa2021 module width
lr2021_thick  = 2.2;     // Module PCB thickness

// ---- CASE PARAMETERS (probably don't need to change) ----
wall          = 2.0;     // Wall thickness (2mm = waterproof + strong)
inner_clear   = 2.0;     // Clearance around boards for wiring
floor_thick   = 2.5;     // Bottom wall thickness
lid_thick     = 2.5;     // Top wall thickness
board_gap     = 3.0;     // Gap between boards for airflow/wiring

// O-ring seal
oring_d    = 2.0;        // O-ring cord diameter (2mm = standard)
oring_groove_depth = 1.5; // Groove depth (75% compression of cord)

// Screws
screw_d    = 3.2;        // M3 screw clearance hole
screw_head_d = 6.0;      // M3 countersink head
screw_boss_d = 7.0;      // Screw boss outer diameter
num_screws_x = 4;        // Screws along X axis (2 rows)
num_screws_y = 2;        // Screw rows along Y axis

// Cable gland
gland_d = 6.0;           // Cable gland hole diameter (for antenna + solar)

// Pole mount
strap_width  = 22.0;     // Zip-tie / hose clamp width slot
strap_depth  = 3.0;      // How deep the strap groove is
strap_count  = 2;        // Number of strap grooves on back

// Solar panel recess (top lid)
solar_recess_x = 40.0;   // Recess for solar panel on lid
solar_recess_y = 40.0;
solar_recess_depth = 2.0;

$fn = 60; // Circle resolution

// ---- CALCULATED ----
// Interior needs to fit boards side by side with gaps
interior_x = max(esp32_length, rp2040_length) + lr2021_length + board_gap*3 + inner_clear*2;
interior_y = max(esp32_width + rp2040_width + board_gap, lr2021_width) + inner_clear*2;
interior_z = max(esp32_thick, rp2040_thick) + lr2021_thick + board_gap*2 + 8; // 8mm headroom for wiring

ext_x = interior_x + wall*2;
ext_y = interior_y + wall*2;
ext_z = interior_z + floor_thick + lid_thick;

// ============================================================
// BOTTOM SHELL
// ============================================================
module bottom_shell() {
    difference() {
        // Outer box with rounded corners
        rounded_box(ext_x, ext_y, interior_z + floor_thick, r=3);
        
        // Interior cavity (hollow from top)
        translate([0, 0, floor_thick])
            rounded_box(interior_x, interior_y, interior_z + 1, r=2);
        
        // O-ring groove (on top face of bottom shell)
        oring_groove();
        
        // Screw holes
        screw_holes_bottom();
        
        // Cable gland hole (one side)
        translate([ext_x/2, 0, floor_thick + interior_z/2])
            rotate([-90, 0, 0])
            cylinder(d=gland_d, h=wall*2, center=true);
        
        // Second gland hole (opposite side, for solar)
        translate([-ext_x/2, 0, floor_thick + interior_z/2])
            rotate([-90, 0, 0])
            cylinder(d=gland_d, h=wall*2, center=true);
        
        // Pole mount strap grooves (on bottom face)
        for (i = [0:strap_count-1]) {
            pos = (i - (strap_count-1)/2) * (ext_y / strap_count);
            translate([0, pos, -0.1])
                strap_groove();
        }
    }
    
    // Board mounting standoffs
    board_standoffs();
}

// ============================================================
// TOP LID
// ============================================================
module top_lid() {
    difference() {
        // Lid slab
        translate([0, 0, interior_z + floor_thick])
            rounded_box(ext_x, ext_y, lid_thick, r=3);
        
        // Solar panel recess (on top of lid)
        translate([0, 0, interior_z + floor_thick + lid_thick - solar_recess_depth])
            rounded_box(solar_recess_x, solar_recess_y, solar_recess_depth + 1, r=2);
        
        // Screw countersink holes
        screw_holes_top();
        
        // Vent hole for pressure equalization (small, will be covered by Gore patch)
        translate([ext_x/2 - 8, ext_y/2 - 8, interior_z + floor_thick - 0.1])
            cylinder(d=2, h=lid_thick + 1);
    }
    
    // O-ring ridge (mates with groove in bottom)
    // Actually the groove is in the bottom, lid has flat mating surface
    // The screws compress lid down onto O-ring
}

// ============================================================
// COMPONENTS
// ============================================================

module rounded_box(x, y, z, r=2) {
    // Box with rounded vertical edges, centered at origin, bottom at z=0
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
    // Rectangular O-ring groove on top face of bottom shell
    // Groove runs along the perimeter of the interior opening
    groove_x = interior_x + wall;  // slightly larger than interior
    groove_y = interior_y + wall;
    translate([0, 0, floor_thick + interior_z - oring_groove_depth])
        difference() {
            rounded_box(groove_x + oring_d*2, groove_y + oring_d*2, oring_groove_depth + 1, r=3);
            rounded_box(groove_x, groove_y, oring_groove_depth + 2, r=2);
        }
}

module screw_holes_bottom() {
    // M3 clearance holes in the bottom shell for screws
    // Screws go from top (through lid) into threaded inserts or nuts in bottom
    positions = screw_positions();
    for (p = positions) {
        translate([p[0], p[1], 0])
            // Nut trap on bottom (hexagonal)
            translate([0, 0, floor_thick/2])
                cylinder(d=screw_d, h=floor_thick + 1, center=true, $fn=12);
    }
    // Nut traps
    for (p = positions) {
        translate([p[0], p[1], -0.1])
            cylinder(d=6.5, h=2.5, $fn=6); // M3 nut trap
    }
}

module screw_holes_top() {
    // Countersink screw holes in the lid
    positions = screw_positions();
    for (p = positions) {
        translate([p[0], p[1], interior_z + floor_thick])
            union() {
                // Clearance hole
                cylinder(d=screw_d, h=lid_thick + 1, center=false, $fn=12);
                // Countersink
                translate([0, 0, lid_thick - 1.5])
                    cylinder(d1=screw_d, d2=screw_head_d, h=2, $fn=12);
            }
    }
}

function screw_positions() = let(
    px = interior_x/2 + wall/2,
    py = interior_y/2 + wall/2
) [
    [ px,  py], [-px,  py],
    [ px, -py], [-px, -py],
];

module strap_groove() {
    // Zip-tie / hose clamp groove on bottom of case
    // Runs across the bottom perpendicular to pole
    translate([0, 0, 0])
        rotate([0, 90, 0])
        difference() {
            cylinder(d=ext_z + strap_depth*2, h=strap_width, center=true, $fn=80);
            cylinder(d=ext_z, h=strap_width + 2, center=true, $fn=80);
        }
}

module board_standoffs() {
    // ESP32-C3 standoffs (4 corners)
    ex_pos = (lr2021_length/2 + board_gap + esp32_length/2);
    ey_pos = (esp32_width/2 + inner_clear);
    standoff_h = 3.0;
    standoff_d = 3.0;
    hole_d = 2.0; // M2 self-tapping
    
    // ESP32 mounting posts
    for (sx = [-1,1], sy = [-1,1]) {
        translate([ex_pos + sx*(esp32_length/2 - 1.5),
                   ey_pos + sy*(esp32_width/2 - 1.5),
                   floor_thick])
            standoff(standoff_h, standoff_d, hole_d);
    }
    
    // RP2040 standoffs (other side)
    rx_pos = -(lr2021_length/2 + board_gap + rp2040_length/2);
    ry_pos = (rp2040_width/2 + inner_clear);
    for (sx = [-1,1], sy = [-1,1]) {
        translate([rx_pos + sx*(rp2040_length/2 - 1.5),
                   ry_pos + sy*(rp2040_width/2 - 1.5),
                   floor_thick])
            standoff(standoff_h, standoff_d, hole_d);
    }
    
    // LR2021 standoffs (center, lower layer)
    lx = 0;
    ly = -(lr2021_width/2 + inner_clear);
    for (sx = [-1,1], sy = [-1,1]) {
        translate([lx + sx*(lr2021_length/2 - 1.5),
                   ly + sy*(lr2021_width/2 - 1.5),
                   floor_thick])
            standoff(1.5, 3.0, 2.0);
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
// Print both parts separately. Bottom first, then lid.
// Orient both flat on build plate (already oriented for printing).

// Print comment: set "bottom_shell" or "top_lid" to render the part you want
// Command line:
//   openscad -o bottom.stl -D 'part="bottom"' balloon-field-case.scad
//   openscad -o lid.stl -D 'part="top"' balloon-field-case.scad

part = "both"; // "bottom", "top", or "both"

if (part == "bottom" || part == "both") {
    bottom_shell();
}

if (part == "top" || part == "both") {
    top_lid();
}
