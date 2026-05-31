from __future__ import annotations

import os
import platform
import shutil
import stat
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Callable


PROJECT_ROOT = Path(__file__).resolve().parents[1]
ASSET_ICON = PROJECT_ROOT / "assets" / "icon.png"
APP_HOME = Path.home() / ".core-utils-desktop"
LAUNCHER_SCRIPT = APP_HOME / "core-utils-desktop.sh"
APP_ID = "core-utils-desktop"
ICON_NAME = APP_ID


@dataclass(frozen=True)
class DesktopEnvironment:
    os_name: str
    desktop_name: str
    shortcut_kind: str
    can_create_shortcut: bool


def detect_desktop_environment() -> DesktopEnvironment:
    system = platform.system()
    if system == "Linux":
        desktop = (
            os.environ.get("XDG_CURRENT_DESKTOP")
            or os.environ.get("DESKTOP_SESSION")
            or os.environ.get("GDMSESSION")
            or "Linux Desktop"
        )
        return DesktopEnvironment("Linux", desktop, ".desktop", True)
    if system == "Darwin":
        return DesktopEnvironment("macOS", "Finder", ".command", True)
    if system == "Windows":
        return DesktopEnvironment("Windows", "Explorer", ".bat", True)
    return DesktopEnvironment(system or "Unknown", "Unknown", "manual", False)


def install_desktop_shortcut(emit: Callable[[str], None]) -> bool:
    env = detect_desktop_environment()
    emit(f"Sistema detectado: {env.os_name} · {env.desktop_name}")
    if not env.can_create_shortcut:
        emit("No hay integración automática para este sistema.")
        return False

    APP_HOME.mkdir(parents=True, exist_ok=True)
    _write_launcher_script()

    if env.os_name == "Linux":
        return _install_linux_shortcut(emit)
    if env.os_name == "macOS":
        return _install_macos_shortcut(emit)
    if env.os_name == "Windows":
        return _install_windows_shortcut(emit)
    return False


def _write_launcher_script() -> None:
    python = _app_python()
    content = f"""#!/usr/bin/env bash
set -euo pipefail
cd "{PROJECT_ROOT}"
exec "{python}" main.py
"""
    LAUNCHER_SCRIPT.write_text(content, encoding="utf-8")
    LAUNCHER_SCRIPT.chmod(LAUNCHER_SCRIPT.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)


def _desktop_dir() -> Path:
    user_dirs = Path.home() / ".config" / "user-dirs.dirs"
    if user_dirs.exists():
        for line in user_dirs.read_text(encoding="utf-8", errors="ignore").splitlines():
            if line.startswith("XDG_DESKTOP_DIR="):
                raw = line.split("=", 1)[1].strip().strip('"')
                return Path(raw.replace("$HOME", str(Path.home())))

    for candidate in (Path.home() / "Desktop", Path.home() / "Escritorio"):
        if candidate.exists():
            return candidate
    return Path.home() / "Desktop"


def _desktop_file_content() -> str:
    return f"""[Desktop Entry]
Version=1.0
Type=Application
Name=Core Utils Desktop
GenericName=Core Utils Hub
Comment=Install, update and uninstall Core Utils tools
Exec={LAUNCHER_SCRIPT}
TryExec={LAUNCHER_SCRIPT}
Icon={ICON_NAME if ASSET_ICON.exists() else "utilities-terminal"}
Terminal=false
Categories=Development;Utility;PackageManager;
Keywords=core-utils;core utils;developer tools;installer;hub;python;cli;desktop;
StartupNotify=true
NoDisplay=false
StartupWMClass=Core Utils Desktop
"""


