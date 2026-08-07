# 3D-printable case assets

STL and OpenSCAD files for the tiny-film hardware enclosure.

Original project files under `assets/` (C-bracket spacers and generators) are
covered by the repository [MIT License](../LICENSE). Third-party Printables
models keep their upstream licenses, listed below.

## Third-party models

### Raspberry Pi Zero 2 Case MK3 Camera

- **Designer:** [XenoTechie](https://www.printables.com/@XenoTechie_72441)
- **Source:** https://www.printables.com/model/799255-raspberry-pi-zero-2-case-mk3-camera
- **License:** [Creative Commons Attribution 4.0 (CC BY)](https://creativecommons.org/licenses/by/4.0/)
- **Files in this repo:**
  - `v0/pi-zero-2w-camera-case-top.stl` — top cover (unmodified)
  - `v0/pi-zero-2w-camera-plate-suv-logo.stl` — camera plate
    remixed with custom “SUV” branding (derivative of the upstream camera
    plate; redistributed under the same CC BY terms with attribution)

### Raspberry Pi Zero 2 WH Waveshare UPS Case

- **Designer:** [PiotrWolinski](https://www.printables.com/@PiotrWolinski_579340)
- **Source:** https://www.printables.com/model/1546215-raspberry-pi-zero-2-wh-waveshare-ups-case
- **License:** [Creative Commons Attribution-ShareAlike 4.0 (CC BY-SA)](https://creativecommons.org/licenses/by-sa/4.0/)
- **Files in this repo:**
  - `v0/pi-zero-2w-waveshare-ups-case-base.stl` — base case (unmodified).
    ShareAlike applies to this file and any adaptations of it.

## Original project files

- `v0/c-bracket-25mm-gap-2.8mm-holes.scad` / `.stl` — 25 mm C-shaped
  spacer with 2.8 mm holes
- `v0/c-bracket-20mm-gap-2.8mm-holes.stl` — 20 mm spacer with 2.8 mm holes
- `v0/c-bracket-20mm-gap-2.1mm-2.8mm-holes.scad` / `.stl` — 20 mm spacer
  with asymmetric 2.1 mm and 2.8 mm holes
- `v0/generate-c-bracket-25mm-gap.py` and
  `v0/generate-c-bracket-20mm-gap.py` — CadQuery STL generators
- `v0/assembled-camera.jpg` — photo of an assembled build

See [`v0/README.md`](v0/README.md) for the version-specific file manifest and
regeneration commands.
