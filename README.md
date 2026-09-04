# Tiny Film Camera

Tiny Film Camera is an open-source digital camera built around the Raspberry Pi
Zero 2 W and Camera Module 3. It can capture photos and record short video clips
using dedicated photo and video buttons, with three selectable looks (warm, cool,
and black & white) controlled by a physical slider switch. A buzzer provides
feedback for startup and photo capture, and a local photo gallery can be accessed
directly from your phone.

Read about the design and build process in
[Building my own camera](https://suveenellawela.com/thoughts/building-my-own-camera).

<p align="center">
  <img src="assets/guides/readme-showcase-two-column.png" alt="Tiny Film Camera assembled, the v1 CAD design, and a sample photo" width="920" />
</p>
<p align="center">
  <sub>
    <a href="assets/v1/product-images/camera-launch-warm.png">Assembled camera</a> ·
    <a href="assets/v1/v1-design.png">v1 CAD design</a> ·
    <a href="assets/photo-samples/train-sample-1935x1346.jpg">Sample photo</a> ·
    <a href="assets/photo-samples/train-original-4608x2592.jpg">Original photo (4608 × 2592)</a>
  </sub>
</p>

## What it does

- Use dedicated physical buttons for photos and short video clips.
- Choose Warm, Cool, or Black & white with a three-position hardware switch.
- Capture, browse, download, and delete photos from a phone on the same Wi-Fi.
- Monitor the Waveshare UPS battery from the web interface.
- Apply configurable exposure, white-balance, focus, rotation, and JPEG settings.
- Start the web app and hardware daemons automatically with systemd.

## Hardware

- Raspberry Pi Zero 2 W
- Raspberry Pi Camera Module 3
- Waveshare UPS HAT (C)
- Two momentary buttons (photo and video)
- Optional passive buzzer and SS23D32 three-position switch
- 3D-printed enclosure from [`assets/`](assets/README.md)

See the complete [bill of materials](docs/bom.md) and [setup guide](docs/setup.md).

### Components and wiring

<table>
  <tr>
    <td align="center" width="50%">
      <a href="assets/guides/components.png">
        <img src="assets/guides/components.png" alt="Components used to build Tiny Film Camera" width="100%" />
      </a>
      <br />
      <strong>Components</strong>
    </td>
    <td align="center" width="50%">
      <a href="assets/guides/wiring.png">
        <img src="assets/guides/wiring.png" alt="Tiny Film Camera wiring guide" width="100%" />
      </a>
      <br />
      <strong>Wiring</strong>
    </td>
  </tr>
</table>

## CAD designs

Browse all [Tiny Film Camera CAD components on Onshape](https://cad.onshape.com/documents?nodeId=a67770dd4e9bb35af20c342a&resourceType=folder).
Download the [printable enclosure files on Printables](https://www.printables.com/model/1827732-raspberry-pi-zero-2-w-camera-module-3-ups-hat-encl/files).

<table>
  <tr>
    <td align="center" width="50%">
      <a href="assets/v1/cad-demo-v1.mp4">
        <img src="assets/v1/cad-demo-v1.gif" alt="Animated view of the assembled Tiny Film Camera v1 enclosure" width="100%" />
      </a>
      <br />
      <strong>Assembled camera</strong>
    </td>
    <td align="center" width="50%">
      <a href="assets/v1/v1-cad.png">
        <img src="assets/v1/v1-cad.png" alt="Tiny Film Camera v1 CAD design" width="100%" />
      </a>
      <br />
      <strong>v1 CAD design</strong>
    </td>
  </tr>
</table>

## Quick start

On a Raspberry Pi running Raspberry Pi OS:

```bash
git clone https://github.com/SuveenE/tiny-film-camera.git
cd tiny-film-camera

sudo apt update
sudo apt install -y \
  python3-picamera2 python3-av python3-pil python3-gpiozero \
  python3-smbus i2c-tools

cp .env.example .env
./scripts/install_service.sh --enable-now
```

Open `http://<pi-ip>:8000` from a phone on the same Wi-Fi network. Captures are
saved under `data/captures/`.

<p align="center">
  <a href="assets/web-app.jpg">
    <img src="assets/web-app.jpg" alt="Tiny Film Camera web app showing capture controls, photo modes, battery level, and gallery" width="252" />
  </a>
</p>

> [!WARNING]
> The web interface has no authentication. Use it only on a trusted local
> network and do not expose port `8000` to the internet.

## Use it

Take a photo or record a ten-second video from the command line:

```bash
python3 src/tiny-film-cam/capture.py
python3 src/tiny-film-cam/record.py --duration 10
```

Customize the camera, GPIO pins, filters, battery calibration, and service
settings in [`.env.example`](.env.example), then copy the values you need into
your local `.env`.

## Build guides

- [Button, slider, and buzzer wiring](docs/wiring.md)
- [Camera and Raspberry Pi setup](docs/setup.md)
- [Physical shutter](docs/shutter-button.md)
- [Passive buzzer](docs/buzzer.md)
- [Photo-filter switch](docs/filter-switch.md)
- [Commands and service management](docs/commands.md)
- [Troubleshooting](docs/debug.md)
- [Enclosure and printable assets](assets/README.md)

## Limitations

- The Raspberry Pi takes approximately 30 seconds to 1 minute to fully start
  up, so there is a short wait before the camera is ready to use.
- Each photo takes approximately 3 to 6 seconds to process because images are
  captured at full resolution.

## License

Code and original CAD are available under the [MIT License](LICENSE).
Third-party enclosure models retain their upstream Creative Commons licenses;
see [`assets/README.md`](assets/README.md) for attribution.
