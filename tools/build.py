#!/usr/bin/env python3
"""Render handbook/chapters/*.md into one self-contained HTML handbook.

Usage:  python3 tools/build.py
Output: handbook/build/handbook.html   (publish this file as the Artifact)

Markdown conventions understood by this build
---------------------------------------------
Front matter (required, first lines of every chapter file):

    ---
    part: I
    part_title: Foundations
    number: 01
    title: Introduction to Linux
    tagline: One line under the chapter title.
    source: PDF p28-38
    minutes: 40
    ---

Callouts use GitHub alert syntax so the same file renders correctly on GitHub
and imports readably into Notion:

    > [!TIP]
    > Body markdown, including lists and code.

Recognised kinds: NOTE INFO TIP WARNING DANGER MEMORY INTERVIEW PROD MISTAKE EXAM

Fenced blocks:
    ```bash title="Create a VM"      -> code panel with a caption
    ```console                        -> terminal transcript panel (always dark)
    ```mermaid                        -> native Artifact mermaid rendering
    ```diagram                        -> monospace ASCII/box diagram panel
"""
from __future__ import annotations

import html
import pathlib
import re
import sys

import markdown
from pygments import highlight
from pygments.formatters import HtmlFormatter
from pygments.lexers import get_lexer_by_name
from pygments.util import ClassNotFound

ROOT = pathlib.Path(__file__).resolve().parent.parent
CHAPTERS = ROOT / "chapters"
ASSETS = ROOT / "assets"
BUILD = ROOT / "build"

CALLOUTS = {
    "NOTE": ("Note", "note"),
    "INFO": ("Background", "info"),
    "TIP": ("Tip", "tip"),
    "WARNING": ("Careful", "warn"),
    "DANGER": ("Destructive", "danger"),
    "MEMORY": ("Memory hook", "memory"),
    "INTERVIEW": ("Interview", "interview"),
    "PROD": ("In production", "prod"),
    "MISTAKE": ("Common mistake", "mistake"),
    "EXAM": ("Exam watch", "exam"),
}

FENCE_RE = re.compile(r"^```([^\n`]*)\n(.*?)^```[ \t]*$", re.S | re.M)
ALERT_RE = re.compile(
    r"(?:^>[ \t]*\[!(?P<kind>[A-Z]+)\][ \t]*\n(?P<body>(?:^>.*\n?)*))", re.M
)
FM_RE = re.compile(r"^---\n(.*?)\n---\n", re.S)


# --------------------------------------------------------------------------- #
# fenced blocks
# --------------------------------------------------------------------------- #
def parse_info(info: str) -> tuple[str, str]:
    """'bash title="Do a thing"' -> ('bash', 'Do a thing')"""
    info = info.strip()
    m = re.search(r'title="([^"]*)"', info)
    title = m.group(1) if m else ""
    lang = re.sub(r'title="[^"]*"', "", info).strip().split()
    return (lang[0] if lang else "text"), title


def render_code(lang: str, title: str, body: str) -> str:
    body = body.rstrip("\n")

    if lang == "mermaid":
        return f'<div class="fig fig-mermaid"><pre class="mermaid">{html.escape(body)}</pre></div>'

    if lang == "diagram":
        cap = f'<figcaption class="fig-cap">{html.escape(title)}</figcaption>' if title else ""
        return (
            f'<figure class="fig fig-diagram">{cap}'
            f'<div class="scroll"><pre class="ascii">{html.escape(body)}</pre></div></figure>'
        )

    is_term = lang in ("console", "shell-session", "terminal")
    lex_name = "console" if is_term else lang
    try:
        lexer = get_lexer_by_name(lex_name, stripall=False)
        inner = highlight(body, lexer, HtmlFormatter(nowrap=True))
    except ClassNotFound:
        inner = html.escape(body)

    label = title or {"console": "terminal", "text": "", "diagram": ""}.get(lang, lang)
    cls = "fig-term" if is_term else "fig-code"
    cap = (
        f'<figcaption class="fig-cap"><span class="fig-lang">{html.escape(label)}</span>'
        f'<button class="copy" type="button" aria-label="Copy to clipboard">copy</button></figcaption>'
        if label
        else '<figcaption class="fig-cap fig-cap-bare">'
        f'<button class="copy" type="button" aria-label="Copy to clipboard">copy</button></figcaption>'
    )
    return (
        f'<figure class="fig {cls}" data-lang="{html.escape(lang)}">{cap}'
        f'<div class="scroll"><pre><code>{inner}</code></pre></div></figure>'
    )


