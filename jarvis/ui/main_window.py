"""Main Application Window for JARVIS AI."""

from typing import Optional
from PySide6.QtCore import Qt, QThread, Signal, QObject
from PySide6.QtWidgets import (
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLineEdit,
    QPushButton,
    QFrame,
    QSplitter,
)
from jarvis.config import config
from jarvis.core.state import AssistantState
from jarvis.core.events import bus
from jarvis.conversation.manager import ConversationManager
from jarvis.voice.audio_capture import AudioCaptureService
from jarvis.voice.stt import STTService
from jarvis.voice.tts import TTSService
from jarvis.ui.theme import QSS_STYLESHEET
from jarvis.ui.widgets.status_bar import StatusBarWidget
from jarvis.ui.widgets.visualizer import VisualizerPanel
from jarvis.ui.widgets.chat_view import ChatView
from jarvis.ui.widgets.settings_dialog import SettingsDialog
from jarvis.utils.logger import logger


class WorkerSignals(QObject):
    """Signals for background chat worker."""
    finished = Signal(str)
    error = Signal(str)


class AudioTranscribeWorker(QThread):
    """Background worker thread for speech transcription."""
    transcript_ready = Signal(str)

    def __init__(self, stt: STTService, audio_data):
        super().__init__()
        self.stt = stt
        self.audio_data = audio_data

    def run(self) -> None:
        try:
            text = self.stt.transcribe_buffer(self.audio_data)
            self.transcript_ready.emit(text)
        except Exception as exc:
            logger.error(f"Error in transcription worker: {exc}")
            self.transcript_ready.emit("")


class ChatWorker(QThread):
    """Background worker thread for non-blocking Ollama generation."""

    def __init__(self, manager: ConversationManager, user_text: str):
        super().__init__()
        self.manager = manager
        self.user_text = user_text
        self.signals = WorkerSignals()

    def run(self) -> None:
        try:
            # Token callback forwards to event bus
            def on_token(token: str) -> None:
                bus.token_streamed.emit(token)

            response = self.manager.process_user_input(
                user_text=self.user_text,
                on_token=on_token,
            )
            self.signals.finished.emit(response)
        except Exception as exc:
            self.signals.error.emit(str(exc))


class ConnectionCheckWorker(QThread):
    """Background worker to verify Ollama status at startup without blocking UI."""

    def __init__(self, manager: ConversationManager):
        super().__init__()
        self.manager = manager

    def run(self) -> None:
        try:
            is_connected = self.manager.ollama.check_connection()
            if is_connected:
                model_name = self.manager.ollama.ensure_model_available()
                bus.ollama_status_changed.emit(True, model_name)
                # Single lightweight background warm-up to pre-load model into GPU VRAM
                if config.ollama.warmup_on_startup:
                    self.manager.ollama.warmup(model_name)
            else:
                bus.ollama_status_changed.emit(False, "Offline")
        except Exception as exc:
            logger.warning(f"Startup Ollama connection check failed: {exc}")
            bus.ollama_status_changed.emit(False, "Offline")


