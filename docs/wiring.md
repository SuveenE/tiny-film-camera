# Wiring

Power off and unplug the Raspberry Pi before changing any wiring.

## Two buttons

| Control | First side | Other side |
| --- | --- | --- |
| Photo button | BCM GPIO 17 (physical pin 11) | GND (physical pin 9) |
| Video button | BCM GPIO 23 (physical pin 16) | GND (physical pin 20) |

The buttons can share any GND pin. For a 4-pin tactile button, connect one leg
from each side of the button; the two legs on each side are already connected
internally.

## Three-position slider

Use one row of three terminals on the SS23D32 slider and leave the other row
unconnected.

| Slider terminal | Raspberry Pi |
| --- | --- |
| Outer A | BCM GPIO 27 (physical pin 13) |
| Centre/common | GND (physical pin 14) |
| Outer B | BCM GPIO 22 (physical pin 15) |

The slider positions select:

| Slider connection | Photo filter |
| --- | --- |
| GPIO 27 connected to GND | Black & white |
| Neither outer terminal connected to GND | Current |
| GPIO 22 connected to GND | Cold |

The Pi's internal pull-up resistors are enabled for all four GPIO inputs, so no
external resistors are needed. Do not connect the buttons or slider to 3.3 V or
5 V.

For testing and configuration details, see
[Photo and Video Buttons](shutter-button.md) and
[Photo-filter switch](filter-switch.md).
