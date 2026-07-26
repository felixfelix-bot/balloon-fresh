// ==========================================================================
// Balloon Dev Board Enclosure — VARIANT B (Big LR2021 Dev Board)
// 
// Same as balloon_dev_case.scad but fits LARGE LR2021 dev board with
// SMA connectors and external PA (~2W output) instead of the small
// bare NiceRF LoRa2021 module.
//
// Changes from Variant A:
//   - Radio board slot is much bigger (big LR2021 dev board)
//   - SMA bulkhead holes on side walls instead of cable glands for antennas
//   - Cable glands kept for solar/power only
//   - Radio board sits on its own layer (it's too big to stack under ESP32)
//
// Usage: openscad -o bottom.stl -D part="bottom" balloon_dev_case_big.scad
//        openscad -o lid.stl -D part="lid" balloon_dev_case_big.scad
// ==========================================================================

/* [Part Selection] */
part = "both"; // "bottom", "lid", "both"

/* [Board Dimensions — ADJUST WITH CALIPERS] */

// ESP32-C3 SuperMini V1 (Maker go)
esp_w = 22.52;
esp_l = 18.0;
esp_h = 1.6;

// BIG LR2021 Development Board (AliExpress, with PA + SMA connectors)
// Typical AliExpress LR2021 dev boards: ~50-55mm x 30-35mm
// Has dual SMA connectors (Sub-GHz + 2.4GHz) on one edge
// Has external PA chip for ~2W (+33dBm) output
// ADJUST THESE when you have calipers!
big_radio_w = 52.0;   // ESTIMATE — measure actual board
big_radio_l = 35.0;   // ESTIMATE — measure actual board
big_radio_h = 8.0;    // ESTIMATE — board + PA + SMA connector height
big_radio_pin_spacing = 2.54; // standard 2.54mm header pins

// RP2040 (SuperMini default — change if Pico)
rp_w = 21.5;
rp_l = 17.8;
rp_h = 1.6;

// GPS Module (oversized to fit all M10S breakouts)
gps_w = 34.0;
gps_l = 26.0;
gps_h = 4.0;

/* [SMA Connectors] */
sma_d = 6.5;           // SMA bulkhead hole diameter (standard SMA nut = 6mm)
sma_count = 2;         // Sub-GHz + 2.4GHz
sma_spacing = 14;      // distance between SMA connectors
// SMA connectors are on one EDGE of the big radio board
// We'll route them through the side wall

/* [Interior Layout] */
// Layout: 3 layers
//   Layer 1 (bottom): ESP32-C3 SuperMini (MCU)
//   Layer 2 (middle): Big LR2021 dev board (radio + PA)
//   Layer 3 (top):    RP2040 + GPS side by side

wire_clearance = 14;
board_margin = 4;

// Interior X: need to fit big radio board width + margin
interior_x = max(
    big_radio_w + board_margin * 2 + 4,
    rp_w + gps_w + board_margin * 3 + 4,
    esp_w + board_margin * 2
);

// Interior Y: fit longest board + margin
_interior_y_raw = max(
    big_radio_l + board_margin * 2,
    esp_l + board_margin * 2,
    gps_l + board_margin * 2
);
interior_y = max(_interior_y_raw, 40);

// Layer heights
esp_layer_h = esp_h + 3;        // ESP32 on standoffs
radio_layer_h = esp_layer_h + 4; // gap + radio board height
radio_top_h = radio_layer_h + big_radio_h;
top_layer_gap = 6;
top_layer_h = radio_top_h + top_layer_gap;
top_layer_boards_h = max(rp_h, gps_h);
interior_z = top_layer_h + top_layer_boards_h + wire_clearance;

echo("=== VARIANT B INTERIOR ===");
echo("X:", interior_x, "Y:", interior_y, "Z:", interior_z);

/* [Wall Thickness] */
wall = 2.5;
floor_thick = 2.5;
lid_thick = 3.0;

/* [External Dimensions] */
ext_x = interior_x + wall * 2;
ext_y = interior_y + wall * 2;
ext_z = interior_z + floor_thick;

echo("=== VARIANT B EXTERIOR ===");
echo("X:", ext_x, "Y:", ext_y, "Z (with lid):", ext_z + lid_thick);

/* [Corner Radius] */
corner_r = 5;

/* [Screw Bosses] */
screw_d = 3.2;
insert_d = 4.2;
insert_h = 5.0;
boss_d = 8;
boss_inset = 7;

/* [O-Ring Groove] */
oring_d = 2.0;
oring_groove_d = oring_d + 0.3;
oring_groove_h = oring_d * 0.75;
oring_wall_offset = 3.5;

/* [Cable Glands — for solar/power only] */
gland_d = 6.0;
gland_count = 1;

/* [Pole Mount] */
pole_tab_w = 20;
pole_tab_h = 12;
pole_hole_d = 5.5;
pole_tab_thick = 4;

