import json
from datetime import date
from html.parser import HTMLParser
from pathlib import Path
import shutil
import tempfile
import unittest
from urllib.parse import unquote, urljoin, urlparse
import xml.etree.ElementTree as ET
from zipfile import ZipFile

from bs4 import BeautifulSoup

from PIL import Image

from build_site import ROOT, SITE_URL, build, load_posts


class Page(HTMLParser):
    def __init__(self, text: str) -> None:
        super().__init__()
        self.links: list[str] = []
        self.ids: list[str] = []
        self.h1s = 0
        self.meta: dict[str, str] = {}
        self.canonical = ""
        self.structured_data: list[dict] = []
        self.json_text: str | None = None
        self.feed(text)

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = dict(attrs)
        if tag == "h1":
            self.h1s += 1
        if "id" in values:
            self.ids.append(values["id"])
        if tag in {"a", "link"} and values.get("href"):
            self.links.append(values["href"])
        if tag in {"img", "script"} and values.get("src"):
            self.links.append(values["src"])
        if tag == "meta":
            self.meta[values.get("name", values.get("property", ""))] = values.get(
                "content", ""
            )
        if tag == "link" and values.get("rel") == "canonical":
            self.canonical = values["href"]
        if tag == "script" and values.get("type") == "application/ld+json":
            self.json_text = ""

    def handle_data(self, data: str) -> None:
        if self.json_text is not None:
            self.json_text += data

    def handle_endtag(self, tag: str) -> None:
        if tag == "script" and self.json_text is not None:
            self.structured_data.append(json.loads(self.json_text))
            self.json_text = None


class BuildTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.source = Path(self.temp.name) / "source"
        self.output = Path(self.temp.name) / "public"
        (self.source / "blog").mkdir(parents=True)
        for name in (
            "index.html",
            "blog.html",
            "post.html",
            "styles.css",
            "site.js",
            "notebook.css",
            "notebook.js",
            "CNAME",
            "og-image.svg",
        ):
            shutil.copyfile(ROOT / name, self.source / name)
        self.today = date(2026, 9, 17)
        self.records = [
            {
                "id": "test-article",
                "title": 'DNA & "models" <explained>',
                "description": 'An explanation with "quotes" & useful context.',
                "date": "2026-09-10",
                "updated": "2026-09-12",
                "file": "article.md",
                "tags": ["DNA", "ML"],
                "references": [
                    {
                        "title": "Original research",
                        "url": "https://doi.org/10.1234/example",
                    }
                ],
            },
            {
                "id": "private-draft",
                "title": "PRIVATE DRAFT",
                "date": "2026-09-01",
                "file": "draft.md",
                "draft": True,
            },
            {
                "id": "future-article",
                "title": "FUTURE ARTICLE",
                "date": "2027-01-01",
                "file": "future.md",
            },
        ]
        (self.source / "blog/article.md").write_text(
            "An introduction with a [paper](https://doi.org/10.1234/example).\n\n"
            "## The method\n\nA precise explanation.[^1]\n\n"
            '```python\nprint("<DNA>")\n```\n\n'
            "## The method\n\nAnother section with a [home link](/).\n\n"
            "| Model | Result |\n| --- | --- |\n| Baseline | 1 |\n\n"
            "[^1]: A source with supporting evidence.\n",
            encoding="utf-8",
        )
        (self.source / "blog/draft.md").write_text("PRIVATE DRAFT BODY")
        (self.source / "blog/future.md").write_text("FUTURE ARTICLE BODY")
        self.save_registry()

    def save_registry(self) -> None:
        (self.source / "blog/posts.json").write_text(json.dumps(self.records))

    def build(self) -> None:
        build(self.source, self.output, self.today)

    def test_static_article_metadata_and_structured_data_agree(self) -> None:
        self.build()
        text = (self.output / "blog/test-article/index.html").read_text()
        page = Page(text)
        self.assertEqual(page.h1s, 1)
        self.assertEqual(page.canonical, SITE_URL + "/blog/test-article/")
        self.assertEqual(page.meta["og:url"], page.canonical)
        self.assertEqual(page.meta["description"], self.records[0]["description"])
        article = next(
            node
            for node in page.structured_data[0]["@graph"]
            if node["@type"] == "BlogPosting"
        )
        self.assertEqual(article["headline"], self.records[0]["title"])
        self.assertEqual(article["datePublished"], "2026-09-10")
        self.assertEqual(article["dateModified"], "2026-09-12")
        self.assertEqual(article["author"]["name"], "McClain Thiel")
        self.assertIn('id="the-method"', text)
        self.assertIn('id="the-method_1"', text)
        self.assertIn("A precise explanation", text)
        self.assertIn("<table>", text)
        self.assertNotIn("fetch(", text)
        self.assertNotIn("marked.min.js", text)
        self.assertIn("Original research", text)
        with Image.open(self.output / "blog/test-article/share.png") as image:
            self.assertEqual(image.size, (1200, 630))
            self.assertEqual(image.format, "PNG")

    def test_drafts_and_scheduled_posts_never_enter_public_output(self) -> None:
        self.build()
        for path in self.output.rglob("*"):
            if path.is_file() and path.suffix in {".html", ".xml", ".json"}:
                text = path.read_text()
                self.assertNotIn("private-draft", text)
                self.assertNotIn("future-article", text)
                self.assertNotIn("PRIVATE DRAFT", text)
        self.assertFalse((self.output / "blog/posts.json").exists())
        self.assertFalse(list(self.output.rglob("*.md")))

    def test_feed_sitemap_and_legacy_route_use_canonical_urls(self) -> None:
        self.build()
        feed = ET.parse(self.output / "feed.xml")
        self.assertEqual(
            feed.findtext("channel/item/link"), SITE_URL + "/blog/test-article/"
        )
        self.assertEqual(feed.findtext("channel/item/title"), self.records[0]["title"])
        sitemap = ET.parse(self.output / "sitemap.xml")
        urls = [node.text for node in sitemap.findall(".//{*}loc")]
        self.assertEqual(
            urls,
            [SITE_URL + "/", SITE_URL + "/blog/", SITE_URL + "/blog/test-article/"],
        )
        self.assertEqual(sitemap.findtext(".//{*}lastmod"), "2026-09-12")
        self.assertIn(
            '"test-article": "/blog/test-article/"',
            (self.output / "post.html").read_text(),
        )
        self.assertIn("url=/blog/", (self.output / "blog.html").read_text())
        self.assertIn(
            f"Sitemap: {SITE_URL}/sitemap.xml", (self.output / "robots.txt").read_text()
        )

    def test_rebuild_removes_articles_that_become_drafts(self) -> None:
        self.build()
        self.records[0]["draft"] = True
        self.save_registry()
        self.build()
        self.assertFalse((self.output / "blog/test-article").exists())
        self.assertFalse(ET.parse(self.output / "feed.xml").findall("channel/item"))
        self.assertIn(
            "New writing is on the way", (self.output / "blog/index.html").read_text()
        )

    def test_all_generated_internal_links_and_anchors_resolve(self) -> None:
        self.build()
        for file in self.output.rglob("*.html"):
            page = Page(file.read_text())
            self.assertEqual(len(page.ids), len(set(page.ids)), file)
            base = SITE_URL + "/" + file.relative_to(self.output).as_posix()
            for link in page.links:
                target = urlparse(urljoin(base, link))
                if target.netloc != "mcclainthiel.com":
                    continue
                local = self.output / unquote(target.path).lstrip("/")
                if local.is_dir():
                    local /= "index.html"
                self.assertTrue(local.is_file(), f"{file}: broken link {link}")
                if target.fragment and local.suffix == ".html":
                    self.assertIn(
                        unquote(target.fragment),
                        Page(local.read_text()).ids,
                        f"{file}: {link}",
                    )

    def test_invalid_metadata_fails_loudly(self) -> None:
        cases = [
            ("id", "../../outside"),
            ("description", ""),
            ("date", "September 10, 2026"),
            ("updated", "2026-09-01"),
            ("file", "../index.html"),
            ("draft", "false"),
            ("tags", "DNA"),
            ("references", [{"title": "Bad URL", "url": "javascript:alert(1)"}]),
        ]
        original = self.records[0].copy()
        for field, value in cases:
            with self.subTest(field=field):
                self.records[0] = {**original, field: value}
                self.save_registry()
                with self.assertRaises(ValueError):
                    load_posts(self.source, self.today)
        self.records[0] = original
        self.records.append(original.copy())
        self.save_registry()
        with self.assertRaisesRegex(ValueError, "Duplicate"):
            load_posts(self.source, self.today)

    def test_extra_h1_and_empty_article_are_rejected(self) -> None:
        for content in ["", "# Another page title\n\nSome text"]:
            (self.source / "blog/article.md").write_text(content)
            with self.assertRaises(ValueError):
                load_posts(self.source, self.today)

    def test_publication_is_sorted_and_future_date_requires_a_later_build(self) -> None:
        self.records[2].update({"description": "A later article", "tags": ["DNA"]})
        self.save_registry()
        self.assertEqual(len(load_posts(self.source, self.today)), 1)
        later = load_posts(self.source, date(2027, 1, 1))
        self.assertEqual(
            [post.slug for post in later], ["future-article", "test-article"]
        )

    def test_real_registry_builds_with_complete_templates(self) -> None:
        build(ROOT, self.output, self.today)
        self.assertEqual(
            len(ET.parse(self.output / "feed.xml").findall("channel/item")),
            len(load_posts(ROOT, self.today)),
        )
        self.assertEqual(Page((self.output / "blog/index.html").read_text()).h1s, 1)
        self.assertNotIn("$metadata", (self.output / "index.html").read_text())

    def test_json_ld_cannot_be_closed_by_metadata(self) -> None:
        self.records[0]["title"] = "Example </script><script>bad()</script>"
        self.save_registry()
        self.build()
        text = (self.output / "blog/test-article/index.html").read_text()
        self.assertNotIn("<script>bad()", text)
        Page(text)

    def test_arbitrary_output_directory_is_protected(self) -> None:
        self.output.mkdir()
        (self.output / "important.txt").write_text("keep me")
        with self.assertRaisesRegex(ValueError, "non-build directory"):
            self.build()
        self.assertEqual((self.output / "important.txt").read_text(), "keep me")

    def test_drop_markdown_without_a_registry(self) -> None:
        self.records = []
        self.save_registry()
        for path in (self.source / "blog").glob("*.md"):
            path.unlink()
        (self.source / "blog/posts.json").unlink()
        (self.source / "blog/new-article.md").write_text(
            "---\ntitle: A dropped article\ndescription: Written directly in Markdown.\n"
            "date: 2026-09-10\ntags: [Methods]\n---\n\n"
            "An introduction.\n\n## Results\n\nA readable result.\n"
        )
        self.build()
        text = (self.output / "blog/new-article/index.html").read_text()
        self.assertIn("A readable result.", text)
        self.assertIn('href="/notebook.css"', text)
        self.assertNotIn('src="/notebook.js"', text)
        self.assertIn("new-article", (self.output / "sitemap.xml").read_text())

    def test_discovery_rejects_missing_ambiguous_or_duplicate_metadata(self) -> None:
        path = self.source / "blog/dropped.md"
        path.write_text("No metadata yet")
        with self.assertRaisesRegex(ValueError, "front matter"):
            load_posts(self.source, self.today)
        path.write_text("---\nid: test-article\ndate: 2026-09-10\ndraft: true\n---\n")
        with self.assertRaisesRegex(ValueError, "Duplicate"):
            load_posts(self.source, self.today)
        path.unlink()
        (self.source / "blog/article.md").write_text("---\ntitle: Ambiguous\n---\nText")
        with self.assertRaisesRegex(ValueError, "both"):
            load_posts(self.source, self.today)

    def test_draft_notebooks_are_never_executed(self) -> None:
        (self.source / "blog/private.py").write_text(
            '# /// script\n# [tool.blog]\n# title = "Private notebook"\n'
            '# date = "2026-09-10"\n# draft = true\n# ///\n'
            'raise RuntimeError("This notebook must not execute")\n'
        )
        self.build()
        self.assertFalse((self.output / "blog/private").exists())
        self.assertNotIn("Private notebook", (self.output / "feed.xml").read_text())

    def test_notebook_is_prerendered_with_download_and_runtime(self) -> None:
        shutil.copyfile(
            ROOT / "tests/fixtures/interactive.py", self.source / "blog/interactive.py"
        )
        self.build()
        text = (self.output / "blog/interactive/index.html").read_text()
        page = Page(text)
        self.assertEqual(page.h1s, 1)
        self.assertIn("The expected count is", text)
        self.assertIn("<strong>4</strong>", text)
        self.assertIn("<strong>4.12.3</strong>", text)
        self.assertIn('href="#a-small-experiment"', text)
        self.assertIn('src="/notebook.js"', text)
        self.assertIn("data-runtime=", text)
        self.assertIn("marimo-slider", text)
        self.assertIn('href="source.py"', text)
        self.assertIn(
            "app = marimo.App", (self.output / "blog/interactive/source.py").read_text()
        )
        self.assertEqual(page.canonical, SITE_URL + "/blog/interactive/")

    def test_notebook_errors_stop_publishing(self) -> None:
        notebook = (ROOT / "tests/fixtures/interactive.py").read_text()
        (self.source / "blog/broken.py").write_text(
            notebook.replace(
                'mo.md(f"The expected count is **{count.value * 2}**.")',
                'raise RuntimeError("Deliberate notebook failure")',
            )
        )
        with self.assertRaisesRegex(ValueError, "Deliberate notebook failure"):
            self.build()
        self.assertFalse(self.output.exists())

    def markdown_bundle(self, name: str = "bundled-note") -> Path:
        folder = self.source / "blog" / name
        (folder / "data").mkdir(parents=True)
        (folder / "assets").mkdir()
        (folder / "index.md").write_text(
            "---\ntitle: A bundled article\ndescription: An article with its own files.\n"
            "date: 2026-09-10\n---\n\n## Results\n\n"
            "![A diagram](assets/figure.svg)\n\n[Download the data](data/results.csv)\n"
        )
        (folder / "data/results.csv").write_text("sample,score\nalpha,0.1\n")
        (folder / "assets/figure.svg").write_text(
            '<svg xmlns="http://www.w3.org/2000/svg" width="20" height="20"><circle cx="10" cy="10" r="5" /></svg>'
        )
        return folder

    def test_markdown_folder_publishes_relative_assets_and_portable_archive(
        self,
    ) -> None:
        folder = self.markdown_bundle()
        (folder / "private-notes.txt").write_text("PRIVATE NOTES")
        (folder / "data/.env").write_text("PRIVATE SETTINGS")
        (folder / "data/binary.bin").write_bytes(bytes(range(256)))
        self.build()
        public = self.output / "blog/bundled-note"
        page = Page((public / "index.html").read_text())
        self.assertEqual(page.canonical, SITE_URL + "/blog/bundled-note/")
        for relative in ["data/results.csv", "assets/figure.svg", "data/binary.bin"]:
            self.assertEqual(
                (public / relative).read_bytes(), (folder / relative).read_bytes()
            )
        self.assertIn("article.zip", page.links)
        self.assertFalse((public / "private-notes.txt").exists())
        self.assertFalse((public / "data/.env").exists())
        with ZipFile(public / "article.zip") as archive:
            self.assertEqual(
                set(archive.namelist()),
                {
                    "bundled-note/index.md",
                    "bundled-note/data/results.csv",
                    "bundled-note/data/binary.bin",
                    "bundled-note/assets/figure.svg",
                },
            )
            self.assertEqual(
                archive.read("bundled-note/index.md"),
                (folder / "index.md").read_bytes(),
            )
        for relative in ["data/results.csv", "assets/figure.svg", "article.zip"]:
            self.assertIn(relative, page.links)

    def test_folder_notebook_reads_bundled_data_and_download_runs_independently(
        self,
    ) -> None:
        folder = self.source / "blog/data-article"
        shutil.copytree(ROOT / "tests/fixtures/data-article", folder)
        self.build()
        public = self.output / "blog/data-article"
        html = (public / "index.html").read_text()
        self.assertIn("<strong>4 samples</strong>", html)
        self.assertIn("β reference", html)
        self.assertIn("Accepted samples: <strong>3</strong>", html)
        self.assertIn('href="article.zip"', html)
        runtime = json.loads(
            BeautifulSoup(html, "html.parser").select_one("#notebook-runtime").string
        )
        self.assertTrue(runtime["wait_for_setup"])
        self.assertIn(
            "/blog/data-article/data/scoring%20rules.json", runtime["runtime_source"]
        )
        self.assertNotIn(str(folder), runtime["runtime_source"])
        download = Path(self.temp.name) / "download"
        (download / "blog").mkdir(parents=True)
        with ZipFile(public / "article.zip") as archive:
            archive.extractall(download / "blog")
        downloaded = load_posts(download, self.today)
        self.assertEqual(downloaded[0].slug, "data-article")
        self.assertIn("Accepted samples: <strong>3</strong>", downloaded[0].html)

    def test_folder_drafts_and_future_articles_publish_no_data_or_downloads(
        self,
    ) -> None:
        for slug, metadata in [
            ("private-bundle", "draft: true"),
            ("scheduled-bundle", "date: 2027-01-01"),
        ]:
            folder = self.markdown_bundle(slug)
            entry = folder / "index.md"
            entry.write_text(
                entry.read_text().replace(
                    "date: 2026-09-10",
                    f"date: 2026-09-10\n{metadata}"
                    if metadata.startswith("draft")
                    else metadata,
                )
            )
            (folder / "data/results.csv").write_text("PRIVATE BUNDLED DATA")
        self.build()
        for path in self.output.rglob("*"):
            if path.is_file():
                self.assertNotIn(b"PRIVATE BUNDLED DATA", path.read_bytes())
        self.assertFalse((self.output / "blog/private-bundle").exists())
        self.assertFalse((self.output / "blog/scheduled-bundle").exists())

    def test_rebuild_removes_stale_bundle_files_and_draft_archives(self) -> None:
        folder = self.markdown_bundle()
        (folder / "data/obsolete.json").write_text("[]")
        self.build()
        (folder / "data/obsolete.json").unlink()
        self.build()
        public = self.output / "blog/bundled-note"
        self.assertFalse((public / "data/obsolete.json").exists())
        with ZipFile(public / "article.zip") as archive:
            self.assertNotIn("bundled-note/data/obsolete.json", archive.namelist())
        entry = folder / "index.md"
        entry.write_text(
            entry.read_text().replace(
                "date: 2026-09-10", "date: 2026-09-10\ndraft: true"
            )
        )
        self.build()
        self.assertFalse(public.exists())

    def test_ambiguous_folder_and_asset_symlinks_fail_loudly(self) -> None:
        folder = self.markdown_bundle()
        (folder / "notebook.py").write_text("This should not execute")
        with self.assertRaisesRegex(ValueError, "exactly one"):
            self.build()
        (folder / "notebook.py").unlink()
        (folder / "data/external.csv").symlink_to(self.source / "blog/article.md")
        with self.assertRaisesRegex(ValueError, "symbolic link"):
            self.build()

    def test_missing_notebook_data_stops_the_build(self) -> None:
        folder = self.source / "blog/missing-data"
        shutil.copytree(ROOT / "tests/fixtures/data-article", folder)
        (folder / "data/results.csv").unlink()
        with self.assertRaisesRegex(ValueError, "results.csv"):
            self.build()
        self.assertFalse(self.output.exists())


if __name__ == "__main__":
    unittest.main()
