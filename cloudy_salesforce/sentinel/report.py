"""Static HTML report for a Schema Sentinel change set. No network."""

from __future__ import annotations

import html
from pathlib import Path

from .types import Change


def _cell(value: object) -> str:
    """Escape one table cell. ``None`` renders as an em dash."""
    if value is None:
        return "—"
    return html.escape(str(value), quote=True)


def render_html_report(
    changes: list[Change],
    *,
    old_label: str,
    new_label: str,
) -> str:
    """Render a standalone HTML page for a change set.

    Args:
        changes: Diff result, already filtered.
        old_label: Baseline path or alias shown in the header.
        new_label: Comparison path or alias shown in the header.

    Returns:
        A complete HTML document as a string.
    """
    rows: list[str] = []
    for change in changes:
        rows.append(
            "<tr>"
            f"<td><code>{_cell(change.kind)}</code></td>"
            f"<td><code>{_cell(change.sobject)}</code></td>"
            f"<td><code>{_cell(change.field)}</code></td>"
            f"<td>{_cell(change.before)}</td>"
            f"<td>{_cell(change.after)}</td>"
            f"<td>{_cell(change.summary)}</td>"
            "</tr>"
        )
    body = (
        "\n".join(rows)
        if rows
        else '<tr><td colspan="6">No schema changes.</td></tr>'
    )
    title = (
        f"{len(changes)} Salesforce schema change(s)"
        if changes
        else "No schema changes"
    )
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8"/>
  <title>{html.escape(title, quote=True)}</title>
  <style>
    body {{ font-family: ui-sans-serif, system-ui, sans-serif; margin: 2rem; }}
    h1 {{ font-size: 1.25rem; }}
    p.meta {{ color: #444; }}
    table {{ border-collapse: collapse; width: 100%; }}
    th, td {{ border-bottom: 1px solid #ddd; padding: 0.4rem 0.6rem; text-align: left; vertical-align: top; }}
    th {{ font-size: 0.8rem; text-transform: uppercase; letter-spacing: 0.04em; }}
    code {{ font-size: 0.9em; }}
  </style>
</head>
<body>
  <h1>{html.escape(title)}</h1>
  <p class="meta">Baseline: <code>{_cell(old_label)}</code> · Comparison: <code>{_cell(new_label)}</code></p>
  <table>
    <thead>
      <tr>
        <th>Kind</th>
        <th>Object</th>
        <th>Field</th>
        <th>Before</th>
        <th>After</th>
        <th>Summary</th>
      </tr>
    </thead>
    <tbody>
      {body}
    </tbody>
  </table>
</body>
</html>
"""


def write_html_report(
    changes: list[Change],
    out_path: str,
    *,
    old_label: str,
    new_label: str,
) -> Path:
    """Write ``render_html_report`` to ``out_path`` and return the path."""
    path = Path(out_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        render_html_report(changes, old_label=old_label, new_label=new_label),
        encoding="utf-8",
    )
    return path
