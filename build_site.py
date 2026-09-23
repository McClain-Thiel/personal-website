"""Build the public site from Markdown articles and reactive marimo notebooks."""

from __future__ import annotations

import argparse
from dataclasses import dataclass, field
from datetime import date, datetime, time, timezone
from email.utils import format_datetime
from html import escape
import hashlib
from io import BytesIO
import json
import math
from pathlib import Path
import re
from string import Template
import subprocess
import sys
import tempfile
import tomllib
from urllib.parse import quote, urlparse
import xml.etree.ElementTree as ET
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo

import markdown
from bs4 import BeautifulSoup
import marimo
from PIL import Image, ImageDraw, ImageFont
import yaml

ROOT = Path(__file__).resolve().parent
SITE_URL = "https://mcclainthiel.com"
BLOG_DESCRIPTION = (
    "Research explainers and practical notes on machine learning, DNA language models, "
    "reinforcement learning, and AI for science by McClain Thiel."
)
AUTHOR = {
    "@type": "Person",
    "@id": f"{SITE_URL}/#person",
    "name": "McClain Thiel",
    "url": f"{SITE_URL}/",
    "sameAs": [
        "https://scholar.google.com/citations?hl=en&user=wgbzrtIAAAAJ",
        "https://github.com/McClain-Thiel",
        "https://www.linkedin.com/in/mcclain-thiel/",
    ],
}


@dataclass
class Post:
    slug: str
    title: str
    description: str
    published: date
    modified: date
    tags: list[str]
    references: list[dict[str, str]]
    html: str
    toc: str
    minutes: int
    notebook_source: str = ""
    attachments: dict[str, bytes] = field(default_factory=dict)

    @property
    def path(self) -> str:
        return f"/blog/{self.slug}/"

    @property
    def url(self) -> str:
        return SITE_URL + self.path


def text_field(record: dict, name: str) -> str:
    value = record.get(name)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(
            f"Post {record.get('id', '<unknown>')}: {name} must be nonempty text"
        )
    return value.strip()


def parse_date(record: dict, name: str) -> date:
    value = text_field(record, name)
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
        raise ValueError(f"Post {record.get('id')}: {name} must use YYYY-MM-DD")
    return date.fromisoformat(value)


def inline_metadata(path: Path) -> tuple[dict, str, list[str]]:
    text = path.read_text(encoding="utf-8")
    if path.suffix == ".md":
        match = re.match(r"\A---\r?\n(.*?)\r?\n---(?:\r?\n|$)", text, re.S)
        if not match:
            return {}, text, []
        record = yaml.safe_load(match[1])
        if not isinstance(record, dict):
            raise ValueError(f"{path}: front matter must be a metadata mapping")
        for key in ("date", "updated"):
            if isinstance(record.get(key), date):
                record[key] = record[key].isoformat()
        return record, text[match.end() :].strip(), []
    blocks = re.findall(r"(?m)^# /// script\n((?:#(?: .*|)\n)*)# ///$", text)
    if len(blocks) > 1:
        raise ValueError(f"{path}: only one PEP 723 script block is allowed")
    if not blocks:
        return {}, text, []
    config = tomllib.loads("\n".join(line[2:] for line in blocks[0].splitlines()))
    record = config.get("tool", {}).get("blog", {})
    if not isinstance(record, dict):
        raise ValueError(f"{path}: [tool.blog] must contain article metadata")
    dependencies = config.get("dependencies", [])
    if not isinstance(dependencies, list) or any(
        not isinstance(item, str) or not item.strip() for item in dependencies
    ):
        raise ValueError(f"{path}: dependencies must be a list of package requirements")
    for key in ("date", "updated"):
        if isinstance(record.get(key), date):
            record[key] = record[key].isoformat()
    return record, text, dependencies


