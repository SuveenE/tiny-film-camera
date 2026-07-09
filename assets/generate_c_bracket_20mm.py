"""Generate STL for the 20mm C-bracket spacer with asymmetric holes.

6.5x6.5mm pads, 1.5mm thick, 20mm gap, 2mm wall.
Bottom pad hole 2.1mm, top pad hole 2.8mm (M2.5 clearance).
All edges filleted for smooth printing.

Run: python3 assets/generate_c_bracket_20mm.py
Output: assets/c_bracket_spacer_20mm_2.1_2.8.stl
"""

import cadquery as cq
from cadquery import Shape
from OCP.gp import gp_Pnt, gp_Dir, gp_Ax2
from OCP.BRepPrimAPI import BRepPrimAPI_MakeCylinder
from OCP.BRepAlgoAPI import BRepAlgoAPI_Cut
from OCP.BRepFilletAPI import BRepFilletAPI_MakeFillet
from OCP.TopExp import TopExp_Explorer
from OCP.TopAbs import TopAbs_EDGE
from OCP.TopoDS import TopoDS
from pathlib import Path

# --- Parameters ---
gap = 20.0
pad_len = 6.5
pad_w = 6.5
pad_t = 1.5
wall = 2.0
hole_d_bottom = 2.1
hole_d_top = 2.8
fillet_r = 0.6

total_h = pad_t + gap + pad_t   # 23
total_d = pad_len + wall         # 8.5

# C-profile in XY, extruded along Z
pts = [
    (0, 0),
    (total_d, 0),
    (total_d, total_h),
    (0, total_h),
    (0, total_h - pad_t),
    (pad_len, total_h - pad_t),
    (pad_len, pad_t),
    (0, pad_t),
]

bracket = (
    cq.Workplane("XY")
    .polyline(pts)
    .close()
    .extrude(pad_w)
)

# Fillet all edges for smooth printing
solid = bracket.val().wrapped
fillet_maker = BRepFilletAPI_MakeFillet(solid)
explorer = TopExp_Explorer(solid, TopAbs_EDGE)
while explorer.More():
    edge = TopoDS.Edge_s(explorer.Current())
    fillet_maker.Add(fillet_r, edge)
    explorer.Next()
fillet_maker.Build()
filleted = fillet_maker.Shape()

# Cut holes through pads (after filleting so hole edges stay sharp)
ax_bot = gp_Ax2(gp_Pnt(pad_len / 2, -0.5, pad_w / 2), gp_Dir(0, 1, 0))
cyl_bot = BRepPrimAPI_MakeCylinder(ax_bot, hole_d_bottom / 2, pad_t + 1.0).Shape()

ax_top = gp_Ax2(gp_Pnt(pad_len / 2, total_h - pad_t - 0.5, pad_w / 2), gp_Dir(0, 1, 0))
cyl_top = BRepPrimAPI_MakeCylinder(ax_top, hole_d_top / 2, pad_t + 1.0).Shape()

cut1 = BRepAlgoAPI_Cut(filleted, cyl_bot)
cut1.Build()
cut2 = BRepAlgoAPI_Cut(cut1.Shape(), cyl_top)
cut2.Build()

final = cq.Workplane().add(Shape(cut2.Shape()))

# Export
output_path = Path(__file__).parent / "c_bracket_spacer_20mm_2.1_2.8.stl"
cq.exporters.export(final, str(output_path), tolerance=0.05, angularTolerance=0.5)

print(f"Exported: {output_path}")
print(f"File size: {output_path.stat().st_size} bytes")
print(f"Overall: {total_d} x {total_h} x {pad_w} mm")
print(f"Pads: {pad_len} x {pad_w} x {pad_t} mm")
print(f"Gap: {gap} mm | Wall: {wall} mm")
print(f"Fillet: {fillet_r} mm on all edges")
print(f"Bottom hole: {hole_d_bottom} mm | Top hole: {hole_d_top} mm")
print()
print("Preview: drag .stl into https://www.viewstl.com/")
