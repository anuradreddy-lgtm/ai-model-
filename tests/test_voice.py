"""Unit tests for the voice subsystem: capture, STT, TTS, and diagnostics."""

from unittest.mock import patch, MagicMock
import numpy as np
import pytest
from jarvis.voice.audio_capture import AudioCaptureService, resample_audio, trim_silence_vad
from jarvis.voice.stt import STTService
from jarvis.voice.tts import TTSService
from jarvis.voice.wake_word import WakeWordAdapter


def test_audio_capture_mute_control():
    """Verify master mute stops capture and emits zero level."""
    capture = AudioCaptureService()
    assert capture.is_muted is False

    capture.set_muted(False)  # set_muted(is_active=False) -> is_muted=True
    assert capture.is_muted is True

    # Starting while muted should fail safely
    assert capture.start_recording() is False

    capture.set_muted(True)  # unmuted
    assert capture.is_muted is False


@patch("sounddevice.InputStream")
def test_audio_capture_start_stop(mock_stream_cls):
    """Verify audio capture lifecycle and stream closing."""
    mock_stream = MagicMock()
    mock_stream_cls.return_value = mock_stream

    capture = AudioCaptureService()
    started = capture.start_recording()
    assert started is True
    assert capture.is_recording is True
    mock_stream.start.assert_called_once()

    # Stop recording
    buffer = capture.stop_recording()
    assert capture.is_recording is False
    mock_stream.stop.assert_called_once()
    mock_stream.close.assert_called_once()


def test_audio_resampling():
    """Verify numpy linear interpolation resamples audio correctly."""
    # 1 second of 44100 Hz audio
    duration = 1.0
    orig_sr = 44100
    target_sr = 16000
    t = np.linspace(0, duration, int(orig_sr * duration), endpoint=False)
    orig_audio = np.sin(2 * np.pi * 440 * t).astype(np.float32)

    resampled = resample_audio(orig_audio, orig_sr, target_sr)
    expected_len = int(len(orig_audio) * (target_sr / orig_sr))

    assert len(resampled) == expected_len
    # Verify no-op when sample rates match
    same_rate = resample_audio(orig_audio, orig_sr, orig_sr)
    assert np.array_equal(same_rate, orig_audio)


def test_vad_silence_trimming():
    """Verify VAD trims leading and trailing silence and rejects pure silence."""
    sr = 16000
    # 1. Pure silence
    silent_audio = np.zeros(sr * 2, dtype=np.float32)
    trimmed_silent = trim_silence_vad(silent_audio, sample_rate=sr, energy_threshold=0.01)
    assert len(trimmed_silent) == 0

    # 2. Audio with speech in the middle (0.5s silence + 1.0s speech + 0.5s silence)
    silence_half = np.zeros(int(sr * 0.5), dtype=np.float32)
    speech = (np.sin(np.linspace(0, 10, int(sr * 1.0))) * 0.5).astype(np.float32)
    composite = np.concatenate([silence_half, speech, silence_half])

    trimmed = trim_silence_vad(composite, sample_rate=sr, energy_threshold=0.02)
    assert len(trimmed) > 0
    # Trimmed audio should be shorter than original composite
    assert len(trimmed) <= len(composite)


def test_stt_empty_and_silence_buffer():
    """Verify STT returns empty string on empty, None, or pure zero silence audio buffer."""
    stt = STTService()
    assert stt.transcribe_buffer(np.array([], dtype=np.float32)) == ""
    assert stt.transcribe_buffer(None) == ""

    # 1 second of pure silence (RMS < 0.005)
    silence = np.zeros(16000, dtype=np.float32)
    assert stt.transcribe_buffer(silence) == ""


def test_tts_text_cleaning_and_abbreviation_expansion():
    """Verify TTS text cleaner strips markdown, action blocks, and expands abbreviations."""
    tts = TTSService()
    raw_text = """
    Here is your answer:
    ACTION: {"tool": "get_time", "args": {}}
    ```python
    print("hidden code")
    ```
    Your CPU usage is 25% and RAM is 16 GB with Ollama running at 150 WPM vs 200 WPM e.g. normal.
    Check [Wikipedia](https://wikipedia.org) for *more* **details**!
    """
    cleaned = tts._clean_speech_text(raw_text)

    assert "ACTION:" not in cleaned
    assert "print" not in cleaned
    assert "code block omitted." in cleaned
    assert "Check Wikipedia for more details!" in cleaned
    assert "C.P.U." in cleaned
    assert "R.A.M." in cleaned
    assert "gigabytes" in cleaned
    assert "percent" in cleaned
    assert "Oll-ahma" in cleaned
    assert "versus" in cleaned
    assert "for example" in cleaned


def test_tts_sentence_splitting():
    """Verify TTS splits multi-sentence paragraphs into natural chunks."""
    tts = TTSService()
    text = "Hello world! How are you doing today? I am JARVIS, ready to assist."
    sentences = tts._split_into_sentences(text)

    assert len(sentences) == 3
    assert sentences[0] == "Hello world!"
    assert sentences[1] == "How are you doing today?"
    assert sentences[2] == "I am JARVIS, ready to assist."


def test_tts_stop_interruption():
    """Verify stop interrupts speech and drains queue."""
    tts = TTSService()
    tts.speak("First sentence.")
    tts.speak("Second sentence.")
    tts.stop()

    assert tts._stop_event.is_set()
    assert tts._speech_queue.empty()


def test_wake_word_adapter_fallback():
    """Verify wake-word adapter safely defaults to disabled fallback without errors."""
    adapter = WakeWordAdapter()
    assert adapter.is_enabled is False
    dummy_chunk = np.zeros(1024, dtype=np.float32)
    assert adapter.process_audio_chunk(dummy_chunk) is False
