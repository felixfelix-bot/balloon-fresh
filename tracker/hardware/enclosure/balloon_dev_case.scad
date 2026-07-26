// ==========================================================================
// Balloon Dev Board Waterproof Enclosure v2
// 
// Fits: ESP32-C3 SuperMini + LR2021 + RP2040 + GPS (MAX-M10S)
// Target: IP65+ outdoor use, pole mount with solar
// Print: PETG or ASA recommended (UV + heat resistant)
// 
// Layout: Two-layer stacked
//   Bottom layer: ESP32-C3 SuperMini (with LR2021 soldered on top)
//   Top layer:    RP2040 + GPS module
// 
// Usage: openscad -o bottom.stl -D part="bottom" balloon_dev_case.scad
//        openscad -o lid.stl -D part="lid" balloon_dev_case.scad
// ==========================================================================

/* [Part Selection] */
part = "both"; // "bottom", "lid", "both"

/* [Board Dimensions - ADJUST THESE WITH CALIPERS] */

// ESP32-C3 SuperMini V1 (Maker go)
esp_w = 22.52;
esp_l = 18.0;
esp_h = 1.6;      // PCB thickness

// NiceRF LR2021 (soldered on top of ESP32)
lr_w = 19.72;
lr_l = 15.0;
lr_h = 2.2;       // module height above PCB
lr_gap = 2.5;     // solder joint gap under module

// RP2040 (DEFAULT: SuperMini form factor — CHANGE if Pico!)
rp_w = 21.5;
rp_l = 17.8;
rp_h = 1.6;

// GPS Module (u-blox MAX-M10S on breakout board)
// OVERSIZED to fit ALL common breakouts:
//   SparkFun: 32 x 24mm (LARGEST — sets our slot size)
//   Adafruit: 25 x 25mm
//   Generic AliExpress: ~24 x 24mm
//   Bare M10S chip: 15.5 x 15.5 x 3.4mm
// Blue LED that flashes on GPS fix — leave room for it facing up
gps_w = 34.0;     // SparkFun 32mm + 2mm clearance
gps_l = 26.0;     // SparkFun 24mm + 2mm clearance
gps_h = 4.0;      // board + patch antenna + header pins

/* [Interior Layout] */
layout = "stacked"; // "stacked" or "sidebyside"

// Clearance above boards for wires/connectors
wire_clearance = 14;
// Margin around boards
board_margin = 4;

// Computed interior dimensions
// Stacked: ESP32+LR2021 on bottom, RP2040+GPS side by side on top
interior_x = max(esp_w + board_margin*2 + 4, rp_w + gps_w + board_margin*3 + 4);
_interior_y_raw = max(esp_l + board_margin*2, rp_l + board_margin*2, gps_l + board_margin*2) + 4;
interior_y = max(_interior_y_raw, 40); // minimum 40mm

// Board stack height (bottom to top)
bottom_layer_h = esp_h + lr_gap + lr_h;     // ESP32 + LR2021 stack
layer_gap = 6;                                // air gap between layers
top_layer_h = max(rp_h, gps_h);              // RP2040 + GPS same layer
interior_z = bottom_layer_h + layer_gap + top_layer_h + wire_clearance;

echo("=== INTERIOR ===");
echo("X:", interior_x, "Y:", interior_y, "Z:", interior_z);

/* [Wall Thickness] */
wall = 2.5;
floor_thick = 2.5;
lid_thick = 3.0;

/* [External Dimensions] */
ext_x = interior_x + wall * 2;
ext_y = interior_y + wall * 2;
ext_z = interior_z + floor_thick;

echo("=== EXTERIOR ===");
echo("X:", ext_x, "Y:", ext_y, "Z (bottom only):", ext_z);
echo("Z (with lid):", ext_z + lid_thick);

/* [Corner Radius] */
corner_r = 5;

