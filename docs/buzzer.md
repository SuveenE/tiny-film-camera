# Feedback Buzzer

Add an optional buzzer so the camera chirps when the physical shutter button
captures a photo. The buzzer is driven by the shutter daemon
(`src/tiny-film-cam/shutter_daemon.py`):

- **Two short high beeps** — capture saved successfully.
- **One long low beep** — capture failed (check the logs).

The buzzer is opt-in. With no pin configured, the shutter daemon behaves exactly
as before and stays silent.

## Choosing a buzzer

- **Active buzzer** (most common, 3-pin or 2-pin "beeper" modules): has its own
  oscillator, so it only needs to be switched on and off. Use `--buzzer-active`
  (the default).
- **Passive buzzer** (bare piezo element): needs a PWM tone to make sound. Use
  `--buzzer-passive`.

If you are unsure, an active buzzer module is the simplest choice.

## Wiring

The default uses BCM GPIO 18 (physical pin 12), which is free — the shutter
button already uses GPIO 17.

```
Buzzer "+" / signal ──→ BCM GPIO 18 (physical pin 12)
Buzzer "-" / GND     ──→ GND         (physical pin 14, or any GND)
```

Most small 3–5 V active buzzer breakout boards can be driven directly from a
GPIO pin. For a bare passive piezo, put a ~100 Ω resistor in series with the
signal line to limit current.

## Enabling it

Set the pin in `.env` (see `.env.example`):

```bash
TINY_FILM_BUZZER_PIN=18
TINY_FILM_BUZZER_ACTIVE=1   # 0 for a passive buzzer
```

Then restart the shutter service:

```bash
sudo systemctl restart tiny-film-shutter.service
```

Or run the daemon directly with CLI flags:

```bash
python3 src/tiny-film-cam/shutter_daemon.py --buzzer-pin 18 --buzzer-active
```

## Configuration

| Setting | Env var | CLI flag | Default |
|---------|---------|----------|---------|
| Buzzer pin | `TINY_FILM_BUZZER_PIN` | `--buzzer-pin` | *(unset = disabled)* |
| Buzzer type | `TINY_FILM_BUZZER_ACTIVE` | `--buzzer-active` / `--buzzer-passive` | active |

## Notes

- The buzzer is best-effort: if `gpiozero` is missing or the pin can't be
  claimed, the daemon logs a warning and keeps capturing silently.
- Only the physical shutter button path beeps. Web UI captures run in a separate
  process and already show on-screen confirmation, so they don't share the pin.
- Tones play on a background thread, so they never delay the next capture.
