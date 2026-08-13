from __future__ import annotations

import importlib.util
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch


SOURCE_ROOT = Path(__file__).resolve().parents[1] / "src" / "tiny-film-cam"
DIAGNOSTIC_PATH = SOURCE_ROOT / "shutter_diagnostic.py"


def load_shutter_diagnostic():
    source_root = str(SOURCE_ROOT)
    if source_root not in sys.path:
        sys.path.insert(0, source_root)
    spec = importlib.util.spec_from_file_location(
        "tiny_film_shutter_diagnostic",
        DIAGNOSTIC_PATH,
    )
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load diagnostic from {DIAGNOSTIC_PATH}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


shutter_diagnostic = load_shutter_diagnostic()


class ShutterDiagnosticTest(unittest.TestCase):
    def test_repeated_capture_passes_when_every_request_saves_a_jpeg(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            project_root = Path(temp_dir)
            settings = shutter_diagnostic.capture_settings_from_env(project_root)
            capture_number = 0

            def capture_photos(capture_settings, on_captured):
                nonlocal capture_number
                capture_number += 1
                on_captured()
                output_path = (
                    capture_settings.output_dir / f"diagnostic-{capture_number}.jpg"
                )
                output_path.parent.mkdir(parents=True, exist_ok=True)
                output_path.write_bytes(b"jpeg")
                return [output_path]

            with (
                patch.object(
                    shutter_diagnostic,
                    "capture_settings_from_env",
                    return_value=settings,
                ),
                patch.object(
                    shutter_diagnostic,
                    "selected_photo_filter_from_cache",
                    return_value="normal",
                ),
                patch.object(
                    shutter_diagnostic,
                    "capture_photos",
                    side_effect=capture_photos,
                ),
            ):
                passed = shutter_diagnostic.run_diagnostic(
                    project_root,
                    count=3,
                    interval=0,
                )

        self.assertTrue(passed)
        self.assertEqual(capture_number, 3)

    def test_repeated_capture_fails_when_a_request_errors(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            project_root = Path(temp_dir)
            settings = shutter_diagnostic.capture_settings_from_env(project_root)
            with (
                patch.object(
                    shutter_diagnostic,
                    "capture_settings_from_env",
                    return_value=settings,
                ),
                patch.object(
                    shutter_diagnostic,
                    "selected_photo_filter_from_cache",
                    return_value="normal",
                ),
                patch.object(
                    shutter_diagnostic,
                    "capture_photos",
                    side_effect=RuntimeError("camera busy"),
                ),
            ):
                passed = shutter_diagnostic.run_diagnostic(
                    project_root,
                    count=1,
                    interval=0,
                )

        self.assertFalse(passed)


if __name__ == "__main__":
    unittest.main()
