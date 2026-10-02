#!/usr/bin/env python3
"""Build the nullstar static site into ./dist."""

from __future__ import annotations

import hashlib
import html
import json
import re
import shutil
from datetime import date, datetime
from pathlib import Path

SRC = Path(__file__).resolve().parent
ROOT = SRC.parent
CONTENT = ROOT / "content"
STATIC = SRC / "static"
DIST = ROOT / "dist"

MONTHS = (
    "jan",
    "feb",
    "mar",
    "apr",
    "may",
    "jun",
    "jul",
    "aug",
    "sep",
    "oct",
    "nov",
    "dec",
)
FOUNDER_FILES = (
    "founder.jpg",
    "founder.jpeg",
    "founder.png",
    "founder.webp",
)
NAV = (
    ("/", "home"),
    ("/worlds/", "worlds"),
    #("/tech/", "tech"),
    #("/news/", "news"),
    #("/about/", "about"),
)

SUN = """<svg class="sun" viewBox="0 0 80 80" aria-hidden="true">
<defs>
<linearGradient id="life-rainbow" x1="0%" y1="50%" x2="100%" y2="50%">
<stop offset="0%" stop-color="hsl(0 62% 82%)"/>
<stop offset="20%" stop-color="hsl(48 62% 82%)"/>
<stop offset="40%" stop-color="hsl(100 62% 82%)"/>
<stop offset="58%" stop-color="hsl(160 62% 82%)"/>
<stop offset="74%" stop-color="hsl(210 62% 82%)"/>
<stop offset="88%" stop-color="hsl(265 62% 82%)"/>
<stop offset="100%" stop-color="hsl(320 62% 82%)"/>
</linearGradient>
</defs>
<g class="rays">
  <line x1="40" y1="13" x2="40" y2="3"/>
  <line x1="53.5" y1="16.6" x2="58.5" y2="7.9"/>
  <line x1="63.4" y1="26.5" x2="72.1" y2="21.5"/>
  <line x1="67" y1="40" x2="77" y2="40"/>
  <line x1="63.4" y1="53.5" x2="72.1" y2="58.5"/>
  <line x1="53.5" y1="63.4" x2="58.5" y2="72.1"/>
  <line x1="40" y1="67" x2="40" y2="77"/>
  <line x1="26.5" y1="63.4" x2="21.5" y2="72.1"/>
  <line x1="16.6" y1="53.5" x2="7.9" y2="58.5"/>
  <line x1="13" y1="40" x2="3" y2="40"/>
  <line x1="16.6" y1="26.5" x2="7.9" y2="21.5"/>
  <line x1="26.5" y1="16.6" x2="21.5" y2="7.9"/>
</g>
<circle class="face" cx="40" cy="40" r="16"/>
<circle class="eye" cx="34.2" cy="37.2" r="1.15"/>
<circle class="eye" cx="45.8" cy="37.2" r="1.15"/>
<path class="smile" d="M33.2 43.2c2.1 3.4 11.5 3.4 13.6 0"/>
</svg>"""

_CODE = re.compile(r"`([^`]+)`")
_IMG = re.compile(r"!\[([^\]]*)\]\(([^)\s]+)\)")
_LINK = re.compile(r"\[([^\]]+)\]\(([^)\s]+)\)")
_BOLD = re.compile(r"\*\*([^*]+)\*\*")
_EM = re.compile(r"(?<!\*)\*([^*]+)\*(?!\*)")
_SLUG = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
_FENCE_LANG = re.compile(r"^[a-z0-9+-]+$")
_SCHEME = re.compile(r"^[a-zA-Z][a-zA-Z0-9+.-]*:")


class BuildError(Exception):
    """A content or template problem that should fail the build."""


def read_text(path: Path) -> str:
    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeError as exc:
        raise BuildError(f"{path.relative_to(ROOT)}: not valid utf-8") from exc
    if text.startswith("\ufeff"):
        text = text[1:]
    return text.replace("\r\n", "\n").replace("\r", "\n")


