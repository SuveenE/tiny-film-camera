"""Generate STL for the C-bracket spacer.

Symmetric design: 6.5x6.5mm pads, 1.5mm thick, 25mm gap, 2mm wall.
All edges filleted for smooth printing. Holes through each pad for M2.5 screws.

Run: python3 assets/generate_c_bracket.py
Output: assets/c_bracket_spacer.stl
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
gap = 25.0
pad_len = 6.5
pad_w = 6.5
pad_t = 1.5
wall = 2.0
hole_d = 2.8
fillet_r = 0.6

total_h = pad_t + gap + pad_t   # 28
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
cyl_bot = BRepPrimAPI_MakeCylinder(ax_bot, hole_d / 2, pad_t + 1.0).Shape()

ax_top = gp_Ax2(gp_Pnt(pad_len / 2, total_h - pad_t - 0.5, pad_w / 2), gp_Dir(0, 1, 0))
cyl_top = BRepPrimAPI_MakeCylinder(ax_top, hole_d / 2, pad_t + 1.0).Shape()

cut1 = BRepAlgoAPI_Cut(filleted, cyl_bot)
cut1.Build()
cut2 = BRepAlgoAPI_Cut(cut1.Shape(), cyl_top)
cut2.Build()

final = cq.Workplane().add(Shape(cut2.Shape()))

# Export
output_path = Path(__file__).parent / "c_bracket_spacer.stl"
cq.exporters.export(final, str(output_path), tolerance=0.05, angularTolerance=0.5)

print(f"Exported: {output_path}")
print(f"File size: {output_path.stat().st_size} bytes")
print(f"Overall: {total_d} x {total_h} x {pad_w} mm")
print(f"Pads: {pad_len} x {pad_w} x {pad_t} mm")
print(f"Gap: {gap} mm | Wall: {wall} mm")
print(f"Fillet: {fillet_r} mm on all edges")
print(f"Hole: {hole_d} mm centered at ({pad_len/2}, {pad_w/2}) on each pad")
print()
print("Preview: drag .stl into https://www.viewstl.com/")
