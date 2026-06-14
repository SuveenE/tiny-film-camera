from __future__ import annotations

import importlib.util
import json
import sys
import time
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory


BATTERY_PATH = Path(__file__).resolve().parents[1] / "src" / "tiny-film-cam" / "battery.py"


def load_battery_module():
    spec = importlib.util.spec_from_file_location("tiny_film_battery", BATTERY_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load battery module from {BATTERY_PATH}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


battery = load_battery_module()


def register_bytes(value: int) -> list[int]:
    return [(value >> 8) & 0xFF, value & 0xFF]


class FakeBus:
    def __init__(self, reads: dict[int, int]) -> None:
        self.reads = reads
        self.writes: list[tuple[int, int, list[int]]] = []

    def read_i2c_block_data(self, address: int, register: int, length: int) -> list[int]:
        if length != 2:
            raise AssertionError(f"Unexpected read length {length}")
        return register_bytes(self.reads[register])

    def write_i2c_block_data(self, address: int, register: int, data: list[int]) -> None:
        self.writes.append((address, register, data))


class BatteryTest(unittest.TestCase):
    def test_estimated_percent_remaining_uses_waveshare_voltage_range(self) -> None:
        self.assertEqual(battery.estimated_percent_remaining(3.0), 0.0)
        self.assertAlmostEqual(battery.estimated_percent_remaining(3.6), 50.0)
        self.assertEqual(battery.estimated_percent_remaining(4.3), 100.0)
        self.assertEqual(battery.estimated_percent_remaining(2.8), 0.0)

    def test_battery_state_uses_current_sign(self) -> None:
        self.assertEqual(battery.battery_state(0.020), "charging")
        self.assertEqual(battery.battery_state(-0.020), "discharging")
        self.assertEqual(battery.battery_state(0.001), "idle")

    def test_read_ups_hat_returns_endpoint_payload(self) -> None:
        bus_voltage_raw = int(4.116 / 0.004) << 3
        fake_bus = FakeBus(
            {
                battery._REG_BUS_VOLTAGE: bus_voltage_raw,
                battery._REG_SHUNT_VOLTAGE: 0,
                battery._REG_CURRENT: 100,
                battery._REG_POWER: 10,
            }
        )

        payload = battery.read_ups_hat(bus=fake_bus)

        self.assertTrue(payload["ok"])
        self.assertEqual(payload["i2c_address"], "0x43")
        self.assertEqual(payload["percent_remaining"], 93.0)
        self.assertEqual(payload["load_voltage_v"], 4.116)
        self.assertEqual(payload["current_a"], 0.015)
        self.assertEqual(payload["power_w"], 0.03)
        self.assertEqual(payload["state"], "charging")
        self.assertTrue(fake_bus.writes)

    def test_cache_status_marks_stale_payloads(self) -> None:
        with TemporaryDirectory() as tmpdir:
            project_root = Path(tmpdir)
            cache_path = project_root / "data" / "battery.json"
            cache_path.parent.mkdir(parents=True)
            cache_path.write_text(
                json.dumps(
                    {
                        "ok": True,
                        "timestamp_unix": time.time() - 120,
                        "percent_remaining": 42.0,
                    }
                ),
                encoding="utf-8",
            )

            payload = battery.battery_status_from_cache(project_root)

        self.assertTrue(payload["stale"])
        self.assertGreaterEqual(payload["age_seconds"], 100)

    def test_missing_cache_is_unavailable_and_stale(self) -> None:
        with TemporaryDirectory() as tmpdir:
            payload = battery.battery_status_from_cache(Path(tmpdir))

        self.assertFalse(payload["ok"])
        self.assertTrue(payload["stale"])
        self.assertIsNone(payload["age_seconds"])
        self.assertNotIn("timestamp_unix", payload)


if __name__ == "__main__":
    unittest.main()
