from __future__ import annotations

import argparse
import logging
import threading
import time

LOGGER = logging.getLogger("tiny_film.buzzer")

# Passive module sweet spot is roughly 1.5–2.5 kHz.
# Each pattern step is (frequency_hz, on_seconds, gap_seconds_after).
# Frequency is ignored for active buzzers (simple on/off).
SOUNDS: dict[str, tuple[tuple[float, float, float], ...]] = {
    "click": ((1800.0, 0.06, 0.0),),
    "beep": ((2000.0, 0.15, 0.0),),
    "chirp": ((2200.0, 0.10, 0.0),),
    "alert": ((2400.0, 0.25, 0.0),),
    "double": ((1600.0, 0.08, 0.05), (1600.0, 0.08, 0.0)),
}

SOUND_ORDER = ("click", "beep", "chirp", "alert", "double")


class ShutterBuzzer:
    """Optional GPIO buzzer for shutter feedback.

    Best-effort: if gpiozero is missing or the pin cannot be claimed, the
    buzzer disables itself so captures are never blocked by sound feedback.
    """

    def __init__(self, pin: int | None, active: bool = False) -> None:
        self._active = active
        self._device = None
        self._lock = threading.Lock()

        if pin is None:
            return

        try:
            if active:
                from gpiozero import Buzzer

                self._device = Buzzer(pin)
            else:
                from gpiozero import TonalBuzzer
                from gpiozero.tones import Tone

                # Centre the PWM range on the module's 1.5–2.5 kHz band.
                self._device = TonalBuzzer(pin, mid_tone=Tone(2000), octaves=1)
        except Exception:
            LOGGER.exception(
                "Could not set up buzzer on GPIO %s; captures will run without sound",
                pin,
            )
            self._device = None

    @property
    def enabled(self) -> bool:
        return self._device is not None

    def click(self) -> None:
        """Short tick when the shutter button fires."""
        self.play("click")

    def photo_ok(self) -> None:
        """Confirmation that a photo was saved."""
        self.play("beep")

    def video_start(self) -> None:
        """Cue that video recording has started."""
        self.play("chirp")

    def video_stop(self) -> None:
        """Cue that video recording finished and was saved."""
        self.play("double")

    def error(self) -> None:
        """Alert tone when capture or recording fails."""
        self.play("alert")

    def play(self, name: str) -> None:
        pattern = SOUNDS.get(name)
        if pattern is None:
            raise ValueError(f"Unknown buzzer sound: {name!r}")
        self._play(pattern)

    def play_all(self, pause_seconds: float = 0.4) -> None:
        """Play every built-in sound once — useful for hardware bring-up."""
        for name in SOUND_ORDER:
            LOGGER.info("Playing buzzer sound %s", name)
            self._run_pattern(SOUNDS[name])
            if pause_seconds:
                time.sleep(pause_seconds)

    def _play(self, pattern: tuple[tuple[float, float, float], ...]) -> None:
        if self._device is None:
            return
        thread = threading.Thread(
            target=self._run_pattern, args=(pattern,), daemon=True
        )
        thread.start()

    def _run_pattern(self, pattern: tuple[tuple[float, float, float], ...]) -> None:
        # Serialise playback so overlapping captures don't fight over the pin.
        with self._lock:
            try:
                for frequency, on_seconds, gap_seconds in pattern:
                    self._tone_on(frequency)
                    time.sleep(on_seconds)
                    self._tone_off()
                    if gap_seconds:
                        time.sleep(gap_seconds)
            except Exception:
                LOGGER.exception("Buzzer playback failed")
                self._tone_off()

    def _tone_on(self, frequency: float) -> None:
        if self._device is None:
            return
        if self._active:
            self._device.on()
        else:
            from gpiozero.tones import Tone

            self._device.play(Tone(frequency=frequency))

    def _tone_off(self) -> None:
        if self._device is None:
            return
        if self._active:
            self._device.off()
        else:
            self._device.stop()

    def close(self) -> None:
        if self._device is None:
            return
        try:
            self._tone_off()
            self._device.close()
        except Exception:
            LOGGER.exception("Buzzer close failed")
        finally:
            self._device = None


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Test the Tiny Film passive (or active) feedback buzzer."
    )
    parser.add_argument(
        "--pin",
        type=int,
        default=18,
        help="BCM GPIO pin for the buzzer I/O line (default: 18).",
    )
    parser.set_defaults(active=False)
    parser.add_argument(
        "--passive",
        dest="active",
        action="store_false",
        help="Drive a passive buzzer with PWM tones (default).",
    )
    parser.add_argument(
        "--active",
        dest="active",
        action="store_true",
        help="Drive an active buzzer with simple on/off.",
    )
    parser.add_argument(
        "--sound",
        choices=SOUND_ORDER,
        help="Play a single named sound instead of the full demo.",
    )
    return parser.parse_args()


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    args = parse_args()
    buzzer = ShutterBuzzer(args.pin, active=args.active)
    if not buzzer.enabled:
        raise SystemExit(
            f"Could not open buzzer on BCM GPIO {args.pin}. "
            "Check wiring and that python3-gpiozero is installed."
        )

    kind = "active" if args.active else "passive"
    LOGGER.info("Testing %s buzzer on BCM GPIO %s", kind, args.pin)
    try:
        if args.sound:
            buzzer._run_pattern(SOUNDS[args.sound])
        else:
            buzzer.play_all()
    finally:
        buzzer.close()
    LOGGER.info("Done.")


if __name__ == "__main__":
    main()