# --------------------------------------------------------------------------- #
# conversion
# --------------------------------------------------------------------------- #
def make_md() -> markdown.Markdown:
    return markdown.Markdown(
        extensions=[
            "tables",
            "attr_list",
            "def_list",
            "sane_lists",
            "footnotes",
            "md_in_html",
            "smarty",
            "abbr",
        ],
        extension_configs={
            "smarty": {"substitutions": {"left-single-quote": "‘", "right-single-quote": "’"}},
            "footnotes": {"UNIQUE_IDS": True},
        },
    )


def convert_alerts(text: str, md: markdown.Markdown) -> str:
    def sub(m: re.Match) -> str:
        kind = m.group("kind").upper()
        label, css = CALLOUTS.get(kind, (kind.title(), "note"))
        body = re.sub(r"^>[ \t]?", "", m.group("body"), flags=re.M)
        inner = md.reset().convert(body.strip())
        return (
            f'<aside class="cal cal-{css}">'
            f'<p class="cal-label"><span class="cal-mark" aria-hidden="true"></span>{label}</p>'
            f'{inner}</aside>\n\n'
        )

    return ALERT_RE.sub(sub, text)


SLUG_BAD = re.compile(r"[^a-z0-9]+")


def slug(text: str) -> str:
    text = re.sub(r"<[^>]+>", "", text)
    text = html.unescape(text).lower().replace("+", "-plus")
    return SLUG_BAD.sub("-", text).strip("-") or "section"


def render_chapter(path: pathlib.Path, md: markdown.Markdown) -> dict:
    raw = path.read_text()
    fm_match = FM_RE.match(raw)
    if not fm_match:
        sys.exit(f"{path.name}: missing front matter")
    meta: dict[str, str] = {}
    for line in fm_match.group(1).splitlines():
        if ":" in line:
            k, v = line.split(":", 1)
            meta[k.strip()] = v.strip()
    body = raw[fm_match.end():]

    # 1. pull fenced blocks out so markdown never touches them
    stash: list[str] = []

    def stash_fence(m: re.Match) -> str:
        lang, title = parse_info(m.group(1))
        stash.append(render_code(lang, title, m.group(2)))
        return f"\n\x00FENCE{len(stash) - 1}\x00\n"

    body = FENCE_RE.sub(stash_fence, body)

    # 2. callouts (their inner markdown is converted with a nested pass)
    body = convert_alerts(body, make_md())

    # 3. main markdown pass
    out = md.reset().convert(body)

    # 4. heading ids + anchors, collect the on-this-page outline
    outline: list[dict] = []
    seen: dict[str, int] = {}

    def heading(m: re.Match) -> str:
        level, attrs, inner = int(m.group(1)), m.group(2), m.group(3)
        base = slug(inner)
        seen[base] = seen.get(base, 0) + 1
        hid = base if seen[base] == 1 else f"{base}-{seen[base]}"
        if level in (2, 3):
            outline.append(
                {"id": hid, "text": html.unescape(re.sub(r"<[^>]+>", "", inner)), "level": level}
            )
        anchor = f'<a class="hash" href="#{meta["number"]}/{hid}" aria-label="Link to this section">#</a>'
        return f'<h{level} id="{hid}"{attrs}>{inner}{anchor}</h{level}>'

    out = re.sub(r"<h([2-4])([^>]*)>(.*?)</h\1>", heading, out, flags=re.S)

    # 5. tables and wide blocks scroll inside their own container
    out = re.sub(r"<table>", '<div class="scroll tw"><table>', out)
    out = re.sub(r"</table>", "</table></div>", out)

    # 6. put the fenced blocks back
    def unstash(m: re.Match) -> str:
        return stash[int(m.group(1))]

    out = re.sub(r"<p>\x00FENCE(\d+)\x00</p>", unstash, out)
    out = re.sub(r"\x00FENCE(\d+)\x00", unstash, out)

    return {"meta": meta, "html": out, "outline": outline}


