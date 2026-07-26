// ==========================================================================
// Balloon Dev Board Waterproof Enclosure
// 
// Fits: ESP32-C3 SuperMini + LR2021 + RP2040 (dev/testing)
// Target: IP65+ outdoor use, pole mount with solar
// Print: PETG or ASA recommended (UV + heat resistant)
// 
// Usage: openscad -o bottom.stla -D part=\"bottom\" balloon_dev_case.scad
//        openscad -o lid.stl -D part=\"lid\" balloon_dev_case.scad
// ==========================================================================

/* [Part Selection] */
part = "both"; // "bottom", "lid", "both"

/* [Board Dimensions - adjustable] */
// ESP32-C3 SuperMini V1
esp_w = 22.52;
esp_l = 18.0;
esp_h = 1.6; // PCB thickness

// NiceRF LR2021 (mounted on top of ESP32)
lr_w = 19.72;
lr_l = 15.0;
lr_h = 2.2; // above PCB, plus ~2mm for solder joints underneath

// RP2040 (SuperMini assumed - adjust if Pico)
rp_w = 21.5;
rp_l = 17.8;
rp_h = 1.6;

/* [Interior Layout] */
// Layout: "stacked" or "sidebyside"
layout = "stacked";

// Clearance above boards for wires/connectors
wire_clearance = 12;
// Margin around boards
board_margin = 4;

// Computed interior dimensions
interior_x = layout == "stacked" 
    ? max(esp_w, rp_w) + lr_w + board_margin * 2 + 2  // LR2021 overlaps ESP but has pads
    : esp_w + rp_w + board_margin * 3 + 4;
interior_y = layout == "stacked"
    ? max(esp_l + lr_l + 2, rp_l) + board_margin * 2
    : max(esp_l, rp_l) + board_margin * 2;

// Board stack height
board_stack_h = layout == "stacked"
    ? esp_h + lr_h + 3 + rp_h  // ESP + LR2021 + gap + RP2040
    : max(esp_h + lr_h, rp_h);

interior_z = board_stack_h + wire_clearance;

echo("Interior dimensions:", interior_x, interior_y, interior_z);

/* [Wall Thickness] */
wall = 2.5;
floor_thick = 2.5;
lid_thick = 3.0;

/* [External Dimensions] */
ext_x = interior_x + wall * 2;
ext_y = interior_y + wall * 2;
ext_z = interior_z + floor_thick;

echo("External dimensions:", ext_x, ext_y, ext_z);

/* [Corner Radius] */
corner_r = 4; // rounded exterior corners

/* [Screw Bosses] */
screw_d = 3.2;       // M3 screw clearance hole (lid) / 2.5 for heat insert
insert_d = 4.2;      // heat-set insert OD
insert_h = 5.0;      // heat-set insert depth
boss_d = 8;          // boss outer diameter
boss_inset = 6;      // distance from interior wall

/* [O-Ring Groove] */
oring_d = 2.0;       // O-ring cord diameter (2mm = AS568 standard)
oring_groove_d = oring_d + 0.3; // slight compression
oring_groove_h = oring_d * 0.75; // 25% squeeze
oring_wall_offset = 3; // distance from outer wall

/* [Cable Glands] */
gland_d = 6.0;       // cable gland hole diameter (M8/M6 PG7)
gland_count = 3;     // antenna1, antenna2, solar
gland_spacing = 12;

/* [Pole Mount] */
pole_tab_w = 18;
pole_tab_h = 10;
pole_hole_d = 5.5;   // for M5 bolt or U-bolt
pole_tab_thick = 4;

/* [Board Mounting] */
// Standoff height for bottom board
standoff_h = 3;
standoff_d = 5;
// Board mounting hole diameter (M2 self-tapping)
board_screw_d = 1.8;

/* [Solar Panel Recess - in lid] */
solar_recess_depth = 1.5;
solar_recess_margin = 3;

