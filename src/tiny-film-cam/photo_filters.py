from __future__ import annotations

from pathlib import Path
from typing import Literal, cast

from filter_switch import filter_status_from_cache


PhotoFilterName = Literal["black_and_white", "normal", "cool"]
DEFAULT_PHOTO_FILTER: PhotoFilterName = "normal"
PHOTO_FILTER_NAMES = ("black_and_white", "normal", "cool")
PHOTO_FILTER_DETAILS: dict[PhotoFilterName, dict[str, object]] = {
    "black_and_white": {
        "id": "black_and_white",
        "label": "Black & white",
        "version": 1,
    },
    "normal": {
        "id": "normal",
        "label": "Normal",
        "version": 1,
    },
    "cool": {
        "id": "cool",
        "label": "Cool",
        "version": 2,
    },
}


def normalize_photo_filter(value: object) -> PhotoFilterName:
    if isinstance(value, str) and value in PHOTO_FILTER_NAMES:
        return cast(PhotoFilterName, value)
    return DEFAULT_PHOTO_FILTER


def photo_filter_details(name: PhotoFilterName) -> dict[str, object]:
    return dict(PHOTO_FILTER_DETAILS[name])


def photo_filter_status_from_cache(project_root: Path) -> dict[str, object]:
    status = filter_status_from_cache(project_root)
    requested = status.get("selection")
    valid_selection = isinstance(requested, str) and requested in PHOTO_FILTER_NAMES
    can_use_selection = (
        bool(status.get("ok")) and not status.get("stale") and valid_selection
    )
    active = normalize_photo_filter(requested if can_use_selection else None)
    status["requested_selection"] = requested
    status["active_filter"] = photo_filter_details(active)
    status["using_fallback"] = not can_use_selection
    if status.get("ok") and not valid_selection:
        status["error"] = f"Unknown photo filter selection: {requested!r}"
    return status


def selected_photo_filter_from_cache(project_root: Path) -> PhotoFilterName:
    status = photo_filter_status_from_cache(project_root)
    active_filter = status["active_filter"]
    assert isinstance(active_filter, dict)
    return normalize_photo_filter(active_filter.get("id"))


def _scaled_lut(multiplier: float) -> list[int]:
    return [max(0, min(255, round(value * multiplier))) for value in range(256)]


def _mask_lut(start: int, end: int, *, invert: bool = False) -> list[int]:
    """Build a smooth luminance mask without requiring NumPy on the camera."""
    values = []
    for value in range(256):
        position = max(0.0, min(1.0, (value - start) / (end - start)))
        smooth = position * position * (3.0 - 2.0 * position)
        if invert:
            smooth = 1.0 - smooth
        values.append(round(smooth * 255))
    return values


def _scaled_mask(mask, amount: float):
    return mask.point(_scaled_lut(amount))


def apply_photo_filter(image, name: PhotoFilterName):
    """Apply a lightweight, versioned photo look to a Pillow image."""
    if name == "normal":
        return image

    from PIL import Image, ImageChops, ImageEnhance, ImageFilter, ImageOps

    rgb_image = image.convert("RGB")
    if name == "black_and_white":
        grayscale = ImageOps.grayscale(rgb_image)
        return ImageEnhance.Contrast(grayscale).enhance(1.08).convert("RGB")

    # A portable Pillow version of the golden-hour teal-and-amber grade. Keep
    # this filter dependency-light because it runs directly on the camera Pi.
    graded = ImageEnhance.Contrast(rgb_image).enhance(1.18)
    graded = graded.point(_scaled_lut(1.0 / 0.96) * 3)
    graded = ImageEnhance.Color(graded).enhance(1.14)

    luminance = ImageOps.grayscale(graded)
    shadow_mask = luminance.point(_mask_lut(36, 148, invert=True))
    highlight_mask = luminance.point(_mask_lut(96, 232))

    red, green, blue = graded.split()

    # Teal shadows.
    red = ImageChops.subtract(red, _scaled_mask(shadow_mask, 0.050))
    green = ImageChops.add(green, _scaled_mask(shadow_mask, 0.020))
    blue = ImageChops.add(blue, _scaled_mask(shadow_mask, 0.042))

    # Amber/golden highlights.
    red = ImageChops.add(red, _scaled_mask(highlight_mask, 0.100))
    green = ImageChops.add(green, _scaled_mask(highlight_mask, 0.044))
    blue = ImageChops.subtract(blue, _scaled_mask(highlight_mask, 0.050))

    graded = Image.merge("RGB", (red, green, blue))
    return graded.filter(ImageFilter.UnsharpMask(radius=1.15, percent=32, threshold=3))
