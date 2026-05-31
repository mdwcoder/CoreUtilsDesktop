from __future__ import annotations

import flet as ft


BG = "#09090B"
SURFACE = "#111113"
SURFACE_2 = "#18181B"
SURFACE_3 = "#202024"
STROKE = "#27272A"
STROKE_SOFT = "#1F1F23"
TEXT = "#FAFAFA"
MUTED = "#A1A1AA"
MUTED_2 = "#71717A"

TEAL = "#2DD4BF"
BLUE = "#60A5FA"
VIOLET = "#A78BFA"
PINK = "#F472B6"
AMBER = "#FBBF24"
ORANGE = "#FB923C"
RED = "#F87171"
GREEN = "#4ADE80"

ICON_COLORS: dict[str, tuple[str, str]] = {
    "sparkles": ("#2E2148", VIOLET),
    "shield": ("#17233F", BLUE),
    "undo": ("#123531", TEAL),
    "lock": ("#402516", ORANGE),
    "search": ("#123326", GREEN),
    "checksquare": ("#3D3210", AMBER),
    "checkSquare": ("#3D3210", AMBER),
    "notebook": ("#402036", PINK),
    "timer": ("#12343A", TEAL),
    "clapperboard": ("#421B2A", "#FB7185"),
    "globe": ("#102A43", BLUE),
    "flaskconical": ("#253814", "#A3E635"),
    "flaskConical": ("#253814", "#A3E635"),
    "terminal": ("#26262B", MUTED),
    "command": ("#211D3B", "#818CF8"),
    "copy": ("#3B2C13", AMBER),
    "clock": ("#12343A", TEAL),
}


def configure(page: ft.Page) -> None:
    page.title = "Core Utils Desktop"
    page.bgcolor = BG
    page.theme_mode = ft.ThemeMode.DARK
    page.padding = 0
    page.window.width = 1240
    page.window.height = 820
    page.window.min_width = 980
    page.window.min_height = 680
    page.window.full_screen = False
    page.window.maximizable = True
    page.window.maximized = True
    page.theme = ft.Theme(
        font_family="Sans",
        scaffold_bgcolor=BG,
        card_bgcolor=SURFACE,
        color_scheme=ft.ColorScheme(
            primary=TEXT,
            secondary=TEAL,
            surface=SURFACE,
            on_primary=BG,
            on_secondary=BG,
            on_surface=TEXT,
            outline=STROKE,
            error=RED,
        ),
    )


def icon_pair(icon_name: str) -> tuple[str, str]:
    return ICON_COLORS.get(icon_name, ICON_COLORS.get(icon_name.lower(), ("#232329", TEXT)))


def pad(horizontal: int = 0, vertical: int = 0) -> ft.Padding:
    return ft.Padding(left=horizontal, top=vertical, right=horizontal, bottom=vertical)


def pad_only(left: int = 0, top: int = 0, right: int = 0, bottom: int = 0) -> ft.Padding:
    return ft.Padding(left=left, top=top, right=right, bottom=bottom)


def border_all(width: int, color: str) -> ft.Border:
    side = ft.BorderSide(width, color)
    return ft.Border(top=side, right=side, bottom=side, left=side)


def border_only(
    *,
    top: ft.BorderSide | None = None,
    right: ft.BorderSide | None = None,
    bottom: ft.BorderSide | None = None,
    left: ft.BorderSide | None = None,
) -> ft.Border:
    empty = ft.BorderSide(0, "transparent")
    return ft.Border(top=top or empty, right=right or empty, bottom=bottom or empty, left=left or empty)


def pill(label: str, color: str | None = None, compact: bool = False) -> ft.Container:
    return ft.Container(
        padding=pad(horizontal=9 if compact else 11, vertical=4 if compact else 5),
        border_radius=999,
        bgcolor=SURFACE_2 if color is None else f"{color}22",
        border=border_all(1, STROKE if color is None else f"{color}44"),
        content=ft.Text(
            label,
            size=10 if compact else 11,
            color=MUTED if color is None else color,
            weight=ft.FontWeight.W_600,
        ),
    )


def panel(content: ft.Control, padding: int = 18, expand: bool | int = False) -> ft.Container:
    return ft.Container(
        expand=expand,
        bgcolor=SURFACE,
        border=border_all(1, STROKE),
        border_radius=18,
        padding=padding,
        content=content,
    )


def ghost_button(icon: str, tooltip: str, on_click=None) -> ft.IconButton:
    return ft.IconButton(
        icon=icon,
        tooltip=tooltip,
        icon_color=MUTED,
        selected_icon_color=TEXT,
        style=ft.ButtonStyle(
            bgcolor={ft.ControlState.HOVERED: SURFACE_2},
            shape=ft.RoundedRectangleBorder(radius=10),
        ),
        on_click=on_click,
    )