def safe_url(url: str) -> str | None:
    url = url.strip()
    if not url or url.startswith("//") or any(c in url for c in ' "\'<>'):
        return None
    if url.startswith(("#", "/")):
        return url
    if url.startswith(("http://", "https://", "mailto:")):
        return url
    if _SCHEME.match(url):
        return None
    return url


def render_inline(text: str) -> str:
    slots: list[str] = []

    def slot(fragment: str) -> str:
        slots.append(fragment)
        return f"\x00{len(slots) - 1}\x00"

    def stash_code(match: re.Match[str]) -> str:
        return slot(f"<code>{html.escape(match.group(1))}</code>")

    def stash_img(match: re.Match[str]) -> str:
        url = safe_url(match.group(2))
        if url is None:
            return match.group(0)
        alt = html.escape(match.group(1), quote=True)
        src = html.escape(url, quote=True)
        return slot(f'<img src="{src}" alt="{alt}">')

    def stash_link(match: re.Match[str]) -> str:
        url = safe_url(match.group(2))
        if url is None:
            return match.group(1)
        label = render_inline(match.group(1))
        href = html.escape(url, quote=True)
        extra = ""
        if url.startswith(("http://", "https://")):
            extra = ' rel="noopener noreferrer"'
        return slot(f'<a href="{href}"{extra}>{label}</a>')

    text = _CODE.sub(stash_code, text)
    text = _IMG.sub(stash_img, text)
    text = _LINK.sub(stash_link, text)
    text = html.escape(text)
    text = _BOLD.sub(r"<strong>\1</strong>", text)
    text = _EM.sub(r"<em>\1</em>", text)
    return re.sub(r"\x00(\d+)\x00", lambda match: slots[int(match.group(1))], text)


def is_block_start(line: str) -> bool:
    if line.startswith(("```", ">")):
        return True
    return bool(
        re.match(r"^#{1,6}\s+\S", line)
        or re.match(r"^[-*]\s+\S", line)
        or re.match(r"^\d+\.\s+\S", line)
        or re.match(r"^(-{3,}|\*{3,})\s*$", line)
    )


def render_markdown(src: str) -> str:
    lines = src.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    out: list[str] = []
    i = 0
    n = len(lines)
    while i < n:
        line = lines[i]
        if line.startswith("```"):
            lang = line[3:].strip()
            i += 1
            buf: list[str] = []
            while i < n and not lines[i].startswith("```"):
                buf.append(lines[i])
                i += 1
            if i >= n:
                raise BuildError("unclosed code fence")
            i += 1
            klass = f' class="language-{lang}"' if _FENCE_LANG.match(lang) else ""
            out.append(f"<pre><code{klass}>{html.escape(chr(10).join(buf))}</code></pre>")
            continue
        if re.match(r"^(-{3,}|\*{3,})\s*$", line):
            out.append("<hr>")
            i += 1
            continue
        heading = re.match(r"^(#{1,6})\s+(\S.*)$", line)
        if heading:
            level = min(len(heading.group(1)), 6)
            out.append(f"<h{level}>{render_inline(heading.group(2).strip())}</h{level}>")
            i += 1
            continue
        if line.startswith(">"):
            buf = []
            while i < n and lines[i].startswith(">"):
                buf.append(lines[i][1:].lstrip())
                i += 1
            out.append(f"<blockquote><p>{render_inline(' '.join(buf))}</p></blockquote>")
            continue
        bullet = re.match(r"^[-*]\s+(\S.*)$", line)
        if bullet:
            items = []
            while i < n and (item := re.match(r"^[-*]\s+(\S.*)$", lines[i])):
                items.append(item.group(1).strip())
                i += 1
            lis = "".join(f"<li>{render_inline(item)}</li>" for item in items)
            out.append(f"<ul>{lis}</ul>")
            continue
        numbered = re.match(r"^\d+\.\s+(\S.*)$", line)
        if numbered:
            items = []
            while i < n and (item := re.match(r"^\d+\.\s+(\S.*)$", lines[i])):
                items.append(item.group(1).strip())
                i += 1
            lis = "".join(f"<li>{render_inline(item)}</li>" for item in items)
            out.append(f"<ol>{lis}</ol>")
            continue
        if not line.strip():
            i += 1
            continue
        buf = [line.strip()]
        i += 1
        while i < n and lines[i].strip() and not is_block_start(lines[i]):
            buf.append(lines[i].strip())
            i += 1
        out.append(f"<p>{render_inline(' '.join(buf))}</p>")
    return "\n".join(out)


