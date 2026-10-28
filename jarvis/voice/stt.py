"""High-accuracy local speech-to-text service using faster-whisper."""

import sys
import types
import time
import threading
from typing import Optional, List
import numpy as np
from jarvis.config import config
from jarvis.core.events import bus
from jarvis.utils.logger import logger

# Ensure PyAV DLL block policy does not prevent faster-whisper from running on in-memory buffers
if "av" not in sys.modules:
    try:
        import av  # noqa: F401
    except Exception:
        mock_av = types.ModuleType("av")
        mock_av.audio = types.ModuleType("av.audio")
        mock_av.audio.codeccontext = types.ModuleType("av.audio.codeccontext")
        sys.modules["av"] = mock_av
        sys.modules["av.audio"] = mock_av.audio
        sys.modules["av.audio.codeccontext"] = mock_av.audio.codeccontext


class STTService:
    """High-accuracy offline speech-to-text transcription engine."""

    def __init__(self, model_size: Optional[str] = None):
        self.model_size = model_size or config.voice.whisper_model
        self.device = config.voice.whisper_device
        self.compute_type = config.voice.whisper_compute_type
        self.language = config.voice.whisper_language
        self.initial_prompt = config.voice.whisper_initial_prompt

        self._model = None
        self._lock = threading.Lock()
        self._last_latency_ms: float = 0.0

        # Lazy load or initialize model
        self._init_model()

    def _init_model(self) -> None:
        """Load faster-whisper model into memory."""
        try:
            from faster_whisper import WhisperModel
            logger.info(f"Loading local Whisper model '{self.model_size}' on {self.device} ({self.compute_type})...")
            start = time.perf_counter()
            self._model = WhisperModel(
                self.model_size,
                device=self.device,
                compute_type=self.compute_type,
            )
            elapsed = (time.perf_counter() - start) * 1000
            logger.info(f"Whisper model '{self.model_size}' loaded in {elapsed:.1f}ms.")
        except Exception as exc:
            logger.error(f"Failed to load faster-whisper model '{self.model_size}': {exc}")
            self._model = None

    @property
    def last_latency_ms(self) -> float:
        return self._last_latency_ms

    def transcribe_buffer(self, audio_data: np.ndarray) -> str:
        """Transcribe in-memory numpy float32 16kHz audio buffer into text.
        
        Args:
            audio_data: 1D numpy array of float32 audio samples normalized between -1.0 and 1.0.
            
        Returns:
            Clean recognized string transcript, or empty string on silence/failure.
        """
        if audio_data is None or len(audio_data) == 0:
            return ""

        # Flatten if 2D
        if audio_data.ndim > 1:
            audio_data = audio_data.flatten()

        # Step 1: Pre-VAD Silence Guard
        duration_sec = len(audio_data) / 16000.0
        rms = float(np.sqrt(np.mean(audio_data ** 2)))
        peak = float(np.max(np.abs(audio_data)))

        # Reject pure silence or negligible audio < 0.25 seconds or RMS under noise floor
        if duration_sec < 0.25 or rms < 0.005:
            logger.debug(f"Audio buffer rejected as silence: {duration_sec:.2f}s, RMS={rms:.4f}")
            return ""

        # Step 2: Local Whisper Inference
        with self._lock:
            if self._model is None:
                self._init_model()

            if self._model is None:
                logger.error("Whisper model is unavailable for transcription.")
                return ""

            try:
                start_time = time.perf_counter()

                # Transcribe with anti-hallucination thresholds
                segments, info = self._model.transcribe(
                    audio_data,
                    language=self.language,
                    initial_prompt=self.initial_prompt,
                    condition_on_previous_text=False,
                    no_speech_threshold=0.55,
                    compression_ratio_threshold=2.4,
                    log_prob_threshold=-1.0,
                    beam_size=3,
                    best_of=3,
                )

                collected_texts: List[str] = []
                for seg in segments:
                    # Filter out silence hallucinations
                    if seg.no_speech_prob > 0.55:
                        continue
                    text_piece = seg.text.strip()
                    if text_piece:
                        collected_texts.append(text_piece)

                self._last_latency_ms = (time.perf_counter() - start_time) * 1000

                full_transcript = " ".join(collected_texts).strip()
                logger.info(
                    f"Transcribed ({duration_sec:.2f}s audio in {self._last_latency_ms:.1f}ms): '{full_transcript}'"
                )

                if full_transcript:
                    bus.speech_detected.emit(full_transcript)
                return full_transcript

            except Exception as exc:
                logger.error(f"Whisper transcription error: {exc}")
                return ""
