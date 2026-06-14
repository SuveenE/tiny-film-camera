# tiny-film

My own digital film camera.

## Phone web app

Run the local capture browser from the project root:

```bash
python3 src/tiny-film-cam/web.py
```

Then open `http://<pi-ip>:8000` from a phone on the same Wi-Fi network.

## Boot services

Install the web app and physical shutter services on the Raspberry Pi:

```bash
./scripts/install_service.sh --enable-now
```

The web service starts the phone app on port `8000`. The shutter service listens
for a simple physical button on BCM GPIO 17 by default and saves each capture to
`data/captures/`. Wire the button between BCM GPIO 17, physical pin 11, and any
GND pin.

To change the button pin or capture settings, copy `.env.example` to `.env` and
edit the `TINY_FILM_*` values.
