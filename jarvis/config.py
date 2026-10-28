"""Configuration management for JARVIS AI Assistant."""

from dataclasses import dataclass, field
import os
from pathlib import Path
from typing import List, Optional


def get_default_data_dir() -> Path:
    """Return the dedicated JARVIS data directory in Windows %LOCALAPPDATA%."""
    local_appdata = os.environ.get("LOCALAPPDATA")
    if local_appdata:
        base = Path(local_appdata) / "JARVIS"
    else:
        base = Path.home() / ".jarvis"
    base.mkdir(parents=True, exist_ok=True)
    return base


@dataclass
class OllamaConfig:
    """Ollama local LLM API configuration."""
    base_url: str = "http://localhost:11434"
    model: str = "gemma4:e2b"
    fallback_models: List[str] = field(default_factory=lambda: ["qwen2.5:3b", "llama3.2:3b"])
    timeout_seconds: int = 45
    temperature: float = 0.6
    max_context_turns: int = 12

    # Performance optimization settings
    keep_alive: str = "30m"          # Keep model warm in Ollama memory (e.g. '30m', '1h', '-1')
    num_ctx: int = 2048              # Bounded context window size for optimal RAM/VRAM
    num_predict: int = 256           # Reasonable max output tokens for voice assistant answers
    think: bool = False              # Disable internal reasoning tokens in thinking models for lower latency
    warmup_on_startup: bool = True   # Perform a lightweight background warm-up on startup


@dataclass
class VoiceConfig:
    """Voice capture, speech recognition, and synthesis settings."""
    sample_rate: int = 16000
    channels: int = 1
    chunk_size: int = 1024
    input_device_index: Optional[int] = None
    input_device_name: Optional[str] = None

    # STT (faster-whisper)
    stt_engine: str = "faster-whisper"
    whisper_model: str = "base.en"  # "tiny.en", "base.en", "small.en", or "base"
    whisper_device: str = "cpu"
    whisper_compute_type: str = "int8"
    whisper_language: Optional[str] = "en"
    whisper_initial_prompt: str = "JARVIS, Windows, Notepad, Calculator, Gemma, Python, Ollama"

    # Voice Activity & Silence Detection (VAD)
    vad_enabled: bool = True
    vad_energy_threshold: float = 0.012  # RMS floor for speech detection
    vad_silence_duration: float = 0.9    # Seconds of silence indicating speech finished
    vad_pre_speech_pad: float = 0.35     # Seconds of audio preserved before voice start (no cut off)

    # TTS Settings
    tts_engine: str = "local"  # "local" (pyttsx3/SAPI5) or "piper"
    tts_voice_id: Optional[str] = None
    tts_rate: int = 185
    tts_volume: float = 0.95

    # Controls
    wake_word: str = "jarvis"
    wake_word_enabled: bool = False
    continuous_listening: bool = False


@dataclass
class SecurityConfig:
    """Security and tool execution safety settings."""
    require_confirmation_for_consequential: bool = True
    allowed_apps: List[str] = field(
        default_factory=lambda: [
            "notepad.exe",
            "calc.exe",
            "mspaint.exe",
            "explorer.exe",
            "taskmgr.exe",
            "cmd.exe",
        ]
    )
    allowed_domains: List[str] = field(
        default_factory=lambda: [
            "google.com",
            "wikipedia.org",
            "github.com",
            "stackoverflow.com",
            "python.org",
            "ollama.com",
        ]
    )


@dataclass
class JarvisConfig:
    """Global JARVIS application configuration."""
    app_name: str = "JARVIS AI"
    version: str = "1.0.0"
    data_dir: Path = field(default_factory=get_default_data_dir)
    ollama: OllamaConfig = field(default_factory=OllamaConfig)
    voice: VoiceConfig = field(default_factory=VoiceConfig)
    security: SecurityConfig = field(default_factory=SecurityConfig)

    @property
    def db_path(self) -> Path:
        return self.data_dir / "jarvis.db"

    @property
    def notes_dir(self) -> Path:
        notes_path = self.data_dir / "notes"
        notes_path.mkdir(parents=True, exist_ok=True)
        return notes_path

    @property
    def logs_dir(self) -> Path:
        logs_path = self.data_dir / "logs"
        logs_path.mkdir(parents=True, exist_ok=True)
        return logs_path


# Global default configuration instance
config = JarvisConfig()