def discover_posts(source: Path) -> list[dict]:
    registry = source / "blog/posts.json"
    records = json.loads(registry.read_text()) if registry.exists() else []
    if not isinstance(records, list):
        raise ValueError("blog/posts.json must be an array")
    if any(not isinstance(record, dict) for record in records):
        raise ValueError("Each post must be an object")
    registered = {
        record.get("file") for record in records if isinstance(record.get("file"), str)
    }
    for path in sorted((source / "blog").iterdir()):
        if path.name in {"README.md", "assets"} or path.name.startswith(("_", ".")):
            continue
        if path.is_symlink():
            raise ValueError(f"Post source must not be a symbolic link: {path}")
        default_slug = path.stem
        if path.is_dir():
            default_slug = path.name
            entries = [
                path / name
                for name in ("index.md", "notebook.py")
                if (path / name).exists()
            ]
            if len(entries) != 1:
                raise ValueError(
                    f"{path}: article folders need exactly one index.md or notebook.py"
                )
            path = entries[0]
            if path.is_symlink():
                raise ValueError(f"Post source must not be a symbolic link: {path}")
        elif path.suffix not in {".md", ".py"}:
            continue
        filename = path.relative_to(source / "blog").as_posix()
        record, _, _ = inline_metadata(path)
        if filename in registered:
            if record:
                raise ValueError(
                    f"{path}: metadata exists both in the file and posts.json; use only one"
                )
            continue
        if not record:
            raise ValueError(
                f"{path}: add YAML front matter (Markdown) or [tool.blog] in a PEP 723 script block (marimo)"
            )
        if "file" in record:
            raise ValueError(
                f"{path}: inline metadata must not override its source file"
            )
        records.append({"id": default_slug, **record, "file": filename})
    return records


def article_assets(directory: Path) -> dict[str, bytes]:
    files = {}
    for name in ("data", "assets"):
        root = directory / name
        if root.is_symlink():
            raise ValueError(f"Article asset must not be a symbolic link: {root}")
        if not root.exists():
            continue
        if not root.is_dir():
            raise ValueError(f"{root}: expected a directory")
        for path in sorted(root.rglob("*")):
            relative = path.relative_to(directory)
            if any(
                part.startswith(".") or part == "__pycache__" for part in relative.parts
            ):
                continue
            if path.is_symlink():
                raise ValueError(f"Article asset must not be a symbolic link: {path}")
            if path.is_file():
                files[relative.as_posix()] = path.read_bytes()
    return files


def article_archive(slug: str, entry: Path, assets: dict[str, bytes]) -> bytes:
    buffer = BytesIO()
    with ZipFile(buffer, "w") as archive:
        for name, content in {entry.name: entry.read_bytes(), **assets}.items():
            info = ZipInfo(f"{slug}/{name}")
            info.compress_type = ZIP_DEFLATED
            archive.writestr(info, content)
    return buffer.getvalue()


def render_notebook(
    path: Path, dependencies: list[str], assets: dict[str, bytes], slug: str
) -> str:
    manifest = [
        {
            "path": name,
            "url": f"/blog/{slug}/{quote(name, safe='/')}",
            "sha256": hashlib.sha256(content).hexdigest(),
        }
        for name, content in assets.items()
    ]
    command = [sys.executable]
    if dependencies:
        command = [
            "uv",
            "run",
            "--no-project",
            "--isolated",
            "--python",
            sys.executable,
            "--with",
            f"marimo=={marimo.__version__}",
        ]
        for dependency in dependencies:
            command += ["--with", dependency]
        command += ["python"]
    with tempfile.TemporaryDirectory(prefix="blog-notebook-") as directory:
        result_path = Path(directory) / "rendered.json"
        command += [
            str(ROOT / "render_notebook.py"),
            str(path.resolve()),
            str(result_path),
            json.dumps({"dependencies": dependencies, "assets": manifest}),
        ]
        try:
            result = subprocess.run(
                command, capture_output=True, text=True, timeout=180, cwd=ROOT
            )
        except subprocess.TimeoutExpired as error:
            raise ValueError(
                f"Notebook {path.name}: rendering exceeded the 180-second limit"
            ) from error
        if result.returncode:
            raise ValueError(
                f"Notebook {path.name} failed to render:\n{result.stdout}\n{result.stderr}"
            )
        if result.stderr.strip():
            print(f"Notebook {path.name}:\n{result.stderr}", file=sys.stderr)
        rendered = json.loads(result_path.read_text())
    soup = BeautifulSoup(rendered.pop("html"), "html.parser")
    # marimo serializes Markdown into attributes; materialize it for readers and crawlers.
    for node in soup.select("marimo-mime-renderer"):
        mime = json.loads(node["data-mime"])
        data = json.loads(node["data-data"])
        if mime in {"text/markdown", "text/html"}:
            node.replace_with(BeautifulSoup(data, "html.parser"))
        elif mime == "text/plain":
            node.replace_with(
                BeautifulSoup(f"<pre>{escape(str(data))}</pre>", "html.parser")
            )
    return (
        str(soup)
        + f'<script id="notebook-runtime" type="application/json" data-runtime="https://cdn.jsdelivr.net/npm/@marimo-team/islands@{marimo.__version__}/dist/main.js">{json_script(rendered)}</script>'
    )


