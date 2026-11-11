#!/usr/bin/env python3
"""Generate the column headers as SVGs, in dark and light variants:

  assets/head-{slug}-{theme}.svg   ("photo" bright + ".banast.as" dimmed)

GitHub forces its own link color on text, so the headers are drawn as images
in Mona Sans (GitHub's interface font) and GitHub's own text colors. They
only need re-running when the copy changes. The font is pulled from Google
Fonts, subset to exactly the characters used, and embedded as base64 so it
renders inside <img>.

    python3 scripts/make_headers.py
"""
import base64
import re
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "assets"

# slug (file name) -> (bright part, dimmed part)
SITES = {
    "photo": ("photo", ".banast.as"),
    "blog": ("blog", ".banast.as"),
    "floor": ("floor1point2", ".com"),
}

# GitHub's foreground and muted text colors per theme.
THEMES = {
    "dark": dict(fg="#f0f6fc", muted="#9198a1"),
    "light": dict(fg="#1f2328", muted="#59636e"),
}

SIZE, WEIGHT, HEIGHT, BASELINE = 16, 600, 22, 16
WIDTH = 160  # wider than the longest label; the extra canvas is transparent

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


def header(name: str, domain: str, theme: str, font: str) -> str:
    t = THEMES[theme]
    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {WIDTH} {HEIGHT}" width="{WIDTH}" height="{HEIGHT}" role="img" aria-label="{name}{domain}">
<defs><style>@font-face{{font-family:"Mona";font-weight:{WEIGHT};src:url(data:font/woff2;base64,{font}) format("woff2");}}</style></defs>
<text x="0" y="{BASELINE}" font-family="Mona,-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif" font-size="{SIZE}" font-weight="{WEIGHT}" fill="{t['fg']}">{name}<tspan fill="{t['muted']}">{domain}</tspan></text>
</svg>
"""


def main() -> None:
    OUT.mkdir(exist_ok=True)
    font = font_b64(f"Mona Sans:wght@{WEIGHT}", "".join(a + b for a, b in SITES.values()))
    for theme in THEMES:
        for slug, (name, domain) in SITES.items():
            path = OUT / f"head-{slug}-{theme}.svg"
            path.write_text(header(name, domain, theme, font))
            print(f"wrote {path.relative_to(ROOT)} ({path.stat().st_size:,} bytes)")


if __name__ == "__main__":
    main()
