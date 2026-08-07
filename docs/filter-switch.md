# Set up the photo-filter switch

The SS23D32 switch selects **Black & white**, **Current**, or **Cold** for new
photos. Videos are unchanged.

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
| outer A | BCM GPIO 27, physical pin 13 |
| common | GND, physical pin 14 |
| outer B | BCM GPIO 22, physical pin 15 |

Leave the second row disconnected. **No resistor is required** because the code
enables the Pi's internal pull-ups. Do not connect the switch to 3.3 V or 5 V.

## 3. Test the switch

Boot the Pi, open the project directory, and install `gpiozero` if needed:

```bash
sudo apt install -y python3-gpiozero
sudo systemctl stop tiny-film-filter.service 2>/dev/null || true
python3 src/tiny-film-cam/filter_switch_test.py
```

Move the switch through all three positions. The expected readings are:

| GPIO 27 | GPIO 22 | Filter |
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
