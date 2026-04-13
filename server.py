"""
server.py — MCP Token Tracker  (main entry point)

MCP tools exposed to Claude
───────────────────────────
  scan_plugins    List every MCP server installed in Claude Desktop or project configs.
  track_call      Record a tool invocation with automatic token counting.
  generate_report Build an interactive HTML dashboard and open it in the browser.
  get_stats       Return a quick plain-text usage summary.
  reset_stats     Erase all recorded usage data (irreversible).

Usage
─────
  python server.py          # stdio transport (for Claude Desktop / claude_desktop_config.json)
"""
import asyncio
import json
import os
import subprocess
import sys
from pathlib import Path

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp import types

import tracker
import config_reader
import report_generator

# Default dashboard output path
REPORT_PATH = Path.home() / ".mcp-tracker" / "report.html"

server = Server("mcp-token-tracker")


# ── Tool definitions ───────────────────────────────────────────────────────────

@server.list_tools()
async def list_tools() -> list[types.Tool]:
    return [
        types.Tool(
            name="scan_plugins",
            description=(
                "Scan and list every MCP server installed in Claude Desktop "
                "(global config) and in any project-level .mcp.json files."
            ),
            inputSchema={"type": "object", "properties": {}, "required": []},
        ),
        types.Tool(
            name="track_call",
            description=(
                "Record an MCP tool call for token tracking. "
                "Call this tool after invoking any other MCP tool, passing the "
                "plugin name, tool name, the input sent, the output received, "
                "and the elapsed time in milliseconds."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "plugin_name": {
                        "type": "string",
                        "description": "Name of the MCP server (e.g. 'github-mcp')",
                    },
                    "tool_name": {
                        "type": "string",
                        "description": "Name of the tool that was called",
                    },
                    "input_data": {
                        "type": "object",
                        "description": "Parameters / payload sent to the tool",
                    },
                    "output": {
                        "type": "string",
                        "description": "Text response returned by the tool",
                    },
                    "duration_ms": {
                        "type": "number",
                        "description": "Wall-clock execution time in milliseconds",
                    },
                },
                "required": [
                    "plugin_name", "tool_name",
                    "input_data", "output", "duration_ms",
                ],
            },
        ),
        types.Tool(
            name="generate_report",
            description=(
                "Generate an interactive HTML dashboard (Plotly + Pandas) showing "
                "token consumption, estimated cost, call frequency, and duration "
                "per plugin. Opens automatically in the default browser."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "open_browser": {
                        "type": "boolean",
                        "description": "Open the report in the browser automatically (default: true)",
                    }
                },
                "required": [],
            },
        ),
        types.Tool(
            name="get_stats",
            description="Return a quick plain-text summary of current usage statistics.",
            inputSchema={"type": "object", "properties": {}, "required": []},
        ),
        types.Tool(
            name="reset_stats",
            description="Erase all recorded usage data. This action is irreversible.",
            inputSchema={"type": "object", "properties": {}, "required": []},
        ),
    ]


# ── Tool implementations ───────────────────────────────────────────────────────

