from __future__ import annotations

from dataclasses import dataclass
import json
import os
from pathlib import Path
import re
import shutil
import shlex
import subprocess
import sys
import tempfile
import threading
import urllib.request
import zipfile

from PySide6.QtCore import QObject, Signal
from PySide6.QtWidgets import QApplication, QMessageBox, QWidget

from src.app_paths import app_root


GITHUB_REPOSITORY = "dj-kata/earth_photo_manager"
LATEST_RELEASE_URL = (
    f"https://api.github.com/repos/{GITHUB_REPOSITORY}/releases/latest"
)
RELEASE_ASSET_NAME = "earth_photo_manager.zip"
APP_FOLDER_NAME = "earth_photo_manager"
EXE_NAME = "earth_photo_manager.exe" if sys.platform == "win32" else "earth_photo_manager"


@dataclass(frozen=True)
class UpdateInfo:
    version: str
    current_version: str
    asset_url: str
    release_url: str


class AutoUpdater(QObject):
    update_found = Signal(object)
    check_failed = Signal(str)
    install_failed = Signal(str)
    install_ready = Signal(str)

    def __init__(self, parent: QWidget) -> None:
        super().__init__(parent)
        self._parent = parent

    def start(self) -> None:
        thread = threading.Thread(target=self._check_worker, daemon=True)
        thread.start()

    def install(self, info: UpdateInfo) -> None:
        thread = threading.Thread(target=self._install_worker, args=(info,), daemon=True)
        thread.start()

    def _check_worker(self) -> None:
        try:
            info = check_for_updates()
        except Exception as exc:
            self.check_failed.emit(str(exc))
            return

        if info is not None:
            self.update_found.emit(info)

    def _install_worker(self, info: UpdateInfo) -> None:
        try:
            script_path = prepare_update(info)
        except Exception as exc:
            self.install_failed.emit(str(exc))
            return

        self.install_ready.emit(str(script_path))


def start_auto_update_check(parent: QWidget) -> None:
    if not getattr(sys, "frozen", False):
        return

    updater = AutoUpdater(parent)
    parent._auto_updater = updater  # type: ignore[attr-defined]
    updater.update_found.connect(lambda info: _prompt_update(parent, updater, info))
    updater.install_ready.connect(_run_update_script)
    updater.install_failed.connect(lambda message: _show_install_error(parent, message))
    updater.start()


def check_for_updates() -> UpdateInfo | None:
    current_version = read_current_version()
    release = _fetch_json(LATEST_RELEASE_URL)
    latest_version = str(release.get("tag_name") or release.get("name") or "").strip()
    if not latest_version:
        return None

    if _version_key(latest_version) <= _version_key(current_version):
        return None

    asset_url = _asset_download_url(release)
    if not asset_url:
        return None

    return UpdateInfo(
        version=latest_version,
        current_version=current_version,
        asset_url=asset_url,
        release_url=str(release.get("html_url") or ""),
    )


def read_current_version() -> str:
    version_path = app_root() / "version.txt"
    try:
        version = version_path.read_text(encoding="utf-8").splitlines()[0].strip()
    except (OSError, IndexError):
        version = "v0.0.0"
    return version or "v0.0.0"


def prepare_update(info: UpdateInfo) -> Path:
    temp_dir = Path(tempfile.mkdtemp(prefix="earth_photo_manager_update_"))
    archive_path = temp_dir / RELEASE_ASSET_NAME
    extract_dir = temp_dir / "extract"
    _download_file(info.asset_url, archive_path)

    with zipfile.ZipFile(archive_path) as archive:
        archive.extractall(extract_dir)

    source_dir = _find_extracted_app_dir(extract_dir)
    if source_dir is None:
        raise RuntimeError("更新ファイル内にアプリ本体が見つかりませんでした。")

    return _write_update_script(source_dir, app_root(), Path(sys.executable).resolve())


