# Setup

1. Flash Raspberry Pi OS onto SD card with Raspberry Pi Imager
2. Insert SD card and boot — wait until you can SSH in
3. Update packages:
   ```bash
   sudo apt update && sudo apt full-upgrade -y
   ```
4. Reboot:
   ```bash
   sudo reboot
   ```
5. Test the camera:
   ```bash
   rpicam-hello -t 5000
   ```
6. Take a picture:
   ```bash
   rpicam-still -o test.jpg
   ```
   Or record a short test clip:
   ```bash
   rpicam-vid -t 5000 -o test.mp4
   ```
7. Install Python helpers (`ffmpeg` is required for MP4 video recording):
   ```bash
   sudo apt install -y python3-picamera2 python3-pil python3-gpiozero python3-smbus i2c-tools ffmpeg
   ```
8. Enable I2C for the Waveshare UPS HAT (C):
   ```bash
   sudo raspi-config
   ```
   Choose `Interface Options` -> `I2C` -> `Yes`, then reboot.
9. Confirm the UPS HAT is visible at address `0x43`:
   ```bash
   i2cdetect -y 1
   ```
10. Wire the shutter button between BCM GPIO 17, physical pin 11, and any GND
   pin. With the default `.env.example` settings, the Pi uses its internal
   pull-up resistor.
11. Optionally wire the passive buzzer: VCC to 3V3, GND to GND, and I/O to
    BCM GPIO 18 (physical pin 12). The shutter daemon enables that pin by
    default — test with `python3 src/tiny-film-cam/buzzer.py`. See
    [buzzer.md](buzzer.md).
12. Install the Tiny Film boot services:
   ```bash
   ./scripts/install_service.sh --enable-now
   ```
