# Commands

## Take a photo
```bash
rpicam-still -o photo1.jpg --quality 95 --sharpness 0.5 --contrast 0.9 --saturation 0.9
```

## Take a photo with the Python capture code
```bash
python3 src/tiny-film-cam/capture.py
```

## Take a full-size Camera Module 3 photo
```bash
python3 src/tiny-film-cam/capture.py --width 4608 --height 2592
```

## Transfer photos to local machine
```bash
scp -r suveen@172.20.10.2:/home/suveen/tiny-film/data/captures .
```
