from __future__ import annotations

import argparse
import io
import json
import mimetypes
import shutil
import socket
import zipfile
from email.utils import formatdate
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import quote, unquote


CAPTURE_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp"}


def default_project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def captures_root(project_root: Path) -> Path:
    return project_root / "data" / "captures"


def is_capture_image_file(path: Path) -> bool:
    return (
        path.is_file()
        and not path.name.startswith(".")
        and path.suffix.lower() in CAPTURE_SUFFIXES
    )


def iter_capture_images(project_root: Path) -> list[Path]:
    root = captures_root(project_root)
    if not root.exists():
        return []
    return sorted(
        (path for path in root.rglob("*") if is_capture_image_file(path)),
        key=lambda path: path.stat().st_mtime_ns,
        reverse=True,
    )


def get_capture_image_by_relative_path(project_root: Path, relative_path: str) -> Path | None:
    root = captures_root(project_root)
    decoded_relative = unquote(relative_path).lstrip("/")
    candidate = (root / decoded_relative).resolve()
    try:
        candidate.relative_to(root.resolve())
    except ValueError:
        return None
    if is_capture_image_file(candidate):
        return candidate
    return None


def get_latest_capture_path(project_root: Path) -> Path | None:
    images = iter_capture_images(project_root)
    if not images:
        return None
    return images[0]


def build_capture_image_list(project_root: Path) -> list[dict[str, object]]:
    root = captures_root(project_root)
    images: list[dict[str, object]] = []
    for image_path in iter_capture_images(project_root):
        relative_path = image_path.relative_to(root).as_posix()
        stat = image_path.stat()
        images.append(
            {
                "filename": image_path.name,
                "relative_path": relative_path,
                "download_url": f"/download/captures/{quote(relative_path)}",
                "modified_unix": stat.st_mtime,
                "size_bytes": stat.st_size,
            }
        )
    return images


def build_captures_zip(project_root: Path) -> bytes:
    root = captures_root(project_root)
    output = io.BytesIO()
    with zipfile.ZipFile(output, mode="w", compression=zipfile.ZIP_DEFLATED) as archive:
        for image_path in iter_capture_images(project_root):
            archive.write(image_path, image_path.relative_to(root).as_posix())
    return output.getvalue()


def format_bytes(value: int) -> str:
    amount = float(value)
    for unit in ("B", "KB", "MB", "GB"):
        if amount < 1024 or unit == "GB":
            return f"{amount:.1f} {unit}" if unit != "B" else f"{int(amount)} B"
        amount /= 1024
    return f"{amount:.1f} GB"


def local_ip_address() -> str:
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.settimeout(0.2)
            sock.connect(("8.8.8.8", 80))
            return str(sock.getsockname()[0])
    except OSError:
        try:
            return socket.gethostbyname(socket.gethostname())
        except OSError:
            return "127.0.0.1"


def build_device_details(project_root: Path, port: int) -> dict[str, object]:
    disk = shutil.disk_usage(project_root)
    hostname = socket.gethostname().strip() or "tiny-film"
    ip_address = local_ip_address()
    port_suffix = "" if port == 80 else f":{port}"
    images = iter_capture_images(project_root)
    latest = images[0].relative_to(captures_root(project_root)).as_posix() if images else None
    return {
        "hostname": hostname,
        "ip_address": ip_address,
        "app_url": f"http://{ip_address}{port_suffix}",
        "capture_count": len(images),
        "latest_capture": latest,
        "storage_status": f"{format_bytes(disk.free)} free of {format_bytes(disk.total)}",
        "storage_free_bytes": disk.free,
        "storage_total_bytes": disk.total,
    }


