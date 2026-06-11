from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Literal


Rotation = Literal[0, 90, 180, 270]
FocusMode = Literal["default", "auto", "continuous", "manual"]


@dataclass(frozen=True)
class CaptureSettings:
    output_dir: Path = Path("images")
    filename: str | None = None
    width: int | None = None
    height: int | None = None
    quality: int = 95
    sharpness: float = 0.5
    contrast: float = 0.9
    saturation: float = 0.9
    rotation: Rotation = 0
    warmup_seconds: float = 0.5
    focus_mode: FocusMode = "continuous"
    lens_position: float | None = None


def _timestamped_filename() -> str:
    return datetime.now().strftime("%Y%m%d-%H%M%S-%f.jpg")


def _normalized_quality(value: int) -> int:
    return max(1, min(100, int(value)))


def _output_path(settings: CaptureSettings) -> Path:
    if settings.filename:
        path = Path(settings.filename).expanduser()
    else:
        path = settings.output_dir.expanduser() / _timestamped_filename()
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def _rotate_image(image, rotation: Rotation):
    from PIL import Image

    if rotation == 90:
        return image.transpose(Image.Transpose.ROTATE_90)
    if rotation == 180:
        return image.transpose(Image.Transpose.ROTATE_180)
    if rotation == 270:
        return image.transpose(Image.Transpose.ROTATE_270)
    return image


def _camera_controls(settings: CaptureSettings) -> dict[str, object]:
    controls: dict[str, object] = {
        "Sharpness": settings.sharpness,
        "Contrast": settings.contrast,
        "Saturation": settings.saturation,
    }

    try:
        from libcamera import controls as libcamera_controls
    except ImportError:
        return controls

    if settings.focus_mode == "auto":
        controls["AfMode"] = libcamera_controls.AfModeEnum.Auto
    elif settings.focus_mode == "continuous":
        controls["AfMode"] = libcamera_controls.AfModeEnum.Continuous
    elif settings.focus_mode == "manual":
        controls["AfMode"] = libcamera_controls.AfModeEnum.Manual
        if settings.lens_position is not None:
            controls["LensPosition"] = settings.lens_position

    return controls


def capture_photo(settings: CaptureSettings = CaptureSettings()) -> Path:
    """Capture one still image from a Raspberry Pi Camera Module 3."""
    import time

    from PIL import Image
    from picamera2 import Picamera2

    picam2 = Picamera2()
    main_config: dict[str, object] = {"format": "RGB888"}
    if settings.width and settings.height:
        main_config["size"] = (settings.width, settings.height)

    config = picam2.create_still_configuration(
        main=main_config,
        controls=_camera_controls(settings),
    )
    output_path = _output_path(settings)
    started = False

    try:
        picam2.configure(config)
        picam2.start()
        started = True
        if settings.warmup_seconds > 0:
            time.sleep(settings.warmup_seconds)

        frame = picam2.capture_array("main")
    finally:
        if started:
            picam2.stop()
        picam2.close()

    image = Image.fromarray(frame, "RGB")
    image = _rotate_image(image, settings.rotation)
    image.save(output_path, format="JPEG", quality=_normalized_quality(settings.quality))
    return output_path
