from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime
import fcntl
import os
from pathlib import Path
from typing import Iterator, Literal


Rotation = Literal[0, 90, 180, 270]
FocusMode = Literal["default", "auto", "continuous", "manual"]
ROTATIONS = {0, 90, 180, 270}
FOCUS_MODES = {"default", "auto", "continuous", "manual"}
PICAMERA_ARRAY_FORMAT = "RGB888"


class CameraCaptureError(RuntimeError):
    """Raised when a photo cannot be captured."""


class CameraUnavailableError(CameraCaptureError):
    """Raised when Raspberry Pi OS does not report an available camera."""


@dataclass(frozen=True)
class CaptureSettings:
    output_dir: Path = Path("data/captures")
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


def env_float(name: str, default: float) -> float:
    value = os.environ.get(name)
    if value is None or value.strip() == "":
        return default
    return float(value)


def env_int(name: str, default: int) -> int:
    value = os.environ.get(name)
    if value is None or value.strip() == "":
        return default
    return int(value)


def env_optional_int(name: str) -> int | None:
    value = os.environ.get(name)
    if value is None or value.strip() == "":
        return None
    return int(value)


def env_optional_float(name: str) -> float | None:
    value = os.environ.get(name)
    if value is None or value.strip() == "":
        return None
    return float(value)


def resolve_project_path(project_root: Path, value: str | Path) -> Path:
    path = Path(value).expanduser()
    if path.is_absolute():
        return path
    return project_root / path


def capture_output_dir_from_env(project_root: Path) -> Path:
    output_dir = os.environ.get("TINY_FILM_OUTPUT_DIR", "data/captures")
    return resolve_project_path(project_root, output_dir)


def capture_settings_from_env(project_root: Path) -> CaptureSettings:
    focus_mode = os.environ.get("TINY_FILM_CAPTURE_FOCUS_MODE", "continuous")
    if focus_mode not in FOCUS_MODES:
        focus_mode = "continuous"
    rotation = env_int("TINY_FILM_CAPTURE_ROTATION", 0)
    if rotation not in ROTATIONS:
        rotation = 0
    return CaptureSettings(
        output_dir=capture_output_dir_from_env(project_root),
        width=env_optional_int("TINY_FILM_CAPTURE_WIDTH"),
        height=env_optional_int("TINY_FILM_CAPTURE_HEIGHT"),
        quality=env_int("TINY_FILM_CAPTURE_QUALITY", 95),
        sharpness=env_float("TINY_FILM_CAPTURE_SHARPNESS", 0.5),
        contrast=env_float("TINY_FILM_CAPTURE_CONTRAST", 0.9),
        saturation=env_float("TINY_FILM_CAPTURE_SATURATION", 0.9),
        rotation=rotation,  # type: ignore[arg-type]
        warmup_seconds=env_float("TINY_FILM_CAPTURE_WARMUP_SECONDS", 0.5),
        focus_mode=focus_mode,  # type: ignore[arg-type]
        lens_position=env_optional_float("TINY_FILM_CAPTURE_LENS_POSITION"),
    )


@contextmanager
def _locked_camera(output_dir: Path) -> Iterator[None]:
    output_dir.mkdir(parents=True, exist_ok=True)
    lock_path = output_dir / ".tiny-film-camera.lock"
    with lock_path.open("w") as lock_file:
        fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)


def _timestamped_path(output_dir: Path) -> Path:
    captured_at = datetime.now()
    date_dir = captured_at.strftime("%Y-%m-%d")
    filename = f"{captured_at.strftime('%Y%m%d-%H%M%S-%f')}.jpg"
    return output_dir / date_dir / filename


def _normalized_quality(value: int) -> int:
    return max(1, min(100, int(value)))


def _output_path(settings: CaptureSettings) -> Path:
    if settings.filename:
        path = Path(settings.filename).expanduser()
    else:
        path = _timestamped_path(settings.output_dir.expanduser())
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def _rotate_image(image, rotation: Rotation):
    """Rotate saved pixels clockwise by the configured number of degrees."""
    from PIL import Image

    if rotation == 90:
        return image.transpose(Image.Transpose.ROTATE_270)
    if rotation == 180:
        return image.transpose(Image.Transpose.ROTATE_180)
    if rotation == 270:
        return image.transpose(Image.Transpose.ROTATE_90)
    return image


def _image_from_picamera_frame(frame):
    from PIL import Image

    # Picamera2's RGB888 stream is B, G, R byte order in NumPy arrays.
    rgb_frame = frame[:, :, [2, 1, 0]]
    return Image.fromarray(rgb_frame, "RGB")


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


def _available_camera_count(Picamera2) -> int | None:
    try:
        cameras = Picamera2.global_camera_info()
    except Exception:
        return None
    return len(cameras)


def _open_camera(Picamera2):
    camera_count = _available_camera_count(Picamera2)
    if camera_count == 0:
        raise CameraUnavailableError(
            "No Raspberry Pi camera was detected. Run "
            "`rpicam-hello --list-cameras` on the Pi and check the camera ribbon."
        )

    try:
        return Picamera2()
    except IndexError as exc:
        raise CameraUnavailableError(
            "No Raspberry Pi camera was detected. Run "
            "`rpicam-hello --list-cameras` on the Pi and check the camera ribbon."
        ) from exc


def capture_photo(settings: CaptureSettings = CaptureSettings()) -> Path:
    """Capture one still image from a Raspberry Pi Camera Module 3."""
    import time

    try:
        from PIL import Image
    except ImportError as exc:
        raise CameraCaptureError(
            "Missing Pillow. Install it on the Pi with `sudo apt install python3-pil`."
        ) from exc

    try:
        from picamera2 import Picamera2
    except ImportError as exc:
        raise CameraCaptureError(
            "Missing Picamera2. Install it on the Pi with "
            "`sudo apt install python3-picamera2`."
        ) from exc

    with _locked_camera(settings.output_dir.expanduser()):
        picam2 = _open_camera(Picamera2)
        main_config: dict[str, object] = {"format": PICAMERA_ARRAY_FORMAT}
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

        image = _image_from_picamera_frame(frame)
        image = _rotate_image(image, settings.rotation)
        image.save(output_path, format="JPEG", quality=_normalized_quality(settings.quality))
        return output_path
