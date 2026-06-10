from __future__ import annotations

import json
import shutil
import subprocess
import threading
from collections import Counter

import flet as ft

from app.catalog import Tool, load_tools
from app.desktop_integration import detect_desktop_environment, install_desktop_shortcut
from app.forge_api import ForgeApiClient, ForgeApiError, ForgeUser, run_desktop_login
from app.installer import APP_DIR, TOOLS_DIR, Installer, StateStore
from app import theme


SETTINGS_PATH = APP_DIR / "settings.json"

TRANSLATIONS = {
    "es": {
        "desktop_installer": "Instalador de escritorio",
        "tools_count": "{count} herramientas",
        "add_shortcut": "Anadir icono al escritorio",
        "settings": "Ajustes",
        "tools": "Herramientas",
        "forge": "Forge",
        "github_sign_in": "Entrar con GitHub",
        "github_sign_out": "Salir",
        "forge_headline": "Forge para Core Utils Desktop",
        "forge_subtitle": "Lee comentarios, issues y propuestas de las herramientas sin salir del desktop.",
        "forge_all_tools": "Todas las herramientas",
        "forge_recent": "Recientes",
        "forge_top": "Mas votados",
        "forge_commented": "Mas comentados",
        "forge_search": "Buscar en Forge",
        "forge_refresh": "Actualizar",
        "forge_no_threads": "No hay conversaciones para este filtro.",
        "forge_select_thread": "Selecciona una conversacion para ver sus comentarios.",
        "forge_comments": "Comentarios",
        "forge_comment_hint": "Escribe un comentario",
        "forge_send_comment": "Enviar comentario",
        "forge_login_required": "Inicia sesion con GitHub para comentar.",
        "forge_login_started": "Abre el navegador y autoriza Core Utils Desktop en GitHub.",
        "forge_login_ok": "Sesion iniciada como {login}.",
        "forge_login_fail": "No se pudo iniciar sesion: {error}",
        "forge_loaded": "Forge actualizado.",
        "forge_load_fail": "No se pudo cargar Forge: {error}",
        "forge_comment_ok": "Comentario enviado.",
        "forge_comment_fail": "No se pudo enviar el comentario: {error}",
        "headline": "Instala, actualiza y limpia tu stack Core Utils",
        "subtitle": "Elige una herramienta, revisa el comando y ejecutalo desde una UI local.",
        "search": "Buscar herramientas",
        "installed_metric": "Instaladas",
        "downloaded_metric": "Descargadas",
        "all": "Todos",
        "no_results": "No hay resultados",
        "try_other": "Prueba con otra seccion o busqueda.",
        "repo": "Repositorio",
        "section": "Seccion",
        "group": "Grupo",
        "local_path": "Ruta local",
        "launch": "Iniciar",
        "info": "Info",
        "dependencies": "Dependencias",
        "install_deps": "Instalar dependencias",
        "deps_title": "Dependencias de {name}",
        "python_deps": "Dependencias Python",
        "system_deps": "Dependencias del sistema",
        "missing_deps": "Faltan",
        "no_python_deps": "No se detectaron dependencias Python declaradas.",
        "no_system_deps": "No se detectaron dependencias de sistema adicionales.",
        "all_system_deps_ok": "Todas las dependencias de sistema estan disponibles.",
        "install_commands": "Comandos de instalacion",
        "log": "Log",
        "no_log": "No hay log todavia.",
        "download": "Descargar",
        "install": "Instalar",
        "update": "Actualizar",
        "uninstall": "Desinstalar",
        "output": "Salida",
        "close": "Cerrar",
        "cancel": "Cancelar",
        "settings_title": "Ajustes",
        "language": "Idioma",
        "spanish": "Espanol",
        "english": "Ingles",
        "desktop_update": "Actualizar Core Utils Desktop",
        "desktop_update_hint": "La actualizacion del hub vive aqui, no como herramienta del catalogo.",
        "shortcut_hint": "Reinstala la entrada del menu de aplicaciones y el icono de escritorio.",
        "menu_shortcut": "Icono y menu",
        "settings_saved": "Ajustes guardados.",
        "folder_opening": "Abriendo carpeta: {path}",
        "folder_open_fail": "No se pudo abrir la carpeta. Ruta: {path}",
        "shortcut_start": "$ core-utils-desktop install-shortcut",
        "shortcut_ok": "Acceso directo creado.",
        "shortcut_fail": "No se pudo crear el acceso directo.",
        "desktop_update_start": "$ core-utils-desktop update",
        "desktop_update_ok": "Desktop actualizado. Reinicia la app para aplicar cambios.",
        "desktop_update_fail": "No se pudo actualizar el desktop.",
        "uninstall_title": "Desinstalar {name}",
        "uninstall_text": "Se intentara desinstalar el paquete Python y se eliminara la descarga local gestionada por Core Utils Desktop.",
        "readme_local": "README local",
        "unknown_action": "Accion desconocida: {action}",
        "done": "Listo.",
        "review_output": "Revisa la salida anterior.",
        "status_summary": "{installed} instaladas · {downloaded} descargadas · {total} disponibles",
        "status_installed": "Instalado",
        "status_downloaded": "Descargado",
        "status_busy": "Procesando",
        "status_available": "Disponible",
    },
    "en": {
        "desktop_installer": "Desktop installer",
        "tools_count": "{count} tools",
        "add_shortcut": "Add desktop icon",
        "settings": "Settings",
        "tools": "Tools",
        "forge": "Forge",
        "github_sign_in": "Sign in with GitHub",
        "github_sign_out": "Sign out",
        "forge_headline": "Forge for Core Utils Desktop",
        "forge_subtitle": "Read comments, issues, and tool proposals without leaving the desktop app.",
        "forge_all_tools": "All tools",
        "forge_recent": "Recent",
        "forge_top": "Top voted",
        "forge_commented": "Most commented",
        "forge_search": "Search Forge",
        "forge_refresh": "Refresh",
        "forge_no_threads": "No conversations match this filter.",
        "forge_select_thread": "Select a conversation to see its comments.",
        "forge_comments": "Comments",
        "forge_comment_hint": "Write a comment",
        "forge_send_comment": "Send comment",
        "forge_login_required": "Sign in with GitHub to comment.",
        "forge_login_started": "Open the browser and authorize Core Utils Desktop on GitHub.",
        "forge_login_ok": "Signed in as {login}.",
        "forge_login_fail": "Could not sign in: {error}",
        "forge_loaded": "Forge refreshed.",
        "forge_load_fail": "Could not load Forge: {error}",
        "forge_comment_ok": "Comment sent.",
        "forge_comment_fail": "Could not send comment: {error}",
        "headline": "Install, update, and clean up your Core Utils stack",
        "subtitle": "Pick a tool, review the command, and run it from a local UI.",
        "search": "Search tools",
        "installed_metric": "Installed",
        "downloaded_metric": "Downloaded",
        "all": "All",
        "no_results": "No results",
        "try_other": "Try another section or search.",
        "repo": "Repository",
        "section": "Section",
        "group": "Group",
        "local_path": "Local path",
        "launch": "Launch",
        "info": "Info",
        "dependencies": "Dependencies",
        "install_deps": "Install dependencies",
        "deps_title": "{name} dependencies",
        "python_deps": "Python dependencies",
        "system_deps": "System dependencies",
        "missing_deps": "Missing",
        "no_python_deps": "No declared Python dependencies detected.",
        "no_system_deps": "No extra system dependencies detected.",
        "all_system_deps_ok": "All system dependencies are available.",
        "install_commands": "Install commands",
        "log": "Log",
        "no_log": "No log yet.",
        "download": "Download",
        "install": "Install",
        "update": "Update",
        "uninstall": "Uninstall",
        "output": "Output",
        "close": "Close",
        "cancel": "Cancel",
        "settings_title": "Settings",
        "language": "Language",
        "spanish": "Spanish",
        "english": "English",
        "desktop_update": "Update Core Utils Desktop",
        "desktop_update_hint": "Hub updates live here, not as a catalog tool.",
        "shortcut_hint": "Reinstall the app-menu entry and desktop icon.",
        "menu_shortcut": "Icon and menu",
        "settings_saved": "Settings saved.",
        "folder_opening": "Opening folder: {path}",
        "folder_open_fail": "Could not open folder. Path: {path}",
        "shortcut_start": "$ core-utils-desktop install-shortcut",
        "shortcut_ok": "Shortcut created.",
        "shortcut_fail": "Could not create shortcut.",
        "desktop_update_start": "$ core-utils-desktop update",
        "desktop_update_ok": "Desktop updated. Restart the app to apply code changes.",
        "desktop_update_fail": "Could not update desktop.",
        "uninstall_title": "Uninstall {name}",
        "uninstall_text": "The app will try to uninstall the Python package and remove the local clone managed by Core Utils Desktop.",
        "readme_local": "Local README",
        "unknown_action": "Unknown action: {action}",
        "done": "Done.",
        "review_output": "Review the output above.",
        "status_summary": "{installed} installed · {downloaded} downloaded · {total} available",
        "status_installed": "Installed",
        "status_downloaded": "Downloaded",
        "status_busy": "Processing",
        "status_available": "Available",
    },
}


