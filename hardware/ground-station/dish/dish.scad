// ============================================================================
// dish.scad — Parametric parabolic reflector for the 2.4 GHz ground station
//
// Status: DESIGN STUDY ONLY. Nothing here is ordered, fabbed, or frozen.
// Companion analysis: docs/analysis/ground-station-dish.md
//
// Geometry (all mm):
//   Paraboloid of revolution:  z = r^2 / (4 f)   with f = f_over_d * diameter
//   Rim sagitta (depth):       depth = D^2 / (16 f) = D / (16 * f_over_d)
//   Feed sits ON AXIS at z = f (above the vertex at z = 0).
//
// Modes (part_mode):
//   "shell"   — one solid revolved shell (for inspection / small dishes)
//   "petal"   — `segments` wedge sectors of the same shell, each with a flat
//               rim flange + bolt tabs (the 3D-printable segmentation)
//   "ribs"    — parabolic rib profiles only + hub ring + outer ring
//               (the recommended build: ribs + stretched aluminium mesh)
//
// Units are MILLIMETRES throughout. Dish points +Z (toward the feed/sky).
// ============================================================================

// ----------------------------- core parameters ------------------------------
diameter    = 1200;   // reflector aperture D [mm]  (0.6 / 0.9 / 1.2 / 1.5 m studied)
f_over_d    = 0.4;    // focal ratio f/D (0.35 / 0.4 / 0.45 studied)
thickness   = 2.0;    // shell wall thickness [mm] (printed shell / moulded skin)
rim_height  = 8;      // rolled rim / edge flange height [mm] (stiffens free edge)
segments    = 12;     // petal count for part_mode="petal"
rib_count   = 12;     // number of radial ribs for part_mode="ribs"
rib_width   = 12;     // rib stock width [mm] (radial face)
rib_height  = 25;     // rib depth (perpendicular to shell) [mm]

// ------------------------------ mounting ------------------------------------
mount_hole_pattern = 4;    // number of hub mount holes (0 = none)
mount_hole_pcir    = 40;   // pitch-circle radius of hub mount holes [mm]
mount_hole_d       = 5.5;  // M5 clearance [mm]
boss_d             = 60;   // central boss OD for feed-support spider [mm]
boss_h             = 15;   // boss height [mm]
boss_bolt_d        = 6.6;  // M6 clearance through boss centre [mm]

// ------------------------------ mesh attachment ------------------------------
mesh_hole_d   = 3.2;  // clearance holes for mesh lacing wire / small screws [mm]
mesh_hole_gap = 90;   // spacing along ribs between mesh attachment holes [mm]

// ------------------------------ tessellation --------------------------------
// $fn controls revolve/rotate-extrude facets; $fa/$fr control the parabola
// polyline. For STL smoothness at 1.2 m the defaults below are adequate;
// the surface-RMS analysis lives in the companion doc, not in the mesh.
fn_circle = 144;
fa_curve  = 4;      // max facet angle for the parabola profile polyline
fs_curve  = 6;      // max facet size [mm]

$fn = fn_circle;
$fa = fa_curve;
$fs = fs_curve;

// ============================ computed geometry ==============================
function focal()      = f_over_d * diameter;            // f [mm]
function depth()      = pow(diameter,2) / (16*focal()); // sagitta [mm]
function r_at(z)      = sqrt(4*focal()*z);              // radius at height z
function feed_angle() = 2 * atan( (diameter/2) / (focal() - depth()) ); // full subtended angle (deg)
// NOTE feed_angle(): half-angle from the axis to the rim AS SEEN FROM THE
// FOCUS = atan((D/2)/(f - depth)); full illumination (subtended) angle = 2x.
// Matches docs/analysis/ground-station-dish.md table 1.

echo(str("dish: D=", diameter, "mm  f/D=", f_over_d,
         "  f=", focal(), "mm  depth=", depth(), "mm",
         "  illumination angle=", feed_angle(), "deg"));

// ------------------------------ helpers -------------------------------------
// Parabolic profile polygon (2D, x=radius, y=height), from axis to rim,
// optionally thickened downward by `t`.
module parabola_profile(t) {
    R = diameter/2;
    f = focal();
    n = 96;                      // profile polyline resolution
    points_outer = [for (i=[0:n]) let(r = R*i/n) [r, pow(r,2)/(4*f)]];
    points_inner = [for (i=[0:n]) let(r = R*i/n) [r, pow(r,2)/(4*f) + t]];
    // build closed polygon: outer curve rim->axis, then inner curve back
    polygon(concat(
        [for (i=[n:-1:0]) points_outer[i]],
        points_inner
    ));
}

// Solid paraboloid shell: surface thickened downward (convex side down when
// printed rim-down).
module dish_shell_solid() {
    rotate_extrude(convexity = 4)
        translate([0.001, 0])       // keep manifold on the axis
            parabola_profile(thickness);
}

// Rolled/stiffened rim: torus at the rim edge.
module rim_torus() {
    R = diameter/2;
    zrim = pow(R,2)/(4*focal());
    rotate_extrude(convexity = 4)
        translate([R, zrim])
            circle(d = rim_height, $fn = 48);
}

// Full assembled reflector shell (single piece).
module part_shell() {
    difference() {
        union() {
            dish_shell_solid();
            rim_torus();
            central_boss();
        }
        mount_holes();
    }
}

