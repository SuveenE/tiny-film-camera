# Wiring

Power off and unplug the Raspberry Pi before changing any wiring.

## Two buttons

| Control | First side | Other side |
| --- | --- | --- |
| Photo button | BCM GPIO 5 (physical pin 29) | GND (physical pin 30) |
| Video button | BCM GPIO 17 (physical pin 11) | GND (physical pin 9) |

The buttons can share any GND pin. For a 4-pin tactile button, connect one leg
from each side of the button; the two legs on each side are already connected
internally.

## Three-position slider

Use one row of three terminals on the SS23D32 slider and leave the other row
unconnected.

| Slider terminal | Raspberry Pi |
| --- | --- |
| Outer A | BCM GPIO 26 (physical pin 37) |
| Centre/common | GND (physical pin 39) |
| Outer B | BCM GPIO 20 (physical pin 38) |

The slider positions select:

| Slider connection | Photo filter |
| --- | --- |
| GPIO 26 connected to GND | Black & white |
| Neither outer terminal connected to GND | Normal |
| GPIO 20 connected to GND | Cool |

## Passive buzzer

| Buzzer terminal | Raspberry Pi |
| --- | --- |
| VCC | 3.3 V (physical pin 1 or 17) |
| GND | GND (physical pin 6 or 14) |
| I/O | BCM GPIO 18 (physical pin 12) |

Use a passive three-pin buzzer module with terminals labelled VCC, GND, and I/O.
Power it from 3.3 V, not 5 V.

The Pi's internal pull-up resistors are enabled for all four button and slider
GPIO inputs, so no external resistors are needed. Do not connect the buttons or
slider to 3.3 V or 5 V.

For testing and configuration details, see
[Photo and Video Buttons](shutter-button.md) and
[Photo-filter switch](filter-switch.md), and [Passive buzzer](buzzer.md).