def _status_label(status: str, locale: str) -> tuple[str, str]:
    copy = TRANSLATIONS[locale]
    if status == "installed":
        return copy["status_installed"], theme.GREEN
    if status == "downloaded":
        return copy["status_downloaded"], theme.BLUE
    if status == "busy":
        return copy["status_busy"], theme.AMBER
    return copy["status_available"], theme.MUTED


def _icon_for(name: str) -> str:
    mapping = {
        "sparkles": ft.Icons.AUTO_AWESOME_ROUNDED,
        "shield": ft.Icons.SHIELD_OUTLINED,
        "undo": ft.Icons.UNDO_ROUNDED,
        "lock": ft.Icons.LOCK_OUTLINE_ROUNDED,
        "search": ft.Icons.SEARCH_ROUNDED,
        "checkSquare": ft.Icons.CHECK_BOX_OUTLINE_BLANK_ROUNDED,
        "checksquare": ft.Icons.CHECK_BOX_OUTLINE_BLANK_ROUNDED,
        "notebook": ft.Icons.MENU_BOOK_ROUNDED,
        "timer": ft.Icons.TIMER_OUTLINED,
        "clapperboard": ft.Icons.MOVIE_CREATION_OUTLINED,
        "globe": ft.Icons.PUBLIC_ROUNDED,
        "flaskConical": ft.Icons.SCIENCE_OUTLINED,
        "flaskconical": ft.Icons.SCIENCE_OUTLINED,
        "terminal": ft.Icons.TERMINAL_ROUNDED,
        "command": ft.Icons.CODE_ROUNDED,
        "copy": ft.Icons.CONTENT_COPY_ROUNDED,
        "clock": ft.Icons.SCHEDULE_ROUNDED,
    }
    return mapping.get(name, mapping.get(name.lower(), ft.Icons.TERMINAL_ROUNDED))


