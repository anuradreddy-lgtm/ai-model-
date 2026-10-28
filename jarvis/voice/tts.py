"""Local text-to-speech engine with natural pacing, sentence chunking, and barge-in interruption."""

import threading
import queue
import re
from typing import List, Optional
import pyttsx3
from jarvis.config import config
from jarvis.core.events import bus
from jarvis.utils.logger import logger


# Common spoken expansions for abbreviations and tech terms
ABBREVIATION_EXPANSIONS = [
    (r"\bGB\b", "gigabytes"),
    (r"\bMB\b", "megabytes"),
    (r"\bKB\b", "kilobytes"),
    (r"\bTB\b", "terabytes"),
    (r"\bGHz\b", "gigahertz"),
    (r"\bMHz\b", "megahertz"),
    (r"\bms\b", "milliseconds"),
    (r"\bWPM\b", "words per minute"),
    (r"\be\.g\.", "for example"),
    (r"\bi\.e\.", "that is"),
    (r"\betc\.", "etcetera"),
    (r"\bvs\.?\b", "versus"),
    (r"\bCPU\b", "C.P.U."),
    (r"\bRAM\b", "R.A.M."),
    (r"\bUI\b", "U.I."),
    (r"\bAPI\b", "A.P.I."),
    (r"\bOllama\b", "Oll-ahma"),
    (r"%", " percent"),
]


class TTSService:
    """Asynchronous local Text-To-Speech worker supporting interruption."""

    def __init__(self):
        self._speech_queue: queue.Queue = queue.Queue()
        self._stop_event = threading.Event()
        self._is_speaking = False
        self._thread: Optional[threading.Thread] = None
        self._engine: Optional[pyttsx3.Engine] = None
        self._lock = threading.Lock()

        # Start background worker thread
        self._start_worker()

    def _start_worker(self) -> None:
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._worker_loop, daemon=True, name="TTS-Worker")
        self._thread.start()

    def _init_engine(self) -> Optional[pyttsx3.Engine]:
        """Initialize SAPI5 engine in the worker thread."""
        try:
            try:
                import pythoncom
                pythoncom.CoInitialize()
            except ImportError:
                pass

            engine = pyttsx3.init()
            engine.setProperty("rate", config.voice.tts_rate)
            engine.setProperty("volume", config.voice.tts_volume)

            # Select configured voice or default to a natural English voice (David or Zira)
            voices = engine.getProperty("voices")
            selected_voice = None

            if config.voice.tts_voice_id:
                for v in voices:
                    if v.id == config.voice.tts_voice_id:
                        selected_voice = v
                        break

            if not selected_voice:
                # Default to David (classic calm JARVIS persona) if available
                for v in voices:
                    if "david" in v.name.lower():
                        selected_voice = v
                        break

            if selected_voice:
                engine.setProperty("voice", selected_voice.id)
                logger.info(f"TTS voice set to: {selected_voice.name}")

            return engine
        except Exception as exc:
            logger.error(f"Failed to initialize pyttsx3 engine: {exc}")
            return None

    def _clean_speech_text(self, text: str) -> str:
        """Sanitize text, expand abbreviations, and remove formatting for natural delivery."""
        # 1. Strip action blocks completely (including nested braces)
        cleaned = text
        if "ACTION:" in cleaned:
            action_idx = cleaned.find("ACTION:")
            brace_start = cleaned.find("{", action_idx)
            if brace_start != -1:
                depth = 0
                end_idx = -1
                for idx in range(brace_start, len(cleaned)):
                    if cleaned[idx] == "{":
                        depth += 1
                    elif cleaned[idx] == "}":
                        depth -= 1
                        if depth == 0:
                            end_idx = idx + 1
                            break
                if end_idx != -1:
                    cleaned = cleaned[:action_idx] + cleaned[end_idx:]
                else:
                    cleaned = cleaned[:action_idx]
            else:
                cleaned = re.sub(r"ACTION:.*$", "", cleaned, flags=re.MULTILINE)

        # 2. Strip code blocks
        cleaned = re.sub(r"```.*?```", "code block omitted.", cleaned, flags=re.DOTALL)
        # 3. Strip markdown links [text](url) -> text
        cleaned = re.sub(r"\[(.*?)\]\(.*?\)", r"\1", cleaned)
        # 4. Strip markdown formatting characters
        cleaned = cleaned.replace("*", "").replace("#", "").replace("`", "").replace("~", "").replace(">", "")
        # 5. Expand abbreviations
        for pattern, replacement in ABBREVIATION_EXPANSIONS:
            cleaned = re.sub(pattern, replacement, cleaned, flags=re.IGNORECASE)

        # 6. Normalize whitespace
        cleaned = re.sub(r"\s+", " ", cleaned).strip()
        return cleaned

    def _split_into_sentences(self, text: str) -> List[str]:
        """Split paragraph into natural sentence chunks with punctuation breaks."""
        # Split on sentence terminals while keeping punctuation
        sentences = re.split(r"(?<=[.!?])\s+", text)
        return [s.strip() for s in sentences if s.strip()]

    def _worker_loop(self) -> None:
        """Background thread consuming speech items sentence by sentence."""
        self._engine = self._init_engine()

        try:
            while True:
                try:
                    text = self._speech_queue.get()
                    if text is None:  # Sentinel to stop
                        break

                    if self._stop_event.is_set():
                        self._speech_queue.task_done()
                        continue

                    clean_text = self._clean_speech_text(text)
                    if not clean_text or not self._engine:
                        self._speech_queue.task_done()
                        continue

                    sentences = self._split_into_sentences(clean_text)
                    self._is_speaking = True
                    bus.speech_started.emit()

                    for sentence in sentences:
                        if self._stop_event.is_set():
                            break

                        try:
                            # Apply dynamic voice/rate/volume from config
                            if config.voice.tts_voice_id:
                                try:
                                    self._engine.setProperty("voice", config.voice.tts_voice_id)
                                except Exception:
                                    pass
                            self._engine.setProperty("rate", config.voice.tts_rate)
                            self._engine.setProperty("volume", config.voice.tts_volume)
                            self._engine.say(sentence)
                            self._engine.runAndWait()
                        except Exception as exc:
                            logger.warning(f"Error during sentence speech playback: {exc}")

                    self._is_speaking = False
                    bus.speech_finished.emit()
                    self._speech_queue.task_done()

                except Exception as exc:
                    logger.error(f"TTS worker loop exception: {exc}")
                    self._is_speaking = False
                    bus.speech_finished.emit()
        finally:
            self._engine = None
            try:
                import pythoncom
                pythoncom.CoUninitialize()
            except Exception:
                pass

    def speak(self, text: str) -> None:
        """Queue text to be spoken asynchronously."""
        if not text or not text.strip():
            return

        # Immediate barge-in: stop any currently active speech first
        self.stop()
        self._stop_event.clear()
        self._speech_queue.put(text)

    def stop(self) -> None:
        """Immediately interrupt and stop any ongoing speech (barge-in)."""
        self._stop_event.set()
        if self._engine and self._is_speaking:
            try:
                self._engine.stop()
            except Exception as exc:
                logger.debug(f"Error interrupting TTS engine: {exc}")

        # Clear remaining queued speech
        while not self._speech_queue.empty():
            try:
                self._speech_queue.get_nowait()
                self._speech_queue.task_done()
            except (queue.Empty, ValueError):
                break

        self._is_speaking = False

    def shutdown(self) -> None:
        """Gracefully terminate TTS worker and release COM resources."""
        self.stop()
        self._speech_queue.put(None)
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=1.5)

    @property
    def is_speaking(self) -> bool:
        return self._is_speaking
