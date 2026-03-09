#!/usr/bin/env python3

import argparse
import os
import re
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any

import markdown
import yaml
from jinja2 import Environment, FileSystemLoader, select_autoescape


REPO_ROOT = Path(__file__).resolve().parent.parent
TEMPLATE_DIR = REPO_ROOT / "templates"
BUILD_ROOT = REPO_ROOT / "build"
PUBLIC_BUILD_DIR = BUILD_ROOT / "public"
INTERNAL_BUILD_DIR = BUILD_ROOT / "internal"
ASSET_SOURCE_DIR = REPO_ROOT / "assets"
PUBLIC_ASSET_DIR = PUBLIC_BUILD_DIR / "assets"
INTERNAL_ASSET_DIR = INTERNAL_BUILD_DIR / "assets"
ROOT_PUBLIC_FILES = [REPO_ROOT / "logo.svg"]
WORDS_PER_MINUTE = 220

TEMPLATE_REGISTRY = {
    "news_article": {
        "template_file": "article.html",
        "extra_css": ["/assets/css/article.css"],
    },
    "home": {
        "template_file": "home.html",
        "extra_css": ["/assets/css/home.css"],
    },
    "page": {
        "template_file": "page.html",
        "extra_css": ["/assets/css/article.css"],
    },
    "games_landing": {
        "template_file": "games.html",
        "extra_css": ["/assets/css/games.css"],
    },
}


def strip_markdown_to_text(md_body: str) -> str:
    text = md_body
    text = re.sub(r"```.*?```", " ", text, flags=re.DOTALL)
    text = re.sub(r"`[^`]*`", " ", text)
    text = re.sub(r"!\[([^\]]*)\]\([^\)]*\)", r"\1", text)
    text = re.sub(r"\[([^\]]+)\]\([^\)]*\)", r"\1", text)
    text = re.sub(r"^\s{0,3}#{1,6}\s+", "", text, flags=re.MULTILINE)
    text = re.sub(r"^\s{0,3}>\s?", "", text, flags=re.MULTILINE)
    text = re.sub(r"^\s*[-*+]\s+", "", text, flags=re.MULTILINE)
    text = re.sub(r"^\s*\d+\.\s+", "", text, flags=re.MULTILINE)
    return re.sub(r"\s+", " ", text).strip()


