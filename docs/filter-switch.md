# Set up the photo-filter switch

The SS23D32 switch selects **Black & white**, **Current**, or **Cold** for new
photos. Videos are unchanged.

The filter service is the only process that reads the switch GPIO pins. It
debounces the contacts and writes the current selection to
`data/filter-state.json`; web and physical-button captures read that state
immediately before taking each photo. If the state is missing, invalid, or
stale, captures fall back to **Current** and the web badge reports the fallback.
Each saved photo also records the filter it used, so its gallery label does not
change when the switch moves later.

## 1. Identify the terminals

Power off and unplug the Pi. Choose either row of three switch terminals:

```text
outer A    common    outer B
unused     unused    unused
```

With a multimeter in continuity mode, confirm that `common` connects to one
outer terminal at each end position and neither outer terminal in the centre.

## 2. Wire one row

| Switch terminal | Raspberry Pi Zero 2 W |
| --- | --- |
| outer A | BCM GPIO 26, physical pin 37 |
| common | GND, physical pin 39 |
| outer B | BCM GPIO 20, physical pin 38 |

Leave the second row disconnected. **No resistor is required** because the code
enables the Pi's internal pull-ups. Do not connect the switch to 3.3 V or 5 V.
GPIO 26 and GPIO 20 avoid the photo button (GPIO 5), video button (GPIO 17),
buzzer (GPIO 18), and UPS I2C pins (GPIO 2 and GPIO 3).

## 3. Test the switch

Boot the Pi, open the project directory, and install `gpiozero` if needed:

```bash
sudo apt install -y python3-gpiozero
sudo systemctl stop tiny-film-filter.service 2>/dev/null || true
python3 src/tiny-film-cam/filter_switch_test.py
```

Move the switch through all three positions. The expected readings are:

| GPIO 26 | GPIO 20 | Filter |
| --- | --- | --- |
| LOW | HIGH | Black & white |
| HIGH | HIGH | Current |
| HIGH | LOW | Cold |

Press `Ctrl+C` when finished. `LOW / LOW` indicates incorrect wiring.

If Black & white and Cold are physically reversed, add this to `.env` rather
than resoldering:

```dotenv
TINY_FILM_FILTER_LEFT=cold
TINY_FILM_FILTER_RIGHT=black_and_white
```

## 4. Install and verify the service

```bash
./scripts/install_service.sh --enable-now
sudo systemctl status tiny-film-filter.service --no-pager
curl -s http://localhost:8000/api/filter | python3 -m json.tool
```

The API should report the current `position`, `selection`, and `active_filter`.
Move the switch and rerun the `curl` command to verify each position.

## 5. Test a photo

Open `http://<pi-ip>:8000`. Confirm that the **Photo filter** badge follows the
switch, then take one photo in each position. The gallery should show the filter
used for every photo.

For service logs:

```bash
sudo journalctl -u tiny-film-filter.service -f
```
