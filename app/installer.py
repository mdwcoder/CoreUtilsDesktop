from __future__ import annotations

import json
import os
import shutil
import socket
import subprocess
import sys
import time
import tomllib
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

# Tools distributed as precompiled binaries (GitHub Releases) instead of
# being cloned and built/installed from source. Maps tool id -> binary name
# installed under ~/.local/bin.
BINARY_TOOLS: dict[str, str] = {
    "core-utils-cli": "cu",
}


@dataclass
class ToolState:
    status: str = "available"
    path: str = ""
    installed_at: str = ""
    last_action: str = ""


@dataclass(frozen=True)
class SystemDependency:
    key: str
    label: str
    check_commands: tuple[str, ...]
    fedora: tuple[str, ...]
    debian: tuple[str, ...]
    arch: tuple[str, ...]


@dataclass(frozen=True)
class DependencyReport:
    tool: str
    python_dependencies: tuple[str, ...]
    system_dependencies: tuple[SystemDependency, ...]
    missing_system_dependencies: tuple[SystemDependency, ...]
    install_commands: tuple[tuple[str, ...], ...]


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
            state.status = "installed" if tool.id in BINARY_TOOLS else "downloaded"
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
        if tool.id in BINARY_TOOLS:
            return Path.home() / ".local" / "bin" / BINARY_TOOLS[tool.id]
        return TOOLS_DIR / tool.repo_name


