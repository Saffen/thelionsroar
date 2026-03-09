import json
import os
import shutil
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
APP_ROOT = Path("/app")
CONTENT_ROOT = APP_ROOT / "content" / "news"
STATE_ROOT = APP_ROOT / "state"
ASSETS_ROOT = APP_ROOT / "assets"
DATA_FILE = APP_ROOT / "data" / "widgets.yaml"
ARTICLE_LOG_ROOT = STATE_ROOT / "article-log"
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


def load_data() -> dict[str, Any]:
    if not DATA_FILE.exists():
        return {"zones": {}}
    with open(DATA_FILE, "r", encoding="utf-8") as handle:
        return yaml.safe_load(handle) or {"zones": {}}


def load_published_state() -> dict[str, Any]:
    state_path = STATE_ROOT / "published.json"
    if not state_path.exists():
        return {}

    try:
        with open(state_path, "r", encoding="utf-8") as handle:
            data = json.load(handle)
            return data if isinstance(data, dict) else {}
    except Exception as exc:
        print(f"Error loading published.json: {exc}")
        return {}


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
        "is_live_public": article_id in published_state or status == "published",
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


templates = Jinja2Templates(directory="/app/templates")

if ASSETS_ROOT.exists():
    app.mount("/assets", StaticFiles(directory="/app/assets"), name="assets")


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
    if article["status"] == "published" or has_been_published(article["id"], published_state):
        snapshot = create_version_snapshot(article_path, article["id"], "deleted")

    previous_status = article["status"]
    article["status"] = "deleted"
    article["updated_at"] = utc_now_iso()
    write_article(article_path, article)
    append_article_log(
        article["id"],
        {
            "timestamp": article["updated_at"],
            "action": "deleted",
            "from_status": previous_status,
            "to_status": "deleted",
            "version_snapshot_created": bool(snapshot),
            "summary": "Article moved to deleted state.",
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
    append_article_log(
        article["id"],
        {
            "timestamp": article["updated_at"],
            "action": "restored",
            "from_status": "deleted",
            "to_status": "draft",
            "version_snapshot_created": False,
            "summary": "Deleted article restored to draft.",
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

    published_state = load_published_state()
    current_article: Optional[dict[str, Any]] = None
    if original_filename:
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

    publish_dt = parse_publish_at(publish_at) or parse_publish_at(
        current_article["publish_at"] if current_article else ""
    ) or datetime.now()

    save_path = resolve_article_path(original_filename, publish_dt, title)
    article_id = current_article["id"] if current_article else save_path.stem

    current_image = current_article["image"] if current_article else {}
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
            "src": save_uploaded_image(
                article_id,
                image,
                str(current_image.get("src") or ""),
            ),
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

    errors = validate_article_payload(article, action)
    if errors:
        return JSONResponse(
            status_code=400,
            content={"status": "error", "message": " ".join(errors), "errors": errors},
        )

    version_snapshot = None
    if current_article and (current_article["status"] == "published" or has_been_published(article["id"], published_state)):
        if action in {"publish_now", "update_published"}:
            version_snapshot = create_version_snapshot(save_path, article["id"], action)

    write_article(save_path, article)

    previous_status = current_article["status"] if current_article else None
    append_article_log(
        article["id"],
        {
            "timestamp": article["updated_at"],
            "action": action,
            "from_status": previous_status,
            "to_status": article["status"],
            "version_snapshot_created": bool(version_snapshot),
            "summary": f"Article saved via {action}.",
        },
    )

    saved = load_article(save_path, published_state=published_state, include_details=True)
    return JSONResponse(
        {
            "status": "ok",
            "message": "Article saved",
            "article": saved,
            "version_snapshot": version_snapshot or {"created": False},
        }
    )


@app.post("/admin/preview")
async def admin_preview(request: Request, content: str = Form(...)) -> JSONResponse:
    verify_ip(request)
    html_content = markdown.markdown(content, extensions=["extra", "smarty"])
    return JSONResponse({"html": html_content})


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
