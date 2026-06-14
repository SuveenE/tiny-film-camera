from __future__ import annotations

import argparse
import logging
import signal
import threading
from pathlib import Path

from battery import (
    DEFAULT_I2C_ADDRESS,
    DEFAULT_I2C_BUS,
    BatteryReadError,
    battery_cache_path_from_env,
    env_float,
    env_int,
    read_ups_hat,
    unavailable_battery_payload,
    write_battery_cache,
)


LOGGER = logging.getLogger("tiny_film.battery")


def default_project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def parse_args() -> argparse.Namespace:
    project_root = default_project_root().expanduser().resolve()
    parser = argparse.ArgumentParser(
        description="Poll the Waveshare UPS HAT (C) battery monitor."
    )
    parser.add_argument("--project-root", type=Path, default=project_root)
    parser.add_argument(
        "--i2c-bus",
        type=lambda value: int(value, 0),
        default=env_int("TINY_FILM_BATTERY_I2C_BUS", DEFAULT_I2C_BUS),
    )
    parser.add_argument(
        "--i2c-address",
        type=lambda value: int(value, 0),
        default=env_int("TINY_FILM_BATTERY_I2C_ADDRESS", DEFAULT_I2C_ADDRESS),
    )
    parser.add_argument(
        "--interval",
        type=float,
        default=env_float("TINY_FILM_BATTERY_POLL_SECONDS", 5.0),
    )
    return parser.parse_args()


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )
    args = parse_args()
    project_root = args.project_root.expanduser().resolve()
    cache_path = battery_cache_path_from_env(project_root)
    stop_event = threading.Event()

    def request_stop(signum: int, frame: object) -> None:
        LOGGER.info("Stopping on signal %s", signum)
        stop_event.set()

    signal.signal(signal.SIGINT, request_stop)
    signal.signal(signal.SIGTERM, request_stop)

    interval = max(1.0, args.interval)
    LOGGER.info(
        "Tiny Film battery monitor ready on I2C bus %s address %#04x",
        args.i2c_bus,
        args.i2c_address,
    )
    LOGGER.info("Battery readings will be cached at %s", cache_path)

    while not stop_event.is_set():
        try:
            payload = read_ups_hat(i2c_bus=args.i2c_bus, address=args.i2c_address)
            LOGGER.info(
                "Battery %s%%, %.3f V, %.3f A, %s",
                payload["percent_remaining"],
                payload["load_voltage_v"],
                payload["current_a"],
                payload["state"],
            )
        except BatteryReadError as exc:
            payload = unavailable_battery_payload(str(exc))
            LOGGER.warning("%s", exc)
        except Exception as exc:
            payload = unavailable_battery_payload(f"Battery read failed: {exc}")
            LOGGER.exception("Battery read failed")

        write_battery_cache(cache_path, payload)
        stop_event.wait(interval)


if __name__ == "__main__":
    main()
