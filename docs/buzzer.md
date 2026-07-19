# Feedback Buzzer

Add an optional passive buzzer so the physical shutter gives audible cues.
The shutter daemon (`src/tiny-film-cam/shutter_daemon.py`) drives these sounds:

| Sound | When |
|-------|------|
| **sparkle** | Shutter daemon initialized successfully; also a photo option |
| **minimal** | Frame captured (default; one low tick) |
| **gentle** | Frame-captured option with a descending two-note cue |
| **shutter** | Frame-captured option with two dry mechanical-style taps |
| **click** | A very short acknowledgement when video recording starts |
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
python3 src/tiny-film-cam/buzzer.py --sound gentle --volume 0.35
python3 src/tiny-film-cam/buzzer.py --sound shutter --volume 0.35
python3 src/tiny-film-cam/buzzer.py --sound sparkle --volume 0.35
python3 src/tiny-film-cam/buzzer.py --sound minimal --volume 0.35
```

The old `--sound beep` name remains as an alias for `gentle`.

If those four still appear to have the same pitch, run the diagnostic at full
volume:

```bash
python3 src/tiny-film-cam/buzzer.py --sound pitch-test --volume 1.0
```

It plays a long 1.5 kHz tone followed by a long 2.5 kHz tone. A passive buzzer
will produce two unmistakably different pitches. If both pitches sound the
same, the connected module is an **active buzzer** with its own fixed-frequency
oscillator; software can vary only its pulse rhythm, not its pitch.

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
With the defaults, a moderate-volume `sparkle` plays once when the shutter
daemon is ready. A moderate-volume `minimal` tick plays immediately after the
camera captures a frame, before rotation, JPEG encoding, and disk saving.
If an existing `.env` overrides older buzzer defaults, set:

```bash
TINY_FILM_BUZZER_PHOTO_SOUND=minimal
TINY_FILM_BUZZER_VOLUME=0.35
```

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
| Photo sound | `TINY_FILM_BUZZER_PHOTO_SOUND` | `--buzzer-photo-sound` | `minimal` |
| Volume (passive) | `TINY_FILM_BUZZER_VOLUME` | `--buzzer-volume` | `0.35` (moderate) |

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
- Burst volume gating retains at least three complete carrier cycles per pulse
  so low-volume playback does not mask the selected pitch.
- Volume is burst density rather than electrical amplitude: `1.0` drives the
  carrier continuously, while `0.35` drives it for roughly 35% of the playback
  time. Perceived loudness is not linear and varies by buzzer module.
