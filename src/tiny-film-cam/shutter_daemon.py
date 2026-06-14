from __future__ import annotations

import argparse
import logging
import os
import signal
import threading
from pathlib import Path

from camera import CaptureSettings, capture_photo


LOGGER = logging.getLogger("tiny_film.shutter")


def env_bool(name: str, default: bool) -> bool:
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() not in {"0", "false", "no", "off"}


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


def default_project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def resolve_project_path(project_root: Path, value: str) -> Path:
    path = Path(value).expanduser()
    if path.is_absolute():
        return path
    return project_root / path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run the Tiny Film physical shutter button listener."
    )
    parser.add_argument("--project-root", type=Path, default=default_project_root())
    parser.add_argument("--pin", type=int, default=env_int("TINY_FILM_BUTTON_PIN", 17))
    parser.set_defaults(pull_up=env_bool("TINY_FILM_BUTTON_PULL_UP", True))
    parser.add_argument("--pull-up", dest="pull_up", action="store_true")
    parser.add_argument("--pull-down", dest="pull_up", action="store_false")
    parser.add_argument(
        "--bounce-time",
        type=float,
        default=env_float("TINY_FILM_BUTTON_BOUNCE_SECONDS", 0.15),
    )
    parser.add_argument(
        "--output-dir",
        default=os.environ.get("TINY_FILM_OUTPUT_DIR", "data/captures"),
    )
    parser.add_argument("--width", type=int, default=env_optional_int("TINY_FILM_CAPTURE_WIDTH"))
    parser.add_argument("--height", type=int, default=env_optional_int("TINY_FILM_CAPTURE_HEIGHT"))
    parser.add_argument(
        "--quality",
        type=int,
        default=env_int("TINY_FILM_CAPTURE_QUALITY", 95),
    )
    parser.add_argument(
        "--sharpness",
        type=float,
        default=env_float("TINY_FILM_CAPTURE_SHARPNESS", 0.5),
    )
    parser.add_argument(
        "--contrast",
        type=float,
        default=env_float("TINY_FILM_CAPTURE_CONTRAST", 0.9),
    )
    parser.add_argument(
        "--saturation",
        type=float,
        default=env_float("TINY_FILM_CAPTURE_SATURATION", 0.9),
    )
    parser.add_argument(
        "--rotation",
        type=int,
        choices=(0, 90, 180, 270),
        default=env_int("TINY_FILM_CAPTURE_ROTATION", 0),
    )
    parser.add_argument(
        "--warmup-seconds",
        type=float,
        default=env_float("TINY_FILM_CAPTURE_WARMUP_SECONDS", 0.5),
    )
    parser.add_argument(
        "--focus-mode",
        choices=("default", "auto", "continuous", "manual"),
        default=os.environ.get("TINY_FILM_CAPTURE_FOCUS_MODE", "continuous"),
    )
    parser.add_argument(
        "--lens-position",
        type=float,
        default=env_optional_float("TINY_FILM_CAPTURE_LENS_POSITION"),
    )
    return parser.parse_args()


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )
    args = parse_args()
    project_root = args.project_root.expanduser().resolve()
    output_dir = resolve_project_path(project_root, args.output_dir)
    capture_lock = threading.Lock()
    stop_event = threading.Event()

    try:
        from gpiozero import Button
    except ImportError as exc:
        raise SystemExit(
            "Missing gpiozero. On the Raspberry Pi, install it with: "
            "sudo apt install -y python3-gpiozero"
        ) from exc

    def request_stop(signum: int, frame: object) -> None:
        LOGGER.info("Stopping on signal %s", signum)
        stop_event.set()

    def take_photo() -> None:
        if not capture_lock.acquire(blocking=False):
            LOGGER.info("Ignored button press because a capture is already running")
            return

        try:
            LOGGER.info("Button pressed; capturing photo")
            settings = CaptureSettings(
                output_dir=output_dir,
                width=args.width,
                height=args.height,
                quality=args.quality,
                sharpness=args.sharpness,
                contrast=args.contrast,
                saturation=args.saturation,
                rotation=args.rotation,
                warmup_seconds=args.warmup_seconds,
                focus_mode=args.focus_mode,
                lens_position=args.lens_position,
            )
            output_path = capture_photo(settings)
            LOGGER.info("Saved photo to %s", output_path)
        except Exception:
            LOGGER.exception("Capture failed")
        finally:
            capture_lock.release()

    signal.signal(signal.SIGINT, request_stop)
    signal.signal(signal.SIGTERM, request_stop)

    button = Button(
        args.pin,
        pull_up=args.pull_up,
        bounce_time=args.bounce_time if args.bounce_time > 0 else None,
    )
    button.when_pressed = take_photo

    wiring = "GPIO-to-GND with pull-up" if args.pull_up else "GPIO-to-3V3 with pull-down"
    LOGGER.info("Tiny Film shutter ready on BCM GPIO %s (%s)", args.pin, wiring)
    LOGGER.info("Captures will be saved under %s", output_dir)

    try:
        while not stop_event.wait(1.0):
            pass
    finally:
        button.close()


if __name__ == "__main__":
    main()
