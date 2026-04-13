"""
report_generator.py — Builds a self-contained, interactive HTML dashboard.

Stack: Pandas (aggregations) + Plotly (charts) → single .html file with no
external dependencies (Plotly JS is loaded from CDN; everything else is inlined).
"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict

import pandas as pd
import plotly.graph_objects as go


# ── Colour palette ─────────────────────────────────────────────────────────────
ACCENT   = "#6C63FF"
ACCENT2  = "#FF6584"
BG       = "#0F0F1A"
CARD_BG  = "#1A1A2E"
TEXT     = "#E0E0FF"
MUTED    = "#7B7BAA"
COLORS   = [
    "#6C63FF", "#FF6584", "#43E8D8", "#FFD166", "#06D6A0",
    "#EF476F", "#118AB2", "#FFC6FF", "#A8DADC", "#FFB703",
]


# ── Helpers ────────────────────────────────────────────────────────────────────

def _fmt_ms(ms: float) -> str:
    """Human-readable duration from milliseconds."""
    return f"{ms:.0f} ms" if ms < 1_000 else f"{ms / 1_000:.2f} s"


def _fig_base(**kwargs) -> go.Figure:
    """Return a Plotly figure pre-configured with the dark theme."""
    return go.Figure(**kwargs).update_layout(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor ="rgba(0,0,0,0)",
        font_color   =TEXT,
        font_family  ="'JetBrains Mono', monospace",
        margin       =dict(l=20, r=20, t=40, b=20),
        legend       =dict(bgcolor="rgba(0,0,0,0)", font_color=TEXT),
    )


def _to_div(fig: go.Figure, div_id: str) -> str:
    """Render a Plotly figure as an embeddable HTML div (no full-page wrapper)."""
    return fig.to_html(
        full_html=False,
        include_plotlyjs=False,
        div_id=div_id,
        config=dict(displayModeBar=False, responsive=True),
    )


# ── Main entry point ───────────────────────────────────────────────────────────

def generate_dashboard(
    usage_data: Dict[str, Any],
    installed_plugins: Dict[str, Any],
    output_path: Path,
) -> Path:
    """
    Build the HTML dashboard and write it to *output_path*.

    Parameters
    ----------
    usage_data : dict
        The structure returned by ``tracker.load_usage()``.
    installed_plugins : dict
        The structure returned by ``config_reader.get_installed_plugins()``.
    output_path : Path
        Destination file (created / overwritten).

    Returns
    -------
    Path
        The same *output_path* for convenience.
    """
    sessions = usage_data.get("sessions", [])

    # ── Aggregate data ─────────────────────────────────────────────────────────
    if sessions:
        df = pd.DataFrame(sessions)
        df["timestamp"] = pd.to_datetime(df["timestamp"])
        df["date"]      = df["timestamp"].dt.date

        by_plugin = (
            df.groupby("plugin")
            .agg(
                total_tokens   =("total_tokens",  "sum"),
                input_tokens   =("input_tokens",  "sum"),
                output_tokens  =("output_tokens", "sum"),
                calls          =("tool",          "count"),
                avg_duration_ms=("duration_ms",   "mean"),
                total_time_ms  =("duration_ms",   "sum"),
                cost_usd       =("cost_usd",      "sum"),
            )
            .reset_index()
            .sort_values("total_tokens", ascending=False)
        )

        by_date = (
            df.groupby(["date", "plugin"])["total_tokens"]
            .sum()
            .reset_index()
        )

        total_tokens   = int(df["total_tokens"].sum())
        total_calls    = len(df)
        total_cost     = float(df["cost_usd"].sum())
        avg_dur_ms     = float(df["duration_ms"].mean())
        unique_plugins = int(df["plugin"].nunique())
    else:
        df = by_plugin = by_date = pd.DataFrame()
        total_tokens = total_calls = 0
        total_cost = avg_dur_ms = 0.0
        unique_plugins = 0

    installed_cnt = len(installed_plugins)

    # ── Charts ─────────────────────────────────────────────────────────────────

    # 1. Horizontal bar — tokens per plugin
    if not by_plugin.empty:
        fig_bar = _fig_base()
        fig_bar.add_trace(go.Bar(
            y           =by_plugin["plugin"],
            x           =by_plugin["total_tokens"],
            orientation ="h",
            marker_color=[COLORS[i % len(COLORS)] for i in range(len(by_plugin))],
            text        =[f"{v:,}" for v in by_plugin["total_tokens"]],
            textposition="outside",
            textfont_color=TEXT,
        ))
        fig_bar.update_layout(
            title ="Token Usage by Plugin",
            xaxis =dict(gridcolor="#2A2A4A", zerolinecolor="#2A2A4A"),
            yaxis =dict(gridcolor="#2A2A4A"),
            height=max(280, len(by_plugin) * 52 + 80),
        )
    else:
        fig_bar = _fig_base().update_layout(title="Token Usage by Plugin", height=280)

    # 2. Donut — input vs output
    if not by_plugin.empty:
        total_in  = int(by_plugin["input_tokens"].sum())
        total_out = int(by_plugin["output_tokens"].sum())
        fig_donut = _fig_base(data=[go.Pie(
            labels  =["Input Tokens", "Output Tokens"],
            values  =[total_in, total_out],
            hole    =0.62,
            marker  =dict(colors=[ACCENT, ACCENT2]),
            textfont_color=TEXT,
        )])
        fig_donut.update_layout(title="Input vs Output", height=300)
    else:
        fig_donut = _fig_base().update_layout(title="Input vs Output", height=300)

    # 3. Line — tokens over time
    if not by_date.empty:
        fig_line = _fig_base()
        for i, plugin in enumerate(by_date["plugin"].unique()):
            sub = by_date[by_date["plugin"] == plugin]
            fig_line.add_trace(go.Scatter(
                x    =sub["date"].astype(str),
                y    =sub["total_tokens"],
                name =plugin,
                mode ="lines+markers",
                line =dict(color=COLORS[i % len(COLORS)], width=2),
                marker=dict(size=6),
            ))
        fig_line.update_layout(
            title ="Token Usage Over Time",
            xaxis =dict(gridcolor="#2A2A4A"),
            yaxis =dict(gridcolor="#2A2A4A"),
            height=300,
        )
    else:
        fig_line = _fig_base().update_layout(title="Token Usage Over Time", height=300)

    # 4. Pie — call distribution
    if not by_plugin.empty:
        fig_calls = _fig_base(data=[go.Pie(
            labels  =by_plugin["plugin"],
            values  =by_plugin["calls"],
            marker  =dict(colors=COLORS[:len(by_plugin)]),
            textfont_color=TEXT,
        )])
        fig_calls.update_layout(title="Calls by Plugin", height=300)
    else:
        fig_calls = _fig_base().update_layout(title="Calls by Plugin", height=300)

    html_bar   = _to_div(fig_bar,   "bar")
    html_donut = _to_div(fig_donut, "donut")
    html_line  = _to_div(fig_line,  "line")
    html_calls = _to_div(fig_calls, "calls")

    # ── Detailed stats table ───────────────────────────────────────────────────
    if not by_plugin.empty:
        rows = ""
        for _, r in by_plugin.iterrows():
            src = installed_plugins.get(r["plugin"], {}).get("source", "—")
            rows += (
                f"<tr>"
                f"<td><span class='badge'>{r['plugin']}</span></td>"
                f"<td>{int(r['total_tokens']):,}</td>"
                f"<td>{int(r['input_tokens']):,}</td>"
                f"<td>{int(r['output_tokens']):,}</td>"
                f"<td>{int(r['calls'])}</td>"
                f"<td>{_fmt_ms(r['avg_duration_ms'])}</td>"
                f"<td>{_fmt_ms(r['total_time_ms'])}</td>"
                f"<td class='cost'>${r['cost_usd']:.4f}</td>"
                f"<td><span class='src'>{src}</span></td>"
                f"</tr>"
            )
        stats_table = (
            "<table><thead><tr>"
            "<th>Plugin</th><th>Total Tokens</th><th>Input</th><th>Output</th>"
            "<th>Calls</th><th>Avg Duration</th><th>Total Time</th>"
            "<th>Est. Cost</th><th>Source</th>"
            f"</tr></thead><tbody>{rows}</tbody></table>"
        )
    else:
        stats_table = "<p class='empty'>No usage data recorded yet.</p>"

    # ── Installed plugins table ────────────────────────────────────────────────
    if installed_plugins:
        inst_rows = ""
        for name, info in installed_plugins.items():
            cmd  = info.get("command", "—")
            args = " ".join(str(a) for a in info.get("args", []))[:60]
            src  = info.get("source", "—")
            inst_rows += (
                f"<tr>"
                f"<td><span class='badge'>{name}</span></td>"
                f"<td><code>{cmd}</code></td>"
                f"<td><code class='muted'>{args}</code></td>"
                f"<td><span class='src'>{src}</span></td>"
                f"</tr>"
            )
        inst_table = (
            "<table><thead><tr>"
            "<th>Plugin</th><th>Command</th><th>Args</th><th>Source</th>"
            f"</tr></thead><tbody>{inst_rows}</tbody></table>"
        )
    else:
        inst_table = "<p class='empty'>No installed plugins detected.</p>"

    generated_at = datetime.now().strftime("%Y-%m-%d at %H:%M:%S")

    # ── Final HTML ─────────────────────────────────────────────────────────────
    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>MCP Token Tracker — Dashboard</title>
  <script src="https://cdn.plot.ly/plotly-2.32.0.min.js"></script>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link href="https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@300;400;600;700&family=Space+Grotesk:wght@400;600;700&display=swap" rel="stylesheet">
  <style>
    *, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}
    :root {{
      --bg: {BG}; --card: {CARD_BG}; --accent: {ACCENT}; --accent2: {ACCENT2};
      --text: {TEXT}; --muted: {MUTED}; --border: #2A2A4A; --radius: 12px;
    }}
    body {{ background: var(--bg); color: var(--text); font-family: 'Space Grotesk', sans-serif; min-height: 100vh; padding-bottom: 60px; }}
    header {{ background: linear-gradient(135deg,#0F0F1A 0%,#1A1A3E 100%); border-bottom: 1px solid var(--border); padding: 28px 40px; display: flex; align-items: center; gap: 20px; position: sticky; top: 0; z-index: 100; }}
    .logo {{ width:42px;height:42px;background:var(--accent);border-radius:10px;display:flex;align-items:center;justify-content:center;font-size:20px; }}
    header h1 {{ font-size:1.4rem;font-weight:700;letter-spacing:-0.02em; }}
    header h1 span {{ color:var(--accent); }}
    .subtitle {{ margin-left:auto;font-family:'JetBrains Mono',monospace;font-size:0.72rem;color:var(--muted); }}
    main {{ max-width:1400px;margin:0 auto;padding:36px 40px 0; }}
    .section-title {{ font-size:0.7rem;font-weight:600;letter-spacing:0.12em;text-transform:uppercase;color:var(--muted);margin:36px 0 16px; }}
    .section-title::before {{ content:'// ';color:var(--accent); }}
    .kpi-grid {{ display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:16px; }}
    .kpi {{ background:var(--card);border:1px solid var(--border);border-radius:var(--radius);padding:22px 24px;position:relative;overflow:hidden;transition:border-color .2s,transform .2s; }}
    .kpi:hover {{ border-color:var(--accent);transform:translateY(-2px); }}
    .kpi::before {{ content:'';position:absolute;top:0;left:0;right:0;height:3px;background:var(--accent); }}
    .kpi.alt::before {{ background:var(--accent2); }}
    .kpi label {{ font-family:'JetBrains Mono',monospace;font-size:0.68rem;color:var(--muted);letter-spacing:0.06em;text-transform:uppercase;display:block;margin-bottom:10px; }}
    .kpi .value {{ font-size:2rem;font-weight:700;line-height:1; }}
    .kpi .unit {{ font-size:0.85rem;color:var(--muted);margin-left:4px; }}
    .chart-grid {{ display:grid;grid-template-columns:1fr 1fr;gap:16px; }}
    .chart-wide {{ grid-column:1/-1; }}
    .chart-card {{ background:var(--card);border:1px solid var(--border);border-radius:var(--radius);padding:20px;overflow:hidden; }}
    .table-card {{ background:var(--card);border:1px solid var(--border);border-radius:var(--radius);overflow:auto; }}
    table {{ width:100%;border-collapse:collapse;font-size:0.85rem; }}
    thead {{ background:#111128; }}
    th {{ padding:14px 16px;text-align:left;font-family:'JetBrains Mono',monospace;font-size:0.65rem;letter-spacing:0.1em;text-transform:uppercase;color:var(--muted);white-space:nowrap;border-bottom:1px solid var(--border); }}
    td {{ padding:12px 16px;border-bottom:1px solid #1E1E38;vertical-align:middle; }}
    tr:last-child td {{ border-bottom:none; }}
    tr:hover td {{ background:rgba(108,99,255,.06); }}
    .badge {{ display:inline-block;background:rgba(108,99,255,.15);color:#A09EFF;border:1px solid rgba(108,99,255,.3);border-radius:6px;padding:3px 9px;font-family:'JetBrains Mono',monospace;font-size:.78rem;white-space:nowrap; }}
    .src {{ font-family:'JetBrains Mono',monospace;font-size:.72rem;color:var(--muted); }}
    .cost {{ color:#FFD166;font-weight:600; }}
    code {{ font-family:'JetBrains Mono',monospace;font-size:.78rem;background:#111128;padding:2px 6px;border-radius:4px; }}
    code.muted {{ color:var(--muted); }}
    .empty {{ padding:32px;text-align:center;color:var(--muted);font-family:'JetBrains Mono',monospace;font-size:.85rem; }}
    footer {{ text-align:center;margin-top:48px;font-family:'JetBrains Mono',monospace;font-size:.7rem;color:var(--muted); }}
    footer a {{ color:var(--accent);text-decoration:none; }}
  </style>
</head>
<body>
<header>
  <div class="logo">⚡</div>
  <h1>MCP <span>Token</span> Tracker</h1>
  <div class="subtitle">Generated on {generated_at}</div>
</header>
<main>
  <p class="section-title">Overview</p>
  <div class="kpi-grid">
    <div class="kpi"><label>Total Tokens</label><div class="value">{total_tokens:,}</div></div>
    <div class="kpi"><label>Tracked Calls</label><div class="value">{total_calls:,}</div></div>
    <div class="kpi alt"><label>Estimated Cost</label><div class="value">${total_cost:.4f}<span class="unit">USD</span></div></div>
    <div class="kpi"><label>Active Plugins</label><div class="value">{unique_plugins}<span class="unit">/ {installed_cnt}</span></div></div>
    <div class="kpi"><label>Avg Duration</label><div class="value">{_fmt_ms(avg_dur_ms)}</div></div>
  </div>
  <p class="section-title">Charts</p>
  <div class="chart-grid">
    <div class="chart-card chart-wide">{html_bar}</div>
    <div class="chart-card">{html_donut}</div>
    <div class="chart-card">{html_calls}</div>
    <div class="chart-card chart-wide">{html_line}</div>
  </div>
  <p class="section-title">Detailed Usage by Plugin</p>
  <div class="table-card">{stats_table}</div>
  <p class="section-title">Installed Plugins ({installed_cnt})</p>
  <div class="table-card">{inst_table}</div>
</main>
<footer>
  <p>MCP Token Tracker &mdash; auto-generated &bull;
     <a href="https://modelcontextprotocol.io" target="_blank">modelcontextprotocol.io</a>
  </p>
</footer>
</body>
</html>"""

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(html, encoding="utf-8")
    return output_path
