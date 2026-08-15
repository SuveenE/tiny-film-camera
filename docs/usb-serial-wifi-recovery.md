# Recover Wi-Fi over USB Serial

Use this procedure when a Raspberry Pi Zero 2 W will not join Wi-Fi and no
mini-HDMI display is available. It provides a temporary login console through
the Pi's micro-USB data port; the SD card does not need to be reflashed.

## Root cause found

The hotspot credentials stored on the boot partition were correct, the Wi-Fi
radio was enabled, and the Pi could see the 2.4 GHz hotspot. However,
`nmcli connection show` contained no saved Wi-Fi profile, so NetworkManager had
nothing to connect to automatically.

## Enable the temporary serial console

Shut down the Pi, put its SD card in another computer, and back up `config.txt`
and `cmdline.txt` from the `bootfs` partition.

Add this under `[all]` in `config.txt`:

```ini
dtoverlay=dwc2,dr_mode=peripheral
```

Add these space-separated parameters to the existing single line in
`cmdline.txt`:

```text
modules-load=dwc2,g_serial console=ttyGS0,115200 systemd.wants=serial-getty@ttyGS0.service
```

Keep all existing `cmdline.txt` content on that same line. Safely eject the SD
card and return it to the Pi.

Connect a known data-capable micro-USB cable between the computer and the Pi's
port labelled **USB**, not **PWR IN**. This cable supplies both data and power;
do not attach a second power source at the same time.

On macOS, locate and open the serial device:

```bash
ls /dev/cu.usbmodem*
screen /dev/cu.usbmodem11301 115200
```

Replace `usbmodem11301` with the name reported on the host. On Linux, the
device is usually `/dev/ttyACM0`. Press Enter if the login prompt is not
immediately visible, then log in with the Pi user account.

## Diagnose and connect

Check the radio, interface, saved profiles, and visible networks:

```bash
nmcli radio
nmcli device status
rfkill list
nmcli connection show
sudo nmcli device wifi rescan ifname wlan0
nmcli -f IN-USE,SSID,CHAN,FREQ,SIGNAL,SECURITY device wifi list ifname wlan0
```

If the hotspot is visible but has no saved profile, create one without putting
the password in shell history:

```bash
sudo nmcli --ask device wifi connect "<SSID>" ifname wlan0
```

Enter the hotspot password when prompted. Confirm the connection, IP address,
route, and automatic reconnection:

```bash
nmcli device status
ip -4 -br address show wlan0
ip route
nmcli -g connection.autoconnect connection show "<SSID>"
ping -c 3 1.1.1.1
```

## Remove the temporary console

After Wi-Fi and SSH work, remove the added `dtoverlay` line from `config.txt`
and the three added parameters from `cmdline.txt`:

```text
modules-load=dwc2,g_serial
console=ttyGS0,115200
systemd.wants=serial-getty@ttyGS0.service
```

Reboot the Pi. Removing the temporary console avoids leaving a physical USB
login interface enabled.
