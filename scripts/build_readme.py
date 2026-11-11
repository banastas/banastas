#!/usr/bin/env python3
"""Build README.md from README.template.md and the three banast.as sites.

    pip install pillow
    python3 scripts/build_readme.py

Each placeholder in the template becomes one table cell, so together they
form a single row:
  {{photo}}  latest frame from photo.banast.as (thumbnailed into assets/photos/)
  {{post}}   latest post from blog.banast.as (hero thumbnailed into assets/blog/)
  {{studio}} signpost to floor1point2.com: the Floor 1.2 mark, drawn here
"""
import html
import io
import json
import re
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from email.utils import parsedate_to_datetime
from pathlib import Path

from PIL import Image, ImageDraw, ImageOps

ROOT = Path(__file__).resolve().parent.parent
TEMPLATE = ROOT / "README.template.md"
README = ROOT / "README.md"
PHOTO_DIR = ROOT / "assets" / "photos"
BLOG_DIR = ROOT / "assets" / "blog"
STUDIO_IMG = ROOT / "assets" / "floor1point2.png"

PHOTO_FEED = "https://photo.banast.as/rss.xml"
BLOG_FEED = "https://blog.banast.as/rss.xml"
STUDIO_URL = "https://floor1point2.com"

THUMB = (720, 480)  # 3:2, shared by photo and post so the cells line up

# The Floor 1.2 mark, from Rune/scripts/brand/family-mark.swift: five bars
# ("##" each, one cell apart), the last one dim, on the HUD's near-black.
MARK_ROW = "##.##.##.##.::"
MARK_BG, MARK_BRIGHT, MARK_DIM = (0x0A, 0x0A, 0x0A), (0xF0, 0xF0, 0xF0), (0x4A, 0x4A, 0x4A)

CONTENT_NS = "{http://purl.org/rss/1.0/modules/content/}encoded"
UA = "banastas-profile-readme (+https://github.com/banastas/banastas)"


# ---- helpers ---------------------------------------------------------------