def render_page() -> bytes:
    page = """
    <!doctype html>
    <html lang="en">
      <head>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <meta name="theme-color" content="#f7f7f4">
        <title>Tiny Film</title>
        <style>
          :root {
            color-scheme: light;
            --bg: #f7f7f4;
            --fg: #111;
            --muted: #62605a;
            --line: #d5d2ca;
            --accent: #b23a30;
          }
          * { box-sizing: border-box; }
          body {
            margin: 0;
            background: var(--bg);
            color: var(--fg);
            font-family: ui-sans-serif, -apple-system, BlinkMacSystemFont, "SF Pro Text", "Helvetica Neue", Arial, sans-serif;
          }
          main {
            width: min(920px, 100%);
            margin: 0 auto;
            padding: 18px;
          }
          header {
            display: flex;
            align-items: baseline;
            justify-content: space-between;
            gap: 18px;
            padding: 8px 0 54px;
          }
          h1, h2, p { margin: 0; }
          h1 { font-size: 20px; font-weight: 650; letter-spacing: 0; }
          h2 { font-size: 28px; line-height: 1.1; font-weight: 650; letter-spacing: 0; }
          section {
            border-top: 1px solid var(--line);
            padding: 18px 0 34px;
          }
          .status {
            color: var(--muted);
            font-size: 14px;
          }
          .latest {
            display: grid;
            gap: 14px;
          }
          .latest-frame {
            min-height: 260px;
            border: 1px solid var(--line);
            background: #fff;
            display: grid;
            place-items: center;
            overflow: hidden;
          }
          .latest-frame img {
            display: block;
            width: 100%;
            max-height: 64vh;
            object-fit: contain;
          }
          .empty {
            color: var(--muted);
            padding: 42px 16px;
            text-align: center;
          }
          .row {
            display: grid;
            grid-template-columns: minmax(0, 1fr) auto;
            gap: 16px;
            align-items: center;
            padding: 14px 0;
            border-bottom: 1px solid var(--line);
          }
          .name {
            overflow-wrap: anywhere;
            font-size: 15px;
          }
          .meta {
            color: var(--muted);
            display: block;
            font-size: 13px;
            margin-top: 4px;
          }
          a.button {
            border: 1px solid var(--fg);
            border-radius: 999px;
            color: var(--fg);
            display: inline-block;
            font-size: 14px;
            font-weight: 600;
            padding: 8px 13px;
            text-decoration: none;
            white-space: nowrap;
          }
          a.button.primary {
            background: var(--fg);
            color: var(--bg);
          }
          .details {
            display: grid;
            border-top: 1px solid var(--line);
          }
          .detail {
            display: grid;
            grid-template-columns: 140px 1fr;
            gap: 16px;
            padding: 13px 0;
            border-bottom: 1px solid var(--line);
          }
          .label {
            color: var(--muted);
            font-size: 14px;
          }
          .value {
            overflow-wrap: anywhere;
          }
          @media (max-width: 640px) {
            header { padding-bottom: 42px; }
            .row { grid-template-columns: 1fr; gap: 10px; }
            .detail { grid-template-columns: 1fr; gap: 3px; }
          }
        </style>
      </head>
      <body>
        <main>
          <header>
            <h1>Tiny Film</h1>
            <a class="button primary" href="/download/captures/">Download All</a>
          </header>

          <section class="latest">
            <h2>Latest</h2>
            <p class="status" id="status">Checking captures...</p>
            <div class="latest-frame" id="latest-frame"></div>
          </section>

          <section>
            <h2>Captures</h2>
            <div id="capture-list"></div>
          </section>

          <section>
            <h2>Device</h2>
            <div class="details" id="device-details"></div>
          </section>
        </main>

        <script>
          const statusElement = document.getElementById("status");
          const latestFrame = document.getElementById("latest-frame");
          const captureList = document.getElementById("capture-list");
          const deviceDetails = document.getElementById("device-details");

          function formatBytes(value) {
            if (!Number.isFinite(value)) return "";
            const units = ["B", "KB", "MB", "GB"];
            let amount = value;
            let index = 0;
            while (amount >= 1024 && index < units.length - 1) {
              amount /= 1024;
              index += 1;
            }
            return index === 0 ? `${amount} ${units[index]}` : `${amount.toFixed(1)} ${units[index]}`;
          }

          function formatDate(seconds) {
            if (!seconds) return "";
            return new Date(seconds * 1000).toLocaleString();
          }

          function renderImages(images) {
            statusElement.textContent = `${images.length} capture${images.length === 1 ? "" : "s"}`;
            latestFrame.innerHTML = "";
            if (images.length) {
              const image = document.createElement("img");
              image.src = `/latest-image?v=${encodeURIComponent(images[0].modified_unix)}`;
              image.alt = images[0].filename || "Latest capture";
              latestFrame.appendChild(image);
            } else {
              latestFrame.innerHTML = '<div class="empty">No captures yet.</div>';
            }
            captureList.innerHTML = images.length ? "" : '<div class="empty">No captures yet.</div>';
            images.forEach((image) => {
              const row = document.createElement("div");
              row.className = "row";

              const text = document.createElement("div");
              const name = document.createElement("div");
              name.className = "name";
              name.textContent = image.relative_path || image.filename;
              const meta = document.createElement("span");
              meta.className = "meta";
              meta.textContent = [formatDate(image.modified_unix), formatBytes(image.size_bytes)]
                .filter(Boolean)
                .join(" / ");
              text.append(name, meta);

              const link = document.createElement("a");
              link.className = "button";
              link.href = image.download_url;
              link.download = image.filename || "capture.jpg";
              link.textContent = "Download";

              row.append(text, link);
              captureList.appendChild(row);
            });
          }

          function renderDetails(details) {
            const rows = [
              ["Hostname", details.hostname],
              ["IP Address", details.ip_address],
              ["App URL", details.app_url],
              ["Captures", details.capture_count],
              ["Latest", details.latest_capture],
              ["Storage", details.storage_status],
            ];
            deviceDetails.innerHTML = "";
            rows.forEach(([label, value]) => {
              const row = document.createElement("div");
              row.className = "detail";
              const labelElement = document.createElement("div");
              labelElement.className = "label";
              labelElement.textContent = label;
              const valueElement = document.createElement("div");
              valueElement.className = "value";
              valueElement.textContent = value === null || value === undefined || value === "" ? "Unknown" : value;
              row.append(labelElement, valueElement);
              deviceDetails.appendChild(row);
            });
          }

          async function refreshImages() {
            const response = await fetch("/api/images", { cache: "no-store" });
            if (!response.ok) throw new Error("Image request failed");
            const data = await response.json();
            renderImages(data.images || []);
          }

          async function refreshDetails() {
            const response = await fetch("/api/device-details", { cache: "no-store" });
            if (!response.ok) throw new Error("Device request failed");
            renderDetails(await response.json());
          }

          refreshImages().catch(() => {
            statusElement.textContent = "Could not load captures.";
          });
          refreshDetails().catch(() => {});
          setInterval(() => refreshImages().catch(() => {}), 5000);
          setInterval(() => refreshDetails().catch(() => {}), 5000);
        </script>
      </body>
    </html>
    """
    return page.encode("utf-8")


