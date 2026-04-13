"""
config_reader.py — Discovers installed MCP servers.

Sources checked (in order):
  1. Claude Desktop global config  (~/.../Claude/claude_desktop_config.json)
  2. Project-level .mcp.json files (walks up from the current working directory)
"""
import json
import os
import platform
from pathlib import Path
from typing import Any, Dict


def _desktop_config_path() -> Path:
    """Return the platform-specific path to Claude Desktop's config file."""
    system = platform.system()
    if system == "Darwin":
        return (
            Path.home()
            / "Library"
            / "Application Support"
            / "Claude"
            / "claude_desktop_config.json"
        )
    elif system == "Windows":
        appdata = os.environ.get("APPDATA", str(Path.home()))
        return Path(appdata) / "Claude" / "claude_desktop_config.json"
    else:  # Linux / WSL
        return Path.home() / ".config" / "Claude" / "claude_desktop_config.json"


def _project_config_paths() -> list[Path]:
    """
    Walk up from the current working directory looking for .mcp.json files.
    Stops at the user's home directory to avoid scanning the entire filesystem.
    """
    found: list[Path] = []
    cwd = Path.cwd()
    for parent in [cwd, *cwd.parents]:
        candidate = parent / ".mcp.json"
        if candidate.exists():
            found.append(candidate)
        if parent == Path.home():
            break
    return found


def get_installed_plugins() -> Dict[str, Any]:
    """
    Return a unified dict of every MCP server found across all config sources.

    Schema
    ------
    {
        "<plugin-name>": {
            "command": "...",
            "args":    [...],
            "env":     {...},          # optional
            "source":  "desktop" | "project:<absolute-path>"
        },
        ...
    }

    Notes
    -----
    - Desktop entries take precedence; project entries only fill gaps.
    - Malformed or unreadable config files are silently skipped.
    """
    plugins: Dict[str, Any] = {}

    # 1. Claude Desktop global config
    desktop_cfg = _desktop_config_path()
    if desktop_cfg.exists():
        try:
            with open(desktop_cfg, encoding="utf-8") as f:
                cfg = json.load(f)
            for name, server in cfg.get("mcpServers", {}).items():
                plugins[name] = {**server, "source": "desktop"}
        except (json.JSONDecodeError, OSError):
            pass

    # 2. Project-level .mcp.json files
    for proj_path in _project_config_paths():
        try:
            with open(proj_path, encoding="utf-8") as f:
                cfg = json.load(f)
            for name, server in cfg.get("mcpServers", {}).items():
                if name not in plugins:  # desktop entries win
                    plugins[name] = {
                        **server,
                        "source": f"project:{proj_path}",
                    }
        except (json.JSONDecodeError, OSError):
            pass

    return plugins
