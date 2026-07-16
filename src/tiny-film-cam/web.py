from __future__ import annotations

import argparse
import json
import mimetypes
import shutil
import socket
from email.utils import formatdate
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import quote, unquote

from battery import battery_status_from_cache
from camera import (
    CameraCaptureError,
    CameraUnavailableError,
    capture_output_dir_from_env,
    capture_photo,
    capture_settings_from_env,
    record_video,
    video_settings_from_env,
)


IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp"}
VIDEO_SUFFIXES = {".mp4"}
CAPTURE_SUFFIXES = IMAGE_SUFFIXES | VIDEO_SUFFIXES


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
                "media_type": media_type_for(image_path),
                "view_url": f"/image/captures/{quote(relative_path)}",
                "download_url": f"/download/captures/{quote(relative_path)}",
                "delete_url": f"/api/captures/{quote(relative_path)}",
                "modified_unix": stat.st_mtime,
                "size_bytes": stat.st_size,
            }
        )
    return images


def build_capture_image(project_root: Path, image_path: Path) -> dict[str, object]:
    root = captures_root(project_root)
    relative_path = image_path.relative_to(root).as_posix()
    stat = image_path.stat()
    return {
        "filename": image_path.name,
        "relative_path": relative_path,
        "media_type": media_type_for(image_path),
        "view_url": f"/image/captures/{quote(relative_path)}",
        "download_url": f"/download/captures/{quote(relative_path)}",
        "delete_url": f"/api/captures/{quote(relative_path)}",
        "modified_unix": stat.st_mtime,
        "size_bytes": stat.st_size,
    }


def capture_from_web(project_root: Path) -> dict[str, object]:
    output_path = capture_photo(capture_settings_from_env(project_root))
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


