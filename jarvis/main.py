"""JARVIS AI application launcher."""

import sys
import signal
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt
from jarvis.config import config
from jarvis.ui.main_window import MainWindow
from jarvis.utils.logger import logger


def main() -> int:
    """Launch the JARVIS desktop assistant."""
    logger.info(f"Starting {config.app_name} v{config.version}...")

    # Allow graceful termination with Ctrl+C
    signal.signal(signal.SIGINT, signal.SIG_DFL)

    # Enable High-DPI scaling
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )

    app = QApplication(sys.argv)
    app.setApplicationName(config.app_name)
    app.setApplicationVersion(config.version)
    app.setOrganizationName("JarvisAI")

    window = MainWindow()
    window.show()

    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
