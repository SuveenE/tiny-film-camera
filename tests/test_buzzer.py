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


class FakePwm:
    def __init__(self) -> None:
        self.frequency: float | None = None
        self._value = 0.0
        self.value_history: list[float] = []

    @property
    def value(self) -> float:
        return self._value

    @value.setter
    def value(self, next_value: float) -> None:
        self._value = next_value
        self.value_history.append(next_value)

    def close(self) -> None:
        return None


class ShutterBuzzerTest(unittest.TestCase):
    def test_no_pin_disables_buzzer(self) -> None:
        device = buzzer.ShutterBuzzer(None)

        self.assertFalse(device.enabled)
        device.shutter()
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

    def test_named_sounds_exist(self) -> None:
        self.assertEqual(
            tuple(buzzer.SOUND_ORDER),
            ("shutter", "click", "beep", "chirp", "alert", "double"),
        )
        for name in buzzer.SOUND_ORDER:
            self.assertIn(name, buzzer.SOUNDS)

    def test_shutter_pattern_is_two_step_click_clack(self) -> None:
        pattern = buzzer.SOUNDS["shutter"]
        self.assertEqual(len(pattern), 2)
        self.assertGreater(pattern[0][0], pattern[1][0])
        self.assertLess(pattern[0][1], 0.05)
        self.assertLess(pattern[1][1], 0.05)

    def test_pattern_plays_tones_in_order(self) -> None:
        device = buzzer.ShutterBuzzer(None)
        device._device = FakePwm()
        device._play_tone = MagicMock()

        device._run_pattern(((2000.0, 0.01, 0.0), (1600.0, 0.01, 0.0)))

        self.assertEqual(
            [call.args for call in device._play_tone.call_args_list],
            [(2000.0, 0.01), (1600.0, 0.01)],
        )

    def test_active_pattern_toggles_device_on_and_off(self) -> None:
        device = buzzer.ShutterBuzzer(None)
        fake = MagicMock()
        device._device = fake
        device._active = True

        device._play_tone(2000.0, 0.001)

        fake.on.assert_called_once_with()
        fake.off.assert_called_once_with()

    def test_full_volume_uses_continuous_carrier(self) -> None:
        device = buzzer.ShutterBuzzer(None, volume=1.0)
        fake = FakePwm()
        device._device = fake
        device._active = False

        device._play_tone(1700.0, 0.002)

        self.assertEqual(fake.frequency, 1700.0)
        self.assertIn(buzzer._CARRIER_DUTY, fake.value_history)
        self.assertEqual(fake.value, 0.0)

    def test_partial_volume_bursts_carrier(self) -> None:
        device = buzzer.ShutterBuzzer(None, volume=0.25)
        fake = FakePwm()
        device._device = fake
        device._active = False

        device._play_tone(1700.0, 0.004)

        self.assertEqual(fake.frequency, 1700.0)
        self.assertGreater(fake.value_history.count(buzzer._CARRIER_DUTY), 1)
        self.assertGreater(fake.value_history.count(0.0), 1)
        self.assertEqual(fake.value, 0.0)

    def test_zero_volume_stays_silent(self) -> None:
        device = buzzer.ShutterBuzzer(None, volume=0.0)
        fake = FakePwm()
        device._device = fake
        device._active = False

        device._play_tone(1700.0, 0.002)

        self.assertIsNone(fake.frequency)
        self.assertEqual(fake.value_history, [])

    def test_volume_is_clamped(self) -> None:
        self.assertEqual(buzzer.clamp_volume(-1.0), 0.0)
        self.assertEqual(buzzer.clamp_volume(1.5), 1.0)
        self.assertEqual(buzzer.clamp_volume(0.22), 0.22)

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
