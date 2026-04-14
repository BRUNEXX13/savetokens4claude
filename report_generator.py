"""
report_generator.py — Builds a self-contained, interactive HTML dashboard.

New features v2:
  - Plugin installation date (config/script mtime)
  - First seen / last seen datetime per plugin
  - Session tokens (last 24 h) highlighted in teal
  - Interactive search/filter on both tables
"""
from __future__ import annotations
import os, platform
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict
import pandas as pd
import plotly.graph_objects as go

ACCENT  = "#6C63FF"
ACCENT2 = "#FF6584"
BG      = "#0F0F1A"
CARD_BG = "#1A1A2E"
TEXT    = "#E0E0FF"
MUTED   = "#7B7BAA"
COLORS  = ["#6C63FF","#FF6584","#43E8D8","#FFD166","#06D6A0","#EF476F","#118AB2","#FFC6FF","#A8DADC","#FFB703"]

def _fmt_ms(ms: float) -> str:
    return f"{ms:.0f} ms" if ms < 1_000 else f"{ms/1_000:.2f} s"

def _install_date(info: Dict[str,Any]) -> str:
    src = info.get("source","")
    if src.startswith("project:"):
        p = Path(src.replace("project:",""))
        if p.exists(): return datetime.fromtimestamp(p.stat().st_mtime).strftime("%Y-%m-%d")
    elif src == "desktop":
        s = platform.system()
        if s == "Darwin":   p = Path.home()/"Library"/"Application Support"/"Claude"/"claude_desktop_config.json"
        elif s == "Windows":p = Path(os.environ.get("APPDATA",str(Path.home())))/"Claude"/"claude_desktop_config.json"
        else:               p = Path.home()/".config"/"Claude"/"claude_desktop_config.json"
        if p.exists(): return datetime.fromtimestamp(p.stat().st_mtime).strftime("%Y-%m-%d")
    for arg in info.get("args",[]):
        p = Path(str(arg))
        if p.exists() and p.suffix in (".py",".js",".ts"):
            return datetime.fromtimestamp(p.stat().st_mtime).strftime("%Y-%m-%d")
    return "—"

def _fig_base(**kw) -> go.Figure:
    return go.Figure(**kw).update_layout(
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        font_color=TEXT, font_family="'JetBrains Mono',monospace",
        margin=dict(l=20,r=20,t=40,b=20),
        legend=dict(bgcolor="rgba(0,0,0,0)",font_color=TEXT))

def _div(fig,div_id):
    return fig.to_html(full_html=False,include_plotlyjs=False,div_id=div_id,config=dict(displayModeBar=False,responsive=True))

