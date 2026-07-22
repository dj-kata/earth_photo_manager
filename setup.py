"""
cx_Freeze build settings for Earth Photo Manager.
"""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

from cx_Freeze import Executable, setup
from cx_Freeze.command.build_exe import build_exe as cx_build_exe


PROJECT_NAME = "earth_photo_manager"
ENTRY_POINT = "earth_photo_manager.pyw"
EXE_NAME = "earth_photo_manager.exe" if sys.platform == "win32" else "earth_photo_manager"
BUILD_DIR = PROJECT_NAME
FREEZE_BUILD_DIR = f"build/{PROJECT_NAME}_freeze"
ICON_FILE = Path("src/icon.ico")


def add_if_exists(include_files: list[tuple[str, str]], src: str, dst: str) -> None:
    path = Path(src)
    if path.exists():
        include_files.append((str(path), dst))


include_files: list[tuple[str, str]] = []

try:
    import PySide6

    pyside6_path = Path(PySide6.__file__).parent
    add_if_exists(include_files, str(pyside6_path / "plugins"), "lib/PySide6/plugins")
    add_if_exists(
        include_files,
        str(pyside6_path / "translations"),
        "lib/PySide6/translations",
    )

    qt_conf = Path("build/qt.conf")
    qt_conf.parent.mkdir(parents=True, exist_ok=True)
    qt_conf.write_text(
        "[Paths]\nPrefix = .\nBinaries = .\nPlugins = lib/PySide6/plugins\n",
        encoding="utf-8",
    )
    include_files.append((str(qt_conf), "qt.conf"))
except ImportError:
    print("Warning: PySide6 not found. Build may not work correctly.")


add_if_exists(include_files, "LICENSE", "LICENSE")
add_if_exists(include_files, "README.md", "README.md")
add_if_exists(include_files, "version.txt", "version.txt")
add_if_exists(include_files, str(ICON_FILE), str(ICON_FILE))


build_exe_options = {
    "packages": [
        "PySide6.QtCore",
        "PySide6.QtGui",
        "PySide6.QtWidgets",
        "src",
    ],
    "includes": [
        "src.app",
        "src.image_scanner",
        "src.main_window",
        "src.models",
        "src.preview_window",
        "src.settings",
        "src.update",
    ],
    "excludes": [
        "matplotlib",
        "numpy",
        "pandas",
        "pip",
        "setuptools",
        "test",
        "unittest",
        "PySide6.Qt3DCore",
        "PySide6.Qt3DRender",
        "PySide6.QtCharts",
        "PySide6.QtDataVisualization",
        "PySide6.QtOpenGL",
        "PySide6.QtPrintSupport",
        "PySide6.QtQml",
        "PySide6.QtQuick",
        "PySide6.QtSql",
        "PySide6.QtTest",
        "PySide6.QtWebEngineCore",
        "PySide6.QtWebEngineWidgets",
    ],
    "include_files": include_files,
    "include_msvcr": True,
    "zip_include_packages": [],
    "zip_exclude_packages": ["PySide6"],
    "optimize": 2,
    "build_exe": FREEZE_BUILD_DIR,
}


base = "gui" if sys.platform == "win32" else None


class build_exe(cx_build_exe):
    """Build in a clean staging directory, then copy into earth_photo_manager/."""

    def run(self) -> None:
        super().run()
        src = Path(FREEZE_BUILD_DIR)
        dst = Path(BUILD_DIR)
        dst.mkdir(parents=True, exist_ok=True)
        shutil.copytree(src, dst, dirs_exist_ok=True)


executables = [
    Executable(
        script=ENTRY_POINT,
        base=base,
        target_name=EXE_NAME,
        icon=str(ICON_FILE) if ICON_FILE.exists() else None,
        shortcut_name="Earth Photo Manager",
        shortcut_dir="DesktopFolder",
    )
]


setup(
    name=PROJECT_NAME,
    version="0.1.0",
    description="Photo manager for browsing image folders",
    options={"build_exe": build_exe_options},
    executables=executables,
    cmdclass={"build_exe": build_exe},
)
