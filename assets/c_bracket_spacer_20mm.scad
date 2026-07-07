// 3D-Printable C-Shaped Corner Spacer Bracket
// 6.5x6.5mm Pads, 1.5mm Thickness, 20mm Gap, 2mm Wall

$fn = 100; // High resolution for perfect circles

// --- Key Dimensions ---
gap = 20.0;         // Gap between mounting surfaces
pad_len = 6.5;      // Pad length (X axis)
pad_w = 6.5;        // Pad width (Z axis, extruded thickness)
pad_t = 1.5;        // Pad thickness (Y axis)
wall = 2.0;         // Wall thickness
hole_d = 2.8;       // M2.5 screw clearance

r_out = 2.0;        // Outer corner rounding
r_in = 1.0;         // Inner corner rounding

// --- Derived Calculations ---
total_h = pad_t + gap + pad_t; // 23.0 mm total height
total_d = pad_len + wall;      // 8.5 mm total depth

// --- 3D Generation ---
difference() {
    // 1. Main Bracket Body (Generated lying flat)
    linear_extrude(height = pad_w) {
        difference() {
            // Outer Boundary Shape
            hull() {
                translate([0, 0]) square([0.1, total_h]);
                translate([total_d - r_out, r_out]) circle(r=r_out);
                translate([total_d - r_out, total_h - r_out]) circle(r=r_out);
            }

            // Inner Cutout Shape (Fixed to guarantee flat 1.5mm pads)
            hull() {
                // Front opening
                translate([-1, pad_t]) square([0.1, gap]);
                // Force perfectly horizontal cuts for the pads
                translate([-1, pad_t]) square([pad_len - r_in + 1, 0.01]);
                translate([-1, total_h - pad_t - 0.01]) square([pad_len - r_in + 1, 0.01]);
                // Inner rounded corners
                translate([pad_len - r_in, pad_t + r_in]) circle(r=r_in);
                translate([pad_len - r_in, total_h - pad_t - r_in]) circle(r=r_in);
            }
        }
    }

    // 2. Center-Punch Bottom Pad Hole
    translate([pad_len / 2, pad_t / 2, pad_w / 2])
        rotate([90, 0, 0])
        cylinder(h = pad_t * 4, d = hole_d, center = true);

    // 3. Center-Punch Top Pad Hole
    translate([pad_len / 2, total_h - (pad_t / 2), pad_w / 2])
        rotate([90, 0, 0])
        cylinder(h = pad_t * 4, d = hole_d, center = true);
}
