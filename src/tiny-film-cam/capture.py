from __future__ import annotations

import argparse
from pathlib import Path

from camera import (
    AWB_MODES,
    CaptureSettings,
    DEFAULT_AWB_LOCK,
    DEFAULT_AWB_MODE,
    DEFAULT_BRACKET_SETTLE_SECONDS,
    DEFAULT_FOCUS_MODE,
    DEFAULT_QUALITY,
    DEFAULT_ROTATION,
    DEFAULT_SHARPNESS,
    capture_photos,
)
from photo_filters import DEFAULT_PHOTO_FILTER, PHOTO_FILTER_NAMES


def parse_exposure_brackets(value: str) -> tuple[float, ...]:
    return tuple(float(part.strip()) for part in value.split(",") if part.strip())


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Capture a still photo with a Raspberry Pi Camera Module 3."
    )
    parser.add_argument(
        "-o",
        "--output",
        help="Output filename, like rpicam-still -o.",
    )
    parser.add_argument(
        "--output-dir",
        default="data/captures",
        help="Base directory for date-grouped timestamped output when --output is omitted.",
    )
    parser.add_argument("--width", type=int, help="Optional still capture width.")
    parser.add_argument("--height", type=int, help="Optional still capture height.")
    parser.add_argument(
        "--quality", type=int, default=DEFAULT_QUALITY, help="JPEG quality, 1-100."
    )
    parser.add_argument("--sharpness", type=float, default=DEFAULT_SHARPNESS)
    parser.add_argument(
        "--contrast",
        type=float,
        help="Override the selected photo filter's contrast.",
    )
    parser.add_argument(
        "--saturation",
        type=float,
        help="Override the selected photo filter's saturation.",
    )
    parser.add_argument(
        "--ev",
        type=float,
        help="Override the selected photo filter's exposure compensation.",
    )
    parser.add_argument(
        "--exposure-brackets",
        type=parse_exposure_brackets,
        default=(),
        help="Comma-separated EV values to capture, e.g. '0,-0.7,-1.0'.",
    )
    parser.add_argument(
        "--bracket-settle-seconds",
        type=float,
        default=DEFAULT_BRACKET_SETTLE_SECONDS,
        help="Seconds to let auto exposure settle between bracketed shots.",
    )
    parser.add_argument(
        "--rotation",
        type=int,
        choices=(0, 90, 180, 270),
        default=DEFAULT_ROTATION,
        help="Rotate the saved JPEG clockwise after capture.",
    )
    parser.add_argument(
        "--warmup-seconds",
        type=float,
        help="Override the selected photo filter's exposure/AWB warmup.",
    )
    parser.add_argument(
        "--focus-mode",
        choices=("default", "auto", "continuous", "manual"),
        default=DEFAULT_FOCUS_MODE,
        help="Camera Module 3 focus mode.",
    )
    parser.add_argument(
        "--lens-position",
        type=float,
        help="Manual lens position. Only used with --focus-mode manual.",
    )
    parser.add_argument(
        "--awb-mode",
        choices=sorted(AWB_MODES),
        default=DEFAULT_AWB_MODE,
        help="White balance mode. Use daylight/cloudy/etc for more consistent grading.",
    )
    parser.add_argument(
        "--awb-lock",
        action="store_true",
        default=DEFAULT_AWB_LOCK,
        help="Let AWB settle during warmup, then lock it before capture.",
    )
    parser.add_argument(
        "--keep-original",
        action="store_true",
        help="Also save the same ungraded frame as a lossless .original.png for regrading.",
    )
    parser.add_argument(
        "--photo-filter",
        choices=PHOTO_FILTER_NAMES,
        default=DEFAULT_PHOTO_FILTER,
        help="Photo look to bake into the saved JPEG.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    settings = CaptureSettings(
        output_dir=Path(args.output_dir),
        filename=args.output,
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
        photo_filter=args.photo_filter,
        keep_original=args.keep_original,
    )
    output_paths = capture_photos(settings)
    for output_path in output_paths:
        print(f"Saved photo to {output_path}")


if __name__ == "__main__":
    main()