def split_front_matter(text: str, path: Path) -> tuple[dict[str, str], str]:
    label = path.relative_to(ROOT)
    if not text.startswith("---\n"):
        raise BuildError(f"{label}: missing front matter")
    end = text.find("\n---\n", 4)
    if end == -1:
        raise BuildError(f"{label}: unclosed front matter")
    meta: dict[str, str] = {}
    for line in text[4:end].splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        if ":" not in line:
            raise BuildError(f"{label}: bad front matter line: {line}")
        key, value = line.split(":", 1)
        meta[key.strip()] = value.strip().strip("\"'")
    body = text[end + 5 :]
    if body.startswith("\n"):
        body = body[1:]
    return meta, body


def parse_date(value: str, path: Path) -> date:
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError as exc:
        raise BuildError(
            f"{path.relative_to(ROOT)}: date must be YYYY-MM-DD"
        ) from exc


def format_date(day: date) -> str:
    return f"{day.day} {MONTHS[day.month - 1]} {day.year}"


def load_phrases() -> list[str]:
    path = CONTENT / "phrases.txt"
    if not path.is_file():
        raise BuildError("content/phrases.txt is missing")
    phrases = []
    for line in read_text(path).splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            phrases.append(line)
    if not phrases:
        raise BuildError("content/phrases.txt has no phrases")
    return phrases


def load_posts() -> list[dict[str, object]]:
    blog = ROOT / "blog"
    if not blog.is_dir():
        raise BuildError("blog/ is missing")
    posts = []
    slugs: set[str] = set()
    for path in sorted(p for p in blog.iterdir() if p.is_file() and p.suffix == ".md"):
        dated = re.match(r"^(\d{4}-\d{2}-\d{2})-(.+)\.md$", path.name)
        if dated:
            slug = dated.group(2)
            file_date = dated.group(1)
        else:
            slug = path.stem
            file_date = None
        if not _SLUG.match(slug):
            raise BuildError(f"{path.relative_to(ROOT)}: slug must be lowercase words")
        if slug in slugs:
            raise BuildError(f"duplicate news slug: {slug}")
        slugs.add(slug)
        meta, body = split_front_matter(read_text(path), path)
        title = meta.get("title", "").strip()
        if not title:
            raise BuildError(f"{path.relative_to(ROOT)}: missing title")
        if "date" not in meta:
            raise BuildError(f"{path.relative_to(ROOT)}: missing date")
        day = parse_date(meta["date"], path)
        if file_date and file_date != meta["date"]:
            raise BuildError(f"{path.relative_to(ROOT)}: filename date does not match")
        description = meta.get("description", "").strip() or excerpt(body)
        posts.append(
            {
                "title": title,
                "date": day,
                "slug": slug,
                "description": description,
                "html": render_markdown(body),
                "source": path.relative_to(ROOT).as_posix(),
            }
        )
    posts.sort(key=lambda post: (post["date"], post["slug"]), reverse=True)
    return posts


def excerpt(body: str, limit: int = 140) -> str:
    parts: list[str] = []
    for line in body.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith(("```", "#", ">", "- ", "* ")):
            if parts:
                break
            continue
        if re.match(r"^\d+\.\s+", stripped):
            if parts:
                break
            continue
        parts.append(stripped)
    text = re.sub(r"[`*\[\]]", "", " ".join(parts))
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip() + "…"


def find_founder() -> Path | None:
    found = [CONTENT / name for name in FOUNDER_FILES if (CONTENT / name).is_file()]
    if len(found) > 1:
        names = ", ".join(path.name for path in found)
        raise BuildError(f"keep a single portrait, found {names}")
    return found[0] if found else None


