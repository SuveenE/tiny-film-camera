# SS23D32 three-position photo-filter switch plan

## Goal

Use a physical three-position selector for the default photo looks:

- left: **Black & white**
- centre: **Current**
- right: **Cold**

The selected look is baked into new JPEGs from both the physical shutter and
the web capture button. The web page shows the live selection and the look used
for each saved photo. Position names and filter recipes should remain easy to
change later.

## Confirmed switch and pin check

The supplied SS23D32 specification confirms that the part is sold as a
six-terminal, two-pole switch with three stable actuator positions. That is
consistent with the expected **DPDT ON-OFF-ON** arrangement: “2 pole 2 throw”
describes the electrical contacts, while the centre-off detent is the third
physical position. The listing does not explicitly name the centre-off contact
pattern, so verify it once rather than relying on the seller's terminology.

Before mounting or soldering it, make one quick multimeter continuity check:

1. It must click into left, centre, and right positions.
2. On one row of three terminals, the centre terminal is the common contact.
3. Common connects to one outer terminal at one end, neither in the centre,
   and the other outer terminal at the other end.

This verifies the terminal orientation and catches a mislabelled part. The
second pole/row is not needed for this project.

## Proposed wiring

Power the Pi off while wiring. Use one pole of the switch and the Pi's internal
pull-up resistors; the switch needs no 3.3 V or 5 V connection.

| Switch contact | Raspberry Pi Zero 2 W |
| --- | --- |
| outer A | BCM GPIO 26, physical pin 37 |
| common/centre | GND, physical pin 39 |
| outer B | BCM GPIO 20, physical pin 38 |
| second row, if present | leave disconnected |

These pins avoid the photo button (BCM 5), video button (BCM 17), buzzer
(BCM 18), and UPS I2C (BCM 2/3) connections.

| GPIO 26 | GPIO 20 | Selection |
| --- | --- | --- |
| LOW | HIGH | Black & white |
| HIGH | HIGH | Current |
| HIGH | LOW | Cold |
| LOW | LOW | invalid wiring/state |

The actuator direction can be opposite to the contacted outer terminal. Verify
the three readings on the Pi before assigning the final left/right labels; keep
the mapping configurable so the wires do not need to be swapped.

## Software design

Only one process should own the two GPIO inputs. A new filter-switch service
will debounce the contacts and atomically write `data/filter-state.json`, like
the existing battery service. The web and shutter processes will read that
cache immediately before each photo.

| Area | Planned change |
| --- | --- |
| `filter_switch.py` | Define positions, GPIO truth-table mapping, cache format, stale/error handling, and configurable position-to-filter mapping. |
| `filter_daemon.py` | Own GPIO 26/20, debounce transitions, and write the initial and changed states to the cache. |
| `photo_filters.py` | Hold the stable IDs (`black_and_white`, `current`, `cold`), display names, versions, and lightweight Pillow filter recipes. |
| `camera.py` | Add the chosen filter to `CaptureSettings` and apply it after rotation but before JPEG encoding. Keep the current raw camera controls common to all three looks. |
| `shutter_daemon.py` | Resolve the cached selector state at button-press time, not only at service startup. |
| `web.py` | Resolve the state for web captures, add `GET /api/filter`, and show a read-only `Photo filter` badge that refreshes after switch movement. |
| capture metadata | Store filter ID/version beside each JPEG so the gallery keeps showing the look used even after the switch moves or recipes change. Delete the metadata with its capture. |
| service/config | Add a systemd unit and runner; extend the installer and `.env.example` with pins, position mapping, cache path, debounce, and fallback settings. |
| tests/docs | Test truth-table mapping, cache failures, image transforms, API payloads, metadata cleanup, and both capture paths; document final wiring and setup. |

Use a short debounce window and retain the last valid selection during a switch
transition. If the service/cache is unavailable, use a clearly reported,
configurable fallback (initially Current) rather than guessing from stale GPIO
data.

## Delivery sequence

1. Add the switch reader, cache, tests, service, and a simulated-state option so
   the web display can be developed without Pi hardware.
2. Add `GET /api/filter` and the live web badge; verify all three physical
   positions before enabling image processing.
3. Add versioned Warm, Black & white, and Cold JPEG processing plus per-capture
   metadata for web and physical-shutter photos.
4. Test all three positions through both capture paths on the Pi, benchmark a
   full-resolution photo for memory/latency, and tune the looks from sample
   images.

Version 1 should apply filters to **photos only**. Video should remain unchanged
and the UI should say `Photo filter`; real-time warm/cold video needs calibrated
Picamera2 colour gains, while monochrome can use zero saturation.

## Acceptance checks

- The web badge follows the physical selector within about one second.
- Each position produces a visibly distinct JPEG from both shutter paths.
- Every photo reports the filter ID/version used; moving the switch does not
  change older gallery labels.
- Invalid/stale states are visible in the API/UI and use the documented fallback.
- Full-resolution capture does not exhaust the Pi Zero 2 W's memory.
- Existing camera, shutter, buzzer, battery, web, and service tests still pass.

## Implementation status

The software path, local simulation, automated tests, service/config updates,
and web UI are implemented in two stacked pull requests. Physical continuity
testing, final pin identification, soldering, full-resolution Pi benchmarking,
and aesthetic tuning from real camera samples still need to be done on the
device.
