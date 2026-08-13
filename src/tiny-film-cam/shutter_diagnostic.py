from __future__ import annotations

import argparse
from dataclasses import dataclass, replace
import logging
from pathlib import Path
import threading
import time

from camera import capture_photos, capture_settings_from_env
from photo_filters import selected_photo_filter_from_cache
from shutter_daemon import CaptureRequestWorker


LOGGER = logging.getLogger("tiny_film.shutter_diagnostic")


@dataclass(frozen=True)
class DiagnosticResult:
    attempt: int
    duration_seconds: float
    output_paths: tuple[Path, ...]
    error: str | None = None


def default_project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Queue repeated Tiny Film photo requests and verify that each one saves."
        )
    )
    parser.add_argument(
        "--project-root",
        type=Path,
        default=default_project_root(),
    )
    parser.add_argument(
        "--count",
        type=int,
        default=5,
        help="Number of photo requests to test (default: 5).",
    )
    parser.add_argument(
        "--interval",
        type=float,
        default=5.0,
        help="Seconds between simulated button presses (default: 5).",
    )
    return parser.parse_args()


def run_diagnostic(project_root: Path, count: int, interval: float) -> bool:
    if count <= 0:
        raise ValueError("count must be greater than 0")
    if interval < 0:
        raise ValueError("interval cannot be negative")

    project_root = project_root.expanduser().resolve()
    settings = capture_settings_from_env(project_root)
    results: list[DiagnosticResult] = []
    result_lock = threading.Lock()
    next_attempt = 1

    def take_photo() -> None:
        nonlocal next_attempt
        attempt = next_attempt
        next_attempt += 1
        started_at = time.monotonic()
        frame_at: float | None = None

        def frame_captured() -> None:
            nonlocal frame_at
            frame_at = time.monotonic()
            LOGGER.info(
                "Diagnostic photo %s sensor frame returned after %.3fs",
                attempt,
                frame_at - started_at,
            )

        try:
            capture_settings = replace(
                settings,
                photo_filter=selected_photo_filter_from_cache(project_root),
            )
            output_paths = tuple(
                capture_photos(
                    capture_settings,
                    on_captured=frame_captured,
                )
            )
            missing_paths = [
                path
                for path in output_paths
                if not path.is_file() or path.stat().st_size == 0
            ]
            if missing_paths:
                raise RuntimeError(f"empty or missing output: {missing_paths}")
            result = DiagnosticResult(
                attempt=attempt,
                duration_seconds=time.monotonic() - started_at,
                output_paths=output_paths,
            )
            LOGGER.info(
                "Diagnostic photo %s saved in %.3fs: %s",
                attempt,
                result.duration_seconds,
                list(output_paths),
            )
        except Exception as exc:
            LOGGER.exception("Diagnostic photo %s failed", attempt)
            result = DiagnosticResult(
                attempt=attempt,
                duration_seconds=time.monotonic() - started_at,
                output_paths=(),
                error=str(exc),
            )

        with result_lock:
            results.append(result)

    worker = CaptureRequestWorker(
        take_photo=take_photo,
        record_clip=lambda: None,
    )
    worker.start()
    schedule_started_at = time.monotonic()
    try:
        for attempt in range(1, count + 1):
            due_at = schedule_started_at + ((attempt - 1) * interval)
            delay_seconds = due_at - time.monotonic()
            if delay_seconds > 0:
                time.sleep(delay_seconds)
            submitted_at = time.monotonic()
            worker.submit_photo()
            LOGGER.info(
                "Simulated press %s/%s at +%.3fs",
                attempt,
                count,
                submitted_at - schedule_started_at,
            )
        worker.wait_until_idle()
    finally:
        worker.stop()

    results.sort(key=lambda result: result.attempt)
    passed = len(results) == count and all(result.error is None for result in results)
    saved_count = sum(len(result.output_paths) for result in results)
    LOGGER.info(
        "Diagnostic %s: %s/%s requests completed, %s JPEG(s) saved",
        "PASSED" if passed else "FAILED",
        sum(result.error is None for result in results),
        count,
        saved_count,
    )
    for result in results:
        if result.error is not None:
            LOGGER.error("Photo %s error: %s", result.attempt, result.error)
    return passed


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )
    args = parse_args()
    try:
        passed = run_diagnostic(args.project_root, args.count, args.interval)
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc
    if not passed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