def _prompt_update(parent: QWidget, updater: AutoUpdater, info: UpdateInfo) -> None:
    result = QMessageBox.question(
        parent,
        "アップデート",
        (
            "新しいバージョンがあります。\n\n"
            f"現在: {info.current_version}\n"
            f"最新: {info.version}\n\n"
            "ダウンロードして更新しますか？"
        ),
        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        QMessageBox.StandardButton.Yes,
    )
    if result == QMessageBox.StandardButton.Yes:
        updater.install(info)


def _show_install_error(parent: QWidget, message: str) -> None:
    QMessageBox.warning(
        parent,
        "アップデート失敗",
        f"アップデートを準備できませんでした。\n\n{message}",
    )


def _run_update_script(script_path_text: str) -> None:
    script_path = Path(script_path_text)
    if sys.platform == "win32":
        subprocess.Popen(
            [
                "powershell.exe",
                "-NoProfile",
                "-ExecutionPolicy",
                "Bypass",
                "-File",
                str(script_path),
            ],
            close_fds=True,
        )
    else:
        subprocess.Popen([str(script_path)], close_fds=True)

    app = QApplication.instance()
    if app is not None:
        app.quit()


def _fetch_json(url: str) -> dict[str, object]:
    request = urllib.request.Request(
        url,
        headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": "earth_photo_manager",
        },
    )
    with urllib.request.urlopen(request, timeout=10) as response:
        return json.loads(response.read().decode("utf-8"))


def _download_file(url: str, destination: Path) -> None:
    request = urllib.request.Request(
        url,
        headers={"User-Agent": "earth_photo_manager"},
    )
    with urllib.request.urlopen(request, timeout=60) as response:
        with destination.open("wb") as file:
            shutil.copyfileobj(response, file)


def _asset_download_url(release: dict[str, object]) -> str | None:
    assets = release.get("assets")
    if not isinstance(assets, list):
        return None

    for asset in assets:
        if not isinstance(asset, dict):
            continue
        if asset.get("name") == RELEASE_ASSET_NAME:
            return str(asset.get("browser_download_url") or "")
    return None


def _find_extracted_app_dir(extract_dir: Path) -> Path | None:
    preferred = extract_dir / APP_FOLDER_NAME
    if (preferred / EXE_NAME).exists():
        return preferred

    for path in extract_dir.rglob(EXE_NAME):
        return path.parent
    return None


def _write_update_script(source_dir: Path, target_dir: Path, executable: Path) -> Path:
    if sys.platform == "win32":
        script_path = source_dir.parent / "apply_update.ps1"
        script_path.write_text(
            "\n".join(
                [
                    f"$pidToWait = {os.getpid()}",
                    f"$source = '{_powershell_literal(source_dir)}'",
                    f"$target = '{_powershell_literal(target_dir)}'",
                    f"$exe = '{_powershell_literal(executable)}'",
                    "Wait-Process -Id $pidToWait -ErrorAction SilentlyContinue",
                    "Start-Sleep -Milliseconds 500",
                    "Copy-Item -Path (Join-Path $source '*') -Destination $target -Recurse -Force",
                    "Start-Process -FilePath $exe -WorkingDirectory $target",
                ]
            ),
            encoding="utf-8",
        )
        return script_path

    script_path = source_dir.parent / "apply_update.sh"
    script_path.write_text(
        "\n".join(
            [
                "#!/bin/sh",
                f"while kill -0 {os.getpid()} 2>/dev/null; do sleep 1; done",
                "sleep 1",
                f"cp -R {shlex.quote(str(source_dir))}/. {shlex.quote(str(target_dir))}/",
                f"chmod +x {shlex.quote(str(executable))} 2>/dev/null || true",
                (
                    f"cd {shlex.quote(str(target_dir))} && "
                    f"{shlex.quote(str(executable))} >/dev/null 2>&1 &"
                ),
            ]
        ),
        encoding="utf-8",
    )
    script_path.chmod(0o755)
    return script_path


def _version_key(version: str) -> tuple[int, ...]:
    numbers = [int(part) for part in re.findall(r"\d+", version)]
    return tuple(numbers or [0])


def _powershell_literal(path: Path) -> str:
    return str(path).replace("'", "''")
