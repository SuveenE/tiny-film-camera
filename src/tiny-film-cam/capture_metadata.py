from __future__ import annotations

import json
from pathlib import Path

from photo_filters import PhotoFilterName, photo_filter_details


def metadata_path_for(capture_path: Path) -> Path:
    return capture_path.with_name(f"{capture_path.name}.json")


def write_photo_filter_metadata(
    capture_path: Path,
    photo_filter: PhotoFilterName,
) -> Path:
    metadata_path = metadata_path_for(capture_path)
    payload = {"photo_filter": photo_filter_details(photo_filter)}
    tmp_path = metadata_path.with_name(f".{metadata_path.name}.tmp")
    tmp_path.write_text(json.dumps(payload, sort_keys=True), encoding="utf-8")
    tmp_path.replace(metadata_path)
    return metadata_path


def read_capture_metadata(capture_path: Path) -> dict[str, object]:
    metadata_path = metadata_path_for(capture_path)
    try:
        payload = json.loads(metadata_path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return {}
    if not isinstance(payload, dict):
        return {}
    return payload


def delete_capture_metadata(capture_path: Path) -> bool:
    metadata_path = metadata_path_for(capture_path)
    try:
        metadata_path.unlink()
    except FileNotFoundError:
        return False
    return True
