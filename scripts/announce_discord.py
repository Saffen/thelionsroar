#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

PROJECT_ROOT = Path(__file__).resolve().parents[1]
PUBLISH_SCRIPT = PROJECT_ROOT / "scripts" / "publish.py"
DEFAULT_CONTENT_DIR = PROJECT_ROOT / "content"
DEFAULT_STATE_FILE = PROJECT_ROOT / "state" / "published.json"

# Optional helper
try:
    from scripts._env import load_dotenv  # when running from repo root
except Exception:
    try:
        from _env import load_dotenv  # fallback
    except Exception:
        load_dotenv = None


def iso_now_utc() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def load_state(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def save_state(path: Path, state: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def run_publish_json(content_dir: Path) -> Tuple[int, str, str]:
    result = subprocess.run(
        [sys.executable, str(PUBLISH_SCRIPT), str(content_dir), "--json"],
        capture_output=True,
        text=True,
        check=False,
    )
    return result.returncode, result.stdout, result.stderr


def parse_isoish(dt_val: Any) -> Optional[datetime]:
    if dt_val is None:
        return None
    s = str(dt_val).strip()
    if not s:
        return None
    # We avoid adding deps here. publish.py already parsed for logic, but in JSON we only have strings.
    # Try a few common formats.
    fmts = [
        "%Y-%m-%d %H:%M",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%dT%H:%M",
        "%Y-%m-%dT%H:%M:%S",
    ]
    for f in fmts:
        try:
            return datetime.strptime(s, f)
        except Exception:
            pass
    try:
        # last resort: fromisoformat (handles offsets if present)
        return datetime.fromisoformat(s)
    except Exception:
        return None


def fmt_publish_time(dt_val: Any) -> str:
    dt = parse_isoish(dt_val)
    if not dt:
        return str(dt_val).strip() if dt_val else ""
    # If dt has tz, keep it. If not, show as provided.
    if dt.tzinfo is None:
        return dt.strftime("%Y-%m-%d %H:%M")
    return dt.astimezone().strftime("%Y-%m-%d %H:%M %Z")


def slug_from_path(path_str: str) -> str:
    name = Path(path_str).name
    return name[:-3] if name.lower().endswith(".md") else name


def year_from_path(path_str: str) -> str:
    parts = Path(path_str).parts
    for p in parts:
        if len(p) == 4 and p.isdigit():
            return p
    return "unknown"


def build_article_url(site_base_url: str, section: str, year: str, slug: str) -> str:
    base = site_base_url.rstrip("/")
    return f"{base}/{section}/{year}/{slug}/"


def normalize_asset_url(site_base_url: str, src: str) -> str:
    src = (src or "").strip()
    if not src:
        return ""
    if src.startswith("http://") or src.startswith("https://"):
        return src
    if not site_base_url:
        return ""
    base = site_base_url.rstrip("/")
    if src.startswith("/"):
        return f"{base}{src}"
    return f"{base}/{src}"


def webhook_post(
    webhook_url: str,
    payload: Dict[str, Any],
    thread_id: str = "",
    wait: bool = True,
    username: str = "",
    avatar_url: str = "",
) -> Dict[str, Any]:
    u = urllib.parse.urlparse(webhook_url)
    q = urllib.parse.parse_qs(u.query)

    if wait:
        q["wait"] = ["true"]
    if thread_id.strip():
        q["thread_id"] = [thread_id.strip()]

    post_url = urllib.parse.urlunparse(u._replace(query=urllib.parse.urlencode(q, doseq=True)))

    if username.strip():
        payload["username"] = username.strip()
    if avatar_url.strip():
        payload["avatar_url"] = avatar_url.strip()

    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        post_url,
        data=data,
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": "LionsRoarPublisher/0.1 (+https://thelionsroar.eu)",
            "Connection": "close",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=25) as resp:
            body = resp.read().decode("utf-8", errors="replace").strip()
            return json.loads(body) if body else {}
    except urllib.error.HTTPError as e:
        err_body = e.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Discord webhook HTTP {e.code}: {err_body}") from e


def build_forum_payload(
    *,
    thread_name: str,
    title: str,
    authors: List[str],
    publish_time: str,
    teaser: str,
    image_url: str,
    article_url: str,
) -> Dict[str, Any]:
    # Forum thread creation: include thread_name.
    # Starter message content can be minimal; we use an embed for layout.
    author_line = ", ".join([a for a in authors if a]) if authors else ""
    fields: List[Dict[str, Any]] = []
    if author_line:
        fields.append({"name": "By", "value": author_line, "inline": True})
    if publish_time:
        fields.append({"name": "Published", "value": publish_time, "inline": True})

    desc_parts: List[str] = []
    if teaser.strip():
        desc_parts.append(teaser.strip())
    if article_url:
        desc_parts.append(f"[Read on the site]({article_url})")
    description = "\n\n".join(desc_parts).strip()

    embed: Dict[str, Any] = {
        "title": title,
        "description": description,
    }
    if fields:
        embed["fields"] = fields
    if image_url:
        embed["image"] = {"url": image_url}

    payload: Dict[str, Any] = {
        "thread_name": thread_name,
        "content": "",  # keep empty, embed does the job
        "embeds": [embed],
        "allowed_mentions": {"parse": []},
    }
    return payload


def build_announce_payload(
    *,
    title: str,
    article_url: str,
    thread_id: str,
) -> Dict[str, Any]:
    # Thread mention makes a clickable link without needing guild id.
    thread_mention = f"<#{thread_id}>" if thread_id else "(thread unavailable)"
    lines = [f"**{title}**"]
    if article_url:
        lines.append(article_url)
    lines.append(f"Discuss: {thread_mention}")

    return {
        "content": "\n".join(lines),
        "allowed_mentions": {"parse": []},
    }


def ensure_state_entry(state: Dict[str, Any], article_id: str, item: Dict[str, Any]) -> None:
    fm = item.get("frontmatter", {}) if isinstance(item.get("frontmatter"), dict) else {}

    if article_id not in state or not isinstance(state.get(article_id), dict):
        state[article_id] = {
            "path": item.get("path"),
            "title": fm.get("title"),
            "section": fm.get("section"),
            "publish_at": fm.get("publish_at"),
            "recorded_at": iso_now_utc(),
            "discord": {"forum": None, "announce": None},
        }
        return

    entry = state[article_id]

    # Upgrade older schemas safely
    discord_val = entry.get("discord")

    # Old schema: "discord": null
    if discord_val is None:
        entry["discord"] = {"forum": None, "announce": None}
    # Old/other schema: "discord": {...} but not the structure we want
    elif not isinstance(discord_val, dict):
        entry["discord"] = {"forum": None, "announce": None}
    else:
        # Ensure expected keys exist
        if "forum" not in discord_val:
            discord_val["forum"] = None
        if "announce" not in discord_val:
            discord_val["announce"] = None

    # Fill in missing basic metadata (do not overwrite existing)
    entry.setdefault("path", item.get("path"))
    entry.setdefault("title", fm.get("title"))
    entry.setdefault("section", fm.get("section"))
    entry.setdefault("publish_at", fm.get("publish_at"))
    entry.setdefault("recorded_at", iso_now_utc())


def main() -> int:
    ap = argparse.ArgumentParser(description="Create a forum thread + post an announce message, store ids in state.")
    ap.add_argument("--content", default=str(DEFAULT_CONTENT_DIR), help="Content root to scan")
    ap.add_argument("--state", default=str(DEFAULT_STATE_FILE), help="State file path")
    ap.add_argument("--apply", action="store_true", help="Actually post to Discord and write state. Default is dry-run.")
    ap.add_argument("--limit", type=int, default=20, help="Max number of articles to process per run")
    args = ap.parse_args()

    if load_dotenv is not None:
        load_dotenv(PROJECT_ROOT / ".env")

    forum_webhook = (os.environ.get("DISCORD_FORUM_WEBHOOK_URL") or "").strip()
    announce_webhook = (os.environ.get("DISCORD_ANNOUNCE_WEBHOOK_URL") or "").strip()
    site_base = (os.environ.get("SITE_BASE_URL") or "").strip()
    username = (os.environ.get("DISCORD_USERNAME") or "").strip()
    avatar_url = (os.environ.get("DISCORD_AVATAR_URL") or "").strip()

    if not forum_webhook:
        print("ERROR: DISCORD_FORUM_WEBHOOK_URL is not set.", file=sys.stderr)
        return 2
    if not announce_webhook:
        print("ERROR: DISCORD_ANNOUNCE_WEBHOOK_URL is not set.", file=sys.stderr)
        return 2

    content_dir = Path(args.content).resolve()
    state_path = Path(args.state).resolve()
    state = load_state(state_path)

    rc, out, err = run_publish_json(content_dir)
    if rc not in (0, 1):
        print("ERROR: publish.py failed to run", file=sys.stderr)
        if err.strip():
            print(err, file=sys.stderr)
        return 2

    try:
        items = json.loads(out)
        if not isinstance(items, list):
            raise ValueError("Expected JSON list from publish.py")
    except Exception as e:
        print("ERROR: Could not parse JSON output from publish.py", file=sys.stderr)
        print(str(e), file=sys.stderr)
        return 2

    # Candidates: should_publish True
    candidates: List[Dict[str, Any]] = []
    for it in items:
        if not it.get("ok", False):
            continue
        decisions = it.get("decisions")
        fm = it.get("frontmatter")
        if not isinstance(decisions, dict) or not isinstance(fm, dict):
            continue
        if decisions.get("should_publish") is not True:
            continue
        article_id = fm.get("id")
        if not isinstance(article_id, str) or not article_id.strip():
            continue
        candidates.append(it)

    if not candidates:
        print("No publishable articles found.")
        return 0

    candidates = candidates[: max(1, args.limit)]

    # Work list: needs either forum thread or announcement (or both)
    work: List[Tuple[str, Dict[str, Any], bool, bool]] = []
    for it in candidates:
        fm = it["frontmatter"]
        aid = fm["id"].strip()
        ensure_state_entry(state, aid, it)

        forum_done = bool(state[aid]["discord"].get("forum"))
        announce_done = bool(state[aid]["discord"].get("announce"))

        # We want double functionality. If either missing, we process.
        if forum_done and announce_done:
            continue
        work.append((aid, it, (not forum_done), (not announce_done)))

    if not work:
        print("Nothing to do. Forum threads and announcements already recorded in state.")
        return 0

    print("Pending Discord actions:")
    for aid, it, need_forum, need_announce in work:
        p = it.get("path", "")
        flags = []
        if need_forum:
            flags.append("forum")
        if need_announce:
            flags.append("announce")
        print(f"- {p} (id: {aid}) -> {', '.join(flags)}")
    print()

    if not args.apply:
        print("Dry-run only. Re-run with --apply to post and write ids to state.")
        return 10

    posted_forum = 0
    posted_announce = 0
    now_utc = iso_now_utc()

    for aid, it, need_forum, need_announce in work:
        fm = it["frontmatter"]
        path_str = it.get("path", "") or ""

        title = str(fm.get("title") or "").strip() or "(Untitled)"
        teaser = str(fm.get("teaser") or "").strip()
        section = str(fm.get("section") or "").strip() or "news"
        publish_time = fmt_publish_time(fm.get("publish_at"))

        authors_raw = fm.get("authors")
        authors: List[str] = []
        if isinstance(authors_raw, list):
            authors = [str(a).strip() for a in authors_raw if str(a).strip()]
        elif isinstance(authors_raw, str) and authors_raw.strip():
            authors = [authors_raw.strip()]

        # Build article URL for embed and announcement
        year = year_from_path(path_str)
        slug = slug_from_path(path_str)
        article_url = build_article_url(site_base, section, year, slug) if site_base else ""

        # Image
        image_url = ""
        img = fm.get("image")
        if isinstance(img, dict):
            image_url = normalize_asset_url(site_base, str(img.get("src") or ""))

        # Step A: create forum thread (if needed)
        thread_id: str = ""
        starter_message_id: str = ""

        existing_forum = state[aid]["discord"].get("forum")
        if isinstance(existing_forum, dict):
            thread_id = str(existing_forum.get("thread_id") or "").strip()
            starter_message_id = str(existing_forum.get("starter_message_id") or "").strip()

        if need_forum:
            payload = build_forum_payload(
                thread_name=title[:100],  # keep it sane
                title=title,
                authors=authors,
                publish_time=publish_time,
                teaser=teaser,
                image_url=image_url,
                article_url=article_url,
            )

            try:
                resp = webhook_post(
                    forum_webhook,
                    payload=payload,
                    username=username,
                    avatar_url=avatar_url,
                )
            except Exception as e:
                print(f"ERROR: Forum post failed for {aid}: {e}", file=sys.stderr)
                continue

            # For forum-created threads, Discord response message has:
            # - id: starter message id
            # - channel_id: the created thread id (forum post)
            starter_message_id = str(resp.get("id") or "").strip()
            thread_id = str(resp.get("channel_id") or "").strip()

            if not thread_id or not starter_message_id:
                print(f"ERROR: Forum post response missing ids for {aid}. Not writing forum state.", file=sys.stderr)
                continue

            state[aid]["discord"]["forum"] = {
                "thread_id": thread_id,
                "starter_message_id": starter_message_id,
                "posted_at": now_utc,
            }
            state[aid]["discord_last_action"] = {"action": "forum_post", "at": now_utc}
            save_state(state_path, state)  # save progress safely
            posted_forum += 1
            print(f"Forum thread created: {aid} -> thread_id={thread_id}")

        # Step B: post in announce channel with link to thread (if needed)
        if need_announce:
            # If we just created the thread, thread_id is known. If not, pull from state.
            forum_state = state[aid]["discord"].get("forum")
            if isinstance(forum_state, dict) and not thread_id:
                thread_id = str(forum_state.get("thread_id") or "").strip()

            payload = build_announce_payload(
                title=title,
                article_url=article_url or f"{section}/{year}/{slug}/",
                thread_id=thread_id,
            )

            try:
                resp = webhook_post(
                    announce_webhook,
                    payload=payload,
                    username=username,
                    avatar_url=avatar_url,
                )
            except Exception as e:
                print(f"ERROR: Announce post failed for {aid}: {e}", file=sys.stderr)
                continue

            announce_message_id = str(resp.get("id") or "").strip()
            if not announce_message_id:
                print(f"ERROR: Announce response missing message id for {aid}. Not writing announce state.", file=sys.stderr)
                continue

            state[aid]["discord"]["announce"] = {
                "message_id": announce_message_id,
                "posted_at": now_utc,
            }
            state[aid]["discord_last_action"] = {"action": "announce_post", "at": now_utc}
            save_state(state_path, state)
            posted_announce += 1
            print(f"Announcement posted: {aid} -> message_id={announce_message_id}")

    print(f"\nUpdated state: {state_path}")
    print(f"Forum threads created: {posted_forum}")
    print(f"Announcements posted: {posted_announce}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
