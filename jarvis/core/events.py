"""Thread-safe event bridge and signals for JARVIS."""

from PySide6.QtCore import QObject, Signal
from jarvis.core.state import AssistantState


class JarvisEventBus(QObject):
    """Central Qt signal bus for cross-thread event dispatching."""

    # State transitions
    state_changed = Signal(object)  # AssistantState

    # LLM and Chat events
    message_received = Signal(str, str)     # role ("user", "assistant", "system", "tool"), content
    token_streamed = Signal(str)           # partial token chunk from streaming LLM
    generation_finished = Signal(str)      # complete final text from assistant
    generation_error = Signal(str)         # error message

    # Tool events
    tool_execution_started = Signal(str, dict)  # tool_name, kwargs
    tool_execution_finished = Signal(str, str)  # tool_name, result
    tool_confirmation_requested = Signal(str, str, dict)  # action_id, description, params

    # Audio & Voice events
    mic_level_changed = Signal(float)       # normalized RMS audio level 0.0 - 1.0 for visualizer
    mic_status_changed = Signal(bool)       # True = active, False = muted/disabled
    speech_detected = Signal(str)           # transcribed text from STT
    speech_started = Signal()               # TTS started speaking
    speech_finished = Signal()              # TTS finished speaking

    # Connection and Diagnostic events
    ollama_status_changed = Signal(bool, str)  # is_connected, model_name
    log_message = Signal(str, str)             # level, message


# Global event bus singleton
bus = JarvisEventBus()