def generate_dashboard(usage_data:Dict[str,Any], installed_plugins:Dict[str,Any], output_path:Path) -> Path:
    sessions = usage_data.get("sessions",[])
    now      = datetime.now()
    cutoff   = now - timedelta(hours=24)

    if sessions:
        df = pd.DataFrame(sessions)
        df["timestamp"] = pd.to_datetime(df["timestamp"])
        df["date"]      = df["timestamp"].dt.date
        df_sess = df[df["timestamp"] >= pd.Timestamp(cutoff)]

        by_plugin = (df.groupby("plugin").agg(
            total_tokens=("total_tokens","sum"), input_tokens=("input_tokens","sum"),
            output_tokens=("output_tokens","sum"), calls=("tool","count"),
            avg_duration_ms=("duration_ms","mean"), total_time_ms=("duration_ms","sum"),
            cost_usd=("cost_usd","sum"), first_seen=("timestamp","min"), last_seen=("timestamp","max")
        ).reset_index().sort_values("total_tokens",ascending=False))

        sess_agg = df_sess.groupby("plugin")["total_tokens"].sum().reset_index().rename(columns={"total_tokens":"session_tokens"})
        by_plugin = by_plugin.merge(sess_agg,on="plugin",how="left")
        by_plugin["session_tokens"] = by_plugin["session_tokens"].fillna(0).astype(int)
        by_date = df.groupby(["date","plugin"])["total_tokens"].sum().reset_index()

        total_tokens=int(df["total_tokens"].sum()); total_calls=len(df)
        total_cost=float(df["cost_usd"].sum()); avg_dur_ms=float(df["duration_ms"].mean())
        unique_plugins=int(df["plugin"].nunique())
        session_tokens=int(df_sess["total_tokens"].sum()) if not df_sess.empty else 0
    else:
        df=by_plugin=by_date=pd.DataFrame()
        total_tokens=total_calls=session_tokens=0; total_cost=avg_dur_ms=0.0; unique_plugins=0

    installed_cnt = len(installed_plugins)

    # charts
    if not by_plugin.empty:
        fb=_fig_base(); fb.add_trace(go.Bar(y=by_plugin["plugin"],x=by_plugin["total_tokens"],orientation="h",
            marker_color=[COLORS[i%len(COLORS)] for i in range(len(by_plugin))],
            text=[f"{v:,}" for v in by_plugin["total_tokens"]],textposition="outside",textfont_color=TEXT))
        fb.update_layout(title="Token Usage by Plugin",xaxis=dict(gridcolor="#2A2A4A",zerolinecolor="#2A2A4A"),
            yaxis=dict(gridcolor="#2A2A4A"),height=max(280,len(by_plugin)*52+80))
        fd=_fig_base(data=[go.Pie(labels=["Input","Output"],values=[int(by_plugin["input_tokens"].sum()),int(by_plugin["output_tokens"].sum())],
            hole=0.62,marker=dict(colors=[ACCENT,ACCENT2]),textfont_color=TEXT)])
        fd.update_layout(title="Input vs Output",height=300)
        fc=_fig_base(data=[go.Pie(labels=by_plugin["plugin"],values=by_plugin["calls"],
            marker=dict(colors=COLORS[:len(by_plugin)]),textfont_color=TEXT)])
        fc.update_layout(title="Calls by Plugin",height=300)
    else:
        fb=_fig_base().update_layout(title="Token Usage by Plugin",height=280)
        fd=_fig_base().update_layout(title="Input vs Output",height=300)
        fc=_fig_base().update_layout(title="Calls by Plugin",height=300)

    if not by_plugin.empty and not by_date.empty:
        fl=_fig_base()
        for i,plugin in enumerate(by_date["plugin"].unique()):
            sub=by_date[by_date["plugin"]==plugin]
            fl.add_trace(go.Scatter(x=sub["date"].astype(str),y=sub["total_tokens"],name=plugin,
                mode="lines+markers",line=dict(color=COLORS[i%len(COLORS)],width=2),marker=dict(size=6)))
        fl.update_layout(title="Token Usage Over Time",xaxis=dict(gridcolor="#2A2A4A"),yaxis=dict(gridcolor="#2A2A4A"),height=300)
    else:
        fl=_fig_base().update_layout(title="Token Usage Over Time",height=300)

    html_bar=_div(fb,"bar"); html_donut=_div(fd,"donut"); html_line=_div(fl,"line"); html_calls=_div(fc,"calls")

    # stats table
    if not by_plugin.empty:
        rows=""
        for _,r in by_plugin.iterrows():
            info=installed_plugins.get(r["plugin"],{})
            inst=_install_date(info)
            fs=r["first_seen"].strftime("%Y-%m-%d %H:%M") if pd.notna(r["first_seen"]) else "—"
            ls=r["last_seen"].strftime("%Y-%m-%d %H:%M")  if pd.notna(r["last_seen"])  else "—"
            st=f"{int(r['session_tokens']):,}" if r["session_tokens"]>0 else "—"
            src=info.get("source","—")
            rows+=(f"<tr data-plugin='{r['plugin'].lower()}'>"
                f"<td><span class='badge'>{r['plugin']}</span></td>"
                f"<td>{int(r['total_tokens']):,}</td>"
                f"<td><span class='stok'>{st}</span></td>"
                f"<td>{int(r['input_tokens']):,}</td>"
                f"<td>{int(r['output_tokens']):,}</td>"
                f"<td>{int(r['calls'])}</td>"
                f"<td>{_fmt_ms(r['avg_duration_ms'])}</td>"
                f"<td class='cost'>${r['cost_usd']:.4f}</td>"
                f"<td><span class='dp'>{inst}</span></td>"
                f"<td><span class='dp'>{fs}</span></td>"
                f"<td><span class='dp'>{ls}</span></td>"
                f"<td><span class='src'>{src}</span></td></tr>")
        stats_table=(
            "<table id='statsTable'><thead><tr>"
            "<th>Plugin</th><th>Total Tokens</th><th>Session (24h)</th>"
            "<th>Input</th><th>Output</th><th>Calls</th><th>Avg Duration</th>"
            "<th>Est. Cost</th><th>Installed</th><th>First Seen</th><th>Last Seen</th><th>Source</th>"
            f"</tr></thead><tbody>{rows}</tbody></table>")
    else:
        stats_table="<p class='empty'>No usage data recorded yet.</p>"

    # installed table
    if installed_plugins:
        ir=""
        for name,info in installed_plugins.items():
            cmd=info.get("command","—"); args=" ".join(str(a) for a in info.get("args",[]))[:60]
            src=info.get("source","—"); inst=_install_date(info)
            ir+=(f"<tr data-plugin='{name.lower()}'>"
                f"<td><span class='badge'>{name}</span></td>"
                f"<td><code>{cmd}</code></td><td><code class='muted'>{args}</code></td>"
                f"<td><span class='dp'>{inst}</span></td>"
                f"<td><span class='src'>{src}</span></td></tr>")
        inst_table=(
            "<table id='instTable'><thead><tr>"
            "<th>Plugin</th><th>Command</th><th>Args</th><th>Installed</th><th>Source</th>"
            f"</tr></thead><tbody>{ir}</tbody></table>")
    else:
        inst_table="<p class='empty'>No installed plugins detected.</p>"

    generated_at=now.strftime("%Y-%m-%d at %H:%M:%S")

    CSS=f"""
    *,*::before,*::after{{box-sizing:border-box;margin:0;padding:0}}
    :root{{--bg:{BG};--card:{CARD_BG};--accent:{ACCENT};--accent2:{ACCENT2};--text:{TEXT};--muted:{MUTED};--border:#2A2A4A;--radius:12px}}
    body{{background:var(--bg);color:var(--text);font-family:'Space Grotesk',sans-serif;min-height:100vh;padding-bottom:60px}}
    header{{background:linear-gradient(135deg,#0F0F1A,#1A1A3E);border-bottom:1px solid var(--border);padding:24px 40px;display:flex;align-items:center;gap:16px;position:sticky;top:0;z-index:100}}
    .logo{{width:40px;height:40px;background:var(--accent);border-radius:10px;display:flex;align-items:center;justify-content:center;font-size:18px;flex-shrink:0}}
    header h1{{font-size:1.3rem;font-weight:700;letter-spacing:-.02em}} header h1 span{{color:var(--accent)}}
    .subtitle{{margin-left:auto;font-family:'JetBrains Mono',monospace;font-size:.7rem;color:var(--muted);white-space:nowrap}}
    main{{max-width:1400px;margin:0 auto;padding:32px 40px 0}}
    .sec{{font-size:.7rem;font-weight:600;letter-spacing:.12em;text-transform:uppercase;color:var(--muted);margin:36px 0 14px}}
    .sec::before{{content:'// ';color:var(--accent)}}
    .kpi-grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(170px,1fr));gap:14px}}
    .kpi{{background:var(--card);border:1px solid var(--border);border-radius:var(--radius);padding:20px 22px;position:relative;overflow:hidden;transition:border-color .2s,transform .2s}}
    .kpi:hover{{border-color:var(--accent);transform:translateY(-2px)}}
    .kpi::before{{content:'';position:absolute;top:0;left:0;right:0;height:3px;background:var(--accent)}}
    .kpi.alt::before{{background:var(--accent2)}} .kpi.grn::before{{background:#06D6A0}}
    .kpi label{{font-family:'JetBrains Mono',monospace;font-size:.65rem;color:var(--muted);letter-spacing:.06em;text-transform:uppercase;display:block;margin-bottom:8px}}
    .kpi .val{{font-size:1.9rem;font-weight:700;line-height:1}} .kpi .unit{{font-size:.8rem;color:var(--muted);margin-left:3px}}
    .chart-grid{{display:grid;grid-template-columns:1fr 1fr;gap:14px}}
    .cw{{grid-column:1/-1}} .cc{{background:var(--card);border:1px solid var(--border);border-radius:var(--radius);padding:18px;overflow:hidden}}
    .sb{{display:flex;align-items:center;gap:10px;background:var(--card);border:1px solid var(--border);border-radius:10px;padding:10px 16px;margin-bottom:12px;transition:border-color .2s}}
    .sb:focus-within{{border-color:var(--accent)}} .sb svg{{color:var(--muted);flex-shrink:0}}
    .sb input{{background:none;border:none;outline:none;color:var(--text);font-family:'JetBrains Mono',monospace;font-size:.88rem;width:100%}}
    .sb input::placeholder{{color:var(--muted)}} .sc{{font-family:'JetBrains Mono',monospace;font-size:.7rem;color:var(--muted);white-space:nowrap}}
    .tw{{background:var(--card);border:1px solid var(--border);border-radius:var(--radius);overflow:auto}}
    table{{width:100%;border-collapse:collapse;font-size:.82rem}}
    thead{{background:#111128;position:sticky;top:0;z-index:2}}
    th{{padding:12px 14px;text-align:left;font-family:'JetBrains Mono',monospace;font-size:.6rem;letter-spacing:.1em;text-transform:uppercase;color:var(--muted);white-space:nowrap;border-bottom:1px solid var(--border)}}
    td{{padding:10px 14px;border-bottom:1px solid #1E1E38;vertical-align:middle}}
    tr:last-child td{{border-bottom:none}} tr:hover td{{background:rgba(108,99,255,.06)}}
    tr[data-plugin].hidden{{display:none}}
    .badge{{display:inline-block;background:rgba(108,99,255,.15);color:#A09EFF;border:1px solid rgba(108,99,255,.3);border-radius:6px;padding:3px 9px;font-family:'JetBrains Mono',monospace;font-size:.75rem;white-space:nowrap}}
    .dp{{display:inline-block;background:rgba(255,255,255,.04);border:1px solid var(--border);border-radius:5px;padding:2px 7px;font-family:'JetBrains Mono',monospace;font-size:.7rem;color:var(--muted);white-space:nowrap}}
    .stok{{color:#43E8D8;font-weight:600}} .src{{font-family:'JetBrains Mono',monospace;font-size:.7rem;color:var(--muted)}}
    .cost{{color:#FFD166;font-weight:600}}
    code{{font-family:'JetBrains Mono',monospace;font-size:.75rem;background:#111128;padding:2px 6px;border-radius:4px}} code.muted{{color:var(--muted)}}
    .empty{{padding:32px;text-align:center;color:var(--muted);font-family:'JetBrains Mono',monospace;font-size:.85rem}}
    .nr{{display:none;padding:20px;text-align:center;color:var(--muted);font-family:'JetBrains Mono',monospace;font-size:.8rem}}
    footer{{text-align:center;margin-top:48px;font-family:'JetBrains Mono',monospace;font-size:.7rem;color:var(--muted)}}
    footer a{{color:var(--accent);text-decoration:none}}"""

    JS="""
    function filterTable(si,ti,ci,ni){
      const q=document.getElementById(si).value.toLowerCase().trim();
      const rows=document.querySelectorAll('#'+ti+' tbody tr[data-plugin]');
      const ce=document.getElementById(ci); const nr=document.getElementById(ni);
      let v=0;
      rows.forEach(r=>{const m=r.dataset.plugin.includes(q);r.classList.toggle('hidden',!m);if(m)v++;});
      ce.textContent=q?v+' result'+(v!==1?'s':''):'';
      nr.style.display=(v===0&&q)?'block':'none';
    }"""

    SEARCH=lambda si,ti,ci,ni: (
        f"<div class='sb'>"
        f"<svg width='16' height='16' viewBox='0 0 24 24' fill='none' stroke='currentColor' stroke-width='2'><circle cx='11' cy='11' r='8'/><path d='m21 21-4.35-4.35'/></svg>"
        f"<input type='text' id='{si}' placeholder='Search plugin…' oninput=\"filterTable('{si}','{ti}','{ci}','{ni}')\">"
        f"<span class='sc' id='{ci}'></span></div>"
    )

    html=(
        f"<!DOCTYPE html><html lang='en'><head>"
        f"<meta charset='UTF-8'><meta name='viewport' content='width=device-width,initial-scale=1'>"
        f"<title>SaveTokens4Claude — Dashboard</title>"
        f"<script src='https://cdn.plot.ly/plotly-2.32.0.min.js'></script>"
        f"<link rel='preconnect' href='https://fonts.googleapis.com'>"
        f"<link href='https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@300;400;600;700&family=Space+Grotesk:wght@400;600;700&display=swap' rel='stylesheet'>"
        f"<style>{CSS}</style></head><body>"
        f"<header><div class='logo'>⚡</div><h1>Save<span>Tokens</span>4Claude</h1>"
        f"<div class='subtitle'>Generated on {generated_at}</div></header>"
        f"<main>"
        f"<p class='sec'>Overview</p>"
        f"<div class='kpi-grid'>"
        f"<div class='kpi'><label>Total Tokens</label><div class='val'>{total_tokens:,}</div></div>"
        f"<div class='kpi grn'><label>Session Tokens (24h)</label><div class='val'>{session_tokens:,}</div></div>"
        f"<div class='kpi'><label>Tracked Calls</label><div class='val'>{total_calls:,}</div></div>"
        f"<div class='kpi alt'><label>Estimated Cost</label><div class='val'>${total_cost:.4f}<span class='unit'>USD</span></div></div>"
        f"<div class='kpi'><label>Active Plugins</label><div class='val'>{unique_plugins}<span class='unit'>/ {installed_cnt}</span></div></div>"
        f"<div class='kpi'><label>Avg Duration</label><div class='val'>{_fmt_ms(avg_dur_ms)}</div></div>"
        f"</div>"
        f"<p class='sec'>Charts</p>"
        f"<div class='chart-grid'>"
        f"<div class='cc cw'>{html_bar}</div>"
        f"<div class='cc'>{html_donut}</div>"
        f"<div class='cc'>{html_calls}</div>"
        f"<div class='cc cw'>{html_line}</div>"
        f"</div>"
        f"<p class='sec'>Detailed Usage by Plugin</p>"
        f"{SEARCH('statsSearch','statsTable','statsCount','statsNR')}"
        f"<div class='tw'>{stats_table}<div class='nr' id='statsNR'>No plugins match your search.</div></div>"
        f"<p class='sec'>Installed Plugins ({installed_cnt})</p>"
        f"{SEARCH('instSearch','instTable','instCount','instNR')}"
        f"<div class='tw'>{inst_table}<div class='nr' id='instNR'>No plugins match your search.</div></div>"
        f"</main>"
        f"<footer><p>SaveTokens4Claude &mdash; auto-generated &bull; "
        f"<a href='https://github.com/BRUNEXX13/savetokens4claude' target='_blank'>github.com/BRUNEXX13/savetokens4claude</a></p></footer>"
        f"<script>{JS}</script>"
        f"</body></html>"
    )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(html, encoding="utf-8")
    return output_path