// One petal: wedge sector of the shell between azimuth a0..a1, plus a flat
// flange strip along each radial cut edge for bolts/screws between petals.
module part_petal(k) {
    a = 360/segments;
    a0 = k*a;
    a1 = (k+1)*a;
    difference() {
        intersection() {
            union() { dish_shell_solid(); rim_torus(); }
            // wedge sector spanning exactly a0..a1
            rotate([0, 0, (a0+a1)/2])
                linear_extrude(height = diameter*2, center = true, convexity = 4)
                    polygon([[0, 0],
                             [diameter, -diameter/2 * tan(a/2)],
                             [diameter,  diameter/2 * tan(a/2)]]);
        }
    }
    // ---- radial joint flange along ONE cut edge (a0) ----
    // The mating petal's shell edge is drilled to match; one flange per
    // joint avoids doubled tabs where adjacent petals meet.
    rotate([0, 0, a0])
        radial_flange();
}

// Flat bolt flange running radially along a petal cut edge, following the
// parabola vertically (a vertical strip, width flange_w, standing on the
// shell's inner surface at the cut plane).
flange_w = 16;
module radial_flange() {
    R = diameter/2;
    f = focal();
    n = 48;
    // a thin wall at y=0 (the cut plane), from axis to rim
    points = [for (i=[0:n]) let(x = R*i/n) [x, pow(x,2)/(4*f)]];
    difference() {
        union() {
            for (i=[0:n-1])
                hull() {
                    translate([points[i][0], 0, points[i][1]])     cube([0.1, flange_w, rib_height*0.6], center=false);
                    translate([points[i+1][0], 0, points[i+1][1]]) cube([0.1, flange_w, rib_height*0.6], center=false);
                }
        }
        // nothing subtracted here; holes added by mesh_holes-ish pattern below
    }
    // bolt holes down the flange
    nholes = floor(R / mesh_hole_gap);
    for (h = [1:nholes])
        let(x = h*mesh_hole_gap, z = pow(x,2)/(4*f))
            translate([x, flange_w/2, rib_height*0.3])
                rotate([90, 0, 0])
                    cylinder(d = mesh_hole_d, h = flange_w + 2, center = true, $fn = 24);
}

// Hub mount holes (circle of mount_hole_pattern holes near centre).
module mount_holes() {
    if (mount_hole_pattern > 0)
        for (i = [0:mount_hole_pattern-1])
            rotate([0, 0, i*360/mount_hole_pattern])
                translate([mount_hole_pcir, 0, -1])
                    cylinder(d = mount_hole_d,
                             h = pow(mount_hole_pcir,2)/(4*focal()) + thickness + rim_height + 2,
                             $fn = 24);
}

// Central boss for the feed-support spider / positioner attach.
module central_boss() {
    difference() {
        cylinder(d = boss_d, h = boss_h, $fn = 48);
        translate([0, 0, -1]) cylinder(d = boss_bolt_d, h = boss_h + 2, $fn = 24);
    }
}

// ---------------- mode: ribs only (recommended build) -----------------------
// Radial parabolic rib: an extruded parabola-profile beam from hub ring to
// outer ring, standing with its web perpendicular to the aperture plane.
module radial_rib(k) {
    R = diameter/2;
    f = focal();
    n = 64;
    pts = [for (i=[0:n]) let(x = R*i/n) [x, pow(x,2)/(4*f)]];
    rotate([0, 0, k*360/rib_count])
    for (i=[0:n-1])
        hull() {
            translate([pts[i][0], 0, pts[i][1]])     cube([0.1, rib_width, rib_height], center=false);
            translate([pts[i+1][0], 0, pts[i+1][1]]) cube([0.1, rib_width, rib_height], center=false);
        }
}

hub_ring_id = boss_d - 10;             // ring overlaps the boss -> one volume
hub_ring_od = boss_d + 2*rib_height;
module hub_ring() {
    // short cylinder ring the ribs land on, centred on axis at z=0.
    translate([0, 0, -rib_height/2])
        difference() {
            cylinder(d = hub_ring_od, h = rib_height, $fn = 64);
            translate([0, 0, -1]) cylinder(d = hub_ring_id, h = rib_height + 2, $fn = 64);
        }
}

outer_ring_t = rib_width;   // ring stock width, matches rib width
outer_ring_h = 8;            // ring thickness (axial), thinner than ribs
module outer_ring() {
    R = diameter/2;
    zrim = pow(R,2)/(4*focal());
    translate([0, 0, zrim - outer_ring_h/2])
        difference() {
            cylinder(r = R + outer_ring_t/2, h = outer_ring_h, $fn = 128);
            translate([0, 0, -1]) cylinder(r = R - outer_ring_t/2, h = outer_ring_h + 2, $fn = 128);
        }
}

module part_ribs() {
    hub_ring();
    outer_ring();
    for (k = [0:rib_count-1]) radial_rib(k);
    central_boss();
}

// ------------------------------ dispatch ------------------------------------
// part_mode: "shell" | "petal" | "ribs"
part_mode = "shell";

if (part_mode == "shell") part_shell();
if (part_mode == "petal") {
    // emit ONE petal per render (loop from the CLI with -D petal_index=N)
    petal_index = 0;
    part_petal(petal_index);
}
if (part_mode == "petals_all") {
    for (k = [0:segments-1]) part_petal(k);
}
if (part_mode == "ribs") part_ribs();

// ------------------------------ sanity echo --------------------------------
assert(diameter > 0 && f_over_d > 0);
assert(thickness > 0.4, "shell thinner than 0.4 mm is not printable");