def delete_capture_image(project_root: Path, relative_path: str) -> dict[str, object] | None:
    image_path = get_capture_image_by_relative_path(project_root, relative_path)
    if image_path is None:
        return None
    root = captures_root(project_root)
    deleted_path = image_path.relative_to(root).as_posix()
    deleted_name = image_path.name
    image_path.unlink()
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
        <title>Suv's Tiny Film Camera</title>
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
            font-family: ui-monospace, "SFMono-Regular", "SF Mono", Consolas, "Liberation Mono", Menlo, monospace;
          }
          main {
            width: min(920px, 100%);
            margin: 0 auto;
            padding: 18px;
          }
          header {
            display: flex;
            align-items: center;
            justify-content: space-between;
            gap: 18px;
            padding: 8px 0 54px;
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
            padding: 18px 0 34px;
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
          .latest-frame img,
          .latest-frame video {
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
            background: transparent;
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
          button.button {
            cursor: pointer;
            font-family: inherit;
          }
          a.button.primary,
          button.button.primary {
            background: var(--fg);
            color: var(--bg);
          }
          button.button:disabled {
            cursor: wait;
            opacity: 0.55;
          }
          .actions {
            display: flex;
            gap: 8px;
            flex-wrap: wrap;
            justify-content: flex-end;
          }
          .battery-summary {
            align-items: center;
            color: var(--fg);
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
          .latest .section-heading {
            margin-bottom: 0;
          }
          .capture-browser {
            display: grid;
            gap: 12px;
          }
          .capture-stage {
            min-height: 260px;
            border: 1px solid var(--line);
            background: #fff;
            display: grid;
            grid-template-columns: auto minmax(0, 1fr) auto;
            align-items: center;
            overflow: hidden;
          }
          .capture-stage img,
          .capture-stage video {
            display: block;
            width: 100%;
            max-height: 62vh;
            object-fit: contain;
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
            header {
              align-items: flex-start;
              padding-bottom: 42px;
            }
            h1 { font-size: 18px; }
            .section-heading { align-items: center; }
            .capture-stage {
              grid-template-columns: 48px minmax(0, 1fr) 48px;
              min-height: 220px;
            }
            .capture-stage .icon-button { margin: 0 4px; }
            .capture-info { grid-template-columns: minmax(0, 1fr) auto; }
            .metric { padding: 13px 10px; }
            .detail { grid-template-columns: 1fr; gap: 3px; }
          }
        </style>
      </head>
      <body>
        <main>
          <p class="status visually-hidden" id="status" aria-live="polite">Checking captures...</p>
          <header>
            <h1>Suv's Tiny Film Camera</h1>
            <div class="battery-summary" id="battery-summary" aria-label="Battery unavailable" title="Battery unavailable">
              <svg viewBox="0 0 24 24" aria-hidden="true">
                <path d="M20 10v4"></path>
                <rect x="3" y="7" width="15" height="10" rx="2"></rect>
                <path d="M7 11h6"></path>
              </svg>
              <span id="battery-summary-percent">--%</span>
            </div>
          </header>

          <section class="latest">
            <div class="section-heading">
              <h2>Latest</h2>
              <div class="actions">
                <button class="button" id="record-button" type="button">Record 10s</button>
                <button class="button primary" id="capture-button" type="button">Take Photo</button>
              </div>
            </div>
            <div class="latest-frame" id="latest-frame"></div>
          </section>

          <section>
            <div class="section-heading">
              <h2>Captures</h2>
              <p class="status" id="capture-position"></p>
            </div>
            <div class="capture-browser" id="capture-browser"></div>
          </section>

          <section>
            <h2>Battery</h2>
            <div class="details" id="battery-details"></div>
          </section>

          <section>
            <h2>Device</h2>
            <div class="details" id="device-details"></div>
          </section>
        </main>

        <script>
          const statusElement = document.getElementById("status");
          const latestFrame = document.getElementById("latest-frame");
          const captureBrowser = document.getElementById("capture-browser");
          const capturePosition = document.getElementById("capture-position");
          const deviceDetails = document.getElementById("device-details");
          const batteryDetails = document.getElementById("battery-details");
          const batterySummary = document.getElementById("battery-summary");
          const batterySummaryPercent = document.getElementById("battery-summary-percent");
          const captureButton = document.getElementById("capture-button");
          const recordButton = document.getElementById("record-button");
          let captureImages = [];
          let selectedCaptureIndex = 0;

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
              next: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="m9 18 6-6-6-6"></path></svg>',
              previous: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="m15 18-6-6 6-6"></path></svg>',
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
            renderCaptureBrowser();
          }

          function clampCaptureIndex(index, images) {
            if (!images.length) return 0;
            return Math.max(0, Math.min(index, images.length - 1));
          }

          function renderCaptureBrowser() {
            captureBrowser.innerHTML = "";
            if (!captureImages.length) {
              capturePosition.textContent = "";
              captureBrowser.innerHTML = '<div class="empty">No captures yet.</div>';
              return;
            }

            const image = captureImages[selectedCaptureIndex];
            const viewUrl = image.view_url || image.download_url || "";
            capturePosition.textContent = `${selectedCaptureIndex + 1} of ${captureImages.length}`;

            const stage = document.createElement("div");
            stage.className = "capture-stage";

            const previousButton = makeIconButton("button", "previous", "Previous capture");
            previousButton.disabled = selectedCaptureIndex === 0;
            previousButton.addEventListener("click", () => {
              selectCapture(selectedCaptureIndex - 1);
            });

            const previewSrc = `${viewUrl}?v=${encodeURIComponent(image.modified_unix || "")}`;
            let preview;
            if (image.media_type === "video") {
              preview = document.createElement("video");
              preview.src = previewSrc;
              preview.controls = true;
              preview.playsInline = true;
              preview.preload = "metadata";
            } else {
              preview = document.createElement("img");
              preview.src = previewSrc;
              preview.alt = image.filename || "Capture";
            }

            const nextButton = makeIconButton("button", "next", "Next capture");
            nextButton.disabled = selectedCaptureIndex === captureImages.length - 1;
            nextButton.addEventListener("click", () => {
              selectCapture(selectedCaptureIndex + 1);
            });

            stage.append(previousButton, preview, nextButton);

            const info = document.createElement("div");
            info.className = "capture-info";
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

            info.append(text, controls);
            captureBrowser.append(stage, info);
          }

          function renderImages(images, options = {}) {
            const previousSelection = captureImages[selectedCaptureIndex];
            const previousPath = previousSelection && previousSelection.relative_path;
            captureImages = images;
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

            statusElement.textContent = `${images.length} capture${images.length === 1 ? "" : "s"}`;
            latestFrame.innerHTML = "";
            if (images.length) {
              const latest = images[0];
              const cacheBust = encodeURIComponent(latest.modified_unix || "");
              if (latest.media_type === "video") {
                const video = document.createElement("video");
                video.src = `${latest.view_url}?v=${cacheBust}`;
                video.controls = true;
                video.playsInline = true;
                video.preload = "metadata";
                latestFrame.appendChild(video);
              } else {
                const image = document.createElement("img");
                image.src = `/latest-image?v=${cacheBust}`;
                image.alt = latest.filename || "Latest capture";
                latestFrame.appendChild(image);
              }
            } else {
              latestFrame.innerHTML = '<div class="empty">No captures yet.</div>';
            }
            renderCaptureBrowser();
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

          async function refreshImages(options = {}) {
            const response = await fetch("/api/images", { cache: "no-store" });
            if (!response.ok) throw new Error("Image request failed");
            const data = await response.json();
            renderImages(data.images || [], options);
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

          async function takePhoto() {
            if (captureButton.disabled) return;
            const wasRecordDisabled = recordButton.disabled;
            captureButton.disabled = true;
            recordButton.disabled = true;
            captureButton.textContent = "Taking...";
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
              captureButton.textContent = "Take Photo";
            }
          }

          async function recordVideo() {
            if (recordButton.disabled) return;
            const wasCaptureDisabled = captureButton.disabled;
            recordButton.disabled = true;
            captureButton.disabled = true;
            recordButton.textContent = "Recording...";
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
              recordButton.textContent = "Record 10s";
            }
          }

          captureButton.addEventListener("click", () => {
            takePhoto();
          });
          recordButton.addEventListener("click", () => {
            recordVideo();
          });
          refreshImages().catch(() => {
            statusElement.textContent = "Could not load captures.";
          });
          refreshDetails().catch(() => {});
          refreshBattery().catch(() => {
            renderBattery({ ok: false, error: "Could not load battery details.", stale: true });
          });
          setInterval(() => refreshImages().catch(() => {}), 5000);
          setInterval(() => refreshDetails().catch(() => {}), 5000);
          setInterval(() => refreshBattery().catch(() => {}), 5000);
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

        def _serve_capture(self, image_path: Path, as_attachment: bool = True) -> None:
            body = image_path.read_bytes()
            content_type = mimetypes.guess_type(image_path.name)[0] or "application/octet-stream"
            headers = {}
            if as_attachment:
                headers["Content-Disposition"] = attachment_header(image_path.name)
            self._send_bytes(
                body,
                content_type,
                extra_headers=headers,
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

            if request_path == "/api/battery":
                self._send_json(battery_status_from_cache(project_root))
                return

            if request_path == "/latest-image":
                self._serve_latest_image(include_body=True)
                return

            if request_path.startswith("/image/captures/"):
                relative_path = request_path[len("/image/captures/") :]
                image_path = get_capture_image_by_relative_path(project_root, relative_path)
                if image_path is None:
                    self.send_error(HTTPStatus.NOT_FOUND, "Capture not found")
                    return
                self._serve_capture(image_path, as_attachment=False)
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
