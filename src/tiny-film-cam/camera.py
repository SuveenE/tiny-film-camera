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
AwbMode = Literal[
    "default",
    "auto",
    "incandescent",
    "tungsten",
    "fluorescent",
    "indoor",
    "daylight",
    "cloudy",
    "custom",
]
ROTATIONS = {0, 90, 180, 270}
FOCUS_MODES = {"default", "auto", "continuous", "manual"}
AWB_MODES = {
    "default",
    "auto",
    "incandescent",
    "tungsten",
    "fluorescent",
    "indoor",
    "daylight",
    "cloudy",
    "custom",
}
AWB_MODE_ENUM_NAMES = {
    "auto": "Auto",
    "incandescent": "Incandescent",
    "tungsten": "Tungsten",
    "fluorescent": "Fluorescent",
    "indoor": "Indoor",
    "daylight": "Daylight",
    "cloudy": "Cloudy",
    "custom": "Custom",
}
PICAMERA_ARRAY_FORMAT = "RGB888"
DEFAULT_QUALITY = 95
DEFAULT_SHARPNESS = 0.3
DEFAULT_CONTRAST = 0.85
DEFAULT_SATURATION = 0.9
DEFAULT_EXPOSURE_VALUE = -0.7
DEFAULT_BRACKET_SETTLE_SECONDS = 0.25
DEFAULT_ROTATION: Rotation = 270
DEFAULT_WARMUP_SECONDS = 0.5
DEFAULT_FOCUS_MODE: FocusMode = "continuous"
DEFAULT_AWB_MODE: AwbMode = "daylight"
DEFAULT_AWB_LOCK = False


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
    quality: int = DEFAULT_QUALITY
    sharpness: float = DEFAULT_SHARPNESS
    contrast: float = DEFAULT_CONTRAST
    saturation: float = DEFAULT_SATURATION
    exposure_value: float = DEFAULT_EXPOSURE_VALUE
    exposure_brackets: tuple[float, ...] = ()
    bracket_settle_seconds: float = DEFAULT_BRACKET_SETTLE_SECONDS
    rotation: Rotation = DEFAULT_ROTATION
    warmup_seconds: float = DEFAULT_WARMUP_SECONDS
    focus_mode: FocusMode = DEFAULT_FOCUS_MODE
    lens_position: float | None = None
    awb_mode: AwbMode = DEFAULT_AWB_MODE
    awb_lock: bool = DEFAULT_AWB_LOCK


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


def env_bool(name: str, default: bool) -> bool:
    value = os.environ.get(name)
    if value is None or value.strip() == "":
        return default
    return value.strip().lower() not in {"0", "false", "no", "off"}


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


def env_float_tuple(name: str) -> tuple[float, ...]:
    value = os.environ.get(name)
    if value is None or value.strip() == "":
        return ()
    return tuple(float(part.strip()) for part in value.split(",") if part.strip())


def resolve_project_path(project_root: Path, value: str | Path) -> Path:
    path = Path(value).expanduser()
    if path.is_absolute():
        return path
    return project_root / path


def capture_output_dir_from_env(project_root: Path) -> Path:
    output_dir = os.environ.get("TINY_FILM_OUTPUT_DIR", "data/captures")
    return resolve_project_path(project_root, output_dir)


