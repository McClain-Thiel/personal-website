# McClain Thiel — Personal Website

A static personal website with Markdown articles and interactive marimo notebooks at [mcclainthiel.com](https://mcclainthiel.com). A Python build renders article text and initial results before deployment. Notebook controls load Python through WebAssembly on demand.

## Run locally

```sh
uv sync --frozen
uv run python build_site.py
uv run python -m http.server 8000 --directory _site
```

Visit [localhost:8000](http://localhost:8000). Rebuild after editing content or templates. Serve `_site`, not the source directory.

## Structure

- `index.html`, `blog.html`, `post.html` — homepage, writing index, and article templates
- `build_site.py`, `render_notebook.py` — article discovery, Markdown/notebook rendering, metadata, share images, sitemap, RSS, and compatibility routes
- `styles.css`, `site.js` — shared appearance and theme switch
- `notebook.css`, `notebook.js` — shared article styling and the browser notebook runtime
- `blog/<article>/index.md` or `blog/<article>/notebook.py` — articles with inline metadata
- `blog/<article>/data/`, `blog/<article>/assets/` — optional bundled datasets and images
- `blog/*.md`, `blog/*.py`, `blog/posts.json`, `blog/assets/` — supported standalone articles and legacy shared assets
- `_site/` — generated output, ignored by Git

## Writing

Drop an article folder into `blog/`, containing either `index.md` with YAML front matter or `notebook.py` with `[tool.blog]` metadata. Include small datasets under `data/` and figures under `assets/`; notebooks can read them using `mo.notebook_dir()` both locally and in WebAssembly. Published folder articles include a ZIP download of their source and bundled files. See [the authoring guide](blog/README.md) for metadata, dependencies, and publishing rules. The existing welcome template and empty agent article remain drafts.

## Checks

```sh
uv run python -m unittest discover -s tests -v
```

Tests cover both article formats, bundled files and portable ZIP downloads, notebook execution and failures, metadata, structured data, links and anchors, feeds, draft exclusion, legacy routes, and rebuild cleanup. Notebook tests require network access for their declared dependencies and permission to open local kernel sockets.

## Deployment

Pull requests run the tests and build. Pushes to `main` and manual workflow runs deploy `_site` through GitHub's official Pages artifact workflow.

The repository's **Settings → Pages → Build and deployment → Source** is configured as **GitHub Actions**, with the custom domain `mcclainthiel.com` and HTTPS preserved. Keep that setting: publishing the source branch directly will not render these templates. The workflow replaces the previous, unused `gh-pages` publishing job. Local changes must still be committed and pushed before the new site is deployed.

After deployment, verify the domain in Google Search Console and Bing Webmaster Tools, then submit `https://mcclainthiel.com/sitemap.xml`. Those account-level steps are separate from this build. No analytics or third-party tracking is installed.

## Search and AI discovery

Published articles have static content, unique canonical URLs, descriptions, Open Graph/Twitter PNG previews, author profiles, honest publication/update dates, and BlogPosting/BreadcrumbList structured data. A sitemap, RSS feed, internal links, and permissive robots.txt support discovery. References are visible and represented in structured data. These features support crawling and attribution; indexing, rankings, and inclusion in AI answers are not guaranteed.