/* [Board Mounting] */
standoff_h = 3;
standoff_d = 5;
board_screw_d = 1.8;

/* [Solar Panel Recess] */
solar_recess_depth = 1.5;
solar_recess_margin = 3;

/* [Ventilation] */
vent_d = 4;

/* [USB Access Port] */
usb_cutout_w = 11;
usb_cutout_h = 8;
usb_cutout = true;

/* [Print Quality] */
$fn = 48;

// ==========================================================================
// MODULES (shared with variant A)
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

// SMA bulkhead hole through wall
module sma_hole(x, z) {
    // x = position along the wall
    // z = height of hole center
    translate([-1, x, z])
        rotate([0, 90, 0])
            cylinder(h=wall + 2, d=sma_d);
    // Recess for SMA nut on outside
    translate([wall - 1, x, z])
        rotate([0, 90, 0])
            cylinder(h=2, d=sma_d + 3);
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
        
        // Cable gland for solar (center of floor)
        cable_gland(ext_x/2, ext_y/2);
        
        // Vent
        vent(ext_x - wall - 6, ext_y - wall - 6);
        
        // SMA holes on the wall where radio board SMA connectors face
        // Radio board is centered, SMA connectors on one edge (say, +Y side)
        // SMA height = radio layer height
        sma_z = floor_thick + radio_layer_h + big_radio_h / 2;
        for (i = [0 : sma_count - 1]) {
            x_pos = ext_x/2 + (i - (sma_count-1)/2) * sma_spacing;
            sma_hole_wall(x_pos, sma_z);
        }
        
        // USB-C cutout
        if (usb_cutout) {
            translate([ext_x/2 - usb_cutout_w/2, ext_y - wall + 0.5, floor_thick + 2])
                cube([usb_cutout_w, wall + 1, usb_cutout_h]);
        }
    }
    
    // Screw bosses
    boss_offset = wall + boss_inset;
    screw_boss(boss_offset, boss_offset);
    screw_boss(ext_x - boss_offset, boss_offset);
    screw_boss(boss_offset, ext_y - boss_offset);
    screw_boss(ext_x - boss_offset, ext_y - boss_offset);
    
    // ===== LAYER 1: ESP32-C3 (bottom, centered) =====
    esp_cx = wall + interior_x/2 - esp_w/2;
    esp_cy = wall + interior_y/2 - esp_l/2;
    for (px = [esp_cx + 2, esp_cx + esp_w - 2],
         py = [esp_cy + 2, esp_cy + esp_l - 2]) {
        standoff(px, py, standoff_h);
    }
    
    // ===== LAYER 2: Big LR2021 Dev Board (middle, centered) =====
    // Oriented so SMA connectors face toward +Y wall
    radio_cx = wall + interior_x/2 - big_radio_w/2;
    radio_cy = wall + board_margin; // push toward bottom so SMA connectors face the wall
    for (px = [radio_cx + 3, radio_cx + big_radio_w - 3],
         py = [radio_cy + 3, radio_cy + big_radio_l - 3]) {
        standoff(px, py, esp_layer_h, d_outer=6, d_inner=2.0);
    }
    
    // ===== LAYER 3: RP2040 + GPS (top, side by side) =====
    top_x_start = wall + board_margin;
    top_y = wall + (interior_y - max(rp_l, gps_l)) / 2;
    
    // RP2040 (left)
    rp_x = top_x_start;
    for (px = [rp_x + 2, rp_x + rp_w - 2],
         py = [top_y + 2, top_y + rp_l - 2]) {
        standoff(px, py, top_layer_h, d_outer=5);
    }
    
    // GPS (right)
    gps_x = top_x_start + rp_w + board_margin;
    for (px = [gps_x + 2, gps_x + gps_w - 2],
         py = [top_y + 2, top_y + gps_l - 2]) {
        standoff(px, py, top_layer_h, d_outer=5);
    }
}

// SMA hole through +Y wall (wall facing camera/back)
module sma_hole_wall(x_pos, z_pos) {
    // Hole through +Y wall
    translate([x_pos, ext_y - wall - 0.5, z_pos])
        rotate([90, 0, 0])
            cylinder(h=wall + 1, d=sma_d);
    // Recess for SMA nut on outside
    translate([x_pos, ext_y - 0.5, z_pos])
        rotate([90, 0, 0])
            cylinder(h=2, d=sma_d + 4);
}

// ==========================================================================
// LID
// ==========================================================================

module lid() {
    difference() {
        rounded_box(ext_x, ext_y, lid_thick, corner_r);
        
        // O-ring groove
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
        
        // Solar panel recess
        solar_x = ext_x - 2 * (wall + solar_recess_margin);
        solar_y = ext_y - 2 * (wall + solar_recess_margin);
        translate([wall + solar_recess_margin, wall + solar_recess_margin, lid_thick - solar_recess_depth])
            rounded_box(solar_x, solar_y, solar_recess_depth + 0.1, 2);
        
        // GPS antenna window
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
