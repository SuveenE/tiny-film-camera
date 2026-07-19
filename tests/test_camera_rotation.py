from __future__ import annotations

import importlib.util
from pathlib import Path
import sys
import unittest
from unittest.mock import MagicMock, patch

import numpy as np
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
    def test_video_settings_default_to_24_fps(self) -> None:
        with patch.dict("os.environ", {}, clear=True):
            settings = camera.video_settings_from_env(Path.cwd())

        self.assertEqual(camera.DEFAULT_VIDEO_FPS, 24)
        self.assertEqual(camera.VideoSettings().fps, 24)
        self.assertEqual(settings.fps, 24)

    def test_capture_settings_default_rotation_is_180(self) -> None:
        with patch.dict("os.environ", {}, clear=True):
            settings = camera.capture_settings_from_env(Path.cwd())

        self.assertEqual(settings.rotation, 180)

    def test_capture_settings_default_film_source_controls(self) -> None:
        with patch.dict("os.environ", {}, clear=True):
            settings = camera.capture_settings_from_env(Path.cwd())

        self.assertEqual(settings.sharpness, 0.3)
        self.assertEqual(settings.contrast, 0.85)
        self.assertEqual(settings.saturation, 0.9)
        self.assertEqual(settings.exposure_value, -0.7)
        self.assertEqual(settings.awb_mode, "daylight")
        self.assertFalse(settings.awb_lock)

    def test_capture_settings_reads_film_source_controls_from_env(self) -> None:
        with patch.dict(
            "os.environ",
            {
                "TINY_FILM_CAPTURE_EV": "-0.7",
                "TINY_FILM_CAPTURE_BRACKETS": "0,-0.7,-1.0",
                "TINY_FILM_CAPTURE_BRACKET_SETTLE_SECONDS": "0.4",
                "TINY_FILM_CAPTURE_AWB_MODE": "cloudy",
                "TINY_FILM_CAPTURE_AWB_LOCK": "1",
            },
            clear=True,
        ):
            settings = camera.capture_settings_from_env(Path.cwd())

        self.assertEqual(settings.exposure_value, -0.7)
        self.assertEqual(settings.exposure_brackets, (0.0, -0.7, -1.0))
        self.assertEqual(settings.bracket_settle_seconds, 0.4)
        self.assertEqual(settings.awb_mode, "cloudy")
        self.assertTrue(settings.awb_lock)

    def test_bracket_output_paths_include_ev_suffixes(self) -> None:
        settings = camera.CaptureSettings(
            filename="photo.jpg",
            exposure_brackets=(0.0, -0.7, -1.0),
        )

        paths = camera._output_paths(settings)

        self.assertEqual(
            [path.name for path in paths],
            ["photo_ev+0p0.jpg", "photo_ev-0p7.jpg", "photo_ev-1p0.jpg"],
        )

    def test_camera_controls_include_exposure_value(self) -> None:
        settings = camera.CaptureSettings(exposure_value=-0.7)

        controls = camera._camera_controls(settings)

        self.assertEqual(controls["ExposureValue"], -0.7)

    def test_picamera_frame_is_converted_from_bgr_to_rgb(self) -> None:
        frame = np.array(
            [
                [
                    [0, 0, 255],
                    [255, 0, 0],
                ]
            ],
            dtype=np.uint8,
        )

        image = camera._image_from_picamera_frame(frame)

        self.assertEqual(image.mode, "RGB")
        self.assertEqual(image.getpixel((0, 0)), (255, 0, 0))
        self.assertEqual(image.getpixel((1, 0)), (0, 0, 255))

    def test_capture_callback_runs_before_image_processing_and_save(self) -> None:
        events: list[str] = []
        picam2 = MagicMock()
        picam2.capture_array.side_effect = lambda stream: events.append(
            "captured"
        ) or object()
        image = MagicMock()
        image.save.side_effect = lambda *args, **kwargs: events.append("saved")

        with (
            patch.object(
                camera,
                "_image_from_picamera_frame",
                side_effect=lambda frame: events.append("processed") or image,
            ),
            patch.object(camera, "_rotate_image", return_value=image),
        ):
            camera._capture_and_save_image(
                picam2,
                camera.CaptureSettings(),
                Path("photo.jpg"),
                lambda: events.append("sound"),
            )

        self.assertEqual(events, ["captured", "sound", "processed", "saved"])

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
