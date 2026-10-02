#!/usr/bin/env python3
"""Build the site and check the pages, the markdown, and text contrast."""

from __future__ import annotations

import re
import tempfile
from datetime import date
from pathlib import Path

import build


def expect(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(message)


def contrast(fg: str, bg: str) -> float:
    def channel(hex_color: str) -> float:
        value = int(hex_color, 16) / 255
        if value <= 0.04045:
            return value / 12.92
        return ((value + 0.055) / 1.055) ** 2.4

    def luminance(color: str) -> float:
        color = color.removeprefix("#")
        red, green, blue = color[0:2], color[2:4], color[4:6]
        return (
            0.2126 * channel(red)
            + 0.7152 * channel(green)
            + 0.0722 * channel(blue)
        )

    lighter = max(luminance(fg), luminance(bg))
    darker = min(luminance(fg), luminance(bg))
    return (lighter + 0.05) / (darker + 0.05)


def check_markdown() -> None:
    html = build.render_markdown(
        "\n".join(
            [
                "# hello",
                "",
                "a *quiet* **page** with `<b>` and `code`.",
                "",
                "see [home](/) and [off](https://example.com/a).",
                "",
                "[nope](javascript:alert(1))",
                "",
                "- one",
                "- two",
                "",
                "1. first",
                "",
                "> a line",
                "",
                "---",
                "",
                "```",
                "<tag>",
                "```",
                "",
                "![mark](/favicon.svg)",
            ]
        )
    )
    expect("<h1>hello</h1>" in html, "heading did not render")
    expect("<em>quiet</em>" in html, "emphasis did not render")
    expect("<strong>page</strong>" in html, "strong did not render")
    expect("&lt;b&gt;" in html, "raw html was not escaped")
    expect("<code>code</code>" in html, "code span did not render")
    expect('<a href="/">home</a>' in html, "relative link did not render")
    expect('rel="noopener noreferrer"' in html, "external link is missing rel")
    expect("javascript:" not in html, "javascript url was kept")
    expect("<ul><li>one</li><li>two</li></ul>" in html, "list did not render")
    expect("<ol><li>first</li></ol>" in html, "numbered list did not render")
    expect("<blockquote><p>a line</p></blockquote>" in html, "quote did not render")
    expect("<hr>" in html, "rule did not render")
    expect("<pre><code>&lt;tag&gt;</code></pre>" in html, "fence did not render")
    expect('src="/favicon.svg"' in html, "image did not render")

    try:
        build.render_markdown("```\nno close\n")
    except build.BuildError:
        pass
    else:
        raise SystemExit("unclosed fence should fail the build")


def check_posts() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        news = root / "blog"
        news.mkdir(parents=True)
        (news / "2026-01-02-note.md").write_text(
            "---\ntitle: note\ndate: 2026-05-01\n---\n\nhello\n",
            encoding="utf-8",
        )
        build.ROOT = root
        build.CONTENT = root / "content"
        try:
            build.load_posts()
        except build.BuildError as exc:
            expect("does not match" in str(exc), f"unexpected date error: {exc}")
        else:
            raise SystemExit("mismatched filename date should fail")
        build.ROOT = Path(__file__).resolve().parent.parent
        build.CONTENT = build.ROOT / "content"


def check_contrast() -> None:
    css = (build.STATIC / "style.css").read_text(encoding="utf-8")
    colors = dict(re.findall(r"--(bg|fg|muted|logic):\s*(#[0-9a-fA-F]{6})", css))
    expect(set(colors) == {"bg", "fg", "muted", "logic"}, "theme colors missing from css")
    for name in ("fg", "muted", "logic"):
        ratio = contrast(colors[name], colors["bg"])
        expect(ratio >= 4.5, f"--{name} contrast {ratio:.2f} is below 4.5")


def check_site(dist: Path) -> None:
    home = (dist / "index.html").read_text(encoding="utf-8")
    news = (dist / "news" / "index.html").read_text(encoding="utf-8")
    post = (dist / "news" / "the-studio-is-open" / "index.html").read_text(encoding="utf-8")
    tech = (dist / "tech" / "index.html").read_text(encoding="utf-8")
    worlds = (dist / "worlds" / "index.html").read_text(encoding="utf-8")
    about = (dist / "about" / "index.html").read_text(encoding="utf-8")
    missing = (dist / "404.html").read_text(encoding="utf-8")
    css = (dist / "style.css").read_text(encoding="utf-8")

    for label, text in (
        ("home", home),
        ("tech", tech),
        ("worlds", worlds),
        ("news", news),
        ("about", about),
    ):
        expect("nullstar" in text, f"{label} is missing the wordmark")
        expect('href="/"' in text and ">home</a>" in text, f"{label} is missing home")
        expect('href="/tech/"' in text, f"{label} is missing tech")
        expect('href="/worlds/"' in text, f"{label} is missing worlds")
        expect('href="/news/"' in text, f"{label} is missing news")
        expect('href="/about/"' in text, f"{label} is missing about")
        expect(
            text.index(">home</a>") < text.index('href="/tech/"') < text.index('href="/worlds/"'),
            f"{label} menu should list tech between home and worlds",
        )

    expect('id="life"' in home, "home is missing the life field")
    expect('id="life"' not in worlds and 'id="life"' not in tech, "life field should stay on the front page")
    expect("<h1>tech</h1>" in tech, "tech title missing")
    expect('src="/tech/field.svg"' in tech, "tech page is missing its pictures")
    expect('src="/tech/study.svg"' in tech and 'src="/tech/room.svg"' in tech, "tech page is missing its pictures")
    expect("life-rainbow" in home, "sun is missing the rainbow")
    expect("hsl(0 62% 82%)" in css, "rainbow is missing from the page")
    expect('class="sun"' in home, "home is missing the sun")
    expect('class="smile"' in home, "sun is missing a smile")
    phrases = [
        line.strip()
        for line in (build.ROOT / "content" / "phrases.txt").read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.strip().startswith("#")
    ]
    expect(phrases[0] in home, "home is missing the first phrase")
    expect(phrases[-1] in home, "home is missing the last phrase")
    expect("text-transform: lowercase" in css, "css is not lowercase")
    expect("background: var(--bg)" in css, "page background is not the black token")
    expect("Space Grotesk" in css, "site font did not change")
    expect((dist / "fonts" / "space-grotesk.woff2").is_file(), "font file missing")
    expect('class="logic"' in worlds and "LOGIC-13" in worlds, "worlds title missing")
    expect("text-transform: none" in css, "logic title would be forced lowercase")

    expect((build.ROOT / "blog" / "2026-10-01-the-studio-is-open.md").is_file(), "blog post is not one markdown file")
    expect(not (build.ROOT / "content" / "news").exists(), "posts should live in blog/")
    expect('datetime="2026-10-01"' in news, "news date missing")
    expect('href="/about/"' in post, "post link did not render")
    expect("m is the founder of nullstar." in about, "about copy missing")
    expect('class="portrait"' in about, "about portrait slot missing")
    expect("founder.jpg" not in about, "portrait should stay empty until the file exists")
    expect("this page is not here." in missing, "404 copy missing")
    expect((dist / "favicon.svg").is_file(), "favicon missing")
    expect((dist / "sun.js").is_file(), "sun.js missing")
    expect((dist / "life.js").is_file(), "life.js missing")

    day = date(2026, 10, 1)
    expect(build.format_date(day) == "1 oct 2026", "date format changed")


def main() -> None:
    check_markdown()
    check_posts()
    check_contrast()
    dist = build.build()
    check_site(dist)
    print("ok")


if __name__ == "__main__":
    main()