def fetch(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read()


def first_item(feed_url: str):
    item = ET.fromstring(fetch(feed_url)).find("./channel/item")
    if item is None:
        raise RuntimeError(f"no items in {feed_url}")
    return item


def text(el, tag: str, default: str = "") -> str:
    found = el.find(tag)
    return (found.text or default).strip() if found is not None else default


def esc(s: str) -> str:
    return html.escape(s, quote=False).replace('"', "&quot;")


def safe_name(s: str, ext: str) -> str:
    return re.sub(r"[^A-Za-z0-9_-]", "", s) + ext


def thumbnail(src_url: str, dest: Path) -> None:
    """Center-crop and downscale a remote image. Skips work if dest exists."""
    if dest.exists():
        return
    dest.parent.mkdir(parents=True, exist_ok=True)
    img = ImageOps.exif_transpose(Image.open(io.BytesIO(fetch(src_url))))
    img = ImageOps.fit(img.convert("RGB"), THUMB, Image.LANCZOS, centering=(0.5, 0.5))
    img.save(dest, "JPEG", quality=82, optimize=True, progressive=True)
    print(f"  thumbnail {dest.relative_to(ROOT)}")


def prune(directory: Path, keep: set, pattern: str) -> None:
    for f in directory.glob(pattern):
        if f.name not in keep:
            f.unlink()
            print(f"  removed {f.relative_to(ROOT)}")


def label(site: str, host: str = "") -> str:
    """Cell header: the site's wordmark (an SVG from make_headers.py), linked.

    GitHub forces its link color on text, so headers are images instead.
    """
    host = host or f"{site}.banast.as"
    return (
        f'<a href="https://{host}"><picture>'
        f'<source media="(prefers-color-scheme: dark)" srcset="assets/head-{site}-dark.svg">'
        f'<img src="assets/head-{site}-light.svg" alt="{host}" height="22">'
        f"</picture></a><br>"
    )


def cell(body: str) -> str:
    return f'<td width="33%" valign="top">\n{body}\n</td>'


# ---- cells -----------------------------------------------------------------

def photo() -> str:
    item = first_item(PHOTO_FEED)
    link = text(item, "link")
    pid = link.rstrip("/").rsplit("/", 1)[-1]
    alt = text(item, "description", pid)
    name = safe_name(pid, ".jpg")
    thumbnail(item.find("enclosure").get("url"), PHOTO_DIR / name)
    prune(PHOTO_DIR, {name}, "*.jpg")

    exif = item.find("exif")
    caption = ""
    if exif is not None:
        bits = [text(exif, k) for k in ("focalLength", "aperture", "shutterSpeed", "iso")]
        if bits[-1]:
            bits[-1] = f"ISO {bits[-1]}"
        caption = " &middot; ".join(b for b in bits if b)
        camera = text(exif, "camera")
        if camera:
            caption = f"{esc(camera)}<br>{caption}"

    return cell(
        label("photo")
        + f'<a href="{esc(link)}"><img src="assets/photos/{name}" alt="{esc(alt)}" title="{esc(alt)}" width="100%"></a>'
        + (f"<br><sub>{caption}</sub>" if caption else "")
    )


def post() -> str:
    item = first_item(BLOG_FEED)
    link = text(item, "link")
    title = text(item, "title")
    date = parsedate_to_datetime(text(item, "pubDate"))
    slug = link.rstrip("/").rsplit("/", 1)[-1]

    image = ""
    hero = re.search(r'<img[^>]+src="([^"]+)"', html.unescape(text(item, CONTENT_NS)))
    keep = set()
    if hero:
        name = safe_name(slug, ".jpg")
        thumbnail(urllib.parse.urljoin(link, hero.group(1)), BLOG_DIR / name)
        keep.add(name)
        image = f'<a href="{esc(link)}"><img src="assets/blog/{name}" alt="" title="{esc(text(item, "description"))}" width="100%"></a><br>'
    prune(BLOG_DIR, keep, "*.jpg")

    return cell(
        label("blog")
        + image
        + f'<sub>{date:%B} {date.day}, {date:%Y}</sub><br><b>{esc(title)}</b>'
    )


def mark(dest: Path) -> None:
    """Draw the Floor 1.2 mark at THUMB size so it lines up with photo and post.

    Square cells, a whole number of pixels each, spanning about 62% of the
    width (the proportion family-mark.swift uses), centred. Deterministic, so
    redrawing every run leaves git with nothing to commit.
    """
    w, h = THUMB
    cell = int(w * 0.62 / len(MARK_ROW))
    x0, y0 = (w - cell * len(MARK_ROW)) // 2, (h - cell) // 2
    img = Image.new("RGB", THUMB, MARK_BG)
    px = ImageDraw.Draw(img)
    for i, ch in enumerate(MARK_ROW):
        if ch != ".":
            x = x0 + i * cell
            px.rectangle([x, y0, x + cell - 1, y0 + cell - 1], fill=MARK_BRIGHT if ch == "#" else MARK_DIM)
    dest.parent.mkdir(parents=True, exist_ok=True)
    img.save(dest, "PNG", optimize=True)


def studio() -> str:
    """A signpost to the studio the apps moved to.

    Header and mark link there; the caption stays plain text because GitHub
    forces its link color on linked text, which would set it apart from the
    photo and post captions.
    """
    mark(STUDIO_IMG)
    link = f'<a href="{STUDIO_URL}">'
    return cell(
        label("floor", "floor1point2.com")
        + f'{link}<img src="assets/{STUDIO_IMG.name}" alt="Floor 1.2" title="Floor 1.2" width="100%"></a>'
        + "<br><sub>Floor 1.2<br>Native apps for the Mac and iPhone</sub>"
    )


# ---- main ------------------------------------------------------------------

def main() -> None:
    out = TEMPLATE.read_text()
    for key, build in (("photo", photo), ("post", post), ("studio", studio)):
        print(f"{key}…")
        out = out.replace("{{" + key + "}}", build())

    if README.exists() and README.read_text() == out:
        print("README.md unchanged")
    else:
        README.write_text(out)
        print("README.md updated")


if __name__ == "__main__":
    main()
