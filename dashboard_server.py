"""
dashboard_server.py — Local HTTP server that serves the dashboard and handles
plugin toggle requests.

Usage
-----
  python3 dashboard_server.py          # serves on http://localhost:7432
  python3 dashboard_server.py --port 8080

What it does
------------
  GET  /              → serves the latest report.html (auto-regenerates)
  GET  /api/plugins   → returns installed plugins + enabled state as JSON
  POST /api/toggle    → enables/disables a plugin in .mcp.json or global config
  POST /api/reload    → regenerates the dashboard HTML
"""
import argparse
import json
import os
import platform
import threading
import webbrowser
from datetime import datetime
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import urlparse

import config_reader
import tracker
import report_generator

PORT        = 7432
REPORT_PATH = Path.home() / ".mcp-tracker" / "report.html"


# ── Config helpers ─────────────────────────────────────────────────────────────

def _desktop_config_path() -> Path:
    system = platform.system()
    if system == "Darwin":
        return Path.home() / "Library" / "Application Support" / "Claude" / "claude_desktop_config.json"
    elif system == "Windows":
        return Path(os.environ.get("APPDATA", str(Path.home()))) / "Claude" / "claude_desktop_config.json"
    else:
        return Path.home() / ".config" / "Claude" / "claude_desktop_config.json"


def _find_mcp_json(plugin_name: str) -> Path | None:
    """Find the .mcp.json file that contains this plugin."""
    cwd = Path.cwd()
    for parent in [cwd, *cwd.parents]:
        candidate = parent / ".mcp.json"
        if candidate.exists():
            try:
                cfg = json.loads(candidate.read_text())
                if plugin_name in cfg.get("mcpServers", {}):
                    return candidate
            except Exception:
                pass
        if parent == Path.home():
            break
    return None


def get_plugins_state() -> list[dict]:
    """Return all plugins with their current enabled state."""
    installed = config_reader.get_installed_plugins()
    disabled  = _load_disabled_set()
    result    = []
    for name, info in installed.items():
        result.append({
            "name":    name,
            "command": info.get("command", ""),
            "source":  info.get("source", ""),
            "enabled": name not in disabled,
        })
    return result


def _disabled_file() -> Path:
    p = Path.home() / ".mcp-tracker" / "disabled.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


def _load_disabled_set() -> set[str]:
    f = _disabled_file()
    if f.exists():
        try:
            return set(json.loads(f.read_text()))
        except Exception:
            pass
    return set()


def _save_disabled_set(disabled: set[str]) -> None:
    _disabled_file().write_text(json.dumps(sorted(disabled), indent=2))


def toggle_plugin(plugin_name: str, enable: bool) -> dict:
    """
    Toggle a plugin by editing the relevant .mcp.json or desktop config.

    Strategy:
      - We keep a ~/.mcp-tracker/disabled.json list as the source of truth.
      - We ALSO physically move the server entry in the config file to a
        '_disabled' key so Claude Code won't load it.
    Returns {"ok": True/False, "message": "..."}
    """
    disabled = _load_disabled_set()

    # Find the config file that owns this plugin
    mcp_json = _find_mcp_json(plugin_name)
    cfg_path = mcp_json if mcp_json else _desktop_config_path()

    try:
        cfg = json.loads(cfg_path.read_text(encoding="utf-8")) if cfg_path.exists() else {}
    except Exception as e:
        return {"ok": False, "message": f"Could not read config: {e}"}

    servers          = cfg.setdefault("mcpServers", {})
    disabled_servers = cfg.setdefault("_disabledMcpServers", {})

    if enable:
        # Restore from disabled bucket
        if plugin_name in disabled_servers:
            servers[plugin_name] = disabled_servers.pop(plugin_name)
        disabled.discard(plugin_name)
        action = "enabled"
    else:
        # Move to disabled bucket
        if plugin_name in servers:
            disabled_servers[plugin_name] = servers.pop(plugin_name)
        disabled.add(plugin_name)
        action = "disabled"

    # Persist config
    try:
        cfg_path.write_text(json.dumps(cfg, indent=2, ensure_ascii=False), encoding="utf-8")
    except Exception as e:
        return {"ok": False, "message": f"Could not write config: {e}"}

    _save_disabled_set(disabled)

    return {
        "ok":      True,
        "message": f"Plugin '{plugin_name}' {action}. Restart Claude Code to apply.",
        "action":  action,
    }


