#!/usr/bin/env python3

import argparse
import json
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
CONTENT_NEWS_DIR = REPO_ROOT / "content" / "news"
SITE_CONFIG_FILE = REPO_ROOT / "content" / "config.yaml"
PUBLISHED_STATE_FILE = REPO_ROOT / "state" / "published.json"
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

DEFAULT_NAV_LINKS = [
    {"label": "Home", "href": "/"},
    {"label": "Games", "href": "/games/"},
]

DEFAULT_FOOTER_LINKS = [
    {"label": "About", "href": "/about/"},
    {"label": "Contact", "href": "/contact/"},
    {"label": "Privacy", "href": "/privacy/"},
    {"label": "Jobs", "href": "/jobs/"},
]

DEFAULT_HOME_EXPLORE_LINKS = [
    {"label": "About", "href": "/about/"},
    {"label": "Contact", "href": "/contact/"},
    {"label": "Privacy", "href": "/privacy/"},
    {"label": "Jobs", "href": "/jobs/"},
]


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
    raw = raw.lstrip("\ufeff")
    raw = raw.lstrip()
    if not raw.startswith("---"):
        raise ValueError(f"{md_path.name} is missing YAML frontmatter")

    _, fm_text, body = raw.split("---", 2)
    frontmatter = yaml.safe_load(fm_text.strip()) or {}
    if not isinstance(frontmatter, dict):
        raise ValueError(f"{md_path.name} has invalid YAML frontmatter")

    md_body = body.strip()
    html_body = markdown.markdown(md_body, extensions=["extra", "smarty"])
    return frontmatter, md_body, html_body


def load_site_config() -> dict[str, Any]:
    if not SITE_CONFIG_FILE.exists():
        return {}
    try:
        data = yaml.safe_load(SITE_CONFIG_FILE.read_text(encoding="utf-8")) or {}
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def parse_publish_datetime(value: Any) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value

    text = str(value).strip()
    if not text:
        return None

    for fmt in ("%d-%m-%Y %H:%M", "%Y-%m-%d %H:%M", "%Y-%m-%dT%H:%M"):
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            continue
    return None


def format_publish_display(dt: datetime | None, raw_value: str) -> str:
    if not dt:
        return raw_value
    return dt.strftime("%d %B (%Y)")


def make_excerpt(text: str, limit: int = 180) -> str:
    current = text.strip()
    if len(current) <= limit:
        return current
    trimmed = current[:limit].rsplit(" ", 1)[0].strip()
    return f"{trimmed}..."


def coerce_int(value: Any, default: int) -> int:
    try:
        return max(0, int(value))
    except (TypeError, ValueError):
        return default


def normalize_href(site_base_url: str, href: str) -> str:
    current = str(href or "").strip()
    if not current:
        return ""
    if current.startswith(("http://", "https://")):
        return current
    if current.startswith("/"):
        return f"{site_base_url}{current}" if site_base_url else current
    return f"{site_base_url}/{current}" if site_base_url else f"/{current}"


def normalize_link_items(raw_items: Any, site_base_url: str, default_items: list[dict[str, str]]) -> list[dict[str, str]]:
    source_items = raw_items if isinstance(raw_items, list) else default_items

    links: list[dict[str, str]] = []
    for item in source_items:
        if not isinstance(item, dict):
            continue
        label = str(item.get("label") or "").strip()
        href = normalize_href(site_base_url, str(item.get("href") or "").strip())
        if label and href:
            links.append({"label": label, "href": href})
    return links


def output_path_to_url(output_path: Path, root: Path, site_base_url: str) -> str:
    rel = output_path.relative_to(root).as_posix()
    if rel in {"index.html", "index.php"}:
        url = "/"
    elif rel.endswith("/index.html") or rel.endswith("/index.php"):
        url = f"/{rel.rsplit('/index.', 1)[0]}/"
    else:
        url = f"/{rel}"
    return f"{site_base_url}{url}" if site_base_url else url


