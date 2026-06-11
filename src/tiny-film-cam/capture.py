from __future__ import annotations

import argparse
from pathlib import Path

from camera import CaptureSettings, capture_photo


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
        default="images",
        help="Directory for timestamped output when --output is omitted.",
    )
    parser.add_argument("--width", type=int, help="Optional still capture width.")
    parser.add_argument("--height", type=int, help="Optional still capture height.")
    parser.add_argument("--quality", type=int, default=95, help="JPEG quality, 1-100.")
    parser.add_argument("--sharpness", type=float, default=0.5)
    parser.add_argument("--contrast", type=float, default=0.9)
    parser.add_argument("--saturation", type=float, default=0.9)
    parser.add_argument(
        "--rotation",
        type=int,
        choices=(0, 90, 180, 270),
        default=0,
        help="Rotate the saved JPEG after capture.",
    )
    parser.add_argument(
        "--warmup-seconds",
        type=float,
        default=0.5,
        help="Seconds to let exposure/focus settle before capture.",
    )
    parser.add_argument(
        "--focus-mode",
        choices=("default", "auto", "continuous", "manual"),
        default="continuous",
        help="Camera Module 3 focus mode.",
    )
    parser.add_argument(
        "--lens-position",
        type=float,
        help="Manual lens position. Only used with --focus-mode manual.",
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
        rotation=args.rotation,
        warmup_seconds=args.warmup_seconds,
        focus_mode=args.focus_mode,
        lens_position=args.lens_position,
    )
    output_path = capture_photo(settings)
    print(f"Saved photo to {output_path}")


if __name__ == "__main__":
    main()
