# Photo and Video Buttons

Wire two 4-pin momentary tactile switches to give photo and video capture their
own physical buttons. The shutter daemon (`src/tiny-film-cam/shutter_daemon.py`)
listens for both and captures using the same settings as the web UI.

Press the **photo button** for a still image. Press the **video button** to
record one video clip (10 seconds by default).

## Wiring

A 4-pin tactile switch has two pairs of internally connected legs. For each
button, use one leg from each side of the switch—not two legs from the same
connected pair. Confirm the sides with a continuity tester if the switch body
does not make them clear.

```
Photo button, one side ──→ BCM GPIO 5 (physical pin 29)
Photo button, other side ─→ GND       (physical pin 30, or any GND)

Video button, one side ──→ BCM GPIO 17 (physical pin 11)
Video button, other side ─→ GND        (physical pin 9, or any GND)
```

The two buttons can share a GND connection. On each 4-pin switch, the unused
two legs can be left unconnected; they duplicate the connected legs for
mechanical stability.

The daemon enables the Pi's internal pull-up resistor on both GPIOs by default,
so each reads HIGH at rest and goes LOW when its button is pressed. No external
resistors are required. Power the Pi off before changing the wiring, and do not
connect either button to 5 V.

## Running

```bash
python3 src/tiny-film-cam/shutter_daemon.py
```

Or enable the systemd service for auto-start on boot:

```bash
./scripts/install_service.sh --enable-now
```

The service file is at `deploy/tiny-film-shutter.service`.

## Configuration

| Setting | Env var | CLI flag | Default |
|---------|---------|----------|---------|
| Photo GPIO pin | `TINY_FILM_PHOTO_BUTTON_PIN` | `--photo-pin` | 5 |
| Video GPIO pin | `TINY_FILM_VIDEO_BUTTON_PIN` | `--video-pin` | 17 |
| Pull direction (both) | `TINY_FILM_BUTTON_PULL_UP` | `--pull-up` / `--pull-down` | pull-up |
| Debounce time | `TINY_FILM_BUTTON_BOUNCE_SECONDS` | `--bounce-time` | 0.15 s |
| Video length | — | `--video-duration` | 10 s |

`TINY_FILM_BUTTON_PIN` and `--pin` remain supported as legacy names for the
photo pin. The new photo-specific setting takes precedence.

When upgrading an existing installation that still has
`TINY_FILM_BUTTON_PIN=17`, replace it with the explicit current mapping:

```dotenv
TINY_FILM_PHOTO_BUTTON_PIN=5
TINY_FILM_VIDEO_BUTTON_PIN=17
```

All capture settings (quality, EV, rotation, AWB, etc.) are inherited from env
vars or can be passed as CLI flags — run with `--help` for the full list.

For optional audible feedback from a passive buzzer module, see
[buzzer.md](buzzer.md).

## Notes

- Button presses are queued and handled in order. A press received while a
  photo or video is in progress runs as soon as the camera is free, without
  overlapping camera access.
- Holding a button does not change its action or repeatedly trigger it: the
  photo button takes one photo and the video button records one fixed-length
  clip per press.
- Photos and videos land in the same output directory as the web UI captures, so
  they appear in the gallery immediately.
- If using pull-down wiring instead, connect the switch between GPIO and 3V3
  and pass `--pull-down`.

## Readiness and repeated-photo test

The startup ready cue now plays only after system startup has settled and
Picamera2 detects a camera. Wait for that cue before taking the first photo. The
same moment appears in the service log as `Tiny Film is ready for photos`.

First test repeated camera capture without involving the physical switch. Stop
the two camera-using services, load the deployed settings, and run five
simulated presses exactly five seconds apart:

```bash
sudo systemctl stop tiny-film-shutter.service tiny-film-web.service
set -a
source .env
set +a
python3 src/tiny-film-cam/shutter_diagnostic.py --count 5 --interval 5
sudo systemctl start tiny-film-web.service tiny-film-shutter.service
```

A successful run ends with `Diagnostic PASSED: 5/5 requests completed`. It also
prints the time from each request to its sensor frame and saved JPEG. A failed
run exits non-zero and prints the exception for the failed request.

Then test the physical button while following the service log:

```bash
sudo journalctl -u tiny-film-shutter.service -f -o cat
```

After the ready cue, press the photo button five times with at least five
seconds between presses. Each press must produce one uninterrupted sequence of
messages with the same request number:

```text
Photo request #1 queued
Photo request #1 started ... after button press
Saved 1 photo(s): ...
Photo request #1 finished in ...
```

If a press has no `queued` message, investigate the button wiring or GPIO
input. If it queues and then logs `Capture failed`, investigate the camera or
capture pipeline. A large `started ... after button press` value means an
earlier photo or video was still using the camera; the request remains queued
instead of being discarded.
