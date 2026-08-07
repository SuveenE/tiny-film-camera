from __future__ import annotations

import json
import importlib
from pathlib import Path
import sys
import time
import unittest
from tempfile import TemporaryDirectory
from unittest.mock import patch

from PIL import Image


SOURCE_ROOT = Path(__file__).resolve().parents[1] / "src" / "tiny-film-cam"
if str(SOURCE_ROOT) not in sys.path:
    sys.path.insert(0, str(SOURCE_ROOT))

capture_metadata = importlib.import_module("capture_metadata")
filter_switch = importlib.import_module("filter_switch")
photo_filters = importlib.import_module("photo_filters")
web = importlib.import_module("web")


class PhotoFiltersTest(unittest.TestCase):
    def test_current_filter_keeps_pixels_unchanged(self) -> None:
        image = Image.new("RGB", (1, 1), (80, 100, 120))

        filtered = photo_filters.apply_photo_filter(image, "current")

        self.assertEqual(filtered.getpixel((0, 0)), (80, 100, 120))

    def test_black_and_white_filter_outputs_equal_channels(self) -> None:
        image = Image.new("RGB", (1, 1), (200, 80, 30))

        filtered = photo_filters.apply_photo_filter(image, "black_and_white")

        red, green, blue = filtered.getpixel((0, 0))
        self.assertEqual(red, green)
        self.assertEqual(green, blue)

    def test_cold_filter_reduces_red_and_raises_blue(self) -> None:
        image = Image.new("RGB", (1, 1), (100, 100, 100))

        filtered = photo_filters.apply_photo_filter(image, "cold")

        red, green, blue = filtered.getpixel((0, 0))
        self.assertLess(red, green)
        self.assertGreater(blue, green)

    def test_fresh_switch_selection_is_used(self) -> None:
        with TemporaryDirectory() as tmpdir:
            project_root = Path(tmpdir)
            cache_path = project_root / "data" / "filter-state.json"
            filter_switch.write_filter_cache(
                cache_path,
                filter_switch.build_filter_state(
                    left_grounded=False,
                    right_grounded=True,
                ),
            )

            status = photo_filters.photo_filter_status_from_cache(project_root)

        self.assertFalse(status["using_fallback"])
        self.assertEqual(status["active_filter"]["id"], "cold")

    def test_stale_or_unknown_switch_selection_falls_back_to_current(self) -> None:
        with TemporaryDirectory() as tmpdir:
            project_root = Path(tmpdir)
            cache_path = project_root / "data" / "filter-state.json"
            cache_path.parent.mkdir(parents=True)
            cache_path.write_text(
                json.dumps(
                    {
                        "ok": True,
                        "timestamp_unix": time.time() - 60,
                        "selection": "cold",
                    }
                ),
                encoding="utf-8",
            )
            stale = photo_filters.photo_filter_status_from_cache(project_root)

            cache_path.write_text(
                json.dumps(
                    {
                        "ok": True,
                        "timestamp_unix": time.time(),
                        "selection": "sepia",
                    }
                ),
                encoding="utf-8",
            )
            unknown = photo_filters.photo_filter_status_from_cache(project_root)

        self.assertTrue(stale["using_fallback"])
        self.assertEqual(stale["active_filter"]["id"], "current")
        self.assertTrue(unknown["using_fallback"])
        self.assertEqual(unknown["active_filter"]["id"], "current")
        self.assertIn("Unknown photo filter", unknown["error"])

    def test_metadata_round_trip_and_delete(self) -> None:
        with TemporaryDirectory() as tmpdir:
            capture_path = Path(tmpdir) / "photo.jpg"
            capture_path.write_bytes(b"jpeg")

            metadata_path = capture_metadata.write_photo_filter_metadata(
                capture_path,
                "black_and_white",
            )
            payload = capture_metadata.read_capture_metadata(capture_path)
            deleted = capture_metadata.delete_capture_metadata(capture_path)

        self.assertEqual(payload["photo_filter"]["label"], "Black & white")
        self.assertTrue(deleted)
        self.assertFalse(metadata_path.exists())

    def test_web_gallery_reads_and_deletes_filter_metadata(self) -> None:
        with TemporaryDirectory() as tmpdir:
            project_root = Path(tmpdir)
            capture_path = project_root / "data" / "captures" / "2026-08-07" / "photo.jpg"
            capture_path.parent.mkdir(parents=True)
            capture_path.write_bytes(b"jpeg")
            capture_metadata.write_photo_filter_metadata(capture_path, "cold")

            item = web.build_capture_image(project_root, capture_path)
            deleted = web.delete_capture_image(
                project_root,
                "2026-08-07/photo.jpg",
            )

        self.assertEqual(item["photo_filter"]["id"], "cold")
        self.assertEqual(deleted["relative_path"], "2026-08-07/photo.jpg")
        self.assertFalse(capture_metadata.metadata_path_for(capture_path).exists())

    def test_web_capture_uses_live_filter_selection(self) -> None:
        with TemporaryDirectory() as tmpdir:
            project_root = Path(tmpdir)
            output_path = project_root / "data" / "captures" / "photo.jpg"
            output_path.parent.mkdir(parents=True)
            output_path.write_bytes(b"jpeg")
            captured_settings = []

            def fake_capture(settings):
                captured_settings.append(settings)
                capture_metadata.write_photo_filter_metadata(
                    output_path,
                    settings.photo_filter,
                )
                return output_path

            with (
                patch.object(
                    web,
                    "selected_photo_filter_from_cache",
                    return_value="black_and_white",
                ),
                patch.object(web, "capture_photo", side_effect=fake_capture),
            ):
                item = web.capture_from_web(project_root)

        self.assertEqual(captured_settings[0].photo_filter, "black_and_white")
        self.assertEqual(item["photo_filter"]["id"], "black_and_white")


if __name__ == "__main__":
    unittest.main()