/* [Ventilation] */
// Gore-Tex patch vent (small, for pressure equalization)
vent_d = 4;

/* [Print Quality] */
$fn = 48; // facets for circles

// ==========================================================================
// MODULES
// ==========================================================================

module rounded_box(x, y, z, r) {
    hull() {
        for (px = [r, x-r], py = [r, y-r]) {
            translate([px, py, 0])
                cylinder(h=z, r=r);
        }
    }
}

module rounded_box_centered(x, y, z, r) {
    translate([-x/2, -y/2, 0])
        rounded_box(x, y, z, r);
}

// Interior cavity (hollowed box)
module interior_cavity() {
    translate([wall, wall, floor_thick])
        cube([interior_x, interior_y, interior_z + 1]);
}

// Screw boss (solid cylinder for heat-set insert)
module screw_boss(x, y) {
    translate([x, y, 0])
        difference() {
            cylinder(h=floor_thick + insert_h + 2, d=boss_d);
            // Heat-set insert hole
            translate([0, 0, floor_thick + insert_h - insert_h])
                cylinder(h=insert_h + 0.5, d=insert_d);
        }
}

// O-ring groove (cut into lid underside)
module oring_groove() {
    // Rectangular groove following the perimeter
    offset_d = oring_wall_offset;
    gx = ext_x - 2 * offset_d;
    gy = ext_y - 2 * offset_d;
    gr = max(corner_r - offset_d, 1);
    
    translate([0, 0, -0.1])
    difference() {
        // Outer cut
        translate([offset_d, offset_d, 0])
            rounded_box(gx, gy, oring_groove_h + 0.2, gr);
        // Inner cut (creates groove channel)
        translate([offset_d + oring_groove_d, offset_d + oring_groove_d, -0.1])
            rounded_box(
                gx - 2 * oring_groove_d, 
                gy - 2 * oring_groove_d, 
                oring_groove_h + 0.4,
                max(gr - oring_groove_d, 0.5)
            );
    }
}

// Board mounting standoffs
module standoff(x, y, h) {
    translate([x, y, floor_thick])
        difference() {
            cylinder(h=h, d=standoff_d);
            cylinder(h=h + 1, d=board_screw_d);
        }
}

// Cable gland hole
module cable_gland(x, y) {
    translate([x, y, -1])
        cylinder(h=floor_thick + 2, d=gland_d);
    // Counterbore for gland nut
    translate([x, y, -1])
        cylinder(h=1.5, d=gland_d + 3);
}

// Pole mount tab (on bottom of case)
module pole_mount_tab(x, y) {
    translate([x, y, 0])
    difference() {
        hull() {
            translate([-pole_tab_w/2, 0, 0])
                cube([pole_tab_w, pole_tab_h, pole_tab_thick]);
            translate([-pole_tab_w/2, -2, 0])
                cube([pole_tab_w, 4, pole_tab_thick + 3]);
        }
        // Mounting hole
        translate([0, pole_tab_h * 0.6, -1])
            cylinder(h=pole_tab_thick + 5, d=pole_hole_d);
    }
}

// Vent hole (for Gore-Tex patch)
module vent(x, y) {
    translate([x, y, -1])
        cylinder(h=floor_thick + 2, d=vent_d);
    // Recess for patch
    translate([x, y, floor_thick - 0.5])
        cylinder(h=1, d=vent_d + 4);
}

// ==========================================================================
// BOTTOM SHELL
// ==========================================================================

module bottom_shell() {
    difference() {
        union() {
            // Main body
            rounded_box(ext_x, ext_y, ext_z, corner_r);
            
            // Pole mount tabs on back side
            translate([ext_x/4, -pole_tab_thick, 0])
                pole_mount_tab(0, pole_tab_thick);
            translate([ext_x * 3/4, -pole_tab_thick, 0])
                pole_mount_tab(0, pole_tab_thick);
        }
        
        // Hollow interior
        interior_cavity();
        
        // Cable gland holes (bottom side)
        for (i = [0 : gland_count - 1]) {
            x_pos = ext_x/2 + (i - (gland_count-1)/2) * gland_spacing;
            cable_gland(x_pos, ext_y/2);
        }
        
        // Vent (center of floor, offset to avoid cable glands)
        vent(ext_x/2, ext_y - wall - 5);
        
        // Lid screw holes (through floor for access from top)
        // Actually these are for inserts in the bosses
    }
    
