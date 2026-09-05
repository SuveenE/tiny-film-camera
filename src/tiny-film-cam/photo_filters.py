from __future__ import annotations

from pathlib import Path
from typing import Literal, cast

from filter_switch import filter_status_from_cache


PhotoFilterName = Literal["black_and_white", "normal", "cool", "wes_anderson", "wes_rose"]
DEFAULT_PHOTO_FILTER: PhotoFilterName = "normal"
PHOTO_FILTER_NAMES = ("black_and_white", "normal", "cool", "wes_anderson", "wes_rose")
PHOTO_FILTER_DETAILS: dict[PhotoFilterName, dict[str, object]] = {
    "wes_anderson": {
        "id": "wes_anderson",
        "label": "Wes · Desert pastels",
        "version": 1,
    },
    "wes_rose": {
        "id": "wes_rose",
        "label": "Wes · Rose pastels",
        "version": 1,
    },
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
        "version": 3,
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


def _smoothstep(edge0: float, edge1: float, value: float) -> float:
    position = max(0.0, min(1.0, (value - edge0) / (edge1 - edge0)))
    return position * position * (3.0 - 2.0 * position)


_COOL_FILTER_LUT = None


def _cool_filter_lut():
    """Return a cached, Pi-friendly cyan/teal and warm-cream 3D color LUT."""
    global _COOL_FILTER_LUT
    if _COOL_FILTER_LUT is not None:
        return _COOL_FILTER_LUT

    from PIL import ImageFilter

    def grade(red: float, green: float, blue: float):
        luminance = 0.2126 * red + 0.7152 * green + 0.0722 * blue

        # Filmic contrast and restrained saturation form the pastel base.
        red = (red - 0.48) * 1.14 + 0.48
        green = (green - 0.48) * 1.14 + 0.48
        blue = (blue - 0.48) * 1.14 + 0.48
        red = luminance + (red - luminance) * 1.08
        green = luminance + (green - luminance) * 1.08
        blue = luminance + (blue - luminance) * 1.08

        shadows = 1.0 - _smoothstep(0.16, 0.58, luminance)
        midtones = _smoothstep(0.10, 0.45, luminance) * (
            1.0 - _smoothstep(0.68, 0.96, luminance)
        )
        highlights = _smoothstep(0.46, 0.88, luminance)

        # Keep orange, tan, and skin-like colors warm while neutral surfaces,
        # greens, and blues receive the stronger Asteroid City-style cyan cast.
        warm_color = _smoothstep(0.035, 0.18, red - blue)
        cyan = midtones * (1.0 - 0.78 * warm_color)

        red += -0.060 * shadows - 0.042 * cyan + 0.110 * highlights
        green += 0.030 * shadows + 0.032 * cyan + 0.036 * highlights
        blue += 0.072 * shadows + 0.070 * cyan - 0.045 * highlights
        return red, green, blue

    _COOL_FILTER_LUT = ImageFilter.Color3DLUT.generate(17, grade)
    return _COOL_FILTER_LUT


def apply_photo_filter(image, name: PhotoFilterName):
    """Apply a lightweight, versioned photo look to a Pillow image."""
    if name not in PHOTO_FILTER_NAMES:
        raise ValueError(f"Unknown photo filter: {name}")
    if name == "normal":
        return image

    from PIL import ImageEnhance, ImageOps

    rgb_image = image if image.mode == "RGB" else image.convert("RGB")
    if name == "black_and_white":
        grayscale = ImageOps.grayscale(rgb_image)
        return ImageEnhance.Contrast(grayscale).enhance(1.08).convert("RGB")

    if name in {"wes_anderson", "wes_rose"}:
        from wes_palette import wes_lut

        return rgb_image.filter(wes_lut("rose" if name == "wes_rose" else "desert"))

    return rgb_image.filter(_cool_filter_lut())
