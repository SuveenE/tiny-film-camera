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