/* [Screw Bosses] */
screw_d = 3.2;       // M3 screw clearance
insert_d = 4.2;      // heat-set insert OD
insert_h = 5.0;
boss_d = 8;
boss_inset = 7;

/* [O-Ring Groove] */
oring_d = 2.0;
oring_groove_d = oring_d + 0.3;
oring_groove_h = oring_d * 0.75;
oring_wall_offset = 3.5;

/* [Cable Glands] */
gland_d = 6.0;
gland_count = 3;
gland_spacing = 14;

/* [Pole Mount] */
pole_tab_w = 20;
pole_tab_h = 12;
pole_hole_d = 5.5;
pole_tab_thick = 4;

/* [Board Mounting] */
standoff_h = 3;
standoff_d = 5;
board_screw_d = 1.8;

// Top layer standoff height (above bottom layer)
top_standoff_h = bottom_layer_h + layer_gap;
top_standoff_d = 5;

/* [Solar Panel Recess - in lid] */
solar_recess_depth = 1.5;
solar_recess_margin = 3;

/* [Ventilation] */
vent_d = 4;

/* [USB Access Port] */
// Side cutout for USB-C programming without opening case
usb_cutout_w = 11;
usb_cutout_h = 8;
usb_cutout = true; // set false for fully sealed

/* [GPS Antenna Clear] */
// GPS patch antenna needs sky view — make sure it's near top
// The GPS board should face up toward the lid

/* [Print Quality] */
$fn = 48;

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

module interior_cavity() {
    translate([wall, wall, floor_thick])
        cube([interior_x, interior_y, interior_z + 1]);
}

module screw_boss(x, y) {
    translate([x, y, 0])
        difference() {
            cylinder(h=floor_thick + insert_h + 2, d=boss_d);
            translate([0, 0, floor_thick])
                cylinder(h=insert_h + 0.5, d=insert_d);
        }
}

module oring_groove() {
    offset_d = oring_wall_offset;
    gx = ext_x - 2 * offset_d;
    gy = ext_y - 2 * offset_d;
    gr = max(corner_r - offset_d, 1);
    
    translate([0, 0, -0.1])
    difference() {
        translate([offset_d, offset_d, 0])
            rounded_box(gx, gy, oring_groove_h + 0.2, gr);
        translate([offset_d + oring_groove_d, offset_d + oring_groove_d, -0.1])
            rounded_box(
                gx - 2 * oring_groove_d, 
                gy - 2 * oring_groove_d, 
                oring_groove_h + 0.4,
                max(gr - oring_groove_d, 0.5)
            );
    }
}

module standoff(x, y, h, d_outer=5, d_inner=1.8) {
    translate([x, y, floor_thick])
        difference() {
            cylinder(h=h, d=d_outer);
            cylinder(h=h + 1, d=d_inner);
        }
}

module cable_gland(x, y) {
    translate([x, y, -1])
        cylinder(h=floor_thick + 2, d=gland_d);
    translate([x, y, -1])
        cylinder(h=1.5, d=gland_d + 3);
}

module pole_mount_tab(x, y) {
    translate([x, y, 0])
    difference() {
        hull() {
            translate([-pole_tab_w/2, 0, 0])
                cube([pole_tab_w, pole_tab_h, pole_tab_thick]);
            translate([-pole_tab_w/2, -2, 0])
                cube([pole_tab_w, 4, pole_tab_thick + 3]);
        }
        translate([0, pole_tab_h * 0.6, -1])
            cylinder(h=pole_tab_thick + 5, d=pole_hole_d);
    }
}

module vent(x, y) {
    translate([x, y, -1])
        cylinder(h=floor_thick + 2, d=vent_d);
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
            
