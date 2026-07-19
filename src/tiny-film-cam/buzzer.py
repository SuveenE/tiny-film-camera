from __future__ import annotations

import argparse
import logging
import threading
import time

LOGGER = logging.getLogger("tiny_film.buzzer")

# Volume is burst density (0–1), not PWM duty — transistor modules ignore
# duty cycle and stay full-loud whenever the pin is high. A restrained default
# keeps the little piezo from dominating the moment.
DEFAULT_VOLUME = 0.16
DEFAULT_PHOTO_SOUND = "gentle"

# Chop the carrier this often; denser "on" slices sound louder.
_BURST_PERIOD_SECONDS = 0.001

# Carrier square-wave duty while a burst slice is active.
_CARRIER_DUTY = 0.5

# Musical pitches are rounded to the nearest hertz and kept inside the
# module's useful ~1.5–2.5 kHz band. Short consonant intervals sound less like
# an appliance alarm than a long single-frequency beep.
#
# Each step: (frequency_hz, on_seconds, gap_seconds_after).
# Frequency is ignored for active buzzers (simple on/off).
_G6 = 1568.0
_B6 = 1976.0
_D7 = 2349.0

PHOTO_SOUNDS = ("gentle", "shutter", "sparkle", "minimal")

SOUNDS: dict[str, tuple[tuple[float, float, float], ...]] = {
    # A short, resolving major-third fall. This is the default photo cue.
    "gentle": ((_B6, 0.022, 0.014), (_G6, 0.040, 0.0)),
    # Dry high/low taps that suggest a mechanical shutter rather than a beep.
    "shutter": (
        (2200.0, 0.010, 0.008),
        (1800.0, 0.014, 0.009),
        (_G6, 0.022, 0.0),
    ),
    # A quick G-major arpeggio for a brighter, playful confirmation.
    "sparkle": (
        (_G6, 0.020, 0.012),
        (_B6, 0.022, 0.012),
        (_D7, 0.032, 0.0),
    ),
    # The least intrusive option: one low, very short tick.
    "minimal": ((_G6, 0.030, 0.0),),
    # Semantic cues used elsewhere in the shutter daemon.
    "click": ((_G6, 0.018, 0.0),),
    "chirp": ((_G6, 0.035, 0.020), (_B6, 0.050, 0.0)),
    "double": ((_B6, 0.035, 0.045), (_G6, 0.045, 0.0)),
    "alert": ((_G6, 0.070, 0.055), (_G6, 0.070, 0.0)),
}

# Keep the old CLI name working, but make it the new gentle cue.
SOUNDS["beep"] = SOUNDS["gentle"]

# The no-argument hardware demo focuses on distinct sounds, not aliases.
SOUND_ORDER = PHOTO_SOUNDS + ("chirp", "double", "alert")


def clamp_volume(volume: float) -> float:
    return max(0.0, min(1.0, volume))


class ShutterBuzzer:
    """Optional GPIO buzzer for shutter feedback.

    Best-effort: if gpiozero is missing or the pin cannot be claimed, the
    buzzer disables itself so captures are never blocked by sound feedback.

    Passive modules with a drive transistor stay full amplitude while the pin
    is high, so loudness is controlled by bursting the tone on/off (volume =
    fraction of time the carrier runs), not by PWM duty cycle.
    """

    def __init__(
        self,
        pin: int | None,
        active: bool = False,
        volume: float = DEFAULT_VOLUME,
        photo_sound: str = DEFAULT_PHOTO_SOUND,
    ) -> None:
        if photo_sound not in PHOTO_SOUNDS:
            choices = ", ".join(PHOTO_SOUNDS)
            raise ValueError(
                f"Unknown photo sound: {photo_sound!r}; choose one of: {choices}"
            )
        self._active = active
        self._volume = clamp_volume(volume)
        self._photo_sound = photo_sound
        self._device = None
        self._lock = threading.Lock()

        if pin is None:
            return

        try:
            if active:
                from gpiozero import Buzzer

                self._device = Buzzer(pin)
            else:
                from gpiozero import PWMOutputDevice

                self._device = PWMOutputDevice(pin, frequency=1600, initial_value=0)
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
        self.play(self._photo_sound)

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
                    self._play_tone(frequency, on_seconds)
                    if gap_seconds:
                        time.sleep(gap_seconds)
            except Exception:
                LOGGER.exception("Buzzer playback failed")
                self._tone_off()

    def _play_tone(self, frequency: float, on_seconds: float) -> None:
        if self._device is None or on_seconds <= 0:
            return
        if self._active:
            self._device.on()
            time.sleep(on_seconds)
            self._device.off()
            return

        if self._volume <= 0:
            time.sleep(on_seconds)
            return

        self._device.frequency = max(1.0, frequency)
        if self._volume >= 1.0:
            self._device.value = _CARRIER_DUTY
            time.sleep(on_seconds)
            self._tone_off()
            return

        # Burst-gate the carrier so volume changes are audible on modules that
        # only hard-switch VCC to the piezo (duty cycle alone does nothing).
        on_slice = _BURST_PERIOD_SECONDS * self._volume
        off_slice = _BURST_PERIOD_SECONDS - on_slice
        deadline = time.monotonic() + on_seconds
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                break
            self._device.value = _CARRIER_DUTY
            time.sleep(min(on_slice, remaining))
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                break
            self._tone_off()
            if off_slice > 0:
                time.sleep(min(off_slice, remaining))
        self._tone_off()

    def _tone_on(self, frequency: float) -> None:
        """Legacy helper used by tests; prefer `_play_tone` for playback."""
        if self._device is None:
            return
        if self._active:
            self._device.on()
        else:
            self._device.frequency = max(1.0, frequency)
            self._device.value = _CARRIER_DUTY

    def _tone_off(self) -> None:
        if self._device is None:
            return
        if self._active:
            self._device.off()
        else:
            self._device.value = 0

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
        "--volume",
        type=float,
        default=DEFAULT_VOLUME,
        help=(
            f"Passive loudness 0.0–1.0 via burst density "
            f"(default: {DEFAULT_VOLUME})."
        ),
    )
    parser.add_argument(
        "--sound",
        choices=tuple(SOUNDS),
        help="Play a single named sound instead of the full demo.",
    )
    return parser.parse_args()


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    args = parse_args()
    buzzer = ShutterBuzzer(args.pin, active=args.active, volume=args.volume)
    if not buzzer.enabled:
        raise SystemExit(
            f"Could not open buzzer on BCM GPIO {args.pin}. "
            "Check wiring and that python3-gpiozero is installed."
        )

    kind = "active" if args.active else "passive"
    LOGGER.info(
        "Testing %s buzzer on BCM GPIO %s (volume=%.2f)",
        kind,
        args.pin,
        clamp_volume(args.volume),
    )
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
