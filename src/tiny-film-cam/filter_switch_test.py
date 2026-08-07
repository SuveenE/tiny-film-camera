from __future__ import annotations

import argparse
import time

from filter_switch import (
    DEFAULT_LEFT_PIN,
    DEFAULT_RIGHT_PIN,
    build_filter_state,
    env_int,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Read and print the three-position filter switch GPIO state."
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
        "--once",
        action="store_true",
        help="Print one reading instead of watching for changes.",
    )
    return parser.parse_args()


def level(grounded: bool) -> str:
    return "LOW" if grounded else "HIGH"


def format_state(payload: dict[str, object]) -> str:
    return (
        f"position={payload['position']:<7} "
        f"selection={str(payload['selection']):<17} "
        f"GPIO{payload['left_pin']}={level(bool(payload['left_grounded']))} "
        f"GPIO{payload['right_pin']}={level(bool(payload['right_grounded']))}"
    )


def main() -> None:
    args = parse_args()
    try:
        from gpiozero import Button
    except ImportError as exc:
        raise SystemExit(
            "Missing gpiozero. On the Raspberry Pi, install it with: "
            "sudo apt install -y python3-gpiozero"
        ) from exc

    print("Stop tiny-film-filter.service before running this direct GPIO test.")
    print("Move the slider through all three positions; press Ctrl+C to finish.")

    try:
        left_input = Button(args.left_pin, pull_up=True)
        right_input = Button(args.right_pin, pull_up=True)
    except Exception as exc:
        raise SystemExit(
            "Could not open the GPIO pins. Check wiring and stop the filter service."
        ) from exc

    previous: tuple[bool, bool] | None = None
    try:
        while True:
            contacts = (left_input.is_pressed, right_input.is_pressed)
            if contacts != previous:
                payload = build_filter_state(
                    left_grounded=contacts[0],
                    right_grounded=contacts[1],
                    left_pin=args.left_pin,
                    right_pin=args.right_pin,
                )
                print(format_state(payload), flush=True)
                previous = contacts
            if args.once:
                break
            time.sleep(0.05)
    except KeyboardInterrupt:
        pass
    finally:
        left_input.close()
        right_input.close()


if __name__ == "__main__":
    main()