            // Pole mount tabs
            translate([ext_x/4, -pole_tab_thick, 0])
                pole_mount_tab(0, pole_tab_thick);
            translate([ext_x * 3/4, -pole_tab_thick, 0])
                pole_mount_tab(0, pole_tab_thick);
        }
        
        // Hollow interior
        interior_cavity();
        
        // Cable glands (center of floor)
        for (i = [0 : gland_count - 1]) {
            x_pos = ext_x/2 + (i - (gland_count-1)/2) * gland_spacing;
            cable_gland(x_pos, ext_y/2);
        }
        
        // Vent (offset corner)
        vent(ext_x - wall - 6, ext_y - wall - 6);
        
        // USB-C cutout (on short end, for programming)
        if (usb_cutout) {
            translate([ext_x/2 - usb_cutout_w/2, ext_y - wall + 0.5, floor_thick + bottom_layer_h - 1])
                cube([usb_cutout_w, wall + 1, usb_cutout_h]);
        }
    }
    
    // Screw bosses at corners
    boss_offset = wall + boss_inset;
    screw_boss(boss_offset, boss_offset);
    screw_boss(ext_x - boss_offset, boss_offset);
    screw_boss(boss_offset, ext_y - boss_offset);
    screw_boss(ext_x - boss_offset, ext_y - boss_offset);
    
    // ===== BOTTOM LAYER: ESP32-C3 + LR2020 (centered) =====
    // ESP32-C3 standoffs
    esp_cx = wall + interior_x/2 - esp_w/2;
    esp_cy = wall + interior_y/2 - esp_l/2;
    for (px = [esp_cx + 2, esp_cx + esp_w - 2],
         py = [esp_cy + 2, esp_cy + esp_l - 2]) {
        standoff(px, py, standoff_h);
    }
    
    // ===== TOP LAYER: RP2040 + GPS (side by side) =====
    // Compute top layer position
    top_x_start = wall + board_margin;
    top_y = wall + (interior_y - max(rp_l, gps_l)) / 2;
    
    // RP2040 standoffs (left half)
    rp_x = top_x_start;
    for (px = [rp_x + 2, rp_x + rp_w - 2],
         py = [top_y + 2, top_y + rp_l - 2]) {
        standoff(px, py, top_standoff_h, d_outer=top_standoff_d);
    }
    
    // GPS standoffs (right half)
    gps_x = top_x_start + rp_w + board_margin;
    for (px = [gps_x + 2, gps_x + gps_w - 2],
         py = [top_y + 2, top_y + gps_l - 2]) {
        standoff(px, py, top_standoff_h, d_outer=top_standoff_d);
    }
}

// ==========================================================================
// LID
// ==========================================================================

module lid() {
    difference() {
        // Lid plate
        rounded_box(ext_x, ext_y, lid_thick, corner_r);
        
        // O-ring groove on underside
        mirror([0, 0, 1])
            translate([0, 0, -lid_thick])
                oring_groove();
        
        // Screw holes
        boss_offset = wall + boss_inset;
        for (px = [boss_offset, ext_x - boss_offset],
             py = [boss_offset, ext_y - boss_offset]) {
            translate([px, py, -1])
                cylinder(h=lid_thick + 2, d=screw_d);
            translate([px, py, lid_thick - 1.5])
                cylinder(h=2, d1=screw_d, d2=screw_d + 3);
        }
        
        // Solar panel recess (top)
        solar_x = ext_x - 2 * (wall + solar_recess_margin);
        solar_y = ext_y - 2 * (wall + solar_recess_margin);
        translate([wall + solar_recess_margin, wall + solar_recess_margin, lid_thick - solar_recess_depth])
            rounded_box(solar_x, solar_y, solar_recess_depth + 0.1, 2);
        
        // GPS patch antenna window — thin material for better signal
        // Cut a thin area over where GPS board sits (right side)
        gps_cx = wall + board_margin + rp_w + board_margin + gps_w/2;
        gps_cy = wall + interior_y/2;
        translate([gps_cx - gps_w/2 + 3, gps_cy - gps_l/2 + 3, lid_thick - 0.8])
            rounded_box(gps_w - 6, gps_l - 6, 1.0, 2);
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
