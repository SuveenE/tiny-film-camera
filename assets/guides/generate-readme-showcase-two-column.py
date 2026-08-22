#!/usr/bin/env python3
"""Build the two-column README showcase from checked-in source images."""

from __future__ import annotations

import argparse
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageOps


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CAMERA = (
    REPO_ROOT / "assets/v1/product-images/camera-launch-warm.png"
)
DEFAULT_CAD_CARD_SOURCE = REPO_ROOT / "assets/guides/readme-showcase.png"
DEFAULT_SAMPLE = (
    REPO_ROOT / "assets/photo-samples/train-sample-1935x1346.jpg"
)
DEFAULT_OUTPUT = REPO_ROOT / "assets/guides/readme-showcase-two-column.png"

CANVAS_SIZE = (1672, 941)
BACKGROUND = (253, 248, 244, 255)
OUTER_MARGIN = 20
GUTTER = 18
LEFT_COLUMN_WIDTH = 918
PANEL_RADIUS = 15
LABEL = "sample photo"
LABEL_FONT_SIZE = 30
LABEL_BOTTOM_PADDING = 25
CAD_CARD_BOX = (968, 540, 1637, 909)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--camera", type=Path, default=DEFAULT_CAMERA)
    parser.add_argument(
        "--cad-card-source",
        type=Path,
        default=DEFAULT_CAD_CARD_SOURCE,
    )
    parser.add_argument("--sample", type=Path, default=DEFAULT_SAMPLE)
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


def rounded_mask(size: tuple[int, int]) -> Image.Image:
    mask = Image.new("L", size, 0)
    ImageDraw.Draw(mask).rounded_rectangle(
        (0, 0, size[0] - 1, size[1] - 1),
        radius=PANEL_RADIUS,
        fill=255,
    )
    return mask


def fit_photo(image: Image.Image, size: tuple[int, int]) -> Image.Image:
    return ImageOps.fit(
        image.convert("RGBA"),
        size,
        method=Image.Resampling.LANCZOS,
        centering=(0.5, 0.5),
    )


def reuse_cad_card(image: Image.Image, size: tuple[int, int]) -> Image.Image:
    panel = Image.new("RGBA", size, (255, 255, 255, 255))
    card = image.crop(CAD_CARD_BOX).convert("RGBA")
    contained = ImageOps.contain(
        card,
        size,
        method=Image.Resampling.LANCZOS,
    )
    position = (
        (size[0] - contained.width) // 2,
        (size[1] - contained.height) // 2,
    )
    panel.alpha_composite(contained, position)
    return panel


def draw_sample_label(
    panel: Image.Image,
    font_path: Path | None,
) -> None:
    draw = ImageDraw.Draw(panel)
    font = load_font(font_path)
    text_box = draw.textbbox((0, 0), LABEL, font=font, stroke_width=1)
    text_width = text_box[2] - text_box[0]
    text_height = text_box[3] - text_box[1]
    text_x = ((panel.width - text_width) // 2) - text_box[0]
    text_y = (
        panel.height
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


def build_collage(
    camera_path: Path,
    cad_card_source_path: Path,
    sample_path: Path,
    output_path: Path,
    font_path: Path | None,
) -> None:
    camera = Image.open(camera_path)
    cad_card_source = Image.open(cad_card_source_path)
    sample = Image.open(sample_path)

    canvas_width, canvas_height = CANVAS_SIZE
    content_height = canvas_height - (2 * OUTER_MARGIN)
    right_x = OUTER_MARGIN + LEFT_COLUMN_WIDTH + GUTTER
    right_width = canvas_width - right_x - OUTER_MARGIN
    top_height = (content_height - GUTTER) // 2
    bottom_height = content_height - GUTTER - top_height
    bottom_y = OUTER_MARGIN + top_height + GUTTER

    canvas = Image.new("RGBA", CANVAS_SIZE, BACKGROUND)

    left_panel = fit_photo(camera, (LEFT_COLUMN_WIDTH, content_height))
    canvas.paste(
        left_panel,
        (OUTER_MARGIN, OUTER_MARGIN),
        rounded_mask(left_panel.size),
    )

    cad_panel = reuse_cad_card(cad_card_source, (right_width, top_height))
    canvas.paste(
        cad_panel,
        (right_x, OUTER_MARGIN),
        rounded_mask(cad_panel.size),
    )

    sample_panel = fit_photo(sample, (right_width, bottom_height))
    draw_sample_label(sample_panel, font_path)
    canvas.paste(
        sample_panel,
        (right_x, bottom_y),
        rounded_mask(sample_panel.size),
    )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    canvas.convert("RGB").save(output_path, format="PNG", optimize=True)


def main() -> None:
    args = parse_args()
    build_collage(
        args.camera,
        args.cad_card_source,
        args.sample,
        args.output,
        args.font,
    )


if __name__ == "__main__":
    main()
