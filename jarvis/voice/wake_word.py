"""Wake-word detection adapter with push-to-talk fallback."""

import threading
from typing import Callable, Optional
import numpy as np
from jarvis.config import config
from jarvis.utils.logger import logger


class WakeWordAdapter:
    """Detects 'JARVIS' wake word with graceful fallback to push-to-talk."""

    def __init__(self, on_wake: Optional[Callable[[], None]] = None):
        self.on_wake = on_wake
        self.is_enabled = config.voice.wake_word_enabled
        self._model = None
        self._lock = threading.Lock()

        if self.is_enabled:
            self._try_load_model()

    def _try_load_model(self) -> bool:
        """Attempt to load openWakeWord model if installed."""
        try:
            import openwakeword
            from openwakeword.model import Model
            self._model = Model(wakeword_models=[config.voice.wake_word])
            logger.info("Loaded openWakeWord engine.")
            return True
        except ImportError:
            logger.info("openWakeWord not installed. Operating in primary Push-To-Talk mode.")
            self.is_enabled = False
            return False
        except Exception as exc:
            logger.warning(f"Could not load openWakeWord model: {exc}")
            self.is_enabled = False
            return False

    def process_audio_chunk(self, chunk: np.ndarray) -> bool:
        """Process real-time audio chunk for wake-word activation."""
        if not self.is_enabled or self._model is None:
            return False

        with self._lock:
            try:
                # Convert float32 chunk to int16 for openWakeWord
                audio_int16 = (np.clip(chunk, -1.0, 1.0) * 32767).astype(np.int16)
                prediction = self._model.predict(audio_int16)

                for mdl_name, score in prediction.items():
                    if score > 0.65:
                        logger.info(f"Wake word '{mdl_name}' detected with score {score:.2f}!")
                        if self.on_wake:
                            self.on_wake()
                        return True
            except Exception as exc:
                logger.debug(f"Error evaluating wake word chunk: {exc}")

        return False

    def enable(self) -> bool:
        """Enable wake-word detection."""
        if not self._model:
            success = self._try_load_model()
            if not success:
                return False
        self.is_enabled = True
        return True

    def disable(self) -> None:
        """Disable wake-word detection."""
        self.is_enabled = False
