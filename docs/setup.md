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
7. Install Python helpers:
   ```bash
   sudo apt install -y python3-picamera2 python3-pil python3-gpiozero
   ```
8. Wire the shutter button between BCM GPIO 17, physical pin 11, and any GND
   pin. With the default `.env.example` settings, the Pi uses its internal
   pull-up resistor.
9. Install the Tiny Film boot services:
   ```bash
   ./scripts/install_service.sh --enable-now
   ```
