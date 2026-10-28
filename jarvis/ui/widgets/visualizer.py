"""Central JARVIS Visualizer with glowing pulse reactor and audio waveform."""

import math
from PySide6.QtCore import Qt, QTimer, QPointF
from PySide6.QtGui import QPainter, QColor, QPen, QBrush, QRadialGradient, QLinearGradient
from PySide6.QtWidgets import QWidget, QVBoxLayout
from jarvis.core.state import AssistantState
from jarvis.core.events import bus


class JarvisOrbVisualizer(QWidget):
    """Central futuristic pulsing reactor orb representing JARVIS state and audio."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(180, 180)
        self.current_state = AssistantState.SLEEPING
        self.phase = 0.0
        self.rotation_angle = 0.0
        self.audio_level = 0.0  # Normalized 0.0 to 1.0

        # Animation timer at ~30 FPS
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._animate)
        self.timer.start(33)

        # Connect to event bus
        bus.state_changed.connect(self.set_state)
        bus.mic_level_changed.connect(self.set_audio_level)

    def set_state(self, state: AssistantState) -> None:
        self.current_state = state
        self.update()

    def set_audio_level(self, level: float) -> None:
        # Smooth damping
        self.audio_level = 0.7 * self.audio_level + 0.3 * max(0.0, min(1.0, level))
        self.update()

    def _animate(self) -> None:
        speed = 0.05
        if self.current_state == AssistantState.THINKING:
            speed = 0.12
            self.rotation_angle += 2.5
        elif self.current_state == AssistantState.LISTENING:
            speed = 0.08
            self.rotation_angle += 1.2
        elif self.current_state == AssistantState.TRANSCRIBING:
            speed = 0.15
            self.rotation_angle += 2.8
        elif self.current_state == AssistantState.RECOGNIZED:
            speed = 0.09
            self.rotation_angle += 1.6
        elif self.current_state == AssistantState.SPEAKING:
            speed = 0.10
            self.rotation_angle -= 1.8
        elif self.current_state == AssistantState.EXECUTING:
            speed = 0.15
            self.rotation_angle += 3.0
        else:
            speed = 0.03
            self.rotation_angle += 0.3

        self.phase += speed
        if self.phase > 2 * math.pi:
            self.phase -= 2 * math.pi

        self.rotation_angle %= 360
        self.update()

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        width = self.width()
        height = self.height()
        center = QPointF(width / 2.0, height / 2.0)
        base_radius = min(width, height) / 2.8

        base_color = QColor(self.current_state.color)

        # Core breathing factor
        pulse = (math.sin(self.phase) + 1.0) * 0.5  # 0.0 to 1.0
        audio_boost = self.audio_level * 25.0
        core_radius = base_radius * 0.45 + (pulse * 8.0) + audio_boost

        # 1. Outer Glow
        outer_gradient = QRadialGradient(center, base_radius * 1.3)
        glow_color = QColor(base_color)
        glow_color.setAlpha(int(35 + pulse * 40))
        outer_gradient.setColorAt(0.0, glow_color)
        outer_gradient.setColorAt(1.0, QColor(0, 0, 0, 0))
        painter.setBrush(QBrush(outer_gradient))
        painter.setPen(Qt.NoPen)
        painter.drawEllipse(center, base_radius * 1.3, base_radius * 1.3)

        # 2. Outer segmented tech ring
        painter.save()
        painter.translate(center)
        painter.rotate(self.rotation_angle)

        ring_pen = QPen(base_color)
        ring_pen.setWidth(2)
        painter.setPen(ring_pen)
        painter.setBrush(Qt.NoBrush)

        num_segments = 12
        seg_angle = 360.0 / num_segments
        for i in range(num_segments):
            if i % 2 == 0:
                painter.drawArc(
                    int(-base_radius),
                    int(-base_radius),
                    int(base_radius * 2),
                    int(base_radius * 2),
                    int(i * seg_angle * 16),
                    int((seg_angle * 0.7) * 16),
                )
        painter.restore()

        # 3. Inner counter-rotating dashed ring
        painter.save()
        painter.translate(center)
        painter.rotate(-self.rotation_angle * 1.5)
        inner_ring_pen = QPen(base_color)
        inner_ring_pen.setWidth(1)
        inner_ring_pen.setStyle(Qt.DashLine)
        painter.setPen(inner_ring_pen)
        inner_r = base_radius * 0.75
        painter.drawEllipse(QPointF(0, 0), inner_r, inner_r)
        painter.restore()

        # 4. Central Glowing Core
        core_gradient = QRadialGradient(center, core_radius)
        core_bright = QColor(base_color)
        core_bright.setAlpha(240)
        core_edge = QColor(base_color)
        core_edge.setAlpha(40)

        core_gradient.setColorAt(0.0, QColor(255, 255, 255, 230))
        core_gradient.setColorAt(0.3, core_bright)
        core_gradient.setColorAt(0.8, core_edge)
        core_gradient.setColorAt(1.0, QColor(0, 0, 0, 0))

        painter.setBrush(QBrush(core_gradient))
        painter.setPen(Qt.NoPen)
        painter.drawEllipse(center, core_radius, core_radius)

        painter.end()


class WaveformVisualizer(QWidget):
    """Animated audio waveform with dynamic frequency bars."""

    def __init__(self, parent=None, num_bars: int = 36):
        super().__init__(parent)
        self.num_bars = num_bars
        self.setFixedHeight(48)
        self.current_state = AssistantState.SLEEPING
        self.audio_level = 0.0
        self.tick = 0

        self.timer = QTimer(self)
        self.timer.timeout.connect(self._step)
        self.timer.start(40)

        bus.state_changed.connect(self.set_state)
        bus.mic_level_changed.connect(self.set_audio_level)

    def set_state(self, state: AssistantState) -> None:
        self.current_state = state
        self.update()

    def set_audio_level(self, level: float) -> None:
        self.audio_level = 0.6 * self.audio_level + 0.4 * level
        self.update()

    def _step(self) -> None:
        self.tick += 1
        self.update()

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        width = self.width()
        height = self.height()
        bar_width = max(3.0, (width / self.num_bars) - 2.5)
        base_color = QColor(self.current_state.color)

        for i in range(self.num_bars):
            # Compute dynamic height based on audio level and state animation
            offset = i * 0.25
            wave = (math.sin(self.tick * 0.15 + offset) + 1.0) * 0.5
            second_wave = (math.cos(self.tick * 0.08 - offset * 0.5) + 1.0) * 0.5

            if self.current_state in (AssistantState.LISTENING, AssistantState.SPEAKING):
                dynamic_mult = 0.3 + 0.7 * self.audio_level
            elif self.current_state in (AssistantState.THINKING, AssistantState.TRANSCRIBING):
                dynamic_mult = 0.45 + 0.35 * wave
            elif self.current_state in (AssistantState.EXECUTING, AssistantState.RECOGNIZED):
                dynamic_mult = 0.6 + 0.4 * second_wave
            else:
                dynamic_mult = 0.15

            bar_height = max(4.0, (wave * 0.6 + second_wave * 0.4) * (height - 8) * dynamic_mult)
            x = i * (bar_width + 2.5) + 4
            y = (height - bar_height) / 2.0

            grad = QLinearGradient(x, y, x, y + bar_height)
            grad.setColorAt(0.0, base_color)
            dim_color = QColor(base_color)
            dim_color.setAlpha(120)
            grad.setColorAt(1.0, dim_color)

            painter.setBrush(QBrush(grad))
            painter.setPen(Qt.NoPen)
            painter.drawRoundedRect(int(x), int(y), int(bar_width), int(bar_height), 2, 2)

        painter.end()


class VisualizerPanel(QWidget):
    """Container holding both the Central Orb Visualizer and Waveform."""

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        self.orb = JarvisOrbVisualizer(self)
        self.waveform = WaveformVisualizer(self)

        layout.addWidget(self.orb, alignment=Qt.AlignCenter)
        layout.addWidget(self.waveform)

    def stop(self) -> None:
        """Stop animation timers for clean shutdown."""
        if hasattr(self.orb, "timer") and self.orb.timer.isActive():
            self.orb.timer.stop()
        if hasattr(self.waveform, "timer") and self.waveform.timer.isActive():
            self.waveform.timer.stop()
