"""State definitions for JARVIS Assistant."""

from enum import Enum, auto


class AssistantState(Enum):
    """Core runtime states for JARVIS."""
    SLEEPING = "Sleeping"
    LISTENING = "Listening"
    TRANSCRIBING = "Transcribing"
    RECOGNIZED = "Recognized"
    THINKING = "Thinking"
    SPEAKING = "Speaking"
    EXECUTING = "Executing"
    ERROR = "Error"

    @property
    def color(self) -> str:
        """Hex color associated with state for UI visualizer."""
        mapping = {
            AssistantState.SLEEPING: "#5C6B73",     # Muted slate gray
            AssistantState.LISTENING: "#00E5FF",    # Bright Cyan
            AssistantState.TRANSCRIBING: "#FF9100", # Vivid Amber Orange
            AssistantState.RECOGNIZED: "#38BDF8",   # Sky Blue
            AssistantState.THINKING: "#7C4DFF",     # Electric Purple / Violet
            AssistantState.SPEAKING: "#00E676",     # Neon Emerald Green
            AssistantState.EXECUTING: "#FFD600",    # Amber Yellow
            AssistantState.ERROR: "#FF1744",        # Alert Red
        }
        return mapping.get(self, "#00E5FF")

    @property
    def status_message(self) -> str:
        """User-friendly status text."""
        mapping = {
            AssistantState.SLEEPING: "JARVIS is sleeping. Click Start Listening or use push-to-talk.",
            AssistantState.LISTENING: "Listening for your voice input...",
            AssistantState.TRANSCRIBING: "Transcribing speech using local Whisper neural model...",
            AssistantState.RECOGNIZED: "Speech recognized successfully.",
            AssistantState.THINKING: "Processing with local LLM...",
            AssistantState.SPEAKING: "Responding via local speech synthesis...",
            AssistantState.EXECUTING: "Executing approved local tool...",
            AssistantState.ERROR: "An error occurred. Check diagnostics.",
        }
        return mapping.get(self, "")
