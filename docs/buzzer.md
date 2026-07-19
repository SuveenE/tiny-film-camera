# Feedback Buzzer

Add an optional passive buzzer so the physical shutter gives audible cues.
The shutter daemon (`src/tiny-film-cam/shutter_daemon.py`) drives these sounds:

| Sound | When |
|-------|------|
| **click** | Shutter button fires (photo or video) |
| **beep** | Photo saved |
| **chirp** | Video recording started |
| **double** | Video saved |
| **alert** | Capture or recording failed |

The buzzer is opt-in. With no pin configured, the shutter daemon stays silent.

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

## Test the five sounds

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

## Enabling it for the shutter

Set the pin in `.env` (see `.env.example`):

```bash
TINY_FILM_BUZZER_PIN=18
TINY_FILM_BUZZER_ACTIVE=0   # 0 = passive PWM (this module), 1 = active
```

Then restart the shutter service:

```bash
sudo systemctl restart tiny-film-shutter.service
```

Or run the daemon directly:

```bash
python3 src/tiny-film-cam/shutter_daemon.py --buzzer-pin 18 --buzzer-passive
```

## Configuration

| Setting | Env var | CLI flag | Default |
|---------|---------|----------|---------|
| Buzzer pin | `TINY_FILM_BUZZER_PIN` | `--buzzer-pin` | *(unset = disabled)* |
| Buzzer type | `TINY_FILM_BUZZER_ACTIVE` | `--buzzer-active` / `--buzzer-passive` | passive |

## Notes

- The buzzer is best-effort: if `gpiozero` is missing or the pin can't be
  claimed, the daemon logs a warning and keeps capturing silently.
- Only the physical shutter path beeps. Web UI captures already show on-screen
  confirmation and run in a separate process.
- Tones play on a background thread, so they never delay the next capture.
- Stay near **1.5–2.5 kHz** for this module; that is its claimed tone range.
