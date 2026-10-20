"""Small, safe Markdown → HTML converter for chat bubbles (no external links are loaded).

Supports fenced code blocks (with a copy link), inline code, bold, italic,
headings, bullet/numbered lists, block quotes and links (shown, not fetched).
"""
from __future__ import annotations

import html
import re

_FENCE = re.compile(r"```[ \t]*([\w+#.-]*)[^\n]*\n(.*?)(?:```|\Z)", re.S)


def split_code_blocks(text: str) -> list[tuple[str, str, str]]:
    """Return a list of (kind, lang, content) where kind is 'text' or 'code'."""
    out, pos = [], 0
    for m in _FENCE.finditer(text):
        if m.start() > pos:
            out.append(("text", "", text[pos:m.start()]))
        out.append(("code", m.group(1) or "", m.group(2).rstrip("\n")))
        pos = m.end()
    if pos < len(text):
        out.append(("text", "", text[pos:]))
    return out


def _inline(s: str) -> str:
    s = html.escape(s, quote=False)
    codes: list[str] = []

    def keep(m):
        codes.append(m.group(1))
        return f"\x00{len(codes) - 1}\x00"
    s = re.sub(r"`([^`\n]+)`", keep, s)
    s = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", s)
    s = re.sub(r"(?<![\w*])\*(?!\s)(.+?)(?<!\s)\*(?![\w*])", r"<i>\1</i>", s)
    s = re.sub(r"(?<![\w_])_(?!\s)(.+?)(?<!\s)_(?![\w_])", r"<i>\1</i>", s)
    s = re.sub(r"\[([^\]]+)\]\((https?://[^)\s]+)\)", r'<a href="\2">\1</a>', s)
    s = re.sub(r"\x00(\d+)\x00", lambda m: f'<code class="ic">{codes[int(m.group(1))]}</code>', s)
    return s


def _text_block(text: str) -> str:
    lines = text.split("\n")
    out, list_tag = [], None
    para: list[str] = []

    def flush_para():
        if para:
            out.append("<p>" + "<br>".join(_inline(p) for p in para) + "</p>")
            para.clear()

    def close_list():
        nonlocal list_tag
        if list_tag:
            out.append(f"</{list_tag}>")
            list_tag = None

    for line in lines:
        st = line.strip()
        if not st:
            flush_para()
            close_list()
            continue
        h = re.match(r"(#{1,4})\s+(.*)", st)
        ul = re.match(r"[-*•]\s+(.*)", st)
        ol = re.match(r"\d+[.)]\s+(.*)", st)
        bq = re.match(r">\s?(.*)", st)
        if h:
            flush_para(); close_list()
            lvl = min(4, len(h.group(1)) + 2)
            out.append(f"<h{lvl}>{_inline(h.group(2))}</h{lvl}>")
        elif ul or ol:
            flush_para()
            tag = "ul" if ul else "ol"
            if list_tag != tag:
                close_list()
                out.append(f"<{tag}>")
                list_tag = tag
            out.append(f"<li>{_inline((ul or ol).group(1))}</li>")
        elif bq:
            flush_para(); close_list()
            out.append(f"<blockquote>{_inline(bq.group(1))}</blockquote>")
        else:
            close_list()
            para.append(st)
    flush_para()
    close_list()
    return "".join(out)


def to_html(text: str, code_start_index: int = 0, copy_label: str = "Copy") -> tuple[str, list[str]]:
    """Convert Markdown to HTML. Returns (html, code_blocks). Copy links use href 'copy:<index>'."""
    parts, codes = [], []
    for kind, lang, content in split_code_blocks(text):
        if kind == "text":
            parts.append(_text_block(content))
        else:
            idx = code_start_index + len(codes)
            codes.append(content)
            label = html.escape(lang or "code")
            parts.append(
                f'<table class="code" width="100%" cellspacing="0" cellpadding="8"><tr><td class="codehead">'
                f'<span class="lang">{label}</span> &nbsp; <a class="copy" href="copy:{idx}">⧉ {copy_label}</a>'
                f'</td></tr><tr><td class="codebody"><pre>{html.escape(content)}</pre></td></tr></table>')
    return "".join(parts), codes