class Installer:
    def __init__(self, store: StateStore) -> None:
        self.store = store

    def download(self, tool: Tool, emit: Callable[[str], None]) -> bool:
        if tool.id in BINARY_TOOLS:
            return self._install_binary_tool(tool, emit, action="installed")
        if not self.ensure_system_dependencies(tool, emit):
            return False
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
        if tool.id in BINARY_TOOLS:
            return self._install_binary_tool(tool, emit, action="installed")
        if not self.ensure_system_dependencies(tool, emit):
            return False
        target = self.store.local_path(tool)
        if not target.exists():
            emit("Descargando antes de instalar...")
            if not self.download(tool, emit):
                return False
            if not self.ensure_system_dependencies(tool, emit):
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
        if tool.id in BINARY_TOOLS:
            return self._install_binary_tool(tool, emit, action="updated")
        if not self.ensure_system_dependencies(tool, emit):
            return False
        target = self.store.local_path(tool)
        if not target.exists():
            emit("La herramienta no está descargada. Descargando antes de actualizar...")
            if not self.download(tool, emit):
                return False
            if not self.ensure_system_dependencies(tool, emit):
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
        if not self.ensure_system_dependencies(tool, emit):
            return False
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
                emit("Falta libmpv.so.1 para abrir la ventana nativa de Flet.")
                emit("No se abrirá en modo web. Instala la dependencia nativa y vuelve a iniciar.")
                emit("Fedora: sudo dnf install mpv-libs")
                emit("Debian/Ubuntu: sudo apt install libmpv2")
                emit("Arch: sudo pacman -S mpv")
            for line in tail:
                emit(line)
            if index < len(commands):
                emit("Probando metodo alternativo de lanzamiento...")

        emit("No se pudo iniciar la aplicación. Revisa el log anterior.")
        return False

    def dependency_report(self, tool: Tool) -> DependencyReport:
        if tool.id in BINARY_TOOLS:
            return DependencyReport(
                tool=tool.name,
                python_dependencies=(),
                system_dependencies=(),
                missing_system_dependencies=(),
                install_commands=(),
            )
        target = self.resolve_tool_path(tool) or self.store.local_path(tool)
        python_dependencies = tuple(self._python_dependencies(target))
        system_dependencies = tuple(self._system_dependencies_for(tool, target, python_dependencies))
        missing = tuple(dep for dep in system_dependencies if not self._system_dependency_installed(dep))
        commands = tuple(self._install_commands_for(missing))
        return DependencyReport(
            tool=tool.name,
            python_dependencies=python_dependencies,
            system_dependencies=system_dependencies,
            missing_system_dependencies=missing,
            install_commands=commands,
        )

    def ensure_system_dependencies(self, tool: Tool, emit: Callable[[str], None]) -> bool:
        if tool.id in BINARY_TOOLS:
            return True
        report = self.dependency_report(tool)
        if not report.system_dependencies:
            return True
        if not report.missing_system_dependencies:
            emit("Dependencias de sistema verificadas.")
            return True
        if not report.install_commands:
            emit("Faltan dependencias de sistema, pero no se encontró un gestor soportado.")
            for dep in report.missing_system_dependencies:
                emit(f"- {dep.label}")
            return False

        emit("Instalando dependencias de sistema necesarias...")
        for command in report.install_commands:
            privileged = self._with_privilege(list(command))
            if privileged is None:
                emit("No se encontró pkexec, sudo ni permisos root para instalar dependencias del sistema.")
                emit(f"Ejecuta manualmente: {' '.join(command)}")
                return False
            if not self._run(privileged, cwd=DESKTOP_ROOT, emit=emit):
                return False

        refreshed = self.dependency_report(tool)
        if refreshed.missing_system_dependencies:
            emit("La instalación terminó, pero aún faltan dependencias:")
            for dep in refreshed.missing_system_dependencies:
                emit(f"- {dep.label}")
            return False
        return True

    def _python_dependencies(self, target: Path) -> list[str]:
        deps: list[str] = []
        requirements = target / "requirements.txt"
        if requirements.exists():
            for line in requirements.read_text(encoding="utf-8", errors="ignore").splitlines():
                stripped = line.strip()
                if stripped and not stripped.startswith("#"):
                    deps.append(stripped)

        pyproject = target / "pyproject.toml"
        if pyproject.exists():
            try:
                data = tomllib.loads(pyproject.read_text(encoding="utf-8"))
            except (tomllib.TOMLDecodeError, OSError):
                data = {}
            project = data.get("project", {}) if isinstance(data, dict) else {}
            for dep in project.get("dependencies", []) if isinstance(project, dict) else []:
                if isinstance(dep, str):
                    deps.append(dep)

        return sorted(dict.fromkeys(deps), key=str.lower)

    def _system_dependencies_for(self, tool: Tool, target: Path, python_dependencies: tuple[str, ...]) -> list[SystemDependency]:
        deps: list[SystemDependency] = [self._dependency_catalog()["python-venv"]]
        if self._requires_git(tool, target):
            deps.append(self._dependency_catalog()["git"])
        if self._uses_flet(target) or any("flet" in dep.lower() for dep in python_dependencies):
            deps.append(self._dependency_catalog()["flet-native"])
        if tool.id == "mmcli" or any("pyperclip" in dep.lower() for dep in python_dependencies):
            deps.append(self._dependency_catalog()["clipboard"])
        if tool.id == "mmcli":
            deps.append(self._dependency_catalog()["age"])
        if any("cryptography" in dep.lower() for dep in python_dependencies):
            deps.append(self._dependency_catalog()["crypto-runtime"])
        if tool.id in {"codejump", "repopulse", "workpulse", "devdrop"}:
            deps.append(self._dependency_catalog()["xdg-utils"])
        return list(dict.fromkeys(deps))

    def _requires_git(self, tool: Tool, target: Path) -> bool:
        if tool.repo_url.startswith("https://github.com") or "git clone" in tool.install_cmd:
            return True
        for path in (target / "README.md", target / "init.sh", target / "scripts" / "init.sh"):
            if path.exists() and "git" in path.read_text(encoding="utf-8", errors="ignore").lower():
                return True
        return False

    def _dependency_catalog(self) -> dict[str, SystemDependency]:
        return {
            "python-venv": SystemDependency(
                key="python-venv",
                label="Python 3, pip y venv",
                check_commands=("__python_venv__",),
                fedora=("python3", "python3-pip"),
                debian=("python3", "python3-pip", "python3-venv"),
                arch=("python", "python-pip"),
            ),
            "git": SystemDependency(
                key="git",
                label="Git",
                check_commands=("git",),
                fedora=("git",),
                debian=("git",),
                arch=("git",),
            ),
            "flet-native": SystemDependency(
                key="flet-native",
                label="Runtime nativo Flet (libmpv)",
                check_commands=("__libmpv__",),
                fedora=("mpv-libs",),
                debian=("libmpv2",),
                arch=("mpv",),
            ),
            "clipboard": SystemDependency(
                key="clipboard",
                label="Portapapeles Linux (xclip o wl-clipboard)",
                check_commands=("__clipboard__",),
                fedora=("xclip", "wl-clipboard"),
                debian=("xclip", "wl-clipboard"),
                arch=("xclip", "wl-clipboard"),
            ),
            "age": SystemDependency(
                key="age",
                label="age encryption CLI",
                check_commands=("age",),
                fedora=("age",),
                debian=("age",),
                arch=("age",),
            ),
            "crypto-runtime": SystemDependency(
                key="crypto-runtime",
                label="Runtime de criptografia del sistema",
                check_commands=("openssl",),
                fedora=("openssl", "libffi"),
                debian=("openssl", "libffi8"),
                arch=("openssl", "libffi"),
            ),
            "xdg-utils": SystemDependency(
                key="xdg-utils",
                label="Integracion de escritorio Linux",
                check_commands=("xdg-open",),
                fedora=("xdg-utils",),
                debian=("xdg-utils",),
                arch=("xdg-utils",),
            ),
        }

    def _system_dependency_installed(self, dependency: SystemDependency) -> bool:
        for check in dependency.check_commands:
            if check == "__libmpv__":
                if self._has_libmpv() or self._libmpv_compat_dir() is not None or self._find_libmpv_compat_source() is not None:
                    return True
                continue
            if check == "__clipboard__":
                if shutil.which("xclip") or shutil.which("wl-copy"):
                    return True
                continue
            if check == "__python_venv__":
                if self._has_python_venv():
                    return True
                continue
            if shutil.which(check):
                return True
        return False

    def _install_commands_for(self, dependencies: tuple[SystemDependency, ...]) -> list[tuple[str, ...]]:
        packages: list[str] = []
        if shutil.which("dnf"):
            for dep in dependencies:
                packages.extend(dep.fedora)
            return [("dnf", "install", "-y", *self._unique(packages))] if packages else []
        if shutil.which("apt-get"):
            for dep in dependencies:
                packages.extend(dep.debian)
            return [("apt-get", "update"), ("apt-get", "install", "-y", *self._unique(packages))] if packages else []
        if shutil.which("pacman"):
            for dep in dependencies:
                packages.extend(dep.arch)
            return [("pacman", "-Sy", "--needed", "--noconfirm", *self._unique(packages))] if packages else []
        return []

    def _unique(self, values: list[str]) -> list[str]:
        return list(dict.fromkeys(value for value in values if value))

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
            if not self._ensure_native_flet_dependencies(target, emit):
                return False
            return self._ensure_flet_runtime(target, python, emit)
        return True

    def _ensure_native_flet_dependencies(self, target: Path, emit: Callable[[str], None]) -> bool:
        if self._has_libmpv():
            return True
        if self._prepare_libmpv_compat(emit):
            return True

        commands = self._native_dependency_install_commands()
        if not commands:
            emit("Falta libmpv.so.1 y no se encontró un gestor soportado para instalarla automaticamente.")
            emit("Soportado: Fedora/dnf, Debian-Ubuntu/apt-get, Arch/pacman.")
            return False

        emit("Falta libmpv.so.1. Instalando dependencia nativa para ventanas Flet...")
        for command in commands:
            privileged = self._with_privilege(command)
            if privileged is None:
                emit("No se encontró pkexec, sudo ni permisos root para instalar dependencias del sistema.")
                emit(f"Ejecuta manualmente: {' '.join(command)}")
                return False
            if not self._run(privileged, cwd=target, emit=emit):
                return False

        if not self._has_libmpv() and not self._prepare_libmpv_compat(emit):
            emit("La instalación terminó, pero libmpv.so.1 aún no aparece disponible.")
            return False
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
        needed = ["flet-cli"]
        if version.startswith("0.28."):
            needed.append("flet-desktop-light")
        else:
            needed.append("flet-desktop")
        if all(self._pip_has(python, package, target) for package in needed):
            return True

        emit(f"Preparando runtime Flet {version}...")
        packages = [f"{package}=={version}" for package in needed]
        return self._run(
            [str(python), "-m", "pip", "install", *packages],
            cwd=target,
            emit=emit,
        )

    def read_readme(self, tool: Tool) -> tuple[str, Path | None]:
        if tool.id in BINARY_TOOLS:
            return (
                f"{tool.name} se distribuye como binario precompilado y no se descarga como "
                f"código fuente.\n\nConsulta el README en {tool.repo_url.removesuffix('.git')}",
                None,
            )
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
        if tool.id in BINARY_TOOLS:
            return None
        local = PROJECTS_ROOT / tool.repo_name
        if local.exists():
            return local
        return None

    def _install_binary_tool(self, tool: Tool, emit: Callable[[str], None], action: str) -> bool:
        target = self.store.local_path(tool)
        emit(f"{tool.name} se distribuye como binario precompilado (GitHub Releases).")
        emit(f"Ejecutando: {tool.install_cmd}")
        return self._run(
            ["bash", "-lc", tool.install_cmd],
            cwd=TOOLS_DIR,
            emit=emit,
            success=lambda: self._mark(tool, "installed", action, path=str(target)),
        )

    def uninstall(self, tool: Tool, emit: Callable[[str], None]) -> bool:
        if tool.id in BINARY_TOOLS:
            target = self.store.local_path(tool)
            if target.exists():
                emit(f"Eliminando binario: {target}")
                try:
                    target.unlink()
                except OSError as exc:
                    emit(f"No se pudo eliminar {target}: {exc}")
                    return False
            else:
                emit(f"{tool.name} no estaba instalado en {target}")
            self._mark(tool, "available", "uninstalled", path="")
            return True

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
        if is_flet and flet_cli and module is not None:
            module_command = [str(flet_cli), "run", "-m"]
            if flet_port:
                module_command.extend(["-p", flet_port])
            module_command.append(module)
            commands.append(module_command)

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
            lib_dir = self._libmpv_compat_dir()
            if lib_dir is not None:
                current = env.get("LD_LIBRARY_PATH") or os.environ.get("LD_LIBRARY_PATH", "")
                env["LD_LIBRARY_PATH"] = f"{lib_dir}:{current}" if current else str(lib_dir)
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

    def _has_libmpv(self) -> bool:
        try:
            result = subprocess.run(["ldconfig", "-p"], capture_output=True, text=True, timeout=10)
        except (OSError, subprocess.TimeoutExpired):
            result = None
        if result is not None and result.returncode == 0 and "libmpv.so.1" in result.stdout:
            return True

        common_paths = (
            "/usr/lib64/libmpv.so.1",
            "/usr/lib/libmpv.so.1",
            "/usr/lib/x86_64-linux-gnu/libmpv.so.1",
        )
        return any(Path(path).exists() for path in common_paths)

    def _find_libmpv_compat_source(self) -> Path | None:
        try:
            result = subprocess.run(["ldconfig", "-p"], capture_output=True, text=True, timeout=10)
        except (OSError, subprocess.TimeoutExpired):
            result = None
        if result is not None and result.returncode == 0:
            for line in result.stdout.splitlines():
                if "libmpv.so." in line and "=>" in line:
                    candidate = Path(line.split("=>", 1)[1].strip())
                    if candidate.exists():
                        return candidate

        for path in (
            "/usr/lib64/libmpv.so.2",
            "/lib64/libmpv.so.2",
            "/usr/lib/libmpv.so.2",
            "/usr/lib/x86_64-linux-gnu/libmpv.so.2",
            "/lib/x86_64-linux-gnu/libmpv.so.2",
            "/usr/local/lib/libmpv.so.2",
            "/usr/lib64/libmpv.so",
            "/lib64/libmpv.so",
            "/usr/lib/libmpv.so",
            "/usr/lib/x86_64-linux-gnu/libmpv.so",
        ):
            candidate = Path(path)
            if candidate.exists():
                return candidate
        return None

    def _libmpv_compat_dir(self) -> Path | None:
        for directory in self._native_lib_dirs():
            link = directory / "libmpv.so.1"
            if link.exists():
                return link.parent
        return None

    def _prepare_libmpv_compat(self, emit: Callable[[str], None]) -> bool:
        source = self._find_libmpv_compat_source()
        if source is None:
            return False

        last_error: OSError | None = None
        for target_dir in self._native_lib_dirs():
            target = target_dir / "libmpv.so.1"
            try:
                target_dir.mkdir(parents=True, exist_ok=True)
                if target.exists() or target.is_symlink():
                    target.unlink()
                target.symlink_to(source)
            except OSError as exc:
                last_error = exc
                continue

            emit(f"Compatibilidad libmpv preparada: {target} -> {source}")
            return True

        if last_error is not None:
            emit(f"No se pudo preparar compatibilidad libmpv local: {last_error}")
        return False

    def _native_lib_dirs(self) -> tuple[Path, ...]:
        return (
            APP_DIR / "runtime" / "native-libs",
            Path("/tmp") / "core-utils-desktop" / "native-libs",
        )

    def _has_python_venv(self) -> bool:
        python = shutil.which("python3") or shutil.which("python")
        if not python:
            return False
        try:
            result = subprocess.run([python, "-m", "venv", "--help"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=10)
        except (OSError, subprocess.TimeoutExpired):
            return False
        return result.returncode == 0

    def _native_dependency_install_commands(self) -> list[list[str]]:
        if shutil.which("dnf"):
            return [["dnf", "install", "-y", "mpv-libs"]]
        if shutil.which("apt-get"):
            return [["apt-get", "update"], ["apt-get", "install", "-y", "libmpv2"]]
        if shutil.which("pacman"):
            return [["pacman", "-Sy", "--needed", "--noconfirm", "mpv"]]
        return []

    def _with_privilege(self, command: list[str]) -> list[str] | None:
        if hasattr(os, "geteuid") and os.geteuid() == 0:
            return command
        if shutil.which("pkexec"):
            return ["pkexec", *command]
        if shutil.which("sudo"):
            return ["sudo", *command]
        return None

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