def _install_linux_shortcut(emit: Callable[[str], None]) -> bool:
    _install_linux_icon(emit)
    content = _desktop_file_content()
    applications_dir = Path.home() / ".local" / "share" / "applications"
    applications_dir.mkdir(parents=True, exist_ok=True)
    app_entry = applications_dir / f"{APP_ID}.desktop"
    app_entry.write_text(content, encoding="utf-8")
    _make_executable(app_entry)
    emit(f"Entrada de menú creada: {app_entry}")

    desktop = _desktop_dir()
    try:
        desktop.mkdir(parents=True, exist_ok=True)
        desktop_entry = desktop / f"{APP_ID}.desktop"
        desktop_entry.write_text(content, encoding="utf-8")
        _make_executable(desktop_entry)
        emit(f"Icono añadido al escritorio: {desktop_entry}")
    except OSError as exc:
        emit(f"No se pudo escribir en el escritorio: {exc}")

    _refresh_linux_desktop_databases(applications_dir, emit)
    return True


def _install_linux_icon(emit: Callable[[str], None]) -> None:
    if not ASSET_ICON.exists():
        emit("No se encontró el icono local; se usará el icono genérico del sistema.")
        return
    icon_dir = Path.home() / ".local" / "share" / "icons" / "hicolor" / "256x256" / "apps"
    icon_dir.mkdir(parents=True, exist_ok=True)
    icon_target = icon_dir / f"{ICON_NAME}.png"
    shutil.copy2(ASSET_ICON, icon_target)
    emit(f"Icono instalado para menús: {icon_target}")


def _refresh_linux_desktop_databases(applications_dir: Path, emit: Callable[[str], None]) -> None:
    commands = [
        ["xdg-desktop-menu", "forceupdate"],
        ["update-desktop-database", str(applications_dir)],
        ["gtk-update-icon-cache", "-f", "-t", str(Path.home() / ".local" / "share" / "icons" / "hicolor")],
    ]
    for command in commands:
        if not shutil.which(command[0]):
            continue
        try:
            result = subprocess.run(command, check=False, capture_output=True, text=True, timeout=20)
        except (OSError, subprocess.TimeoutExpired) as exc:
            emit(f"No se pudo ejecutar {' '.join(command)}: {exc}")
            continue
        if result.returncode == 0:
            emit(f"Cache de escritorio actualizada: {' '.join(command)}")
        elif result.stderr.strip():
            emit(f"{command[0]} avisó: {result.stderr.strip()}")


def _install_macos_shortcut(emit: Callable[[str], None]) -> bool:
    desktop = Path.home() / "Desktop"
    desktop.mkdir(parents=True, exist_ok=True)
    shortcut = desktop / "Core Utils Desktop.command"
    shortcut.write_text(
        f"""#!/usr/bin/env bash
cd "{PROJECT_ROOT}"
exec "{_app_python()}" main.py
""",
        encoding="utf-8",
    )
    shortcut.chmod(shortcut.stat().st_mode | stat.S_IXUSR)
    emit(f"Lanzador añadido al escritorio: {shortcut}")
    return True


def _install_windows_shortcut(emit: Callable[[str], None]) -> bool:
    desktop = Path.home() / "Desktop"
    desktop.mkdir(parents=True, exist_ok=True)
    shortcut = desktop / "Core Utils Desktop.bat"
    shortcut.write_text(
        f"""@echo off
cd /d "{PROJECT_ROOT}"
"{_app_python()}" main.py
""",
        encoding="utf-8",
    )
    emit(f"Lanzador añadido al escritorio: {shortcut}")
    return True


def _app_python() -> Path:
    if platform.system() == "Windows":
        venv_python = PROJECT_ROOT / ".venv" / "Scripts" / "python.exe"
    else:
        venv_python = PROJECT_ROOT / ".venv" / "bin" / "python"
    return venv_python if venv_python.exists() else Path(sys.executable)


def _make_executable(path: Path) -> None:
    path.chmod(path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)


def main() -> None:
    quiet = "--quiet" in sys.argv

    def emit(message: str) -> None:
        if not quiet:
            print(message)

    ok = install_desktop_shortcut(emit)
    raise SystemExit(0 if ok else 1)


if __name__ == "__main__":
    main()