def base_context(site_base_url: str) -> dict[str, Any]:
    site_config = load_site_config()
    link_config = site_config.get("links") if isinstance(site_config.get("links"), dict) else {}

    site = {
        "base_url": site_base_url,
        "name": "The Lion's Roar",
        "tagline": "An Independent source of news for the discerning reader of Azeroth.",
        "edition_left": "",
        "edition_right": "",
        "edition_pill": "",
    }

    nav = normalize_link_items(link_config.get("nav"), site_base_url, DEFAULT_NAV_LINKS)
    footer_links = normalize_link_items(link_config.get("footer"), site_base_url, DEFAULT_FOOTER_LINKS)

    explore_links = normalize_link_items(link_config.get("explore"), site_base_url, DEFAULT_HOME_EXPLORE_LINKS)

    return {
        "site": site,
        "nav": nav,
        "footer_links": footer_links,
        "explore_links": explore_links,
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
    publish_at_raw = str(frontmatter.get("publish_at", "")).strip()
    publish_dt = parse_publish_datetime(publish_at_raw)

    article = dict(frontmatter)
    article["html_body"] = body_html
    article["authors_display"] = ", ".join(str(author).strip() for author in authors if str(author).strip())
    article["date_iso"] = publish_dt.isoformat() if publish_dt else publish_at_raw
    article["date_display"] = format_publish_display(publish_dt, publish_at_raw)
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


def load_published_state() -> dict[str, Any]:
    if not PUBLISHED_STATE_FILE.exists():
        return {}
    try:
        data = json.loads(PUBLISHED_STATE_FILE.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def iter_article_files(root: Path) -> list[Path]:
    if not root.exists():
        return []
    return sorted(
        path for path in root.rglob("*.md")
        if all(not part.startswith("_") and not part.startswith(".") for part in path.relative_to(root).parts)
    )


def article_is_public(frontmatter: dict[str, Any], article_id: str, published_state: dict[str, Any]) -> bool:
    if article_id in published_state:
        return True

    status = str(frontmatter.get("status") or "draft").strip().lower()
    return status == "published"


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


def build_article_summary(frontmatter: dict[str, Any], md_body: str, md_path: Path, site_base_url: str) -> dict[str, Any]:
    authors = frontmatter.get("authors") or []
    if isinstance(authors, str):
        authors = [authors]

    article_id = str(frontmatter.get("id") or md_path.stem).strip()
    publish_at_raw = str(frontmatter.get("publish_at") or "").strip()
    publish_dt = parse_publish_datetime(publish_at_raw)
    plain_text = strip_markdown_to_text(md_body)
    teaser = str(frontmatter.get("teaser") or "").strip() or make_excerpt(plain_text)
    image = frontmatter.get("image") if isinstance(frontmatter.get("image"), dict) else {}
    output_path = compute_output_path(frontmatter, md_path, mode="public")
    word_count, reading_minutes = estimate_reading_time_minutes(plain_text)

    return {
        "id": article_id,
        "title": str(frontmatter.get("title") or article_id).strip(),
        "kicker": str(frontmatter.get("kicker") or "").strip(),
        "teaser": teaser,
        "authors_display": ", ".join(str(author).strip() for author in authors if str(author).strip()),
        "date_iso": publish_dt.isoformat() if publish_dt else publish_at_raw,
        "date_display": format_publish_display(publish_dt, publish_at_raw),
        "image": {
            "src": str(image.get("src") or "").strip(),
            "url": normalize_href(site_base_url, str(image.get("src") or "").strip()),
            "credit": str(image.get("credit") or "").strip(),
            "source": str(image.get("source") or "").strip(),
        },
        "url": output_path_to_url(output_path, PUBLIC_BUILD_DIR, site_base_url),
        "word_count": word_count,
        "reading_time_minutes": reading_minutes,
        "_sort_timestamp": publish_dt.timestamp() if publish_dt else 0,
    }


def collect_public_articles(site_base_url: str) -> list[dict[str, Any]]:
    published_state = load_published_state()
    articles: list[dict[str, Any]] = []

    for md_path in iter_article_files(CONTENT_NEWS_DIR):
        frontmatter, md_body, _ = load_markdown_with_frontmatter(md_path)
        article_id = str(frontmatter.get("id") or md_path.stem).strip()
        if not article_is_public(frontmatter, article_id, published_state):
            continue
        articles.append(build_article_summary(frontmatter, md_body, md_path, site_base_url))

    articles.sort(key=lambda article: (article.get("_sort_timestamp", 0), article.get("id", "")), reverse=True)
    return articles


def normalize_home_modules(raw_items: Any, site_base_url: str) -> list[dict[str, str]]:
    if not isinstance(raw_items, list):
        return []

    modules: list[dict[str, str]] = []
    for item in raw_items:
        if not isinstance(item, dict):
            continue
        title = str(item.get("title") or "").strip()
        text = str(item.get("text") or "").strip()
        href = normalize_href(site_base_url, str(item.get("href") or "").strip())
        cta = str(item.get("cta") or "Open").strip() if href else ""
        if title or text or href:
            modules.append({
                "title": title,
                "text": text,
                "href": href,
                "cta": cta,
            })
    return modules


def build_home_context(frontmatter: dict[str, Any], site_base_url: str) -> dict[str, Any]:
    articles = collect_public_articles(site_base_url)
    site_config = load_site_config()
    link_config = site_config.get("links") if isinstance(site_config.get("links"), dict) else {}
    secondary_count = coerce_int(frontmatter.get("secondary_count"), 4)
    recent_count = coerce_int(frontmatter.get("recent_count"), 6)
    archive_count = coerce_int(frontmatter.get("archive_count"), 6)

    lead_article = articles[0] if articles else {
        "title": str(frontmatter.get("empty_title") or "The presses are quiet for the moment.").strip(),
        "kicker": "",
        "teaser": str(frontmatter.get("empty_teaser") or "When the next report is published, it will appear here automatically.").strip(),
        "authors_display": "",
        "date_iso": "",
        "date_display": "",
        "image": {"src": "", "url": "", "credit": "", "source": ""},
        "url": normalize_href(site_base_url, "/about/"),
        "word_count": 0,
        "reading_time_minutes": 0,
        "_sort_timestamp": 0,
    }

    secondary_articles = articles[1 : 1 + secondary_count]
    remaining_articles = articles[1 + secondary_count :]
    recent_articles = remaining_articles[:recent_count] if remaining_articles else articles[1 : 1 + recent_count]
    archive_articles = remaining_articles[recent_count : recent_count + archive_count] if remaining_articles else []

    home = {
        "kicker": str(frontmatter.get("kicker") or "The Latest Edition").strip(),
        "title": str(frontmatter.get("title") or "The Lion's Roar").strip(),
        "intro": str(frontmatter.get("intro") or frontmatter.get("teaser") or "").strip(),
        "about_text": str(frontmatter.get("about_text") or "The Lion's Roar chronicles the roleplaying life of Azeroth through reports, features, and curious notices from around the realm.").strip(),
        "lead_article": lead_article,
        "secondary_articles": secondary_articles,
        "recent_articles": recent_articles,
        "archive_articles": archive_articles,
        "secondary_title": str(frontmatter.get("secondary_title") or "More Stories").strip(),
        "recent_title": str(frontmatter.get("recent_title") or "Recent Articles").strip(),
        "archive_title": str(frontmatter.get("archive_title") or "Earlier Editions").strip(),
        "recent_empty_text": str(frontmatter.get("recent_empty_text") or "Recent articles will appear here once more reports have been published.").strip(),
        "explore_links": normalize_link_items(link_config.get("explore"), site_base_url, DEFAULT_HOME_EXPLORE_LINKS),
        "modules": normalize_home_modules(frontmatter.get("modules"), site_base_url),
        "has_articles": bool(articles),
    }

    ctx = base_context(site_base_url)
    page_title = home["title"] if home["title"] == ctx["site"]["name"] else f"{home['title']} | {ctx['site']['name']}"
    ctx.update(
        {
            "page_title": page_title,
            "home": home,
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
    elif template_key == "home":
        ctx = build_home_context(frontmatter, site_base_url)
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