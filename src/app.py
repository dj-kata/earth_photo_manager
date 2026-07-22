from __future__ import annotations

import sys

from PySide6.QtWidgets import QApplication

from src.main_window import MainWindow


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("Earth Photo Manager")
    app.setOrganizationName("earth_photo_manager")

    window = MainWindow()
    window.show()
    return app.exec()
