# Wes-inspired camera filter

`wes_anderson` is a deterministic cream-and-cyan grade inspired by the warm
pastels in Asteroid City. `wes_rose` is a softer pink/blue alternative. These
are original RGB transforms, not official movie LUTs. No AI, synthesis,
random grain, blur, object replacement, or queue is involved.

The grade lifts midtones, gently compresses the tonal endpoints, moves blue
fabric toward cyan and greens toward olive, and separates cream highlights
from warm golden accents. A cached 33 × 33 × 33 Pillow LUT processes the pixels.
The source should be a correctly exposed sRGB photograph, not sensor RAW.

## Capture on the Pi

Run from `/home/suveen/tiny-film`:

```bash
python3 src/tiny-film-cam/capture.py \
  --photo-filter wes_anderson \
  --contrast 1 --saturation 1 --sharpness 0.3 \
  --ev 0 --warmup-seconds 4 --rotation 0 \
  --keep-original
```

This writes a timestamped JPEG and filter-version sidecar under `data/captures`.
`--keep-original` also saves the same rotated, ungraded frame as
`<name>.original.png`, with a Normal sidecar. This is lossless ISP output,
not Bayer RAW. Omit the option for faster saving and less storage use.

The command uses the sensor's full 4608 × 2592 resolution. Add
`--width 2304 --height 1296` for quicker experiments. Rotation 0 is correct for
the camera's position during this experiment; the project's normal rotation
remains 180. Exposure 0 worked for this room; it is not a universal exposure.
Start there and lower exposure if important highlights clip.

The explicit neutral contrast/saturation settings avoid stacking the existing
camera's softened look underneath this filter. Warmup lets focus, exposure,
and auto white balance settle; white balance is then locked for that capture.
This does not lock gains across separate invocations or changing lighting.

## Grade an existing photograph

Run from the project root on either the Pi or a computer with Pillow:

```bash
python3 src/tiny-film-cam/grade.py original.png wes.jpg
python3 src/tiny-film-cam/grade.py original.png softer.png --strength 0.7
python3 src/tiny-film-cam/grade.py original.png rose.jpg --photo-filter wes_rose
```

Always choose a new output filename. The tool refuses to overwrite the input,
existing output, or its metadata. It honors EXIF orientation, converts tagged
ICC inputs to sRGB, and saves a JSON sidecar with source, strength, and filter
version. JPEG quality is 95 with 4:4:4 sampling; PNG preserves exact graded
pixels. Input EXIF is not copied into the output. An untagged input is assumed
to be sRGB. Profile conversion requires Pillow's ImageCms support.

Camera capture and this tool use `apply_photo_filter` from `photo_filters.py`.
Given identical RGB inputs, filter name, and strength 1, their graded pixels
are identical. JPEG files can differ if encoder settings differ.

## Physical switch

The CLI filter is installed on the Pi. Existing hardware switch mappings were
left in place. To assign this look to the right position later, set
`TINY_FILM_FILTER_RIGHT=wes_anderson` in the Pi's `.env` and restart the filter,
shutter, and web services. Set capture contrast/saturation to 1, EV to 0, and
warmup to 4 in `.env` to reproduce the baseline above. The gallery understands
the new metadata labels; its three fixed mode badges still list the original
switch defaults. The CLI is the tested selection path for this experiment.

## Experiment: 5 September 2026

Real IMX708 Camera Module 3 images are in `data/captures/wes-lab-20260905/`
on the Pi and local workspace; they are intentionally ignored by Git.

- Baseline: existing camera defaults, 2304 × 1296; upside down for this placement.
- Exposure sweep: neutral ISP settings, rotation 0, 4-second warmup, EV 0,
  +0.7, +1.0; fixed color gains and lens position across the sweep.
  EV +0.7 put about 7% of channel samples at 254 or above. EV 0 retained
  highlight detail, so the LUT supplies the brightness lift instead.
- First iteration: subtle desert and rose grades. The user chose cream/cyan,
  then correctly noted the subtle result did not look strongly Wes-inspired.
- Second iteration: stronger cream/cyan separation and midtone lift; the main
  `wes_anderson` v1 filter uses this direction.
- Full resolution: `full-wes.jpg` plus its `.original.png`; later grading and
  saving with the same JPEG settings produced a byte-identical JPEG.
- Three repeated full-resolution LUT runs produced identical pixel SHA-256
  hashes. After removing an unnecessary RGB copy, measured processing was
  6.06 seconds first run, then 2.86 and 2.45 seconds. JPEG encoding took 0.93
  seconds. Times vary with Pi load, swap, and LUT cache state; these exclude
  loading, capture warmup, and optional PNG saving.
- Full-resolution mean luma rose from 119.4 to 150.6 (0–255). The graded JPEG
  contained no pixels with any channel at 255 in this scene. This is not a
  guarantee against clipping for every input, particularly saturated colors.

One repeated capture exposed a camera shutdown stall after the files had been
saved. The capture path was changed to stop streaming immediately after the
array is captured, before PNG saving and grading. A reboot released the stuck thread. After the change, three consecutive
full-resolution captures completed: 40.63 seconds with a lossless original,
then 12.02 and 11.97 seconds for JPEG-only output, all including 4-second
warmup. This is a small repeat test, not a long-run soak test.

Useful artifacts: `final-comparison.jpg`, `iteration-two.jpg`,
`benchmark.json`, `image-metrics.json`, and exposure metadata JSON files.

## What remains to tune

This is a working color look, not a claim that an arbitrary room becomes a
Wes Anderson film still. The available scene is mostly neutral and the camera
is off-center. For a better visual test, place the camera level and directly
opposite the bed, center the headboard, remove the foreground obstruction,
and include a mustard/cream object with one cyan or red accent. Use broad,
soft light. Then compare Normal and Wes from the same frame again.

Only this indoor scene has been visually tuned. Before treating it as a
universal preset, check daylight, skin tones, foliage, saturated reds, and
low light. Evaluate white balance and exposure separately from the look;
a static LUT cannot repair mixed lighting or recover clipped sensor detail.

Reference: [Wes Anderson Color Palette Explained](https://spotlightfx.com/blog/wes-anderson-color-palette).
