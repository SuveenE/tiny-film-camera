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
Photo button, one side ──→ BCM GPIO 17 (physical pin 11)
Photo button, other side ─→ GND        (physical pin 9, or any GND)

Video button, one side ──→ BCM GPIO 23 (physical pin 16)
Video button, other side ─→ GND        (physical pin 20, or any GND)
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
| Photo GPIO pin | `TINY_FILM_PHOTO_BUTTON_PIN` | `--photo-pin` | 17 |
| Video GPIO pin | `TINY_FILM_VIDEO_BUTTON_PIN` | `--video-pin` | 23 |
| Pull direction (both) | `TINY_FILM_BUTTON_PULL_UP` | `--pull-up` / `--pull-down` | pull-up |
| Debounce time | `TINY_FILM_BUTTON_BOUNCE_SECONDS` | `--bounce-time` | 0.15 s |
| Video length | — | `--video-duration` | 10 s |

`TINY_FILM_BUTTON_PIN` and `--pin` remain supported as legacy names for the
photo pin. The new photo-specific setting takes precedence.

All capture settings (quality, EV, rotation, AWB, etc.) are inherited from env
vars or can be passed as CLI flags — run with `--help` for the full list.

For optional audible feedback from a passive buzzer module, see
[buzzer.md](buzzer.md).

## Notes

- Pressing either button while a photo or video is already in progress is
  ignored (no double-fires or overlapping access to the camera).
- Holding a button does not change its action or repeatedly trigger it: the
  photo button takes one photo and the video button records one fixed-length
  clip per press.
- Photos and videos land in the same output directory as the web UI captures, so
  they appear in the gallery immediately.
- If using pull-down wiring instead, connect the switch between GPIO and 3V3
  and pass `--pull-down`.