# --------------------------------------------------------------------------- #
# page shell
# --------------------------------------------------------------------------- #
def build_nav(chapters: list[dict]) -> str:
    parts: list[tuple[str, str, list[dict]]] = []
    for ch in chapters:
        key = (ch["meta"].get("part", ""), ch["meta"].get("part_title", ""))
        if not parts or (parts[-1][0], parts[-1][1]) != key:
            parts.append((key[0], key[1], []))
        parts[-1][2].append(ch)

    rows = []
    for pnum, ptitle, chs in parts:
        rows.append(
            f'<li class="nav-part"><span class="nav-part-num">{html.escape(pnum)}</span>'
            f'<span class="nav-part-title">{html.escape(ptitle)}</span></li>'
        )
        for ch in chs:
            n = ch["meta"]["number"]
            rows.append(
                f'<li class="nav-ch"><a href="#{n}" data-ch="{n}">'
                f'<span class="nav-num">{n}</span>'
                f'<span class="nav-title">{html.escape(ch["meta"]["title"])}</span></a></li>'
            )
    return "\n".join(rows)


def build_articles(chapters: list[dict]) -> str:
    out = []
    for i, ch in enumerate(chapters):
        m = ch["meta"]
        prev_ch = chapters[i - 1] if i else None
        next_ch = chapters[i + 1] if i + 1 < len(chapters) else None
        plate = [
            ("chapter", m["number"]),
            ("part", f'{m.get("part", "")} · {m.get("part_title", "")}'.strip(" ·")),
        ]
        if m.get("source"):
            plate.append(("source", m["source"]))
        if m.get("minutes"):
            plate.append(("read", f'{m["minutes"]} min'))
        plate_html = "".join(
            f'<div class="plate-cell"><dt>{html.escape(k)}</dt><dd>{html.escape(v)}</dd></div>'
            for k, v in plate
        )
        foot = []
        if prev_ch:
            foot.append(
                f'<a class="pager pager-prev" href="#{prev_ch["meta"]["number"]}">'
                f'<span class="pager-dir">Previous</span>'
                f'<span class="pager-name">{html.escape(prev_ch["meta"]["title"])}</span></a>'
            )
        else:
            foot.append('<span class="pager pager-empty"></span>')
        if next_ch:
            foot.append(
                f'<a class="pager pager-next" href="#{next_ch["meta"]["number"]}">'
                f'<span class="pager-dir">Next</span>'
                f'<span class="pager-name">{html.escape(next_ch["meta"]["title"])}</span></a>'
            )
        else:
            foot.append('<span class="pager pager-empty"></span>')

        tagline = (
            f'<p class="ch-tagline">{html.escape(m["tagline"])}</p>' if m.get("tagline") else ""
        )
        out.append(
            f'<article class="ch" id="ch-{m["number"]}" data-ch="{m["number"]}" hidden>'
            f'<header class="ch-head">'
            f'<p class="eyebrow">{html.escape(m.get("part", ""))} — {html.escape(m.get("part_title", ""))}</p>'
            f'<h1><span class="ch-num" aria-hidden="true">{m["number"]}</span>'
            f'{html.escape(m["title"])}</h1>{tagline}'
            f'<dl class="plate">{plate_html}</dl></header>'
            f'<div class="prose">{ch["html"]}</div>'
            f'<nav class="ch-foot">{"".join(foot)}</nav>'
            f"</article>"
        )
    return "\n".join(out)


