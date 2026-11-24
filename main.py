"""Standalone Desktop Application Entry Point (Windows / macOS / Linux)."""

from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtWidgets import QApplication

# Ensure project root is importable when launched directly or via PyInstaller
ROOT_DIR = Path(__file__).resolve().parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from src.ui.app_window import APP_QSS, MainWindow


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("Stock Multi-Agent Desktop")
    app.setOrganizationName("AlphaPulse")
    app.setStyle("Fusion")
    app.setStyleSheet(APP_QSS)

    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
