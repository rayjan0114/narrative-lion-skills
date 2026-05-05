"""Output formatters for NL CLI."""

from __future__ import annotations

import json


def as_json(data: object) -> str:
    return json.dumps(data, indent=2, ensure_ascii=False)


def table(rows: list[dict], columns: list[tuple[str, str]], title: str | None = None) -> str:
    """Format a list of dicts as an aligned text table.

    columns: list of (key, header_label) tuples.
    """
    if not rows:
        return "(no results)"

    headers = [col[1] for col in columns]
    keys = [col[0] for col in columns]

    col_widths = [len(h) for h in headers]
    str_rows: list[list[str]] = []
    for row in rows:
        str_row = [str(row.get(k, "") or "") for k in keys]
        str_rows.append(str_row)
        for i, val in enumerate(str_row):
            col_widths[i] = max(col_widths[i], len(val))

    lines: list[str] = []
    if title:
        lines.append(title)
        lines.append("")

    header_line = "  ".join(h.ljust(col_widths[i]) for i, h in enumerate(headers))
    lines.append(header_line)
    lines.append("  ".join("-" * w for w in col_widths))

    for str_row in str_rows:
        lines.append("  ".join(val.ljust(col_widths[i]) for i, val in enumerate(str_row)))

    return "\n".join(lines)


def kv(pairs: list[tuple[str, str]], title: str | None = None) -> str:
    """Format key-value pairs aligned."""
    if not pairs:
        return ""
    max_key = max(len(k) for k, _ in pairs)
    lines: list[str] = []
    if title:
        lines.append(title)
        lines.append("")
    for k, v in pairs:
        lines.append(f"  {k.ljust(max_key)}  {v}")
    return "\n".join(lines)


def status_bar(counts: dict, total: int) -> str:
    """Compact status summary like: 3 done, 2 ready, 1 blocked / 6 total."""
    parts = []
    for key in ["done", "ready", "review", "generating", "assetPrep", "notStarted", "blocked"]:
        n = counts.get(key, 0)
        if n > 0:
            label = {
                "done": "done",
                "ready": "ready",
                "review": "review",
                "generating": "generating",
                "assetPrep": "asset_prep",
                "notStarted": "not_started",
                "blocked": "blocked",
            }.get(key, key)
            parts.append(f"{n} {label}")
    return f"{', '.join(parts)} / {total} total"
