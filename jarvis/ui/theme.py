"""Futuristic Dark UI Theme with Blue/Cyan Accents for JARVIS."""

CYAN_PRIMARY = "#00D4FF"
CYAN_HOVER = "#33DDFF"
CYAN_GLOW = "rgba(0, 212, 255, 0.35)"
BG_DARK = "#0B0F19"
BG_CARD = "#111827"
BG_CARD_LIGHT = "#1F2937"
BORDER_COLOR = "#1E293B"
TEXT_PRIMARY = "#F3F4F6"
TEXT_SECONDARY = "#94A3B8"
TEXT_MUTED = "#64748B"

QSS_STYLESHEET = f"""
QMainWindow {{
    background-color: {BG_DARK};
    color: {TEXT_PRIMARY};
}}

QWidget {{
    background-color: transparent;
    color: {TEXT_PRIMARY};
    font-family: 'Segoe UI', 'SF Pro Display', -apple-system, sans-serif;
    font-size: 13px;
}}

/* Header and Panels */
QFrame#HeaderFrame, QFrame#ControlPanel {{
    background-color: {BG_CARD};
    border: 1px solid {BORDER_COLOR};
    border-radius: 12px;
}}

QFrame#VisualizerContainer {{
    background-color: {BG_CARD};
    border: 1px solid {BORDER_COLOR};
    border-radius: 16px;
}}

/* Buttons */
QPushButton {{
    background-color: #162032;
    border: 1px solid #23354E;
    border-radius: 8px;
    padding: 8px 16px;
    color: {TEXT_PRIMARY};
    font-weight: 600;
}}

QPushButton:hover {{
    background-color: #1F304B;
    border: 1px solid {CYAN_PRIMARY};
    color: {CYAN_PRIMARY};
}}

QPushButton:pressed {{
    background-color: #101B2E;
}}

QPushButton#PrimaryButton {{
    background-color: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #0088CC, stop:1 {CYAN_PRIMARY});
    border: 1px solid {CYAN_PRIMARY};
    color: #FFFFFF;
}}

QPushButton#PrimaryButton:hover {{
    background-color: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #00A3F5, stop:1 {CYAN_HOVER});
}}

QPushButton#DangerButton {{
    background-color: #3B1219;
    border: 1px solid #7F1D1D;
    color: #F87171;
}}

QPushButton#DangerButton:hover {{
    background-color: #4C1D24;
    border: 1px solid #EF4444;
    color: #FCA5A5;
}}

/* Input line edit */
QLineEdit {{
    background-color: #0E1626;
    border: 1px solid #23354E;
    border-radius: 8px;
    padding: 10px 14px;
    color: #FFFFFF;
    selection-background-color: {CYAN_PRIMARY};
    selection-color: #000000;
}}

QLineEdit:focus {{
    border: 1px solid {CYAN_PRIMARY};
    background-color: #131E33;
}}

/* Chat Area */
QScrollArea {{
    border: none;
    background-color: transparent;
}}

QScrollBar:vertical {{
    background-color: {BG_DARK};
    width: 8px;
    margin: 0px;
    border-radius: 4px;
}}

QScrollBar::handle:vertical {{
    background-color: #1E293B;
    min-height: 24px;
    border-radius: 4px;
}}

QScrollBar::handle:vertical:hover {{
    background-color: {CYAN_PRIMARY};
}}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    height: 0px;
}}

/* Status badges */
QLabel#StateBadge {{
    background-color: #1A2639;
    border: 1px solid {CYAN_PRIMARY};
    border-radius: 12px;
    padding: 4px 12px;
    font-weight: bold;
    color: {CYAN_PRIMARY};
}}
"""
