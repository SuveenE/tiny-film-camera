from __future__ import annotations

import http.client
import importlib
import json
from pathlib import Path
import sys
import threading
import unittest
from tempfile import TemporaryDirectory


SOURCE_ROOT = Path(__file__).resolve().parents[1] / "src" / "tiny-film-cam"
if str(SOURCE_ROOT) not in sys.path:
    sys.path.insert(0, str(SOURCE_ROOT))

web = importlib.import_module("web")


class ByteRangeTest(unittest.TestCase):
    def test_parses_explicit_open_and_suffix_ranges(self) -> None:
        self.assertEqual(web.parse_byte_range_header("bytes=2-5", 10), (2, 5))
        self.assertEqual(web.parse_byte_range_header("bytes=7-", 10), (7, 9))
        self.assertEqual(web.parse_byte_range_header("bytes=-3", 10), (7, 9))
        self.assertEqual(web.parse_byte_range_header("bytes=8-20", 10), (8, 9))

    def test_rejects_invalid_or_unsatisfied_ranges(self) -> None:
        for value in ("items=0-1", "bytes=", "bytes=3-2", "bytes=10-11"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                web.parse_byte_range_header(value, 10)


class RenderPageTest(unittest.TestCase):
    def test_capture_controls_do_not_render_latest_position_heading(self) -> None:
        page = web.render_page().decode("utf-8")

        self.assertIn('id="capture-button"', page)
        self.assertNotIn('id="preview-heading"', page)
        self.assertNotIn('id="capture-position"', page)
        self.assertNotIn('id="filter-active-label"', page)
        self.assertNotIn('id="filter-state"', page)

    def test_home_page_limits_the_gallery_and_links_to_the_full_gallery(self) -> None:
        page = web.render_page().decode("utf-8")

        self.assertIn('data-page="home"', page)
        self.assertIn('href="/gallery"', page)
        self.assertIn("const HOME_GALLERY_LIMIT = 50", page)
        self.assertNotIn('id="save-selected-button"', page)
        self.assertNotIn("navigator.share", page)

    def test_gallery_page_has_a_back_control(self) -> None:
        page = web.render_page("gallery").decode("utf-8")

        self.assertIn('data-page="gallery"', page)
        self.assertIn('href="/" id="back-button"', page)
        self.assertIn("Gallery · Suv's Tiny Film Camera", page)


class CaptureListLimitTest(unittest.TestCase):
    def test_parses_and_caps_positive_gallery_limits(self) -> None:
        self.assertEqual(web.parse_capture_list_limit("limit=12"), 12)
        self.assertEqual(web.parse_capture_list_limit("limit=500"), 50)

    def test_ignores_missing_invalid_and_non_positive_limits(self) -> None:
        for query in ("", "limit=nope", "limit=0", "limit=-2"):
            with self.subTest(query=query):
                self.assertIsNone(web.parse_capture_list_limit(query))


class CaptureMediaServerTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = TemporaryDirectory()
        self.project_root = Path(self.temporary_directory.name)
        self.capture_path = (
            self.project_root / "data" / "captures" / "2026-08-10" / "clip.mp4"
        )
        self.capture_path.parent.mkdir(parents=True)
        self.capture_path.write_bytes(b"0123456789")
        self.server = web.ThreadingHTTPServer(
            ("127.0.0.1", 0),
            web.build_handler(self.project_root, 0),
        )
        self.server_thread = threading.Thread(
            target=self.server.serve_forever,
            daemon=True,
        )
        self.server_thread.start()

    def tearDown(self) -> None:
        self.server.shutdown()
        self.server.server_close()
        self.server_thread.join(timeout=2)
        self.temporary_directory.cleanup()

    def request(
        self,
        method: str,
        headers: dict[str, str] | None = None,
        path: str = "/image/captures/2026-08-10/clip.mp4",
    ) -> tuple[int, dict[str, str], bytes]:
        connection = http.client.HTTPConnection(*self.server.server_address)
        connection.request(
            method,
            path,
            headers=headers or {},
        )
        response = connection.getresponse()
        result = response.status, dict(response.getheaders()), response.read()
        connection.close()
        return result

    def test_video_endpoint_serves_safari_style_byte_ranges(self) -> None:
        status, headers, body = self.request("GET", {"Range": "bytes=2-5"})

        self.assertEqual(status, 206)
        self.assertEqual(body, b"2345")
        self.assertEqual(headers["Accept-Ranges"], "bytes")
        self.assertEqual(headers["Content-Range"], "bytes 2-5/10")
        self.assertEqual(headers["Content-Length"], "4")
        self.assertEqual(headers["Content-Type"], "video/mp4")

    def test_unsatisfied_range_returns_416_with_file_size(self) -> None:
        status, headers, body = self.request("GET", {"Range": "bytes=20-30"})

        self.assertEqual(status, 416)
        self.assertEqual(body, b"")
        self.assertEqual(headers["Content-Range"], "bytes */10")

    def test_head_returns_media_headers_without_a_body(self) -> None:
        status, headers, body = self.request("HEAD")

        self.assertEqual(status, 200)
        self.assertEqual(body, b"")
        self.assertEqual(headers["Accept-Ranges"], "bytes")
        self.assertEqual(headers["Content-Length"], "10")

    def test_serves_the_dedicated_gallery_page(self) -> None:
        status, _, body = self.request("GET", path="/gallery")

        self.assertEqual(status, 200)
        self.assertIn(b'data-page="gallery"', body)
        self.assertIn(b'id="back-button"', body)

    def test_limited_image_api_reports_the_complete_capture_count(self) -> None:
        for index in range(51):
            (self.capture_path.parent / f"photo-{index:02d}.jpg").write_bytes(b"photo")

        status, _, body = self.request("GET", path="/api/images?limit=50")
        payload = json.loads(body)

        self.assertEqual(status, 200)
        self.assertEqual(len(payload["images"]), 50)
        self.assertEqual(payload["total"], 52)


if __name__ == "__main__":
    unittest.main()
