#!/usr/bin/env python3
"""Build the README showcase collage from checked-in source images."""

from __future__ import annotations

import argparse
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageOps


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_BASE = REPO_ROOT / "assets/guides/readme-showcase.png"
DEFAULT_PORTRAIT = (
    REPO_ROOT / "assets/photo-samples/train-zoomed-1170x2080.jpg"
)
DEFAULT_OUTPUT = REPO_ROOT / "assets/guides/readme-showcase-with-sample.png"

OUTER_MARGIN = 20
PANEL_RADIUS = 15
LABEL = "sample photo"
LABEL_FONT_SIZE = 30
LABEL_BOTTOM_PADDING = 25


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", type=Path, default=DEFAULT_BASE)
    parser.add_argument("--portrait", type=Path, default=DEFAULT_PORTRAIT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--font", type=Path)
    return parser.parse_args()


def load_font(font_path: Path | None) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    candidates = [
        font_path,
        Path("/System/Library/Fonts/SFNS.ttf"),
        Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
        Path("/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf"),
    ]
    for candidate in candidates:
        if candidate and candidate.is_file():
            return ImageFont.truetype(candidate, LABEL_FONT_SIZE)
    return ImageFont.load_default(size=LABEL_FONT_SIZE)


def build_collage(
    base_path: Path,
    portrait_path: Path,
    output_path: Path,
    font_path: Path | None,
) -> None:
    base = Image.open(base_path).convert("RGBA")
    portrait = Image.open(portrait_path).convert("RGBA")

    panel_y = OUTER_MARGIN
    panel_height = base.height - (2 * OUTER_MARGIN)
    panel_width = round(panel_height * portrait.width / portrait.height)
    panel_x = base.width
    output_width = panel_x + panel_width + OUTER_MARGIN

    # Extend the original outer background across the wider canvas while
    # retaining its subtle vertical color variation.
    edge_strip = base.crop((base.width - OUTER_MARGIN, 0, base.width, base.height))
    edge_strip = edge_strip.resize((1, base.height), Image.Resampling.BOX)
    background = edge_strip.resize(
        (output_width, base.height), Image.Resampling.NEAREST
    )
    background.paste(base, (0, 0), base)

    panel = ImageOps.fit(
        portrait,
        (panel_width, panel_height),
        method=Image.Resampling.LANCZOS,
        centering=(0.5, 0.5),
    )
    mask = Image.new("L", panel.size, 0)
    ImageDraw.Draw(mask).rounded_rectangle(
        (0, 0, panel_width - 1, panel_height - 1),
        radius=PANEL_RADIUS,
        fill=255,
    )
    background.paste(panel, (panel_x, panel_y), mask)

    draw = ImageDraw.Draw(background)
    font = load_font(font_path)
    text_box = draw.textbbox((0, 0), LABEL, font=font, stroke_width=1)
    text_width = text_box[2] - text_box[0]
    text_height = text_box[3] - text_box[1]
    text_x = panel_x + ((panel_width - text_width) // 2) - text_box[0]
    text_y = (
        panel_y
        + panel_height
        - LABEL_BOTTOM_PADDING
        - text_height
        - text_box[1]
    )
    draw.text(
        (text_x, text_y),
        LABEL,
        font=font,
        fill=(247, 243, 238, 255),
        stroke_width=1,
        stroke_fill=(25, 25, 25, 210),
    )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    background.convert("RGB").save(output_path, format="PNG", optimize=True)


def main() -> None:
    args = parse_args()
    build_collage(args.base, args.portrait, args.output, args.font)


if __name__ == "__main__":
    main()
