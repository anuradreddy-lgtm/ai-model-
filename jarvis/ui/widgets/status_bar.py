"""Status bar widget displaying assistant state, LLM status, and microphone status."""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QWidget,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QFrame,
)
from jarvis.core.state import AssistantState
from jarvis.core.events import bus


class StatusBarWidget(QFrame):
    """Top status bar with diagnostics and state indicators."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("HeaderFrame")
        self.setFixedHeight(54)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 8, 16, 8)
        layout.setSpacing(16)

        # App Brand
        brand_label = QLabel("⚡ JARVIS AI")
        brand_label.setStyleSheet("font-size: 15px; font-weight: bold; color: #00E5FF; letter-spacing: 1.5px;")
        layout.addWidget(brand_label)

        # State Pill Badge
        self.state_badge = QLabel("Sleeping")
        self.state_badge.setObjectName("StateBadge")
        self.state_badge.setAlignment(Qt.AlignCenter)
        self.state_badge.setFixedHeight(28)
        layout.addWidget(self.state_badge)

        layout.addStretch(1)

        # Ollama status indicator
        self.ollama_dot = QLabel("●")
        self.ollama_dot.setStyleSheet("color: #EF4444; font-size: 14px;")
        self.ollama_label = QLabel("Ollama: Checking...")
        self.ollama_label.setStyleSheet("color: #94A3B8; font-size: 12px;")

        layout.addWidget(self.ollama_dot)
        layout.addWidget(self.ollama_label)

        # Mic status indicator
        self.mic_dot = QLabel("●")
        self.mic_dot.setStyleSheet("color: #10B981; font-size: 14px;")
        self.mic_label = QLabel("Mic: Standby")
        self.mic_label.setStyleSheet("color: #94A3B8; font-size: 12px;")

        layout.addWidget(self.mic_dot)
        layout.addWidget(self.mic_label)

        # Quick Mic Mute / Unmute Button
        self.mute_btn = QPushButton("Mute Mic")
        self.mute_btn.setFixedHeight(28)
        self.mute_btn.clicked.connect(self._toggle_mic)
        layout.addWidget(self.mute_btn)

        self.mic_active = True

        # Connect event bus signals
        bus.state_changed.connect(self.on_state_changed)
        bus.ollama_status_changed.connect(self.on_ollama_status_changed)
        bus.mic_status_changed.connect(self.on_mic_status_changed)

    def on_state_changed(self, state: AssistantState) -> None:
        color = state.color
        self.state_badge.setText(state.value)
        self.state_badge.setStyleSheet(f"""
            QLabel#StateBadge {{
                background-color: #111C2D;
                border: 1px solid {color};
                border-radius: 12px;
                padding: 2px 14px;
                font-weight: bold;
                color: {color};
            }}
        """)
        self.state_badge.setToolTip(state.status_message)

    def on_ollama_status_changed(self, is_connected: bool, model_name: str) -> None:
        if is_connected:
            self.ollama_dot.setStyleSheet("color: #10B981; font-size: 14px;")  # Green
            self.ollama_label.setText(f"Ollama: {model_name}")
            self.ollama_label.setStyleSheet("color: #38BDF8; font-size: 12px;")
        else:
            self.ollama_dot.setStyleSheet("color: #EF4444; font-size: 14px;")  # Red
            self.ollama_label.setText("Ollama: Offline")
            self.ollama_label.setStyleSheet("color: #EF4444; font-size: 12px;")

    def on_mic_status_changed(self, is_active: bool) -> None:
        self.mic_active = is_active
        if is_active:
            self.mic_dot.setStyleSheet("color: #10B981; font-size: 14px;")
            self.mic_label.setText("Mic: Ready")
            self.mute_btn.setText("Mute Mic")
        else:
            self.mic_dot.setStyleSheet("color: #EF4444; font-size: 14px;")
            self.mic_label.setText("Mic: Muted")
            self.mute_btn.setText("Unmute Mic")

    def _toggle_mic(self) -> None:
        new_state = not self.mic_active
        bus.mic_status_changed.emit(new_state)