    // Screw bosses at corners
    boss_offset = wall + boss_inset;
    translate([0, 0, 0]) {
        screw_boss(boss_offset, boss_offset);
        screw_boss(ext_x - boss_offset, boss_offset);
        screw_boss(boss_offset, ext_y - boss_offset);
        screw_boss(ext_x - boss_offset, ext_y - boss_offset);
    }
    
    // Board standoffs (bottom board = ESP32-C3)
    board_offset_x = wall + board_margin;
    board_offset_y = wall + board_margin;
    
    if (layout == "stacked") {
        // ESP32-C3 in center-bottom
        cx = wall + interior_x/2;
        cy = wall + interior_y/2;
        // 4 corners of ESP32 board
        for (px = [cx - esp_w/2 + 2, cx + esp_w/2 - 2],
             py = [cy - esp_l/2 + 2, cy + esp_l/2 - 2]) {
            standoff(px, py, standoff_h);
        }
    } else {
        // Side by side: ESP32 on left, RP2040 on right
        for (px = [board_offset_x + 2, board_offset_x + esp_w - 2],
             py = [board_offset_y + 2, board_offset_y + esp_l - 2]) {
            standoff(px, py, standoff_h);
        }
        // RP2040 standoffs
        rp_offset_x = board_offset_x + esp_w + board_margin;
        for (px = [rp_offset_x + 2, rp_offset_x + rp_w - 2],
             py = [board_offset_y + 2, board_offset_y + rp_l - 2]) {
            standoff(px, py, standoff_h);
        }
    }
}

// ==========================================================================
// LID
// ==========================================================================

module lid() {
    union() {
        difference() {
            // Lid plate
            rounded_box(ext_x, ext_y, lid_thick, corner_r);
            
            // O-ring groove on underside
            mirror([0, 0, 1])
                translate([0, 0, -lid_thick])
                    oring_groove();
            
            // Screw holes through lid
            boss_offset = wall + boss_inset;
            for (px = [boss_offset, ext_x - boss_offset],
                 py = [boss_offset, ext_y - boss_offset]) {
                translate([px, py, -1])
                    cylinder(h=lid_thick + 2, d=screw_d);
                // Countersink
                translate([px, py, lid_thick - 1.5])
                    cylinder(h=2, d1=screw_d, d2=screw_d + 3);
            }
            
            // Solar panel recess (top side)
            solar_x = ext_x - 2 * (wall + solar_recess_margin);
            solar_y = ext_y - 2 * (wall + solar_recess_margin);
            translate([wall + solar_recess_margin, wall + solar_recess_margin, lid_thick - solar_recess_depth])
                rounded_box(solar_x, solar_y, solar_recess_depth + 0.1, 2);
            
            // USB-C cutout (on one short edge of the lid, for programming access)
            // This is optional - can be sealed with tape for outdoor use
        }
    }
}

// ==========================================================================
// RENDER
// ==========================================================================

if (part == "bottom" || part == "both") {
    bottom_shell();
}

if (part == "lid" || part == "both") {
    translate([0, ext_y + 15, 0])
        lid();
}

// Dimensions text (commented out for clean STL)
// echo("=== ENCLOSURE DIMENSIONS ===");
// echo("Exterior:", ext_x, "x", ext_y, "x", (ext_z + lid_thick), "mm");
// echo("Print volume needed:", ext_x, "x", (ext_y * 2 + 15), "x", max(ext_z, lid_thick), "mm");
