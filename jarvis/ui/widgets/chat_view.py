"""Conversation history display widget with streaming message bubbles."""

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QScrollArea,
    QLabel,
    QFrame,
    QHBoxLayout,
    QSizePolicy,
)
from jarvis.core.events import bus


class MessageBubble(QFrame):
    """Individual formatted speech bubble."""

    def __init__(self, role: str, content: str, parent=None):
        super().__init__(parent)
        self.role = role
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 10, 14, 10)
        layout.setSpacing(4)

        # Header tag (Role label)
        role_label = QLabel(self._get_header_title())
        role_label.setStyleSheet(self._get_header_style())
        layout.addWidget(role_label)

        # Message Body
        self.text_label = QLabel(content)
        self.text_label.setWordWrap(True)
        self.text_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.text_label.setStyleSheet("color: #F3F4F6; font-size: 13px; line-height: 1.4;")
        layout.addWidget(self.text_label)

        self.setStyleSheet(self._get_bubble_style())
        self.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Minimum)

    def _get_header_title(self) -> str:
        if self.role == "user":
            return "YOU"
        elif self.role == "assistant":
            return "JARVIS"
        elif self.role == "tool":
            return "SYSTEM TOOL"
        return "SYSTEM"

    def _get_header_style(self) -> str:
        if self.role == "user":
            return "color: #38BDF8; font-weight: bold; font-size: 11px; letter-spacing: 1px;"
        elif self.role == "assistant":
            return "color: #00E5FF; font-weight: bold; font-size: 11px; letter-spacing: 1px;"
        elif self.role == "tool":
            return "color: #FBBF24; font-weight: bold; font-size: 11px; letter-spacing: 1px;"
        return "color: #94A3B8; font-size: 11px;"

    def _get_bubble_style(self) -> str:
        if self.role == "user":
            return """
                QFrame {
                    background-color: #17253C;
                    border: 1px solid #1E3A5F;
                    border-radius: 12px;
                }
            """
        elif self.role == "assistant":
            return """
                QFrame {
                    background-color: #0F172A;
                    border: 1px solid #1E293B;
                    border-radius: 12px;
                }
            """
        elif self.role == "tool":
            return """
                QFrame {
                    background-color: #1E1B13;
                    border: 1px solid #78350F;
                    border-radius: 12px;
                }
            """
        return """
            QFrame {
                background-color: #181E29;
                border: 1px solid #233044;
                border-radius: 12px;
            }
        """

    def append_text(self, text: str) -> None:
        new_text = self.text_label.text() + text
        self.text_label.setText(new_text)

    def set_text(self, text: str) -> None:
        self.text_label.setText(text)


class ChatView(QWidget):
    """Scrollable conversation container supporting streaming updates."""

    def __init__(self, parent=None):
        super().__init__(parent)
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)

        # Scroll Area
        self.scroll_area = QScrollArea(self)
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        # Message List Container
        self.container = QWidget()
        self.messages_layout = QVBoxLayout(self.container)
        self.messages_layout.setContentsMargins(16, 16, 16, 16)
        self.messages_layout.setSpacing(12)
        self.messages_layout.addStretch(1)

        self.scroll_area.setWidget(self.container)
        main_layout.addWidget(self.scroll_area)

        self.current_streaming_bubble: Optional[MessageBubble] = None

        # Connect event bus
        bus.message_received.connect(self.on_message_received)
        bus.token_streamed.connect(self.on_token_streamed)
        bus.generation_finished.connect(self.on_generation_finished)
        bus.generation_error.connect(self.on_generation_error)

    def add_message(self, role: str, content: str) -> MessageBubble:
        """Add a new message bubble to the chat."""
        bubble = MessageBubble(role, content, self.container)

        wrapper = QWidget()
        wrap_layout = QHBoxLayout(wrapper)
        wrap_layout.setContentsMargins(0, 0, 0, 0)

        if role == "user":
            wrap_layout.addStretch(1)
            wrap_layout.addWidget(bubble, stretch=4)
        elif role == "assistant":
            wrap_layout.addWidget(bubble, stretch=4)
            wrap_layout.addStretch(1)
        else:
            wrap_layout.addWidget(bubble, stretch=1)

        # Insert before the stretch at the bottom
        count = self.messages_layout.count()
        self.messages_layout.insertWidget(count - 1, wrapper)

        self._scroll_to_bottom()
        return bubble

    def start_streaming_assistant(self) -> None:
        """Prepare a new assistant bubble for streaming tokens."""
        self.current_streaming_bubble = self.add_message("assistant", "")

    def on_token_streamed(self, token: str) -> None:
        """Handle incoming token from Ollama stream."""
        if not self.current_streaming_bubble:
            self.start_streaming_assistant()
        if self.current_streaming_bubble:
            self.current_streaming_bubble.append_text(token)
            self._scroll_to_bottom()

    def on_generation_finished(self, full_text: str) -> None:
        """Ensure full text is synchronized when stream completes."""
        if self.current_streaming_bubble:
            if not self.current_streaming_bubble.text_label.text():
                self.current_streaming_bubble.set_text(full_text)
            self.current_streaming_bubble = None
        self._scroll_to_bottom()

    def on_generation_error(self, error_text: str) -> None:
        """Render error message."""
        self.current_streaming_bubble = None
        self.add_message("system", f"⚠️ {error_text}")
        self._scroll_to_bottom()

    def on_message_received(self, role: str, content: str) -> None:
        """Called when a user message is sent."""
        if role == "user":
            self.add_message(role, content)

    def clear_messages(self) -> None:
        """Clear all messages from the view."""
        while self.messages_layout.count() > 1:
            item = self.messages_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

    def _scroll_to_bottom(self) -> None:
        QTimer.singleShot(15, lambda: self.scroll_area.verticalScrollBar().setValue(
            self.scroll_area.verticalScrollBar().maximum()
        ))
