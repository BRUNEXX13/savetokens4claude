"""
tracker.py — Token counting and usage persistence layer.

Handles:
  - Counting tokens using tiktoken (cl100k_base encoding)
  - Loading / saving usage records to ~/.mcp-tracker/usage.json
  - Estimating USD cost based on approximate per-token pricing
"""
import json
from pathlib import Path
from datetime import datetime
from typing import Any

import tiktoken

# ── Storage paths ──────────────────────────────────────────────────────────────
DATA_DIR   = Path.home() / ".mcp-tracker"
USAGE_FILE = DATA_DIR / "usage.json"

# ── Pricing (approximate — adjust to your actual model) ───────────────────────
INPUT_COST_PER_1K  = 0.003   # USD per 1 000 input tokens
OUTPUT_COST_PER_1K = 0.015   # USD per 1 000 output tokens


def _get_encoding() -> tiktoken.Encoding:
    """Return the cl100k_base encoding (compatible with Claude / GPT-4 family)."""
    return tiktoken.get_encoding("cl100k_base")


def count_tokens(text: str) -> int:
    """Return the number of tokens in *text*."""
    return len(_get_encoding().encode(str(text)))


def load_usage() -> dict:
    """Load persisted usage data, returning an empty structure if not found."""
    if USAGE_FILE.exists():
        with open(USAGE_FILE, encoding="utf-8") as f:
            return json.load(f)
    return {"sessions": []}


def save_usage(data: dict) -> None:
    """Persist *data* to disk, creating the directory if necessary."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with open(USAGE_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def estimate_cost(input_tokens: int, output_tokens: int) -> float:
    """Return the estimated USD cost for the given token counts."""
    return (
        (input_tokens  / 1_000) * INPUT_COST_PER_1K
        + (output_tokens / 1_000) * OUTPUT_COST_PER_1K
    )


def ensure_plugin_meta(plugin_name: str) -> None:
    """Record first-seen (install) date for a plugin if not already stored."""
    data = load_usage()
    meta = data.setdefault("plugin_meta", {})
    if plugin_name not in meta:
        meta[plugin_name] = {
            "first_seen": datetime.now().isoformat(),
        }
        save_usage(data)


def log_tool_call(
    plugin_name: str,
    tool_name: str,
    input_data: Any,
    output: str,
    duration_ms: float,
) -> dict:
    """
    Persist one tool-call record and return it.

    Parameters
    ----------
    plugin_name : str
        Name of the MCP server (e.g. "github-mcp").
    tool_name : str
        Name of the specific tool that was invoked.
    input_data : Any
        The arguments / payload sent to the tool (will be JSON-serialised).
    output : str
        The raw text response returned by the tool.
    duration_ms : float
        Wall-clock execution time in milliseconds.

    Returns
    -------
    dict
        The newly created usage record.
    """
    ensure_plugin_meta(plugin_name)
    input_tokens  = count_tokens(json.dumps(input_data, ensure_ascii=False))
    output_tokens = count_tokens(output)
    cost_usd      = estimate_cost(input_tokens, output_tokens)

    entry = {
        "timestamp":     datetime.now().isoformat(),
        "plugin":        plugin_name,
        "tool":          tool_name,
        "input_tokens":  input_tokens,
        "output_tokens": output_tokens,
        "total_tokens":  input_tokens + output_tokens,
        "duration_ms":   round(duration_ms, 2),
        "cost_usd":      round(cost_usd, 6),
    }

    data = load_usage()
    data["sessions"].append(entry)
    save_usage(data)
    return entry


def reset_usage() -> None:
    """Erase all usage records (irreversible)."""
    save_usage({"sessions": []})
