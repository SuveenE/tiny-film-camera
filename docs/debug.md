# Debug

## LED Behavior

- **Solid green** — powered and idle
- **Blinking/flickering** — reading/writing to SD card (common during boot)
- **Off** — no power, or issue with SD card/power supply

## Capture Failed: No Camera

If the phone app says `Capture failed` and mentions no Raspberry Pi camera, run:

```bash
rpicam-hello --list-cameras
```

Expected: at least one camera is listed.

If no camera appears, power down safely, reseat the camera ribbon, check the
ribbon orientation, boot again, and rerun the check before testing the web app.
