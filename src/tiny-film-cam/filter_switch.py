from __future__ import annotations

import json
import os
from pathlib import Path
import time
from typing import Literal


FilterPosition = Literal["left", "center", "right"]

DEFAULT_LEFT_PIN = 27
DEFAULT_RIGHT_PIN = 22
DEFAULT_CACHE_PATH = "data/filter-state.json"
DEFAULT_STALE_SECONDS = 15.0
DEFAULT_LEFT_SELECTION = "black_and_white"
DEFAULT_CENTER_SELECTION = "current"
DEFAULT_RIGHT_SELECTION = "cold"


def env_int(name: str, default: int) -> int:
    value = os.environ.get(name)
    if value is None or value.strip() == "":
        return default
    return int(value, 0)


def env_float(name: str, default: float) -> float:
    value = os.environ.get(name)
    if value is None or value.strip() == "":
        return default
    return float(value)


def resolve_project_path(project_root: Path, value: str | Path) -> Path:
    path = Path(value).expanduser()
    if path.is_absolute():
        return path
    return project_root / path


def filter_cache_path_from_env(project_root: Path) -> Path:
    cache_path = os.environ.get("TINY_FILM_FILTER_CACHE_PATH", DEFAULT_CACHE_PATH)
    return resolve_project_path(project_root, cache_path)


def position_selections_from_env() -> dict[FilterPosition, str]:
    return {
        "left": os.environ.get("TINY_FILM_FILTER_LEFT", DEFAULT_LEFT_SELECTION).strip()
        or DEFAULT_LEFT_SELECTION,
        "center": os.environ.get(
            "TINY_FILM_FILTER_CENTER", DEFAULT_CENTER_SELECTION
        ).strip()
        or DEFAULT_CENTER_SELECTION,
        "right": os.environ.get(
            "TINY_FILM_FILTER_RIGHT", DEFAULT_RIGHT_SELECTION
        ).strip()
        or DEFAULT_RIGHT_SELECTION,
    }


def position_from_contacts(
    left_grounded: bool,
    right_grounded: bool,
) -> FilterPosition | None:
    """Map active-low switch contacts to one stable selector position."""
    if left_grounded and not right_grounded:
        return "left"
    if not left_grounded and not right_grounded:
        return "center"
    if not left_grounded and right_grounded:
        return "right"
    return None


def contacts_for_position(position: FilterPosition) -> tuple[bool, bool]:
    if position == "left":
        return True, False
    if position == "center":
        return False, False
    return False, True


def build_filter_state(
    *,
    left_grounded: bool,
    right_grounded: bool,
    left_pin: int = DEFAULT_LEFT_PIN,
    right_pin: int = DEFAULT_RIGHT_PIN,
    timestamp: float | None = None,
    simulated: bool = False,
) -> dict[str, object]:
    position = position_from_contacts(left_grounded, right_grounded)
    payload: dict[str, object] = {
        "ok": position is not None,
        "timestamp_unix": time.time() if timestamp is None else timestamp,
        "source": "simulated" if simulated else "ss23d32",
        "position": position or "invalid",
        "left_pin": left_pin,
        "right_pin": right_pin,
        "left_grounded": left_grounded,
        "right_grounded": right_grounded,
    }
    if position is None:
        payload["selection"] = None
        payload["error"] = "Both switch inputs are grounded; check the wiring."
    else:
        payload["selection"] = position_selections_from_env()[position]
    return payload


def unavailable_filter_payload(
    error: str,
    *,
    include_timestamp: bool = True,
) -> dict[str, object]:
    payload: dict[str, object] = {
        "ok": False,
        "source": "ss23d32",
        "position": "unavailable",
        "selection": None,
        "error": error,
    }
    if include_timestamp:
        payload["timestamp_unix"] = time.time()
    return payload


def write_filter_cache(cache_path: Path, payload: dict[str, object]) -> None:
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = cache_path.with_name(f".{cache_path.name}.tmp")
    tmp_path.write_text(json.dumps(payload, sort_keys=True), encoding="utf-8")
    tmp_path.replace(cache_path)


def read_filter_cache(cache_path: Path) -> dict[str, object]:
    try:
        payload = json.loads(cache_path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return unavailable_filter_payload(
            "Filter switch service has not written a state yet.",
            include_timestamp=False,
        )
    except json.JSONDecodeError:
        return unavailable_filter_payload(
            "Filter switch cache is not valid JSON.",
            include_timestamp=False,
        )

    if not isinstance(payload, dict):
        return unavailable_filter_payload(
            "Filter switch cache is not a JSON object.",
            include_timestamp=False,
        )
    return payload


def filter_status_from_cache(project_root: Path) -> dict[str, object]:
    cache_path = filter_cache_path_from_env(project_root)
    payload = read_filter_cache(cache_path)
    payload["cache_path"] = str(cache_path)

    timestamp = payload.get("timestamp_unix")
    if isinstance(timestamp, (int, float)):
        stale_seconds = env_float(
            "TINY_FILM_FILTER_STALE_SECONDS", DEFAULT_STALE_SECONDS
        )
        payload["age_seconds"] = round(max(0.0, time.time() - float(timestamp)), 1)
        payload["stale"] = payload["age_seconds"] > stale_seconds
    else:
        payload["age_seconds"] = None
        payload["stale"] = True

    return payload