def estimate_reading_time_minutes(text: str) -> tuple[int, int]:
    words = re.findall(r"\b[\w']+\b", text)
    word_count = len(words)
    if word_count == 0:
        return 0, 0
    minutes = max(1, (word_count + WORDS_PER_MINUTE - 1) // WORDS_PER_MINUTE)
    return word_count, minutes


def load_markdown_with_frontmatter(md_path: Path) -> tuple[dict[str, Any], str, str]:
    raw = md_path.read_text(encoding="utf-8")
    if not raw.startswith("---"):
        raise ValueError(f"{md_path.name} is missing YAML frontmatter")

    _, fm_text, body = raw.split("---", 2)
    frontmatter = yaml.safe_load(fm_text.strip()) or {}
    if not isinstance(frontmatter, dict):
        raise ValueError(f"{md_path.name} has invalid YAML frontmatter")

    md_body = body.strip()
    html_body = markdown.markdown(md_body, extensions=["extra", "smarty"])
    return frontmatter, md_body, html_body


def base_context(site_base_url: str) -> dict[str, Any]:
    site = {
        "base_url": site_base_url,
        "name": "The Lion's Roar",
        "tagline": "An Independent source of news for the discerning reader of Azeroth.",
        "edition_left": "",
        "edition_right": "",
        "edition_pill": "",
    }

    nav = [
        {"href": f"{site_base_url}/", "label": "Home"},
        {"href": f"{site_base_url}/news/", "label": "News"},
        {"href": f"{site_base_url}/opinion/", "label": "Opinion"},
        {"href": f"{site_base_url}/events/", "label": "Events"},
        {"href": f"{site_base_url}/games/", "label": "Games"},
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


def build_news_article_context(frontmatter: dict[str, Any], md_body: str, body_html: str, site_base_url: str) -> dict[str, Any]:
    authors = frontmatter.get("authors") or []
    if isinstance(authors, str):
        authors = [authors]

    tags = frontmatter.get("tags") or []
    tag_objs = []
    for tag in tags:
        label = str(tag).strip()
        if label:
            tag_objs.append({"label": label, "url": f"/tags/{label}/"})

    section = str(frontmatter.get("section", "")).strip()
    section_label = section.replace("-", " ").title() if section else ""
    plain_text = strip_markdown_to_text(md_body)
    word_count, reading_minutes = estimate_reading_time_minutes(plain_text)

    article = dict(frontmatter)
    article["html_body"] = body_html
    article["authors_display"] = ", ".join(str(author).strip() for author in authors if str(author).strip())
    publish_at_raw = str(frontmatter.get("publish_at", "")).strip()
    article["date_iso"] = publish_at_raw

    try:
        dt = datetime.strptime(publish_at_raw, "%d-%m-%Y %H:%M")
        article["date_display"] = dt.strftime("%d %B (%Y)")
    except ValueError:
        article["date_display"] = publish_at_raw

    article["tags"] = tag_objs
    article["section_label"] = section_label
    article["word_count"] = word_count
    article["reading_time_minutes"] = reading_minutes

    ctx = base_context(site_base_url)
    ctx.update(
        {
            "page_title": f"{article.get('title', 'Article')} | {ctx['site']['name']}",
            "article": article,
            "related": [],
            "latest": [],
            "section_url": f"/{section}/" if section else "/",
            "related_more_url": f"/{section}/" if section else "/",
            "discord_thread_url": None,
        }
    )
    return ctx


def build_page_context(frontmatter: dict[str, Any], body_html: str, site_base_url: str) -> dict[str, Any]:
    page = {
        "title": str(frontmatter.get("title") or "Page").strip(),
        "kicker": str(frontmatter.get("kicker") or "").strip(),
        "teaser": str(frontmatter.get("teaser") or "").strip(),
        "html_body": body_html,
    }

    ctx = base_context(site_base_url)
    ctx.update(
        {
            "page_title": f"{page['title']} | {ctx['site']['name']}",
            "page": page,
        }
    )
    return ctx


def build_games_landing_context(frontmatter: dict[str, Any], site_base_url: str) -> dict[str, Any]:
    games_raw = frontmatter.get("games") or []
    games = []
    for game in games_raw:
        if not isinstance(game, dict):
            continue
        games.append(
            {
                "href": str(game.get("href") or "#").strip(),
                "image_src": str(game.get("image_src") or "").strip(),
                "eyebrow": str(game.get("eyebrow") or "Arcade Cabinet").strip(),
                "title": str(game.get("title") or "Untitled game").strip(),
                "description": str(game.get("description") or "").strip(),
            }
        )

    ctx = base_context(site_base_url)
    ctx.update(
        {
            "page_title": f"{str(frontmatter.get('title') or 'Games').strip()} | {ctx['site']['name']}",
            "games_landing": {
                "kicker": str(frontmatter.get("kicker") or "").strip(),
                "title": str(frontmatter.get("title") or "Games").strip(),
                "intro": str(frontmatter.get("intro") or "").strip(),
            },
            "games": games,
        }
    )
    return ctx


def normalize_extra_css(site_base_url: str, paths: list[str]) -> list[str]:
    out: list[str] = []
    for path in paths:
        current = str(path).strip()
        if not current:
            continue
        if current.startswith(("http://", "https://")):
            out.append(current)
        elif current.startswith("/"):
            out.append(f"{site_base_url}{current}")
        else:
            out.append(f"{site_base_url}/{current}")
    return out


def render(template_file: str, context: dict[str, Any]) -> str:
    env = Environment(
        loader=FileSystemLoader(TEMPLATE_DIR),
        autoescape=select_autoescape(["html"]),
    )
    return env.get_template(template_file).render(**context)


def parse_publish_year(frontmatter: dict[str, Any], md_path: Path) -> str:
    publish_at_raw = str(frontmatter.get("publish_at", "")).strip()
    if publish_at_raw:
        for fmt in ("%d-%m-%Y %H:%M", "%Y-%m-%d %H:%M", "%Y-%m-%dT%H:%M"):
            try:
                return datetime.strptime(publish_at_raw, fmt).strftime("%Y")
            except ValueError:
                continue
    for part in md_path.parts:
        if len(part) == 4 and part.isdigit():
            return part
    return datetime.now().strftime("%Y")


def ensure_public_assets() -> None:
    for target in (PUBLIC_ASSET_DIR, INTERNAL_ASSET_DIR):
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists():
            shutil.rmtree(target)
        shutil.copytree(ASSET_SOURCE_DIR, target)

    for source in ROOT_PUBLIC_FILES:
        if not source.exists():
            continue
        shutil.copy2(source, PUBLIC_BUILD_DIR / source.name)


def compute_output_path(frontmatter: dict[str, Any], md_path: Path, mode: str) -> Path:
    explicit = str(frontmatter.get("output_path") or "").strip().lstrip("/")
    root = PUBLIC_BUILD_DIR if mode == "public" else INTERNAL_BUILD_DIR
    if explicit:
        target = root / explicit
        if target.suffix:
            return target
        return target / "index.html"

    template_key = str(frontmatter.get("template", "news_article")).strip() or "news_article"
    slug = str(frontmatter.get("id") or md_path.stem).strip()
    section = str(frontmatter.get("section") or "news").strip() or "news"
    year = parse_publish_year(frontmatter, md_path)

    if template_key == "home":
        return root / "index.html"

    if mode == "public":
        return PUBLIC_BUILD_DIR / section / year / slug / "index.html"
    return INTERNAL_BUILD_DIR / section / year / slug / "index.html"


def build(md_path: Path, mode: str = "public") -> Path:
    if mode not in {"public", "internal"}:
        raise ValueError("mode must be 'public' or 'internal'")

    site_base_url = os.getenv("SITE_BASE_URL", "")
    frontmatter, md_body, body_html = load_markdown_with_frontmatter(md_path)

    template_key = str(frontmatter.get("template", "news_article")).strip() or "news_article"
    spec = TEMPLATE_REGISTRY.get(template_key)
    if not spec:
        known = ", ".join(sorted(TEMPLATE_REGISTRY.keys()))
        raise ValueError(f"Unknown template '{template_key}'. Known: {known}")

    if template_key == "news_article":
        ctx = build_news_article_context(frontmatter, md_body, body_html, site_base_url)
    elif template_key == "page":
        ctx = build_page_context(frontmatter, body_html, site_base_url)
    elif template_key == "games_landing":
        ctx = build_games_landing_context(frontmatter, site_base_url)
    else:
        ctx = base_context(site_base_url)
        ctx.update({
            "page_title": f"{frontmatter.get('title', 'Page')} | {ctx['site']['name']}",
        })

    ctx["extra_css"] = normalize_extra_css(site_base_url, spec.get("extra_css", []))
    html = render(spec["template_file"], ctx)

    out_path = compute_output_path(frontmatter, md_path, mode)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(html, encoding="utf-8")

    print(f"Built -> {out_path.relative_to(REPO_ROOT)} (template={template_key}, mode={mode})")
    return out_path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("path", help="Path to a markdown file")
    parser.add_argument("--mode", choices=["public", "internal"], default="public")
    parser.add_argument("--sync-assets", action="store_true", help="Refresh build/public/assets and build/internal/assets first")
    args = parser.parse_args()

    md_file = Path(args.path)
    if not md_file.exists():
        print(f"File not found: {md_file}")
        return 1

    if args.sync_assets:
        ensure_public_assets()

    build(md_file, mode=args.mode)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
