from __future__ import annotations

import argparse
import logging
import os
import signal
import threading
from pathlib import Path

from buzzer import ShutterBuzzer
from camera import (
    AWB_MODES,
    CaptureSettings,
    VideoSettings,
    capture_photos,
    capture_settings_from_env,
    record_video,
    resolve_project_path,
    video_settings_from_env,
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


def env_optional_int(name: str, default: int | None = None) -> int | None:
    """Read an optional int env var.

    Unset → ``default``. Explicit empty string → ``None`` (used to disable the
    buzzer while keeping the code default of GPIO 18 when the var is absent).
    """
    value = os.environ.get(name)
    if value is None:
        return default
    if value.strip() == "":
        return None
    return int(value)


def env_float(name: str, default: float) -> float:
    value = os.environ.get(name)
    if value is None or value.strip() == "":
        return default
    return float(value)


def parse_exposure_brackets(value: str) -> tuple[float, ...]:
    return tuple(float(part.strip()) for part in value.split(",") if part.strip())


def default_project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def parse_args() -> argparse.Namespace:
    project_root = default_project_root().expanduser().resolve()
    capture_defaults = capture_settings_from_env(project_root)
    video_defaults = video_settings_from_env(project_root)
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
        "--buzzer-pin",
        type=int,
        default=env_optional_int("TINY_FILM_BUZZER_PIN", 18),
        help="BCM GPIO pin for the feedback buzzer (default: 18). Use --no-buzzer to disable.",
    )
    parser.add_argument(
        "--no-buzzer",
        action="store_true",
        help="Disable the feedback buzzer.",
    )
    parser.set_defaults(buzzer_active=env_bool("TINY_FILM_BUZZER_ACTIVE", False))
    parser.add_argument(
        "--buzzer-active",
        dest="buzzer_active",
        action="store_true",
        help="Treat the buzzer as an active buzzer (simple on/off tone).",
    )
    parser.add_argument(
        "--buzzer-passive",
        dest="buzzer_active",
        action="store_false",
        help="Treat the buzzer as a passive buzzer driven with PWM tones (default).",
    )
    parser.add_argument(
        "--buzzer-volume",
        type=float,
        default=env_float("TINY_FILM_BUZZER_VOLUME", 0.14),
        help="Passive buzzer loudness 0.0–1.0 via burst density (default: 0.14).",
    )
    parser.add_argument(
        "--hold-time",
        type=float,
        default=1.0,
        help="Seconds to hold the button before it records a video instead of a photo.",
    )
    parser.add_argument(
        "--video-duration",
        type=float,
        default=video_defaults.duration_seconds,
        help="Length in seconds of a held-button video clip.",
    )
    parser.add_argument("--video-width", type=int, default=video_defaults.width)
    parser.add_argument("--video-height", type=int, default=video_defaults.height)
    parser.add_argument("--video-fps", type=int, default=video_defaults.fps)
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
        "--ev",
        type=float,
        default=capture_defaults.exposure_value,
    )
    parser.add_argument(
        "--exposure-brackets",
        type=parse_exposure_brackets,
        default=capture_defaults.exposure_brackets,
    )
    parser.add_argument(
        "--bracket-settle-seconds",
        type=float,
        default=capture_defaults.bracket_settle_seconds,
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
    parser.add_argument(
        "--awb-mode",
        choices=sorted(AWB_MODES),
        default=capture_defaults.awb_mode,
    )
    parser.add_argument(
        "--awb-lock",
        action="store_true",
        default=capture_defaults.awb_lock,
    )
    parser.add_argument(
        "--no-awb-lock",
        dest="awb_lock",
        action="store_false",
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
    held_flag = threading.Event()
    buzzer_pin = None if args.no_buzzer else args.buzzer_pin
    buzzer = ShutterBuzzer(
        buzzer_pin,
        active=args.buzzer_active,
        volume=args.buzzer_volume,
    )

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
            buzzer.shutter()
            settings = CaptureSettings(
                output_dir=output_dir,
                width=args.width,
                height=args.height,
                quality=args.quality,
                sharpness=args.sharpness,
                contrast=args.contrast,
                saturation=args.saturation,
                exposure_value=args.ev,
                exposure_brackets=args.exposure_brackets,
                bracket_settle_seconds=args.bracket_settle_seconds,
                rotation=args.rotation,
                warmup_seconds=args.warmup_seconds,
                focus_mode=args.focus_mode,
                lens_position=args.lens_position,
                awb_mode=args.awb_mode,
                awb_lock=args.awb_lock,
            )
            output_paths = capture_photos(settings)
            LOGGER.info("Saved %s photo(s): %s", len(output_paths), output_paths)
        except Exception:
            LOGGER.exception("Capture failed")
            buzzer.error()
        finally:
            capture_lock.release()

    def record_clip() -> None:
        held_flag.set()
        if not capture_lock.acquire(blocking=False):
            LOGGER.info("Ignored button hold because a capture is already running")
            return

        try:
            LOGGER.info("Button held; recording %.1fs video", args.video_duration)
            buzzer.video_start()
            settings = VideoSettings(
                output_dir=output_dir,
                width=args.video_width,
                height=args.video_height,
                fps=args.video_fps,
                duration_seconds=args.video_duration,
                sharpness=args.sharpness,
                contrast=args.contrast,
                saturation=args.saturation,
                exposure_value=args.ev,
                rotation=args.rotation,
                warmup_seconds=args.warmup_seconds,
                focus_mode=args.focus_mode,
                lens_position=args.lens_position,
                awb_mode=args.awb_mode,
                awb_lock=args.awb_lock,
            )
            output_path = record_video(settings)
            LOGGER.info("Saved video: %s", output_path)
            buzzer.video_stop()
        except Exception:
            LOGGER.exception("Recording failed")
            buzzer.error()
        finally:
            capture_lock.release()

    def on_release() -> None:
        # A long hold already triggered a video via when_held; skip the photo.
        if held_flag.is_set():
            held_flag.clear()
            return
        take_photo()

    signal.signal(signal.SIGINT, request_stop)
    signal.signal(signal.SIGTERM, request_stop)

    button = Button(
        args.pin,
        pull_up=args.pull_up,
        bounce_time=args.bounce_time if args.bounce_time > 0 else None,
        hold_time=args.hold_time if args.hold_time > 0 else 1.0,
    )
    button.when_held = record_clip
    button.when_released = on_release

    wiring = "GPIO-to-GND with pull-up" if args.pull_up else "GPIO-to-3V3 with pull-down"
    LOGGER.info("Tiny Film shutter ready on BCM GPIO %s (%s)", args.pin, wiring)
    LOGGER.info(
        "Tap to photograph; hold %.1fs to record a %.1fs video",
        args.hold_time,
        args.video_duration,
    )
    LOGGER.info("Captures will be saved under %s", output_dir)
    if buzzer.enabled:
        buzzer_kind = "active" if args.buzzer_active else "passive"
        LOGGER.info(
            "Buzzer feedback on BCM GPIO %s (%s, volume=%.2f)",
            buzzer_pin,
            buzzer_kind,
            args.buzzer_volume,
        )
    elif args.no_buzzer or buzzer_pin is None:
        LOGGER.info("Buzzer feedback disabled")

    try:
        while not stop_event.wait(1.0):
            pass
    finally:
        button.close()
        buzzer.close()


if __name__ == "__main__":
    main()