def attachment_header(filename: str) -> str:
    safe_filename = filename.replace("\\", "_").replace('"', "_")
    return f'attachment; filename="{safe_filename}"'


def build_handler(project_root: Path, port: int):
    class TinyFilmHandler(BaseHTTPRequestHandler):
        def _send_bytes(
            self,
            body: bytes,
            content_type: str,
            status: HTTPStatus = HTTPStatus.OK,
            extra_headers: dict[str, str] | None = None,
        ) -> None:
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(body)))
            for key, value in (extra_headers or {}).items():
                self.send_header(key, value)
            self.end_headers()
            self.wfile.write(body)

        def _send_json(self, payload: dict[str, object]) -> None:
            self._send_bytes(
                json.dumps(payload).encode("utf-8"),
                "application/json; charset=utf-8",
            )

        def _serve_capture(self, image_path: Path) -> None:
            body = image_path.read_bytes()
            content_type = mimetypes.guess_type(image_path.name)[0] or "application/octet-stream"
            self._send_bytes(
                body,
                content_type,
                extra_headers={"Content-Disposition": attachment_header(image_path.name)},
            )

        def _serve_latest_image(self, include_body: bool = True) -> None:
            image_path = get_latest_capture_path(project_root)
            if image_path is None:
                self.send_error(HTTPStatus.NOT_FOUND, "No captures available yet")
                return

            stat = image_path.stat()
            content_type = mimetypes.guess_type(image_path.name)[0] or "application/octet-stream"
            etag = f'"{image_path.name}-{stat.st_mtime_ns}-{stat.st_size}"'
            if self.headers.get("If-None-Match") == etag:
                self.send_response(HTTPStatus.NOT_MODIFIED)
                self.send_header("ETag", etag)
                self.end_headers()
                return

            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", content_type)
            self.send_header("Cache-Control", "no-store, no-cache, must-revalidate, max-age=0")
            self.send_header("Content-Length", str(stat.st_size))
            self.send_header("ETag", etag)
            self.send_header("Last-Modified", formatdate(stat.st_mtime, usegmt=True))
            self.end_headers()
            if include_body:
                try:
                    self.wfile.write(image_path.read_bytes())
                except (BrokenPipeError, ConnectionResetError):
                    return

        def do_GET(self) -> None:
            request_path = self.path.split("?", 1)[0]
            if request_path == "/":
                self._send_bytes(render_page(), "text/html; charset=utf-8")
                return

            if request_path == "/api/images":
                self._send_json({"images": build_capture_image_list(project_root)})
                return

            if request_path == "/api/device-details":
                self._send_json(build_device_details(project_root, port))
                return

            if request_path == "/latest-image":
                self._serve_latest_image(include_body=True)
                return

            if request_path == "/download/captures/":
                body = build_captures_zip(project_root)
                self._send_bytes(
                    body,
                    "application/zip",
                    extra_headers={"Content-Disposition": attachment_header("tiny-film-captures.zip")},
                )
                return

            if request_path.startswith("/download/captures/"):
                relative_path = request_path[len("/download/captures/") :]
                image_path = get_capture_image_by_relative_path(project_root, relative_path)
                if image_path is None:
                    self.send_error(HTTPStatus.NOT_FOUND, "Capture not found")
                    return
                self._serve_capture(image_path)
                return

            self.send_error(HTTPStatus.NOT_FOUND, "Not Found")

        def do_HEAD(self) -> None:
            request_path = self.path.split("?", 1)[0]
            if request_path == "/latest-image":
                self._serve_latest_image(include_body=False)
                return
            self.send_error(HTTPStatus.NOT_FOUND, "Not Found")

        def log_message(self, format: str, *args) -> None:
            return

    return TinyFilmHandler


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the Tiny Film capture web app.")
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--project-root", type=Path, default=default_project_root())
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    project_root = args.project_root.expanduser().resolve()
    captures_root(project_root).mkdir(parents=True, exist_ok=True)
    server = ThreadingHTTPServer(
        (args.host, args.port),
        build_handler(project_root, args.port),
    )
    print(f"Tiny Film web app: http://{args.host}:{args.port}")
    try:
        server.serve_forever(poll_interval=0.5)
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
