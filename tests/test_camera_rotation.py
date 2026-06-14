from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path

from PIL import Image


CAMERA_PATH = Path(__file__).resolve().parents[1] / "src" / "tiny-film-cam" / "camera.py"


def load_camera_module():
    spec = importlib.util.spec_from_file_location("tiny_film_camera", CAMERA_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load camera module from {CAMERA_PATH}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


camera = load_camera_module()


def marker_image() -> Image.Image:
    image = Image.new("RGB", (2, 3))
    pixels = {
        (0, 0): (255, 0, 0),
        (1, 0): (0, 255, 0),
        (0, 1): (0, 0, 255),
        (1, 1): (255, 255, 0),
        (0, 2): (255, 0, 255),
        (1, 2): (0, 255, 255),
    }
    for point, color in pixels.items():
        image.putpixel(point, color)
    return image


class CameraRotationTest(unittest.TestCase):
    def test_rotation_90_is_clockwise(self) -> None:
        rotated = camera._rotate_image(marker_image(), 90)

        self.assertEqual(rotated.size, (3, 2))
        self.assertEqual(rotated.getpixel((2, 0)), (255, 0, 0))
        self.assertEqual(rotated.getpixel((2, 1)), (0, 255, 0))

    def test_rotation_270_is_counterclockwise(self) -> None:
        rotated = camera._rotate_image(marker_image(), 270)

        self.assertEqual(rotated.size, (3, 2))
        self.assertEqual(rotated.getpixel((0, 0)), (0, 255, 0))
        self.assertEqual(rotated.getpixel((0, 1)), (255, 0, 0))

    def test_rotation_180_flips_pixels(self) -> None:
        rotated = camera._rotate_image(marker_image(), 180)

        self.assertEqual(rotated.size, (2, 3))
        self.assertEqual(rotated.getpixel((1, 2)), (255, 0, 0))
        self.assertEqual(rotated.getpixel((0, 0)), (0, 255, 255))


if __name__ == "__main__":
    unittest.main()