class CoreUtilsDesktop:
    def __init__(self, page: ft.Page) -> None:
        self.page = page
        self.tools = load_tools()
        self.store = StateStore()
        self.installer = Installer(self.store)
        settings = self._load_settings()
        self.locale = self._settings_locale(settings)
        self.forge_token = settings.get("forge_token") if isinstance(settings.get("forge_token"), str) else None
        self.forge_user: ForgeUser | None = None
        self.forge_client = ForgeApiClient(self.forge_token)
        self.desktop_env = detect_desktop_environment()
        self.selected = self.tools[0] if self.tools else None
        self.active_view = "tools"
        self.active_section = "__all__"
        self.query = ""
        self.busy_tool_id: str | None = None
        self.forge_threads: list[dict] = []
        self.forge_comments: list[dict] = []
        self.forge_selected_thread: dict | None = None
        self.forge_query = ""
        self.forge_tool_slug: str | None = None
        self.forge_sort = "recent"
        self.forge_busy = False

        self.search = ft.TextField(
            hint_text=self._t("search"),
            prefix_icon=ft.Icons.SEARCH_ROUNDED,
            border_radius=12,
            border_color=theme.STROKE,
            focused_border_color=theme.TEXT,
            bgcolor=theme.SURFACE,
            color=theme.TEXT,
            hint_style=ft.TextStyle(color=theme.MUTED_2),
            content_padding=theme.pad(horizontal=14, vertical=12),
            on_change=self._on_search,
        )
        self.toolbar_host = ft.Container()
        self.section_tabs = ft.Row(spacing=8, wrap=True)
        self.body_host = ft.Container(expand=True)
        self.cards = ft.GridView(
            expand=True,
            runs_count=3,
            max_extent=315,
            child_aspect_ratio=1.18,
            spacing=14,
            run_spacing=14,
            padding=theme.pad_only(right=6, bottom=20),
        )
        self.detail_host = ft.Container(width=420)
        self.log = ft.ListView(expand=True, spacing=4, auto_scroll=True, padding=0)
        self.status_text = ft.Text("", size=11, color=theme.MUTED)
        self.progress = ft.ProgressBar(visible=False, color=theme.TEXT, bgcolor=theme.SURFACE_3, height=2)
        self.forge_search = ft.TextField(
            hint_text=self._t("forge_search"),
            prefix_icon=ft.Icons.SEARCH_ROUNDED,
            border_radius=12,
            border_color=theme.STROKE,
            focused_border_color=theme.TEXT,
            bgcolor=theme.SURFACE,
            color=theme.TEXT,
            hint_style=ft.TextStyle(color=theme.MUTED_2),
            content_padding=theme.pad(horizontal=14, vertical=12),
            on_change=self._on_forge_search,
        )
        self.forge_thread_list = ft.ListView(expand=True, spacing=10, padding=theme.pad_only(right=6, bottom=20))
        self.forge_detail_host = ft.Container(width=460)
        self.comment_input = ft.TextField(
            hint_text=self._t("forge_comment_hint"),
            multiline=True,
            min_lines=2,
            max_lines=4,
            border_radius=12,
            border_color=theme.STROKE,
            focused_border_color=theme.TEXT,
            bgcolor="#050507",
            color=theme.TEXT,
            hint_style=ft.TextStyle(color=theme.MUTED_2),
        )

    def _t(self, key: str, **values: object) -> str:
        text = TRANSLATIONS.get(self.locale, TRANSLATIONS["es"]).get(key, key)
        return text.format(**values) if values else text

    def _load_settings(self) -> dict:
        if not SETTINGS_PATH.exists():
            return {}
        try:
            return json.loads(SETTINGS_PATH.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {}

    def _settings_locale(self, data: dict) -> str:
        locale = data.get("locale")
        return locale if locale in TRANSLATIONS else "es"

    def _load_locale(self) -> str:
        data = self._load_settings()
        locale = data.get("locale")
        if locale not in TRANSLATIONS:
            return "es"
        return locale

    def _save_locale(self, locale: str) -> None:
        if locale not in TRANSLATIONS:
            return
        try:
            APP_DIR.mkdir(parents=True, exist_ok=True)
            data = self._load_settings()
            data["locale"] = locale
            SETTINGS_PATH.write_text(json.dumps(data, indent=2), encoding="utf-8")
        except OSError:
            pass
        self.locale = locale
        self.search.hint_text = self._t("search")
        self.forge_search.hint_text = self._t("forge_search")

    def _save_forge_token(self, token: str | None) -> None:
        data = self._load_settings()
        if token:
            data["forge_token"] = token
        else:
            data.pop("forge_token", None)
        try:
            APP_DIR.mkdir(parents=True, exist_ok=True)
            SETTINGS_PATH.write_text(json.dumps(data, indent=2), encoding="utf-8")
        except OSError:
            pass
        self.forge_token = token
        self.forge_client = ForgeApiClient(token)

    def build(self) -> None:
        theme.configure(self.page)
        self.page.on_resize = lambda _: self._render()
        self.page.add(self._root())
        self._render()

    def _root(self) -> ft.Control:
        return ft.Container(
            expand=True,
            bgcolor=theme.BG,
            content=ft.Column(
                expand=True,
                spacing=0,
                controls=[
                    self._header(),
                    self.progress,
                    self.body_host,
                    self._footer(),
                ],
            ),
        )

    def _header(self) -> ft.Control:
        return ft.Container(
            padding=theme.pad(horizontal=28, vertical=18),
            border=theme.border_only(bottom=ft.BorderSide(1, theme.STROKE_SOFT)),
            gradient=ft.LinearGradient(
                begin=ft.Alignment(-1, -1),
                end=ft.Alignment(1, 1),
                colors=["#09090B", "#111113", "#09090B"],
            ),
            content=ft.Row(
                controls=[
                    ft.Container(
                        width=44,
                        height=44,
                        border_radius=14,
                        bgcolor=theme.TEXT,
                        content=ft.Icon(ft.Icons.TERMINAL_ROUNDED, color=theme.BG, size=22),
                        alignment=ft.Alignment(0, 0),
                    ),
                    ft.Column(
                        spacing=2,
                        controls=[
                            ft.Text("Core Utils", size=20, weight=ft.FontWeight.W_800, color=theme.TEXT),
                            ft.Text(self._t("desktop_installer"), size=12, color=theme.MUTED),
                        ],
                    ),
                    ft.Container(expand=True),
                    self._view_button("tools", self._t("tools"), ft.Icons.APPS_ROUNDED),
                    self._view_button("forge", self._t("forge"), ft.Icons.FORUM_ROUNDED),
                    theme.pill(f"{self.desktop_env.os_name} · {self.desktop_env.desktop_name}"),
                    theme.pill(self._t("tools_count", count=len(self.tools))),
                    theme.ghost_button(ft.Icons.SETTINGS_ROUNDED, self._t("settings"), self._open_settings_dialog),
                    theme.ghost_button(ft.Icons.FOLDER_OPEN_ROUNDED, self._t("local_path"), self._show_paths),
                ],
            ),
        )

    def _view_button(self, view: str, label: str, icon: str) -> ft.Control:
        active = self.active_view == view
        return ft.FilledButton(
            label,
            icon=icon,
            height=36,
            style=ft.ButtonStyle(
                bgcolor=theme.TEXT if active else theme.SURFACE,
                color=theme.BG if active else theme.MUTED,
                shape=ft.RoundedRectangleBorder(radius=10),
                side=ft.BorderSide(1, theme.STROKE),
                padding=theme.pad(horizontal=12, vertical=0),
            ),
            on_click=lambda _e: self._set_view(view),
        )

    def _toolbar(self) -> ft.Control:
        installed = sum(1 for tool in self.tools if self.store.get(tool).status == "installed")
        downloaded = sum(1 for tool in self.tools if self.store.get(tool).status == "downloaded")
        width = self._page_width()
        compact = width < 1180
        narrow = width < 1040
        detail_width = int(self.detail_host.width or 360)
        left_width = max(520, width - detail_width - 90)
        search_width = min(360, max(260, left_width - 240))
        self.search.width = search_width

        headline = ft.Column(
            spacing=4,
            controls=[
                ft.Text(
                    self._t("headline"),
                    size=22 if compact else 24,
                    weight=ft.FontWeight.W_800,
                    color=theme.TEXT,
                    max_lines=2 if compact else 1,
                    overflow=ft.TextOverflow.ELLIPSIS,
                ),
                ft.Text(
                    self._t("subtitle"),
                    size=12 if compact else 13,
                    color=theme.MUTED,
                ),
            ],
        )

        search_and_metrics = ft.Row(
            spacing=12,
            wrap=True,
            controls=[
                ft.Container(width=search_width, content=self.search),
                self._metric(self._t("installed_metric"), str(installed), theme.GREEN),
                self._metric(self._t("downloaded_metric"), str(downloaded), theme.BLUE),
            ],
        )

        if compact:
            return ft.Column(
                spacing=14,
                controls=[
                    headline,
                    search_and_metrics,
                ],
            )

        return ft.Row(
            spacing=14,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
            controls=[
                ft.Container(
                    expand=True,
                    content=headline,
                ),
                search_and_metrics if narrow else ft.Container(width=580, content=search_and_metrics),
            ],
        )

    def _metric(self, label: str, value: str, color: str) -> ft.Control:
        return ft.Container(
            width=104,
            padding=12,
            border_radius=14,
            bgcolor=theme.SURFACE,
            border=theme.border_all(1, theme.STROKE),
            content=ft.Column(
                spacing=2,
                controls=[
                    ft.Text(label.upper(), size=9, color=theme.MUTED_2, weight=ft.FontWeight.W_700),
                    ft.Text(value, size=20, color=color, weight=ft.FontWeight.W_800),
                ],
            ),
        )

    def _footer(self) -> ft.Control:
        return ft.Container(
            padding=theme.pad(horizontal=28, vertical=12),
            border=theme.border_only(top=ft.BorderSide(1, theme.STROKE_SOFT)),
            bgcolor="#0A0A0C",
            content=ft.Row(
                controls=[
                    self.status_text,
                    ft.Container(expand=True),
                    ft.Text(str(APP_DIR), size=11, color=theme.MUTED_2),
                ],
            ),
        )

    def _render(self) -> None:
        if self.active_view == "forge":
            self._render_forge()
        else:
            self._render_layout_shell()
            self.toolbar_host.content = self._toolbar()
            self._render_tabs()
            self._render_cards()
            self._render_detail()
            self.body_host.content = self._tools_body()
        self.status_text.value = self._status_summary()
        self.page.update()

    def _tools_body(self) -> ft.Control:
        return ft.Row(
            expand=True,
            spacing=0,
            controls=[
                ft.Container(
                    expand=True,
                    padding=theme.pad_only(left=28, top=22, right=20, bottom=18),
                    content=ft.Column(
                        expand=True,
                        spacing=18,
                        controls=[
                            self.toolbar_host,
                            self.section_tabs,
                            self.cards,
                        ],
                    ),
                ),
                ft.Container(width=1, bgcolor=theme.STROKE_SOFT),
                self.detail_host,
            ],
        )

    def _set_view(self, view: str) -> None:
        self.active_view = view
        if view == "forge" and not self.forge_threads and not self.forge_busy:
            self._load_forge()
        self._render()

    def _render_forge(self) -> None:
        width = self._page_width()
        self.forge_detail_host.width = 400 if width < 1160 else 480
        self.forge_thread_list.controls = [self._forge_thread_card(thread) for thread in self.forge_threads]
        if not self.forge_thread_list.controls:
            self.forge_thread_list.controls = [
                theme.panel(
                    ft.Column(
                        alignment=ft.MainAxisAlignment.CENTER,
                        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                        controls=[
                            ft.Icon(ft.Icons.FORUM_OUTLINED, color=theme.MUTED, size=32),
                            ft.Text(self._t("forge_no_threads"), color=theme.TEXT, weight=ft.FontWeight.W_700),
                        ],
                    ),
                    expand=True,
                )
            ]
        self._render_forge_detail()
        self.body_host.content = ft.Row(
            expand=True,
            spacing=0,
            controls=[
                ft.Container(
                    expand=True,
                    padding=theme.pad_only(left=28, top=22, right=20, bottom=18),
                    content=ft.Column(
                        expand=True,
                        spacing=18,
                        controls=[
                            self._forge_toolbar(),
                            self.forge_thread_list,
                        ],
                    ),
                ),
                ft.Container(width=1, bgcolor=theme.STROKE_SOFT),
                self.forge_detail_host,
            ],
        )

    def _forge_toolbar(self) -> ft.Control:
        tool_options = [ft.dropdown.Option("", self._t("forge_all_tools"))]
        tool_options.extend(ft.dropdown.Option(tool.id, tool.name) for tool in self.tools)
        sort_options = [
            ft.dropdown.Option("recent", self._t("forge_recent")),
            ft.dropdown.Option("top", self._t("forge_top")),
            ft.dropdown.Option("most_commented", self._t("forge_commented")),
        ]
        return ft.Column(
            spacing=14,
            controls=[
                ft.Row(
                    wrap=True,
                    spacing=12,
                    run_spacing=10,
                    controls=[
                        ft.Column(
                            expand=True,
                            spacing=4,
                            controls=[
                                ft.Text(self._t("forge_headline"), size=24, weight=ft.FontWeight.W_800, color=theme.TEXT),
                                ft.Text(self._t("forge_subtitle"), size=13, color=theme.MUTED),
                            ],
                        ),
                        self._forge_auth_control(),
                        ft.OutlinedButton(
                            self._t("forge_refresh"),
                            icon=ft.Icons.REFRESH_ROUNDED,
                            disabled=self.forge_busy,
                            style=ft.ButtonStyle(color=theme.TEXT, side=ft.BorderSide(1, theme.STROKE), shape=ft.RoundedRectangleBorder(radius=10)),
                            on_click=lambda _e: self._load_forge(),
                        ),
                    ],
                ),
                ft.Row(
                    wrap=True,
                    spacing=12,
                    run_spacing=10,
                    controls=[
                        ft.Container(width=320, content=self.forge_search),
                        ft.Dropdown(
                            width=220,
                            value=self.forge_tool_slug or "",
                            options=tool_options,
                            bgcolor=theme.SURFACE,
                            border_color=theme.STROKE,
                            color=theme.TEXT,
                            on_change=self._on_forge_tool_change,
                        ),
                        ft.Dropdown(
                            width=180,
                            value=self.forge_sort,
                            options=sort_options,
                            bgcolor=theme.SURFACE,
                            border_color=theme.STROKE,
                            color=theme.TEXT,
                            on_change=self._on_forge_sort_change,
                        ),
                    ],
                ),
            ],
        )

    def _forge_auth_control(self) -> ft.Control:
        if self.forge_user:
            return ft.Container(
                padding=theme.pad(horizontal=12, vertical=8),
                border_radius=12,
                bgcolor=theme.SURFACE,
                border=theme.border_all(1, theme.STROKE),
                content=ft.Row(
                    tight=True,
                    spacing=10,
                    controls=[
                        ft.Text(self.forge_user.display_name or self.forge_user.github_login, size=12, color=theme.TEXT, weight=ft.FontWeight.W_700),
                        ft.IconButton(
                            icon=ft.Icons.LOGOUT_ROUNDED,
                            icon_color=theme.MUTED,
                            tooltip=self._t("github_sign_out"),
                            on_click=self._forge_logout,
                        ),
                    ],
                ),
            )
        return ft.FilledButton(
            self._t("github_sign_in"),
            icon=ft.Icons.LOGIN_ROUNDED,
            disabled=self.forge_busy,
            style=ft.ButtonStyle(bgcolor=theme.TEXT, color=theme.BG, shape=ft.RoundedRectangleBorder(radius=10)),
            on_click=self._forge_login,
        )

    def _forge_thread_card(self, thread: dict) -> ft.Control:
        selected = self.forge_selected_thread and self.forge_selected_thread.get("id") == thread.get("id")
        author = thread.get("author") or {}
        tool_slug = thread.get("tool_slug") or "general"
        return ft.Container(
            border_radius=16,
            bgcolor=theme.SURFACE_2 if selected else theme.SURFACE,
            border=theme.border_all(1, theme.TEXT if selected else theme.STROKE),
            padding=16,
            on_click=lambda _e, value=thread: self._select_forge_thread(value),
            content=ft.Column(
                tight=True,
                spacing=10,
                controls=[
                    ft.Row(
                        controls=[
                            theme.pill(str(thread.get("type", "discussion")).replace("_", " "), theme.BLUE, compact=True),
                            theme.pill(str(thread.get("status", "open")).replace("_", " "), theme.GREEN if thread.get("status") == "open" else theme.MUTED, compact=True),
                            ft.Container(expand=True),
                            ft.Text(f"▲ {thread.get('votes_count', 0)}", size=11, color=theme.MUTED),
                            ft.Text(f"C {thread.get('comments_count', 0)}", size=11, color=theme.MUTED),
                        ],
                    ),
                    ft.Text(str(thread.get("title", "")), size=15, color=theme.TEXT, weight=ft.FontWeight.W_700, max_lines=2, overflow=ft.TextOverflow.ELLIPSIS),
                    ft.Text(str(thread.get("body", "")), size=12, color=theme.MUTED, max_lines=2, overflow=ft.TextOverflow.ELLIPSIS),
                    ft.Row(
                        controls=[
                            ft.Text(f"@{author.get('github_login', 'unknown')}", size=11, color=theme.MUTED_2),
                            ft.Container(expand=True),
                            theme.pill(tool_slug, compact=True),
                        ],
                    ),
                ],
            ),
        )

    def _render_forge_detail(self) -> None:
        if not self.forge_selected_thread:
            self.forge_detail_host.content = ft.Container(
                expand=True,
                padding=22,
                bgcolor=theme.BG,
                content=theme.panel(
                    ft.Column(
                        alignment=ft.MainAxisAlignment.CENTER,
                        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                        controls=[
                            ft.Icon(ft.Icons.CHAT_BUBBLE_OUTLINE_ROUNDED, color=theme.MUTED, size=34),
                            ft.Text(self._t("forge_select_thread"), color=theme.MUTED, text_align=ft.TextAlign.CENTER),
                        ],
                    ),
                    expand=True,
                ),
            )
            return

        thread = self.forge_selected_thread
        author = thread.get("author") or {}
        comments = self.forge_comments
        comment_controls: list[ft.Control] = []
        for comment in comments:
            if comment.get("is_deleted"):
                body = "[deleted]"
                name = "deleted"
            else:
                c_author = comment.get("author") or {}
                body = str(comment.get("body") or "")
                name = c_author.get("display_name") or c_author.get("github_login") or "unknown"
            comment_controls.append(
                ft.Container(
                    padding=12,
                    border_radius=12,
                    bgcolor=theme.SURFACE,
                    border=theme.border_all(1, theme.STROKE),
                    content=ft.Column(
                        tight=True,
                        spacing=6,
                        controls=[
                            ft.Text(str(name), size=12, color=theme.TEXT, weight=ft.FontWeight.W_700),
                            ft.Text(body, size=12, color=theme.MUTED, selectable=True),
                        ],
                    ),
                )
            )

        composer = (
            ft.Column(
                spacing=8,
                controls=[
                    self.comment_input,
                    ft.FilledButton(
                        self._t("forge_send_comment"),
                        icon=ft.Icons.SEND_ROUNDED,
                        disabled=self.forge_busy,
                        style=ft.ButtonStyle(bgcolor=theme.TEXT, color=theme.BG, shape=ft.RoundedRectangleBorder(radius=10)),
                        on_click=lambda _e: self._send_forge_comment(),
                    ),
                ],
            )
            if self.forge_user
            else ft.Container(
                padding=12,
                border_radius=12,
                bgcolor=theme.SURFACE,
                border=theme.border_all(1, theme.STROKE),
                content=ft.Text(self._t("forge_login_required"), color=theme.MUTED, size=12),
            )
        )

        self.forge_detail_host.content = ft.Container(
            expand=True,
            padding=22,
            bgcolor=theme.BG,
            content=ft.Column(
                expand=True,
                spacing=14,
                controls=[
                    ft.Column(
                        spacing=8,
                        controls=[
                            ft.Text(str(thread.get("title", "")), size=22, color=theme.TEXT, weight=ft.FontWeight.W_800),
                            ft.Text(f"@{author.get('github_login', 'unknown')} · {thread.get('tool_slug') or 'general'}", size=12, color=theme.MUTED_2),
                            ft.Text(str(thread.get("body", "")), size=13, color=theme.MUTED, selectable=True),
                        ],
                    ),
                    ft.Text(self._t("forge_comments"), size=12, color=theme.MUTED_2, weight=ft.FontWeight.W_700),
                    ft.Container(
                        expand=True,
                        content=ft.ListView(expand=True, spacing=10, controls=comment_controls),
                    ),
                    composer,
                ],
            ),
        )

    def _load_forge(self) -> None:
        if self.forge_busy:
            return
        self.forge_busy = True
        self.progress.visible = True
        self.progress.value = None
        self._render()

        def worker() -> None:
            try:
                if self.forge_token and not self.forge_user:
                    try:
                        self.forge_user = self.forge_client.me()
                    except ForgeApiError:
                        self._save_forge_token(None)
                        self.forge_user = None
                data = self.forge_client.list_threads(
                    tool_slug=self.forge_tool_slug,
                    q=self.forge_query.strip() or None,
                    sort=self.forge_sort,
                )
                self.forge_threads = list(data.get("items", []))
                if self.forge_selected_thread and not any(t.get("id") == self.forge_selected_thread.get("id") for t in self.forge_threads):
                    self.forge_selected_thread = None
                    self.forge_comments = []
                self._finish_forge_load(None)
            except Exception as exc:
                self._finish_forge_load(str(exc))

        threading.Thread(target=worker, daemon=True).start()

    def _finish_forge_load(self, error: str | None) -> None:
        self.forge_busy = False
        self.progress.visible = False
        self.progress.value = 0
        if error:
            self._append_log(self._t("forge_load_fail", error=error), accent=theme.RED)
        else:
            self._append_log(self._t("forge_loaded"), accent=theme.GREEN)
        self._render()

    def _select_forge_thread(self, thread: dict) -> None:
        self.forge_selected_thread = thread
        self.forge_comments = []
        self._render()

        def worker() -> None:
            try:
                data = self.forge_client.list_comments(int(thread["id"]))
                self.forge_comments = list(data.get("items", []))
                self._render()
            except Exception as exc:
                self._append_log(self._t("forge_load_fail", error=str(exc)), accent=theme.RED)

        threading.Thread(target=worker, daemon=True).start()

    def _on_forge_search(self, event: ft.ControlEvent) -> None:
        self.forge_query = event.control.value or ""
        self._load_forge()

    def _on_forge_tool_change(self, event: ft.ControlEvent) -> None:
        value = event.control.value or ""
        self.forge_tool_slug = value or None
        self._load_forge()

    def _on_forge_sort_change(self, event: ft.ControlEvent) -> None:
        self.forge_sort = event.control.value or "recent"
        self._load_forge()

    def _forge_login(self, _event: ft.ControlEvent) -> None:
        if self.forge_busy:
            return
        self.forge_busy = True
        self._append_log(self._t("forge_login_started"), accent=theme.BLUE)
        self._render()

        def on_result(token: str | None, error: str | None) -> None:
            if error or not token:
                self.forge_busy = False
                self._append_log(self._t("forge_login_fail", error=error or "No token"), accent=theme.RED)
                self._render()
                return
            self._save_forge_token(token)
            try:
                self.forge_user = self.forge_client.me()
                self._append_log(self._t("forge_login_ok", login=self.forge_user.github_login), accent=theme.GREEN)
            except Exception as exc:
                self._append_log(self._t("forge_login_fail", error=str(exc)), accent=theme.RED)
            self.forge_busy = False
            self._load_forge()

        threading.Thread(target=lambda: run_desktop_login(on_result), daemon=True).start()

    def _forge_logout(self, _event: ft.ControlEvent) -> None:
        self._save_forge_token(None)
        self.forge_user = None
        self._render()

    def _send_forge_comment(self) -> None:
        if not self.forge_selected_thread or not self.forge_user:
            return
        body = (self.comment_input.value or "").strip()
        if len(body) < 2:
            return
        self.forge_busy = True
        self._render()

        def worker() -> None:
            try:
                self.forge_client.create_comment(int(self.forge_selected_thread["id"]), body)
                self.comment_input.value = ""
                data = self.forge_client.list_comments(int(self.forge_selected_thread["id"]))
                self.forge_comments = list(data.get("items", []))
                self._append_log(self._t("forge_comment_ok"), accent=theme.GREEN)
            except Exception as exc:
                self._append_log(self._t("forge_comment_fail", error=str(exc)), accent=theme.RED)
            self.forge_busy = False
            self._render()

        threading.Thread(target=worker, daemon=True).start()

    def _render_layout_shell(self) -> None:
        width = self._page_width()
        if width < 1060:
            self.detail_host.width = 340
            self.cards.max_extent = 285
            self.cards.child_aspect_ratio = 1.08
            return
        if width < 1220:
            self.detail_host.width = 360
            self.cards.max_extent = 295
            self.cards.child_aspect_ratio = 1.12
            return
        self.detail_host.width = 420
        self.cards.max_extent = 315
        self.cards.child_aspect_ratio = 1.18

    def _render_tabs(self) -> None:
        sections = [("__all__", self._t("all"))] + [(section, section) for section in sorted({tool.section for tool in self.tools})]
        self.section_tabs.controls = [
            ft.FilledButton(
                content=label,
                height=34,
                style=ft.ButtonStyle(
                    bgcolor=theme.TEXT if section_id == self.active_section else theme.SURFACE,
                    color=theme.BG if section_id == self.active_section else theme.MUTED,
                    shape=ft.RoundedRectangleBorder(radius=10),
                    side=ft.BorderSide(1, theme.STROKE),
                    padding=theme.pad(horizontal=14, vertical=0),
                ),
                on_click=lambda _e, value=section_id: self._set_section(value),
            )
            for section_id, label in sections
        ]

    def _render_cards(self) -> None:
        self.cards.controls = [self._card(tool) for tool in self._filtered_tools()]
        if not self.cards.controls:
            self.cards.controls = [
                theme.panel(
                    ft.Column(
                        alignment=ft.MainAxisAlignment.CENTER,
                        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                        controls=[
                            ft.Icon(ft.Icons.SEARCH_OFF_ROUNDED, color=theme.MUTED, size=32),
                            ft.Text(self._t("no_results"), color=theme.TEXT, weight=ft.FontWeight.W_700),
                            ft.Text(self._t("try_other"), color=theme.MUTED, size=12),
                        ],
                    ),
                    expand=True,
                )
            ]

    def _card(self, tool: Tool) -> ft.Control:
        state = self.store.get(tool)
        if self.busy_tool_id == tool.id:
            state.status = "busy"
        label, status_color = _status_label(state.status, self.locale)
        icon_bg, icon_color = theme.icon_pair(tool.icon)
        selected = self.selected and self.selected.id == tool.id

        return ft.Container(
            border_radius=18,
            bgcolor=theme.SURFACE_2 if selected else theme.SURFACE,
            border=theme.border_all(1, theme.TEXT if selected else theme.STROKE),
            padding=18,
            on_click=lambda _e, value=tool: self._select(value),
            content=ft.Column(
                spacing=12,
                controls=[
                    ft.Row(
                        controls=[
                            ft.Container(
                                width=42,
                                height=42,
                                border_radius=13,
                                bgcolor=icon_bg,
                                alignment=ft.Alignment(0, 0),
                                content=ft.Icon(_icon_for(tool.icon), color=icon_color, size=21),
                            ),
                            ft.Container(expand=True),
                            theme.pill(label, status_color, compact=True),
                        ],
                    ),
                    ft.Column(
                        spacing=5,
                        controls=[
                            ft.Text(tool.name, size=16, color=theme.TEXT, weight=ft.FontWeight.W_700, max_lines=1, overflow=ft.TextOverflow.ELLIPSIS),
                            ft.Text(tool.tagline, size=12, color=theme.MUTED, max_lines=2, overflow=ft.TextOverflow.ELLIPSIS),
                        ],
                    ),
                    ft.Row(wrap=True, spacing=6, run_spacing=6, controls=[theme.pill(target, compact=True) for target in tool.targets[:3]]),
                    ft.Container(expand=True),
                    ft.Row(
                        controls=[
                            ft.Text(tool.group, size=11, color=theme.MUTED_2),
                            ft.Container(expand=True),
                            ft.Icon(ft.Icons.ARROW_FORWARD_ROUNDED, size=17, color=theme.MUTED),
                        ],
                    ),
                ],
            ),
        )

    def _render_detail(self) -> None:
        if not self.selected:
            self.detail_host.content = ft.Container()
            return

        tool = self.selected
        state = self.store.get(tool)
        if self.busy_tool_id == tool.id:
            state.status = "busy"
        label, status_color = _status_label(state.status, self.locale)
        icon_bg, icon_color = theme.icon_pair(tool.icon)
        busy = self.busy_tool_id is not None
        is_desktop_app = tool.category == "Desktop" or "Desktop" in tool.targets
        action_controls: list[ft.Control] = []
        if is_desktop_app:
            action_controls.append(
                ft.FilledButton(
                    self._t("launch"),
                    icon=ft.Icons.ROCKET_LAUNCH_ROUNDED,
                    disabled=busy,
                    style=ft.ButtonStyle(bgcolor=theme.SURFACE_3, color=theme.TEXT, shape=ft.RoundedRectangleBorder(radius=10)),
                    on_click=lambda _e: self._run_action("launch", tool),
                )
            )
        action_controls.extend(
            [
                ft.OutlinedButton(
                    self._t("info"),
                    icon=ft.Icons.INFO_OUTLINE_ROUNDED,
                    disabled=busy,
                    style=ft.ButtonStyle(color=theme.MUTED, side=ft.BorderSide(1, theme.STROKE), shape=ft.RoundedRectangleBorder(radius=10)),
                    on_click=lambda _e: self._open_info_dialog(tool),
                ),
                ft.OutlinedButton(
                    self._t("dependencies"),
                    icon=ft.Icons.INVENTORY_2_OUTLINED,
                    disabled=busy,
                    style=ft.ButtonStyle(color=theme.MUTED, side=ft.BorderSide(1, theme.STROKE), shape=ft.RoundedRectangleBorder(radius=10)),
                    on_click=lambda _e: self._open_dependencies_dialog(tool),
                ),
                ft.OutlinedButton(
                    self._t("log"),
                    icon=ft.Icons.DESCRIPTION_OUTLINED,
                    disabled=busy,
                    style=ft.ButtonStyle(color=theme.MUTED, side=ft.BorderSide(1, theme.STROKE), shape=ft.RoundedRectangleBorder(radius=10)),
                    on_click=lambda _e: self._open_log_dialog(tool),
                ),
                ft.FilledButton(
                    self._t("download"),
                    icon=ft.Icons.DOWNLOAD_ROUNDED,
                    disabled=busy,
                    style=ft.ButtonStyle(bgcolor=theme.SURFACE_3, color=theme.TEXT, shape=ft.RoundedRectangleBorder(radius=10)),
                    on_click=lambda _e: self._run_action("download", tool),
                ),
                ft.FilledButton(
                    self._t("install"),
                    icon=ft.Icons.PLAY_ARROW_ROUNDED,
                    disabled=busy,
                    style=ft.ButtonStyle(bgcolor=theme.TEXT, color=theme.BG, shape=ft.RoundedRectangleBorder(radius=10)),
                    on_click=lambda _e: self._run_action("install", tool),
                ),
                ft.OutlinedButton(
                    self._t("update"),
                    icon=ft.Icons.UPDATE_ROUNDED,
                    disabled=busy,
                    style=ft.ButtonStyle(color=theme.BLUE, side=ft.BorderSide(1, f"{theme.BLUE}66"), shape=ft.RoundedRectangleBorder(radius=10)),
                    on_click=lambda _e: self._run_action("update", tool),
                ),
                ft.OutlinedButton(
                    self._t("uninstall"),
                    icon=ft.Icons.DELETE_OUTLINE_ROUNDED,
                    disabled=busy,
                    style=ft.ButtonStyle(color=theme.RED, side=ft.BorderSide(1, f"{theme.RED}66"), shape=ft.RoundedRectangleBorder(radius=10)),
                    on_click=lambda _e: self._confirm_uninstall(tool),
                ),
            ]
        )

        self.detail_host.content = ft.Container(
            expand=True,
            padding=22,
            bgcolor=theme.BG,
            content=ft.Column(
                expand=True,
                spacing=18,
                controls=[
                    ft.Row(
                        controls=[
                            ft.Container(
                                width=52,
                                height=52,
                                border_radius=16,
                                bgcolor=icon_bg,
                                alignment=ft.Alignment(0, 0),
                                content=ft.Icon(_icon_for(tool.icon), color=icon_color, size=26),
                            ),
                            ft.Container(expand=True),
                            theme.pill(label, status_color),
                        ],
                    ),
                    ft.Column(
                        spacing=6,
                        controls=[
                            ft.Text(tool.name, size=24, color=theme.TEXT, weight=ft.FontWeight.W_800),
                            ft.Text(tool.tagline, size=13, color=theme.MUTED),
                        ],
                    ),
                    ft.Row(wrap=True, spacing=7, run_spacing=7, controls=[theme.pill(target) for target in tool.targets]),
                    theme.panel(
                        ft.Column(
                            spacing=10,
                            controls=[
                                self._detail_row(self._t("repo"), tool.repo),
                                self._detail_row(self._t("section"), tool.section),
                                self._detail_row(self._t("group"), tool.group),
                                self._detail_row(self._t("local_path"), str(self.store.local_path(tool))),
                            ],
                        ),
                        padding=14,
                    ),
                    ft.Container(
                        padding=14,
                        border_radius=14,
                        bgcolor="#050507",
                        border=theme.border_all(1, theme.STROKE),
                        content=ft.Text(tool.install_cmd, size=11, color=theme.MUTED, font_family="Monospace", selectable=True),
                    ),
                    ft.Row(
                        spacing=10,
                        run_spacing=10,
                        wrap=True,
                        controls=action_controls,
                    ),
                    ft.Text(self._t("output"), size=12, color=theme.MUTED_2, weight=ft.FontWeight.W_700),
                    ft.Container(
                        expand=True,
                        padding=12,
                        border_radius=14,
                        bgcolor="#050507",
                        border=theme.border_all(1, theme.STROKE),
                        content=self.log,
                    ),
                ],
            ),
        )

    def _detail_row(self, label: str, value: str) -> ft.Control:
        return ft.Row(
            controls=[
                ft.Text(label, width=86, size=11, color=theme.MUTED_2, weight=ft.FontWeight.W_700),
                ft.Text(value, expand=True, size=11, color=theme.MUTED, selectable=True),
            ],
        )

    def _filtered_tools(self) -> list[Tool]:
        query = self.query.lower().strip()
        tools = self.tools
        if self.active_section != "__all__":
            tools = [tool for tool in tools if tool.section == self.active_section]
        if query:
            tools = [
                tool
                for tool in tools
                if query in tool.name.lower()
                or query in tool.id.lower()
                or query in tool.tagline.lower()
                or any(query in target.lower() for target in tool.targets)
            ]
        return tools

    def _set_section(self, section: str) -> None:
        self.active_section = section
        filtered = self._filtered_tools()
        if filtered:
            self.selected = filtered[0]
        self._render()

    def _select(self, tool: Tool) -> None:
        self.selected = tool
        self._render()

    def _on_search(self, event: ft.ControlEvent) -> None:
        self.query = event.control.value or ""
        filtered = self._filtered_tools()
        if filtered and (not self.selected or self.selected not in filtered):
            self.selected = filtered[0]
        self._render()

    def _run_action(self, action: str, tool: Tool) -> None:
        if self.busy_tool_id:
            return
        self.busy_tool_id = tool.id
        self.log.controls.clear()
        self._append_log(f"$ core-utils {action} {tool.id}", accent=theme.TEXT)
        self.progress.visible = True
        self.progress.value = None
        self._render()

        def worker() -> None:
            if action == "download":
                ok = self.installer.download(tool, self._append_log_threadsafe)
            elif action == "install":
                ok = self.installer.install(tool, self._append_log_threadsafe)
            elif action == "update":
                ok = self.installer.update(tool, self._append_log_threadsafe)
            elif action == "launch":
                ok = self.installer.launch(tool, self._append_log_threadsafe)
            elif action == "dependencies":
                ok = self.installer.ensure_system_dependencies(tool, self._append_log_threadsafe)
            elif action == "uninstall":
                ok = self.installer.uninstall(tool, self._append_log_threadsafe)
            else:
                self._append_log_threadsafe(self._t("unknown_action", action=action))
                ok = False
            self._finish_action(tool, ok)

        threading.Thread(target=worker, daemon=True).start()

    def _open_dependencies_dialog(self, tool: Tool) -> None:
        report = self.installer.dependency_report(tool)
        content = self._format_dependency_report(report)
        dialog = ft.AlertDialog(
            modal=True,
            bgcolor=theme.SURFACE,
            title=ft.Row(
                controls=[
                    ft.Icon(ft.Icons.INVENTORY_2_OUTLINED, color=theme.TEXT, size=20),
                    ft.Text(self._t("deps_title", name=tool.name), color=theme.TEXT, weight=ft.FontWeight.W_700),
                ]
            ),
            content=ft.Container(
                width=760,
                height=520,
                bgcolor="#050507",
                border=theme.border_all(1, theme.STROKE),
                border_radius=14,
                padding=16,
                content=ft.Column(
                    expand=True,
                    scroll=ft.ScrollMode.AUTO,
                    controls=[
                        ft.Text(content, color=theme.MUTED, font_family="Monospace", size=11, selectable=True),
                    ],
                ),
            ),
            actions=[
                ft.TextButton(self._t("close"), on_click=lambda _e: self._close_dialog(dialog)),
                ft.FilledButton(
                    self._t("install_deps"),
                    icon=ft.Icons.DOWNLOAD_ROUNDED,
                    disabled=not bool(report.missing_system_dependencies),
                    style=ft.ButtonStyle(bgcolor=theme.TEXT, color=theme.BG, shape=ft.RoundedRectangleBorder(radius=10)),
                    on_click=lambda _e: self._close_and_install_dependencies(dialog, tool),
                ),
            ],
        )
        self._open_dialog(dialog)

    def _format_dependency_report(self, report) -> str:
        lines = [report.tool, ""]
        lines.append(f"{self._t('python_deps')}:")
        if report.python_dependencies:
            lines.extend(f"  - {dep}" for dep in report.python_dependencies)
        else:
            lines.append(f"  {self._t('no_python_deps')}")

        lines.append("")
        lines.append(f"{self._t('system_deps')}:")
        if report.system_dependencies:
            missing_keys = {dep.key for dep in report.missing_system_dependencies}
            for dep in report.system_dependencies:
                state = self._t("missing_deps") if dep.key in missing_keys else "OK"
                lines.append(f"  - [{state}] {dep.label}")
        else:
            lines.append(f"  {self._t('no_system_deps')}")

        lines.append("")
        if report.missing_system_dependencies:
            lines.append(f"{self._t('install_commands')}:")
            if report.install_commands:
                lines.extend(f"  {' '.join(command)}" for command in report.install_commands)
            else:
                lines.append("  No disponible para esta distro.")
        else:
            lines.append(self._t("all_system_deps_ok"))
        return "\n".join(lines)

    def _close_and_install_dependencies(self, dialog: ft.AlertDialog, tool: Tool) -> None:
        self._close_dialog(dialog)
        self._run_action("dependencies", tool)

    def _open_info_dialog(self, tool: Tool) -> None:
        content, path = self.installer.read_readme(tool)
        source = str(path) if path else self._t("readme_local")
        dialog = ft.AlertDialog(
            modal=True,
            bgcolor=theme.SURFACE,
            title=ft.Row(
                controls=[
                    ft.Icon(_icon_for(tool.icon), color=theme.TEXT, size=20),
                    ft.Text(tool.name, color=theme.TEXT, weight=ft.FontWeight.W_700),
                ]
            ),
            content=ft.Container(
                width=760,
                height=560,
                bgcolor="#050507",
                border=theme.border_all(1, theme.STROKE),
                border_radius=14,
                padding=16,
                content=ft.Column(
                    expand=True,
                    spacing=12,
                    controls=[
                        ft.Text(source, color=theme.MUTED_2, size=11, selectable=True),
                        ft.Container(
                            expand=True,
                            content=ft.Column(
                                expand=True,
                                scroll=ft.ScrollMode.AUTO,
                                controls=[
                                    ft.Markdown(
                                        content,
                                        selectable=True,
                                        extension_set=ft.MarkdownExtensionSet.GITHUB_FLAVORED,
                                        code_theme="atom-one-dark",
                                    )
                                ],
                            ),
                        ),
                    ],
                ),
            ),
            actions=[
                ft.TextButton(self._t("close"), on_click=lambda _e: self._close_dialog(dialog)),
            ],
        )
        self._open_dialog(dialog)

    def _open_log_dialog(self, tool: Tool) -> None:
        log_path = self.installer._log_path(tool.id)
        content = log_path.read_text(encoding="utf-8", errors="replace") if log_path.exists() else self._t("no_log")
        dialog = ft.AlertDialog(
            modal=True,
            bgcolor=theme.SURFACE,
            title=ft.Text(f"{tool.name} log", color=theme.TEXT, weight=ft.FontWeight.W_700),
            content=ft.Container(
                width=760,
                height=520,
                bgcolor="#050507",
                border=theme.border_all(1, theme.STROKE),
                border_radius=14,
                padding=16,
                content=ft.Column(
                    expand=True,
                    scroll=ft.ScrollMode.AUTO,
                    controls=[
                        ft.Text(content, color=theme.MUTED, font_family="Monospace", size=11, selectable=True),
                    ],
                ),
            ),
            actions=[ft.TextButton(self._t("close"), on_click=lambda _e: self._close_dialog(dialog))],
        )
        self._open_dialog(dialog)

    def _open_settings_dialog(self, _event: ft.ControlEvent) -> None:
        dialog = ft.AlertDialog(
            modal=True,
            bgcolor=theme.SURFACE,
            title=ft.Row(
                controls=[
                    ft.Icon(ft.Icons.SETTINGS_ROUNDED, color=theme.TEXT, size=20),
                    ft.Text(self._t("settings_title"), color=theme.TEXT, weight=ft.FontWeight.W_700),
                ]
            ),
            content=ft.Container(
                width=520,
                padding=4,
                content=ft.Column(
                    tight=True,
                    spacing=18,
                    controls=[
                        ft.Column(
                            spacing=8,
                            controls=[
                                ft.Text(self._t("language"), color=theme.MUTED_2, size=11, weight=ft.FontWeight.W_700),
                                ft.Row(
                                    spacing=10,
                                    controls=[
                                        ft.FilledButton(
                                            self._t("spanish"),
                                            icon=ft.Icons.LANGUAGE_ROUNDED,
                                            style=ft.ButtonStyle(
                                                bgcolor=theme.TEXT if self.locale == "es" else theme.SURFACE_3,
                                                color=theme.BG if self.locale == "es" else theme.TEXT,
                                                shape=ft.RoundedRectangleBorder(radius=10),
                                            ),
                                            on_click=lambda _e: self._change_language(dialog, "es"),
                                        ),
                                        ft.FilledButton(
                                            self._t("english"),
                                            icon=ft.Icons.LANGUAGE_ROUNDED,
                                            style=ft.ButtonStyle(
                                                bgcolor=theme.TEXT if self.locale == "en" else theme.SURFACE_3,
                                                color=theme.BG if self.locale == "en" else theme.TEXT,
                                                shape=ft.RoundedRectangleBorder(radius=10),
                                            ),
                                            on_click=lambda _e: self._change_language(dialog, "en"),
                                        ),
                                    ],
                                ),
                            ],
                        ),
                        theme.panel(
                            ft.Column(
                                tight=True,
                                spacing=10,
                                controls=[
                                    ft.Text(self._t("desktop_update"), color=theme.TEXT, weight=ft.FontWeight.W_700),
                                    ft.Text(self._t("desktop_update_hint"), color=theme.MUTED, size=12),
                                    ft.FilledButton(
                                        self._t("desktop_update"),
                                        icon=ft.Icons.UPDATE_ROUNDED,
                                        style=ft.ButtonStyle(bgcolor=theme.TEXT, color=theme.BG, shape=ft.RoundedRectangleBorder(radius=10)),
                                        on_click=lambda _e: self._close_and_update_desktop(dialog),
                                    ),
                                ],
                            ),
                            padding=14,
                        ),
                        theme.panel(
                            ft.Column(
                                tight=True,
                                spacing=10,
                                controls=[
                                    ft.Text(self._t("menu_shortcut"), color=theme.TEXT, weight=ft.FontWeight.W_700),
                                    ft.Text(self._t("shortcut_hint"), color=theme.MUTED, size=12),
                                    ft.OutlinedButton(
                                        self._t("add_shortcut"),
                                        icon=ft.Icons.ADD_TO_HOME_SCREEN_ROUNDED,
                                        style=ft.ButtonStyle(color=theme.TEXT, side=ft.BorderSide(1, theme.STROKE), shape=ft.RoundedRectangleBorder(radius=10)),
                                        on_click=lambda _e: self._close_and_install_shortcut(dialog),
                                    ),
                                ],
                            ),
                            padding=14,
                        ),
                    ],
                ),
            ),
            actions=[
                ft.TextButton(self._t("close"), on_click=lambda _e: self._close_dialog(dialog)),
            ],
        )
        self._open_dialog(dialog)

    def _change_language(self, dialog: ft.AlertDialog, locale: str) -> None:
        self._save_locale(locale)
        self._close_dialog(dialog)
        self._append_log(self._t("settings_saved"), accent=theme.GREEN)
        self._render()

    def _close_and_update_desktop(self, dialog: ft.AlertDialog) -> None:
        self._close_dialog(dialog)
        self._run_desktop_update(None)

    def _close_and_install_shortcut(self, dialog: ft.AlertDialog) -> None:
        self._close_dialog(dialog)
        self._run_shortcut_install(None)

    def _run_desktop_update(self, _event: ft.ControlEvent | None) -> None:
        if self.busy_tool_id:
            return
        self.busy_tool_id = "__desktop__"
        self.log.controls.clear()
        self._append_log(self._t("desktop_update_start"), accent=theme.TEXT)
        self.progress.visible = True
        self.progress.value = None
        self._render()

        def worker() -> None:
            ok = self.installer.update_desktop(self._append_log_threadsafe)
            self._finish_desktop_update(ok)

        threading.Thread(target=worker, daemon=True).start()

    def _run_shortcut_install(self, _event: ft.ControlEvent | None) -> None:
        if self.busy_tool_id:
            return
        self.busy_tool_id = "__shortcut__"
        self.log.controls.clear()
        self._append_log(self._t("shortcut_start"), accent=theme.TEXT)
        self.progress.visible = True
        self.progress.value = None
        self._render()

        def worker() -> None:
            ok = install_desktop_shortcut(self._append_log_threadsafe)
            self._finish_shortcut_install(ok)

        threading.Thread(target=worker, daemon=True).start()

    def _finish_shortcut_install(self, ok: bool) -> None:
        self.busy_tool_id = None
        self.progress.visible = False
        self.progress.value = 0
        self._append_log(
            self._t("shortcut_ok") if ok else self._t("shortcut_fail"),
            accent=theme.GREEN if ok else theme.RED,
        )
        self._render()

    def _finish_desktop_update(self, ok: bool) -> None:
        self.busy_tool_id = None
        self.progress.visible = False
        self.progress.value = 0
        self._append_log(
            self._t("desktop_update_ok") if ok else self._t("desktop_update_fail"),
            accent=theme.GREEN if ok else theme.RED,
        )
        self._render()

    def _finish_action(self, tool: Tool, ok: bool) -> None:
        self.busy_tool_id = None
        self.progress.visible = False
        self.progress.value = 0
        self._append_log(self._t("done") if ok else self._t("review_output"), accent=theme.GREEN if ok else theme.RED)
        self.selected = tool
        self._render()

    def _append_log_threadsafe(self, message: str) -> None:
        self._append_log(message)

    def _append_log(self, message: str, accent: str | None = None) -> None:
        self.log.controls.append(
            ft.Text(
                message or " ",
                size=11,
                color=accent or theme.MUTED,
                font_family="Monospace",
                selectable=True,
            )
        )
        self.status_text.value = message[-140:] if message else self.status_text.value
        self.page.update()

    def _confirm_uninstall(self, tool: Tool) -> None:
        dialog = ft.AlertDialog(
            modal=True,
            bgcolor=theme.SURFACE,
            title=ft.Text(self._t("uninstall_title", name=tool.name), color=theme.TEXT),
            content=ft.Text(
                self._t("uninstall_text"),
                color=theme.MUTED,
            ),
            actions=[
                ft.TextButton(self._t("cancel"), on_click=lambda _e: self._close_dialog(dialog)),
                ft.FilledButton(
                    self._t("uninstall"),
                    style=ft.ButtonStyle(bgcolor=theme.RED, color=theme.BG),
                    on_click=lambda _e: self._close_and_uninstall(dialog, tool),
                ),
            ],
        )
        self._open_dialog(dialog)

    def _close_and_uninstall(self, dialog: ft.AlertDialog, tool: Tool) -> None:
        self._close_dialog(dialog)
        self._run_action("uninstall", tool)

    def _close_dialog(self, dialog: ft.AlertDialog) -> None:
        pop_dialog = getattr(self.page, "pop_dialog", None)
        if callable(pop_dialog):
            try:
                pop_dialog()
                return
            except Exception:
                pass
        close = getattr(self.page, "close", None)
        if callable(close):
            try:
                close(dialog)
                return
            except Exception:
                pass
        dialog.open = False
        self.page.update()

    def _open_dialog(self, dialog: ft.AlertDialog) -> None:
        show_dialog = getattr(self.page, "show_dialog", None)
        if callable(show_dialog):
            try:
                show_dialog(dialog)
                return
            except Exception as exc:
                self._append_log(f"No se pudo abrir el dialogo: {exc}", accent=theme.RED)
        open_control = getattr(self.page, "open", None)
        if callable(open_control):
            try:
                open_control(dialog)
                return
            except Exception as exc:
                self._append_log(f"No se pudo abrir el dialogo: {exc}", accent=theme.RED)
        if dialog not in self.page.overlay:
            self.page.overlay.append(dialog)
        dialog.open = True
        self.page.update()

    def _show_paths(self, _event: ft.ControlEvent) -> None:
        TOOLS_DIR.mkdir(parents=True, exist_ok=True)
        opened = self._open_folder(TOOLS_DIR)
        message = self._t("folder_opening" if opened else "folder_open_fail", path=str(TOOLS_DIR))
        self._show_snackbar(message)
        self._append_log(message, accent=theme.GREEN if opened else theme.RED)

    def _open_folder(self, path) -> bool:
        command: list[str] | None = None
        if shutil.which("xdg-open"):
            command = ["xdg-open", str(path)]
        elif shutil.which("gio"):
            command = ["gio", "open", str(path)]
        elif shutil.which("kde-open5"):
            command = ["kde-open5", str(path)]
        elif shutil.which("dolphin"):
            command = ["dolphin", str(path)]
        elif shutil.which("nautilus"):
            command = ["nautilus", str(path)]
        elif shutil.which("thunar"):
            command = ["thunar", str(path)]

        if command is None:
            return False
        try:
            subprocess.Popen(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
        except OSError:
            return False
        return True

    def _show_snackbar(self, message: str) -> None:
        snack_bar = ft.SnackBar(
            ft.Text(message, color=theme.TEXT),
            bgcolor=theme.SURFACE_3,
        )
        open_control = getattr(self.page, "open", None)
        if callable(open_control):
            try:
                open_control(snack_bar)
                return
            except Exception:
                pass
        if snack_bar not in self.page.overlay:
            self.page.overlay.append(snack_bar)
        snack_bar.open = True
        self.page.update()

    def _status_summary(self) -> str:
        counts = Counter(self.store.get(tool).status for tool in self.tools)
        return self._t(
            "status_summary",
            installed=counts["installed"],
            downloaded=counts["downloaded"],
            total=len(self.tools),
        )

    def _page_width(self) -> int:
        return int(self.page.width or self.page.window.width or 1240)


def main() -> None:
    ft.run(lambda page: CoreUtilsDesktop(page).build())