def regenerate_report() -> None:
    usage_data       = tracker.load_usage()
    installed        = config_reader.get_installed_plugins()
    disabled         = _load_disabled_set()
    # mark disabled state in installed dict for the report
    for name in disabled:
        if name in installed:
            installed[name]["_disabled"] = True
    report_generator.generate_dashboard(usage_data, installed, REPORT_PATH)


# ── HTTP handler ───────────────────────────────────────────────────────────────

class Handler(BaseHTTPRequestHandler):

    def log_message(self, fmt, *args):
        pass  # silence default access log

    def _send_json(self, data: dict, status: int = 200) -> None:
        body = json.dumps(data, ensure_ascii=False).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def _send_html(self, html: bytes) -> None:
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(html)))
        self.end_headers()
        self.wfile.write(html)

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_GET(self):
        path = urlparse(self.path).path

        if path == "/" or path == "/dashboard":
            regenerate_report()
            if REPORT_PATH.exists():
                self._send_html(REPORT_PATH.read_bytes())
            else:
                self._send_html(b"<h1>Dashboard not yet generated</h1>")

        elif path == "/api/plugins":
            self._send_json({"plugins": get_plugins_state()})

        else:
            self._send_json({"error": "Not found"}, 404)

    def do_POST(self):
        path = urlparse(self.path).path
        length = int(self.headers.get("Content-Length", 0))
        body   = self.rfile.read(length)

        try:
            payload = json.loads(body) if body else {}
        except Exception:
            self._send_json({"error": "Invalid JSON"}, 400)
            return

        if path == "/api/toggle":
            plugin = payload.get("plugin", "").strip()
            enable = bool(payload.get("enable", True))
            if not plugin:
                self._send_json({"error": "Missing plugin name"}, 400)
                return
            result = toggle_plugin(plugin, enable)
            self._send_json(result)

        elif path == "/api/reload":
            regenerate_report()
            self._send_json({"ok": True, "message": "Dashboard regenerated"})

        else:
            self._send_json({"error": "Not found"}, 404)


# ── Inline dashboard with toggle UI ───────────────────────────────────────────

TOGGLE_JS = """
<script>
const API = 'http://localhost:7432';

async function loadPlugins() {
  try {
    const r = await fetch(API + '/api/plugins');
    const { plugins } = await r.json();
    renderPlugins(plugins);
  } catch(e) {
    document.getElementById('toggle-panel').innerHTML =
      '<p style="color:#FF6584;font-family:monospace;padding:16px">⚠ Dashboard server not running.<br>Start it with: <code>python3 dashboard_server.py</code></p>';
  }
}

function renderPlugins(plugins) {
  const panel = document.getElementById('toggle-panel');
  panel.innerHTML = plugins.map(p => `
    <div class="toggle-row" id="row-${p.name}">
      <div class="toggle-info">
        <span class="badge">${p.name}</span>
        <span class="src">${p.source}</span>
      </div>
      <label class="switch" title="${p.enabled ? 'Click to disable' : 'Click to enable'}">
        <input type="checkbox" ${p.enabled ? 'checked' : ''}
               onchange="togglePlugin('${p.name}', this.checked)">
        <span class="slider"></span>
      </label>
    </div>
  `).join('');
}

async function togglePlugin(name, enable) {
  const row = document.getElementById('row-' + name);
  row.classList.add('toggling');
  try {
    const r = await fetch(API + '/api/toggle', {
      method: 'POST',
      headers: {'Content-Type':'application/json'},
      body: JSON.stringify({ plugin: name, enable })
    });
    const data = await r.json();
    showToast(data.ok ? '✅ ' + data.message : '❌ ' + data.message, data.ok);
    if (data.ok) {
      row.style.opacity = enable ? '1' : '0.45';
    } else {
      // revert checkbox
      const cb = row.querySelector('input[type=checkbox]');
      if (cb) cb.checked = !enable;
    }
  } catch(e) {
    showToast('❌ Could not reach dashboard server', false);
    const cb = row.querySelector('input[type=checkbox]');
    if (cb) cb.checked = !enable;
  }
  row.classList.remove('toggling');
}

function showToast(msg, ok) {
  let t = document.getElementById('toast');
  if (!t) { t = document.createElement('div'); t.id='toast'; document.body.appendChild(t); }
  t.textContent = msg;
  t.className   = 'toast ' + (ok ? 'toast-ok' : 'toast-err');
  t.style.opacity = '1';
  clearTimeout(t._hide);
  t._hide = setTimeout(() => { t.style.opacity = '0'; }, 3500);
}

loadPlugins();
</script>
"""

