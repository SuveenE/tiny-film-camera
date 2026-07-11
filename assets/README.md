# 3D-printable case assets

STL and OpenSCAD files for the tiny-film hardware enclosure.

Original project files in this folder (C-bracket spacers and generators) are
covered by the repository [MIT License](../LICENSE). Third-party Printables
models keep their upstream licenses, listed below.

## Third-party models

### Raspberry Pi Zero 2 Case MK3 Camera

- **Designer:** [XenoTechie](https://www.printables.com/@XenoTechie_72441)
- **Source:** https://www.printables.com/model/799255-raspberry-pi-zero-2-case-mk3-camera
- **License:** [Creative Commons Attribution 4.0 (CC BY)](https://creativecommons.org/licenses/by/4.0/)
- **Files in this repo:**
  - `Raspberry_Pi_Zero_2_Case_MK3_Camera_top.stl` — top cover (unmodified)
  - `Raspberry_Pi_Zero_2_Case_MK3_Camera_camera-suv-text.stl` — camera plate
    remixed with custom “SUV” branding (derivative of the upstream camera
    plate; redistributed under the same CC BY terms with attribution)

### Raspberry Pi Zero 2 WH Waveshare UPS Case

- **Designer:** [PiotrWolinski](https://www.printables.com/@PiotrWolinski_579340)
- **Source:** https://www.printables.com/model/1546215-raspberry-pi-zero-2-wh-waveshare-ups-case
- **License:** [Creative Commons Attribution-ShareAlike 4.0 (CC BY-SA)](https://creativecommons.org/licenses/by-sa/4.0/)
- **Files in this repo:**
  - `rpizerocase.stl` — base case (unmodified). ShareAlike applies to this
    file and any adaptations of it.

## Original project files

- `c_bracket_spacer.scad` / `c_bracket_spacer.stl` — C-shaped corner spacer
- `c_bracket_spacer_20mm.scad` / `c_bracket_spacer_20mm.stl` /
  `c_bracket_spacer_20mm_2.1_2.8.stl` — 20 mm spacer variants
- `generate_c_bracket.py` / `generate_c_bracket_20mm.py` — OpenSCAD helpers
- `v0/v0-build.jpg` — photo of an assembled build
