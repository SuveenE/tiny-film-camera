"""Grade existing photographs with the same LUT used during camera capture."""
from __future__ import annotations

import argparse
import io
import json
import math
from pathlib import Path

from PIL import Image, ImageOps

from photo_filters import PHOTO_FILTER_NAMES, apply_photo_filter, photo_filter_details


def grade_file(source: Path, output: Path, photo_filter: str = "wes_anderson",
               strength: float = 1.0) -> Path:
    """Read an original once, normalize to sRGB, and write a new JPEG or PNG.

    Existing outputs are never overwritten. Strength blends the original and
    graded RGB pixels; always regrade from the original, not an earlier result.
    """
    if photo_filter not in PHOTO_FILTER_NAMES:
        raise ValueError(f"Unknown photo filter: {photo_filter}")
    if not math.isfinite(strength) or not 0.0 <= strength <= 1.0:
        raise ValueError("Strength must be between 0 and 1")
    if source.resolve() == output.resolve():
        raise ValueError("Output must differ from the original")
    image_format = {".jpg": "JPEG", ".jpeg": "JPEG", ".png": "PNG"}.get(output.suffix.lower())
    if image_format is None:
        raise ValueError("Output must be .jpg, .jpeg, or .png")
    sidecar = output.with_name(output.name + ".json")
    if output.exists() or sidecar.exists():
        raise FileExistsError(f"Output already exists: {output}")
    with Image.open(source) as opened:
        original = ImageOps.exif_transpose(opened)
        profile = original.info.get("icc_profile")
        if profile:
            from PIL import ImageCms

            original = ImageCms.profileToProfile(
                original, ImageCms.ImageCmsProfile(io.BytesIO(profile)),
                ImageCms.createProfile("sRGB"), outputMode="RGB",
            )
        else:
            original = original.convert("RGB")
        graded = apply_photo_filter(original, photo_filter)
        if strength != 1.0:
            graded = Image.blend(original, graded, strength)
        # The orientation is already baked into pixels; avoid stale thumbnails
        # and color-profile tags from the input. Record provenance separately.
        graded.info.clear()
        output.parent.mkdir(parents=True, exist_ok=True)
        with output.open("xb") as stream:
            graded.save(stream, format=image_format, **(
                {"quality": 95, "subsampling": 0} if image_format == "JPEG" else {}
            ))
    payload = {
        "photo_filter": photo_filter_details(photo_filter),
        "strength": strength,
        "source": str(source.resolve()),
        "color_space": "sRGB",
        "processing": "deterministic color processing; no AI",
    }
    with sidecar.open("x", encoding="utf-8") as stream:
        json.dump(payload, stream, indent=2)
    return output


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--photo-filter", choices=PHOTO_FILTER_NAMES, default="wes_anderson")
    parser.add_argument("--strength", type=float, default=1.0)
    args = parser.parse_args()
    try:
        result = grade_file(args.source, args.output, args.photo_filter, args.strength)
    except (ValueError, OSError) as exc:
        parser.exit(1, f"Grading failed: {exc}\n")
    print(f"Saved {result}")


if __name__ == "__main__":
    main()
