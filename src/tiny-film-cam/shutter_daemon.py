from __future__ import annotations

import argparse
import logging
import os
import signal
import threading
from pathlib import Path

from camera import (
    CaptureSettings,
    capture_photo,
    capture_settings_from_env,
    resolve_project_path,
)


LOGGER = logging.getLogger("tiny_film.shutter")


def env_bool(name: str, default: bool) -> bool:
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() not in {"0", "false", "no", "off"}


def env_int(name: str, default: int) -> int:
    value = os.environ.get(name)
    if value is None or value.strip() == "":
        return default
    return int(value)


def env_float(name: str, default: float) -> float:
    value = os.environ.get(name)
    if value is None or value.strip() == "":
        return default
    return float(value)


def default_project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def parse_args() -> argparse.Namespace:
    project_root = default_project_root().expanduser().resolve()
    capture_defaults = capture_settings_from_env(project_root)
    parser = argparse.ArgumentParser(
        description="Run the Tiny Film physical shutter button listener."
    )
    parser.add_argument("--project-root", type=Path, default=project_root)
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
        default=str(capture_defaults.output_dir),
    )
    parser.add_argument("--width", type=int, default=capture_defaults.width)
    parser.add_argument("--height", type=int, default=capture_defaults.height)
    parser.add_argument(
        "--quality",
        type=int,
        default=capture_defaults.quality,
    )
    parser.add_argument(
        "--sharpness",
        type=float,
        default=capture_defaults.sharpness,
    )
    parser.add_argument(
        "--contrast",
        type=float,
        default=capture_defaults.contrast,
    )
    parser.add_argument(
        "--saturation",
        type=float,
        default=capture_defaults.saturation,
    )
    parser.add_argument(
        "--rotation",
        type=int,
        choices=(0, 90, 180, 270),
        default=capture_defaults.rotation,
        help="Rotate the saved JPEG clockwise after capture.",
    )
    parser.add_argument(
        "--warmup-seconds",
        type=float,
        default=capture_defaults.warmup_seconds,
    )
    parser.add_argument(
        "--focus-mode",
        choices=("default", "auto", "continuous", "manual"),
        default=capture_defaults.focus_mode,
    )
    parser.add_argument(
        "--lens-position",
        type=float,
        default=capture_defaults.lens_position,
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
