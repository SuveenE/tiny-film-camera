from __future__ import annotations

import argparse
from pathlib import Path

from camera import (
    AWB_MODES,
    DEFAULT_AWB_LOCK,
    DEFAULT_AWB_MODE,
    DEFAULT_CONTRAST,
    DEFAULT_EXPOSURE_VALUE,
    DEFAULT_FOCUS_MODE,
    DEFAULT_ROTATION,
    DEFAULT_SATURATION,
    DEFAULT_SHARPNESS,
    DEFAULT_VIDEO_DURATION_SECONDS,
    DEFAULT_VIDEO_FPS,
    DEFAULT_VIDEO_HEIGHT,
    DEFAULT_VIDEO_WIDTH,
    DEFAULT_WARMUP_SECONDS,
    VideoSettings,
    record_video,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Record a short video with a Raspberry Pi Camera Module 3."
    )
    parser.add_argument(
        "-o",
        "--output",
        help="Output filename ending in .mp4, like rpicam-vid -o.",
    )
    parser.add_argument(
        "--output-dir",
        default="data/captures",
        help="Base directory for date-grouped timestamped output when --output is omitted.",
    )
    parser.add_argument(
        "--duration",
        type=float,
        default=DEFAULT_VIDEO_DURATION_SECONDS,
        help="Clip length in seconds.",
    )
    parser.add_argument("--width", type=int, default=DEFAULT_VIDEO_WIDTH)
    parser.add_argument("--height", type=int, default=DEFAULT_VIDEO_HEIGHT)
    parser.add_argument("--fps", type=int, default=DEFAULT_VIDEO_FPS)
    parser.add_argument(
        "--bitrate",
        type=int,
        help="H.264 bitrate in bits/sec. Omit for the encoder default.",
    )
    parser.add_argument("--sharpness", type=float, default=DEFAULT_SHARPNESS)
    parser.add_argument("--contrast", type=float, default=DEFAULT_CONTRAST)
    parser.add_argument("--saturation", type=float, default=DEFAULT_SATURATION)
    parser.add_argument(
        "--ev",
        type=float,
        default=DEFAULT_EXPOSURE_VALUE,
        help="Exposure compensation in stops, e.g. -0.7 to protect highlights.",
    )
    parser.add_argument(
        "--rotation",
        type=int,
        choices=(0, 180),
        default=DEFAULT_ROTATION,
        help="Rotate the recording. Video supports 0 or 180 only.",
    )
    parser.add_argument(
        "--warmup-seconds",
        type=float,
        default=DEFAULT_WARMUP_SECONDS,
        help="Seconds to let exposure/focus settle before recording.",
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
        help="White balance mode.",
    )
    parser.add_argument(
        "--awb-lock",
        action="store_true",
        default=DEFAULT_AWB_LOCK,
        help="Let AWB settle during warmup, then lock it before recording.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    settings = VideoSettings(
        output_dir=Path(args.output_dir),
        filename=args.output,
        width=args.width,
        height=args.height,
        fps=args.fps,
        duration_seconds=args.duration,
        bitrate=args.bitrate,
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
    print(f"Saved video to {output_path}")


if __name__ == "__main__":
    main()
