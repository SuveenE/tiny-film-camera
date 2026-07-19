# Commands

## Take a photo
```bash
rpicam-still -o photo1.jpg --quality 95 --sharpness 0.5 --contrast 0.9 --saturation 0.9
```

## Take a film-friendlier highlight-protected photo
```bash
python3 src/tiny-film-cam/capture.py \
  --output photo1.jpg \
  --quality 95 \
  --sharpness 0.3 \
  --contrast 0.85 \
  --saturation 0.9 \
  --ev -0.7 \
  --awb-mode daylight \
  --rotation 180
```

## Take an exposure bracket
```bash
python3 src/tiny-film-cam/capture.py \
  --output photo1.jpg \
  --exposure-brackets 0,-0.7,-1.0 \
  --awb-lock
```

## Take a photo with the Python capture code
```bash
python3 src/tiny-film-cam/capture.py
```

## Take a full-size Camera Module 3 photo
```bash
python3 src/tiny-film-cam/capture.py --width 4608 --height 2592
```

## Record a short video (10s default)
```bash
python3 src/tiny-film-cam/record.py
```

## Record a custom-length video
```bash
python3 src/tiny-film-cam/record.py --duration 5 --width 1920 --height 1080 --fps 30
```

## Transfer photos to local machine
```bash
scp -r <pi-user>@<pi-ip>:/home/<pi-user>/tiny-film/data/captures .
```

Example (Pi over phone hotspot):
```bash
scp -r suveen@172.20.10.2:/home/suveen/tiny-film/data/captures .
```

## Test the feedback buzzer
```bash
python3 src/tiny-film-cam/buzzer.py
```

## Play one buzzer sound
```bash
python3 src/tiny-film-cam/buzzer.py --sound gentle --volume 0.16
```

## Install boot services
```bash
./scripts/install_service.sh --enable-now
```

## Restart services
```bash
./scripts/restart_services.sh
```

## Service status
```bash
sudo systemctl status tiny-film-web.service tiny-film-shutter.service tiny-film-battery.service --no-pager
```

## Take a photo through the web server
```bash
curl -X POST http://localhost:8000/api/capture
```

## Record a video through the web server
```bash
curl -X POST http://localhost:8000/api/record
```

## Read battery details through the web server
```bash
curl http://localhost:8000/api/battery
```

## Follow service logs
```bash
sudo journalctl -u tiny-film-web.service -u tiny-film-shutter.service -u tiny-film-battery.service -f
```