def load_posts(source: Path, today: date) -> list[Post]:
    records = discover_posts(source)
    posts = []
    seen = set()
    for record in records:
        if not isinstance(record, dict):
            raise ValueError("Each post must be an object")
        unknown = record.keys() - {
            "id",
            "title",
            "description",
            "date",
            "updated",
            "file",
            "draft",
            "tags",
            "references",
        }
        if unknown:
            raise ValueError(f"Unknown post fields: {', '.join(sorted(unknown))}")
        slug = text_field(record, "id")
        if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", slug) or slug in {
            "assets",
            "index",
        }:
            raise ValueError(f"Invalid or reserved post ID: {slug}")
        if slug in seen:
            raise ValueError(f"Duplicate post ID: {slug}")
        seen.add(slug)
        draft = record.get("draft", False)
        if not isinstance(draft, bool):
            raise ValueError(f"Post {slug}: draft must be true or false")
        published = parse_date(record, "date")
        if draft or published > today:
            continue
        title = text_field(record, "title")
        description = text_field(record, "description")
        filename = text_field(record, "file")
        relative = Path(filename)
        if (
            relative.is_absolute()
            or len(relative.parts) not in {1, 2}
            or any(part in {".", ".."} for part in relative.parts)
            or relative.as_posix() != filename
            or relative.suffix not in {".md", ".py"}
        ):
            raise ValueError(
                f"Post {slug}: file must be a Markdown or marimo file directly inside blog/ or an article folder"
            )
        content_path = source / "blog" / filename
        if content_path.is_symlink() or content_path.parent.is_symlink():
            raise ValueError(f"Post {slug}: source must not be a symbolic link")
        modified = parse_date(record, "updated") if "updated" in record else published
        if not published <= modified <= today:
            raise ValueError(
                f"Post {slug}: updated must be between publication and today"
            )
        tags = record.get("tags", [])
        if not isinstance(tags, list) or any(
            not isinstance(tag, str) or not tag.strip() for tag in tags
        ):
            raise ValueError(f"Post {slug}: tags must be a list of nonempty strings")
        references = record.get("references", [])
        if not isinstance(references, list):
            raise ValueError(f"Post {slug}: references must be a list")
        for reference in references:
            if not isinstance(reference, dict):
                raise ValueError(f"Post {slug}: each reference needs a title and URL")
            text_field(reference, "title")
            url = urlparse(text_field(reference, "url"))
            if url.scheme != "https" or not url.netloc:
                raise ValueError(
                    f"Post {slug}: reference URLs must be absolute HTTPS URLs"
                )
        _, body, dependencies = inline_metadata(content_path)
        attachments = (
            article_assets(content_path.parent) if len(relative.parts) == 2 else {}
        )
        renderer = markdown.Markdown(
            extensions=["fenced_code", "tables", "footnotes", "toc", "attr_list"],
            extension_configs={"toc": {"toc_depth": "2-3", "permalink": False}},
        )
        notebook_source = body if content_path.suffix == ".py" else ""
        html = (
            render_notebook(content_path, dependencies, attachments, slug)
            if notebook_source
            else renderer.convert(body)
        )
        document = BeautifulSoup(html, "html.parser")
        h1s = document.find_all("h1")
        if h1s:
            if len(h1s) != 1 or h1s[0].get_text(" ", strip=True) != title:
                raise ValueError(
                    f"Post {slug}: use ## headings, or a single # heading matching the article title"
                )
            island = h1s[0].find_parent("marimo-island")
            if island:
                island["data-article-title"] = ""
            h1s[0].decompose()
        html = str(document)
        toc = renderer.toc if renderer.toc_tokens else ""
        if notebook_source:
            headings = document.select("h2[id], h3[id]")
            ids = [heading["id"] for heading in headings]
            if len(ids) != len(set(ids)):
                raise ValueError(
                    f"Post {slug}: notebook section headings need unique IDs"
                )
            if headings:
                toc = (
                    "<ul>"
                    + "".join(
                        f'<li><a href="#{escape(heading["id"], quote=True)}">{escape(heading.get_text(" ", strip=True))}</a></li>'
                        for heading in headings
                    )
                    + "</ul>"
                )
        readable = BeautifulSoup(html, "html.parser")
        for hidden in readable.select("script, style, marimo-cell-code, [hidden]"):
            hidden.decompose()
        words = re.findall(r"\b\w+\b", readable.get_text(" "))
        if not words:
            raise ValueError(f"Post {slug}: published posts need content")
        if len(relative.parts) == 2:
            attachments["article.zip"] = article_archive(
                slug, content_path, attachments
            )
        posts.append(
            Post(
                slug,
                title,
                description,
                published,
                modified,
                tags,
                references,
                html,
                toc,
                max(1, math.ceil(len(words) / 220)),
                notebook_source,
                attachments,
            )
        )
    return sorted(posts, key=lambda post: (post.published, post.slug), reverse=True)


