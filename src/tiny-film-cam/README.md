# tiny-film-cam

Raspberry Pi camera application and hardware integration code for Tiny Film.

This folder contains the photo and video capture paths, phone web UI, and the
shutter, battery, buzzer, and filter-switch integrations used by the systemd
services in `deploy/`. It does not include OpenAI image generation or queues.

Run one capture from the project root on the Raspberry Pi:

```bash
python3 src/tiny-film-cam/capture.py
```

Choose one of the three JPEG looks directly with:

```bash
python3 src/tiny-film-cam/capture.py --photo-filter black_and_white
python3 src/tiny-film-cam/capture.py --photo-filter normal
python3 src/tiny-film-cam/capture.py --photo-filter cool
```

If `--output` is omitted, the script writes a timestamped JPEG into
`data/captures/YYYY-MM-DD/`.

To save to a specific filename instead, pass `--output`:

```bash
python3 src/tiny-film-cam/capture.py --output photo1.jpg
```

For a Camera Module 3 full-size still, pass an explicit size:

```bash
python3 src/tiny-film-cam/capture.py --width 4608 --height 2592
```

The default image tuning is set for a film-friendly source capture:

```text
quality=95, sharpness=0.3, contrast=0.85, saturation=0.9,
ev=-0.7, awb_mode=daylight, rotation=180
```

For a more film-friendly source capture, protect highlights and reduce digital
edge bite:

```bash
python3 src/tiny-film-cam/capture.py \
  --width 4608 \
  --height 2592 \
  --sharpness 0.3 \
  --contrast 0.85 \
  --saturation 0.9 \
  --ev -0.7 \
  --awb-mode daylight \
  --rotation 180
```

To capture multiple exposure candidates from one warmed-up camera session:

```bash
python3 src/tiny-film-cam/capture.py \
  --output photo1.jpg \
  --exposure-brackets 0,-0.7,-1.0 \
  --awb-lock
```

Bracketed filenames include the EV value, such as
`photo1_ev+0p0.jpg`, `photo1_ev-0p7.jpg`, and `photo1_ev-1p0.jpg`.

Record a short video (H.264/MP4, 10s by default) into the same
`data/captures/YYYY-MM-DD/` tree:

```bash
python3 src/tiny-film-cam/record.py --duration 10
```

Video recording requires PyAV and ffmpeg on the Pi
(`sudo apt install python3-av ffmpeg`) and only supports rotation 0 or 180.
PyAV preserves camera timestamps when frames arrive late, then ffmpeg losslessly
places the MP4 index at the front so recordings retain their real-world duration
and play reliably in phone browsers.

Run the capture browser:

```bash
python3 src/tiny-film-cam/web.py
```

The web app serves captures from `data/captures/` and exposes:

- `GET /`
- `GET /gallery`
- `GET /api/images` (accepts an optional `limit` query parameter up to 50)
- `POST /api/capture`
- `POST /api/record`
- `DELETE /api/captures/<capture-path>`
- `GET /image/captures/<capture-path>`
- `GET /download/captures/<capture-path>`
- `GET /api/device-details`
- `GET /api/battery`
- `GET /api/filter`
- `GET /latest-image`
