# ⚡ SaveTokens4Claude

> A Model Context Protocol (MCP) server that monitors **every MCP plugin installed in Claude Desktop or Claude Code**, counts their token usage, measures execution time, estimates USD cost, and exports a beautiful **interactive HTML dashboard** powered by Plotly + Pandas.

![Python](https://img.shields.io/badge/Python-3.11%2B-blue?style=flat-square&logo=python)
![MCP](https://img.shields.io/badge/MCP-1.0%2B-purple?style=flat-square)
![License](https://img.shields.io/badge/License-MIT-green?style=flat-square)

---

## 📸 Dashboard Features

The generated report is a **self-contained HTML file** (no server needed) that opens directly in your browser with:

- **KPI cards** — total tokens, session tokens (24h), calls, estimated cost, avg duration
- **Interactive charts** — horizontal bar, input/output donut, calls pie, timeline
- **Detailed table** — per-plugin breakdown with installation date, first/last seen, session tokens, and cost
- **🔍 Search menu** — filter plugins instantly in both tables
- **Installed plugins inventory** — all discovered servers and their sources

---

## ✨ Features

| Feature | Description |
|---|---|
| 🔍 **Plugin Scanner** | Reads `claude_desktop_config.json` + project `.mcp.json` files |
| 🧮 **Token Counting** | Uses `tiktoken` (cl100k_base) — same encoding as Claude / GPT-4 |
| 💰 **Cost Estimation** | Configurable per-token pricing (input / output separately) |
| ⏱️ **Duration Tracking** | Records wall-clock time per tool call in milliseconds |
| 📅 **Install Date** | Shows when each plugin was installed (config file mtime) |
| 🕐 **First / Last Seen** | Tracks first and last usage datetime per plugin |
| 🟢 **Session Tokens** | Highlights tokens consumed in the last 24 hours |
| 📊 **HTML Dashboard** | Single-file report with Plotly charts, opens automatically |
| 🗄️ **Persistent Storage** | Usage data saved to `~/.mcp-tracker/usage.json` |
| 🧹 **Reset Tool** | Clear all data with a single command |

---

## 🗂️ Project Structure

```
savetokens4claude/
├── server.py            # MCP server — exposes 5 tools to Claude
├── tracker.py           # Token counting & JSON persistence layer
├── config_reader.py     # Discovers installed MCP servers from configs
├── report_generator.py  # Builds the interactive HTML dashboard
├── install.py           # One-command auto installer
└── requirements.txt     # Python dependencies
```

### Data directory (created automatically)

```
~/.mcp-tracker/
├── usage.json           # All recorded tool-call sessions
└── report.html          # Latest generated dashboard
```

---

## ⚡ Quick Install (one command)

### macOS / Linux / Ubuntu (Claude Code)

```bash
python3 <(curl -fsSL https://raw.githubusercontent.com/BRUNEXX13/savetokens4claude/blog/install.py)
```

### Windows (PowerShell)

```powershell
python (Invoke-WebRequest -Uri "https://raw.githubusercontent.com/BRUNEXX13/savetokens4claude/blog/install.py" -UseBasicParsing).Content
```

The installer will automatically:
1. Clone this repository to `~/savetokens4claude`
2. Create an isolated Python virtual environment
3. Install all dependencies
4. Register `mcp-save-tokens-4-claude` in your Claude config

Then **restart Claude Desktop** (or reopen Claude Code) — and you're done. 🎉

### Uninstall

```bash
python3 ~/savetokens4claude/install.py --uninstall
```

### Custom install path

```bash
python3 <(curl -fsSL https://raw.githubusercontent.com/BRUNEXX13/savetokens4claude/blog/install.py) --dir ~/tools/savetokens4claude
```

---

## 🚀 Manual Setup

> Only needed if you prefer to set things up yourself.

### Prerequisites

- **Python 3.11+**
- **Claude Desktop** or **Claude Code** (CLI)
- **git** and **pip**

### 1 — Clone the repository

```bash
git clone --branch blog https://github.com/BRUNEXX13/savetokens4claude.git ~/savetokens4claude
cd ~/savetokens4claude
```

### 2 — Create virtual environment and install dependencies

```bash
python3 -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### 3 — Register the plugin

#### Option A — Claude Desktop

Open your config file:

| OS | Path |
|---|---|
| macOS | `~/Library/Application Support/Claude/claude_desktop_config.json` |
| Windows | `%APPDATA%\Claude\claude_desktop_config.json` |
| Linux | `~/.config/Claude/claude_desktop_config.json` |

Add the entry inside `"mcpServers"`:

```json
{
  "mcpServers": {
    "mcp-save-tokens-4-claude": {
      "command": "/home/your-user/savetokens4claude/.venv/bin/python3",
      "args": ["/home/your-user/savetokens4claude/server.py"]
    }
  }
}
```

> **Windows:** use `python` and escape backslashes:
> `"C:\\Users\\you\\savetokens4claude\\.venv\\Scripts\\python.exe"`

Restart Claude Desktop — done.

#### Option B — Claude Code / Claude CLI (Linux / Ubuntu)

Create a `.mcp.json` file in your project root:

```bash
cat > /path/to/your-project/.mcp.json << EOF
{
  "mcpServers": {
    "mcp-save-tokens-4-claude": {
      "command": "/home/$USER/savetokens4claude/.venv/bin/python3",
      "args": ["/home/$USER/savetokens4claude/server.py"]
    }
  }
}
EOF
```

Then open Claude Code inside your project:

```bash
cd /path/to/your-project
claude
```

Claude Code detects `.mcp.json` automatically — no restart needed.

---

## 🛠️ Available Tools

Once registered, Claude can call these tools on your behalf:

### `scan_plugins`
Lists every MCP server discovered in Claude Desktop's global config and any project-level `.mcp.json` files.

```
Example output:
🔌 5 MCP plugin(s) installed:

  • github-mcp
    Command : npx -y @modelcontextprotocol/server-github
    Source  : desktop

  • filesystem-mcp
    Command : npx -y @modelcontextprotocol/server-filesystem /home
    Source  : desktop
```

---

### `track_call`
Records a tool invocation. Call this **after** using any other MCP tool to log it.

| Parameter | Type | Description |
|---|---|---|
| `plugin_name` | string | Name of the MCP server (e.g. `"github-mcp"`) |
| `tool_name` | string | Name of the specific tool used |
| `input_data` | object | Parameters sent to the tool |
| `output` | string | Text response returned by the tool |
| `duration_ms` | number | Elapsed time in milliseconds |

```
Example output:
✅ Call recorded:
  Plugin   : github-mcp
  Tool     : search_repos
  Tokens   : 742 (in 128 / out 614)
  Duration : 1 203.4 ms
  Cost est.: $0.009594 USD
```

---

### `generate_report`
Generates the full HTML dashboard and opens it in your default browser.

| Parameter | Type | Default | Description |
|---|---|---|---|
| `open_browser` | boolean | `true` | Open the report automatically |

```
Example output:
📊 Dashboard generated successfully!
  File     : /home/you/.mcp-tracker/report.html
  Sessions : 180
  Plugins  : 5
  Browser  : opened automatically ✓
```

Open manually on Linux:
```bash
xdg-open ~/.mcp-tracker/report.html
```

---

### `get_stats`
Returns a quick plain-text summary without generating the full report.

```
Example output:
📈 Usage Summary
  Total tokens  : 128,450
  Total calls   : 180
  Estimated cost: $1.2034 USD

By plugin:
  • browser-mcp   : 42,310 tokens | 63 calls | 189.4s
  • github-mcp    : 38,902 tokens | 54 calls | 87.2s
  • postgres-mcp  : 25,680 tokens | 31 calls | 44.8s
```

---

### `reset_stats`
Permanently erases all recorded usage data from `~/.mcp-tracker/usage.json`.

> ⚠️ This action **cannot be undone**.

---

## 💡 Recommended Workflow

```
1. Open Claude Code inside your project (cd your-project && claude).
2. Ask Claude to use any MCP tool (search GitHub, query a DB, read a file, etc.).
3. After the response, ask Claude to call track_call to log the usage.
4. Repeat throughout your session.
5. When ready, ask Claude to generate_report — the dashboard opens automatically.
```

**Example prompt:**

```
Use github-mcp to search for Python MCP servers.
After you get the result, track the call with track_call.
When done, generate the token usage report.
```

> **⚠️ Claude Code tip:** If you have other plugins/skills installed, typing generic phrases
> like `scan my plugins` may trigger them instead of this plugin.
> To call your tools directly, always be explicit:
>
> ```
> use the mcp-save-tokens-4-claude scan_plugins tool
> call scan_plugins from mcp-save-tokens-4-claude
> call generate_report from mcp-save-tokens-4-claude
> call get_stats from mcp-save-tokens-4-claude
> call track_call from mcp-save-tokens-4-claude
> ```

---

## ⚙️ Configuration

### Adjusting token pricing

Edit `tracker.py`:

```python
# USD per 1 000 tokens — adjust to match your actual model pricing
INPUT_COST_PER_1K  = 0.003
OUTPUT_COST_PER_1K = 0.015
```

### Changing the report output path

Edit `server.py`:

```python
REPORT_PATH = Path.home() / ".mcp-tracker" / "report.html"
```

---

## 🏗️ Architecture

```
Claude Desktop / Claude Code (CLI)
     │
     │  stdio (MCP protocol)
     ▼
┌──────────────────────┐   reads   ┌─────────────────────┐
│      server.py       │◄─────────►│  config_reader.py   │
│  (mcp-save-tokens-   │           │  (plugin discovery) │
│    4-claude)         │           └─────────────────────┘
└──────────┬───────────┘
           │ log / read
           ▼
┌─────────────────┐  aggregates  ┌──────────────────────┐
│   tracker.py    │─────────────►│  report_generator.py │
│   (storage)     │              │  (Plotly dashboard)  │
└─────────────────┘              └──────────┬───────────┘
~/.mcp-tracker/                             │
  usage.json                                ▼
                                   report.html (browser)
```

---

## 📦 Dependencies

| Package | Purpose |
|---|---|
| `mcp` | Model Context Protocol SDK — server transport & tool API |
| `tiktoken` | Token counting with cl100k_base encoding |
| `pandas` | Data aggregation and transformation |
| `plotly` | Interactive chart generation |

---

## 🤝 Contributing

Contributions are welcome! Ideas for future improvements:

- [ ] Auto-intercept proxy mode (wrap other MCP servers transparently)
- [ ] SQLite backend for larger datasets
- [ ] Cost alerts / budget thresholds
- [ ] Export to CSV / Excel
- [ ] Claude Code plugin marketplace listing (`.claude-plugin/marketplace.json`)
- [ ] GitHub Actions CI

To contribute:

```bash
git clone --branch blog https://github.com/BRUNEXX13/savetokens4claude.git
cd savetokens4claude
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
# make your changes, then open a pull request
```

---

## 📄 License

MIT — see [LICENSE](LICENSE) for details.

---

## 🔗 Resources

- [Model Context Protocol — official docs](https://modelcontextprotocol.io)
- [MCP Python SDK](https://github.com/modelcontextprotocol/python-sdk)
- [Claude Desktop](https://claude.ai/download)
- [Claude Code](https://claude.ai/code)
- [tiktoken](https://github.com/openai/tiktoken)
- [Plotly Python](https://plotly.com/python/)
