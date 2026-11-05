#!/usr/bin/env python3
"""Generate the column headers as SVGs, in dark and light variants:

  assets/head-{site}-{theme}.svg   ("■ PHOTO.BANAST.AS ↗")

GitHub forces its own link color on text, so the headers are drawn as images
in the dev.banast.as type and palette. They only need re-running when the
copy changes. JetBrains Mono is pulled from Google Fonts, subset to exactly
the characters used, and embedded as base64 so it renders inside <img>.

    python3 scripts/make_headers.py
"""
import base64
import re
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "assets"

SITES = ["photo", "blog", "dev"]  # each header reads <SITE>.BANAST.AS
ARROW = "↗"

# Palette from dev.banast.as.
THEMES = {
    "dark": dict(text="#eeeee9", muted="#797971"),
    "light": dict(text="#121210", muted="#85857c"),
}

# JetBrains Mono advances are 0.6em.
SIZE, TRACK, HEIGHT, BASELINE = 14, 2.5, 22, 15

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/130.0 Safari/537.36")


def font_b64(family: str, text: str) -> str:
    """Fetch a Google Fonts woff2 subset containing only `text`, as base64."""
    query = urllib.parse.urlencode({"family": family, "text": "".join(sorted(set(text)))})
    req = urllib.request.Request(f"https://fonts.googleapis.com/css2?{query}", headers={"User-Agent": UA})
    css = urllib.request.urlopen(req).read().decode()
    url = re.search(r"url\((https://[^)]+)\)", css).group(1)
    data = urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": UA})).read()
    return base64.b64encode(data).decode()


def label(site: str) -> str:
    return f"{site}.banast.as".upper()


def header(site: str, theme: str, font: str) -> str:
    """A pixel bullet, the site name, and a muted arrow."""
    t = THEMES[theme]
    text = label(site)
    advance = SIZE * 0.6 + TRACK
    text_x = 14
    arrow_x = text_x + len(text) * advance + 4
    width = round(arrow_x + advance)
    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {HEIGHT}" width="{width}" height="{HEIGHT}" role="img" aria-label="{site}.banast.as">
<defs><style>@font-face{{font-family:"JBM";font-weight:500;src:url(data:font/woff2;base64,{font}) format("woff2");}}.m{{font-family:"JBM",ui-monospace,monospace;}}</style></defs>
<rect x="0" y="{BASELINE - 8}" width="7" height="7" fill="{t['text']}"/>
<text class="m" x="{text_x}" y="{BASELINE}" font-size="{SIZE}" font-weight="500" letter-spacing="{TRACK}" fill="{t['text']}">{text}</text>
<text class="m" x="{arrow_x:.1f}" y="{BASELINE}" font-size="{SIZE}" font-weight="500" fill="{t['muted']}">{ARROW}</text>
</svg>
"""


def main() -> None:
    OUT.mkdir(exist_ok=True)
    font = font_b64("JetBrains Mono:wght@500", "".join(label(s) for s in SITES) + ARROW)
    for theme in THEMES:
        for site in SITES:
            path = OUT / f"head-{site}-{theme}.svg"
            path.write_text(header(site, theme, font))
            print(f"wrote {path.relative_to(ROOT)} ({path.stat().st_size:,} bytes)")


if __name__ == "__main__":
    main()