def build_rails(chapters: list[dict]) -> str:
    out = []
    for ch in chapters:
        items = "".join(
            f'<li class="lvl{h["level"]}"><a href="#{ch["meta"]["number"]}/{h["id"]}">'
            f'{html.escape(h["text"])}</a></li>'
            for h in ch["outline"]
        )
        out.append(
            f'<div class="rail-set" data-ch="{ch["meta"]["number"]}" hidden>'
            f'<p class="rail-label">On this page</p><ul class="rail-list">{items}</ul></div>'
        )
    return "\n".join(out)


def main() -> None:
    files = sorted(CHAPTERS.glob("*.md"))
    if not files:
        sys.exit("no chapters found in handbook/chapters/")
    md = make_md()
    chapters = [render_chapter(f, md) for f in files]

    css = (ASSETS / "fonts.css").read_text() + "\n" + (ASSETS / "handbook.css").read_text()
    js = (ASSETS / "handbook.js").read_text()

    first = chapters[0]["meta"]["number"]
    page = f"""<meta charset="utf-8">
<title>The Linux, Virtualization &amp; DevOps Handbook</title>
<meta name="description" content="A rebuilt, taught-from-scratch handbook covering Linux, virtualization, system administration and Docker.">
<style>
{css}
</style>
<div class="app">
  <a class="skip" href="#main">Skip to content</a>

  <header class="topbar">
    <button class="icon-btn nav-toggle" type="button" aria-label="Toggle chapter list" aria-expanded="false">
      <span class="bars" aria-hidden="true"></span>
    </button>
    <a class="brand" href="#{first}">
      <span class="brand-mark" aria-hidden="true">::</span>
      <span class="brand-text">Linux &amp; DevOps <em>Handbook</em></span>
    </a>
    <div class="search">
      <label class="sr" for="q">Search the handbook</label>
      <input id="q" type="search" placeholder="Search commands, concepts, flags" autocomplete="off" spellcheck="false">
      <kbd class="search-kbd">/</kbd>
      <div class="results" hidden></div>
    </div>
    <button class="icon-btn theme-btn" type="button" aria-label="Switch colour theme">
      <span class="theme-dot" aria-hidden="true"></span>
    </button>
  </header>

  <div class="progress" aria-hidden="true"><span></span></div>

  <nav class="nav" aria-label="Chapters">
    <ol class="nav-list">
{build_nav(chapters)}
    </ol>
  </nav>

  <main class="main" id="main">
{build_articles(chapters)}
  </main>

  <aside class="rail" aria-label="Section outline">
{build_rails(chapters)}
  </aside>

  <div class="scrim" hidden></div>
</div>
<script src="https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.min.js"></script>
<script>
window.getMermaidTheme = function() {{
  const attr = document.documentElement.getAttribute('data-theme');
  if (attr === 'dark') return 'dark';
  if (attr === 'light') return 'default';
  return matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'default';
}};
mermaid.initialize({{
  startOnLoad: true,
  theme: window.getMermaidTheme(),
  securityLevel: 'loose',
  flowchart: {{ useMaxWidth: true }},
  sequence: {{ useMaxWidth: true }},
  mindmap: {{ useMaxWidth: true }}
}});
{js}
</script>
"""
    BUILD.mkdir(exist_ok=True)
    dest = BUILD / "handbook.html"
    dest.write_text(page)
    words = sum(len(re.sub(r"<[^>]+>", " ", c["html"]).split()) for c in chapters)
    print(f"chapters : {len(chapters)}")
    print(f"words    : {words:,}")
    print(f"output   : {dest}  ({dest.stat().st_size/1024:.0f} KB)")


if __name__ == "__main__":
    main()
