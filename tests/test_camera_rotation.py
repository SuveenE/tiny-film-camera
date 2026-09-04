from __future__ import annotations

from contextlib import nullcontext
import importlib.util
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
from types import ModuleType
import unittest
from unittest.mock import MagicMock, patch

import numpy as np
from PIL import Image


CAMERA_PATH = (
    Path(__file__).resolve().parents[1] / "src" / "tiny-film-cam" / "camera.py"
)


def load_camera_module():
    source_root = str(CAMERA_PATH.parent)
    if source_root not in sys.path:
        sys.path.insert(0, source_root)
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
    def test_video_settings_default_to_15_fps(self) -> None:
        with patch.dict("os.environ", {}, clear=True):
            settings = camera.video_settings_from_env(Path.cwd())

        self.assertEqual(camera.DEFAULT_VIDEO_FPS, 15)
        self.assertEqual(camera.VideoSettings().fps, 15)
        self.assertEqual(settings.fps, 15)

    def test_video_recording_preserves_timestamps_and_uses_yuv420(self) -> None:
        picam2 = MagicMock()
        encoder = object()
        output = object()
        h264_encoder = MagicMock(return_value=encoder)
        pyav_output = MagicMock(return_value=output)
        picamera2_module = ModuleType("picamera2")
        picamera2_module.Picamera2 = object  # type: ignore[attr-defined]
        encoders_module = ModuleType("picamera2.encoders")
        encoders_module.H264Encoder = h264_encoder  # type: ignore[attr-defined]
        outputs_module = ModuleType("picamera2.outputs")
        outputs_module.PyavOutput = pyav_output  # type: ignore[attr-defined]

        with TemporaryDirectory() as temporary_directory:
            output_path = Path(temporary_directory) / "clip.mp4"
            settings = camera.VideoSettings(
                output_dir=Path(temporary_directory),
                filename=str(output_path),
                duration_seconds=10,
                warmup_seconds=0,
                rotation=0,
            )
            with (
                patch.dict(
                    sys.modules,
                    {
                        "picamera2": picamera2_module,
                        "picamera2.encoders": encoders_module,
                        "picamera2.outputs": outputs_module,
                    },
                ),
                patch.object(
                    camera,
                    "_locked_camera",
                    return_value=nullcontext(),
                ),
                patch.object(camera, "_open_camera", return_value=picam2),
                patch.object(camera, "_video_transform", return_value=None),
                patch.object(camera, "_finalize_video") as finalize_video,
                patch("time.sleep") as sleep,
            ):
                saved_path = camera.record_video(settings)

        self.assertEqual(saved_path, output_path)
        h264_encoder.assert_called_once_with()
        recording_path = output_path.with_name(f".{output_path.name}.recording.mkv")
        pyav_output.assert_called_once_with(str(recording_path))
        finalize_video.assert_called_once_with(recording_path, output_path, 15, None)
        picam2.create_video_configuration.assert_called_once_with(
            main={"size": (1280, 720), "format": "YUV420"},
            controls={
                "Sharpness": 0.3,
                "Contrast": 0.85,
                "Saturation": 0.9,
                "ExposureValue": -0.3,
                "FrameRate": 15.0,
            },
            transform=None,
        )
        picam2.start_recording.assert_called_once_with(encoder, output)
        sleep.assert_called_once_with(10)

    def test_video_finalization_transcodes_safari_compatible_h264(self) -> None:
        with TemporaryDirectory() as temporary_directory:
            recording_path = Path(temporary_directory) / "recording.mkv"
            output_path = Path(temporary_directory) / "clip.mp4"
            recording_path.write_bytes(b"matroska")

            def fake_run(command, **kwargs):
                second_map = command.index("-map", command.index("-map") + 1)
                Path(command[second_map - 1]).write_bytes(b"mp4")
                Path(command[-1]).write_bytes(b"jpeg")
                return None

            with patch.object(camera.subprocess, "run", side_effect=fake_run) as run:
                camera._finalize_video(recording_path, output_path, 15)

            command = run.call_args.args[0]
            self.assertEqual(output_path.read_bytes(), b"mp4")
            self.assertEqual(
                camera.video_poster_path(output_path).read_bytes(), b"jpeg"
            )
            self.assertNotIn("copy", command)
            self.assertIn("libx264", command)
            self.assertIn("ultrafast", command)
            self.assertIn("baseline", command)
            self.assertIn("3.1", command)
            video_filter = command[command.index("-vf") + 1]
            self.assertIn("fps=15", video_filter)
            self.assertIn("setparams=range=limited", video_filter)
            self.assertIn("yuv420p", command)
            self.assertIn("bt709", command)
            self.assertIn("avc1", command)
            self.assertIn("+faststart", command)
            self.assertIn("image2", command)
            self.assertEqual(
                run.call_args.kwargs,
                {"check": True, "capture_output": True, "text": True},
            )

    def test_video_finalization_preserves_requested_bitrate(self) -> None:
        with TemporaryDirectory() as temporary_directory:
            recording_path = Path(temporary_directory) / "recording.mkv"
            output_path = Path(temporary_directory) / "clip.mp4"
            recording_path.write_bytes(b"matroska")

            def fake_run(command, **kwargs):
                second_map = command.index("-map", command.index("-map") + 1)
                Path(command[second_map - 1]).write_bytes(b"mp4")
                Path(command[-1]).write_bytes(b"jpeg")
                return None

            with patch.object(camera.subprocess, "run", side_effect=fake_run) as run:
                camera._finalize_video(recording_path, output_path, 15, 4_000_000)

            command = run.call_args.args[0]
            bitrate_option = command.index("-b:v")
            self.assertEqual(command[bitrate_option + 1], "4000000")

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
        self.assertEqual(settings.exposure_value, -0.3)
        self.assertEqual(settings.awb_mode, "auto")
        self.assertTrue(settings.awb_lock)
        self.assertEqual(settings.photo_filter, "normal")

    def test_capture_settings_reads_film_source_controls_from_env(self) -> None:
        with patch.dict(
            "os.environ",
            {
                "TINY_FILM_CAPTURE_EV": "-0.7",
                "TINY_FILM_CAPTURE_BRACKETS": "0,-0.7,-1.0",
                "TINY_FILM_CAPTURE_BRACKET_SETTLE_SECONDS": "0.4",
                "TINY_FILM_CAPTURE_AWB_MODE": "cloudy",
                "TINY_FILM_CAPTURE_AWB_LOCK": "1",
                "TINY_FILM_CAPTURE_FILTER": "cool",
            },
            clear=True,
        ):
            settings = camera.capture_settings_from_env(Path.cwd())

        self.assertEqual(settings.exposure_value, -0.7)
        self.assertEqual(settings.exposure_brackets, (0.0, -0.7, -1.0))
        self.assertEqual(settings.bracket_settle_seconds, 0.4)
        self.assertEqual(settings.awb_mode, "cloudy")
        self.assertTrue(settings.awb_lock)
        self.assertEqual(settings.photo_filter, "cool")

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
        picam2.capture_array.side_effect = (
            lambda stream: events.append("captured") or object()
        )
        image = MagicMock()
        image.save.side_effect = lambda *args, **kwargs: events.append("saved")

        with (
            patch.object(
                camera,
                "_image_from_picamera_frame",
                side_effect=lambda frame: events.append("processed") or image,
            ),
            patch.object(camera, "_rotate_image", return_value=image),
            patch.object(
                camera,
                "apply_photo_filter",
                side_effect=lambda source, name: events.append("filtered") or image,
            ),
            patch.object(
                camera,
                "write_photo_filter_metadata",
                side_effect=lambda path, name: events.append("metadata"),
            ),
        ):
            camera._capture_and_save_image(
                picam2,
                camera.CaptureSettings(),
                Path("photo.jpg"),
                lambda: events.append("sound"),
            )

        self.assertEqual(
            events,
            ["captured", "sound", "processed", "filtered", "saved", "metadata"],
        )

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