def json_script(value: object) -> str:
    # A literal closing script tag in a title must not break out of JSON-LD.
    return json.dumps(value, ensure_ascii=False).replace("<", "\\u003c")


def metadata(
    title: str, description: str, path: str, *, post: Post | None = None
) -> str:
    url = SITE_URL + path
    image = SITE_URL + (post.path + "share.png" if post else "/og-image.png")
    tags = [
        f"<title>{escape(title)} — McClain Thiel</title>",
        f'<meta name="description" content="{escape(description, quote=True)}" />',
        '<meta name="author" content="McClain Thiel" />',
        '<meta name="robots" content="index, follow, max-image-preview:large, max-snippet:-1, max-video-preview:-1" />',
        f'<link rel="canonical" href="{url}" />',
        '<link rel="icon" type="image/png" sizes="96x96" href="/favicon.png" />',
        f'<link rel="alternate" type="application/rss+xml" title="McClain Thiel — Writing" href="{SITE_URL}/feed.xml" />',
    ]
    properties = {
        "og:type": "article" if post else "website",
        "og:site_name": "McClain Thiel",
        "og:locale": "en_GB",
        "og:title": title,
        "og:description": description,
        "og:url": url,
        "og:image": image,
        "og:image:type": "image/png",
        "og:image:width": "1200",
        "og:image:height": "630",
        "og:image:alt": f"{title} — McClain Thiel",
    }
    if post:
        properties.update(
            {
                "article:published_time": post.published.isoformat(),
                "article:modified_time": post.modified.isoformat(),
                "article:author": SITE_URL + "/",
            }
        )
    tags.extend(
        f'<meta property="{key}" content="{escape(value, quote=True)}" />'
        for key, value in properties.items()
    )
    for key, value in {
        "card": "summary_large_image",
        "title": title,
        "description": description,
        "image": image,
        "image:alt": properties["og:image:alt"],
    }.items():
        tags.append(
            f'<meta name="twitter:{key}" content="{escape(value, quote=True)}" />'
        )
    website = {
        "@type": "WebSite",
        "@id": SITE_URL + "/#website",
        "url": SITE_URL + "/",
        "name": "McClain Thiel",
        "publisher": {"@id": AUTHOR["@id"]},
    }
    if post:
        page = {
            "@type": "BlogPosting",
            "@id": url + "#article",
            "url": url,
            "mainEntityOfPage": {"@type": "WebPage", "@id": url},
            "headline": post.title,
            "description": post.description,
            "datePublished": post.published.isoformat(),
            "dateModified": post.modified.isoformat(),
            "author": AUTHOR,
            "publisher": {"@id": AUTHOR["@id"]},
            "image": {
                "@type": "ImageObject",
                "url": image,
                "width": 1200,
                "height": 630,
            },
            "inLanguage": "en",
            "isAccessibleForFree": True,
            "isPartOf": {
                "@type": "Blog",
                "@id": SITE_URL + "/blog/#blog",
                "url": SITE_URL + "/blog/",
                "name": "Writing — McClain Thiel",
            },
        }
        if post.tags:
            page["keywords"] = post.tags
        if post.references:
            page["citation"] = [
                {"@type": "CreativeWork", "name": ref["title"], "url": ref["url"]}
                for ref in post.references
            ]
    else:
        page = {
            "@type": "Blog" if path == "/blog/" else "WebPage",
            "@id": url + ("#blog" if path == "/blog/" else "#webpage"),
            "url": url,
            "name": title,
            "description": description,
            "inLanguage": "en",
            "author": AUTHOR,
            "isPartOf": {"@id": website["@id"]},
        }
    graph = [AUTHOR, website, page]
    if post:
        graph.append(
            {
                "@type": "BreadcrumbList",
                "itemListElement": [
                    {
                        "@type": "ListItem",
                        "position": 1,
                        "name": "Home",
                        "item": SITE_URL + "/",
                    },
                    {
                        "@type": "ListItem",
                        "position": 2,
                        "name": "Blog",
                        "item": SITE_URL + "/blog/",
                    },
                    {
                        "@type": "ListItem",
                        "position": 3,
                        "name": post.title,
                        "item": url,
                    },
                ],
            }
        )
    tags.append(
        f'<script type="application/ld+json">{json_script({"@context": "https://schema.org", "@graph": graph})}</script>'
    )
    return "\n  ".join(tags)


