"""Audio capture service using sounddevice with native device matching, resampling, and VAD."""

import queue
import threading
from typing import Any, Dict, List, Optional, Tuple
import numpy as np
import sounddevice as sd
from jarvis.config import config
from jarvis.core.events import bus
from jarvis.utils.logger import logger


def resample_audio(audio: np.ndarray, orig_sr: int, target_sr: int = 16000) -> np.ndarray:
    """Resample 1D float32 audio array from orig_sr to target_sr using linear interpolation."""
    if orig_sr == target_sr or len(audio) == 0:
        return audio.astype(np.float32)

    target_length = int(len(audio) * target_sr / orig_sr)
    if target_length <= 0:
        return np.array([], dtype=np.float32)

    x_old = np.linspace(0, 1, len(audio), endpoint=False)
    x_new = np.linspace(0, 1, target_length, endpoint=False)
    return np.interp(x_new, x_old, audio).astype(np.float32)


def trim_silence_vad(
    audio: np.ndarray,
    sample_rate: int = 16000,
    energy_threshold: float = 0.012,
    pre_speech_pad: float = 0.35,
    post_speech_pad: float = 0.40,
) -> np.ndarray:
    """Trim leading and trailing silence using short-time frame RMS energy."""
    if len(audio) == 0:
        return audio

    frame_len = int(sample_rate * 0.03)  # 30 ms frames
    if frame_len <= 0 or len(audio) < frame_len:
        return audio

    num_frames = len(audio) // frame_len
    energies = []
    for i in range(num_frames):
        chunk = audio[i * frame_len : (i + 1) * frame_len]
        rms = np.sqrt(np.mean(chunk ** 2))
        energies.append(rms)

    energies = np.array(energies)
    active_indices = np.where(energies > energy_threshold)[0]

    # If no speech above threshold, check peak
    if len(active_indices) == 0:
        if np.max(np.abs(audio)) < energy_threshold:
            return np.array([], dtype=np.float32)
        return audio

    start_frame = active_indices[0]
    end_frame = active_indices[-1]

    # Apply padding in frames
    pad_pre_frames = int(pre_speech_pad / 0.03)
    pad_post_frames = int(post_speech_pad / 0.03)

    start_idx = max(0, (start_frame - pad_pre_frames) * frame_len)
    end_idx = min(len(audio), (end_frame + 1 + pad_post_frames) * frame_len)

    trimmed = audio[start_idx:end_idx]
    logger.debug(f"VAD trimmed audio from {len(audio)/sample_rate:.2f}s to {len(trimmed)/sample_rate:.2f}s.")
    return trimmed


