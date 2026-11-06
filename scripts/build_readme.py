#!/usr/bin/env python3
"""Build README.md from README.template.md and the three banast.as sites.

    pip install pillow
    python3 scripts/build_readme.py

Each placeholder in the template becomes one table cell, so together they
form a single row:
  {{photo}}  latest frame from photo.banast.as (thumbnailed into assets/photos/)
  {{post}}   latest post from blog.banast.as (hero thumbnailed into assets/blog/)
  {{apps}}   Mac app icons from dev.banast.as, each linked to the app's site
"""
import hashlib
import html
import io
import json
import re
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from email.utils import parsedate_to_datetime
from pathlib import Path

from PIL import Image, ImageOps

ROOT = Path(__file__).resolve().parent.parent
TEMPLATE = ROOT / "README.template.md"
README = ROOT / "README.md"
PHOTO_DIR = ROOT / "assets" / "photos"
BLOG_DIR = ROOT / "assets" / "blog"
ICON_DIR = ROOT / "assets" / "icons"

PHOTO_FEED = "https://photo.banast.as/rss.xml"
BLOG_FEED = "https://blog.banast.as/rss.xml"
DEV_SITE = "https://dev.banast.as/"

THUMB = (720, 480)  # 3:2, shared by photo and post so the cells line up
ICON_SIZE = 58      # display width in px (4 per row in the column); PNGs are stored at 2x

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


def icon_png(src_url: str, dest: Path) -> None:
    """Convert a remote app icon to a transparent PNG at 2x display size.

    Always re-fetched (no exists() check) so icon changes on the site show up;
    git only commits when the bytes differ.
    """
    dest.parent.mkdir(parents=True, exist_ok=True)
    img = Image.open(io.BytesIO(fetch(src_url))).convert("RGBA")
    img = img.resize((ICON_SIZE * 2, ICON_SIZE * 2), Image.LANCZOS)
    img.save(dest, "PNG", optimize=True)
    print(f"  icon {dest.relative_to(ROOT)}")


def prune(directory: Path, keep: set, pattern: str) -> None:
    for f in directory.glob(pattern):
        if f.name not in keep:
            f.unlink()
            print(f"  removed {f.relative_to(ROOT)}")


def label(site: str) -> str:
    """Cell header: the site's wordmark (an SVG from make_headers.py), linked.

    GitHub forces its link color on text, so headers are images instead.
    """
    host = f"{site}.banast.as"
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


def dev_haiku(page: str) -> dict:
    """Map project URL -> haiku (with line breaks) from dev.banast.as JSON-LD."""
    found = {}

    def walk(node):
        if isinstance(node, dict):
            if "url" in node and "description" in node:
                found[node["url"].rstrip("/").lower()] = node["description"]
            for v in node.values():
                walk(v)
        elif isinstance(node, list):
            for v in node:
                walk(v)

    for block in re.findall(r'<script type="application/ld\+json">(.*?)</script>', page, re.S):
        try:
            walk(json.loads(block))
        except json.JSONDecodeError:
            pass
    return found


APP_TILE = re.compile(
    r'<a class="app-tile" href="(?P<url>[^"]+)".*?'
    r'<img src="(?P<icon>[^"]+)".*?'
    r'<span class="app-name">(?P<name>[^<]+)</span>',
    re.S,
)


def apps() -> str:
    page = fetch(DEV_SITE).decode("utf-8", "replace")
    grids = "".join(re.findall(r'<ul class="app-grid".*?</ul>', page, re.S))
    if not grids:
        raise RuntimeError("app grid not found on dev.banast.as")
    haiku = dev_haiku(page)

    links, keep, seen = [], set(), set()
    for m in APP_TILE.finditer(grids):
        url, name = m["url"], html.unescape(m["name"]).strip()
        if url in seen:
            continue
        seen.add(url)
        file = safe_name(Path(urllib.parse.urlparse(m["icon"]).path).stem, ".png")
        icon_png(urllib.parse.urljoin(DEV_SITE, m["icon"]), ICON_DIR / file)
        keep.add(file)
        # Content hash in the URL busts GitHub/browser caches when an icon changes.
        ver = hashlib.sha1((ICON_DIR / file).read_bytes()).hexdigest()[:8]
        verse = haiku.get(url.rstrip("/").lower(), "")
        tip = esc(name + ("\n\n" + verse if verse else "")).replace("\n", "&#10;")
        links.append(f'<a href="{esc(url)}"><img src="assets/icons/{file}?v={ver}" alt="{esc(name)}" title="{tip}" width="{ICON_SIZE}"></a>')
    prune(ICON_DIR, keep, "*.png")

    return cell(label("dev") + "\n".join(links))


# ---- main ------------------------------------------------------------------

def main() -> None:
    out = TEMPLATE.read_text()
    for key, build in (("photo", photo), ("post", post), ("apps", apps)):
        print(f"{key}…")
        out = out.replace("{{" + key + "}}", build())

    if README.exists() and README.read_text() == out:
        print("README.md unchanged")
    else:
        README.write_text(out)
        print("README.md updated")


if __name__ == "__main__":
    main()
