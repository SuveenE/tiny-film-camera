from __future__ import annotations

import builtins
import importlib.util
import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch


BUZZER_PATH = Path(__file__).resolve().parents[1] / "src" / "tiny-film-cam" / "buzzer.py"


def load_buzzer_module():
    spec = importlib.util.spec_from_file_location("tiny_film_buzzer", BUZZER_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load buzzer module from {BUZZER_PATH}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


buzzer = load_buzzer_module()


class ShutterBuzzerTest(unittest.TestCase):
    def test_no_pin_disables_buzzer(self) -> None:
        device = buzzer.ShutterBuzzer(None)

        self.assertFalse(device.enabled)
        device.click()
        device.photo_ok()
        device.video_start()
        device.video_stop()
        device.error()
        device.close()

    def test_missing_gpiozero_degrades_gracefully(self) -> None:
        # Simulate a missing gpiozero even on a Pi where it is installed, so the
        # test does not claim a real GPIO pin or depend on the host packages.
        real_import = builtins.__import__

        def block_gpiozero(
            name: str,
            globals_=None,
            locals_=None,
            fromlist: tuple[str, ...] = (),
            level: int = 0,
        ):
            if name == "gpiozero" or name.startswith("gpiozero."):
                raise ModuleNotFoundError("No module named 'gpiozero'")
            return real_import(name, globals_, locals_, fromlist, level)

        with patch("builtins.__import__", side_effect=block_gpiozero):
            device = buzzer.ShutterBuzzer(18, active=False)

        self.assertFalse(device.enabled)

    def test_five_named_sounds_exist(self) -> None:
        self.assertEqual(
            tuple(buzzer.SOUND_ORDER),
            ("click", "beep", "chirp", "alert", "double"),
        )
        for name in buzzer.SOUND_ORDER:
            self.assertIn(name, buzzer.SOUNDS)

    def test_pattern_calls_tone_helpers_in_order(self) -> None:
        device = buzzer.ShutterBuzzer(None)
        device._device = MagicMock()
        device._tone_on = MagicMock()
        device._tone_off = MagicMock()

        device._run_pattern(((2000.0, 0.0, 0.0), (1600.0, 0.0, 0.0)))

        self.assertEqual(
            [call.args[0] for call in device._tone_on.call_args_list],
            [2000.0, 1600.0],
        )
        self.assertEqual(device._tone_off.call_count, 2)

    def test_active_pattern_toggles_device_on_and_off(self) -> None:
        device = buzzer.ShutterBuzzer(None)
        fake = MagicMock()
        device._device = fake
        device._active = True

        device._run_pattern(((2000.0, 0.0, 0.0),))

        fake.on.assert_called_once_with()
        fake.off.assert_called_once_with()

    def test_close_releases_device(self) -> None:
        device = buzzer.ShutterBuzzer(None)
        fake = MagicMock()
        device._device = fake
        device._active = True

        device.close()

        fake.close.assert_called_once_with()
        self.assertFalse(device.enabled)


if __name__ == "__main__":
    unittest.main()
