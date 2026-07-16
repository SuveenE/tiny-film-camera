# Shutter Button

Wire a 4-pin momentary tactile switch to trigger capture from a physical
button. The shutter daemon (`src/tiny-film-cam/shutter_daemon.py`) listens for
button presses and captures using the same settings as the web UI.

**Tap** the button for a photo. **Hold** it (1s by default) to record a short
video clip instead.

## Wiring

A 4-pin tactile switch has two pairs of internally-connected pins. Only two
connections are needed:

```
Tactile switch pin 1 ──→ BCM GPIO 17 (physical pin 11)
Tactile switch pin 2 ──→ GND         (physical pin 9, or any GND)
```

The remaining two pins are left unconnected — they exist for mechanical
stability on the PCB.

The daemon enables the Pi's internal pull-up resistor by default, so the GPIO
reads HIGH at rest and goes LOW when the button is pressed.

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
| GPIO pin | `TINY_FILM_BUTTON_PIN` | `--pin` | 17 |
| Pull direction | `TINY_FILM_BUTTON_PULL_UP` | `--pull-up` / `--pull-down` | pull-up |
| Debounce time | `TINY_FILM_BUTTON_BOUNCE_SECONDS` | `--bounce-time` | 0.15 s |
| Hold-to-record | — | `--hold-time` | 1.0 s |
| Video length | — | `--video-duration` | 10 s |

All capture settings (quality, EV, rotation, AWB, etc.) are inherited from env
vars or can be passed as CLI flags — run with `--help` for the full list.

## Notes

- Pressing the button while a capture is already in progress is ignored (no
  double-fires).
- A hold long enough to start a video suppresses the photo that would otherwise
  fire on release, so one long press yields exactly one clip.
- Photos and videos land in the same output directory as the web UI captures, so
  they appear in the gallery immediately.
- If using pull-down wiring instead, connect the switch between GPIO and 3V3
  and pass `--pull-down`.
