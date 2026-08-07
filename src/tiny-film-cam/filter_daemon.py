from __future__ import annotations

import argparse
import logging
import os
from pathlib import Path
import signal
import threading
import time
from typing import Callable

from filter_switch import (
    DEFAULT_LEFT_PIN,
    DEFAULT_RIGHT_PIN,
    build_filter_state,
    contacts_for_position,
    env_float,
    env_int,
    filter_cache_path_from_env,
    write_filter_cache,
)


LOGGER = logging.getLogger("tiny_film.filter")
DEFAULT_POLL_SECONDS = 0.05
DEFAULT_DEBOUNCE_SECONDS = 0.08
DEFAULT_HEARTBEAT_SECONDS = 5.0


def default_project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Monitor the Tiny Film three-position photo-filter switch."
    )
    parser.add_argument(
        "--project-root",
        type=Path,
        default=default_project_root(),
    )
    parser.add_argument(
        "--left-pin",
        type=int,
        default=env_int("TINY_FILM_FILTER_LEFT_PIN", DEFAULT_LEFT_PIN),
    )
    parser.add_argument(
        "--right-pin",
        type=int,
        default=env_int("TINY_FILM_FILTER_RIGHT_PIN", DEFAULT_RIGHT_PIN),
    )
    parser.add_argument(
        "--poll-seconds",
        type=float,
        default=env_float("TINY_FILM_FILTER_POLL_SECONDS", DEFAULT_POLL_SECONDS),
    )
    parser.add_argument(
        "--debounce-seconds",
        type=float,
        default=env_float(
            "TINY_FILM_FILTER_DEBOUNCE_SECONDS", DEFAULT_DEBOUNCE_SECONDS
        ),
    )
    parser.add_argument(
        "--heartbeat-seconds",
        type=float,
        default=env_float(
            "TINY_FILM_FILTER_HEARTBEAT_SECONDS", DEFAULT_HEARTBEAT_SECONDS
        ),
    )
    parser.add_argument(
        "--simulate-position",
        choices=("left", "center", "right"),
        default=os.environ.get("TINY_FILM_FILTER_SIMULATE_POSITION") or None,
        help="Write a simulated state without opening GPIO pins.",
    )
    return parser.parse_args()


def monitor_contacts(
    *,
    read_contacts: Callable[[], tuple[bool, bool]],
    write_state: Callable[[bool, bool], None],
    stop_event: threading.Event,
    poll_seconds: float,
    debounce_seconds: float,
    heartbeat_seconds: float,
) -> None:
    poll_seconds = max(0.01, poll_seconds)
    debounce_seconds = max(0.0, debounce_seconds)
    heartbeat_seconds = max(0.5, heartbeat_seconds)
    candidate = read_contacts()
    candidate_since = time.monotonic()
    accepted: tuple[bool, bool] | None = None
    last_write = 0.0

    while not stop_event.is_set():
        now = time.monotonic()
        contacts = read_contacts()
        if contacts != candidate:
            candidate = contacts
            candidate_since = now

        stable = now - candidate_since >= debounce_seconds
        state_changed = stable and candidate != accepted
        heartbeat_due = accepted is not None and now - last_write >= heartbeat_seconds
        if state_changed:
            accepted = candidate
        if state_changed or heartbeat_due:
            assert accepted is not None
            write_state(*accepted)
            last_write = now

        stop_event.wait(poll_seconds)


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )
    args = parse_args()
    project_root = args.project_root.expanduser().resolve()
    cache_path = filter_cache_path_from_env(project_root)
    stop_event = threading.Event()

    def request_stop(signum: int, frame: object) -> None:
        LOGGER.info("Stopping on signal %s", signum)
        stop_event.set()

    signal.signal(signal.SIGINT, request_stop)
    signal.signal(signal.SIGTERM, request_stop)

    left_input = None
    right_input = None
    simulated_position = args.simulate_position
    if simulated_position is not None:
        simulated_contacts = contacts_for_position(simulated_position)

        def read_contacts() -> tuple[bool, bool]:
            return simulated_contacts

        LOGGER.info("Using simulated filter position %s", simulated_position)
    else:
        try:
            from gpiozero import Button
        except ImportError as exc:
            raise SystemExit(
                "Missing gpiozero. On the Raspberry Pi, install it with: "
                "sudo apt install -y python3-gpiozero"
            ) from exc

        try:
            left_input = Button(args.left_pin, pull_up=True)
            right_input = Button(args.right_pin, pull_up=True)
        except Exception as exc:
            raise SystemExit(
                "Could not open the filter switch GPIO pins. Check the wiring, "
                "pin settings, and whether another process owns them."
            ) from exc

        def read_contacts() -> tuple[bool, bool]:
            assert left_input is not None and right_input is not None
            return left_input.is_pressed, right_input.is_pressed

    last_logged: tuple[object, object] | None = None

    def write_state(left_grounded: bool, right_grounded: bool) -> None:
        nonlocal last_logged
        payload = build_filter_state(
            left_grounded=left_grounded,
            right_grounded=right_grounded,
            left_pin=args.left_pin,
            right_pin=args.right_pin,
            simulated=simulated_position is not None,
        )
        write_filter_cache(cache_path, payload)
        current = (payload["position"], payload["selection"])
        if current != last_logged:
            if payload["ok"]:
                LOGGER.info(
                    "Filter switch: %s -> %s",
                    payload["position"],
                    payload["selection"],
                )
            else:
                LOGGER.warning("%s", payload["error"])
            last_logged = current

    LOGGER.info(
        "Tiny Film filter switch ready on BCM GPIO %s/%s; cache=%s",
        args.left_pin,
        args.right_pin,
        cache_path,
    )
    try:
        monitor_contacts(
            read_contacts=read_contacts,
            write_state=write_state,
            stop_event=stop_event,
            poll_seconds=args.poll_seconds,
            debounce_seconds=args.debounce_seconds,
            heartbeat_seconds=args.heartbeat_seconds,
        )
    finally:
        if left_input is not None:
            left_input.close()
        if right_input is not None:
            right_input.close()


if __name__ == "__main__":
    main()