def display_date(value: date) -> str:
    return f"{value.day} {value.strftime('%B %Y')}"


def post_card(post: Post) -> str:
    return (
        f'<li class="post-item"><a href="{post.path}"><div>'
        f'<h2 class="post-title">{escape(post.title)}</h2>'
        f'<p class="writing-description">{escape(post.description)}</p></div>'
        f'<time class="post-date" datetime="{post.published}">{display_date(post.published)}</time></a></li>'
    )


def render_post(source: Path, post: Post, posts: list[Post], year: int) -> str:
    bundle_link = (
        '<a href="article.zip" download>Download article + data</a>'
        if "article.zip" in post.attachments
        else ""
    )
    references = ""
    if post.references:
        links = "".join(
            f'<li><a href="{escape(ref["url"], quote=True)}">{escape(ref["title"])}</a></li>'
            for ref in post.references
        )
        references = f'<section class="post-references" aria-labelledby="post-references-title"><h2 id="post-references-title">References &amp; resources</h2><ol>{links}</ol></section>'
    others = sorted(
        (other for other in posts if other.slug != post.slug),
        key=lambda other: len(set(other.tags) & set(post.tags)),
        reverse=True,
    )[:3]
    related = ""
    if others:
        related = (
            '<section class="related-posts" aria-labelledby="related-title"><h2 id="related-title">More writing</h2><ul class="post-list">'
            + "".join(post_card(other) for other in others)
            + "</ul></section>"
        )
    updated = (
        f' · Updated <time datetime="{post.modified}">{display_date(post.modified)}</time>'
        if post.modified > post.published
        else ""
    )
    return Template((source / "post.html").read_text()).substitute(
        metadata=metadata(post.title, post.description, post.path, post=post),
        title=escape(post.title),
        description=escape(post.description),
        published=post.published.isoformat(),
        date=display_date(post.published),
        updated=updated,
        minutes=post.minutes,
        notebook_head=(
            f'<link rel="stylesheet" title="marimo-islands" crossorigin="anonymous" href="https://cdn.jsdelivr.net/npm/@marimo-team/islands@{marimo.__version__}/dist/style.css">'
            '<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/katex@0.16.10/dist/katex.min.css">'
            '<script type="module" src="/notebook.js"></script>'
            if post.notebook_source
            else ""
        ),
        notebook_controls=(
            '<div class="notebook-controls">'
            '<p id="notebook-status" role="status">Explore this article with interactive controls.</p>'
            '<button type="button" id="notebook-start" hidden>Enable interactivity</button>'
            + (bundle_link or '<a href="source.py" download>Download notebook</a>')
            + "<noscript><p>Enable JavaScript to use the controls. You can read the saved results below.</p></noscript>"
            "</div>"
            "<marimo-filename hidden></marimo-filename>"
            if post.notebook_source
            else f'<div class="notebook-controls">{bundle_link}</div>'
            if bundle_link
            else ""
        ),
        content=post.html,
        references=references,
        related=related,
        year=year,
        tags='<p class="post-topics">'
        + " · ".join(escape(tag) for tag in post.tags)
        + "</p>"
        if post.tags
        else "",
        toc=f'<nav class="post-toc" aria-label="On this page"><p>On this page</p>{post.toc}</nav>'
        if post.toc
        else "",
    )


