from __future__ import annotations

from dataclasses import dataclass
import json
import os
from pathlib import Path
import time
from typing import Any


DEFAULT_I2C_BUS = 1
DEFAULT_I2C_ADDRESS = 0x43
DEFAULT_CACHE_PATH = "data/battery.json"
DEFAULT_STALE_SECONDS = 30.0

_REG_CONFIG = 0x00
_REG_SHUNT_VOLTAGE = 0x01
_REG_BUS_VOLTAGE = 0x02
_REG_POWER = 0x03
_REG_CURRENT = 0x04
_REG_CALIBRATION = 0x05

_CONFIG_16V_5A = (
    (0x00 << 13)  # 16V bus voltage range
    | (0x01 << 11)  # +/-80mV shunt range
    | (0x0D << 7)  # 12-bit bus ADC, 32 samples
    | (0x0D << 3)  # 12-bit shunt ADC, 32 samples
    | 0x07  # shunt and bus continuous
)


class BatteryReadError(RuntimeError):
    """Raised when the UPS HAT cannot be read."""


@dataclass(frozen=True)
class INA219Calibration:
    value: int = 26868
    current_lsb_ma: float = 0.1524
    power_lsb_w: float = 0.003048


def env_float(name: str, default: float) -> float:
    value = os.environ.get(name)
    if value is None or value.strip() == "":
        return default
    return float(value)


def env_int(name: str, default: int) -> int:
    value = os.environ.get(name)
    if value is None or value.strip() == "":
        return default
    return int(value, 0)


def resolve_project_path(project_root: Path, value: str | Path) -> Path:
    path = Path(value).expanduser()
    if path.is_absolute():
        return path
    return project_root / path


def battery_cache_path_from_env(project_root: Path) -> Path:
    cache_path = os.environ.get("TINY_FILM_BATTERY_CACHE_PATH", DEFAULT_CACHE_PATH)
    return resolve_project_path(project_root, cache_path)


def battery_calibration_from_env() -> INA219Calibration:
    return INA219Calibration(
        value=env_int("TINY_FILM_BATTERY_CALIBRATION", INA219Calibration.value),
        current_lsb_ma=env_float(
            "TINY_FILM_BATTERY_CURRENT_LSB_MA",
            INA219Calibration.current_lsb_ma,
        ),
        power_lsb_w=env_float(
            "TINY_FILM_BATTERY_POWER_LSB_W",
            INA219Calibration.power_lsb_w,
        ),
    )


def open_smbus(i2c_bus: int) -> Any:
    try:
        import smbus  # type: ignore[import-not-found]

        return smbus.SMBus(i2c_bus)
    except ImportError:
        try:
            import smbus2  # type: ignore[import-not-found]

            return smbus2.SMBus(i2c_bus)
        except ImportError as exc:
            raise BatteryReadError(
                "Missing smbus. On the Raspberry Pi, install it with: "
                "sudo apt install -y python3-smbus"
            ) from exc


def signed_16bit(value: int) -> int:
    if value & 0x8000:
        return value - 0x10000
    return value


def estimated_percent_remaining(voltage_v: float) -> float:
    # Waveshare's UPS HAT (C) demo derives capacity from 3.0V..4.2V.
    percent = (voltage_v - 3.0) / 1.2 * 100.0
    return max(0.0, min(100.0, percent))


def battery_state(current_a: float, threshold_a: float = 0.005) -> str:
    if current_a > threshold_a:
        return "charging"
    if current_a < -threshold_a:
        return "discharging"
    return "idle"


