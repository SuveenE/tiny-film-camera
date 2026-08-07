# Tiny Film v0 hardware files

Files use lowercase, descriptive names so printable outputs and editable sources
are easy to identify. Dimensions are in millimetres.

## Case parts

| File | Purpose |
| --- | --- |
| `pi-zero-2w-waveshare-ups-case-base.stl` | Base for the Pi Zero 2 W and Waveshare UPS HAT |
| `pi-zero-2w-camera-case-top.stl` | Camera case top cover |
| `pi-zero-2w-camera-plate-suv-logo.stl` | Camera plate remixed with the SUV logo |

These models retain their upstream Creative Commons licences and attribution;
see the parent [`assets/README.md`](../README.md).

## Additional case part

| File | Purpose |
| --- | --- |
| `pi-camera-top-cover-v0.stl` | Updated v0 Raspberry Pi camera top cover |

## C-bracket spacers

| Printable STL | Editable source | Generator |
| --- | --- | --- |
| `c-bracket-25mm-gap-2.8mm-holes.stl` | `c-bracket-25mm-gap-2.8mm-holes.scad` | `generate-c-bracket-25mm-gap.py` |
| `c-bracket-20mm-gap-2.8mm-holes.stl` | — | — |
| `c-bracket-20mm-gap-2.1mm-2.8mm-holes.stl` | `c-bracket-20mm-gap-2.1mm-2.8mm-holes.scad` | `generate-c-bracket-20mm-gap.py` |

Run the CadQuery generators from the repository root:

```bash
python3 assets/v0/generate-c-bracket-25mm-gap.py
python3 assets/v0/generate-c-bracket-20mm-gap.py
```

The generators overwrite their corresponding STL output. The bracket sources
and generators are covered by the repository MIT licence.

## Reference photo

`assembled-camera.jpg` shows the completed v0 build.
