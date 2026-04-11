"""
markdown_lite.py - Tiny in-house markdown -> HTML converter.

This is NOT a general-purpose markdown parser. It handles only the
specific patterns that core/report.py's executive_summary.md uses:

  - # H1, ## H2, ### H3 headers
  - **bold** and *italic*
  - `inline code`
  - | col | col | tables (with separator row | --- | --- |)
  - - list items / * list items
  - blank lines as paragraph breaks
  - emoji pass-through (HTML supports them natively)
  - --- horizontal rules

Anything more complex (nested lists, code fences, footnotes, links with
titles, HTML embedding) is intentionally not supported. If we need real
markdown rendering later, swap this for python-markdown — it's a simple
function call replacement.

The output is HTML wrapped with cyberpunk-themed CSS classes so it
inherits the rest of the theme automatically.
"""

import html
import re
from typing import List


# Inline patterns — applied after block-level parsing
_INLINE_PATTERNS = [
    # Bold: **text** or __text__
    (re.compile(r"\*\*(.+?)\*\*"), r"<strong>\1</strong>"),
    (re.compile(r"__(.+?)__"), r"<strong>\1</strong>"),
    # Italic: *text* or _text_ (but not adjacent to letters — avoid matching snake_case)
    (re.compile(r"(?<![a-zA-Z0-9])\*([^*\n]+?)\*(?![a-zA-Z0-9])"), r"<em>\1</em>"),
    (re.compile(r"(?<![a-zA-Z0-9])_([^_\n]+?)_(?![a-zA-Z0-9])"), r"<em>\1</em>"),
    # Inline code: `text`
    (re.compile(r"`([^`\n]+?)`"), r"<code>\1</code>"),
]


def _apply_inline(text: str) -> str:
    """Apply inline formatting (bold, italic, code) to a single text string."""
    for pattern, replacement in _INLINE_PATTERNS:
        text = pattern.sub(replacement, text)
    return text


def _escape_then_inline(text: str) -> str:
    """
    HTML-escape text first, then apply inline markdown.

    The order matters: we escape first so user content is safe, then we
    apply markdown which inserts <strong>, <em>, <code> tags. The
    markdown patterns operate on the escaped text, which is fine because
    none of the patterns contain HTML special characters as delimiters
    (they use *, _, `).
    """
    escaped = html.escape(text)
    return _apply_inline(escaped)


def render_markdown(md: str) -> str:
    """
    Convert markdown text to HTML.

    Handles only the patterns the executive_summary.md uses. Output is
    HTML with cyberpunk-themed class names where appropriate.

    Args:
        md: Markdown source text

    Returns:
        HTML string (no surrounding <html> or <body> tags)
    """
    if not md:
        return ""

    lines = md.split("\n")
    out: List[str] = []

    i = 0
    in_paragraph = False
    in_list = False

    def close_paragraph():
        nonlocal in_paragraph
        if in_paragraph:
            out.append("</p>")
            in_paragraph = False

    def close_list():
        nonlocal in_list
        if in_list:
            out.append("</ul>")
            in_list = False

    while i < len(lines):
        line = lines[i]
        stripped = line.strip()

        # Blank line — close any open paragraph or list
        if not stripped:
            close_paragraph()
            close_list()
            i += 1
            continue

        # Horizontal rule
        if stripped in ("---", "***", "___"):
            close_paragraph()
            close_list()
            out.append('<hr class="cp-hr">')
            i += 1
            continue

        # Headers
        if stripped.startswith("# "):
            close_paragraph()
            close_list()
            out.append(f'<h1 class="cp-md-h1">{_escape_then_inline(stripped[2:])}</h1>')
            i += 1
            continue
        if stripped.startswith("## "):
            close_paragraph()
            close_list()
            out.append(f'<h2 class="cp-md-h2">{_escape_then_inline(stripped[3:])}</h2>')
            i += 1
            continue
        if stripped.startswith("### "):
            close_paragraph()
            close_list()
            out.append(f'<h3 class="cp-md-h3">{_escape_then_inline(stripped[4:])}</h3>')
            i += 1
            continue

        # Tables: must start with `|` and have a separator row beneath
        if stripped.startswith("|") and i + 1 < len(lines):
            next_line = lines[i + 1].strip()
            # Separator row: | --- | --- | (cells contain only -, :, |, spaces)
            if next_line.startswith("|") and re.match(r"^\|[\s\-:|]+\|$", next_line):
                close_paragraph()
                close_list()
                # Collect all consecutive table rows
                header_cells = [c.strip() for c in stripped.strip("|").split("|")]
                rows: List[List[str]] = []
                j = i + 2  # skip header and separator
                while j < len(lines) and lines[j].strip().startswith("|"):
                    cells = [c.strip() for c in lines[j].strip().strip("|").split("|")]
                    rows.append(cells)
                    j += 1
                out.append('<table class="cp-table cp-md-table">')
                out.append("<tr>")
                for h in header_cells:
                    out.append(f"<th>{_escape_then_inline(h)}</th>")
                out.append("</tr>")
                for row in rows:
                    out.append("<tr>")
                    for cell in row:
                        out.append(f"<td>{_escape_then_inline(cell)}</td>")
                    out.append("</tr>")
                out.append("</table>")
                i = j
                continue

        # List items: - text  or  * text
        if stripped.startswith("- ") or stripped.startswith("* "):
            close_paragraph()
            if not in_list:
                out.append('<ul class="cp-md-list">')
                in_list = True
            content = stripped[2:]
            out.append(f"<li>{_escape_then_inline(content)}</li>")
            i += 1
            continue

        # Plain paragraph line — accumulate into current paragraph
        close_list()
        if not in_paragraph:
            out.append('<p class="cp-md-p">')
            in_paragraph = True
        else:
            out.append("<br>")
        out.append(_escape_then_inline(stripped))
        i += 1

    close_paragraph()
    close_list()

    return "\n".join(out)
