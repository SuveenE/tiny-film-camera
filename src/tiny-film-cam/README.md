# tiny-film-cam

Capture-only Raspberry Pi camera code for Tiny Film.

This folder intentionally contains only the local camera capture path. It does
not include OpenAI image generation, queues, phone UI, or service deployment.

Run one capture from the project root on the Raspberry Pi:

```bash
python3 src/tiny-film-cam/capture.py
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

The default image tuning matches the existing `rpicam-still` command:

```text
quality=95, sharpness=0.5, contrast=0.9, saturation=0.9
```

Run the capture browser:

```bash
python3 src/tiny-film-cam/web.py
```

The web app serves captures from `data/captures/` and exposes:

- `GET /`
- `GET /api/images`
- `POST /api/capture`
- `GET /image/captures/<capture-path>`
- `GET /download/captures/<capture-path>`
- `GET /api/device-details`
- `GET /api/battery`
- `GET /latest-image`