TOGGLE_CSS = """
.toggle-panel { background: var(--card); border: 1px solid var(--border); border-radius: var(--radius); overflow: hidden; }
.toggle-row { display: flex; align-items: center; justify-content: space-between; padding: 14px 20px; border-bottom: 1px solid #1E1E38; gap: 16px; transition: opacity .3s; }
.toggle-row:last-child { border-bottom: none; }
.toggle-row.toggling { pointer-events: none; opacity: .6; }
.toggle-info { display: flex; flex-direction: column; gap: 4px; }
.switch { position: relative; display: inline-block; width: 48px; height: 26px; flex-shrink: 0; }
.switch input { opacity: 0; width: 0; height: 0; }
.slider { position: absolute; cursor: pointer; inset: 0; background: #2A2A4A; border-radius: 26px; transition: .3s; }
.slider::before { content:''; position: absolute; height: 18px; width: 18px; left: 4px; bottom: 4px; background: #7B7BAA; border-radius: 50%; transition: .3s; }
.switch input:checked + .slider { background: rgba(108,99,255,.35); border: 1px solid var(--accent); }
.switch input:checked + .slider::before { transform: translateX(22px); background: var(--accent); box-shadow: 0 0 8px var(--accent); }
.toast { position: fixed; bottom: 28px; left: 50%; transform: translateX(-50%); padding: 12px 24px; border-radius: 10px; font-family: 'JetBrains Mono', monospace; font-size: .82rem; z-index: 9999; transition: opacity .4s; pointer-events: none; white-space: nowrap; }
.toast-ok  { background: rgba(6,214,160,.15); border: 1px solid #06D6A0; color: #06D6A0; }
.toast-err { background: rgba(255,101,132,.15); border: 1px solid #FF6584; color: #FF6584; }
"""


# ── Entry point ────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="SaveTokens4Claude dashboard server")
    parser.add_argument("--port", type=int, default=PORT)
    parser.add_argument("--no-browser", action="store_true")
    args = parser.parse_args()

    # Patch report_generator to inject toggle UI before serving
    _patch_report_generator()

    regenerate_report()

    print(f"\n⚡ SaveTokens4Claude Dashboard Server")
    print(f"   http://localhost:{args.port}")
    print(f"   Press Ctrl+C to stop\n")

    if not args.no_browser:
        threading.Timer(0.8, lambda: webbrowser.open(f"http://localhost:{args.port}")).start()

    httpd = HTTPServer(("localhost", args.port), Handler)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n\nServer stopped.")


def _patch_report_generator():
    """Inject toggle CSS + JS + panel into report_generator output."""
    original_generate = report_generator.generate_dashboard

    def patched(usage_data, installed_plugins, output_path):
        path = original_generate(usage_data, installed_plugins, output_path)
        html = path.read_text(encoding="utf-8")

        # Inject CSS before </style>
        html = html.replace("</style>", TOGGLE_CSS + "\n</style>", 1)

        # Inject toggle panel section before the first detailed table section
        toggle_section = (
            "\n<p class='sec'>Plugin Toggle — Enable / Disable</p>"
            "\n<div class='toggle-panel' id='toggle-panel'>"
            "\n  <p style='padding:20px;color:var(--muted);font-family:monospace;font-size:.82rem'>Loading plugins…</p>"
            "\n</div>\n"
        )
        # Insert before Detailed Usage section
        marker = "<p class='sec'>Detailed Usage by Plugin</p>"
        html = html.replace(marker, toggle_section + marker, 1)

        # Inject JS before </body>
        html = html.replace("</body>", TOGGLE_JS + "\n</body>", 1)

        path.write_text(html, encoding="utf-8")
        return path

    report_generator.generate_dashboard = patched


if __name__ == "__main__":
    main()