class MainWindow(QMainWindow):
    """Primary desktop interface for JARVIS Assistant."""

    def __init__(
        self,
        conversation_manager: Optional[ConversationManager] = None,
        auto_check: bool = True,
    ):
        super().__init__()
        self.manager = conversation_manager or ConversationManager()
        self.active_worker: Optional[ChatWorker] = None
        self.transcribe_worker: Optional[AudioTranscribeWorker] = None
        self.check_worker: Optional[ConnectionCheckWorker] = None

        # Voice Subsystem
        self.audio_capture = AudioCaptureService()
        self.stt = STTService()
        self.tts = TTSService()

        self.setWindowTitle(f"{config.app_name} v{config.version} — Windows Desktop Assistant")
        self.resize(1000, 750)
        self.setMinimumSize(800, 600)
        self.setStyleSheet(QSS_STYLESHEET)

        self._init_ui()
        self._init_connections()

        # Run startup connection check
        if auto_check:
            self.check_worker = ConnectionCheckWorker(self.manager)
            self.check_worker.start()

        # Add initial greeting
        self.chat_view.add_message(
            "assistant",
            f"Greetings. I am JARVIS, your Windows AI assistant running locally with {config.ollama.model}. How may I assist you today?",
        )

    def _init_ui(self) -> None:
        central_widget = QWidget(self)
        self.setCentralWidget(central_widget)

        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(16, 16, 16, 16)
        main_layout.setSpacing(12)

        # 1. Top Status Bar
        self.status_bar = StatusBarWidget(self)
        main_layout.addWidget(self.status_bar)

        # 2. Main Center Body (Splitter with Visualizer on Left/Top and Chat on Right/Bottom)
        splitter = QSplitter(Qt.Horizontal, self)
        splitter.setHandleWidth(2)

        # Left Container: Central Visualizer & Waveform
        left_container = QFrame(self)
        left_container.setObjectName("VisualizerContainer")
        left_layout = QVBoxLayout(left_container)
        left_layout.setContentsMargins(12, 12, 12, 12)
        self.visualizer_panel = VisualizerPanel(left_container)
        left_layout.addWidget(self.visualizer_panel)
        left_layout.addStretch(1)

        splitter.addWidget(left_container)

        # Right Container: Conversation History
        self.chat_view = ChatView(self)
        splitter.addWidget(self.chat_view)

        splitter.setSizes([340, 660])
        main_layout.addWidget(splitter, stretch=1)

        # 3. Bottom Control and Input Panel
        bottom_panel = QFrame(self)
        bottom_panel.setObjectName("ControlPanel")
        bottom_layout = QVBoxLayout(bottom_panel)
        bottom_layout.setContentsMargins(14, 12, 14, 12)
        bottom_layout.setSpacing(10)

        # Action Buttons Row
        btn_row = QHBoxLayout()
        btn_row.setSpacing(10)

        self.btn_listen = QPushButton("🎤 Start Listening")
        self.btn_listen.setObjectName("PrimaryButton")
        self.btn_listen.setToolTip("Activate voice input or push-to-talk")
        self.btn_listen.clicked.connect(self.on_listen_clicked)
        btn_row.addWidget(self.btn_listen)

        self.btn_stop = QPushButton("⏹ Stop")
        self.btn_stop.setObjectName("DangerButton")
        self.btn_stop.setToolTip("Cancel ongoing LLM generation or tool execution")
        self.btn_stop.clicked.connect(self.on_stop_clicked)
        btn_row.addWidget(self.btn_stop)

        self.btn_sleep = QPushButton("🌙 Sleep")
        self.btn_sleep.setToolTip("Put JARVIS to standby mode")
        self.btn_sleep.clicked.connect(self.on_sleep_clicked)
        btn_row.addWidget(self.btn_sleep)

        btn_row.addStretch(1)

        self.btn_clear = QPushButton("🗑 Clear Chat")
        self.btn_clear.clicked.connect(self.on_clear_clicked)
        btn_row.addWidget(self.btn_clear)

        self.btn_settings = QPushButton("⚙ Settings")
        self.btn_settings.clicked.connect(self.on_settings_clicked)
        btn_row.addWidget(self.btn_settings)

        bottom_layout.addLayout(btn_row)

        # Text Input Row
        input_row = QHBoxLayout()
        input_row.setSpacing(8)

        self.input_edit = QLineEdit(self)
        self.input_edit.setPlaceholderText("Type a command or ask a question (e.g., 'What time is it?', 'Open calculator')...")
        self.input_edit.returnPressed.connect(self.on_send_clicked)
        input_row.addWidget(self.input_edit, stretch=1)

        self.btn_send = QPushButton("Send")
        self.btn_send.setObjectName("PrimaryButton")
        self.btn_send.setFixedWidth(90)
        self.btn_send.clicked.connect(self.on_send_clicked)
        input_row.addWidget(self.btn_send)

        bottom_layout.addLayout(input_row)

        main_layout.addWidget(bottom_panel)

    def _init_connections(self) -> None:
        bus.state_changed.connect(self.on_state_changed)
        bus.speech_started.connect(self.on_speech_started)
        bus.speech_finished.connect(self.on_speech_finished)

    def on_state_changed(self, state: AssistantState) -> None:
        """Handle state transitions across UI buttons."""
        if state in (AssistantState.THINKING, AssistantState.EXECUTING):
            self.btn_send.setEnabled(False)
            self.input_edit.setEnabled(False)
        else:
            self.btn_send.setEnabled(True)
            self.input_edit.setEnabled(True)

    def on_speech_started(self) -> None:
        if self.manager.current_state != AssistantState.EXECUTING:
            self.manager.set_state(AssistantState.SPEAKING)

    def on_speech_finished(self) -> None:
        if self.manager.current_state == AssistantState.SPEAKING:
            self.manager.set_state(AssistantState.LISTENING)

    def on_send_clicked(self) -> None:
        """Process typed message from user."""
        text = self.input_edit.text().strip()
        if not text:
            return

        self.input_edit.clear()
        self._start_chat_worker(text)

    def _start_chat_worker(self, text: str) -> None:
        """Launch non-blocking generation worker."""
        # Interrupt TTS if currently speaking
        self.tts.stop()

        # Start streaming assistant bubble in view
        self.chat_view.start_streaming_assistant()

        self.active_worker = ChatWorker(self.manager, text)
        self.active_worker.signals.finished.connect(self._on_worker_finished)
        self.active_worker.signals.error.connect(self._on_worker_error)
        self.active_worker.start()

    def _on_worker_finished(self, response: str) -> None:
        self.active_worker = None
        # Speak response using local speech synthesis
        self.tts.speak(response)

    def _on_worker_error(self, error_msg: str) -> None:
        self.active_worker = None
        bus.generation_error.emit(error_msg)

    def on_listen_clicked(self) -> None:
        """Toggle Push-To-Talk microphone capture."""
        if not self.audio_capture.is_recording:
            # User starts speaking: interrupt TTS immediately
            self.tts.stop()
            started = self.audio_capture.start_recording()
            if started:
                self.manager.set_state(AssistantState.LISTENING)
                self.btn_listen.setText("🔴 Recording... (Click to Finish)")
                self.btn_listen.setStyleSheet("background-color: #991B1B; color: #FFFFFF; font-weight: bold;")
            else:
                self.chat_view.add_message("system", "Microphone is unavailable or muted.")
        else:
            # User finished speaking: capture buffer and transcribe
            self.btn_listen.setText("🎤 Start Listening")
            self.btn_listen.setStyleSheet("")
            audio_buffer = self.audio_capture.stop_recording()

            if len(audio_buffer) > 0:
                self.manager.set_state(AssistantState.TRANSCRIBING)
                self.transcribe_worker = AudioTranscribeWorker(self.stt, audio_buffer)
                self.transcribe_worker.transcript_ready.connect(self._on_transcript_ready)
                self.transcribe_worker.start()
            else:
                self.manager.set_state(AssistantState.SLEEPING)

    def _on_transcript_ready(self, text: str) -> None:
        self.transcribe_worker = None
        clean_text = text.strip()
        if clean_text:
            self.manager.set_state(AssistantState.RECOGNIZED)
            self._start_chat_worker(clean_text)
        else:
            self.chat_view.add_message("system", "No clear speech detected. Please try again.")
            self.manager.set_state(AssistantState.SLEEPING)

    def on_stop_clicked(self) -> None:
        """Cancel ongoing stream, tool, speech, or audio recording."""
        self.tts.stop()
        if self.audio_capture.is_recording:
            self.audio_capture.stop_recording()
            self.btn_listen.setText("🎤 Start Listening")
            self.btn_listen.setStyleSheet("")
        if self.transcribe_worker and self.transcribe_worker.isRunning():
            self.transcribe_worker.quit()
            self.transcribe_worker.wait(500)
            self.transcribe_worker = None
        self.manager.stop_generation()

    def on_sleep_clicked(self) -> None:
        """Enter sleep state and stop active speech."""
        self.tts.stop()
        if self.audio_capture.is_recording:
            self.audio_capture.stop_recording()
            self.btn_listen.setText("🎤 Start Listening")
            self.btn_listen.setStyleSheet("")
        if self.transcribe_worker and self.transcribe_worker.isRunning():
            self.transcribe_worker.quit()
            self.transcribe_worker.wait(500)
            self.transcribe_worker = None
        self.manager.set_state(AssistantState.SLEEPING)

    def on_clear_clicked(self) -> None:
        """Clear visible chat history and manager memory."""
        self.tts.stop()
        self.chat_view.clear_messages()
        self.manager.reset_conversation()

    def on_settings_clicked(self) -> None:
        """Open settings dialog."""
        dialog = SettingsDialog(self)
        dialog.exec()

    def cleanup(self) -> None:
        """Safely terminate all background threads, audio streams, and timers."""
        if hasattr(self, "visualizer_panel"):
            self.visualizer_panel.stop()
        if hasattr(self, "tts"):
            self.tts.shutdown()
        if hasattr(self, "audio_capture") and self.audio_capture.is_recording:
            self.audio_capture.stop_recording()

        if self.transcribe_worker and self.transcribe_worker.isRunning():
            self.transcribe_worker.quit()
            self.transcribe_worker.wait(1000)

        if self.check_worker and self.check_worker.isRunning():
            self.check_worker.quit()
            self.check_worker.wait(1000)

        if self.active_worker and self.active_worker.isRunning():
            self.manager.stop_generation()
            self.active_worker.quit()
            self.active_worker.wait(1000)

        if hasattr(self, "manager") and hasattr(self.manager, "ollama"):
            self.manager.ollama.close()

    def closeEvent(self, event) -> None:
        """Ensure background threads and audio streams are safely terminated upon exit."""
        self.cleanup()
        super().closeEvent(event)
