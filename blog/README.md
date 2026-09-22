# Blog posts

Create one folder per article. The build discovers it and publishes `/blog/<folder-name>/`; no registry entry is needed.

```text
blog/my-article/
  index.md          # Markdown, OR notebook.py for marimo
  data/
    results.csv
  assets/
    figure.png
```

Use exactly one entry file: `index.md` or `notebook.py`. The `data/` and `assets/` directories are optional and may contain subdirectories. Standalone `.md` and `.py` files directly in `blog/` still work. `README.md`, dotfiles, and article names beginning with `_` are ignored.

## Markdown

Put YAML front matter at the top of `index.md`:

```markdown
---
title: How to evaluate a DNA language model
description: A concise, accurate summary of the article's question and contribution.
date: 2026-09-20
draft: true
tags: [DNA language models, Evaluation]
references:
  - title: The source paper's full title
    url: https://doi.org/replace-with-the-real-doi
---

Start with the main finding or question.

## The method

Explain the method here.
```

## Marimo

Save a normal marimo notebook as `blog/my-article/notebook.py` and add article metadata to its PEP 723 script header. If marimo already created this header, add `[tool.blog]` to the existing block:

```python
# /// script
# requires-python = ">=3.13"
# dependencies = ["marimo==0.24.2"]
# [tool.blog]
# title = "How to evaluate a DNA language model"
# description = "An explanation with a small interactive experiment."
# date = "2026-09-20"
# draft = true
# tags = ["DNA language models", "Evaluation"]
# [[tool.blog.references]]
# title = "The source paper's full title"
# url = "https://doi.org/replace-with-the-real-doi"
# ///
```

Write the article in `mo.md(...)` cells; use `mo.ui.slider`, dropdowns, or other controls for small experiments. Define controls in one cell and read their `.value` in another. The article template supplies the title. Use `##` section headings; a single `#` heading matching the metadata title is also accepted and deduplicated. Keep section headings unique.

The build executes published notebooks and renders their initial text and outputs into HTML. Readers can then choose **Enable interactivity** to load marimo and Pyodide; calculations run in the browser without a Python server. Notebook code is hidden in the article. Each folder article has a **Download article + data** link containing its original source and bundled files. Markdown and notebooks use the same article template, fonts, reading width, and theme.

Declare additional packages in `dependencies`, preferably with exact versions. The build installs them in a separate uv environment; the original dependency header also reaches the browser runtime. Use packages compatible with both the build's Python 3.13 and Pyodide. Pure Python and supported scientific packages can work; native libraries without a WebAssembly build, GPU workloads, access to arbitrary files on your computer, and secret-bearing backend APIs need a different deployment.

The marimo islands API is still evolving, so the Python package and browser runtime are pinned together. In this version, move `app.setup` code into ordinary cells and remove disabled cells before publication; the build rejects those exporter cases rather than silently changing their behavior. Use final expressions or `mo.output` for article outputs. Notebook failures stop the build with the filename and cell error. Builds execute trusted repository code, so review imported notebooks before publishing. Do not include credentials in notebook source.

## Bundled data and images

Put small datasets in the article's `data/` folder and images in its `assets/` folder. The build copies both directories to the article's URL, preserving their paths. Markdown can use relative links:

```markdown
![Describe what the figure shows](assets/figure.png)
[Download the measurements](data/results.csv)
```

In a notebook cell, use the notebook directory to read the same file locally, during the site build, and in the browser:

```python
import csv
import marimo as mo

with (mo.notebook_dir() / "data/results.csv").open(encoding="utf-8") as source:
    results = list(csv.DictReader(source))
```

When a reader enables interactivity, the browser downloads bundled files, checks their hashes, and writes them into Python's virtual filesystem before running the article's cells. Slider changes reuse those files; they do not download them again. Files live in browser memory for that session. A missing or mismatched file produces an error. No platform-specific loader is needed in the notebook.

The ZIP download preserves the folder structure, including the original `index.md` or `notebook.py`. After extracting a notebook article, open it with `uv run marimo edit --sandbox path/to/notebook.py` to use its declared dependencies and bundled data.

All non-hidden files under a published article's `data/` and `assets/` directories are public and included in the ZIP. Other files beside the entry file are not published; symlinks in bundles are rejected. Drafts and future-dated articles publish none of their bundled files. Keep bundles small because all bundled files are downloaded into memory when interactivity starts. Large datasets can remain on an external host with browser-compatible access, or be reduced to a small precomputed sample.

## Publish and preview

Each entry file needs `title`, `description`, and `date`. Optional fields are `id` (override the folder name, or the filename for standalone articles), `updated`, `draft`, `tags`, and `references`. Dates use `YYYY-MM-DD`; reference URLs must be absolute HTTPS URLs. Use a lowercase, hyphen-separated folder name and keep its slug stable after publication.

Keep `draft: true` while writing. To preview a finished article, set it to `false`, use its actual publication date, and rebuild:

```sh
uv sync --frozen
uv run python build_site.py
uv run python -m http.server 8000 --directory _site
```

Visit `/blog/` or `/blog/<slug>/`. Rebuild after editing a file. Pushing the finished changes to `main` triggers the same build and deploys the resulting static site.

Drafts and future-dated articles are excluded from pages, bundled files, downloads, share images, RSS, sitemap, and redirects. Draft notebooks are not executed. Future dates require another build on or after that date; the site does not schedule builds automatically. The legacy shared `blog/assets/` directory is always public; use article folders for assets that should follow draft status. Add `updated` only after a substantive revision, preserving the original `date`.

The existing `posts.json` entries remain supported for older Markdown articles. Don't put metadata in both that registry and the source file. New articles should keep their metadata in the file.

## Content features

- Markdown fenced code, tables, footnotes, and heading anchors
- Automatic contents, reading time, author biography, references, and related articles
- Canonical URLs, structured data, and a generated PNG share image for both formats
- A shared RSS feed and sitemap
- Relative article images and data links, plus a ZIP download of each article folder

Use descriptive image alt text. Markdown supports image dimensions and lazy loading:

```markdown
![Describe what the figure shows](assets/figure.png){ width="1200" height="800" loading="lazy" decoding="async" }
```

Markdown may contain raw HTML because this is an author-controlled repository. Treat imported HTML as code to review before publishing.

## Research explainers

Lead with a direct answer or main finding, then explain the problem, evidence, method, limitations, and practical uses. Link claims to original sources. `references` produces prominent paper, repository, model, or dataset links and citations in the article's structured data.

The explainer is a blog article, not a duplicate scholarly publication. Keep the source paper's title and DOI accurate, and direct academic citations to that paper. No Scholar-specific paper metadata is added to blog explainers.
