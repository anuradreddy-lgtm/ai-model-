"""Unit tests for PySide6 UI widgets and layout."""

from PySide6.QtWidgets import QApplication
from jarvis.core.state import AssistantState
from jarvis.ui.widgets.status_bar import StatusBarWidget
from jarvis.ui.widgets.visualizer import VisualizerPanel, JarvisOrbVisualizer, WaveformVisualizer
from jarvis.ui.widgets.chat_view import ChatView
from jarvis.ui.main_window import MainWindow


def get_app():
    return QApplication.instance() or QApplication([])


def test_status_bar_state_updates():
    """Verify that StatusBarWidget properly updates state badges and colors."""
    _ = get_app()
    status_bar = StatusBarWidget()

    status_bar.on_state_changed(AssistantState.LISTENING)
    assert status_bar.state_badge.text() == "Listening"

    status_bar.on_state_changed(AssistantState.THINKING)
    assert status_bar.state_badge.text() == "Thinking"

    status_bar.on_ollama_status_changed(True, "qwen2.5:3b")
    assert "qwen2.5:3b" in status_bar.ollama_label.text()

    status_bar.on_mic_status_changed(False)
    assert "Muted" in status_bar.mic_label.text()


def test_chat_view_bubbles():
    """Verify message addition and streaming to ChatView."""
    _ = get_app()
    chat_view = ChatView()

    bubble1 = chat_view.add_message("user", "Hello JARVIS")
    assert bubble1.text_label.text() == "Hello JARVIS"

    chat_view.start_streaming_assistant()
    chat_view.on_token_streamed("I am ")
    chat_view.on_token_streamed("ready.")
    assert chat_view.current_streaming_bubble is not None
    assert chat_view.current_streaming_bubble.text_label.text() == "I am ready."

    chat_view.on_generation_finished("I am ready.")
    assert chat_view.current_streaming_bubble is None


def test_visualizer_creation():
    """Verify visualizer panel and animation step components."""
    _ = get_app()
    panel = VisualizerPanel()
    assert isinstance(panel.orb, JarvisOrbVisualizer)
    assert isinstance(panel.waveform, WaveformVisualizer)

    panel.orb.set_audio_level(0.75)
    assert panel.orb.audio_level > 0.0


def test_main_window_assembly():
    """Verify full MainWindow assembly, controls, and clean shutdown."""
    _ = get_app()
    win = MainWindow(auto_check=False)
    assert win.btn_listen is not None
    assert win.btn_stop is not None
    assert win.btn_sleep is not None
    assert win.btn_settings is not None
    assert win.input_edit is not None

    win.cleanup()
    win.close()
