# Feedback Buzzer

Add an optional passive buzzer so the physical shutter gives audible cues.
The shutter daemon (`src/tiny-film-cam/shutter_daemon.py`) drives these sounds:

| Sound | When |
|-------|------|
| **shutter** | Photo capture (open/close click-clack) |
| **chirp** | Video recording started |
| **double** | Video saved |
| **alert** | Capture or recording failed |
| **click** / **beep** | Extra cues in the hardware demo |

By default the shutter daemon uses a **passive** buzzer on **BCM GPIO 18**.
Leave `TINY_FILM_BUZZER_PIN` blank in `.env`, or pass `--no-buzzer`, to disable.

## Hardware

This project uses a **passive** buzzer module (PWM-driven, not an active beeper
with a built-in oscillator). The BOM lists the module with pins **VCC**, **I/O**,
and **GND**.

## Wiring

Avoid BCM GPIO 17 (shutter button) and BCM GPIO 2/3 (UPS HAT I2C). Use
**BCM GPIO 18** (physical pin 12):

```
Buzzer VCC ──→ 3V3          (physical pin 1 or 17)
Buzzer GND ──→ GND          (physical pin 6 or 14)
Buzzer I/O ──→ BCM GPIO 18  (physical pin 12)
```

Power the module from **3.3V**, not 5V — the Pi GPIO is 3.3V and matches the
module's 3.3–5.5V supply range.

## Test the sounds

With the module wired, run the demo from the project root on the Pi:

```bash
python3 src/tiny-film-cam/buzzer.py
```

Or play one sound:

```bash
python3 src/tiny-film-cam/buzzer.py --sound beep
```

Default pin is BCM 18. Override with `--pin` if needed. Use `--active` only if
you wired a simple on/off active buzzer instead.

Passive cues use a low PWM duty cycle so they stay soft. Try a quieter demo:

```bash
python3 src/tiny-film-cam/buzzer.py --sound shutter --volume 0.12
```

## Using it with the shutter

No `.env` entries are required for the default wiring (GPIO 18, passive).
Restart the shutter service after deploying code that includes the buzzer:

```bash
sudo systemctl restart tiny-film-shutter.service
```

Or run the daemon directly:

```bash
python3 src/tiny-film-cam/shutter_daemon.py
```

To disable sound, leave the pin blank in `.env` or pass `--no-buzzer`:

```bash
TINY_FILM_BUZZER_PIN=
```

```bash
python3 src/tiny-film-cam/shutter_daemon.py --no-buzzer
```

## Configuration

| Setting | Env var | CLI flag | Default |
|---------|---------|----------|---------|
| Buzzer pin | `TINY_FILM_BUZZER_PIN` | `--buzzer-pin` / `--no-buzzer` | `18` (blank = disabled) |
| Buzzer type | `TINY_FILM_BUZZER_ACTIVE` | `--buzzer-active` / `--buzzer-passive` | passive |
| Volume (passive) | `TINY_FILM_BUZZER_VOLUME` | `--buzzer-volume` | `0.16` |

## Notes

- The buzzer is best-effort: if `gpiozero` is missing or the pin can't be
  claimed, the daemon logs a warning and keeps capturing silently.
- Only the physical shutter path beeps. Web UI captures already show on-screen
  confirmation and run in a separate process.
- Tones play on a background thread, so they never delay the next capture.
- Stay near **1.5–2.5 kHz** for this module; that is its claimed tone range.
