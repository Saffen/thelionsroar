import json
import os
import shutil
import subprocess
import sys
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

import markdown
import yaml
from fastapi import FastAPI, File, Form, HTTPException, Query, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from slugify import slugify


ALLOWED_IP = "192.168.0.1"
ALLOWED_IP = "192.168.0.1"
API_ROOT = Path(__file__).resolve().parent
APP_ROOT = API_ROOT.parent
CONTENT_ROOT = APP_ROOT / "content" / "news"
STATE_ROOT = APP_ROOT / "state"
ASSETS_ROOT = APP_ROOT / "assets"
DATA_FILE = API_ROOT / 'data' / 'widgets.yaml'
SITE_CONFIG_FILE = APP_ROOT / 'content' / 'config.yaml'
ARTICLE_LOG_ROOT = STATE_ROOT / "article-log"
PUBLISHED_STATE_FILE = STATE_ROOT / "published.json"
PUBLIC_BUILD_ROOT = APP_ROOT / "build" / "public"
SCRIPTS_ROOT = APP_ROOT / "scripts"
BUILD_SCRIPT = SCRIPTS_ROOT / "build.py"
BUILD_PAGES_SCRIPT = SCRIPTS_ROOT / "build_pages.py"
ANNOUNCE_DISCORD_SCRIPT = SCRIPTS_ROOT / "announce_discord.py"
ALLOWED_STATUSES = {"draft", "build", "scheduled", "published", "deleted"}
ACTION_TO_STATUS = {
    "save_draft": "draft",
    "save_build": "build",
    "schedule": "scheduled",
    "publish_now": "published",
    "update_published": "published",
    "save_scheduled_changes": "scheduled",
}

app = FastAPI(title="The Lion's Roar API", redirect_slashes=False)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


