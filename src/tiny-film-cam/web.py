from __future__ import annotations

import argparse
import json
import mimetypes
import shutil
import socket
from dataclasses import replace
from email.utils import formatdate
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, quote, unquote, urlsplit

from battery import battery_status_from_cache
from capture_metadata import delete_capture_metadata, read_capture_metadata
from camera import (
    CameraCaptureError,
    CameraUnavailableError,
    capture_output_dir_from_env,
    capture_photo,
    capture_settings_from_env,
    record_video,
    video_poster_path,
    video_settings_from_env,
)
from photo_filters import (
    photo_filter_status_from_cache,
    selected_photo_filter_from_cache,
)


IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp"}
VIDEO_SUFFIXES = {".mp4"}
CAPTURE_SUFFIXES = IMAGE_SUFFIXES | VIDEO_SUFFIXES
HOME_GALLERY_LIMIT = 50


def media_type_for(path: Path) -> str:
    return "video" if path.suffix.lower() in VIDEO_SUFFIXES else "image"


def default_project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def captures_root(project_root: Path) -> Path:
    return capture_output_dir_from_env(project_root)


def is_capture_image_file(path: Path) -> bool:
    return (
        path.is_file()
        and not path.name.startswith(".")
        and not path.name.lower().endswith(".mp4.poster.jpg")
        and path.suffix.lower() in CAPTURE_SUFFIXES
    )


