# Blog Posts

This folder contains all your blog posts and metadata.

## How to Add a New Post

1. **Create a markdown file** in this directory (e.g., `my-new-post.md`)

2. **Write your post** using markdown syntax. For example:

```markdown
# My Post Title

This is the introduction to my post.

## Section Heading

Content goes here...
```

3. **Update `posts.json`** to register your new post. Add a new entry to the array:

```json
{
  "id": "my-new-post",
  "title": "My New Post Title",
  "date": "November 1, 2025",
  "file": "my-new-post.md"
}
```

**Important**: The `id` should be URL-friendly (lowercase, hyphens, no spaces)

## Post Order

Posts appear in the order they're listed in `posts.json`. Put newer posts at the top for reverse chronological order.

## Markdown Features Supported

- Headers (`#`, `##`, `###`)
- **Bold** and *italic* text
- Links: `[text](url)`
- Lists (ordered and unordered)
- Code blocks with syntax highlighting
- Blockquotes
- Images

## Example Structure

```
blog/
├── posts.json          # Metadata for all posts
├── first-post.md       # Your markdown files
├── second-post.md
└── third-post.md
```

