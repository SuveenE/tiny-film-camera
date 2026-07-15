from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock


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
        # Should be safe no-ops when disabled.
        device.success()
        device.error()
        device.close()

    def test_missing_gpiozero_degrades_gracefully(self) -> None:
        # gpiozero is not installed off-Pi, so requesting a pin must not raise.
        device = buzzer.ShutterBuzzer(18, active=True)

        self.assertFalse(device.enabled)

    def test_active_pattern_toggles_device_on_and_off(self) -> None:
        device = buzzer.ShutterBuzzer(None)
        fake = MagicMock()
        device._device = fake
        device._active = True

        device._run_pattern(((880.0, 0.0, 0.0),))

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
