# McClain Thiel — Personal Website

A dependency-free personal website and small Markdown blog, published at [mcclainthiel.com](https://mcclainthiel.com).

## Structure

- `index.html` — résumé-first homepage
- `blog.html` — blog index
- `post.html` — Markdown post reader
- `styles.css` — shared visual system and responsive styles
- `site.js` — shared theme behavior
- `blog/posts.json` — blog post registry
- `blog/*.md` — blog post content

## Run locally

The blog loads content with `fetch`, so preview the site through a local server rather than opening the HTML files directly:

```sh
python3 -m http.server 8000
```

Then visit [localhost:8000](http://localhost:8000).

## Add a blog post

Create a Markdown file in `blog/`, then add its title, date, ID, and filename to `blog/posts.json`. Posts appear in the order listed.

## Deployment

Pushes to `main` deploy the static files to GitHub Pages through `.github/workflows/deploy.yml`. No package installation or build step is required.
