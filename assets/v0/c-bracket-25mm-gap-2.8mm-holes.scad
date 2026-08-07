// 3D-Printable C-Shaped Corner Spacer Bracket
// Perfectly symmetric, 6.5x6.5mm Pads, 1.5mm Thickness, 25mm Gap, 2mm Wall

$fn = 100; // High resolution for smooth holes and fillets

// --- Key Dimensions ---
gap = 25;           // Gap between mounting surfaces
pad_len = 6.5;      // Pad length (X axis)
pad_w = 6.5;        // Pad width (Z axis, extruded thickness)
pad_t = 1.5;        // Pad thickness (Y axis)
wall = 2.0;         // Wall thickness
hole_d = 2.8;       // M2.5 screw clearance

r_out = 2.0;        // Outer corner rounding
r_in = 1.0;         // Inner corner rounding

// --- Derived Calculations ---
total_h = pad_t + gap + pad_t; // 28 mm total height
total_d = pad_len + wall;      // 8.5 mm total depth

// --- 3D Generation ---
difference() {
    // 1. Main Bracket Body (Generated lying flat for optimal printing)
    linear_extrude(height = pad_w) {
        difference() {
            // Outer Boundary
            hull() {
                // Front edges of the pads
                translate([0, 0]) square([0.1, pad_t]);
                translate([0, total_h - pad_t]) square([0.1, pad_t]);

                // Back outer rounded corners
                translate([total_d - r_out, r_out]) circle(r=r_out);
                translate([total_d - r_out, total_h - r_out]) circle(r=r_out);
            }

            // Inner Cutout
            hull() {
                // Open front section between the pads
                translate([-1, pad_t]) square([0.1, gap]);

                // Back inner rounded corners
                translate([pad_len - r_in, pad_t + r_in]) circle(r=r_in);
                translate([pad_len - r_in, total_h - pad_t - r_in]) circle(r=r_in);
            }
        }
    }

    // 2. Drill Bottom Pad Hole (Horizontal orientation)
    // Perfectly centered at 3.25mm from the edges
    translate([pad_len / 2, -1, pad_w / 2])
        rotate([-90, 0, 0])
        cylinder(h = pad_t + 2, d = hole_d);

    // 3. Drill Top Pad Hole (Horizontal orientation)
    // Perfectly centered at 3.25mm from the edges
    translate([pad_len / 2, total_h - pad_t - 1, pad_w / 2])
        rotate([-90, 0, 0])
        cylinder(h = pad_t + 2, d = hole_d);
}
