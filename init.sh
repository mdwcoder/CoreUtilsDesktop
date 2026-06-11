#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="$ROOT_DIR/.venv"

has_libmpv() {
  if command -v ldconfig >/dev/null 2>&1 && ldconfig -p 2>/dev/null | grep -q 'libmpv.so.1'; then
    return 0
  fi
  [ -e /usr/lib64/libmpv.so.1 ] || [ -e /usr/lib/libmpv.so.1 ] || [ -e /usr/lib/x86_64-linux-gnu/libmpv.so.1 ]
}

run_as_admin() {
  if [ "$(id -u)" -eq 0 ]; then
    "$@"
  elif command -v pkexec >/dev/null 2>&1; then
    pkexec "$@"
  elif command -v sudo >/dev/null 2>&1; then
    sudo "$@"
  else
    echo "No se encontro pkexec, sudo ni permisos root para instalar dependencias del sistema." >&2
    return 1
  fi
}

install_native_flet_deps() {
  if has_libmpv; then
    return 0
  fi

  echo "Falta libmpv.so.1. Instalando dependencia nativa para ventanas Flet..."
  if command -v dnf >/dev/null 2>&1; then
    run_as_admin dnf install -y mpv-libs
  elif command -v apt-get >/dev/null 2>&1; then
    run_as_admin apt-get update
    run_as_admin apt-get install -y libmpv2
  elif command -v pacman >/dev/null 2>&1; then
    run_as_admin pacman -Sy --needed --noconfirm mpv
  else
    echo "No se encontro un gestor soportado. Soportado: Fedora/dnf, Debian-Ubuntu/apt-get, Arch/pacman." >&2
    return 1
  fi
}

has_webkit_gi() {
  python3 -c "import gi; gi.require_version('WebKit2', '4.1'); from gi.repository import WebKit2" >/dev/null 2>&1
}

install_native_webview_deps() {
  if has_webkit_gi; then
    return 0
  fi

  echo "Faltan PyGObject/WebKit2GTK. Instalando dependencias nativas para las ventanas web (Connect, Relay, EasyForms, Devs, Forge)..."
  if command -v dnf >/dev/null 2>&1; then
    run_as_admin dnf install -y python3-gobject webkit2gtk4.1
  elif command -v apt-get >/dev/null 2>&1; then
    run_as_admin apt-get update
    run_as_admin apt-get install -y python3-gi gir1.2-webkit2-4.1 libwebkit2gtk-4.1-0
  elif command -v pacman >/dev/null 2>&1; then
    run_as_admin pacman -Sy --needed --noconfirm python-gobject webkit2gtk-4.1
  else
    echo "No se encontro un gestor soportado para las dependencias de webview. Soportado: Fedora/dnf, Debian-Ubuntu/apt-get, Arch/pacman." >&2
    return 1
  fi
}

cd "$ROOT_DIR"

if [ ! -x "$VENV_DIR/bin/python" ]; then
  python3 -m venv --system-site-packages "$VENV_DIR"
fi

"$VENV_DIR/bin/python" -m pip install --upgrade pip
"$VENV_DIR/bin/python" -m pip install -r requirements.txt
install_native_flet_deps || true
install_native_webview_deps || true

"$VENV_DIR/bin/python" -m app.desktop_integration --quiet || true
exec "$VENV_DIR/bin/python" main.py