def is_video_poster_file(path: Path) -> bool:
    return (
        path.is_file()
        and not path.name.startswith(".")
        and path.name.lower().endswith(".mp4.poster.jpg")
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


def get_capture_image_by_relative_path(
    project_root: Path, relative_path: str
) -> Path | None:
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


def get_capture_media_by_relative_path(
    project_root: Path, relative_path: str
) -> Path | None:
    root = captures_root(project_root)
    decoded_relative = unquote(relative_path).lstrip("/")
    candidate = (root / decoded_relative).resolve()
    try:
        candidate.relative_to(root.resolve())
    except ValueError:
        return None
    if is_capture_image_file(candidate) or is_video_poster_file(candidate):
        return candidate
    return None


def get_latest_capture_path(project_root: Path) -> Path | None:
    images = iter_capture_images(project_root)
    if not images:
        return None
    return images[0]


def build_capture_image_list(
    project_root: Path, limit: int | None = None
) -> list[dict[str, object]]:
    image_paths = iter_capture_images(project_root)
    if limit is not None:
        image_paths = image_paths[: max(0, limit)]
    return [
        build_capture_image(project_root, image_path)
        for image_path in image_paths
    ]


def parse_capture_list_limit(query: str) -> int | None:
    raw_limit = parse_qs(query).get("limit", [None])[0]
    if raw_limit is None:
        return None
    try:
        limit = int(raw_limit)
    except (TypeError, ValueError):
        return None
    if limit <= 0:
        return None
    return min(limit, HOME_GALLERY_LIMIT)


def build_capture_image(project_root: Path, image_path: Path) -> dict[str, object]:
    root = captures_root(project_root).resolve()
    relative_path = image_path.resolve().relative_to(root).as_posix()
    stat = image_path.stat()
    metadata = read_capture_metadata(image_path)
    photo_filter = metadata.get("photo_filter")
    poster_path = video_poster_path(image_path)
    poster_url = None
    if media_type_for(image_path) == "video" and poster_path.is_file():
        poster_relative_path = poster_path.resolve().relative_to(root).as_posix()
        poster_url = f"/image/captures/{quote(poster_relative_path)}"
    return {
        "filename": image_path.name,
        "relative_path": relative_path,
        "media_type": media_type_for(image_path),
        "view_url": f"/image/captures/{quote(relative_path)}",
        "download_url": f"/download/captures/{quote(relative_path)}",
        "delete_url": f"/api/captures/{quote(relative_path)}",
        "modified_unix": stat.st_mtime,
        "size_bytes": stat.st_size,
        "poster_url": poster_url,
        "photo_filter": photo_filter if isinstance(photo_filter, dict) else None,
    }


def capture_from_web(project_root: Path) -> dict[str, object]:
    settings = replace(
        capture_settings_from_env(project_root),
        photo_filter=selected_photo_filter_from_cache(project_root),
    )
    output_path = capture_photo(settings)
    try:
        output_path.relative_to(captures_root(project_root))
    except ValueError as exc:
        raise RuntimeError(
            "Capture was saved outside the configured captures directory"
        ) from exc
    return build_capture_image(project_root, output_path)


def record_from_web(project_root: Path) -> dict[str, object]:
    output_path = record_video(video_settings_from_env(project_root))
    try:
        output_path.relative_to(captures_root(project_root))
    except ValueError as exc:
        raise RuntimeError(
            "Recording was saved outside the configured captures directory"
        ) from exc
    return build_capture_image(project_root, output_path)


def remove_empty_capture_dirs(project_root: Path, start: Path) -> None:
    root = captures_root(project_root).resolve()
    current = start.resolve()
    while current != root:
        try:
            current.relative_to(root)
        except ValueError:
            return
        try:
            current.rmdir()
        except OSError:
            return
        current = current.parent


def delete_capture_image(
    project_root: Path, relative_path: str
) -> dict[str, object] | None:
    image_path = get_capture_image_by_relative_path(project_root, relative_path)
    if image_path is None:
        return None
    root = captures_root(project_root).resolve()
    deleted_path = image_path.relative_to(root).as_posix()
    deleted_name = image_path.name
    image_path.unlink()
    if media_type_for(image_path) == "video":
        video_poster_path(image_path).unlink(missing_ok=True)
    delete_capture_metadata(image_path)
    remove_empty_capture_dirs(project_root, image_path.parent)
    return {
        "ok": True,
        "filename": deleted_name,
        "relative_path": deleted_path,
    }


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
    latest = (
        images[0].relative_to(captures_root(project_root)).as_posix()
        if images
        else None
    )
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


def render_page(page_name: str = "home") -> bytes:
    page = """
    <!doctype html>
    <html lang="en">
      <head>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <meta name="theme-color" content="#f7f7f4">
        <title>Suv's Tiny Film Camera</title>
        <style>
          :root {
            color-scheme: light;
            --bg: #f3efe7;
            --surface: #fffdf8;
            --surface-strong: #fff;
            --fg: #1d1b17;
            --muted: #706c63;
            --line: #d9d2c5;
            --accent: #e34f32;
            --accent-dark: #a82f1e;
            --gold: #f3b83f;
            --blue: #4b78c2;
            --shadow: 0 18px 45px rgba(58, 44, 27, 0.09);
          }
          * { box-sizing: border-box; }
          body {
            margin: 0;
            background:
              radial-gradient(circle at 8% -8%, rgba(243, 184, 63, 0.2), transparent 27rem),
              var(--bg);
            color: var(--fg);
            font-family: ui-monospace, "SFMono-Regular", "SF Mono", Consolas, "Liberation Mono", Menlo, monospace;
          }
          main {
            width: min(1080px, 100%);
            margin: 0 auto;
            padding: 20px;
          }
          header {
            display: flex;
            align-items: center;
            justify-content: space-between;
            gap: 18px;
            padding: 9px 0 42px;
          }
          body[data-page="home"] .gallery-only { display: none; }
          body[data-page="gallery"] .home-only { display: none; }
          body[data-page="gallery"] .gallery-only { display: inline-flex; }
          body[data-page="gallery"] header { padding-bottom: 20px; }
          body[data-page="gallery"] .gallery-section {
            border-top: 0;
            padding-top: 6px;
          }
          h1, h2, p { margin: 0; }
          h1 {
            font-size: 20px;
            font-weight: 650;
            letter-spacing: 0;
          }
          h2 { font-size: 22px; line-height: 1.1; font-weight: 650; letter-spacing: 0; }
          section {
            border-top: 1px solid var(--line);
            padding: 20px 0 38px;
          }
          .status {
            color: var(--muted);
            font-size: 14px;
          }
          .visually-hidden {
            border: 0;
            clip: rect(0 0 0 0);
            clip-path: inset(50%);
            height: 1px;
            margin: -1px;
            overflow: hidden;
            padding: 0;
            position: absolute;
            white-space: nowrap;
            width: 1px;
          }
          .latest {
            display: grid;
            gap: 16px;
          }
          .latest-frame {
            min-height: 340px;
            border: 1px solid var(--line);
            border-radius: 20px;
            background: var(--surface-strong);
            display: grid;
            place-items: center;
            overflow: hidden;
            position: relative;
            box-shadow: var(--shadow);
          }
          .latest-frame img,
          .latest-frame video {
            display: block;
            width: 100%;
            max-height: 68vh;
            object-fit: contain;
          }
          .empty {
            color: var(--muted);
            padding: 42px 16px;
            text-align: center;
          }
          .media-error {
            color: var(--muted);
            display: grid;
            gap: 12px;
            justify-items: center;
            max-width: 380px;
            padding: 44px 24px;
            text-align: center;
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
          a.button,
          button.button {
            appearance: none;
            align-items: center;
            background: var(--surface);
            border: 1px solid var(--fg);
            border-radius: 999px;
            color: var(--fg);
            display: inline-flex;
            font-size: 14px;
            font-weight: 600;
            gap: 8px;
            padding: 8px 13px;
            text-decoration: none;
            white-space: nowrap;
          }
          button.button {
            cursor: pointer;
            font-family: inherit;
          }
          a.button.primary,
          button.button.primary {
            background: var(--accent);
            border-color: var(--accent-dark);
            color: #fff;
          }
          .button svg {
            display: block;
            fill: none;
            height: 18px;
            stroke: currentColor;
            stroke-linecap: round;
            stroke-linejoin: round;
            stroke-width: 2;
            width: 18px;
          }
          .button.record svg {
            color: var(--accent);
            fill: currentColor;
            stroke: none;
          }
          .button.primary svg {
            color: #ffe7d8;
          }
          button.button:disabled {
            cursor: wait;
            opacity: 0.55;
          }
          .actions {
            align-items: center;
            display: flex;
            gap: 8px;
            flex-wrap: wrap;
            justify-content: flex-end;
          }
          .filter-summary {
            align-items: center;
            background: rgba(255, 253, 248, 0.82);
            border: 1px solid var(--line);
            border-radius: 18px;
            display: grid;
            gap: 16px;
            grid-template-columns: minmax(145px, 0.72fr) minmax(0, 2fr);
            padding: 14px;
          }
          .filter-summary.warning {
            border-color: rgba(227, 79, 50, 0.55);
          }
          .mode-copy {
            display: grid;
            gap: 3px;
            padding: 0 4px;
          }
          .eyebrow {
            color: var(--muted);
            font-size: 11px;
            letter-spacing: 0.08em;
            text-transform: uppercase;
          }
          .mode-options {
            display: grid;
            gap: 8px;
            grid-template-columns: repeat(3, minmax(0, 1fr));
          }
          .mode-option {
            align-items: center;
            border: 1px solid transparent;
            border-radius: 13px;
            color: var(--muted);
            display: flex;
            gap: 8px;
            min-width: 0;
            padding: 8px;
          }
          .mode-option.active {
            background: var(--surface-strong);
            border-color: var(--line);
            box-shadow: 0 5px 14px rgba(58, 44, 27, 0.08);
            color: var(--fg);
            font-weight: 650;
          }
          .mode-icon {
            align-items: center;
            border-radius: 10px;
            display: inline-flex;
            flex: 0 0 auto;
            height: 34px;
            justify-content: center;
            width: 34px;
          }
          .mode-icon svg {
            display: block;
            fill: none;
            height: 19px;
            stroke: currentColor;
            stroke-linecap: round;
            stroke-linejoin: round;
            stroke-width: 1.9;
            width: 19px;
          }
          [data-filter="black_and_white"] .mode-icon {
            background: #34343a;
            color: #fff;
          }
          [data-filter="normal"] .mode-icon {
            background: #ffe1a0;
            color: #9a5d00;
          }
          [data-filter="cool"] .mode-icon {
            background: #dce9ff;
            color: #285ba9;
          }
          .battery-summary {
            align-items: center;
            color: #367552;
            display: inline-flex;
            flex: 0 0 auto;
            font-size: 14px;
            font-weight: 650;
            gap: 7px;
            white-space: nowrap;
          }
          .battery-summary.warning {
            color: var(--accent);
          }
          .battery-summary svg {
            display: block;
            fill: none;
            height: 22px;
            stroke: currentColor;
            stroke-linecap: round;
            stroke-linejoin: round;
            stroke-width: 2;
            width: 22px;
          }
          .section-heading {
            display: flex;
            align-items: baseline;
            justify-content: space-between;
            gap: 16px;
            margin-bottom: 14px;
          }
          .gallery-heading-actions {
            align-items: center;
            display: flex;
            flex-wrap: wrap;
            gap: 10px;
          }
          .latest .section-heading {
            margin-bottom: 0;
          }
          .capture-browser {
            display: grid;
            gap: 14px;
            grid-template-columns: repeat(auto-fill, minmax(148px, 1fr));
          }
          .gallery-item {
            contain-intrinsic-size: auto 150px;
            content-visibility: auto;
            display: grid;
            gap: 7px;
            min-width: 0;
            overflow: hidden;
            position: relative;
          }
          .gallery-preview {
            appearance: none;
            background: transparent;
            border: 0;
            color: var(--fg);
            cursor: pointer;
            display: grid;
            font-family: inherit;
            gap: 7px;
            min-width: 0;
            padding: 0;
            text-align: left;
            width: 100%;
          }
          .gallery-thumb {
            aspect-ratio: 4 / 3;
            background: #e8e2d8;
            border: 2px solid transparent;
            border-radius: 14px;
            display: grid;
            overflow: hidden;
            place-items: center;
            position: relative;
            transition: border-color 140ms ease, transform 140ms ease;
          }
          .gallery-item:hover .gallery-thumb {
            transform: translateY(-2px);
          }
          .gallery-item.selected .gallery-thumb {
            border-color: var(--blue);
          }
          .gallery-thumb img {
            display: block;
            height: 100%;
            width: 100%;
            object-fit: cover;
          }
          .gallery-load {
            align-items: center;
            color: var(--muted);
            display: flex;
            flex-direction: column;
            font-size: 12px;
            gap: 7px;
          }
          .gallery-load svg {
            fill: none;
            height: 28px;
            stroke: currentColor;
            stroke-linecap: round;
            stroke-linejoin: round;
            stroke-width: 1.7;
            width: 28px;
          }
          .gallery-video {
            align-content: center;
            background: linear-gradient(145deg, #272b36, #46506c);
            color: #fff;
            display: grid;
            height: 100%;
            justify-items: center;
            width: 100%;
          }
          .gallery-video svg {
            fill: rgba(255, 255, 255, 0.22);
            height: 42px;
            stroke: #fff;
            stroke-linejoin: round;
            stroke-width: 1.5;
            width: 42px;
          }
          .media-badge {
            align-items: center;
            -webkit-backdrop-filter: blur(8px);
            backdrop-filter: blur(8px);
            background: rgba(20, 20, 20, 0.72);
            border-radius: 999px;
            bottom: 7px;
            color: #fff;
            display: inline-flex;
            font-size: 10px;
            gap: 4px;
            padding: 4px 7px;
            position: absolute;
            right: 7px;
          }
          .media-badge svg {
            fill: currentColor;
            height: 9px;
            stroke: none;
            width: 9px;
          }
          .gallery-caption {
            color: var(--muted);
            font-size: 11px;
            overflow: hidden;
            padding: 0 2px;
            text-overflow: ellipsis;
            white-space: nowrap;
          }
          .capture-info {
            display: grid;
            grid-template-columns: minmax(0, 1fr) auto;
            gap: 12px;
            align-items: center;
          }
          .capture-controls {
            display: flex;
            align-items: center;
            gap: 8px;
          }
          a.icon-button,
          button.icon-button {
            appearance: none;
            align-items: center;
            background: transparent;
            border: 1px solid var(--fg);
            border-radius: 50%;
            color: var(--fg);
            cursor: pointer;
            display: inline-flex;
            flex: 0 0 auto;
            height: 42px;
            justify-content: center;
            padding: 0;
            text-decoration: none;
            width: 42px;
          }
          button.icon-button {
            font-family: inherit;
          }
          .capture-stage .icon-button {
            background: rgba(247, 247, 244, 0.94);
            margin: 0 8px;
          }
          .icon-button svg {
            display: block;
            fill: none;
            height: 20px;
            stroke: currentColor;
            stroke-linecap: round;
            stroke-linejoin: round;
            stroke-width: 2;
            width: 20px;
          }
          button.icon-button:disabled {
            cursor: default;
            opacity: 0.35;
          }
          .icon-button.danger {
            border-color: var(--accent);
            color: var(--accent);
          }
          .gallery-preview:focus-visible,
          .button:focus-visible,
          .icon-button:focus-visible {
            outline: 3px solid rgba(75, 120, 194, 0.4);
            outline-offset: 3px;
          }
          .details {
            display: grid;
            border-top: 1px solid var(--line);
          }
          .metric-grid {
            display: grid;
            border-bottom: 1px solid var(--line);
          }
          .metric-grid.primary {
            grid-template-columns: repeat(2, minmax(0, 1fr));
          }
          .metric-grid.secondary {
            grid-template-columns: repeat(3, minmax(0, 1fr));
          }
          .metric {
            min-width: 0;
            padding: 13px 14px;
            border-right: 1px solid var(--line);
          }
          .metric:last-child {
            border-right: 0;
          }
          .metric .value {
            margin-top: 4px;
          }
          .detail {
            display: grid;
            grid-template-columns: 140px 1fr;
            gap: 16px;
            padding: 13px 14px;
            border-bottom: 1px solid var(--line);
          }
          .label {
            color: var(--muted);
            font-size: 12px;
          }
          .value {
            font-size: 13px;
            overflow-wrap: anywhere;
          }
          .value.warning {
            color: var(--accent);
            font-weight: 600;
          }
          @media (max-width: 640px) {
            main { padding: 14px; }
            header {
              align-items: flex-start;
              padding-bottom: 34px;
            }
            h1 { font-size: 18px; }
            .section-heading {
              align-items: flex-start;
              flex-direction: column;
            }
            .gallery-heading-actions { width: 100%; }
            .actions { justify-content: flex-start; }
            .filter-summary {
              align-items: stretch;
              gap: 10px;
              grid-template-columns: 1fr;
              padding: 11px 12px;
            }
            .mode-copy {
              display: block;
            }
            .mode-option {
              flex-direction: column;
              font-size: 10px;
              gap: 4px;
              justify-content: center;
              padding: 5px 3px;
              text-align: center;
            }
            .mode-icon { height: 30px; width: 30px; }
            .latest-frame { min-height: 220px; }
            .capture-browser {
              gap: 11px 8px;
              grid-template-columns: repeat(3, minmax(0, 1fr));
            }
            .gallery-thumb { border-radius: 10px; }
            .capture-info { grid-template-columns: minmax(0, 1fr) auto; }
            .capture-info .name { font-size: 12px; }
            .capture-info .meta { font-size: 10px; }
            .icon-button { height: 38px; width: 38px; }
            .metric { padding: 13px 10px; }
            .detail { grid-template-columns: 1fr; gap: 3px; }
          }
          @media (prefers-reduced-motion: reduce) {
            .gallery-thumb { transition: none; }
          }
        </style>
      </head>
      <body data-page="__PAGE_NAME__">
        <main>
          <p class="status visually-hidden" id="status" aria-live="polite">Checking captures...</p>
          <header>
            <h1 id="page-title">Suv's Tiny Film Camera</h1>
            <a class="button gallery-only" href="/" id="back-button">
              <svg viewBox="0 0 24 24" aria-hidden="true"><path d="m15 18-6-6 6-6"></path></svg>
              Back
            </a>
            <div class="battery-summary home-only" id="battery-summary" aria-label="Battery unavailable" title="Battery unavailable">
              <svg viewBox="0 0 24 24" aria-hidden="true">
                <path d="M20 10v4"></path>
                <rect x="3" y="7" width="15" height="10" rx="2"></rect>
                <path d="M7 11h6"></path>
              </svg>
              <span id="battery-summary-percent">--%</span>
            </div>
          </header>

          <section class="latest home-only">
            <div class="section-heading">
              <div class="actions">
                <button class="button record" id="record-button" type="button">
                  <svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="7"></circle></svg>
                  <span id="record-button-label">Record 10s</span>
                </button>
                <button class="button primary" id="capture-button" type="button">
                  <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M4 7h3l2-3h6l2 3h3a2 2 0 0 1 2 2v9a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V9a2 2 0 0 1 2-2Z"></path><circle cx="12" cy="13" r="4"></circle></svg>
                  <span id="capture-button-label">Take Photo</span>
                </button>
              </div>
            </div>
            <div class="filter-summary warning" id="filter-summary" aria-live="polite">
              <div class="mode-copy">
                <span class="eyebrow">Current photo mode</span>
              </div>
              <div class="mode-options" role="list" aria-label="Available photo modes">
                <div class="mode-option" data-filter="black_and_white" role="listitem">
                  <span class="mode-icon">
                    <svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="8"></circle><path d="M12 4a8 8 0 0 1 0 16Z"></path></svg>
                  </span>
                  <span>Black &amp; white</span>
                </div>
                <div class="mode-option" data-filter="normal" role="listitem">
                  <span class="mode-icon">
                    <svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="4"></circle><path d="M12 2v2M12 20v2M4.93 4.93l1.42 1.42M17.66 17.66l1.41 1.41M2 12h2M20 12h2M4.93 19.07l1.42-1.42M17.66 6.34l1.41-1.41"></path></svg>
                  </span>
                  <span>Normal</span>
                </div>
                <div class="mode-option" data-filter="cool" role="listitem">
                  <span class="mode-icon">
                    <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 2v20M4 6l16 12M20 6 4 18M8.5 4 12 6l3.5-2M8.5 20l3.5-2 3.5 2M3.5 10 7 12l-3.5 2M20.5 10 17 12l3.5 2"></path></svg>
                  </span>
                  <span>Cool</span>
                </div>
              </div>
            </div>
            <div class="latest-frame" id="latest-frame"></div>
            <div class="capture-info" id="capture-info"></div>
          </section>

          <section class="gallery-section">
            <div class="section-heading">
              <h2>Gallery</h2>
              <div class="gallery-heading-actions">
                <p class="status" id="gallery-count"></p>
                <a class="button home-only" href="/gallery" id="view-gallery-button">View Gallery</a>
              </div>
            </div>
            <div class="capture-browser" id="capture-browser"></div>
          </section>

          <section class="home-only">
            <h2>Battery</h2>
            <div class="details" id="battery-details"></div>
          </section>

          <section class="home-only">
            <h2>Device</h2>
            <div class="details" id="device-details"></div>
          </section>
        </main>

        <script>
          const isGalleryPage = document.body.dataset.page === "gallery";
          const HOME_GALLERY_LIMIT = __HOME_GALLERY_LIMIT__;
          const INITIAL_THUMBNAIL_LIMIT = 3;
          const statusElement = document.getElementById("status");
          const latestFrame = document.getElementById("latest-frame");
          const captureInfo = document.getElementById("capture-info");
          const captureBrowser = document.getElementById("capture-browser");
          const galleryCount = document.getElementById("gallery-count");
          const deviceDetails = document.getElementById("device-details");
          const batteryDetails = document.getElementById("battery-details");
          const batterySummary = document.getElementById("battery-summary");
          const batterySummaryPercent = document.getElementById("battery-summary-percent");
          const captureButton = document.getElementById("capture-button");
          const captureButtonLabel = document.getElementById("capture-button-label");
          const recordButton = document.getElementById("record-button");
          const recordButtonLabel = document.getElementById("record-button-label");
          const filterSummary = document.getElementById("filter-summary");
          const modeOptions = Array.from(document.querySelectorAll(".mode-option"));
          let captureImages = [];
          const loadedThumbnailPaths = new Set();
          let totalCaptureCount = 0;
          let selectedCaptureIndex = 0;
          let renderedCaptureKey = "";
          let renderedGalleryKey = "";

          if (isGalleryPage) {
            document.title = "Gallery · Suv's Tiny Film Camera";
          }

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

          function formatFixed(value, digits, unit) {
            const number = Number(value);
            if (!Number.isFinite(number)) return "";
            return `${number.toFixed(digits)} ${unit}`;
          }

          function formatPercent(value) {
            const number = Number(value);
            if (!Number.isFinite(number)) return "";
            return `${number.toFixed(1)}%`;
          }

          function titleCase(value) {
            if (!value) return "";
            return String(value).replace(/\\b\\w/g, (letter) => letter.toUpperCase());
          }

          function iconSvg(name) {
            const icons = {
              delete: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M3 6h18"></path><path d="M8 6V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path><path d="M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6"></path><path d="M10 11v6"></path><path d="M14 11v6"></path></svg>',
              download: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path><path d="M7 10l5 5 5-5"></path><path d="M12 15V3"></path></svg>',
              load: '<svg viewBox="0 0 24 24" aria-hidden="true"><rect x="3" y="4" width="18" height="16" rx="2"></rect><path d="m3 16 5-5 4 4 3-3 6 6"></path></svg>',
              video: '<svg viewBox="0 0 24 24" aria-hidden="true"><rect x="3" y="5" width="13" height="14" rx="2"></rect><path d="m16 10 5-3v10l-5-3Z"></path></svg>',
              play: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="m9 7 8 5-8 5Z"></path></svg>',
            };
            return icons[name] || "";
          }

          function makeIconButton(tagName, iconName, label) {
            const element = document.createElement(tagName);
            element.className = "icon-button";
            element.title = label;
            element.setAttribute("aria-label", label);
            element.innerHTML = iconSvg(iconName);
            if (tagName === "button") {
              element.type = "button";
            }
            return element;
          }

          function selectCapture(index) {
            if (index < 0 || index >= captureImages.length) return;
            selectedCaptureIndex = index;
            renderSelectedCapture();
            renderGallery();
          }

          function clampCaptureIndex(index, images) {
            if (!images.length) return 0;
            return Math.max(0, Math.min(index, images.length - 1));
          }

          function renderCaptureInfo(image) {
            captureInfo.innerHTML = "";
            const text = document.createElement("div");
            const name = document.createElement("div");
            name.className = "name";
            name.textContent = image.relative_path || image.filename;
            const meta = document.createElement("span");
            meta.className = "meta";
            const filterLabel = image.photo_filter && image.photo_filter.label
              ? image.photo_filter.label
              : "";
            meta.textContent = [formatDate(image.modified_unix), formatBytes(image.size_bytes), filterLabel]
              .filter(Boolean)
              .join(" / ");
            text.append(name, meta);

            const controls = document.createElement("div");
            controls.className = "capture-controls";
            const downloadLink = makeIconButton("a", "download", `Download ${image.filename || "capture"}`);
            downloadLink.href = image.download_url;
            downloadLink.download = image.filename || "capture.jpg";
            const deleteButton = makeIconButton("button", "delete", `Delete ${image.filename || "capture"}`);
            deleteButton.classList.add("danger");
            deleteButton.addEventListener("click", () => {
              deleteCapture(image);
            });
            controls.append(downloadLink, deleteButton);
            captureInfo.append(text, controls);
          }

          function renderMediaError(image) {
            const error = document.createElement("div");
            error.className = "media-error";
            const message = document.createElement("p");
            message.textContent = "This video could not be played in the browser.";
            const downloadLink = document.createElement("a");
            downloadLink.className = "button";
            downloadLink.href = image.download_url;
            downloadLink.download = image.filename || "capture.mp4";
            downloadLink.textContent = "Download video instead";
            error.append(message, downloadLink);
            latestFrame.replaceChildren(error);
          }

          function renderSelectedCapture(force = false) {
            if (!captureImages.length) {
              renderedCaptureKey = "";
              latestFrame.innerHTML = '<div class="empty">No captures yet.</div>';
              captureInfo.innerHTML = "";
              return;
            }

            const image = captureImages[selectedCaptureIndex];
            const viewUrl = image.view_url || image.download_url || "";
            const captureKey = `${image.relative_path || image.filename}:${image.modified_unix || ""}`;
            if (!force && renderedCaptureKey === captureKey) return;

            renderedCaptureKey = captureKey;
            latestFrame.innerHTML = "";
            const previewSrc = `${viewUrl}?v=${encodeURIComponent(image.modified_unix || "")}`;
            let preview;
            if (image.media_type === "video") {
              preview = document.createElement("video");
              preview.controls = true;
              preview.playsInline = true;
              preview.setAttribute("playsinline", "");
              preview.preload = "auto";
              if (image.poster_url) {
                preview.poster = `${image.poster_url}?v=${encodeURIComponent(image.modified_unix || "")}`;
              }
              preview.src = `${previewSrc}#t=0.001`;
              preview.addEventListener("error", () => renderMediaError(image), { once: true });
            } else {
              preview = document.createElement("img");
              preview.src = previewSrc;
              preview.alt = image.filename || "Capture";
              preview.decoding = "async";
            }
            latestFrame.appendChild(preview);
            renderCaptureInfo(image);
          }

          function renderGallery() {
            const galleryKey = `${isGalleryPage}:${selectedCaptureIndex}:${captureImages
              .map((image) => `${image.relative_path}:${image.modified_unix}`)
              .join("|")}`;
            if (renderedGalleryKey === galleryKey) return;

            renderedGalleryKey = galleryKey;
            captureBrowser.innerHTML = "";
            galleryCount.textContent = totalCaptureCount
              ? !isGalleryPage && totalCaptureCount > captureImages.length
                ? `Showing ${captureImages.length} of ${totalCaptureCount} items`
                : `${totalCaptureCount} item${totalCaptureCount === 1 ? "" : "s"}`
              : "";
            if (!captureImages.length) {
              captureBrowser.innerHTML = '<div class="empty">No captures yet.</div>';
              return;
            }

            const fragment = document.createDocumentFragment();
            captureImages.forEach((image, index) => {
              const item = document.createElement("div");
              item.className = [
                "gallery-item",
                !isGalleryPage && index === selectedCaptureIndex ? "selected" : "",
              ].filter(Boolean).join(" ");

              const previewButton = document.createElement("button");
              previewButton.type = "button";
              previewButton.className = "gallery-preview";
              previewButton.setAttribute(
                "aria-label",
                `Preview ${image.filename || "capture"}`,
              );

              const thumb = document.createElement("span");
              thumb.className = "gallery-thumb";
              let thumbnailLoaded = image.media_type === "video"
                || index < INITIAL_THUMBNAIL_LIMIT
                || loadedThumbnailPaths.has(image.relative_path);
              const loadThumbnail = () => {
                if (thumbnailLoaded || image.media_type === "video") return;
                const thumbnail = document.createElement("img");
                const viewUrl = image.view_url || image.download_url || "";
                thumbnail.src = `${viewUrl}?v=${encodeURIComponent(image.modified_unix || "")}`;
                thumbnail.alt = "";
                thumbnail.decoding = "async";
                thumb.replaceChildren(thumbnail);
                loadedThumbnailPaths.add(image.relative_path);
                thumbnailLoaded = true;
                previewButton.setAttribute("aria-label", `Preview ${image.filename || "capture"}`);
              };
              if (image.media_type === "video") {
                const videoTile = document.createElement("span");
                videoTile.className = "gallery-video";
                videoTile.innerHTML = iconSvg("video");
                const badge = document.createElement("span");
                badge.className = "media-badge";
                badge.innerHTML = `${iconSvg("play")} Video`;
                thumb.append(videoTile, badge);
              } else if (thumbnailLoaded) {
                const thumbnail = document.createElement("img");
                const viewUrl = image.view_url || image.download_url || "";
                thumbnail.src = `${viewUrl}?v=${encodeURIComponent(image.modified_unix || "")}`;
                thumbnail.alt = "";
                thumbnail.loading = "lazy";
                thumbnail.decoding = "async";
                thumb.appendChild(thumbnail);
              } else {
                const loadPrompt = document.createElement("span");
                loadPrompt.className = "gallery-load";
                loadPrompt.innerHTML = `${iconSvg("load")}<span>Load image</span>`;
                thumb.appendChild(loadPrompt);
                previewButton.setAttribute(
                  "aria-label",
                  `Load ${image.filename || "capture"}`,
                );
              }

              const caption = document.createElement("span");
              caption.className = "gallery-caption";
              caption.textContent = image.filename || image.relative_path || "Capture";
              previewButton.append(thumb, caption);
              previewButton.addEventListener("click", () => {
                if (!thumbnailLoaded && image.media_type !== "video") {
                  loadThumbnail();
                  return;
                }
                if (isGalleryPage) {
                  window.open(image.view_url, "_blank", "noopener");
                  return;
                }
                selectCapture(index);
                latestFrame.scrollIntoView({ block: "center" });
              });
              item.appendChild(previewButton);
              fragment.appendChild(item);
            });
            captureBrowser.appendChild(fragment);
          }

          function renderImages(images, options = {}) {
            const previousSelection = captureImages[selectedCaptureIndex];
            const previousPath = previousSelection && previousSelection.relative_path;
            captureImages = images;
            totalCaptureCount = Number.isFinite(options.totalImages) ? options.totalImages : images.length;
            if (Number.isFinite(options.selectedIndex)) {
              selectedCaptureIndex = clampCaptureIndex(options.selectedIndex, captureImages);
            } else if (options.selectLatest) {
              selectedCaptureIndex = 0;
            } else {
              const preservedIndex = previousPath
                ? captureImages.findIndex((image) => image.relative_path === previousPath)
                : selectedCaptureIndex;
              selectedCaptureIndex = preservedIndex >= 0
                ? clampCaptureIndex(preservedIndex, captureImages)
                : 0;
            }

            statusElement.textContent = `${totalCaptureCount} capture${totalCaptureCount === 1 ? "" : "s"}`;
            renderSelectedCapture();
            renderGallery();
          }

          function renderDetails(details) {
            const rows = [
              ["App URL", details.app_url],
              ["Storage", details.storage_status],
            ];
            deviceDetails.innerHTML = "";
            rows.forEach(([label, value]) => {
              deviceDetails.appendChild(makeDetailRow(label, value));
            });
          }

          function renderBattery(details) {
            renderBatterySummary(details);
            batteryDetails.innerHTML = "";
            if (details.ok) {
              const primaryMetrics = [
                ["Charge", formatPercent(details.percent_remaining), details.stale],
                ["State", titleCase(details.state), details.stale],
              ];
              const secondaryMetrics = [
                ["Voltage", formatFixed(details.load_voltage_v, 3, "V"), false],
                ["Current", formatFixed(details.current_a, 3, "A"), false],
                ["Power", formatFixed(details.power_w, 3, "W"), false],
              ];
              batteryDetails.appendChild(makeMetricGrid(primaryMetrics, "primary"));
              batteryDetails.appendChild(makeMetricGrid(secondaryMetrics, "secondary"));
              batteryDetails.appendChild(makeDetailRow("Updated", formatDate(details.timestamp_unix), details.stale));
              return;
            }

            [
              ["Status", "Unavailable", true],
              ["Error", details.error, true],
              ["Updated", formatDate(details.timestamp_unix), details.stale],
            ].forEach(([label, value, warning]) => {
              batteryDetails.appendChild(makeDetailRow(label, value, warning));
            });
          }

          function makeMetricGrid(metrics, className) {
            const metricGrid = document.createElement("div");
            metricGrid.className = `metric-grid ${className}`;
            metrics.forEach(([label, value, warning]) => {
              metricGrid.appendChild(makeMetric(label, value, warning));
            });
            return metricGrid;
          }

          function makeMetric(label, value, warning = false) {
            const metric = document.createElement("div");
            metric.className = "metric";
            const labelElement = document.createElement("div");
            labelElement.className = "label";
            labelElement.textContent = label;
            const valueElement = document.createElement("div");
            valueElement.className = warning ? "value warning" : "value";
            valueElement.textContent = value === null || value === undefined || value === "" ? "Unknown" : value;
            metric.append(labelElement, valueElement);
            return metric;
          }

          function makeDetailRow(label, value, warning = false) {
            const row = document.createElement("div");
            row.className = "detail";
            const labelElement = document.createElement("div");
            labelElement.className = "label";
            labelElement.textContent = label;
            const valueElement = document.createElement("div");
            valueElement.className = warning ? "value warning" : "value";
            valueElement.textContent = value === null || value === undefined || value === "" ? "Unknown" : value;
            row.append(labelElement, valueElement);
            return row;
          }

          function renderBatterySummary(details) {
            const percent = details.ok ? formatPercent(details.percent_remaining) : "";
            const label = percent ? `Battery ${percent}` : "Battery unavailable";
            batterySummaryPercent.textContent = percent || "--%";
            batterySummary.className = details.ok && !details.stale ? "battery-summary" : "battery-summary warning";
            batterySummary.setAttribute("aria-label", label);
            batterySummary.title = label;
          }

          function renderFilter(details) {
            const activeFilter = details.active_filter || {};
            const label = activeFilter.label || "Normal";
            const activeFilterId = activeFilter.id || "normal";
            const warning = Boolean(details.using_fallback || details.stale || !details.ok);
            filterSummary.className = warning ? "filter-summary warning" : "filter-summary";
            const summary = warning
              ? details.error || "Filter switch unavailable; using Normal"
              : `Current mode: ${label}`;
            filterSummary.title = summary;
            filterSummary.setAttribute(
              "aria-label",
              warning ? `Current photo mode: ${label}. ${summary}` : `Current photo mode: ${label}`,
            );
            modeOptions.forEach((option) => {
              const active = option.dataset.filter === activeFilterId;
              option.classList.toggle("active", active);
              option.setAttribute("aria-current", active ? "true" : "false");
            });
          }

          async function refreshImages(options = {}) {
            const imagesUrl = isGalleryPage ? "/api/images" : `/api/images?limit=${HOME_GALLERY_LIMIT}`;
            const response = await fetch(imagesUrl, { cache: "no-store" });
            if (!response.ok) throw new Error("Image request failed");
            const data = await response.json();
            renderImages(data.images || [], { ...options, totalImages: data.total });
          }

          async function deleteCapture(image) {
            if (!image || !image.delete_url) return;
            const name = image.relative_path || image.filename || "this capture";
            if (!window.confirm(`Delete ${name}?`)) return;

            const deleteIndex = selectedCaptureIndex;
            statusElement.textContent = `Deleting ${name}...`;
            try {
              const response = await fetch(image.delete_url, {
                method: "DELETE",
                cache: "no-store",
              });
              const data = await response.json().catch(() => ({}));
              if (!response.ok) {
                throw new Error(data.error || "Delete failed");
              }
              const nextIndex = Math.min(deleteIndex, Math.max(0, captureImages.length - 2));
              await refreshImages({ selectedIndex: nextIndex });
              await refreshDetails();
              statusElement.textContent = `Deleted ${name}`;
            } catch (error) {
              statusElement.textContent = error instanceof Error ? error.message : "Delete failed";
            }
          }

          async function refreshDetails() {
            const response = await fetch("/api/device-details", { cache: "no-store" });
            if (!response.ok) throw new Error("Device request failed");
            renderDetails(await response.json());
          }

          async function refreshBattery() {
            const response = await fetch("/api/battery", { cache: "no-store" });
            if (!response.ok) throw new Error("Battery request failed");
            renderBattery(await response.json());
          }

          async function refreshFilter() {
            const response = await fetch("/api/filter", { cache: "no-store" });
            if (!response.ok) throw new Error("Filter request failed");
            renderFilter(await response.json());
          }

          async function takePhoto() {
            if (captureButton.disabled) return;
            const wasRecordDisabled = recordButton.disabled;
            captureButton.disabled = true;
            recordButton.disabled = true;
            captureButtonLabel.textContent = "Taking...";
            statusElement.textContent = "Taking photo...";
            try {
              const response = await fetch("/api/capture", {
                method: "POST",
                cache: "no-store",
              });
              const data = await response.json().catch(() => ({}));
              if (!response.ok) {
                throw new Error(data.error || "Capture failed");
              }
              await refreshImages({ selectLatest: true });
              await refreshDetails();
              const savedPath = data.image && data.image.relative_path ? data.image.relative_path : "photo";
              statusElement.textContent = `Saved ${savedPath}`;
            } catch (error) {
              statusElement.textContent = error instanceof Error ? error.message : "Capture failed";
            } finally {
              captureButton.disabled = false;
              recordButton.disabled = wasRecordDisabled;
              captureButtonLabel.textContent = "Take Photo";
            }
          }

          async function recordVideo() {
            if (recordButton.disabled) return;
            const wasCaptureDisabled = captureButton.disabled;
            recordButton.disabled = true;
            captureButton.disabled = true;
            recordButtonLabel.textContent = "Recording...";
            statusElement.textContent = "Recording video...";
            try {
              const response = await fetch("/api/record", {
                method: "POST",
                cache: "no-store",
              });
              const data = await response.json().catch(() => ({}));
              if (!response.ok) {
                throw new Error(data.error || "Recording failed");
              }
              await refreshImages({ selectLatest: true });
              await refreshDetails();
              const savedPath = data.image && data.image.relative_path ? data.image.relative_path : "video";
              statusElement.textContent = `Saved ${savedPath}`;
            } catch (error) {
              statusElement.textContent = error instanceof Error ? error.message : "Recording failed";
            } finally {
              recordButton.disabled = false;
              captureButton.disabled = wasCaptureDisabled;
              recordButtonLabel.textContent = "Record 10s";
            }
          }

          refreshImages().catch(() => {
            statusElement.textContent = "Could not load captures.";
          });
          setInterval(() => refreshImages().catch(() => {}), 5000);
          if (!isGalleryPage) {
            captureButton.addEventListener("click", () => {
              takePhoto();
            });
            recordButton.addEventListener("click", () => {
              recordVideo();
            });
            refreshDetails().catch(() => {});
            refreshBattery().catch(() => {
              renderBattery({ ok: false, error: "Could not load battery details.", stale: true });
            });
            refreshFilter().catch(() => {
              renderFilter({ ok: false, error: "Could not load filter switch.", stale: true, using_fallback: true });
            });
            setInterval(() => refreshDetails().catch(() => {}), 5000);
            setInterval(() => refreshBattery().catch(() => {}), 5000);
            setInterval(() => refreshFilter().catch(() => {}), 1000);
          }
        </script>
      </body>
    </html>
    """
    return (
        page.replace("__PAGE_NAME__", page_name)
        .replace("__HOME_GALLERY_LIMIT__", str(HOME_GALLERY_LIMIT))
        .encode("utf-8")
    )


def attachment_header(filename: str) -> str:
    safe_filename = filename.replace("\\", "_").replace('"', "_")
    return f'attachment; filename="{safe_filename}"'


def parse_byte_range_header(
    value: str | None, file_size: int
) -> tuple[int, int] | None:
    """Parse one HTTP byte range and return its inclusive bounds."""
    if value is None:
        return None
    if file_size <= 0 or not value.startswith("bytes="):
        raise ValueError("Invalid byte range")

    requested_range = value[len("bytes=") :].strip()
    if not requested_range or "," in requested_range:
        raise ValueError("Only one byte range is supported")

    start_text, separator, end_text = requested_range.partition("-")
    if not separator or (not start_text and not end_text):
        raise ValueError("Invalid byte range")

    if start_text:
        start = int(start_text)
        end = int(end_text) if end_text else file_size - 1
        if start < 0 or start >= file_size or end < start:
            raise ValueError("Byte range is outside the file")
        return start, min(end, file_size - 1)

    suffix_length = int(end_text)
    if suffix_length <= 0:
        raise ValueError("Invalid suffix byte range")
    return max(0, file_size - suffix_length), file_size - 1


def build_handler(project_root: Path, port: int):
    class TinyFilmHandler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

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

        def _send_json(
            self,
            payload: dict[str, object],
            status: HTTPStatus = HTTPStatus.OK,
        ) -> None:
            self._send_bytes(
                json.dumps(payload).encode("utf-8"),
                "application/json; charset=utf-8",
                status=status,
            )

        def _serve_capture(
            self,
            image_path: Path,
            as_attachment: bool = True,
            include_body: bool = True,
        ) -> None:
            stat = image_path.stat()
            content_type = (
                mimetypes.guess_type(image_path.name)[0] or "application/octet-stream"
            )
            try:
                byte_range = parse_byte_range_header(
                    self.headers.get("Range"), stat.st_size
                )
            except (TypeError, ValueError):
                self.send_response(HTTPStatus.REQUESTED_RANGE_NOT_SATISFIABLE)
                self.send_header("Accept-Ranges", "bytes")
                self.send_header("Content-Range", f"bytes */{stat.st_size}")
                self.send_header("Content-Length", "0")
                self.end_headers()
                return

            start, end = byte_range or (0, stat.st_size - 1)
            content_length = end - start + 1
            status = HTTPStatus.PARTIAL_CONTENT if byte_range else HTTPStatus.OK
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Cache-Control", "no-store")
            self.send_header("Accept-Ranges", "bytes")
            self.send_header("Content-Length", str(content_length))
            self.send_header("Last-Modified", formatdate(stat.st_mtime, usegmt=True))
            if byte_range:
                self.send_header(
                    "Content-Range", f"bytes {start}-{end}/{stat.st_size}"
                )
            if as_attachment:
                self.send_header(
                    "Content-Disposition", attachment_header(image_path.name)
                )
            self.end_headers()
            if not include_body:
                return

            remaining = content_length
            try:
                with image_path.open("rb") as capture_file:
                    capture_file.seek(start)
                    while remaining > 0:
                        chunk = capture_file.read(min(64 * 1024, remaining))
                        if not chunk:
                            break
                        self.wfile.write(chunk)
                        remaining -= len(chunk)
            except (BrokenPipeError, ConnectionResetError):
                return

        def _serve_latest_image(self, include_body: bool = True) -> None:
            image_path = get_latest_capture_path(project_root)
            if image_path is None:
                self.send_error(HTTPStatus.NOT_FOUND, "No captures available yet")
                return

            stat = image_path.stat()
            content_type = (
                mimetypes.guess_type(image_path.name)[0] or "application/octet-stream"
            )
            etag = f'"{image_path.name}-{stat.st_mtime_ns}-{stat.st_size}"'
            if self.headers.get("If-None-Match") == etag:
                self.send_response(HTTPStatus.NOT_MODIFIED)
                self.send_header("ETag", etag)
                self.end_headers()
                return

            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", content_type)
            self.send_header(
                "Cache-Control", "no-store, no-cache, must-revalidate, max-age=0"
            )
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
            parsed_request = urlsplit(self.path)
            request_path = parsed_request.path
            if request_path == "/":
                self._send_bytes(render_page(), "text/html; charset=utf-8")
                return

            if request_path == "/gallery":
                self._send_bytes(
                    render_page("gallery"), "text/html; charset=utf-8"
                )
                return

            if request_path == "/api/images":
                image_paths = iter_capture_images(project_root)
                limit = parse_capture_list_limit(parsed_request.query)
                visible_paths = image_paths if limit is None else image_paths[:limit]
                self._send_json(
                    {
                        "images": [
                            build_capture_image(project_root, path)
                            for path in visible_paths
                        ],
                        "total": len(image_paths),
                    }
                )
                return

            if request_path == "/api/device-details":
                self._send_json(build_device_details(project_root, port))
                return

            if request_path == "/api/battery":
                self._send_json(battery_status_from_cache(project_root))
                return

            if request_path == "/api/filter":
                self._send_json(photo_filter_status_from_cache(project_root))
                return

            if request_path == "/latest-image":
                self._serve_latest_image(include_body=True)
                return

            if request_path.startswith("/image/captures/"):
                relative_path = request_path[len("/image/captures/") :]
                image_path = get_capture_media_by_relative_path(
                    project_root, relative_path
                )
                if image_path is None:
                    self.send_error(HTTPStatus.NOT_FOUND, "Capture not found")
                    return
                self._serve_capture(image_path, as_attachment=False)
                return

            if request_path.startswith("/download/captures/"):
                relative_path = request_path[len("/download/captures/") :]
                image_path = get_capture_image_by_relative_path(
                    project_root, relative_path
                )
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
            if request_path.startswith("/image/captures/"):
                relative_path = request_path[len("/image/captures/") :]
                image_path = get_capture_media_by_relative_path(
                    project_root, relative_path
                )
                if image_path is None:
                    self.send_error(HTTPStatus.NOT_FOUND, "Capture not found")
                    return
                self._serve_capture(
                    image_path, as_attachment=False, include_body=False
                )
                return
            if request_path.startswith("/download/captures/"):
                relative_path = request_path[len("/download/captures/") :]
                image_path = get_capture_image_by_relative_path(
                    project_root, relative_path
                )
                if image_path is None:
                    self.send_error(HTTPStatus.NOT_FOUND, "Capture not found")
                    return
                self._serve_capture(image_path, include_body=False)
                return
            self.send_error(HTTPStatus.NOT_FOUND, "Not Found")

        def do_POST(self) -> None:
            request_path = self.path.split("?", 1)[0]
            if request_path == "/api/capture":
                try:
                    image = capture_from_web(project_root)
                except CameraUnavailableError as exc:
                    self._send_json(
                        {"ok": False, "error": f"Capture failed: {exc}"},
                        status=HTTPStatus.SERVICE_UNAVAILABLE,
                    )
                    return
                except CameraCaptureError as exc:
                    self._send_json(
                        {"ok": False, "error": f"Capture failed: {exc}"},
                        status=HTTPStatus.INTERNAL_SERVER_ERROR,
                    )
                    return
                except Exception as exc:
                    self._send_json(
                        {"ok": False, "error": f"Capture failed: {exc}"},
                        status=HTTPStatus.INTERNAL_SERVER_ERROR,
                    )
                    return
                self._send_json({"ok": True, "image": image})
                return
            if request_path == "/api/record":
                try:
                    media = record_from_web(project_root)
                except CameraUnavailableError as exc:
                    self._send_json(
                        {"ok": False, "error": f"Recording failed: {exc}"},
                        status=HTTPStatus.SERVICE_UNAVAILABLE,
                    )
                    return
                except CameraCaptureError as exc:
                    self._send_json(
                        {"ok": False, "error": f"Recording failed: {exc}"},
                        status=HTTPStatus.INTERNAL_SERVER_ERROR,
                    )
                    return
                except Exception as exc:
                    self._send_json(
                        {"ok": False, "error": f"Recording failed: {exc}"},
                        status=HTTPStatus.INTERNAL_SERVER_ERROR,
                    )
                    return
                self._send_json({"ok": True, "image": media})
                return
            self.send_error(HTTPStatus.NOT_FOUND, "Not Found")

        def do_DELETE(self) -> None:
            request_path = self.path.split("?", 1)[0]
            if request_path.startswith("/api/captures/"):
                relative_path = request_path[len("/api/captures/") :]
                try:
                    deleted = delete_capture_image(project_root, relative_path)
                except OSError as exc:
                    self._send_json(
                        {"ok": False, "error": f"Delete failed: {exc}"},
                        status=HTTPStatus.INTERNAL_SERVER_ERROR,
                    )
                    return
                if deleted is None:
                    self._send_json(
                        {"ok": False, "error": "Capture not found"},
                        status=HTTPStatus.NOT_FOUND,
                    )
                    return
                self._send_json(deleted)
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