def capture_settings_from_env(project_root: Path) -> CaptureSettings:
    focus_mode = os.environ.get("TINY_FILM_CAPTURE_FOCUS_MODE", DEFAULT_FOCUS_MODE)
    if focus_mode not in FOCUS_MODES:
        focus_mode = DEFAULT_FOCUS_MODE
    awb_mode = os.environ.get("TINY_FILM_CAPTURE_AWB_MODE", DEFAULT_AWB_MODE)
    if awb_mode not in AWB_MODES:
        awb_mode = DEFAULT_AWB_MODE
    rotation = env_int("TINY_FILM_CAPTURE_ROTATION", DEFAULT_ROTATION)
    if rotation not in ROTATIONS:
        rotation = DEFAULT_ROTATION
    return CaptureSettings(
        output_dir=capture_output_dir_from_env(project_root),
        width=env_optional_int("TINY_FILM_CAPTURE_WIDTH"),
        height=env_optional_int("TINY_FILM_CAPTURE_HEIGHT"),
        quality=env_int("TINY_FILM_CAPTURE_QUALITY", DEFAULT_QUALITY),
        sharpness=env_float("TINY_FILM_CAPTURE_SHARPNESS", DEFAULT_SHARPNESS),
        contrast=env_float("TINY_FILM_CAPTURE_CONTRAST", DEFAULT_CONTRAST),
        saturation=env_float("TINY_FILM_CAPTURE_SATURATION", DEFAULT_SATURATION),
        exposure_value=env_float("TINY_FILM_CAPTURE_EV", DEFAULT_EXPOSURE_VALUE),
        exposure_brackets=env_float_tuple("TINY_FILM_CAPTURE_BRACKETS"),
        bracket_settle_seconds=env_float(
            "TINY_FILM_CAPTURE_BRACKET_SETTLE_SECONDS",
            DEFAULT_BRACKET_SETTLE_SECONDS,
        ),
        rotation=rotation,  # type: ignore[arg-type]
        warmup_seconds=env_float(
            "TINY_FILM_CAPTURE_WARMUP_SECONDS", DEFAULT_WARMUP_SECONDS
        ),
        focus_mode=focus_mode,  # type: ignore[arg-type]
        lens_position=env_optional_float("TINY_FILM_CAPTURE_LENS_POSITION"),
        awb_mode=awb_mode,  # type: ignore[arg-type]
        awb_lock=env_bool("TINY_FILM_CAPTURE_AWB_LOCK", DEFAULT_AWB_LOCK),
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


def _ev_suffix(exposure_value: float) -> str:
    label = f"{exposure_value:+.1f}".replace(".", "p")
    return f"ev{label}"


def _path_with_stem_suffix(path: Path, stem_suffix: str) -> Path:
    return path.with_name(f"{path.stem}_{stem_suffix}{path.suffix}")


def _normalized_quality(value: int) -> int:
    return max(1, min(100, int(value)))


def _output_path(settings: CaptureSettings) -> Path:
    if settings.filename:
        path = Path(settings.filename).expanduser()
    else:
        path = _timestamped_path(settings.output_dir.expanduser())
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def _exposure_values(settings: CaptureSettings) -> tuple[float, ...]:
    if settings.exposure_brackets:
        return settings.exposure_brackets
    return (settings.exposure_value,)


def _output_paths(settings: CaptureSettings) -> list[Path]:
    path = _output_path(settings)
    exposure_values = _exposure_values(settings)
    if len(exposure_values) == 1:
        return [path]
    return [_path_with_stem_suffix(path, _ev_suffix(ev)) for ev in exposure_values]


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
        "ExposureValue": settings.exposure_value,
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

    if settings.awb_mode != "default":
        enum_name = AWB_MODE_ENUM_NAMES.get(settings.awb_mode)
        enum_value = getattr(libcamera_controls.AwbModeEnum, enum_name, None)
        if enum_value is not None:
            controls["AwbMode"] = enum_value

    return controls


def _apply_awb_lock(picam2, settings: CaptureSettings) -> None:
    if settings.awb_lock:
        picam2.set_controls({"AwbEnable": False})


def _set_exposure_value(picam2, exposure_value: float) -> None:
    picam2.set_controls({"ExposureValue": exposure_value})


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


def capture_photos(settings: CaptureSettings = CaptureSettings()) -> list[Path]:
    """Capture one or more still images from a Raspberry Pi Camera Module 3."""
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
        output_paths = _output_paths(settings)
        exposure_values = _exposure_values(settings)
        started = False

        try:
            picam2.configure(config)
            picam2.start()
            started = True
            if settings.warmup_seconds > 0:
                time.sleep(settings.warmup_seconds)
            _apply_awb_lock(picam2, settings)

            for exposure_value, output_path in zip(
                exposure_values, output_paths, strict=True
            ):
                if len(exposure_values) > 1 or exposure_value != settings.exposure_value:
                    _set_exposure_value(picam2, exposure_value)
                    if settings.bracket_settle_seconds > 0:
                        time.sleep(settings.bracket_settle_seconds)

                frame = picam2.capture_array("main")
                image = _image_from_picamera_frame(frame)
                image = _rotate_image(image, settings.rotation)
                image.save(
                    output_path,
                    format="JPEG",
                    quality=_normalized_quality(settings.quality),
                )
        finally:
            if started:
                picam2.stop()
            picam2.close()

        return output_paths


def capture_photo(settings: CaptureSettings = CaptureSettings()) -> Path:
    """Capture still image(s) and return the primary saved path."""
    return capture_photos(settings)[0]
