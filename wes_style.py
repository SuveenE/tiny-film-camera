from PIL import Image, ImageEnhance, ImageFilter
import numpy as np
import sys
from pathlib import Path

# Cache vignette masks by resolution so they are not recomputed every time
_VIGNETTE_CACHE = {}


def get_vignette_mask(width, height, strength=0.12):
    """
    Returns a uint8 mask in range 0..255.
    Cached by (width, height, strength).
    """
    key = (width, height, strength)
    if key in _VIGNETTE_CACHE:
        return _VIGNETTE_CACHE[key]

    y, x = np.ogrid[:height, :width]
    cx = width / 2.0
    cy = height / 2.0

    dx = (x - cx) / cx
    dy = (y - cy) / cy
    dist2 = dx * dx + dy * dy

    # Simple smooth radial falloff
    mask = 1.0 - strength * np.clip(dist2, 0, 1.5)
    mask = np.clip(mask, 0.0, 1.0)

    mask_u8 = (mask * 255).astype(np.uint8)
    _VIGNETTE_CACHE[key] = mask_u8
    return mask_u8


def add_grain_single_channel(arr, amount=6, downscale=2):
    """
    Add subtle single-channel grain to RGB image.
    - arr: uint8 RGB numpy array
    - amount: noise strength in pixel values
    - downscale: generate lower-res grain and scale up to save memory
    """
    h, w = arr.shape[:2]

    gh = max(1, h // downscale)
    gw = max(1, w // downscale)

    # Generate low-res grain as int16 so we can add/subtract safely
    grain_small = np.random.randint(-amount, amount + 1, size=(gh, gw), dtype=np.int16)

    # Upscale grain back to image size
    grain_img = Image.fromarray((grain_small + 128).astype(np.uint8), mode="L")
    grain_img = grain_img.resize((w, h), Image.BILINEAR)
    grain = np.asarray(grain_img, dtype=np.int16) - 128

    # Compute luminance approximately using integer math
    r = arr[:, :, 0].astype(np.uint16)
    g = arr[:, :, 1].astype(np.uint16)
    b = arr[:, :, 2].astype(np.uint16)
    lum = (77 * r + 150 * g + 29 * b) >> 8  # approx 0.299R + 0.587G + 0.114B

    # More grain in darker areas, less in highlights
    # weight ranges roughly 0.35 .. 1.0
    weight = 255 - lum
    grain_weighted = (grain * (90 + weight)) >> 8

    out = arr.astype(np.int16)
    out[:, :, 0] += grain_weighted
    out[:, :, 1] += grain_weighted
    out[:, :, 2] += grain_weighted

    return np.clip(out, 0, 255).astype(np.uint8)


def apply_vignette(arr, strength=0.12):
    """
    Apply vignette using uint8 mask and integer arithmetic.
    """
    h, w = arr.shape[:2]
    mask = get_vignette_mask(w, h, strength).astype(np.uint16)

    out = arr.copy()
    out[:, :, 0] = ((out[:, :, 0].astype(np.uint16) * mask) >> 8).astype(np.uint8)
    out[:, :, 1] = ((out[:, :, 1].astype(np.uint16) * mask) >> 8).astype(np.uint8)
    out[:, :, 2] = ((out[:, :, 2].astype(np.uint16) * mask) >> 8).astype(np.uint8)
    return out


def apply_channel_shift_inplace(arr):
    """
    Warm color shift using integer math, one channel at a time.
    Avoids big float arrays.
    """
    # Red up slightly
    r = arr[:, :, 0].astype(np.uint16)
    arr[:, :, 0] = np.minimum(255, (r * 106) // 100).astype(np.uint8)

    # Green up a little
    g = arr[:, :, 1].astype(np.uint16)
    arr[:, :, 1] = np.minimum(255, (g * 102) // 100).astype(np.uint8)

    # Blue down slightly
    b = arr[:, :, 2].astype(np.uint16)
    arr[:, :, 2] = ((b * 92) // 100).astype(np.uint8)


def apply_shadow_lift_inplace(arr, lift=10):
    """
    Slightly lift blacks / fade shadows.
    """
    out = arr.astype(np.uint16)
    out = (out * 94) // 100 + lift
    np.clip(out, 0, 255, out=out)
    return out.astype(np.uint8)


def apply_wes_anderson_style(input_path, output_path, resize_long_edge=None):
    img = Image.open(input_path).convert("RGB")

    # Optional resize for speed/memory
    if resize_long_edge is not None:
        w, h = img.size
        long_edge = max(w, h)
        if long_edge > resize_long_edge:
            scale = resize_long_edge / long_edge
            new_size = (int(w * scale), int(h * scale))
            img = img.resize(new_size, Image.LANCZOS)

    # Use Pillow ops first (efficient and simple)
    img = img.filter(ImageFilter.GaussianBlur(radius=0.25))
    img = ImageEnhance.Contrast(img).enhance(0.87)
    img = ImageEnhance.Color(img).enhance(0.92)
    img = ImageEnhance.Brightness(img).enhance(1.02)

    # Warm tint with blend (cheap, easy)
    tint = Image.new("RGB", img.size, (220, 200, 100))
    img = Image.blend(img, tint, alpha=0.08)

    # Convert once to numpy and do remaining ops
    arr = np.asarray(img, dtype=np.uint8).copy()

    apply_channel_shift_inplace(arr)
    arr = apply_shadow_lift_inplace(arr, lift=10)
    arr = add_grain_single_channel(arr, amount=6, downscale=2)
    arr = apply_vignette(arr, strength=0.10)

    final = Image.fromarray(arr, mode="RGB")
    final.save(output_path, quality=92, optimize=True)

    print(f"Saved styled image to {output_path}")


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python3 wes_style_fast.py input.jpg output.jpg [max_long_edge]")
        sys.exit(1)

    input_path = Path(sys.argv[1])
    output_path = Path(sys.argv[2])

    resize_long_edge = None
    if len(sys.argv) >= 4:
        resize_long_edge = int(sys.argv[3])

    apply_wes_anderson_style(input_path, output_path, resize_long_edge)