def share_image(title: str, *, article: bool = False) -> bytes:
    image = Image.new("RGB", (1200, 630), "#fcfdfb")
    draw = ImageDraw.Draw(image)
    draw.rectangle((0, 0, 1200, 10), fill="#2f6648")
    draw.text(
        (70, 60),
        "MCCLAIN THIEL / WRITING" if article else "MCCLAIN THIEL",
        font=ImageFont.load_default(size=24),
        fill="#2f6648",
    )
    for size in range(64, 23, -2):
        font = ImageFont.load_default(size=size)
        lines = [""]
        for word in title.split():
            candidate = (lines[-1] + " " + word).strip()
            if draw.textlength(candidate, font=font) > 1060 and lines[-1]:
                lines.append(word)
            else:
                lines[-1] = candidate
        if len(lines) <= 4 and all(
            draw.textlength(line, font=font) <= 1060 for line in lines
        ):
            break
    else:
        raise ValueError(f"Title is too long for its share image: {title}")
    draw.multiline_text(
        (70, 180), "\n".join(lines), font=font, fill="#17251d", spacing=14
    )
    draw.line((70, 530, 1130, 530), fill="#cbd6ce", width=2)
    draw.text(
        (70, 558),
        "mcclainthiel.com",
        font=ImageFont.load_default(size=24),
        fill="#647168",
    )
    buffer = BytesIO()
    image.save(buffer, format="PNG", optimize=True)
    return buffer.getvalue()


def rss_feed(posts: list[Post]) -> bytes:
    ET.register_namespace("atom", "http://www.w3.org/2005/Atom")
    root = ET.Element("rss", version="2.0")
    channel = ET.SubElement(root, "channel")
    for tag, value in {
        "title": "Writing — McClain Thiel",
        "link": SITE_URL + "/blog/",
        "description": BLOG_DESCRIPTION,
        "language": "en-gb",
    }.items():
        ET.SubElement(channel, tag).text = value
    ET.SubElement(
        channel,
        "{http://www.w3.org/2005/Atom}link",
        href=SITE_URL + "/feed.xml",
        rel="self",
        type="application/rss+xml",
    )
    for post in posts:
        item = ET.SubElement(channel, "item")
        for tag, value in {
            "title": post.title,
            "link": post.url,
            "description": post.description,
            "pubDate": format_datetime(
                datetime.combine(post.published, time(), tzinfo=timezone.utc),
                usegmt=True,
            ),
        }.items():
            ET.SubElement(item, tag).text = value
        ET.SubElement(item, "guid", isPermaLink="true").text = post.url
        for tag in post.tags:
            ET.SubElement(item, "category").text = tag
    return ET.tostring(root, encoding="utf-8", xml_declaration=True)


def favicon(image_format: str) -> bytes:
    image = Image.new("RGB", (96, 96), "#17251d")
    draw = ImageDraw.Draw(image)
    draw.text(
        (48, 48),
        "MT",
        anchor="mm",
        font=ImageFont.load_default(size=44),
        fill="#fcfdfb",
    )
    buffer = BytesIO()
    image.save(buffer, format=image_format)
    return buffer.getvalue()


def sitemap(posts: list[Post]) -> bytes:
    root = ET.Element("urlset", xmlns="http://www.sitemaps.org/schemas/sitemap/0.9")
    for path, modified in [("/", None), ("/blog/", None)] + [
        (post.path, post.modified) for post in posts
    ]:
        node = ET.SubElement(root, "url")
        ET.SubElement(node, "loc").text = SITE_URL + path
        if modified:
            ET.SubElement(node, "lastmod").text = modified.isoformat()
    return ET.tostring(root, encoding="utf-8", xml_declaration=True)


def redirect_page(path: str) -> str:
    return (
        f'<!doctype html><html lang="en"><head><meta charset="utf-8"><title>Writing — McClain Thiel</title>'
        f'<link rel="canonical" href="{SITE_URL}{path}"><meta http-equiv="refresh" content="0; url={path}">'
        f'</head><body><p>This page has moved to <a href="{path}">Writing</a>.</p></body></html>'
    )


def legacy_reader(posts: list[Post]) -> str:
    # GitHub Pages cannot issue query-dependent HTTP redirects. Only known public IDs redirect.
    destinations = json_script({post.slug: post.path for post in posts})
    return (
        '<!doctype html><html lang="en"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1">'
        '<meta name="robots" content="noindex, follow"><title>Writing — McClain Thiel</title></head>'
        '<body><p>Find articles in <a href="/blog/">Writing</a>.</p>'
        f'<script>const posts = {destinations}; const id = new URLSearchParams(location.search).get("id");'
        "if (Object.hasOwn(posts, id)) location.replace(posts[id] + location.hash);</script></body></html>"
    )


