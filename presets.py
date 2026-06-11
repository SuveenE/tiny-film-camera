from PIL import Image, ImageEnhance, ImageFilter
import numpy as np
import sys
from pathlib import Path

_VIGNETTE_CACHE = {}


def get_vignette_mask(width, height, strength=0.12):
    key = (width, height, strength)
    if key in _VIGNETTE_CACHE:
        return _VIGNETTE_CACHE[key]

    y, x = np.ogrid[:height, :width]
    cx, cy = width / 2.0, height / 2.0
    dx = (x - cx) / cx
    dy = (y - cy) / cy
    dist2 = dx * dx + dy * dy

    mask = 1.0 - strength * np.clip(dist2, 0, 1.5)
    mask = np.clip(mask, 0.0, 1.0)
    mask_u8 = (mask * 255).astype(np.uint8)
    _VIGNETTE_CACHE[key] = mask_u8
    return mask_u8


def add_grain(arr, amount=6, downscale=2):
    h, w = arr.shape[:2]
    gh, gw = max(1, h // downscale), max(1, w // downscale)

    grain_small = np.random.randint(-amount, amount + 1, size=(gh, gw), dtype=np.int16)
    grain_img = Image.fromarray((grain_small + 128).astype(np.uint8), mode="L")
    grain_img = grain_img.resize((w, h), Image.BILINEAR)
    grain = np.asarray(grain_img, dtype=np.int16) - 128

    r = arr[:, :, 0].astype(np.uint16)
    g = arr[:, :, 1].astype(np.uint16)
    b = arr[:, :, 2].astype(np.uint16)
    lum = (77 * r + 150 * g + 29 * b) >> 8

    weight = 255 - lum
    grain_weighted = (grain * (90 + weight)) >> 8

    out = arr.astype(np.int16)
    out[:, :, 0] += grain_weighted
    out[:, :, 1] += grain_weighted
    out[:, :, 2] += grain_weighted
    return np.clip(out, 0, 255).astype(np.uint8)


def apply_vignette(arr, strength=0.12):
    h, w = arr.shape[:2]
    mask = get_vignette_mask(w, h, strength).astype(np.uint16)
    out = arr.copy()
    out[:, :, 0] = ((out[:, :, 0].astype(np.uint16) * mask) >> 8).astype(np.uint8)
    out[:, :, 1] = ((out[:, :, 1].astype(np.uint16) * mask) >> 8).astype(np.uint8)
    out[:, :, 2] = ((out[:, :, 2].astype(np.uint16) * mask) >> 8).astype(np.uint8)
    return out


def channel_shift(arr, r_mult, g_mult, b_mult):
    r = arr[:, :, 0].astype(np.uint16)
    arr[:, :, 0] = np.minimum(255, (r * r_mult) // 100).astype(np.uint8)
    g = arr[:, :, 1].astype(np.uint16)
    arr[:, :, 1] = np.minimum(255, (g * g_mult) // 100).astype(np.uint8)
    b = arr[:, :, 2].astype(np.uint16)
    arr[:, :, 2] = ((b * b_mult) // 100).astype(np.uint8)


def shadow_lift(arr, lift=10, compress=94):
    out = arr.astype(np.uint16)
    out = (out * compress) // 100 + lift
    np.clip(out, 0, 255, out=out)
    return out.astype(np.uint8)


PRESETS = {
    "warm_vintage": {
        "blur": 0.4,
        "contrast": 0.82,
        "saturation": 0.85,
        "brightness": 1.03,
        "tint_color": (230, 190, 80),
        "tint_alpha": 0.10,
        "r_mult": 108,
        "g_mult": 101,
        "b_mult": 88,
        "shadow_lift": 14,
        "shadow_compress": 92,
        "grain_amount": 8,
        "grain_downscale": 2,
        "vignette_strength": 0.15,
    },
    "cool_muted": {
        "blur": 0.2,
        "contrast": 0.90,
        "saturation": 0.78,
        "brightness": 0.99,
        "tint_color": (140, 180, 210),
        "tint_alpha": 0.07,
        "r_mult": 96,
        "g_mult": 100,
        "b_mult": 106,
        "shadow_lift": 12,
        "shadow_compress": 93,
        "grain_amount": 5,
        "grain_downscale": 2,
        "vignette_strength": 0.12,
    },
    "punchy_film": {
        "blur": 0.0,
        "contrast": 1.05,
        "saturation": 1.10,
        "brightness": 1.01,
        "tint_color": (200, 180, 120),
        "tint_alpha": 0.05,
        "r_mult": 103,
        "g_mult": 101,
        "b_mult": 95,
        "shadow_lift": 6,
        "shadow_compress": 96,
        "grain_amount": 4,
        "grain_downscale": 3,
        "vignette_strength": 0.08,
    },
    "faded_pastel": {
        "blur": 0.3,
        "contrast": 0.78,
        "saturation": 0.75,
        "brightness": 1.05,
        "tint_color": (210, 200, 180),
        "tint_alpha": 0.12,
        "r_mult": 102,
        "g_mult": 102,
        "b_mult": 96,
        "shadow_lift": 20,
        "shadow_compress": 88,
        "grain_amount": 5,
        "grain_downscale": 2,
        "vignette_strength": 0.06,
    },
}


def apply_preset(input_path, output_path, preset_name, resize_long_edge=None):
    p = PRESETS[preset_name]
    img = Image.open(input_path).convert("RGB")

    if resize_long_edge is not None:
        w, h = img.size
        long_edge = max(w, h)
        if long_edge > resize_long_edge:
            scale = resize_long_edge / long_edge
            img = img.resize((int(w * scale), int(h * scale)), Image.LANCZOS)

    if p["blur"] > 0:
        img = img.filter(ImageFilter.GaussianBlur(radius=p["blur"]))
    img = ImageEnhance.Contrast(img).enhance(p["contrast"])
    img = ImageEnhance.Color(img).enhance(p["saturation"])
    img = ImageEnhance.Brightness(img).enhance(p["brightness"])

    tint = Image.new("RGB", img.size, p["tint_color"])
    img = Image.blend(img, tint, alpha=p["tint_alpha"])

    arr = np.asarray(img, dtype=np.uint8).copy()

    channel_shift(arr, p["r_mult"], p["g_mult"], p["b_mult"])
    arr = shadow_lift(arr, lift=p["shadow_lift"], compress=p["shadow_compress"])
    arr = add_grain(arr, amount=p["grain_amount"], downscale=p["grain_downscale"])
    arr = apply_vignette(arr, strength=p["vignette_strength"])

    final = Image.fromarray(arr, mode="RGB")
    final.save(output_path, quality=92, optimize=True)
    print(f"[{preset_name}] Saved to {output_path}")


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print(f"Usage: python3 presets.py <input.jpg> <output_dir> [max_long_edge]")
        print(f"\nAvailable presets: {', '.join(PRESETS.keys())}")
        print("\nRuns all presets and saves each to output_dir/preset_name.jpg")
        sys.exit(1)

    input_path = Path(sys.argv[1])
    output_dir = Path(sys.argv[2])
    output_dir.mkdir(parents=True, exist_ok=True)

    resize_long_edge = None
    if len(sys.argv) >= 4:
        resize_long_edge = int(sys.argv[3])

    for name in PRESETS:
        out = output_dir / f"{name}.jpg"
        apply_preset(input_path, out, name, resize_long_edge)

    print(f"\nDone! Compare outputs in {output_dir}/")
