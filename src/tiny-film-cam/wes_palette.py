"""Deterministic sRGB color grading; no generated pixels, grain, or scene analysis."""
from __future__ import annotations

import colorsys
from functools import lru_cache


def _smooth(a: float, b: float, value: float) -> float:
    t = max(0.0, min(1.0, (value - a) / (b - a)))
    return t * t * (3.0 - 2.0 * t)


@lru_cache(maxsize=2)
def wes_lut(palette: str = "desert"):
    """Cache a small LUT; Pillow applies it in C with bounded per-pixel memory.

    Input/output are display-referred sRGB, not linear sensor data. Smooth hue
    masks keep gradients continuous. This is an inspired look, not a film LUT.
    """
    from PIL import ImageFilter

    if palette not in {"desert", "rose"}:
        raise ValueError(f"Unknown Wes palette: {palette}")

    def grade(red: float, green: float, blue: float):
        luminance = 0.2126 * red + 0.7152 * green + 0.0722 * blue
        hue, saturation, value = colorsys.rgb_to_hsv(red, green, blue)

        def hue_weight(center: float, width: float) -> float:
            distance = abs((hue - center + 0.5) % 1.0 - 0.5)
            return (1.0 - _smooth(0.0, width, distance)) * _smooth(
                0.04, 0.25, saturation
            )

        blues = hue_weight(0.61, 0.18)
        greens = hue_weight(0.34, 0.16)
        reds = hue_weight(0.98, 0.10)
        oranges = hue_weight(0.075, 0.12)
        if palette == "desert":
            # Dusty cyan blues, olive greens, restrained warm accents.
            hue -= 0.070 * blues + 0.045 * greens
            saturation *= 0.92 - 0.10 * greens
            saturation = min(1.0, saturation + 0.12 * blues + 0.065 * oranges)
        else:
            hue += -0.018 * blues + 0.028 * greens - 0.022 * reds
            saturation *= 0.80

        rgb = colorsys.hsv_to_rgb(hue % 1.0, saturation, value)
        adjusted_luma = sum(c * w for c, w in zip(rgb, (0.2126, 0.7152, 0.0722)))
        # Lift midtones without an exposure multiplier that clips bright walls.
        # Gentle endpoint compression retains detail in shadows and highlights.
        if palette == "desert":
            tone = 0.028 + 0.940 * luminance ** 0.72
            rgb = tuple(tone + (c - adjusted_luma) * 1.02 for c in rgb)
            mid = _smooth(0.015, 0.20, luminance) * (1.0 - _smooth(0.82, 1.0, luminance))
            high = _smooth(0.40, 0.95, luminance)
            warm = 1.0 - 0.85 * blues
            tint = (0.066 * mid * warm + 0.024 * high,
                    0.027 * mid + 0.009 * high,
                    -0.049 * mid * warm - 0.045 * high)
        else:
            tone = 0.022 + 0.953 * luminance ** 0.86
            rgb = tuple(tone + (c - adjusted_luma) * 0.98 for c in rgb)
            mid = _smooth(0.03, 0.23, luminance) * (1.0 - _smooth(0.78, 1.0, luminance))
            high = _smooth(0.35, 0.90, luminance)
            tint = (0.030 * mid + 0.012 * high, -0.014 * mid,
                    -0.002 * mid - 0.008 * high)
        return tuple(max(0.0, min(1.0, c + t)) for c, t in zip(rgb, tint))

    return ImageFilter.Color3DLUT.generate(33, grade)
