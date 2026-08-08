from __future__ import annotations

import importlib.util
import os
from pathlib import Path
import sys
import types
import unittest
from unittest.mock import MagicMock, patch


SOURCE_ROOT = Path(__file__).resolve().parents[1] / "src" / "tiny-film-cam"
SHUTTER_DAEMON_PATH = SOURCE_ROOT / "shutter_daemon.py"


def load_shutter_daemon():
    source_root = str(SOURCE_ROOT)
    if source_root not in sys.path:
        sys.path.insert(0, source_root)
    spec = importlib.util.spec_from_file_location(
        "tiny_film_shutter_daemon", SHUTTER_DAEMON_PATH
    )
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load shutter daemon from {SHUTTER_DAEMON_PATH}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


shutter_daemon = load_shutter_daemon()


class FakeButton:
    instances: list["FakeButton"] = []

    def __init__(self, pin: int, **kwargs: object) -> None:
        self.pin = pin
        self.kwargs = kwargs
        self.when_pressed = None
        self.closed = False
        self.instances.append(self)

    def close(self) -> None:
        self.closed = True


class StopImmediatelyEvent:
    def set(self) -> None:
        return None

    def wait(self, timeout: float) -> bool:
        return True


class ShutterDaemonTest(unittest.TestCase):
    def setUp(self) -> None:
        FakeButton.instances.clear()

    def test_default_and_configured_button_pins(self) -> None:
        with (
            patch.dict(os.environ, {}, clear=True),
            patch.object(sys, "argv", ["shutter_daemon.py"]),
        ):
            defaults = shutter_daemon.parse_args()

        self.assertEqual(defaults.photo_pin, 5)
        self.assertEqual(defaults.video_pin, 17)

        with (
            patch.dict(
                os.environ,
                {
                    "TINY_FILM_BUTTON_PIN": "5",
                    "TINY_FILM_PHOTO_BUTTON_PIN": "6",
                    "TINY_FILM_VIDEO_BUTTON_PIN": "24",
                },
                clear=True,
            ),
            patch.object(sys, "argv", ["shutter_daemon.py"]),
        ):
            configured = shutter_daemon.parse_args()

        self.assertEqual(configured.photo_pin, 6)
        self.assertEqual(configured.video_pin, 24)

    def test_legacy_button_pin_still_configures_photo_button(self) -> None:
        with (
            patch.dict(os.environ, {"TINY_FILM_BUTTON_PIN": "6"}, clear=True),
            patch.object(sys, "argv", ["shutter_daemon.py"]),
        ):
            args = shutter_daemon.parse_args()

        self.assertEqual(args.photo_pin, 6)
        self.assertEqual(args.video_pin, 17)

    def test_each_button_registers_its_own_capture_action(self) -> None:
        fake_gpiozero = types.ModuleType("gpiozero")
        fake_gpiozero.Button = FakeButton
        buzzer = MagicMock()
        buzzer.enabled = False
        photo_path = Path("photo.jpg")
        video_path = Path("video.mp4")

        with (
            patch.dict(os.environ, {}, clear=True),
            patch.dict(sys.modules, {"gpiozero": fake_gpiozero}),
            patch.object(sys, "argv", ["shutter_daemon.py", "--no-buzzer"]),
            patch.object(shutter_daemon, "ShutterBuzzer", return_value=buzzer),
            patch.object(
                shutter_daemon, "capture_photos", return_value=[photo_path]
            ) as capture_photos,
            patch.object(
                shutter_daemon, "record_video", return_value=video_path
            ) as record_video,
            patch.object(
                shutter_daemon,
                "selected_photo_filter_from_cache",
                return_value="normal",
            ),
            patch.object(
                shutter_daemon.threading,
                "Event",
                return_value=StopImmediatelyEvent(),
            ),
            patch.object(shutter_daemon.signal, "signal"),
        ):
            shutter_daemon.main()
            self.assertEqual([button.pin for button in FakeButton.instances], [5, 17])
            self.assertTrue(all(button.closed for button in FakeButton.instances))
            self.assertNotIn("hold_time", FakeButton.instances[0].kwargs)
            self.assertNotIn("hold_time", FakeButton.instances[1].kwargs)

            photo_action = FakeButton.instances[0].when_pressed
            video_action = FakeButton.instances[1].when_pressed
            self.assertIsNotNone(photo_action)
            self.assertIsNotNone(video_action)
            photo_action()
            video_action()

            capture_photos.assert_called_once()
            record_video.assert_called_once()
            self.assertEqual(capture_photos.call_args.args[0].photo_filter, "normal")
            self.assertEqual(record_video.call_args.args[0].duration_seconds, 10.0)


if __name__ == "__main__":
    unittest.main()
