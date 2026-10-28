"""Voice subsystem diagnostics for audio devices, STT, and TTS engines."""

import time
from typing import Any, Dict, List, Optional
import numpy as np
import sounddevice as sd
from jarvis.config import config
from jarvis.utils.logger import logger


def get_audio_input_devices() -> List[Dict[str, Any]]:
    """Enumerate all available audio input devices on Windows."""
    devices = []
    try:
        all_devs = sd.query_devices()
        default_in = sd.default.device[0]
        host_apis = sd.query_hostapis()

        for idx, dev in enumerate(all_devs):
            if dev.get("max_input_channels", 0) > 0:
                host_api_idx = dev.get("hostapi", 0)
                api_name = host_apis[host_api_idx]["name"] if host_api_idx < len(host_apis) else "Unknown"

                devices.append({
                    "index": idx,
                    "name": dev["name"],
                    "channels": dev["max_input_channels"],
                    "default_samplerate": int(dev["default_samplerate"]),
                    "host_api": api_name,
                    "is_default": (idx == default_in),
                })
    except Exception as exc:
        logger.error(f"Error querying audio input devices: {exc}")

    return devices


def get_tts_voices() -> List[Dict[str, str]]:
    """Enumerate all installed Windows TTS voices."""
    voices = []
    try:
        import pyttsx3
        engine = pyttsx3.init()
        engine_voices = engine.getProperty("voices")
        for v in engine_voices:
            voices.append({
                "id": str(v.id),
                "name": str(v.name),
                "languages": str(getattr(v, "languages", "")),
                "gender": str(getattr(v, "gender", "unknown")),
            })
    except Exception as exc:
        logger.error(f"Error querying TTS voices: {exc}")
    return voices


def test_microphone_capture(device_index: Optional[int] = None, duration_seconds: float = 0.5) -> Dict[str, Any]:
    """Test capturing a brief audio buffer and calculate noise/signal levels."""
    sample_rate = config.voice.sample_rate
    channels = config.voice.channels

    target_device = device_index if device_index is not None else config.voice.input_device_index
    num_frames = int(sample_rate * duration_seconds)

    try:
        recording = sd.rec(
            frames=num_frames,
            samplerate=sample_rate,
            channels=channels,
            dtype="float32",
            device=target_device,
        )
        sd.wait()

        flat = recording.flatten()
        rms = float(np.sqrt(np.mean(flat ** 2)))
        peak = float(np.max(np.abs(flat)))

        return {
            "success": True,
            "device_index": target_device,
            "sample_rate": sample_rate,
            "channels": channels,
            "captured_frames": len(flat),
            "rms_level": round(rms, 5),
            "peak_amplitude": round(peak, 5),
            "is_silent": rms < 0.001,
            "message": f"Successfully captured {len(flat)} frames. RMS: {rms:.4f}, Peak: {peak:.4f}",
        }
    except Exception as exc:
        return {
            "success": False,
            "device_index": target_device,
            "error": str(exc),
            "message": f"Microphone capture failed on device {target_device}: {exc}",
        }


def run_full_voice_diagnostics() -> Dict[str, Any]:
    """Run comprehensive voice diagnostics across hardware, STT, and TTS."""
    input_devices = get_audio_input_devices()
    tts_voices = get_tts_voices()
    mic_test = test_microphone_capture(duration_seconds=0.3)

    return {
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "input_devices": input_devices,
        "input_devices_count": len(input_devices),
        "selected_device_index": config.voice.input_device_index,
        "mic_capture_test": mic_test,
        "tts_voices": tts_voices,
        "tts_voices_count": len(tts_voices),
        "stt_engine": "faster-whisper",
        "stt_model": config.voice.whisper_model,
        "tts_engine": config.voice.tts_engine,
        "tts_rate": config.voice.tts_rate,
    }
