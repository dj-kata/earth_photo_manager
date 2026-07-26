from __future__ import annotations

import sys

from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication

from src.app_paths import app_icon_path
from src.main_window import MainWindow
from src.update import start_auto_update_check


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("Earth Photo Manager")
    app.setOrganizationName("earth_photo_manager")
    icon_path = app_icon_path()
    if icon_path.exists():
        app.setWindowIcon(QIcon(str(icon_path)))

    window = MainWindow()
    window.show()
    start_auto_update_check(window)
    return app.exec()