def utc_now_iso() -> str:
    return (
        datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


def load_site_config() -> dict[str, Any]:
    if not SITE_CONFIG_FILE.exists():
        return {}
    try:
        with open(SITE_CONFIG_FILE, "r", encoding="utf-8") as handle:
            data = yaml.safe_load(handle) or {}
            return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def normalize_shared_links(value: Any, default: list[dict[str, str]]) -> list[dict[str, str]]:
    items = value if isinstance(value, list) else default
    out: list[dict[str, str]] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        label = str(item.get("label") or "").strip()
        href = str(item.get("href") or "").strip()
        if label and href:
            out.append({"label": label, "href": href})
    return out


def load_data() -> dict[str, Any]:
    if not DATA_FILE.exists():
        data: dict[str, Any] = {"zones": {}}
    else:
        with open(DATA_FILE, "r", encoding="utf-8") as handle:
            data = yaml.safe_load(handle) or {"zones": {}}
            if not isinstance(data, dict):
                data = {"zones": {}}

    site_config = load_site_config()
    link_config = site_config.get("links") if isinstance(site_config.get("links"), dict) else {}
    explore_links = normalize_shared_links(
        link_config.get("explore"),
        [
            {"label": "About", "href": "/about/"},
            {"label": "Contact", "href": "/contact/"},
            {"label": "Privacy", "href": "/privacy/"},
            {"label": "Jobs", "href": "/jobs/"},
        ],
    )

    zones = data.get("zones") if isinstance(data.get("zones"), dict) else {}
    for widgets in zones.values():
        if not isinstance(widgets, list):
            continue
        for widget in widgets:
            if not isinstance(widget, dict):
                continue
            if widget.get("id") == "nav-widget" and widget.get("type") == "navigation":
                widget["title"] = str(widget.get("title") or "Explore")
                widget["data"] = explore_links

    data["zones"] = zones
    return data


def load_published_state() -> dict[str, Any]:
    if not PUBLISHED_STATE_FILE.exists():
        return {}

    try:
        with open(PUBLISHED_STATE_FILE, "r", encoding="utf-8") as handle:
            data = json.load(handle)
            return data if isinstance(data, dict) else {}
    except Exception as exc:
        print(f"Error loading published.json: {exc}")
        return {}


def save_published_state(state: dict[str, Any]) -> None:
    STATE_ROOT.mkdir(parents=True, exist_ok=True)
    PUBLISHED_STATE_FILE.write_text(
        json.dumps(state, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def normalize_discord_state(value: Any) -> dict[str, Any]:
    discord_state = value if isinstance(value, dict) else {}
    forum_state = discord_state.get("forum") if isinstance(discord_state.get("forum"), dict) else None
    announce_state = discord_state.get("announce") if isinstance(discord_state.get("announce"), dict) else None
    return {"forum": forum_state, "announce": announce_state}


def normalize_discord_bot_auth(bot_token: str) -> str:
    token = str(bot_token or "").strip()
    if not token:
        return ""
    if token.lower().startswith("bot ") or token.lower().startswith("bearer "):
        return token
    return f"Bot {token}"


def article_is_live_public(status: str, article_id: str, published_state: dict[str, Any]) -> bool:
    if status == "deleted":
        return False
    return article_id in published_state or status == "published"


def ensure_live_state_entry(article: dict[str, Any], published_state: dict[str, Any]) -> bool:
    article_id = str(article.get("id") or "").strip()
    if not article_id:
        return False

    existing = published_state.get(article_id)
    entry = existing if isinstance(existing, dict) else {}
    before = json.dumps(entry, sort_keys=True, ensure_ascii=False)

    discord_state = normalize_discord_state(entry.get("discord"))
    normalized = {
        "path": article.get("filename") or entry.get("path") or "",
        "title": article.get("title") or entry.get("title") or article_id,
        "section": article.get("section") or entry.get("section") or "news",
        "publish_at": publish_at_to_storage(article.get("publish_at")) or entry.get("publish_at") or "",
        "recorded_at": entry.get("recorded_at") or utc_now_iso(),
        "discord": discord_state,
    }
    if entry.get("discord_last_action"):
        normalized["discord_last_action"] = entry.get("discord_last_action")

    after = json.dumps(normalized, sort_keys=True, ensure_ascii=False)
    published_state[article_id] = normalized
    return before != after or existing is None


def remove_live_state_entry(article_id: str, published_state: dict[str, Any]) -> bool:
    article_key = str(article_id or "").strip()
    if not article_key or article_key not in published_state:
        return False
    del published_state[article_key]
    return True


def iter_article_source_files() -> list[Path]:
    if not CONTENT_ROOT.exists():
        return []
    return sorted(
        path for path in CONTENT_ROOT.rglob("*.md")
        if "_history" not in path.parts
        and all(not part.startswith("_") and not part.startswith(".") for part in path.relative_to(CONTENT_ROOT).parts)
    )


def parse_publish_year_from_article(article: dict[str, Any]) -> str:
    publish_dt = parse_publish_at(article.get("publish_at"))
    if publish_dt:
        return publish_dt.strftime("%Y")

    filename = str(article.get("filename") or "")
    for part in Path(filename).parts:
        if len(part) == 4 and part.isdigit():
            return part
    return datetime.now().strftime("%Y")


def public_output_path_for_article(article: dict[str, Any]) -> Path:
    section = str(article.get("section") or "news").strip() or "news"
    slug = str(article.get("id") or "untitled").strip() or "untitled"
    year = parse_publish_year_from_article(article)
    return PUBLIC_BUILD_ROOT / section / year / slug / "index.html"


def remove_public_output(article: dict[str, Any]) -> str:
    target = public_output_path_for_article(article)
    resolved = target.resolve()
    build_root = PUBLIC_BUILD_ROOT.resolve()
    if not resolved.is_relative_to(build_root):
        raise RuntimeError(f"Refusing to remove output outside public build root: {resolved}")

    if resolved.parent.exists():
        shutil.rmtree(resolved.parent)
        return str(resolved.parent)
    if resolved.exists():
        resolved.unlink()
        return str(resolved)
    return ""


def run_project_script(script_path: Path, *args: str) -> str:
    if not script_path.exists():
        raise RuntimeError(f"Required script is missing: {script_path}")

    result = subprocess.run(
        [sys.executable, str(script_path), *args],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        detail = (result.stderr or result.stdout or "").strip()
        raise RuntimeError(
            f"{script_path.name} failed with exit code {result.returncode}. {detail}".strip()
        )
    return (result.stdout or "").strip()


def build_single_article(article_path: Path, mode: str) -> str:
    return run_project_script(BUILD_SCRIPT, str(article_path), "--mode", mode)


def rebuild_public_pages() -> str:
    return run_project_script(BUILD_PAGES_SCRIPT, "--mode", "public")


def rebuild_live_public_articles(published_state: dict[str, Any]) -> dict[str, int]:
    built_articles = 0
    removed_outputs = 0

    for article_path in iter_article_source_files():
        try:
            article = load_article(article_path, published_state=published_state, include_details=False)
        except Exception:
            continue

        if article_is_live_public(article["status"], article["id"], published_state):
            build_single_article(article_path, "public")
            built_articles += 1
        else:
            if remove_public_output(article):
                removed_outputs += 1

    return {
        "built_articles": built_articles,
        "removed_outputs": removed_outputs,
    }


def refresh_public_site(published_state: dict[str, Any]) -> dict[str, int]:
    result = rebuild_live_public_articles(published_state)
    rebuild_public_pages()
    return result


def normalize_asset_url(site_base_url: str, src: str) -> str:
    path = str(src or "").strip()
    if not path:
        return ""
    if path.startswith(("http://", "https://")):
        return path
    if not site_base_url:
        return ""
    base = site_base_url.rstrip("/")
    if path.startswith("/"):
        return f"{base}{path}"
    return f"{base}/{path}"


def build_public_article_url(article: dict[str, Any]) -> str:
    site_base = (os.environ.get("SITE_BASE_URL") or "").strip().rstrip("/")
    if not site_base:
        return ""
    section = str(article.get("section") or "news").strip() or "news"
    year = parse_publish_year_from_article(article)
    slug = str(article.get("id") or "untitled").strip() or "untitled"
    return f"{site_base}/{section}/{year}/{slug}/"


def webhook_post(
    webhook_url: str,
    payload: dict[str, Any],
    thread_id: str = "",
    wait: bool = True,
    username: str = "",
    avatar_url: str = "",
) -> dict[str, Any]:
    parsed = urllib.parse.urlparse(webhook_url)
    query = urllib.parse.parse_qs(parsed.query)

    if wait:
        query["wait"] = ["true"]
    if thread_id.strip():
        query["thread_id"] = [thread_id.strip()]

    post_url = urllib.parse.urlunparse(parsed._replace(query=urllib.parse.urlencode(query, doseq=True)))

    body = dict(payload)
    if username.strip():
        body["username"] = username.strip()
    if avatar_url.strip():
        body["avatar_url"] = avatar_url.strip()

    data = json.dumps(body).encode("utf-8")
    request = urllib.request.Request(
        post_url,
        data=data,
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": "LionsRoarAdmin/0.1 (+https://thelionsroar.eu)",
            "Connection": "close",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=25) as response:
            raw = response.read().decode("utf-8", errors="replace").strip()
            return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Discord webhook HTTP {exc.code}: {raw}") from exc


def webhook_channel_id(webhook_url: str) -> str:
    request = urllib.request.Request(
        webhook_url,
        headers={
            "Accept": "application/json",
            "User-Agent": "LionsRoarAdmin/0.1 (+https://thelionsroar.eu)",
            "Connection": "close",
        },
        method="GET",
    )

    try:
        with urllib.request.urlopen(request, timeout=25) as response:
            raw = response.read().decode("utf-8", errors="replace").strip()
            data = json.loads(raw) if raw else {}
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Discord webhook lookup HTTP {exc.code}: {raw}") from exc

    channel_id = str(data.get("channel_id") or "").strip() if isinstance(data, dict) else ""
    if not channel_id:
        raise RuntimeError("Discord webhook lookup response did not include a channel id.")
    return channel_id


def crosspost_discord_announcement(bot_token: str, channel_id: str, message_id: str) -> dict[str, Any]:
    auth_header = normalize_discord_bot_auth(bot_token)
    if not auth_header:
        raise RuntimeError("DISCORD_BOT_TOKEN is not set.")

    channel_key = str(channel_id or "").strip()
    message_key = str(message_id or "").strip()
    if not channel_key or not message_key:
        raise RuntimeError("Discord announce channel id or message id is missing.")

    request = urllib.request.Request(
        f"https://discord.com/api/v10/channels/{channel_key}/messages/{message_key}/crosspost",
        data=b"{}",
        headers={
            "Authorization": auth_header,
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": "LionsRoarAdmin/0.1 (+https://thelionsroar.eu)",
            "Connection": "close",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=25) as response:
            raw = response.read().decode("utf-8", errors="replace").strip()
            return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Discord crosspost HTTP {exc.code}: {raw}") from exc


def build_forum_payload(
    *,
    thread_name: str,
    title: str,
    authors: list[str],
    publish_time: str,
    teaser: str,
    image_url: str,
    article_url: str,
) -> dict[str, Any]:
    fields: list[dict[str, Any]] = []
    author_line = ", ".join(author for author in authors if author)
    if author_line:
        fields.append({"name": "By", "value": author_line, "inline": True})
    if publish_time:
        fields.append({"name": "Published", "value": publish_time, "inline": True})

    description_parts: list[str] = []
    if teaser.strip():
        description_parts.append(teaser.strip())
    if article_url:
        description_parts.append(f"[Read on the site]({article_url})")

    embed: dict[str, Any] = {
        "title": title,
        "description": "\n\n".join(description_parts).strip(),
    }
    if fields:
        embed["fields"] = fields
    if image_url:
        embed["image"] = {"url": image_url}

    return {
        "thread_name": thread_name[:100],
        "content": "",
        "embeds": [embed],
        "allowed_mentions": {"parse": []},
    }


def build_announce_payload(
    *,
    title: str,
    authors: list[str],
    publish_time: str,
    teaser: str,
    image_url: str,
    article_url: str,
    thread_id: str,
) -> dict[str, Any]:
    fields: list[dict[str, Any]] = []
    author_line = ", ".join(author for author in authors if author)
    if author_line:
        fields.append({"name": "By", "value": author_line, "inline": True})
    if publish_time:
        fields.append({"name": "Published", "value": publish_time, "inline": True})
    if thread_id:
        fields.append({"name": "Discuss", "value": f"<#{thread_id}>", "inline": True})

    description_parts: list[str] = []
    if teaser.strip():
        description_parts.append(teaser.strip())
    if article_url:
        description_parts.append(f"[Read on the site]({article_url})")

    embed: dict[str, Any] = {
        "title": title,
        "description": "\n\n".join(description_parts).strip(),
        "color": 0x3D352E,
    }
    if fields:
        embed["fields"] = fields
    if image_url:
        embed["image"] = {"url": image_url}

    return {
        "content": "",
        "embeds": [embed],
        "allowed_mentions": {"parse": []},
    }


def trigger_discord_announce(article: dict[str, Any], published_state: dict[str, Any], force: bool = False) -> dict[str, Any]:
    forum_webhook = (os.environ.get("DISCORD_FORUM_WEBHOOK_URL") or "").strip()
    announce_webhook = (os.environ.get("DISCORD_ANNOUNCE_WEBHOOK_URL") or "").strip()
    bot_token = (os.environ.get("DISCORD_BOT_TOKEN") or "").strip()
    username = (os.environ.get("DISCORD_USERNAME") or "").strip()
    avatar_url = (os.environ.get("DISCORD_AVATAR_URL") or "").strip()

    if not forum_webhook:
        raise RuntimeError("DISCORD_FORUM_WEBHOOK_URL is not set.")
    if not announce_webhook:
        raise RuntimeError("DISCORD_ANNOUNCE_WEBHOOK_URL is not set.")
    if not force and not bool(article.get("discord_announce", True)):
        raise RuntimeError("discord_announce is disabled for this article.")

    if not ensure_live_state_entry(article, published_state):
        if article.get("id") not in published_state:
            raise RuntimeError("Article is not available in live publish state.")
    save_published_state(published_state)

    article_id = str(article.get("id") or "").strip()
    state_entry = published_state.get(article_id) if isinstance(published_state.get(article_id), dict) else {}
    discord_state = normalize_discord_state(state_entry.get("discord"))
    now_utc = utc_now_iso()

    title = str(article.get("title") or "").strip() or "(Untitled)"
    teaser = str(article.get("teaser") or "").strip()
    authors = [str(author).strip() for author in (article.get("authors") or []) if str(author).strip()]
    publish_time = publish_at_to_storage(article.get("publish_at")) or str(article.get("publish_at") or "").strip()
    article_url = build_public_article_url(article)
    image_ref = article.get("image") if isinstance(article.get("image"), dict) else {}
    image_url = normalize_asset_url((os.environ.get("SITE_BASE_URL") or "").strip(), str(image_ref.get("src") or ""))

    forum_info = discord_state.get("forum") if isinstance(discord_state.get("forum"), dict) else None
    announce_info = discord_state.get("announce") if isinstance(discord_state.get("announce"), dict) else None
    created_forum = False
    posted_announce = False
    crossposted_announce = False
    crosspost_error = ""

    thread_id = str(forum_info.get("thread_id") or "") if forum_info else ""
    starter_message_id = str(forum_info.get("starter_message_id") or "") if forum_info else ""
    announce_message_id = str(announce_info.get("message_id") or "").strip() if announce_info else ""
    announce_channel_id = str(announce_info.get("channel_id") or "").strip() if announce_info else ""
    announce_crossposted_at = str(announce_info.get("crossposted_at") or "").strip() if announce_info else ""

    if not thread_id:
        forum_response = webhook_post(
            forum_webhook,
            build_forum_payload(
                thread_name=title,
                title=title,
                authors=authors,
                publish_time=publish_time,
                teaser=teaser,
                image_url=image_url,
                article_url=article_url,
            ),
            username=username,
            avatar_url=avatar_url,
        )
        starter_message_id = str(forum_response.get("id") or "").strip()
        thread_id = str(forum_response.get("channel_id") or "").strip()
        if not thread_id or not starter_message_id:
            raise RuntimeError("Discord forum response did not include the created thread ids.")
        discord_state["forum"] = {
            "thread_id": thread_id,
            "starter_message_id": starter_message_id,
            "posted_at": now_utc,
        }
        created_forum = True

    if not announce_message_id:
        announce_response = webhook_post(
            announce_webhook,
            build_announce_payload(
                title=title,
                authors=authors,
                publish_time=publish_time,
                teaser=teaser,
                image_url=image_url,
                article_url=article_url,
                thread_id=thread_id,
            ),
            username=username,
            avatar_url=avatar_url,
        )
        announce_message_id = str(announce_response.get("id") or "").strip()
        announce_channel_id = str(announce_response.get("channel_id") or "").strip() or announce_channel_id
        if not announce_message_id:
            raise RuntimeError("Discord announce response did not include a message id.")
        discord_state["announce"] = {
            "message_id": announce_message_id,
            "channel_id": announce_channel_id,
            "posted_at": now_utc,
        }
        state_entry["discord"] = discord_state
        state_entry["discord_last_action"] = {"action": "announce_post", "at": now_utc}
        published_state[article_id] = state_entry
        save_published_state(published_state)
        posted_announce = True
    elif isinstance(announce_info, dict):
        discord_state["announce"] = dict(announce_info)

    if not announce_channel_id:
        try:
            announce_channel_id = webhook_channel_id(announce_webhook)
            announce_state = discord_state.get("announce") if isinstance(discord_state.get("announce"), dict) else {}
            announce_state["message_id"] = announce_message_id
            announce_state["channel_id"] = announce_channel_id
            announce_state.setdefault("posted_at", now_utc)
            if announce_crossposted_at:
                announce_state["crossposted_at"] = announce_crossposted_at
            discord_state["announce"] = announce_state
        except Exception as exc:
            crosspost_error = str(exc) or repr(exc)

    if not announce_crossposted_at:
        try:
            crosspost_discord_announcement(bot_token, announce_channel_id, announce_message_id)
            announce_state = discord_state.get("announce") if isinstance(discord_state.get("announce"), dict) else {}
            announce_state["message_id"] = announce_message_id
            announce_state["channel_id"] = announce_channel_id
            announce_state.setdefault("posted_at", now_utc)
            announce_state["crossposted_at"] = now_utc
            announce_state["crosspost_status"] = "crossposted"
            announce_state["crosspost_attempted_at"] = now_utc
            announce_state.pop("crosspost_error", None)
            discord_state["announce"] = announce_state
            state_entry["discord_last_action"] = {"action": "announce_crosspost", "at": now_utc}
            crossposted_announce = True
        except Exception as exc:
            crosspost_error = str(exc) or repr(exc)
            announce_state = discord_state.get("announce") if isinstance(discord_state.get("announce"), dict) else {}
            announce_state["message_id"] = announce_message_id
            if announce_channel_id:
                announce_state["channel_id"] = announce_channel_id
            announce_state.setdefault("posted_at", now_utc)
            announce_state["crosspost_status"] = "failed"
            announce_state["crosspost_attempted_at"] = now_utc
            announce_state["crosspost_error"] = crosspost_error
            discord_state["announce"] = announce_state
            state_entry["discord_last_action"] = {"action": "announce_crosspost_failed", "at": now_utc}

    state_entry["discord"] = discord_state
    state_entry.setdefault("discord_last_action", {"action": "announce_post", "at": now_utc})
    published_state[article_id] = state_entry
    save_published_state(published_state)

    return {
        "forum_created": created_forum,
        "announcement_posted": posted_announce,
        "announcement_crossposted": crossposted_announce,
        "thread_id": thread_id,
        "starter_message_id": starter_message_id,
        "announce_message_id": announce_message_id,
        "announce_channel_id": announce_channel_id,
        "crosspost_error": crosspost_error,
        "previous_announce": bool(announce_info),
    }


def verify_ip(request: Request):
    return request.client.host



def parse_frontmatter_document(raw: str) -> tuple[dict[str, Any], str]:
    if not raw.startswith("---"):
        return {}, raw.strip()

    parts = raw.split("---", 2)
    if len(parts) < 3:
        return {}, raw.strip()

    frontmatter = yaml.safe_load(parts[1]) or {}
    if not isinstance(frontmatter, dict):
        frontmatter = {}
    return frontmatter, parts[2].lstrip("\n").rstrip()


def parse_publish_at(value: Any) -> Optional[datetime]:
    if value is None:
        return None

    if isinstance(value, datetime):
        return value

    text = str(value).strip()
    if not text:
        return None

    formats = (
        "%Y-%m-%dT%H:%M",
        "%Y-%m-%d %H:%M",
        "%d-%m-%Y %H:%M",
        "%Y-%m-%dT%H:%M:%S",
    )
    for fmt in formats:
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            continue

    try:
        return datetime.fromisoformat(text)
    except ValueError:
        return None


def publish_at_to_storage(value: Any) -> str:
    dt = parse_publish_at(value)
    if not dt:
        return ""
    return dt.strftime("%d-%m-%Y %H:%M")


def publish_at_to_form(value: Any) -> str:
    dt = parse_publish_at(value)
    if not dt:
        return ""
    return dt.strftime("%Y-%m-%dT%H:%M")


def ensure_content_path(path: Path) -> Path:
    resolved = path.resolve()
    content_root = CONTENT_ROOT.resolve()
    if not resolved.is_relative_to(content_root):
        raise HTTPException(status_code=400, detail="Invalid article path")
    return resolved


def history_dir_for(article_path: Path, article_id: str) -> Path:
    return article_path.parent / "_history" / article_id


def log_path_for(article_id: str) -> Path:
    return ARTICLE_LOG_ROOT / f"{article_id}.json"


def load_article_log(article_id: str) -> list[dict[str, Any]]:
    path = log_path_for(article_id)
    if not path.exists():
        return []

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, list) else []
    except Exception:
        return []


def append_article_log(article_id: str, entry: dict[str, Any]) -> None:
    ARTICLE_LOG_ROOT.mkdir(parents=True, exist_ok=True)
    existing = load_article_log(article_id)
    existing.insert(0, entry)
    log_path_for(article_id).write_text(
        json.dumps(existing, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def load_article_versions(article_path: Path, article_id: str) -> list[dict[str, Any]]:
    versions_dir = history_dir_for(article_path, article_id)
    if not versions_dir.exists():
        return []

    items: list[dict[str, Any]] = []
    for version_path in sorted(versions_dir.glob("*.bak.md"), reverse=True):
        stem = version_path.name[:-7] if version_path.name.endswith(".bak.md") else version_path.stem
        parts = stem.split(".")
        timestamp = ""
        action = "snapshot"
        if len(parts) >= 3:
            timestamp = parts[-2]
            action = parts[-1]

        created_at = ""
        if timestamp:
            try:
                created_at = datetime.strptime(timestamp, "%Y%m%d%H%M%S").strftime(
                    "%Y-%m-%dT%H:%M:%S"
                )
            except ValueError:
                created_at = timestamp

        items.append(
            {
                "version_id": version_path.name,
                "created_at": created_at,
                "action": action,
                "path": str(version_path),
            }
        )

    return items


def create_version_snapshot(article_path: Path, article_id: str, action: str) -> Optional[dict[str, Any]]:
    if not article_path.exists():
        return None

    versions_dir = history_dir_for(article_path, article_id)
    versions_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    filename = f"{article_id}.{timestamp}.{action}.bak.md"
    target = versions_dir / filename
    shutil.copy2(article_path, target)
    return {
        "created": True,
        "version_id": filename,
        "path": str(target),
    }


def normalize_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        items = value
    else:
        items = str(value).split(",")
    return [str(item).strip() for item in items if str(item).strip()]


def normalize_article_payload(
    frontmatter: dict[str, Any],
    body_markdown: str,
    article_path: Path,
    published_state: Optional[dict[str, Any]] = None,
    include_details: bool = True,
) -> dict[str, Any]:
    published_state = published_state or {}

    article_id = str(frontmatter.get("id") or article_path.stem).strip()
    filename = article_path.relative_to(CONTENT_ROOT).as_posix()
    status = str(frontmatter.get("status") or "draft").strip().lower()
    if status not in ALLOWED_STATUSES:
        status = "draft"

    image = frontmatter.get("image") if isinstance(frontmatter.get("image"), dict) else {}
    versions = load_article_versions(article_path, article_id)
    state_entry = published_state.get(article_id) if isinstance(published_state.get(article_id), dict) else {}
    payload = {
        "id": article_id,
        "filename": filename,
        "title": str(frontmatter.get("title") or "").strip(),
        "section": str(frontmatter.get("section") or "news").strip(),
        "type": str(frontmatter.get("type") or "report").strip(),
        "authors": normalize_list(frontmatter.get("authors")),
        "teaser": str(frontmatter.get("teaser") or "").strip(),
        "publish_at": publish_at_to_form(frontmatter.get("publish_at")),
        "status": status,
        "discord_announce": bool(frontmatter.get("discord_announce", True)),
        "tags": normalize_list(frontmatter.get("tags")),
        "image": {
            "src": str(image.get("src") or "").strip(),
            "credit": str(image.get("credit") or "").strip(),
            "source": str(image.get("source") or "").strip(),
            "image_type": str(image.get("image_type") or "illustration").strip(),
        },
        "kicker": str(frontmatter.get("kicker") or "").strip(),
        "template": str(frontmatter.get("template") or "news_article").strip(),
        "body_markdown": body_markdown,
        "created_at": str(frontmatter.get("created_at") or "").strip(),
        "updated_at": str(frontmatter.get("updated_at") or "").strip(),
        "discord": normalize_discord_state(state_entry.get("discord")),
        "recorded_at": str(state_entry.get("recorded_at") or "").strip(),
        "is_live_public": article_is_live_public(status, article_id, published_state),
        "version_count": len(versions),
    }

    if include_details:
        payload["versions"] = versions
        payload["log"] = load_article_log(article_id)

    return payload


def load_article(
    article_path: Path,
    published_state: Optional[dict[str, Any]] = None,
    include_details: bool = True,
) -> dict[str, Any]:
    full_path = ensure_content_path(article_path)
    if not full_path.exists():
        raise HTTPException(status_code=404, detail="File not found")

    raw = full_path.read_text(encoding="utf-8")
    frontmatter, body_markdown = parse_frontmatter_document(raw)
    return normalize_article_payload(
        frontmatter,
        body_markdown,
        full_path,
        published_state=published_state,
        include_details=include_details,
    )


def build_admin_article_summary(article: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": article["id"],
        "filename": article["filename"],
        "title": article["title"],
        "authors": article["authors"],
        "publish_at": article["publish_at"],
        "status": article["status"],
        "updated_at": article["updated_at"],
        "created_at": article["created_at"],
        "version_count": article["version_count"],
        "is_live_public": article["is_live_public"],
        "has_discord_forum": bool(article.get("discord", {}).get("forum")),
        "has_discord_announce": bool(article.get("discord", {}).get("announce")),
    }


def validate_article_payload(payload: dict[str, Any], action: str) -> list[str]:
    errors: list[str] = []
    requires_complete = action in {
        "save_build",
        "schedule",
        "publish_now",
        "update_published",
        "save_scheduled_changes",
    }

    if requires_complete:
        if not payload["title"]:
            errors.append("Headline is required.")
        if not payload["authors"]:
            errors.append("At least one author is required.")
        if not payload["teaser"]:
            errors.append("Teaser is required.")
        if not payload["section"]:
            errors.append("Section is required.")
        if not payload["body_markdown"].strip():
            errors.append("Article body is required.")

    if action in {"schedule", "save_scheduled_changes"} and not payload["publish_at"]:
        errors.append("Publish date and time are required for scheduling.")

    return errors


def resolve_article_path(
    original_filename: Optional[str],
    publish_at: Optional[datetime],
    title: str,
) -> Path:
    if original_filename:
        return ensure_content_path(CONTENT_ROOT / original_filename)

    dt = publish_at or datetime.now()
    article_id = f"{dt.strftime('%Y%m%d%H%M')}-{slugify(title or 'untitled')}"
    return CONTENT_ROOT / dt.strftime("%Y") / f"{article_id}.md"


def has_been_published(article_id: str, published_state: dict[str, Any]) -> bool:
    return article_id in published_state


def write_article(article_path: Path, article: dict[str, Any]) -> None:
    article_path.parent.mkdir(parents=True, exist_ok=True)
    publish_at_storage = publish_at_to_storage(article.get("publish_at"))
    frontmatter = {
        "id": article["id"],
        "title": article["title"],
        "section": article["section"],
        "type": article["type"],
        "authors": article["authors"],
        "teaser": article["teaser"],
        "publish_at": publish_at_storage,
        "status": article["status"],
        "discord_announce": article["discord_announce"],
        "tags": article["tags"],
        "image": article["image"],
        "kicker": article["kicker"],
        "template": article["template"],
        "created_at": article["created_at"],
        "updated_at": article["updated_at"],
    }

    output = (
        "---\n"
        + yaml.dump(frontmatter, allow_unicode=True, sort_keys=False)
        + "---\n"
        + article["body_markdown"].rstrip()
        + "\n"
    )
    article_path.write_text(output, encoding="utf-8")


def save_uploaded_image(article_id: str, image: Optional[UploadFile], current_src: str) -> str:
    image_ref = current_src
    if image and image.filename:
        ext = os.path.splitext(image.filename)[1].lower()
        img_name = f"{article_id}{ext}"
        img_dest = ASSETS_ROOT / "images" / img_name
        img_dest.parent.mkdir(parents=True, exist_ok=True)
        with open(img_dest, "wb") as buffer:
            shutil.copyfileobj(image.file, buffer)
        image_ref = f"/assets/images/{img_name}"
    return image_ref
templates = Jinja2Templates(directory=str(APP_ROOT / "templates"))

if ASSETS_ROOT.exists():
    app.mount("/assets", StaticFiles(directory=str(ASSETS_ROOT)), name="assets")


@app.get("/api/config")
async def get_config() -> dict[str, Any]:
    config_path = APP_ROOT / "content" / "config.yaml"
    if config_path.exists():
        with open(config_path, "r", encoding="utf-8") as handle:
            return yaml.safe_load(handle) or {}
    return {"error": "Config not found"}


@app.get("/widgets/config")
async def get_widgets_config() -> dict[str, Any]:
    return load_data()


@app.get("/admin", response_class=HTMLResponse)
@app.get("/admin/", response_class=HTMLResponse)
async def get_admin_editor(request: Request) -> HTMLResponse:
    verify_ip(request)
    return templates.TemplateResponse("admin_editor.html", {"request": request})


@app.get("/admin/articles")
async def list_articles(
    request: Request,
    status: str = Query("active"),
) -> dict[str, Any]:
    verify_ip(request)
    published_state = load_published_state()
    status_filter = status.strip().lower()
    valid_filters = {"active", "all", *ALLOWED_STATUSES}
    if status_filter not in valid_filters:
        raise HTTPException(status_code=400, detail="Invalid status filter")

    items: list[dict[str, Any]] = []
    if not CONTENT_ROOT.exists():
        return {"items": items}

    for md_file in CONTENT_ROOT.glob("**/*.md"):
        if "_history" in md_file.parts:
            continue

        try:
            article = load_article(md_file, published_state=published_state, include_details=False)
        except Exception:
            continue

        article_status = article["status"]
        if status_filter == "active" and article_status == "deleted":
            continue
        if status_filter not in {"active", "all"} and article_status != status_filter:
            continue

        items.append(build_admin_article_summary(article))

    items.sort(
        key=lambda item: (
            item.get("publish_at") or "",
            item.get("updated_at") or "",
            item.get("title") or "",
        ),
        reverse=True,
    )
    return {"items": items}


@app.get("/admin/articles/{filepath:path}")
async def get_article(request: Request, filepath: str) -> dict[str, Any]:
    verify_ip(request)
    published_state = load_published_state()
    return load_article(CONTENT_ROOT / filepath, published_state=published_state, include_details=True)


@app.delete("/admin/articles/{filepath:path}")
async def delete_article(request: Request, filepath: str) -> JSONResponse:
    verify_ip(request)
    published_state = load_published_state()
    article_path = ensure_content_path(CONTENT_ROOT / filepath)
    article = load_article(article_path, published_state=published_state, include_details=True)

    if article["status"] == "deleted":
        return JSONResponse(
            {
                "status": "ok",
                "message": f"{article['title'] or article['filename']} is already deleted.",
                "article": build_admin_article_summary(article),
            }
        )

    snapshot = None
    was_live_public = bool(article.get("is_live_public"))
    if article["status"] == "published" or has_been_published(article["id"], published_state):
        snapshot = create_version_snapshot(article_path, article["id"], "deleted")

    previous_status = article["status"]
    article["status"] = "deleted"
    article["updated_at"] = utc_now_iso()
    write_article(article_path, article)

    state_changed = remove_live_state_entry(article["id"], published_state)
    if state_changed:
        save_published_state(published_state)

    removed_output = remove_public_output(article)
    if was_live_public or state_changed or removed_output:
        refresh_public_site(published_state)

    append_article_log(
        article["id"],
        {
            "timestamp": article["updated_at"],
            "action": "deleted",
            "from_status": previous_status,
            "to_status": "deleted",
            "version_snapshot_created": bool(snapshot),
            "summary": "Article moved to deleted state and removed from public output.",
        },
    )

    updated = load_article(article_path, published_state=published_state, include_details=False)
    return JSONResponse(
        {
            "status": "ok",
            "message": f"Deleted {updated['title'] or updated['filename']}",
            "article": build_admin_article_summary(updated),
        }
    )


@app.post("/admin/articles/{filepath:path}/restore")
async def restore_article(request: Request, filepath: str) -> JSONResponse:
    verify_ip(request)
    published_state = load_published_state()
    article_path = ensure_content_path(CONTENT_ROOT / filepath)
    article = load_article(article_path, published_state=published_state, include_details=True)

    if article["status"] != "deleted":
        raise HTTPException(status_code=400, detail="Only deleted articles can be restored")

    article["status"] = "draft"
    article["updated_at"] = utc_now_iso()
    write_article(article_path, article)

    state_changed = remove_live_state_entry(article["id"], published_state)
    if state_changed:
        save_published_state(published_state)

    removed_output = remove_public_output(article)
    if state_changed or removed_output:
        refresh_public_site(published_state)

    append_article_log(
        article["id"],
        {
            "timestamp": article["updated_at"],
            "action": "restored",
            "from_status": "deleted",
            "to_status": "draft",
            "version_snapshot_created": False,
            "summary": "Deleted article restored to draft and kept off the public site.",
        },
    )

    updated = load_article(article_path, published_state=published_state, include_details=False)
    return JSONResponse(
        {
            "status": "ok",
            "message": f"Restored {updated['title'] or updated['filename']} to draft.",
            "article": build_admin_article_summary(updated),
        }
    )


@app.post("/admin/publish")
async def handle_publish(
    request: Request,
    action: str = Form("save_draft"),
    title: str = Form(""),
    author: str = Form(""),
    publish_at: str = Form(""),
    section: str = Form("news"),
    type: str = Form("report"),
    tags: str = Form(""),
    image_credit: str = Form(""),
    image_source: str = Form("Lion's Roar archives"),
    image_type: str = Form("illustration"),
    teaser: str = Form(""),
    content: str = Form(""),
    discord_announce: bool = Form(True),
    original_filename: Optional[str] = Form(None),
    image: UploadFile = File(None),
) -> JSONResponse:
    verify_ip(request)

    if action not in ACTION_TO_STATUS:
        return JSONResponse(
            status_code=400,
            content={"status": "error", "message": "Unknown article action."},
        )

    failed_step = "initializing article submission"
    save_path: Optional[Path] = None
    article_id: Optional[str] = None
    workflow: dict[str, Any] = {
        "internal_build": False,
        "public_refresh": None,
        "removed_public_output": "",
        "state_changed": False,
    }

    try:
        failed_step = "loading published state"
        published_state = load_published_state()
        current_article: Optional[dict[str, Any]] = None
        if original_filename:
            failed_step = "loading existing article"
            current_path = ensure_content_path(CONTENT_ROOT / original_filename)
            if current_path.exists():
                current_article = load_article(
                    current_path,
                    published_state=published_state,
                    include_details=True,
                )

        if action == "update_published" and (
            not current_article or current_article["status"] != "published"
        ):
            return JSONResponse(
                status_code=400,
                content={"status": "error", "message": "Only published articles can be updated live."},
            )

        if action == "save_scheduled_changes" and (
            not current_article or current_article["status"] != "scheduled"
        ):
            return JSONResponse(
                status_code=400,
                content={"status": "error", "message": "Only scheduled articles can save scheduled changes."},
            )

        failed_step = "parsing publish date"
        publish_dt = parse_publish_at(publish_at) or parse_publish_at(
            current_article["publish_at"] if current_article else ""
        ) or datetime.now()

        failed_step = "resolving article path"
        save_path = resolve_article_path(original_filename, publish_dt, title)
        article_id = current_article["id"] if current_article else save_path.stem

        current_image = current_article["image"] if current_article else {}
        failed_step = "processing article image"
        image_src = save_uploaded_image(
            article_id,
            image,
            str(current_image.get("src") or ""),
        )

        failed_step = "building article payload"
        article = {
            "id": article_id,
            "filename": save_path.relative_to(CONTENT_ROOT).as_posix(),
            "title": title.strip(),
            "section": section.strip() or "news",
            "type": type.strip() or "report",
            "authors": normalize_list(author),
            "teaser": teaser.strip(),
            "publish_at": publish_dt.strftime("%Y-%m-%dT%H:%M"),
            "status": ACTION_TO_STATUS[action],
            "discord_announce": bool(discord_announce),
            "tags": normalize_list(tags),
            "image": {
                "src": image_src,
                "credit": image_credit.strip(),
                "source": image_source.strip() or "Lion's Roar archives",
                "image_type": image_type.strip() or "illustration",
            },
            "kicker": current_article["kicker"] if current_article else "",
            "template": current_article["template"] if current_article else "news_article",
            "body_markdown": content.rstrip(),
            "created_at": current_article["created_at"] if current_article else utc_now_iso(),
            "updated_at": utc_now_iso(),
        }

        failed_step = "validating article payload"
        errors = validate_article_payload(article, action)
        if errors:
            return JSONResponse(
                status_code=400,
                content={"status": "error", "message": " ".join(errors), "errors": errors},
            )

        version_snapshot = None
        if current_article and (
            current_article["status"] == "published"
            or has_been_published(article["id"], published_state)
        ):
            if action in {"publish_now", "update_published"}:
                failed_step = "creating version snapshot"
                version_snapshot = create_version_snapshot(save_path, article["id"], action)

        failed_step = "writing article file"
        write_article(save_path, article)

        was_live_public = bool(current_article.get("is_live_public")) if current_article else False
        failed_step = "updating live state"
        if article["status"] == "published":
            workflow["state_changed"] = ensure_live_state_entry(article, published_state)
            if workflow["state_changed"]:
                save_published_state(published_state)
        else:
            workflow["state_changed"] = remove_live_state_entry(article["id"], published_state)
            if workflow["state_changed"]:
                save_published_state(published_state)

        if action == "save_build":
            failed_step = "building internal article output"
            build_single_article(save_path, "internal")
            workflow["internal_build"] = True

        if article["status"] == "published":
            failed_step = "rebuilding public site"
            workflow["public_refresh"] = refresh_public_site(published_state)
        elif was_live_public or workflow["state_changed"]:
            failed_step = "removing stale public output"
            workflow["removed_public_output"] = remove_public_output(article)
            failed_step = "rebuilding public site"
            workflow["public_refresh"] = refresh_public_site(published_state)

        previous_status = current_article["status"] if current_article else None
        summary_parts = [f"Article saved via {action}."]
        if workflow["internal_build"]:
            summary_parts.append("Internal build refreshed.")
        if workflow["state_changed"] and article["status"] == "published":
            summary_parts.append("Live publish state updated.")
        elif workflow["state_changed"]:
            summary_parts.append("Live publish state cleared.")
        if workflow["removed_public_output"]:
            summary_parts.append("Removed stale public output.")
        if isinstance(workflow["public_refresh"], dict):
            summary_parts.append(
                f"Public site rebuilt ({workflow['public_refresh'].get('built_articles', 0)} article outputs, {workflow['public_refresh'].get('removed_outputs', 0)} stale outputs removed)."
            )

        failed_step = "writing article activity log"
        append_article_log(
            article["id"],
            {
                "timestamp": article["updated_at"],
                "action": action,
                "from_status": previous_status,
                "to_status": article["status"],
                "version_snapshot_created": bool(version_snapshot),
                "summary": " ".join(summary_parts),
            },
        )

        failed_step = "reloading saved article"
        saved = load_article(save_path, published_state=published_state, include_details=True)
        message_map = {
            "save_draft": "Draft saved.",
            "save_build": "Article saved and internal build refreshed.",
            "schedule": "Article scheduled.",
            "save_scheduled_changes": "Scheduled article updated.",
            "publish_now": "Article published and public site rebuilt.",
            "update_published": "Live article updated and public site rebuilt.",
        }
        return JSONResponse(
            {
                "status": "ok",
                "message": message_map.get(action, "Article saved."),
                "article": saved,
                "workflow": workflow,
                "version_snapshot": version_snapshot or {"created": False},
            }
        )
    except HTTPException:
        raise
    except Exception as exc:
        return JSONResponse(
            status_code=500,
            content={
                "status": "error",
                "message": "Article save failed.",
                "failed_step": failed_step,
                "error_type": exc.__class__.__name__,
                "detail": str(exc) or repr(exc),
                "context": {
                    "action": action,
                    "title": title.strip(),
                    "original_filename": original_filename or "",
                    "save_path": str(save_path) if save_path else "",
                    "article_id": article_id or "",
                    "log_path": str(log_path_for(article_id)) if article_id else str(ARTICLE_LOG_ROOT),
                },
            },
        )


@app.post("/admin/articles/{filepath:path}/workflow")
async def run_article_workflow(
    request: Request,
    filepath: str,
    command: str = Form(...),
) -> JSONResponse:
    verify_ip(request)

    if command != "announce_discord":
        return JSONResponse(
            status_code=400,
            content={"status": "error", "message": "Unknown workflow command."},
        )

    failed_step = "loading article"
    try:
        published_state = load_published_state()
        article_path = ensure_content_path(CONTENT_ROOT / filepath)
        article = load_article(article_path, published_state=published_state, include_details=True)

        if not article.get("is_live_public") and article.get("status") != "published":
            return JSONResponse(
                status_code=400,
                content={"status": "error", "message": "Only live published articles can be announced."},
            )

        failed_step = "running Discord announcement"
        announce_output = trigger_discord_announce(article, published_state, force=True)

        failed_step = "reloading article state"
        published_state = load_published_state()
        updated = load_article(article_path, published_state=published_state, include_details=True)

        workflow_message = "Discord announcement completed."
        workflow_summary = "Discord announcement triggered from the admin panel."
        if announce_output.get("crosspost_error"):
            workflow_message = "Discord announcement posted, but crosspost failed and can be retried."
            workflow_summary = f"Discord announcement posted, but crosspost failed: {announce_output['crosspost_error']}"
        elif announce_output.get("announcement_crossposted"):
            workflow_message = "Discord announcement posted and crossposted."
            workflow_summary = "Discord announcement posted and crossposted from the admin panel."
        elif announce_output.get("previous_announce"):
            workflow_message = "Discord announcement already posted and crossposted."
            workflow_summary = "Discord announcement was already posted and crossposted."

        failed_step = "writing workflow activity log"
        append_article_log(
            updated["id"],
            {
                "timestamp": utc_now_iso(),
                "action": command,
                "from_status": updated["status"],
                "to_status": updated["status"],
                "version_snapshot_created": False,
                "summary": workflow_summary,
            },
        )
        updated = load_article(article_path, published_state=published_state, include_details=True)

        return JSONResponse(
            {
                "status": "ok",
                "message": workflow_message,
                "article": updated,
                "workflow": {
                    "command": command,
                    "output": announce_output,
                },
            }
        )
    except HTTPException:
        raise
    except Exception as exc:
        return JSONResponse(
            status_code=500,
            content={
                "status": "error",
                "message": "Article workflow failed.",
                "failed_step": failed_step,
                "error_type": exc.__class__.__name__,
                "detail": str(exc) or repr(exc),
                "context": {
                    "command": command,
                    "filepath": filepath,
                },
            },
        )

@app.post("/admin/preview")
async def admin_preview(request: Request, content: str = Form(...)) -> JSONResponse:
    verify_ip(request)
    html_content = markdown.markdown(content, extensions=["extra", "smarty"])
    return JSONResponse({"html": html_content})


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
