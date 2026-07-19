# Feedback Buzzer

Add an optional passive buzzer so the physical shutter gives audible cues.
The shutter daemon (`src/tiny-film-cam/shutter_daemon.py`) drives these sounds:

| Sound | When |
|-------|------|
| **click** | A very short acknowledgement when the button fires |
| **gentle** | Photo saved (default; a soft descending two-note cue) |
| **shutter** | Photo saved option with three dry mechanical-style taps |
| **sparkle** | Photo saved option with a quick ascending major chord |
| **minimal** | Photo saved option with one low tick |
| **chirp** | Video recording started |
| **double** | Video saved |
| **alert** | Capture or recording failed |

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

Or audition the four photo sounds individually:

```bash
python3 src/tiny-film-cam/buzzer.py --sound gentle --volume 0.16
python3 src/tiny-film-cam/buzzer.py --sound shutter --volume 0.16
python3 src/tiny-film-cam/buzzer.py --sound sparkle --volume 0.16
python3 src/tiny-film-cam/buzzer.py --sound minimal --volume 0.16
```

The old `--sound beep` name remains as an alias for `gentle`.

Default pin is BCM 18. Override with `--pin` if needed. Use `--active` only if
you wired a simple on/off active buzzer instead.

Passive modules with a drive transistor ignore PWM duty cycle (they stay full
loud while the pin is high). Loudness is controlled by bursting the tone
on/off — lower `--volume` means shorter bursts. Compare:

```bash
python3 src/tiny-film-cam/buzzer.py --sound gentle --volume 0.10
python3 src/tiny-film-cam/buzzer.py --sound gentle --volume 0.3
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
| Photo sound | `TINY_FILM_BUZZER_PHOTO_SOUND` | `--buzzer-photo-sound` | `gentle` |
| Volume (passive) | `TINY_FILM_BUZZER_VOLUME` | `--buzzer-volume` | `0.16` (burst density) |

## Notes

- The buzzer is best-effort: if `gpiozero` is missing or the pin can't be
  claimed, the daemon logs a warning and keeps capturing silently.
- Only the physical shutter path beeps. Web UI captures already show on-screen
  confirmation and run in a separate process.
- Tones play on a background thread, so they never delay the next capture.
- Stay near **1.5–2.5 kHz** for this module; that is its claimed tone range.
- A passive piezo can only make simple square-wave tones, not play sampled
  camera audio. The presets use short timing and musical intervals to make the
  most of that hardware.
