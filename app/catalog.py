from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[3]
REGISTRY_PATH = ROOT / "core-utils" / "src" / "data" / "registry.json"
HUB_TOOL_ID = "core-utils-desktop"


@dataclass(frozen=True)
class Tool:
    id: str
    name: str
    tagline: str
    repo: str
    category: str
    section: str
    group: str
    targets: tuple[str, ...]
    icon: str
    install_cmd: str

    @property
    def repo_name(self) -> str:
        return self.repo.split("/")[-1] if self.repo else self.id

    @property
    def repo_url(self) -> str:
        return f"https://github.com/{self.repo}.git"


def _fallback_catalog() -> list[Tool]:
    return [
        Tool(
            id="pyclit",
            name="PythonCLITools",
            tagline="Automate your Python project lifecycle: scaffold, run, test, ship.",
            repo="mdwcoder/PythonCLITools",
            category="Utility",
            section="CLI Ecosystem",
            group="Automation",
            targets=("Automation", "Python", "Scaffolding"),
            icon="sparkles",
            install_cmd="git clone https://github.com/mdwcoder/PythonCLITools.git && cd PythonCLITools && pipx install .",
        )
    ]


def load_tools() -> list[Tool]:
    if not REGISTRY_PATH.exists():
        return _fallback_catalog()

    data: dict[str, Any] = json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))
    tools: list[Tool] = []
    for section in data.get("sections", []):
        for group in section.get("categories", []):
            for item in group.get("tools", []):
                if item.get("tool_type") == "online" or not item.get("install_cmd") or not item.get("repo"):
                    continue
                if item.get("id") == HUB_TOOL_ID:
                    continue
                marketing = item.get("marketing", {})
                tools.append(
                    Tool(
                        id=str(item["id"]),
                        name=str(marketing.get("name", item["id"])),
                        tagline=str(marketing.get("tagline", "")),
                        repo=str(item.get("repo", "")),
                        category=str(item.get("category", "")),
                        section=str(section.get("title", "")),
                        group=str(group.get("name", "")),
                        targets=tuple(str(target) for target in item.get("targets", [])),
                        icon=str(marketing.get("icon", "terminal")),
                        install_cmd=str(item.get("install_cmd", "")),
                    )
                )
    return tools
