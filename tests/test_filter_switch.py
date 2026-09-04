from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import sys
import threading
import time
import unittest
from tempfile import TemporaryDirectory
from unittest.mock import patch


SOURCE_ROOT = Path(__file__).resolve().parents[1] / "src" / "tiny-film-cam"


def load_module(name: str, filename: str):
    spec = importlib.util.spec_from_file_location(name, SOURCE_ROOT / filename)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load {filename}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


filter_switch = load_module("filter_switch", "filter_switch.py")
filter_daemon = load_module("tiny_film_filter_daemon", "filter_daemon.py")


class FilterSwitchTest(unittest.TestCase):
    def test_contact_truth_table(self) -> None:
        self.assertEqual(filter_switch.position_from_contacts(True, False), "left")
        self.assertEqual(filter_switch.position_from_contacts(False, False), "center")
        self.assertEqual(filter_switch.position_from_contacts(False, True), "right")
        self.assertIsNone(filter_switch.position_from_contacts(True, True))

    def test_default_selections_match_camera_labels(self) -> None:
        with patch.dict("os.environ", {}, clear=True):
            selections = filter_switch.position_selections_from_env()

        self.assertEqual(
            selections,
            {
                "left": "black_and_white",
                "center": "normal",
                "right": "cool",
            },
        )

    def test_position_selections_are_configurable(self) -> None:
        with patch.dict(
            "os.environ",
            {
                "TINY_FILM_FILTER_LEFT": "cool",
                "TINY_FILM_FILTER_CENTER": "normal",
                "TINY_FILM_FILTER_RIGHT": "black_and_white",
            },
            clear=True,
        ):
            payload = filter_switch.build_filter_state(
                left_grounded=True,
                right_grounded=False,
            )

        self.assertEqual(payload["position"], "left")
        self.assertEqual(payload["selection"], "cool")

    def test_both_grounded_is_an_invalid_state(self) -> None:
        payload = filter_switch.build_filter_state(
            left_grounded=True,
            right_grounded=True,
        )

        self.assertFalse(payload["ok"])
        self.assertEqual(payload["position"], "invalid")
        self.assertIsNone(payload["selection"])

    def test_cache_round_trip_and_status(self) -> None:
        with TemporaryDirectory() as tmpdir:
            project_root = Path(tmpdir)
            cache_path = project_root / "data" / "filter-state.json"
            payload = filter_switch.build_filter_state(
                left_grounded=False,
                right_grounded=False,
            )
            filter_switch.write_filter_cache(cache_path, payload)

            status = filter_switch.filter_status_from_cache(project_root)

        self.assertTrue(status["ok"])
        self.assertEqual(status["position"], "center")
        self.assertEqual(status["selection"], "normal")
        self.assertFalse(status["stale"])

    def test_stale_and_missing_cache_statuses(self) -> None:
        with TemporaryDirectory() as tmpdir:
            project_root = Path(tmpdir)
            cache_path = project_root / "data" / "filter-state.json"
            cache_path.parent.mkdir(parents=True)
            cache_path.write_text(
                json.dumps(
                    {
                        "ok": True,
                        "timestamp_unix": time.time() - 60,
                        "position": "right",
                        "selection": "cool",
                    }
                ),
                encoding="utf-8",
            )

            stale = filter_switch.filter_status_from_cache(project_root)
            cache_path.unlink()
            missing = filter_switch.filter_status_from_cache(project_root)

        self.assertTrue(stale["stale"])
        self.assertFalse(missing["ok"])
        self.assertTrue(missing["stale"])

    def test_monitor_debounces_and_emits_heartbeats(self) -> None:
        readings = iter(
            [
                (False, False),
                (True, False),
                (False, False),
                (True, False),
                (True, False),
                (True, False),
                (True, False),
            ]
        )
        last_reading = (True, False)

        def read_contacts() -> tuple[bool, bool]:
            nonlocal last_reading
            try:
                last_reading = next(readings)
            except StopIteration:
                pass
            return last_reading

        writes: list[tuple[bool, bool]] = []
        stop_event = threading.Event()

        def write_state(left: bool, right: bool) -> None:
            writes.append((left, right))
            if len(writes) == 2:
                stop_event.set()

        filter_daemon.monitor_contacts(
            read_contacts=read_contacts,
            write_state=write_state,
            stop_event=stop_event,
            poll_seconds=0.01,
            debounce_seconds=0.015,
            heartbeat_seconds=0.03,
        )

        self.assertEqual(writes, [(True, False), (True, False)])


if __name__ == "__main__":
    unittest.main()
