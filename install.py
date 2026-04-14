#!/usr/bin/env python3
"""
install.py — MCP Token Tracker one-command installer

Usage
-----
  python3 install.py            # install to ~/mcp-token-tracker
  python3 install.py --dir /custom/path
  python3 install.py --uninstall

What it does
------------
  1. Clones (or updates) the repo into the target directory
  2. Creates a Python virtual environment
  3. Installs all dependencies (mcp, tiktoken, pandas, plotly)
  4. Patches claude_desktop_config.json automatically
  5. Prints next steps
"""
import argparse
import json
import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path

REPO_URL    = "https://github.com/BRUNEXX13/savetokens4claude.git"
REPO_BRANCH = "blog"
SERVER_NAME = "mcp-save-tokens-4-claude"
DEFAULT_DIR = Path.home() / "mcp-token-tracker"


# ── Helpers ────────────────────────────────────────────────────────────────────

def log(msg: str, icon: str = "→") -> None:
    print(f"\033[96m{icon}\033[0m  {msg}")

def ok(msg: str) -> None:
    print(f"\033[92m✔\033[0m  {msg}")

def err(msg: str) -> None:
    print(f"\033[91m✘\033[0m  {msg}", file=sys.stderr)

def run(cmd: list[str], cwd: Path | None = None, check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, cwd=cwd, check=check,
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)


def claude_config_path() -> Path:
    system = platform.system()
    if system == "Darwin":
        return Path.home() / "Library" / "Application Support" / "Claude" / "claude_desktop_config.json"
    elif system == "Windows":
        return Path(os.environ.get("APPDATA", str(Path.home()))) / "Claude" / "claude_desktop_config.json"
    else:
        return Path.home() / ".config" / "Claude" / "claude_desktop_config.json"


def python_bin(install_dir: Path) -> Path:
    """Return the venv Python binary path (cross-platform)."""
    if platform.system() == "Windows":
        return install_dir / ".venv" / "Scripts" / "python.exe"
    return install_dir / ".venv" / "bin" / "python3"


# ── Install ────────────────────────────────────────────────────────────────────

def install(install_dir: Path) -> None:
    print()
    print("\033[1m⚡ MCP Token Tracker — Installer\033[0m")
    print("─" * 40)

    # 1. Clone or pull
    if (install_dir / ".git").exists():
        log(f"Updating existing repo at {install_dir} …")
        run(["git", "pull", "origin", REPO_BRANCH], cwd=install_dir)
        ok("Repository updated")
    else:
        log(f"Cloning repo to {install_dir} …")
        install_dir.parent.mkdir(parents=True, exist_ok=True)
        run(["git", "clone", "--branch", REPO_BRANCH, REPO_URL, str(install_dir)])
        ok("Repository cloned")

    # 2. Create virtual environment
    venv_dir = install_dir / ".venv"
    if not venv_dir.exists():
        log("Creating virtual environment …")
        run([sys.executable, "-m", "venv", str(venv_dir)])
        ok("Virtual environment created")
    else:
        ok("Virtual environment already exists — skipping")

    # 3. Install dependencies
    py = python_bin(install_dir)
    log("Installing dependencies (mcp, tiktoken, pandas, plotly) …")
    run([str(py), "-m", "pip", "install", "--quiet", "--upgrade", "pip"])
    run([str(py), "-m", "pip", "install", "--quiet",
         "mcp>=1.0.0", "tiktoken", "pandas", "plotly"])
    ok("Dependencies installed")

    # 4. Patch claude_desktop_config.json
    cfg_path = claude_config_path()
    log(f"Patching Claude Desktop config at {cfg_path} …")

    cfg_path.parent.mkdir(parents=True, exist_ok=True)
    cfg: dict = {}
    if cfg_path.exists():
        try:
            cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            cfg = {}

    cfg.setdefault("mcpServers", {})

    if SERVER_NAME in cfg["mcpServers"]:
        log("Entry already present — updating path …", icon="↺")
    
    cfg["mcpServers"][SERVER_NAME] = {
        "command": str(py),
        "args":    [str(install_dir / "server.py")],
    }

    cfg_path.write_text(
        json.dumps(cfg, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    ok(f"Claude Desktop config updated → {SERVER_NAME} registered")

    # 5. Done
    print()
    print("─" * 40)
    print("\033[92m\033[1m✔ Installation complete!\033[0m")
    print()
    print("  Next step: \033[1mrestart Claude Desktop\033[0m")
    print()
    print("  Then ask Claude:")
    print('  \033[93m"Scan my MCP plugins and generate a token usage report"\033[0m')
    print()


# ── Uninstall ──────────────────────────────────────────────────────────────────

def uninstall(install_dir: Path) -> None:
    print()
    print("\033[1m⚡ MCP Token Tracker — Uninstaller\033[0m")
    print("─" * 40)

    # Remove from config
    cfg_path = claude_config_path()
    if cfg_path.exists():
        try:
            cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
            if SERVER_NAME in cfg.get("mcpServers", {}):
                del cfg["mcpServers"][SERVER_NAME]
                cfg_path.write_text(json.dumps(cfg, indent=2), encoding="utf-8")
                ok("Removed from Claude Desktop config")
            else:
                log("Not found in Claude Desktop config — skipping")
        except json.JSONDecodeError:
            err("Could not parse claude_desktop_config.json")
    else:
        log("Claude Desktop config not found — skipping")

    # Remove install directory
    if install_dir.exists():
        answer = input(f"\n  Delete {install_dir}? [y/N] ").strip().lower()
        if answer == "y":
            shutil.rmtree(install_dir)
            ok(f"Deleted {install_dir}")
        else:
            log("Directory kept")

    # Remove data directory
    data_dir = Path.home() / ".mcp-tracker"
    if data_dir.exists():
        answer = input(f"  Delete usage data at {data_dir}? [y/N] ").strip().lower()
        if answer == "y":
            shutil.rmtree(data_dir)
            ok(f"Deleted {data_dir}")

    print()
    ok("Uninstall complete. Restart Claude Desktop to apply.")
    print()


# ── Entry point ────────────────────────────────────────────────────────────────

def main() -> None:
    # Quick dependency check
    missing = [t for t in ("git",) if not shutil.which(t)]
    if missing:
        err(f"Missing required tools: {', '.join(missing)}")
        err("Please install them and try again.")
        sys.exit(1)

    parser = argparse.ArgumentParser(
        description="MCP Token Tracker installer",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--dir",
        type=Path,
        default=DEFAULT_DIR,
        metavar="PATH",
        help=f"Installation directory (default: {DEFAULT_DIR})",
    )
    parser.add_argument(
        "--uninstall",
        action="store_true",
        help="Remove the plugin and clean up config",
    )
    args = parser.parse_args()

    if args.uninstall:
        uninstall(args.dir)
    else:
        install(args.dir)


if __name__ == "__main__":
    main()
