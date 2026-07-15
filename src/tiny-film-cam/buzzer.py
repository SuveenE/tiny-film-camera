from __future__ import annotations

import logging
import threading
import time

LOGGER = logging.getLogger("tiny_film.buzzer")

SUCCESS_FREQUENCY = 880.0
ERROR_FREQUENCY = 220.0

# Each step is (frequency_hz, on_seconds, gap_seconds_after). Frequency is only
# used for passive buzzers; active buzzers just switch on and off.
SUCCESS_PATTERN = (
    (SUCCESS_FREQUENCY, 0.08, 0.06),
    (SUCCESS_FREQUENCY, 0.08, 0.0),
)
ERROR_PATTERN = ((ERROR_FREQUENCY, 0.45, 0.0),)


class ShutterBuzzer:
    """Optional GPIO buzzer that chirps to confirm capture events.

    The buzzer is best-effort: if gpiozero is missing or the device cannot be
    claimed (nothing wired, pin in use, running off-Pi), it silently disables
    itself so a capture is never blocked by sound feedback.
    """

    def __init__(self, pin: int | None, active: bool = True) -> None:
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

                # Widen the range so both the success and error tones are valid.
                self._device = TonalBuzzer(pin, octaves=3)
        except Exception:
            LOGGER.exception(
                "Could not set up buzzer on GPIO %s; captures will run without sound",
                pin,
            )
            self._device = None

    @property
    def enabled(self) -> bool:
        return self._device is not None

    def success(self) -> None:
        self._play(SUCCESS_PATTERN)

    def error(self) -> None:
        self._play(ERROR_PATTERN)

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
