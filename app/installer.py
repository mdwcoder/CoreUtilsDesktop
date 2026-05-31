from __future__ import annotations

import json
import os
import shutil
import socket
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Callable

from app.catalog import Tool


APP_DIR = Path.home() / ".core-utils-desktop"
TOOLS_DIR = APP_DIR / "tools"
STATE_PATH = APP_DIR / "state.json"
LOGS_DIR = APP_DIR / "logs"
DESKTOP_ROOT = Path(__file__).resolve().parents[1]
PROJECTS_ROOT = DESKTOP_ROOT.parent


@dataclass
class ToolState:
    status: str = "available"
    path: str = ""
    installed_at: str = ""
    last_action: str = ""


class StateStore:
    def __init__(self) -> None:
        APP_DIR.mkdir(parents=True, exist_ok=True)
        TOOLS_DIR.mkdir(parents=True, exist_ok=True)
        self._data: dict[str, dict[str, str]] = self._read()

    def _read(self) -> dict[str, dict[str, str]]:
        if not STATE_PATH.exists():
            return {}
        try:
            raw = json.loads(STATE_PATH.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {}
        return raw if isinstance(raw, dict) else {}

    def save(self) -> None:
        STATE_PATH.write_text(json.dumps(self._data, indent=2), encoding="utf-8")

    def get(self, tool: Tool) -> ToolState:
        raw = self._data.get(tool.id, {})
        state = ToolState(
            status=raw.get("status", "available"),
            path=raw.get("path", ""),
            installed_at=raw.get("installed_at", ""),
            last_action=raw.get("last_action", ""),
        )
        if self.local_path(tool).exists() and state.status == "available":
            state.status = "downloaded"
        return state

    def set(self, tool: Tool, state: ToolState) -> None:
        self._data[tool.id] = {
            "status": state.status,
            "path": state.path,
            "installed_at": state.installed_at,
            "last_action": state.last_action,
        }
        self.save()

    def local_path(self, tool: Tool) -> Path:
        return TOOLS_DIR / tool.repo_name


class Installer:
    def __init__(self, store: StateStore) -> None:
        self.store = store

    def download(self, tool: Tool, emit: Callable[[str], None]) -> bool:
        target = self.store.local_path(tool)
        if target.exists():
            emit(f"{tool.name} ya está descargado en {target}")
            self._mark(tool, "downloaded", "downloaded")
            return True
        return self._run(
            ["git", "clone", tool.repo_url, str(target)],
            cwd=TOOLS_DIR,
            emit=emit,
            success=lambda: self._mark(tool, "downloaded", "downloaded"),
        )

    def install(self, tool: Tool, emit: Callable[[str], None]) -> bool:
        target = self.store.local_path(tool)
        if not target.exists():
            emit("Descargando antes de instalar...")
            if not self.download(tool, emit):
                return False

        command = self._local_install_command(tool, target)
        emit(f"Ejecutando: {' '.join(command)}")
        return self._run(
            command,
            cwd=target,
            emit=emit,
            success=lambda: self._mark(tool, "installed", "installed"),
        )

    def update(self, tool: Tool, emit: Callable[[str], None]) -> bool:
        target = self.store.local_path(tool)
        if not target.exists():
            emit("La herramienta no está descargada. Descargando antes de actualizar...")
            if not self.download(tool, emit):
                return False

        if (target / ".git").exists():
            emit(f"Actualizando código en {target}")
            if not self._run(["git", "pull", "--ff-only"], cwd=target, emit=emit):
                return False
        else:
            emit("La carpeta local no es un repositorio Git; se reinstalará la versión existente.")

        command = self._local_install_command(tool, target)
        emit(f"Reinstalando: {' '.join(command)}")
        return self._run(
            command,
            cwd=target,
            emit=emit,
            success=lambda: self._mark(tool, "installed", "updated"),
        )

    def update_desktop(self, emit: Callable[[str], None]) -> bool:
        ok = True
        if (DESKTOP_ROOT / ".git").exists():
            emit(f"Actualizando Core Utils Desktop en {DESKTOP_ROOT}")
            ok = self._run(["git", "pull", "--ff-only"], cwd=DESKTOP_ROOT, emit=emit)
            if not ok:
                return False
        else:
            emit("Core Utils Desktop no está dentro de un repositorio Git propio; se omite git pull.")

        requirements = DESKTOP_ROOT / "requirements.txt"
        if requirements.exists():
            emit("Reinstalando dependencias del desktop...")
            ok = self._run(
                [sys.executable, "-m", "pip", "install", "-r", str(requirements)],
                cwd=DESKTOP_ROOT,
                emit=emit,
            )
        else:
            emit("No se encontró requirements.txt para reinstalar dependencias.")

        if ok:
            emit("Core Utils Desktop actualizado. Reinicia la app para cargar cambios de código.")
        return ok

    def launch(self, tool: Tool, emit: Callable[[str], None]) -> bool:
        target = self.resolve_tool_path(tool)
        if target is None:
            emit("No se encontró la herramienta localmente. Descárgala o instálala primero.")
            return False
        if tool.category != "Desktop" and "Desktop" not in tool.targets:
            emit("Esta acción está pensada para aplicaciones de escritorio.")
            return False

        if not self._ensure_desktop_runtime(target, emit):
            return False

        launch_env = self._launch_env(target, tool.id)
        commands = self._launch_commands(target, launch_env.get("FLET_SERVER_PORT"))
        if not commands:
            emit(f"No se encontró un punto de entrada desktop en {target}")
            return False

        log_path = self._log_path(tool.id)
        env = os.environ.copy()
        env["PYTHONUNBUFFERED"] = "1"
        env.update(launch_env)

        for index, command in enumerate(commands, start=1):
            emit(f"Iniciando {tool.name}: {' '.join(command)}")
            emit(f"Log: {log_path}")
            try:
                with log_path.open("a", encoding="utf-8") as log:
                    log.write(f"\n\n[{datetime.now().isoformat(timespec='seconds')}] {' '.join(command)}\n")
                    process = subprocess.Popen(
                        command,
                        cwd=str(target),
                        stdout=log,
                        stderr=subprocess.STDOUT,
                        stdin=subprocess.DEVNULL,
                        env=env,
                        start_new_session=True,
                    )
            except OSError as exc:
                emit(str(exc))
                continue

            code = self._wait_for_early_exit(process, seconds=8)
            if code is None:
                emit("Aplicación iniciada en un proceso independiente.")
                return True

            emit(f"El proceso terminó al arrancar con código {code}.")
            tail = self._tail_lines(log_path, limit=18)
            if self._mentions_missing_libmpv(tail):
                emit("Falta libmpv.so.1 para la ventana nativa de Flet. Se intentara abrir en modo web.")
                emit("En Fedora suele resolverse instalando mpv-libs; en Debian/Ubuntu, libmpv2.")
            for line in tail:
                emit(line)
            if index < len(commands):
                emit("Probando metodo alternativo de lanzamiento...")

        emit("No se pudo iniciar la aplicación. Revisa el log anterior.")
        return False

    def _ensure_desktop_runtime(self, target: Path, emit: Callable[[str], None]) -> bool:
        requirements = target / "requirements.txt"
        python = self._venv_python(target)
        if requirements.exists() and python is None:
            venv_dir = target / ".venv"
            emit(f"Preparando entorno virtual para {target.name}: {venv_dir}")
            if not self._run([sys.executable, "-m", "venv", str(venv_dir)], cwd=target, emit=emit):
                return False
            python = self._venv_python(target)
            if python is None:
                emit("No se pudo localizar el Python del entorno virtual recién creado.")
                return False

        if requirements.exists() and python is not None:
            emit("Verificando dependencias de la aplicación desktop...")
            if not self._run([str(python), "-m", "pip", "install", "-r", str(requirements)], cwd=target, emit=emit):
                return False

        if python is not None and self._uses_flet(target):
            return self._ensure_flet_runtime(target, python, emit)
        return True

    def _ensure_flet_runtime(self, target: Path, python: Path, emit: Callable[[str], None]) -> bool:
        version = self._python_output(
            [str(python), "-c", "import flet; print(getattr(flet, '__version__', ''))"],
            cwd=target,
        )
        if not version:
            return True

        # Flet apps lazy-install their CLI/desktop runtime if only the base
        # package is present. Check installed distributions, not import names,
        # because older Flet releases ship flet-desktop-light.
        needed = ["flet-cli", "flet-web"]
        if version.startswith("0.28."):
            needed.append("flet-desktop-light")
        else:
            needed.append("flet-desktop")
        if all(self._pip_has(python, package, target) for package in needed):
            return True

        emit(f"Preparando runtime Flet {version}...")
        return self._run(
            [str(python), "-m", "pip", "install", f"flet[all]=={version}"],
            cwd=target,
            emit=emit,
        )

    def read_readme(self, tool: Tool) -> tuple[str, Path | None]:
        target = self.resolve_tool_path(tool)
        if target is None:
            return (
                "README no disponible localmente.\n\nDescarga o instala la herramienta para verlo desde el hub.",
                None,
            )
        for name in ("README.md", "readme.md", "README", "README.txt"):
            path = target / name
            if path.exists():
                return path.read_text(encoding="utf-8", errors="replace"), path
        return (f"No se encontró README en {target}", None)

    def resolve_tool_path(self, tool: Tool) -> Path | None:
        managed = self.store.local_path(tool)
        if managed.exists():
            return managed
        local = PROJECTS_ROOT / tool.repo_name
        if local.exists():
            return local
        return None

    def uninstall(self, tool: Tool, emit: Callable[[str], None]) -> bool:
        target = self.store.local_path(tool)
        package = self._package_name(target) or tool.id
        ok = True

        emit(f"Intentando desinstalar paquete Python: {package}")
        pipx = shutil.which("pipx")
        if pipx:
            self._run([pipx, "uninstall", package], cwd=TOOLS_DIR, emit=emit, allow_failure=True)

        self._run([sys.executable, "-m", "pip", "uninstall", "-y", package], cwd=TOOLS_DIR, emit=emit, allow_failure=True)

        if target.exists():
            emit(f"Eliminando descarga local: {target}")
            try:
                shutil.rmtree(target)
            except OSError as exc:
                emit(f"No se pudo eliminar {target}: {exc}")
                ok = False

        if ok:
            self._mark(tool, "available", "uninstalled", path="")
        return ok

    def _local_install_command(self, tool: Tool, target: Path) -> list[str]:
        if shutil.which("pipx") and (target / "pyproject.toml").exists():
            return ["pipx", "install", "--force", "."]
        if (target / "init.sh").exists():
            return ["bash", "init.sh"]
        if (target / "scripts" / "init.sh").exists():
            return ["bash", "scripts/init.sh"]
        if (target / "pyproject.toml").exists():
            return [sys.executable, "-m", "pip", "install", "."]
        if (target / "requirements.txt").exists():
            return [sys.executable, "-m", "pip", "install", "-r", "requirements.txt"]
        return ["bash", "-lc", tool.install_cmd]

    def _launch_commands(self, target: Path, flet_port: str | None = None) -> list[list[str]]:
        python = self._venv_python(target) or Path(sys.executable)
        commands: list[list[str]] = []
        is_flet = self._uses_flet(target)
        if (target / "main.py").exists():
            commands.append([str(python), "main.py"])

        package_main = next(target.glob("*/main.py"), None)
        module: str | None = None
        if package_main is not None:
            module = f"{package_main.parent.name}.main"
            commands.append([str(python), "-m", module])

        flet_cli = self._venv_executable(target, "flet")
        if flet_cli and (target / "main.py").exists():
            flet_command = [str(flet_cli), "run"]
            if flet_port:
                flet_command.extend(["-p", flet_port])
            flet_command.append("main.py")
            commands.append(flet_command)
            if is_flet:
                web_command = [str(flet_cli), "run", "-w"]
                if flet_port:
                    web_command.extend(["-p", flet_port])
                web_command.append("main.py")
                commands.append(web_command)
        if is_flet and flet_cli and module is not None:
            module_command = [str(flet_cli), "run", "-m"]
            if flet_port:
                module_command.extend(["-p", flet_port])
            module_command.append(module)
            commands.append(module_command)

            module_web_command = [str(flet_cli), "run", "-w", "-m"]
            if flet_port:
                module_web_command.extend(["-p", flet_port])
            module_web_command.append(module)
            commands.append(module_web_command)

        return commands

    def _launch_env(self, target: Path, tool_id: str) -> dict[str, str]:
        env: dict[str, str] = {}
        if self._uses_flet(target):
            port = self._free_tcp_port()
            if port:
                env["FLET_SERVER_PORT"] = str(port)

            runtime_dir = APP_DIR / "runtime" / tool_id
            data_dir = runtime_dir / "data"
            temp_dir = runtime_dir / "temp"
            try:
                data_dir.mkdir(parents=True, exist_ok=True)
                temp_dir.mkdir(parents=True, exist_ok=True)
                env["FLET_APP_STORAGE_DATA"] = str(data_dir)
                env["FLET_APP_STORAGE_TEMP"] = str(temp_dir)
            except OSError:
                pass
        return env

    def _free_tcp_port(self) -> int | None:
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                sock.bind(("127.0.0.1", 0))
                return int(sock.getsockname()[1])
        except OSError:
            return None

    def _venv_python(self, target: Path) -> Path | None:
        if sys.platform == "win32":
            python = target / ".venv" / "Scripts" / "python.exe"
        else:
            python = target / ".venv" / "bin" / "python"
        return python if python.exists() else None

    def _venv_executable(self, target: Path, name: str) -> Path | None:
        if sys.platform == "win32":
            executable = target / ".venv" / "Scripts" / f"{name}.exe"
        else:
            executable = target / ".venv" / "bin" / name
        return executable if executable.exists() else None

    def _uses_flet(self, target: Path) -> bool:
        requirements = target / "requirements.txt"
        if requirements.exists() and "flet" in requirements.read_text(encoding="utf-8", errors="ignore").lower():
            return True
        for path in (target / "main.py", *target.glob("*/main.py")):
            if path.exists() and "import flet" in path.read_text(encoding="utf-8", errors="ignore"):
                return True
        return False

    def _python_output(self, command: list[str], cwd: Path) -> str:
        try:
            result = subprocess.run(command, cwd=str(cwd), capture_output=True, text=True, timeout=20)
        except (OSError, subprocess.TimeoutExpired):
            return ""
        if result.returncode != 0:
            return ""
        return result.stdout.strip()

    def _pip_has(self, python: Path, package: str, cwd: Path) -> bool:
        try:
            result = subprocess.run(
                [str(python), "-m", "pip", "show", package],
                cwd=str(cwd),
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=20,
            )
        except (OSError, subprocess.TimeoutExpired):
            return False
        return result.returncode == 0

    def _wait_for_early_exit(self, process: subprocess.Popen[str], seconds: int) -> int | None:
        deadline = time.monotonic() + seconds
        while time.monotonic() < deadline:
            code = process.poll()
            if code is not None:
                return code
            time.sleep(0.25)
        return process.poll()

    def _tail_lines(self, path: Path, limit: int = 20) -> list[str]:
        if not path.exists():
            return []
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        return lines[-limit:]

    def _mentions_missing_libmpv(self, lines: list[str]) -> bool:
        text = "\n".join(lines).lower()
        return "libmpv.so.1" in text and "cannot open shared object file" in text

    def _log_path(self, tool_id: str) -> Path:
        for directory in (LOGS_DIR, Path("/tmp") / "core-utils-desktop-logs"):
            try:
                directory.mkdir(parents=True, exist_ok=True)
                return directory / f"{tool_id}.log"
            except OSError:
                continue
        return Path(f"{tool_id}.log")

    def _package_name(self, target: Path) -> str | None:
        pyproject = target / "pyproject.toml"
        if not pyproject.exists():
            return None
        for line in pyproject.read_text(encoding="utf-8", errors="ignore").splitlines():
            stripped = line.strip()
            if stripped.startswith("name ="):
                return stripped.split("=", 1)[1].strip().strip('"').strip("'")
        return None

    def _mark(self, tool: Tool, status: str, action: str, path: str | None = None) -> None:
        local = self.store.local_path(tool)
        self.store.set(
            tool,
            ToolState(
                status=status,
                path=str(local) if path is None else path,
                installed_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S") if status == "installed" else "",
                last_action=action,
            ),
        )

    def _run(
        self,
        command: list[str],
        cwd: Path,
        emit: Callable[[str], None],
        success: Callable[[], None] | None = None,
        allow_failure: bool = False,
    ) -> bool:
        env = os.environ.copy()
        env["PYTHONUNBUFFERED"] = "1"
        try:
            process = subprocess.Popen(
                command,
                cwd=str(cwd),
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                env=env,
            )
        except OSError as exc:
            emit(str(exc))
            return allow_failure

        assert process.stdout is not None
        for line in process.stdout:
            emit(line.rstrip())
        code = process.wait()
        if code == 0:
            if success:
                success()
            emit("Completado correctamente.")
            return True
        emit(f"El comando terminó con código {code}.")
        return allow_failure