class INA219:
    def __init__(
        self,
        i2c_bus: int = DEFAULT_I2C_BUS,
        address: int = DEFAULT_I2C_ADDRESS,
        calibration: INA219Calibration | None = None,
        bus: Any | None = None,
    ) -> None:
        self.address = address
        self.bus = bus if bus is not None else open_smbus(i2c_bus)
        self.calibration = calibration or battery_calibration_from_env()
        self.configure()

    def read_register(self, register: int) -> int:
        data = self.bus.read_i2c_block_data(self.address, register, 2)
        return (data[0] << 8) | data[1]

    def write_register(self, register: int, value: int) -> None:
        data = [(value >> 8) & 0xFF, value & 0xFF]
        self.bus.write_i2c_block_data(self.address, register, data)

    def configure(self) -> None:
        self.write_register(_REG_CALIBRATION, self.calibration.value)
        self.write_register(_REG_CONFIG, _CONFIG_16V_5A)

    def bus_voltage_v(self) -> float:
        self.write_register(_REG_CALIBRATION, self.calibration.value)
        return (self.read_register(_REG_BUS_VOLTAGE) >> 3) * 0.004

    def shunt_voltage_v(self) -> float:
        self.write_register(_REG_CALIBRATION, self.calibration.value)
        return signed_16bit(self.read_register(_REG_SHUNT_VOLTAGE)) * 0.00001

    def current_a(self) -> float:
        self.write_register(_REG_CALIBRATION, self.calibration.value)
        return signed_16bit(self.read_register(_REG_CURRENT)) * self.calibration.current_lsb_ma / 1000.0

    def power_w(self) -> float:
        self.write_register(_REG_CALIBRATION, self.calibration.value)
        return signed_16bit(self.read_register(_REG_POWER)) * self.calibration.power_lsb_w


def read_ups_hat(
    i2c_bus: int = DEFAULT_I2C_BUS,
    address: int = DEFAULT_I2C_ADDRESS,
    bus: Any | None = None,
    calibration: INA219Calibration | None = None,
) -> dict[str, object]:
    try:
        monitor = INA219(
            i2c_bus=i2c_bus,
            address=address,
            calibration=calibration,
            bus=bus,
        )
        load_voltage_v = monitor.bus_voltage_v()
        shunt_voltage_v = monitor.shunt_voltage_v()
        current_a = monitor.current_a()
        power_w = monitor.power_w()
    except OSError as exc:
        raise BatteryReadError(
            f"Could not read UPS HAT at I2C address {address:#04x} on bus {i2c_bus}. "
            "Check that I2C is enabled and the HAT is detected."
        ) from exc

    state = battery_state(current_a)
    percent = estimated_percent_remaining(load_voltage_v)
    return {
        "ok": True,
        "timestamp_unix": time.time(),
        "source": "waveshare-ups-hat-c",
        "i2c_bus": i2c_bus,
        "i2c_address": f"{address:#04x}",
        "percent_remaining": round(percent, 1),
        "capacity_source": "voltage_estimate",
        "load_voltage_v": round(load_voltage_v, 3),
        "shunt_voltage_v": round(shunt_voltage_v, 6),
        "supply_voltage_v": round(load_voltage_v + shunt_voltage_v, 3),
        "current_a": round(current_a, 3),
        "power_w": round(power_w, 3),
        "state": state,
        "is_charging": state == "charging",
        "is_discharging": state == "discharging",
    }


def unavailable_battery_payload(error: str, include_timestamp: bool = True) -> dict[str, object]:
    payload: dict[str, object] = {
        "ok": False,
        "source": "waveshare-ups-hat-c",
        "error": error,
    }
    if include_timestamp:
        payload["timestamp_unix"] = time.time()
    return payload


def write_battery_cache(cache_path: Path, payload: dict[str, object]) -> None:
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = cache_path.with_name(f".{cache_path.name}.tmp")
    tmp_path.write_text(json.dumps(payload, sort_keys=True), encoding="utf-8")
    tmp_path.replace(cache_path)


def read_battery_cache(cache_path: Path) -> dict[str, object]:
    try:
        payload = json.loads(cache_path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return unavailable_battery_payload(
            "Battery service has not written a reading yet.",
            include_timestamp=False,
        )
    except json.JSONDecodeError:
        return unavailable_battery_payload(
            "Battery cache is not valid JSON.",
            include_timestamp=False,
        )

    if not isinstance(payload, dict):
        return unavailable_battery_payload(
            "Battery cache is not a JSON object.",
            include_timestamp=False,
        )
    return payload


def battery_status_from_cache(project_root: Path) -> dict[str, object]:
    cache_path = battery_cache_path_from_env(project_root)
    payload = read_battery_cache(cache_path)
    payload["cache_path"] = str(cache_path)

    timestamp = payload.get("timestamp_unix")
    if isinstance(timestamp, (int, float)):
        stale_seconds = env_float("TINY_FILM_BATTERY_STALE_SECONDS", DEFAULT_STALE_SECONDS)
        payload["age_seconds"] = round(max(0.0, time.time() - float(timestamp)), 1)
        payload["stale"] = payload["age_seconds"] > stale_seconds
    else:
        payload["age_seconds"] = None
        payload["stale"] = True

    return payload
