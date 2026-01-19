#!/usr/bin/env python3

import os
import sys
from pathlib import Path

import yaml
import markdown
from jinja2 import Environment, FileSystemLoader, select_autoescape
import re


REPO_ROOT = Path(__file__).resolve().parent.parent
TEMPLATE_DIR = REPO_ROOT / "templates"
BUILD_DIR = REPO_ROOT / "build"


# Add new templates here later
TEMPLATE_REGISTRY = {
    # frontmatter template name -> template file + output subdir + css
    "news_article": {
        "template_file": "article.html",
        "output_subdir": "news",
        "extra_css": ["/assets/css/article.css"],
    },
    "home": {
        "template_file": "home.html",
        "output_subdir": "",
        "extra_css": ["/assets/css/home.css"],
    },
}

WORDS_PER_MINUTE = 220

def strip_markdown_to_text(md_body: str) -> str:
    text = md_body

    # Remove fenced code blocks and inline code
    text = re.sub(r"```.*?```", " ", text, flags=re.DOTALL)
    text = re.sub(r"`[^`]*`", " ", text)

    # Images: keep alt text
    text = re.sub(r"!\[([^\]]*)\]\([^\)]*\)", r"\1", text)

    # Links: keep link text
    text = re.sub(r"\[([^\]]+)\]\([^\)]*\)", r"\1", text)

    # Strip common markdown markers
    text = re.sub(r"^\s{0,3}#{1,6}\s+", "", text, flags=re.MULTILINE)
    text = re.sub(r"^\s{0,3}>\s?", "", text, flags=re.MULTILINE)
    text = re.sub(r"^\s*[-*+]\s+", "", text, flags=re.MULTILINE)
    text = re.sub(r"^\s*\d+\.\s+", "", text, flags=re.MULTILINE)

    # Collapse whitespace
    text = re.sub(r"\s+", " ", text).strip()
    return text


def estimate_reading_time_minutes(text: str) -> tuple[int, int]:
    words = re.findall(r"\b[\w']+\b", text)
    word_count = len(words)
    if word_count == 0:
        return 0, 0
    minutes = max(1, (word_count + WORDS_PER_MINUTE - 1) // WORDS_PER_MINUTE)
    return word_count, minutes



def load_markdown_with_frontmatter(md_path: Path):
    raw = md_path.read_text(encoding="utf-8")
    if not raw.startswith("---"):
        raise ValueError(f"{md_path.name} is missing YAML frontmatter")

    _, fm_text, body = raw.split("---", 2)
    frontmatter = yaml.safe_load(fm_text.strip()) or {}

    md_body = body.strip()
    html_body = markdown.markdown(md_body, extensions=["extra", "smarty"])
    return frontmatter, md_body, html_body


def base_context(site_base_url: str) -> dict:
    site = {
        "base_url": site_base_url,
        "name": "The Lion's Roar",
        "tagline": "Reporting from Stormwind and beyond",
        "edition_left": "",
        "edition_right": "",
        "edition_pill": "",
    }

    nav = [
        {"href": f"{site_base_url}/", "label": "Home"},
        {"href": f"{site_base_url}/news/", "label": "News"},
        {"href": f"{site_base_url}/opinion/", "label": "Opinion"},
        {"href": f"{site_base_url}/culture/", "label": "Culture"},
    ]

    footer_links = [
        {"href": f"{site_base_url}/about/", "label": "About"},
        {"href": f"{site_base_url}/contact/", "label": "Contact"},
        {"href": f"{site_base_url}/privacy/", "label": "Privacy"},
    ]

    return {
        "site": site,
        "nav": nav,
        "footer_links": footer_links,
        "ticker_items": [],
    }


def build_news_article_context(frontmatter: dict, md_body: str, body_html: str, site_base_url: str) -> dict:
    authors = frontmatter.get("authors") or []
    if isinstance(authors, str):
        authors = [authors]

    publish_at = str(frontmatter.get("publish_at", "")).strip()

    tags = frontmatter.get("tags") or []
    tag_objs = []
    for t in tags:
        t = str(t).strip()
        if t:
            tag_objs.append({"label": t, "url": f"/tags/{t}/"})

    section = str(frontmatter.get("section", "")).strip()
    section_label = section.replace("-", " ").title() if section else ""
    plain_text = strip_markdown_to_text(md_body)
    word_count, reading_minutes = estimate_reading_time_minutes(plain_text)

    article = dict(frontmatter)
    article["html_body"] = body_html
    article["authors_display"] = ", ".join(authors)
    article["date_iso"] = publish_at
    article["date_display"] = publish_at
    article["tags"] = tag_objs
    article["section_label"] = section_label
    article["word_count"] = word_count
    article["reading_time_minutes"] = reading_minutes


    ctx = base_context(site_base_url)
    ctx.update({
        "page_title": f"{article.get('title', 'Article')} | {ctx['site']['name']}",
        "article": article,

        # Safe defaults referenced by article.html
        "related": [],
        "latest": [],
        "section_url": f"/{section}/" if section else "/",
        "related_more_url": f"/{section}/" if section else "/",
        "discord_thread_url": None,
    })
    return ctx


def normalize_extra_css(site_base_url: str, paths: list[str]) -> list[str]:
    out = []
    for p in paths:
        p = str(p).strip()
        if not p:
            continue
        if p.startswith("http://") or p.startswith("https://"):
            out.append(p)
        elif p.startswith("/"):
            out.append(f"{site_base_url}{p}")
        else:
            out.append(f"{site_base_url}/{p}")
    return out


def render(template_file: str, context: dict) -> str:
    template_path = TEMPLATE_DIR / template_file
    if not template_path.exists():
        raise FileNotFoundError(f"Missing template: {template_path}")

    env = Environment(
        loader=FileSystemLoader(TEMPLATE_DIR),
        autoescape=select_autoescape(["html"]),
    )
    return env.get_template(template_file).render(**context)


def build(md_path: Path):
    site_base_url = os.getenv("SITE_BASE_URL", "")

    frontmatter, md_body, body_html = load_markdown_with_frontmatter(md_path)


    template_key = str(frontmatter.get("template", "news_article")).strip() or "news_article"
    spec = TEMPLATE_REGISTRY.get(template_key)
    if not spec:
        known = ", ".join(sorted(TEMPLATE_REGISTRY.keys()))
        raise ValueError(f"Unknown template '{template_key}'. Known: {known}")

    # Build context by template type
    if template_key == "news_article":
        ctx = build_news_article_context(frontmatter, md_body, body_html, site_base_url)
    else:
        # Placeholder for future template context builders
        ctx = base_context(site_base_url)
        ctx.update({
            "page_title": f"{frontmatter.get('title', 'Page')} | {ctx['site']['name']}",
        })

    # extra_css support (base.html must render it)
    ctx["extra_css"] = normalize_extra_css(site_base_url, spec.get("extra_css", []))

    html = render(spec["template_file"], ctx)

    out_dir = BUILD_DIR / spec["output_subdir"]
    out_dir.mkdir(parents=True, exist_ok=True)

    slug = frontmatter.get("id", md_path.stem)
    out_path = out_dir / f"{slug}.html"
    out_path.write_text(html, encoding="utf-8")

    print(f"Built -> {out_path.relative_to(REPO_ROOT)} (template={template_key})")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python scripts/build.py path/to/page.md")
        sys.exit(1)

    md_file = Path(sys.argv[1])
    if not md_file.exists():
        print(f"File not found: {md_file}")
        sys.exit(1)

    build(md_file)
