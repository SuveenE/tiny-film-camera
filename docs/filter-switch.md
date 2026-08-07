# Photo filter switch

The SS23D32 three-position switch selects **Black & white**, the **current**
camera look, or **Cold**. Version 1 applies the selection to photos only.

## Wiring

Power off the Pi before wiring. Use one row of three switch terminals:

```text
outer A ── BCM GPIO 27 (physical pin 13)
common  ── GND         (physical pin 14)
outer B ── BCM GPIO 22 (physical pin 15)
```

Leave the second row of three terminals disconnected. The service enables the
Pi's internal pull-up resistors, so no external resistor and no 3.3 V/5 V wire
are needed.

| GPIO 27 | GPIO 22 | Default selection |
| --- | --- | --- |
| LOW | HIGH | Black & white |
| HIGH | HIGH | Current |
| HIGH | LOW | Cold |
| LOW | LOW | invalid wiring/state |

The handle can operate opposite the contacted terminal. Swap the left/right
configuration values if the physical order is reversed.

## Test before enabling the service

```bash
sudo systemctl stop tiny-film-filter.service
python3 src/tiny-film-cam/filter_switch_test.py
```

Move through all three positions and confirm the printed GPIO levels and
selection. Press `Ctrl+C` when finished. Start the service again with:

```bash
sudo systemctl start tiny-film-filter.service
```

The service writes the debounced state to `data/filter-state.json`. For a local
test without GPIO hardware:

```bash
TINY_FILM_FILTER_SIMULATE_POSITION=center ./scripts/run_filter_switch.sh
```

## Configuration

The defaults are in `.env.example`. `TINY_FILM_FILTER_LEFT` and
`TINY_FILM_FILTER_RIGHT` can be swapped without rewiring the switch.
