# Core Utils Desktop

Beautiful local installer for the Core Utils ecosystem, built with Python and Flet.

## Run

```bash
cd core-utils-projects/CoreUtilsDesktop
./init.sh
```

`init.sh` creates `.venv`, upgrades `pip`, installs all dependencies inside the venv, registers the desktop/menu launcher, and starts the app.

```bash
.venv/bin/python main.py
```

Use the venv Python directly after the first install if you do not want to reinstall dependencies on every launch.

## What it does

- Loads the same installable tools used by the `core-utils` web registry.
- Downloads repositories into `~/.core-utils-desktop/tools`.
- Installs Python tools with `pipx install --force .` when available, falling back to the local init scripts or `pip install`.
- Detects Python and system dependencies for each tool from `requirements.txt`, `pyproject.toml`, and known Core Utils runtime needs.
- Installs required distro packages automatically from the desktop hub on Fedora (`dnf`), Debian/Ubuntu (`apt-get`), and Arch (`pacman`).
- Shows each tool's dependency report from the `Dependencias` / `Dependencies` button.
- Starts desktop apps from the hub. If a desktop app has `requirements.txt` and no `.venv`, the hub creates the venv and installs dependencies before launching it.
- Shows local README files in an in-app Markdown info dialog.
- Updates tools with `git pull --ff-only` in the managed local clone and then reinstalls them.
- Uninstalls by attempting `pipx uninstall`, `pip uninstall`, and removing the managed local clone.
- Updates Core Utils Desktop itself when the app folder is a Git repository, then reinstalls its dependencies. Restart the app after a desktop update.
- Detects the desktop environment (Linux desktop session, macOS Finder, or Windows Explorer).
- Adds a launcher/icon to the desktop using the same Core Utils icon from the web assets.
- On Linux, installs a proper app menu entry in `~/.local/share/applications/core-utils-desktop.desktop`, installs the icon into the hicolor icon theme, and refreshes desktop/menu caches when the system tools are available.

The app keeps its state in `~/.core-utils-desktop/state.json`.
