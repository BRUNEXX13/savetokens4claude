# ⚡ MCP Token Tracker

> A Model Context Protocol (MCP) server that monitors **every MCP plugin installed in Claude Desktop**, counts their token usage, measures execution time, estimates USD cost, and exports a beautiful **interactive HTML dashboard** powered by Plotly + Pandas.

![Python](https://img.shields.io/badge/Python-3.11%2B-blue?style=flat-square&logo=python)
![MCP](https://img.shields.io/badge/MCP-1.0%2B-purple?style=flat-square)
![License](https://img.shields.io/badge/License-MIT-green?style=flat-square)

---

## 📸 Dashboard Preview

The generated report is a **self-contained HTML file** (no server needed) that opens directly in your browser with:

- **KPI cards** — total tokens, calls, estimated cost, avg duration
- **Interactive charts** — horizontal bar, input/output donut, calls pie, timeline
- **Detailed table** — per-plugin breakdown with cost estimates
- **Installed plugins inventory** — all discovered servers and their sources

---

## ✨ Features

| Feature | Description |
|---|---|
| 🔍 **Plugin Scanner** | Reads `claude_desktop_config.json` + project `.mcp.json` files |
| 🧮 **Token Counting** | Uses `tiktoken` (cl100k_base) — same encoding as Claude / GPT-4 |
| 💰 **Cost Estimation** | Configurable per-token pricing (input / output separately) |
| ⏱️ **Duration Tracking** | Records wall-clock time per tool call in milliseconds |
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

Open your terminal and run:

```bash
# macOS / Linux
python3 <(curl -fsSL https://raw.githubusercontent.com/BRUNEXX13/savetokens4claude/blog/install.py)
```

```powershell
# Windows (PowerShell)
python (Invoke-WebRequest -Uri "https://raw.githubusercontent.com/BRUNEXX13/savetokens4claude/blog/install.py" -UseBasicParsing).Content
```

The installer will automatically:
1. Clone this repository to `~/mcp-token-tracker`
2. Create an isolated Python virtual environment
3. Install all dependencies
4. Register the plugin in `claude_desktop_config.json`

Then **restart Claude Desktop** — and you're done. 🎉

### Uninstall

```bash
python3 ~/mcp-token-tracker/install.py --uninstall
```

### Custom install path

```bash
python3 <(curl -fsSL https://raw.githubusercontent.com/BRUNEXX13/savetokens4claude/blog/install.py) --dir ~/tools/mcp-tracker
```

---

## 🚀 Manual Setup

> Only needed if you prefer to set things up yourself.

### Prerequisites

- **Python 3.11+**
- **Claude Desktop** (with at least one MCP server already configured)
- **pip**

### 1 — Clone the repository

```bash
git clone --branch blog https://github.com/BRUNEXX13/savetokens4claude.git
cd savetokens4claude
```

### 2 — Install dependencies

```bash
pip install -r requirements.txt
```

Or, if you are using a virtual environment (recommended):

```bash
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### 3 — Register the server in Claude Desktop

Open your Claude Desktop config file:

| OS | Path |
|---|---|
| macOS | `~/Library/Application Support/Claude/claude_desktop_config.json` |
| Windows | `%APPDATA%\Claude\claude_desktop_config.json` |
| Linux | `~/.config/Claude/claude_desktop_config.json` |

Add the following entry inside `"mcpServers"`:

```json
{
  "mcpServers": {
    "mcp-token-tracker": {
      "command": "python3",
      "args": ["/absolute/path/to/savetokens4claude/server.py"]
    }
  }
}
```

> **Windows users:** use `python` instead of `python3`, and escape backslashes in the path:
> `"C:\\Users\\you\\savetokens4claude\\server.py"`

### 4 — Restart Claude Desktop

Close and reopen Claude Desktop. The five tracker tools will now appear in Claude's tool list automatically.

---

## 🛠️ Available Tools

Once registered, Claude can call these tools on your behalf:

### `scan_plugins`
Lists every MCP server discovered in Claude Desktop's global config and any project-level `.mcp.json` files found by walking up from the current directory.

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
Generates the full HTML dashboard from all recorded sessions and opens it in your default browser.

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
1. Ask Claude to use any MCP tool (e.g. search GitHub, query a database, read a file).
2. After the response, ask Claude to call  track_call  with the plugin name,
   tool name, the input/output, and the duration.
3. Repeat for other tool calls throughout your session.
4. When ready, ask Claude to  generate_report  to open the dashboard.
```

**Example prompt to Claude:**

```
Use github-mcp to search for Python MCP servers.
After you get the result, track the call with track_call so we can see the token usage.
When done, generate the report.
```

---

## ⚙️ Configuration

### Adjusting token pricing

Edit the constants at the top of `tracker.py`:

```python
# USD per 1 000 tokens — adjust to match your actual model pricing
INPUT_COST_PER_1K  = 0.003
OUTPUT_COST_PER_1K = 0.015
```

### Changing the report output path

Edit `REPORT_PATH` in `server.py`:

```python
REPORT_PATH = Path.home() / ".mcp-tracker" / "report.html"
```

### Using a virtual environment with Claude Desktop

If you installed dependencies inside a venv, point Claude Desktop to the venv's Python binary:

```json
{
  "mcpServers": {
    "mcp-token-tracker": {
      "command": "/absolute/path/to/savetokens4claude/.venv/bin/python3",
      "args": ["/absolute/path/to/savetokens4claude/server.py"]
    }
  }
}
```

---

## 🏗️ Architecture

```
Claude Desktop
     │
     │  stdio (MCP protocol)
     ▼
┌─────────────┐      reads      ┌─────────────────────┐
│  server.py  │◄───────────────►│  config_reader.py   │
│  (MCP server)│                │  (plugin discovery) │
└──────┬──────┘                 └─────────────────────┘
       │
       │  log / read
       ▼
┌─────────────┐   aggregates   ┌─────────────────────┐
│  tracker.py │───────────────►│ report_generator.py │
│  (storage)  │                │ (Plotly dashboard)  │
└─────────────┘                └──────────┬──────────┘
~/.mcp-tracker/                           │
  usage.json                              ▼
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

Contributions are welcome! Here are some ideas for future improvements:

- [ ] Auto-intercept proxy mode (wrap other MCP servers transparently)
- [ ] SQLite backend for larger datasets
- [ ] Cost alerts / budget thresholds
- [ ] Export to CSV / Excel
- [ ] Dark / light theme toggle in the dashboard
- [ ] GitHub Actions CI

To contribute:

```bash
git clone https://github.com/BRUNEXX13/savetokens4claude.git
cd savetokens4claude
python -m venv .venv && source .venv/bin/activate
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
- [tiktoken](https://github.com/openai/tiktoken)
- [Plotly Python](https://plotly.com/python/)