def build(source: Path, output: Path, today: date) -> int:
    posts = load_posts(source, today)
    files: dict[str, bytes] = {}

    def add(path: str, content: str | bytes) -> None:
        files[path] = content.encode("utf-8") if isinstance(content, str) else content

    add(
        "index.html",
        Template((source / "index.html").read_text()).substitute(
            metadata=metadata(
                "Machine Learning Researcher & Scientist",
                "McClain Thiel is a machine learning researcher and scientist interested in biology, research and medicine, a PhD student in the Barnes Lab, and a consultant at Databricks.",
                "/",
            ),
            year=today.year,
        ),
    )
    listing = (
        '<ul class="post-list">' + "".join(post_card(post) for post in posts) + "</ul>"
        if posts
        else (
            '<div class="blog-empty"><h2>New writing is on the way.</h2>'
            "<p>Research explainers and practical notes on AI and biology. "
            'For now, explore the <a href="/#publications">papers</a> or <a href="/#talks">talks and essays</a>.</p></div>'
        )
    )
    add(
        "blog/index.html",
        Template((source / "blog.html").read_text()).substitute(
            metadata=metadata("Writing on AI & Biology", BLOG_DESCRIPTION, "/blog/"),
            posts=listing,
            year=today.year,
        ),
    )
    for post in posts:
        add(
            f"blog/{post.slug}/index.html", render_post(source, post, posts, today.year)
        )
        add(f"blog/{post.slug}/share.png", share_image(post.title, article=True))
        if post.notebook_source:
            add(f"blog/{post.slug}/source.py", post.notebook_source)
        for name, content in post.attachments.items():
            add(f"blog/{post.slug}/{name}", content)
    for name in (
        "styles.css",
        "site.js",
        "notebook.css",
        "notebook.js",
        "CNAME",
        "og-image.svg",
    ):
        add(name, (source / name).read_bytes())
    assets = source / "blog/assets"
    if assets.is_symlink():
        raise ValueError("blog/assets must not be a symbolic link")
    if assets.exists():
        for path in assets.rglob("*"):
            if path.is_symlink():
                raise ValueError(f"Asset must not be a symbolic link: {path}")
            if path.is_file():
                add(path.relative_to(source).as_posix(), path.read_bytes())
    add("og-image.png", share_image("Research and practical notes on AI & biology"))
    add("favicon.png", favicon("PNG"))
    add("favicon.ico", favicon("ICO"))
    add("blog.html", redirect_page("/blog/"))
    add("post.html", legacy_reader(posts))
    add("feed.xml", rss_feed(posts))
    add("sitemap.xml", sitemap(posts))
    add("robots.txt", f"User-agent: *\nAllow: /\n\nSitemap: {SITE_URL}/sitemap.xml\n")
    add(".nojekyll", "")
    add(
        "404.html",
        '<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><meta name="robots" content="noindex"><title>Page not found — McClain Thiel</title><link rel="stylesheet" href="/styles.css"></head><body><main class="post-page"><header class="post-header"><h1>Page not found.</h1><p>This address doesn’t have a page. <a href="/blog/">Browse the writing</a> or <a href="/">go home</a>.</p></header></main></body></html>',
    )

    # Only replace files owned by an earlier build; never wipe an arbitrary directory.
    manifest = output / ".build-files.json"
    if output.is_symlink():
        raise ValueError(f"Output must not be a symbolic link: {output}")
    previous = json.loads(manifest.read_text()) if manifest.exists() else []
    if output.exists() and any(output.iterdir()) and not manifest.exists():
        raise ValueError(f"Refusing to overwrite non-build directory: {output}")
    for name in set(previous) | files.keys():
        path = output / name
        if not path.resolve().is_relative_to(output.resolve()) or path.is_symlink():
            raise ValueError(f"Unsafe generated path: {name}")
    for name, content in files.items():
        path = output / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
    for name in set(previous) - files.keys():
        path = output / name
        path.unlink()
        parent = path.parent
        while parent != output and not any(parent.iterdir()):
            parent.rmdir()
            parent = parent.parent
    manifest.write_text(json.dumps(sorted(files), indent=2) + "\n")
    return len(posts)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "_site")
    args = parser.parse_args()
    count = build(ROOT, args.output.absolute(), datetime.now(timezone.utc).date())
    print(f"Built {count} published articles into {args.output}")
