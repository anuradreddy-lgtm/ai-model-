"""Automated tests for the voice diagnostics module."""

from unittest.mock import patch, MagicMock
import numpy as np
from jarvis.voice.diagnostics import (
    get_audio_input_devices,
    get_tts_voices,
    test_microphone_capture as run_mic_test,
    run_full_voice_diagnostics,
)


def test_get_audio_input_devices():
    """Verify audio input devices enumeration returns valid structured list."""
    devices = get_audio_input_devices()
    assert isinstance(devices, list)
    if len(devices) > 0:
        dev = devices[0]
        assert "index" in dev
        assert "name" in dev
        assert "channels" in dev
        assert "default_samplerate" in dev
        assert "is_default" in dev
        assert isinstance(dev["is_default"], bool)


def test_get_tts_voices():
    """Verify SAPI5 voice enumeration returns installed voices."""
    voices = get_tts_voices()
    assert isinstance(voices, list)
    if len(voices) > 0:
        v = voices[0]
        assert "id" in v
        assert "name" in v
        assert "languages" in v
        assert "gender" in v


@patch("sounddevice.wait")
@patch("sounddevice.rec")
def test_test_microphone_capture_mocked(mock_rec, mock_wait):
    """Verify test_microphone_capture handles audio data and computes levels."""
    # Mock 0.5s of stereo/mono audio
    sample_rate = 16000
    mock_audio = np.full((8000, 1), 0.1, dtype=np.float32)
    mock_rec.return_value = mock_audio

    result = run_mic_test(device_index=1, duration_seconds=0.5)

    assert result["success"] is True
    assert result["device_index"] == 1
    assert result["captured_frames"] == 8000
    assert result["rms_level"] > 0
    assert result["is_silent"] is False
    assert "Successfully captured" in result["message"]


@patch("sounddevice.wait")
@patch("sounddevice.rec")
def test_run_full_voice_diagnostics(mock_rec, mock_wait):
    """Verify full diagnostic report aggregates hardware, STT, and TTS states."""
    mock_audio = np.zeros((4800, 1), dtype=np.float32)
    mock_rec.return_value = mock_audio

    report = run_full_voice_diagnostics()

    assert "timestamp" in report
    assert "input_devices" in report
    assert "input_devices_count" in report
    assert "tts_voices" in report
    assert "mic_capture_test" in report
    assert report["stt_engine"] == "faster-whisper"
    assert "stt_model" in report
    assert "tts_engine" in report
