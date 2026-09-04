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
        "version": 1,
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


def apply_photo_filter(image, name: PhotoFilterName):
    """Apply a lightweight, versioned photo look to a Pillow image."""
    if name == "normal":
        return image

    from PIL import Image, ImageEnhance, ImageOps

    rgb_image = image.convert("RGB")
    if name == "black_and_white":
        grayscale = ImageOps.grayscale(rgb_image)
        return ImageEnhance.Contrast(grayscale).enhance(1.08).convert("RGB")

    muted = ImageEnhance.Color(rgb_image).enhance(0.88)
    red, green, blue = muted.split()
    red = red.point(_scaled_lut(0.93))
    blue = blue.point(_scaled_lut(1.10))
    return Image.merge("RGB", (red, green, blue))