def asset_version(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()[:10]


def nav(current: str) -> str:
    links = []
    for href, label in NAV:
        here = current == href or (href != "/" and current.startswith(href))
        attr = ' aria-current="page"' if here else ""
        links.append(f'<a href="{href}"{attr}>{label}</a>')
    return "\n".join(links)


def page(
    *,
    title: str,
    description: str,
    current: str,
    main: str,
    css_version: str,
    body_class: str = "",
    scripts: str = "",
) -> str:
    body_attr = f' class="{body_class}"' if body_class else ""
    description_attr = html.escape(description, quote=True)
    title_text = html.escape(title)
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="theme-color" content="#000000">
<meta name="color-scheme" content="dark">
<meta name="description" content="{description_attr}">
<title>{title_text}</title>
<link rel="icon" href="/favicon.svg" type="image/svg+xml">
<link rel="stylesheet" href="/style.css?v={css_version}">
</head>
<body{body_attr}>
<a class="skip" href="#content">skip to content</a>
<header>
<a class="mark" href="/">nullstar</a>
<nav aria-label="pages">
{nav(current)}
</nav>
</header>
{main}
{scripts}</body>
</html>
"""


def write_page(dest: Path, text: str) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(text, encoding="utf-8")


def home_page(phrases: list[str], css_version: str) -> str:
    payload = (
        json.dumps(phrases, ensure_ascii=False)
        .replace("<", "\\u003c")
        .replace(">", "\\u003e")
        .replace("&", "\\u0026")
    )
    spoken = html.escape(". ".join(phrases))
    first = html.escape(phrases[0])
    main = f"""<main id="content" class="stage" tabindex="-1">
<div class="speaker">
{SUN}
<p class="visually-hidden">{spoken}.</p>
<p class="phrase" aria-hidden="true">{first}</p>
</div>
</main>
<footer class="life">
<canvas id="life" width="2" height="2" aria-hidden="true"></canvas>
<p class="visually-hidden">a game of life runs along the bottom.</p>
</footer>
"""
    life_version = asset_version(STATIC / "life.js")
    scripts = f"""<script id="phrases" type="application/json">{payload}</script>
<script src="/sun.js?v={css_version}"></script>
<script src="/life.js?v={life_version}"></script>
"""
    return page(
        title="nullstar.games",
        description=phrases[0],
        current="/",
        main=main,
        css_version=css_version,
        body_class="home",
        scripts=scripts,
    )


def tech_page(css_version: str, out: Path) -> str:
    path = CONTENT / "tech.md"
    if not path.is_file():
        raise BuildError("content/tech.md is missing")
    meta, body = split_front_matter(read_text(path), path)
    title = meta.get("title", "").strip() or "tech"
    media = CONTENT / "tech"
    pictures = {".svg", ".jpg", ".jpeg", ".png", ".webp", ".gif"}
    if media.is_dir():
        dest = out / "tech"
        dest.mkdir(parents=True, exist_ok=True)
        for file in sorted(media.iterdir()):
            if file.is_file() and file.suffix.lower() in pictures and not file.name.startswith("."):
                shutil.copyfile(file, dest / file.name)
    main = f"""<main id="content" class="page" tabindex="-1">
<h1>{html.escape(title)}</h1>
<div class="prose">
{render_markdown(body)}
</div>
</main>
"""
    return page(
        title=f"{title} · nullstar.games",
        description=excerpt(body) or "tech",
        current="/tech/",
        main=main,
        css_version=css_version,
    )


def worlds_page(css_version: str) -> str:
    main = """<main id="content" class="stage" tabindex="-1">
<h1 class="logic">LOGIC-13</h1>
<h2 class="logic-coming-soon">2027<br>
<h3 class="logic-coming-soon-2">for real friends</h3>
</main>
"""
    return page(
        title="worlds · nullstar.games",
        description="LOGIC-13",
        current="/worlds/",
        main=main,
        css_version=css_version,
        body_class="worlds",
    )


def news_index(posts: list[dict[str, object]], css_version: str) -> str:
    if posts:
        items = []
        for post in posts:
            day = post["date"]
            assert isinstance(day, date)
            items.append(
                "<li>"
                f'<time datetime="{day.isoformat()}">{format_date(day)}</time>'
                f'<a href="/news/{post["slug"]}/">{html.escape(str(post["title"]))}</a>'
                "</li>"
            )
        listing = f'<ul class="index">{"".join(items)}</ul>'
    else:
        listing = '<p class="quiet">nothing yet.</p>'
    main = f"""<main id="content" class="page" tabindex="-1">
<h1>news</h1>
{listing}
</main>
"""
    return page(
        title="news · nullstar.games",
        description="notes from nullstar.",
        current="/news/",
        main=main,
        css_version=css_version,
    )


def news_post(post: dict[str, object], css_version: str) -> str:
    day = post["date"]
    assert isinstance(day, date)
    title = str(post["title"])
    main = f"""<main id="content" class="page prose" tabindex="-1">
<p class="meta"><a href="/news/">news</a> · <time datetime="{day.isoformat()}">{format_date(day)}</time></p>
<h1>{html.escape(title)}</h1>
{post["html"]}
</main>
"""
    return page(
        title=f"{title} · nullstar.games",
        description=str(post["description"]),
        current=f'/news/{post["slug"]}/',
        main=main,
        css_version=css_version,
    )


def about_page(css_version: str, out: Path) -> str:
    path = CONTENT / "about.md"
    if not path.is_file():
        raise BuildError("content/about.md is missing")
    meta, body = split_front_matter(read_text(path), path)
    title = meta.get("title", "").strip() or "about"
    alt = meta.get("alt", "").strip()
    if not alt:
        raise BuildError("content/about.md needs an alt field for the portrait")
    founder = find_founder()
    if founder:
        target = out / founder.name
        shutil.copyfile(founder, target)
        portrait = (
            f'<img class="portrait" src="/{founder.name}" '
            f'alt="{html.escape(alt, quote=True)}">'
        )
    else:
        portrait = '<div class="portrait" role="img" aria-label="portrait"></div>'
    main = f"""<main id="content" class="page" tabindex="-1">
<h1>{html.escape(title)}</h1>
<div class="about">
{portrait}
<div class="prose">
{render_markdown(body)}
</div>
</div>
</main>
"""
    return page(
        title=f"{title} · nullstar.games",
        description=excerpt(body) or "about nullstar.",
        current="/about/",
        main=main,
        css_version=css_version,
    )


def missing_page(css_version: str) -> str:
    main = """<main id="content" class="page" tabindex="-1">
<h1>not found</h1>
<p class="quiet">this page is not here.</p>
<p><a href="/">home</a></p>
</main>
"""
    return page(
        title="not found · nullstar",
        description="this page is not here.",
        current="",
        main=main,
        css_version=css_version,
    )


def copy_static(out: Path) -> str:
    if not (STATIC / "style.css").is_file():
        raise BuildError("src/static/style.css is missing")
    for path in STATIC.rglob("*"):
        if not path.is_file() or path.name.startswith("."):
            continue
        dest = out / path.relative_to(STATIC)
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(path, dest)
    return asset_version(STATIC / "style.css")


def build(root: Path | None = None) -> Path:
    global ROOT, CONTENT, STATIC, DIST
    if root is not None:
        ROOT = root
        CONTENT = root / "content"
        STATIC = root / "src" / "static"
        DIST = root / "dist"
    if DIST.is_symlink():
        raise BuildError("dist is a symlink; not removing it")
    out = ROOT / "dist.tmp"
    if out.exists():
        shutil.rmtree(out)
    out.mkdir()
    try:
        css_version = copy_static(out)
        phrases = load_phrases()
        posts = load_posts()
        write_page(out / "index.html", home_page(phrases, css_version))
        write_page(out / "tech" / "index.html", tech_page(css_version, out))
        write_page(out / "worlds" / "index.html", worlds_page(css_version))
        write_page(out / "news" / "index.html", news_index(posts, css_version))
        for post in posts:
            write_page(
                out / "news" / str(post["slug"]) / "index.html",
                news_post(post, css_version),
            )
        write_page(out / "about" / "index.html", about_page(css_version, out))
        write_page(out / "404.html", missing_page(css_version))
    except Exception:
        shutil.rmtree(out, ignore_errors=True)
        raise
    if DIST.exists():
        shutil.rmtree(DIST)
    out.rename(DIST)
    return DIST


def main() -> None:
    build()
    print(f"built {DIST.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
