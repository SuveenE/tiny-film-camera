from __future__ import annotations

from pathlib import Path
from typing import Literal, cast

from filter_switch import filter_status_from_cache


PhotoFilterName = Literal["black_and_white", "normal", "cold", "vivid_50"]
DEFAULT_PHOTO_FILTER: PhotoFilterName = "normal"
PHOTO_FILTER_NAMES = ("black_and_white", "normal", "cold", "vivid_50")
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
    "cold": {
        "id": "cold",
        "label": "Cold",
        "version": 1,
    },
    "vivid_50": {
        "id": "vivid_50",
        "label": "Vivid 50",
        "version": 1,
        "intensity_percent": 50,
        "approximation": True,
    },
}

VIVID_50_BLEND = 0.5
VIVID_FULL_CONTRAST = 1.22
VIVID_FULL_SATURATION = 1.18
VIVID_FULL_VIBRANCE = 0.35
VIVID_FULL_TONE_CURVE = 0.20


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


def _vibrance_lut(amount: float) -> list[int]:
    """Boost muted colours more than colours already near full saturation."""
    return [
        max(
            0,
            min(
                255,
                round(value + amount * value * (1.0 - value / 255.0)),
            ),
        )
        for value in range(256)
    ]


def _s_curve_lut(amount: float) -> list[int]:
    """Return a gentle, endpoint-preserving contrast curve."""
    lut = []
    for value in range(256):
        normalized = value / 255.0
        smoothstep = normalized * normalized * (3.0 - 2.0 * normalized)
        curved = normalized + amount * (smoothstep - normalized)
        lut.append(max(0, min(255, round(curved * 255.0))))
    return lut


def _apply_rgb_lut(image, lut: list[int]):
    from PIL import Image

    red, green, blue = image.split()
    return Image.merge("RGB", (red.point(lut), green.point(lut), blue.point(lut)))


def _apply_vivid_50(rgb_image):
    """Approximate Apple's Vivid filter, blended to its 50% slider position."""
    from PIL import Image, ImageEnhance

    vivid = ImageEnhance.Contrast(rgb_image).enhance(VIVID_FULL_CONTRAST)
    vivid = _apply_rgb_lut(vivid, _s_curve_lut(VIVID_FULL_TONE_CURVE))

    hue, saturation, value = vivid.convert("HSV").split()
    saturation = saturation.point(_vibrance_lut(VIVID_FULL_VIBRANCE))
    vivid = Image.merge("HSV", (hue, saturation, value)).convert("RGB")
    vivid = ImageEnhance.Color(vivid).enhance(VIVID_FULL_SATURATION)

    return Image.blend(rgb_image, vivid, VIVID_50_BLEND)


def apply_photo_filter(image, name: PhotoFilterName):
    """Apply a lightweight, versioned photo look to a Pillow image."""
    if name == "normal":
        return image

    from PIL import Image, ImageEnhance, ImageOps

    rgb_image = image.convert("RGB")
    if name == "black_and_white":
        grayscale = ImageOps.grayscale(rgb_image)
        return ImageEnhance.Contrast(grayscale).enhance(1.08).convert("RGB")

    if name == "vivid_50":
        return _apply_vivid_50(rgb_image)

    muted = ImageEnhance.Color(rgb_image).enhance(0.88)
    red, green, blue = muted.split()
    red = red.point(_scaled_lut(0.93))
    blue = blue.point(_scaled_lut(1.10))
    return Image.merge("RGB", (red, green, blue))