class AudioCaptureService:
    """Manages microphone input stream, device capability detection, and buffering."""

    def __init__(self):
        self.target_sample_rate = config.voice.sample_rate  # 16000
        self.chunk_size = config.voice.chunk_size

        # Queue capacity for ~5 minutes of audio chunks
        self.audio_queue: queue.Queue = queue.Queue(maxsize=5000)
        self.is_recording = False
        self.is_muted = False
        self._stream: Optional[sd.InputStream] = None
        self._lock = threading.Lock()

        # Active stream properties
        self.active_device_index: Optional[int] = config.voice.input_device_index
        self.stream_sample_rate: int = 16000
        self.stream_channels: int = 1

        bus.mic_status_changed.connect(self.set_muted)

    def set_muted(self, is_active: bool) -> None:
        """Master mute control."""
        self.is_muted = not is_active
        if self.is_muted and self.is_recording:
            self.stop_recording()
        logger.info(f"Microphone mute state set to: {self.is_muted}")

    def query_device_parameters(self, device_index: Optional[int] = None) -> Tuple[int, int, str]:
        """Determine safe sample rate, channel count, and name for given device."""
        try:
            dev_idx = device_index if device_index is not None else sd.default.device[0]
            dev_info = sd.query_devices(dev_idx)
            dev_name = dev_info.get("name", "Default Microphone")
            max_channels = min(2, max(1, dev_info.get("max_input_channels", 1)))
            native_rate = int(dev_info.get("default_samplerate", 44100))

            # Check if 16000 Hz is supported natively
            try:
                sd.check_input_settings(device=dev_idx, channels=max_channels, samplerate=16000)
                preferred_rate = 16000
            except Exception:
                preferred_rate = native_rate

            return preferred_rate, max_channels, dev_name
        except Exception as exc:
            logger.warning(f"Could not query device parameters: {exc}. Using fallback 16000 Hz Mono.")
            return 16000, 1, "Fallback Microphone"

    def _audio_callback(self, indata: np.ndarray, frames: int, time_info, status) -> None:
        """High-priority SoundDevice input callback."""
        if status:
            logger.debug(f"Audio stream status: {status}")

        if self.is_muted:
            bus.mic_level_changed.emit(0.0)
            return

        # Downmix to mono for level calculation
        mono_chunk = np.mean(indata, axis=1) if indata.ndim > 1 else indata.flatten()

        # Calculate normalized RMS audio level for waveform / visualizer
        rms = float(np.sqrt(np.mean(mono_chunk ** 2)))
        normalized_level = min(1.0, rms * 14.0)
        bus.mic_level_changed.emit(normalized_level)

        if self.is_recording:
            try:
                self.audio_queue.put_nowait(mono_chunk.copy())
            except queue.Full:
                # Discard oldest chunk only if buffer exceeds ~5 minutes
                try:
                    self.audio_queue.get_nowait()
                except queue.Empty:
                    pass
                self.audio_queue.put_nowait(mono_chunk.copy())

    def start_recording(self, device_index: Optional[int] = None) -> bool:
        """Open microphone and start buffering audio frames."""
        with self._lock:
            if self.is_recording:
                return True
            if self.is_muted:
                logger.warning("Cannot start recording: Microphone is muted.")
                return False

            target_idx = device_index if device_index is not None else config.voice.input_device_index
            rate, channels, name = self.query_device_parameters(target_idx)
            self.stream_sample_rate = rate
            self.stream_channels = channels
            self.active_device_index = target_idx

            try:
                # Clear queue before starting
                while not self.audio_queue.empty():
                    self.audio_queue.get_nowait()

                self._stream = sd.InputStream(
                    samplerate=self.stream_sample_rate,
                    channels=self.stream_channels,
                    dtype="float32",
                    blocksize=self.chunk_size,
                    callback=self._audio_callback,
                    device=target_idx,
                )
                self._stream.start()
                self.is_recording = True
                logger.info(f"Microphone recording started on [{target_idx}] '{name}' ({rate} Hz, {channels} ch).")
                return True
            except Exception as exc:
                logger.error(f"Failed to start audio stream on device {target_idx}: {exc}")
                self._stream = None
                self.is_recording = False
                return False

    def stop_recording(self) -> np.ndarray:
        """Stop audio stream, release microphone handle, and return resampled 16kHz mono audio."""
        with self._lock:
            if not self.is_recording:
                return np.array([], dtype=np.float32)

            self.is_recording = False
            if self._stream is not None:
                try:
                    self._stream.stop()
                    self._stream.close()
                except Exception as exc:
                    logger.debug(f"Error closing audio stream: {exc}")
                finally:
                    self._stream = None

            # Drain recorded frames from queue
            frames = []
            while not self.audio_queue.empty():
                try:
                    frames.append(self.audio_queue.get_nowait())
                except queue.Empty:
                    break

            bus.mic_level_changed.emit(0.0)
            logger.info(f"Microphone stopped. Captured {len(frames)} audio chunks.")

            if not frames:
                return np.array([], dtype=np.float32)

            # Concatenate raw chunks
            raw_mono = np.concatenate(frames, axis=0)

            # Resample to 16000 Hz if recorded at hardware rate (e.g. 44100 or 48000 Hz)
            if self.stream_sample_rate != self.target_sample_rate:
                resampled = resample_audio(raw_mono, self.stream_sample_rate, self.target_sample_rate)
            else:
                resampled = raw_mono

            # Apply Voice Activity Detection (VAD) silence trimming
            if config.voice.vad_enabled:
                clean_audio = trim_silence_vad(
                    resampled,
                    sample_rate=self.target_sample_rate,
                    energy_threshold=config.voice.vad_energy_threshold,
                    pre_speech_pad=config.voice.vad_pre_speech_pad,
                    post_speech_pad=0.40,
                )
            else:
                clean_audio = resampled

            return clean_audio
