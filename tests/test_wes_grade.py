from pathlib import Path
import json
import sys
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import MagicMock, patch
import types

import numpy as np
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src' / 'tiny-film-cam'))
from photo_filters import apply_photo_filter
from grade import grade_file
from camera import CaptureSettings, _capture_and_save_image, capture_photos


class WesGradeTest(unittest.TestCase):
    def test_single_capture_stops_stream_before_grading(self):
        events = []
        device = MagicMock()
        device.capture_array.side_effect = lambda *a: (
            events.append('capture') or np.zeros((2, 2, 3), dtype=np.uint8)
        )
        device.stop.side_effect = lambda: events.append('stop')
        device.close.side_effect = lambda: events.append('close')
        fake_module = types.ModuleType('picamera2')
        fake_module.Picamera2 = MagicMock(return_value=device)
        fake_module.Picamera2.global_camera_info.return_value = [{}]
        def grade(image, name):
            events.append('grade')
            return image
        with TemporaryDirectory() as tmp, patch.dict(sys.modules, {'picamera2': fake_module}), patch('camera.apply_photo_filter', side_effect=grade):
            capture_photos(CaptureSettings(output_dir=Path(tmp), warmup_seconds=0),
                           on_captured=lambda: events.append('notify'))
        self.assertEqual(events, ['capture', 'notify', 'stop', 'grade', 'close'])

    def test_repeatable_smooth_neutral_ramp(self):
        ramp = Image.fromarray(np.tile(np.arange(256, dtype=np.uint8)[None, :, None], (2, 1, 3)))
        first = apply_photo_filter(ramp, 'wes_anderson')
        self.assertEqual(first.tobytes(), apply_photo_filter(ramp, 'wes_anderson').tobytes())
        result = np.asarray(first).astype(int)
        self.assertTrue((np.diff(result, axis=1) >= 0).all())
        self.assertLessEqual(np.diff(result, axis=1).max(), 3)
        r, g, b = first.getpixel((128, 0))
        self.assertGreater(r, g)
        self.assertGreater(g, b)
        self.assertGreater(min(first.getpixel((0, 0))), 0)
        self.assertLess(max(first.getpixel((255, 0))), 255)

    def test_blues_become_cyan_and_wood_stays_warm(self):
        import colorsys
        image = Image.new('RGB', (2, 1))
        image.putdata([(100, 140, 190), (150, 95, 45)])
        result = apply_photo_filter(image, 'wes_anderson')
        blue_hue = colorsys.rgb_to_hsv(*(c / 255 for c in result.getpixel((0, 0))))[0]
        self.assertTrue(0.45 < blue_hue < 0.57)
        r, g, b = result.getpixel((1, 0))
        self.assertGreater(r, g)
        self.assertGreater(g, b)

    def test_saved_original_regrades_to_same_capture_pixels(self):
        with TemporaryDirectory() as tmp:
            out = Path(tmp) / 'shot.jpg'
            camera = MagicMock()
            camera.capture_array.return_value = np.array([[[30, 70, 140], [180, 130, 90]]], dtype=np.uint8)
            _capture_and_save_image(camera, CaptureSettings(photo_filter='wes_anderson', keep_original=True, rotation=0), out, None)
            original = out.with_name('shot.original.png')
            regraded = Path(tmp) / 'regraded.png'
            grade_file(original, regraded)
            with Image.open(original) as raw, Image.open(regraded) as actual:
                self.assertEqual(raw.getpixel((0, 0)), (140, 70, 30))
                self.assertEqual(actual.tobytes(), apply_photo_filter(raw, 'wes_anderson').tobytes())
            metadata = json.loads(out.with_name('shot.jpg.json').read_text())
            self.assertEqual(metadata['photo_filter']['id'], 'wes_anderson')

    def test_strength_zero_orientation_and_no_overwrite(self):
        with TemporaryDirectory() as tmp:
            original = Path(tmp) / 'in.png'
            result = Path(tmp) / 'out.png'
            img = Image.new('RGB', (2, 3), (30, 80, 120))
            exif = Image.Exif()
            exif[274] = 6
            img.save(original, exif=exif)
            before = original.read_bytes()
            grade_file(original, result, strength=0)
            with Image.open(result) as graded:
                self.assertEqual(graded.size, (3, 2))
                self.assertEqual(graded.getpixel((0, 0)), (30, 80, 120))
                self.assertNotIn(274, graded.getexif())
            self.assertEqual(original.read_bytes(), before)
            with self.assertRaises(FileExistsError):
                grade_file(original, result)
            with self.assertRaises(ValueError):
                grade_file(original, original)
            for strength in [-.1, 1.1, float('nan')]:
                with self.assertRaises(ValueError):
                    grade_file(original, Path(tmp) / 'invalid.png', strength=strength)


if __name__ == '__main__':
    unittest.main()
