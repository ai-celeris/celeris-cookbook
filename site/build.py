#!/usr/bin/env python3
"""Build the Celeris Cookbook website.

Renders registry.yaml + each registered example README into a static site at
site/dist/. Deliberately boring: no framework, one pass, plain HTML output.

    python3 -m pip install -r site/requirements.txt
    python3 site/build.py
"""

import html
import json
import shutil
from datetime import date
from pathlib import Path

import markdown
import yaml

ROOT = Path(__file__).resolve().parent.parent
SITE = ROOT / "site"
DIST = SITE / "dist"
GITHUB_REPO = "https://github.com/ai-celeris/celeris-cookbook"

MARKDOWN_EXTENSIONS = ["fenced_code", "tables", "toc", "sane_lists"]

PAGE_TEMPLATE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
<meta name="description" content="{description}">
<link rel="stylesheet" href="{root}style.css">
<link rel="icon" href="data:image/svg+xml,<svg xmlns=%22http://www.w3.org/2000/svg%22 viewBox=%220 0 100 100%22><text y=%22.9em%22 font-size=%2290%22>&#9889;</text></svg>">
</head>
<body>
<header class="site-header">
  <a class="brand" href="{root}">Celeris Cookbook</a>
  <nav><a href="{github}">GitHub</a></nav>
</header>
<main>
{content}
</main>
<footer class="site-footer">
  <p>Celeris Cookbook &middot; <a href="{github}">Source on GitHub</a></p>
</footer>
{scripts}
</body>
</html>
"""

COPY_SCRIPT = """<script>
document.querySelectorAll("pre").forEach((pre) => {
  const button = document.createElement("button");
  button.className = "copy-button";
  button.textContent = "Copy";
  button.addEventListener("click", async () => {
    await navigator.clipboard.writeText(pre.querySelector("code")?.innerText ?? pre.innerText);
    button.textContent = "Copied";
    setTimeout(() => (button.textContent = "Copy"), 1500);
  });
  pre.appendChild(button);
});
</script>"""

INDEX_SCRIPT = """<script>
const cards = [...document.querySelectorAll(".card")];
const search = document.getElementById("search");
const chips = [...document.querySelectorAll(".tag-chip")];
const active = new Set();

function apply() {
  const query = search.value.trim().toLowerCase();
  for (const card of cards) {
    const text = card.dataset.text;
    const tags = card.dataset.tags.split(" ");
    const matchesQuery = !query || text.includes(query);
    const matchesTags = active.size === 0 || [...active].every((t) => tags.includes(t));
    card.hidden = !(matchesQuery && matchesTags);
  }
  document.getElementById("empty").hidden = cards.some((c) => !c.hidden);
}

search.addEventListener("input", apply);
for (const chip of chips) {
  chip.addEventListener("click", () => {
    const tag = chip.dataset.tag;
    if (active.has(tag)) { active.delete(tag); chip.classList.remove("active"); }
    else { active.add(tag); chip.classList.add("active"); }
    apply();
  });
}
</script>"""


def load_registry():
    registry = yaml.safe_load((ROOT / "registry.yaml").read_text()) or []
    authors = yaml.safe_load((ROOT / "authors.yaml").read_text()) or {}
    registry = [entry for entry in registry if not entry.get("archived")]
    registry.sort(key=lambda entry: entry["date"], reverse=True)
    return registry, authors


def author_html(username, authors):
    meta = authors.get(username) or {}
    name = meta.get("name", username)
    website = meta.get("website", f"https://github.com/{username}")
    return f'<a class="author" href="{html.escape(website)}">{html.escape(name)}</a>'


def format_date(value):
    if isinstance(value, date):
        return value.strftime("%b %Y")
    return html.escape(str(value))


def render_example(entry, authors):
    source = ROOT / entry["path"]
    body = markdown.markdown(source.read_text(), extensions=MARKDOWN_EXTENSIONS)
    authors_line = ", ".join(author_html(a, authors) for a in entry["authors"])
    tags_line = " ".join(
        f'<span class="tag">{html.escape(tag)}</span>' for tag in entry["tags"]
    )
    github_dir = f"{GITHUB_REPO}/tree/main/{Path(entry['path']).parent.as_posix()}"
    content = f"""<article class="example">
<div class="example-meta">
  <span class="date">{format_date(entry["date"])}</span>
  {tags_line}
</div>
{body}
<div class="example-footer">
  <p>By {authors_line} &middot; <a href="{github_dir}">View source on GitHub</a></p>
</div>
</article>"""
    page = PAGE_TEMPLATE.format(
        title=f"{html.escape(entry['title'])} · Celeris Cookbook",
        description=html.escape(entry["description"]),
        root="../",
        github=GITHUB_REPO,
        content=content,
        scripts=COPY_SCRIPT,
    )
    out = DIST / entry["slug"] / "index.html"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(page)


def render_index(registry, authors):
    all_tags = sorted({tag for entry in registry for tag in entry["tags"]})
    chips = "".join(
        f'<button class="tag-chip" data-tag="{html.escape(tag)}">{html.escape(tag)}</button>'
        for tag in all_tags
    )
    cards = []
    for entry in registry:
        text = " ".join(
            [entry["title"], entry["description"], " ".join(entry["tags"])]
        ).lower()
        tags_line = " ".join(
            f'<span class="tag">{html.escape(tag)}</span>' for tag in entry["tags"]
        )
        authors_line = ", ".join(author_html(a, authors) for a in entry["authors"])
        cards.append(
            f"""<a class="card" href="{entry["slug"]}/"
   data-text="{html.escape(text)}" data-tags="{html.escape(" ".join(entry["tags"]))}">
  <h2>{html.escape(entry["title"])}</h2>
  <p class="card-meta">{format_date(entry["date"])} &middot; {tags_line}</p>
  <p>{html.escape(entry["description"])}</p>
  <p class="card-authors">{authors_line}</p>
</a>"""
        )
    content = f"""<section class="hero">
  <h1>Celeris Cookbook</h1>
  <p>Practical, runnable examples for building with the Celeris API.</p>
</section>
<section class="controls">
  <input id="search" type="search" placeholder="Search examples&hellip;" autocomplete="off">
  <div class="tag-chips">{chips}</div>
</section>
<section class="cards">
{"".join(cards)}
</section>
<p id="empty" hidden>No examples match.</p>"""
    page = PAGE_TEMPLATE.format(
        title="Celeris Cookbook",
        description="Practical, runnable examples for building with the Celeris API.",
        root="",
        github=GITHUB_REPO,
        content=content,
        scripts=INDEX_SCRIPT,
    )
    (DIST / "index.html").write_text(page)


def render_404():
    content = """<section class="hero">
  <h1>Page not found</h1>
  <p>That page does not exist (or was renamed). <a href="/">Browse all examples</a>.</p>
</section>"""
    page = PAGE_TEMPLATE.format(
        title="Not found · Celeris Cookbook",
        description="Page not found.",
        root="/",
        github=GITHUB_REPO,
        content=content,
        scripts="",
    )
    (DIST / "404.html").write_text(page)


def main():
    if DIST.exists():
        shutil.rmtree(DIST)
    DIST.mkdir(parents=True)
    registry, authors = load_registry()
    for entry in registry:
        render_example(entry, authors)
    render_index(registry, authors)
    render_404()
    shutil.copy(SITE / "static" / "style.css", DIST / "style.css")
    manifest = [
        {"slug": entry["slug"], "title": entry["title"], "date": str(entry["date"])}
        for entry in registry
    ]
    (DIST / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(f"built {len(registry)} example page(s) -> {DIST}")


if __name__ == "__main__":
    main()