@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[types.TextContent]:

    # ── scan_plugins ────────────────────────────────────────────────────────────
    if name == "scan_plugins":
        plugins = config_reader.get_installed_plugins()
        if not plugins:
            return [types.TextContent(type="text", text="No installed MCP plugins found.")]

        lines = [f"🔌 {len(plugins)} MCP plugin(s) installed:\n"]
        for pname, info in plugins.items():
            cmd  = info.get("command", "?")
            args = " ".join(str(a) for a in info.get("args", []))
            src  = info.get("source", "?")
            lines.append(
                f"  • {pname}\n"
                f"    Command : {cmd} {args}\n"
                f"    Source  : {src}\n"
            )
        return [types.TextContent(type="text", text="\n".join(lines))]

    # ── track_call ──────────────────────────────────────────────────────────────
    elif name == "track_call":
        entry = tracker.log_tool_call(
            plugin_name=arguments["plugin_name"],
            tool_name  =arguments["tool_name"],
            input_data =arguments.get("input_data", {}),
            output     =arguments.get("output", ""),
            duration_ms=arguments.get("duration_ms", 0.0),
        )
        return [types.TextContent(
            type="text",
            text=(
                f"✅ Call recorded:\n"
                f"  Plugin   : {entry['plugin']}\n"
                f"  Tool     : {entry['tool']}\n"
                f"  Tokens   : {entry['total_tokens']:,} "
                f"(in {entry['input_tokens']:,} / out {entry['output_tokens']:,})\n"
                f"  Duration : {entry['duration_ms']:.1f} ms\n"
                f"  Cost est.: ${entry['cost_usd']:.6f} USD"
            ),
        )]

    # ── generate_report ─────────────────────────────────────────────────────────
    elif name == "generate_report":
        usage_data = tracker.load_usage()
        plugins    = config_reader.get_installed_plugins()

        report_generator.generate_dashboard(usage_data, plugins, REPORT_PATH)

        open_browser = arguments.get("open_browser", True)
        if open_browser:
            try:
                if sys.platform == "darwin":
                    subprocess.run(["open", str(REPORT_PATH)], check=False)
                elif sys.platform == "win32":
                    os.startfile(str(REPORT_PATH))
                else:
                    subprocess.run(["xdg-open", str(REPORT_PATH)], check=False)
            except Exception:
                pass  # best-effort; never crash the server

        sessions = len(usage_data.get("sessions", []))
        return [types.TextContent(
            type="text",
            text=(
                f"📊 Dashboard generated successfully!\n"
                f"  File     : {REPORT_PATH}\n"
                f"  Sessions : {sessions:,}\n"
                f"  Plugins  : {len(plugins)}\n"
                f"  Browser  : {'opened automatically ✓' if open_browser else 'not opened'}"
            ),
        )]

    # ── get_stats ───────────────────────────────────────────────────────────────
    elif name == "get_stats":
        data     = tracker.load_usage()
        sessions = data.get("sessions", [])
        if not sessions:
            return [types.TextContent(type="text", text="No usage data recorded yet.")]

        total_tokens = sum(s["total_tokens"] for s in sessions)
        total_cost   = sum(s.get("cost_usd", 0) for s in sessions)
        total_calls  = len(sessions)

        by_plugin: dict[str, dict] = {}
        for s in sessions:
            p = s["plugin"]
            if p not in by_plugin:
                by_plugin[p] = {"tokens": 0, "calls": 0, "time_ms": 0.0}
            by_plugin[p]["tokens"]  += s["total_tokens"]
            by_plugin[p]["calls"]   += 1
            by_plugin[p]["time_ms"] += s.get("duration_ms", 0)

        lines = [
            "📈 Usage Summary",
            f"  Total tokens  : {total_tokens:,}",
            f"  Total calls   : {total_calls:,}",
            f"  Estimated cost: ${total_cost:.4f} USD",
            "",
            "By plugin:",
        ]
        for pname, stats in sorted(by_plugin.items(), key=lambda x: -x[1]["tokens"]):
            t_sec = stats["time_ms"] / 1_000
            lines.append(
                f"  • {pname}: {stats['tokens']:,} tokens | "
                f"{stats['calls']} calls | {t_sec:.1f}s"
            )

        return [types.TextContent(type="text", text="\n".join(lines))]

    # ── reset_stats ─────────────────────────────────────────────────────────────
    elif name == "reset_stats":
        tracker.reset_usage()
        return [types.TextContent(type="text", text="🗑️ All usage data has been erased.")]

    return [types.TextContent(type="text", text=f"Unknown tool: {name}")]


# ── Entry point ────────────────────────────────────────────────────────────────

async def main() -> None:
    async with stdio_server() as streams:
        await server.run(
            streams[0],
            streams[1],
            server.create_initialization_options(),
        )


if __name__ == "__main__":
    asyncio.run(main())
