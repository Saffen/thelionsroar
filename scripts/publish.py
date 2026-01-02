#!/usr/bin/env python3
"""
publish.py
- If PATH is a file: print frontmatter + decisions (single mode)
- If PATH is a directory: scan all *.md recursively and print grouped decisions (bulk mode)
- Optional: --json for machine-readable output

Important:
- In bulk mode, we skip any directories that start with "_" or "." under the scan root.
  This prevents scanning editor-only and template folders like:
    content/_templates, content/_references, content/.obsidian, content/.trash

Usage:
  python3 scripts/publish.py content/news
  python3 scripts/publish.py content --now "2025-12-31 21:00"
  python3 scripts/publish.py content --json
"""

from __future__ import annotations

import argparse
import os
import sys
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, Iterable, List, Optional, Tuple

try:
    import yaml  # pip install pyyaml
except Exception:
    print("ERROR: Missing dependency PyYAML. Install with: pip install pyyaml", file=sys.stderr)
    raise

try:
    from dateutil import parser as dtparser  # pip install python-dateutil
    from dateutil import tz as dttz
except Exception:
    print("ERROR: Missing dependency python-dateutil. Install with: pip install python-dateutil", file=sys.stderr)
    raise


FRONTMATTER_DELIM = "---"


def read_text(path: str) -> str:
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def split_frontmatter(md: str) -> Tuple[Dict[str, Any], str]:
    """
    Returns (frontmatter_dict, body_text). If no valid frontmatter, returns ({}, md).
    Frontmatter format: first line '---', later line '---' ends it.
    """
    lines = md.splitlines()
    if not lines or lines[0].strip() != FRONTMATTER_DELIM:
        return {}, md

    end_idx = None
    for i in range(1, len(lines)):
        if lines[i].strip() == FRONTMATTER_DELIM:
            end_idx = i
            break

    if end_idx is None:
        return {}, md

    fm_text = "\n".join(lines[1:end_idx]).strip() + "\n"
    body = "\n".join(lines[end_idx + 1 :]).lstrip("\n")

    try:
        fm = yaml.safe_load(fm_text) or {}
        if not isinstance(fm, dict):
            fm = {}
    except Exception as e:
        print(f"ERROR: Failed to parse YAML frontmatter: {e}", file=sys.stderr)
        fm = {}

    return fm, body


def parse_dt(value: Any, tzname: str) -> Optional[datetime]:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    s = str(value).strip()
    if not s:
        return None

    dt = dtparser.parse(s)
    if dt.tzinfo is None:
        zone = dttz.gettz(tzname)
        dt = dt.replace(tzinfo=zone)
    return dt


def as_list(v: Any) -> list:
    if v is None:
        return []
    if isinstance(v, list):
        return v
    return [v]


def is_truthy(v: Any) -> bool:
    if isinstance(v, bool):
        return v
    if v is None:
        return False
    return str(v).strip().lower() in {"1", "true", "yes", "y", "on"}


@dataclass
class Decisions:
    status: str
    should_build: bool
    should_publish: bool
    should_announce_discord: bool
    reasons: list


def decide(frontmatter: Dict[str, Any], now: datetime, tzname: str) -> Decisions:
    status = str(frontmatter.get("status", "draft")).strip().lower()
    publish_at = parse_dt(frontmatter.get("publish_at"), tzname)
    discord_announce = is_truthy(frontmatter.get("discord_announce"))

    title = str(frontmatter.get("title", "")).strip()
    section = str(frontmatter.get("section", "")).strip()
    authors = [str(a).strip() for a in as_list(frontmatter.get("authors")) if str(a).strip()]
    tags = [str(t).strip() for t in as_list(frontmatter.get("tags")) if str(t).strip()]

    image = frontmatter.get("image") if isinstance(frontmatter.get("image"), dict) else {}
    image_src = str(image.get("src", "")).strip() if image else ""
    image_type = str(image.get("image_type", "")).strip().lower() if image else ""

    reasons: List[str] = []

    allowed_status = {"draft", "review", "scheduled", "published", "archived"}
    if status not in allowed_status:
        reasons.append(f"Unknown status '{status}' (allowed: {sorted(allowed_status)}).")

    should_build = status in {"draft", "review", "scheduled", "published"}
    if status == "archived":
        should_build = False
        reasons.append("Archived content is not built.")

    should_publish = False
    if status == "published":
        should_publish = True
    elif status == "scheduled":
        if publish_at is None:
            reasons.append("Status is scheduled but publish_at is missing, will not publish.")
        else:
            should_publish = now >= publish_at
            if not should_publish:
                reasons.append("Not time yet (now < publish_at).")
    else:
        reasons.append(f"Status is '{status}', will not publish.")

    should_announce_discord = bool(should_publish and discord_announce)

    # Soft warnings
    if not title:
        reasons.append("Missing title.")
    if not section:
        reasons.append("Missing section.")
    if not authors:
        reasons.append("Missing authors list.")
    if image_src and not image_type:
        reasons.append("Image has src but missing image_type.")
    if not tags:
        reasons.append("No tags set (can be ok).")

    return Decisions(
        status=status,
        should_build=should_build,
        should_publish=should_publish,
        should_announce_discord=should_announce_discord,
        reasons=reasons,
    )


def iter_markdown_files(root: str) -> Iterable[str]:
    """
    Walk root recursively and yield *.md, but skip any directory whose name starts
    with "_" or "." (templates, references, editor state, trash).
    """
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if not (d.startswith("_") or d.startswith("."))]

        for fn in filenames:
            if fn.lower().endswith(".md"):
                yield os.path.join(dirpath, fn)


@dataclass
class BulkResult:
    path: str
    ok: bool
    frontmatter: Dict[str, Any]
    decisions: Optional[Decisions]
    error: str = ""


def evaluate_file(path: str, now: datetime, tzname: str) -> BulkResult:
    try:
        md = read_text(path)
    except Exception as e:
        return BulkResult(path=path, ok=False, frontmatter={}, decisions=None, error=f"read failed: {e}")

    fm, _ = split_frontmatter(md)
    if not fm:
        return BulkResult(path=path, ok=False, frontmatter={}, decisions=None, error="missing or invalid frontmatter")

    try:
        d = decide(fm, now=now, tzname=tzname)
    except Exception as e:
        return BulkResult(path=path, ok=False, frontmatter=fm, decisions=None, error=f"decision failed: {e}")

    return BulkResult(path=path, ok=True, frontmatter=fm, decisions=d)


def relpath(path: str, base: str) -> str:
    try:
        return os.path.relpath(path, base)
    except Exception:
        return path


def print_bulk(results: List[BulkResult], base: str, as_json: bool = False) -> int:
    if as_json:
        import json

        payload = []
        for r in results:
            payload.append(
                {
                    "path": relpath(r.path, base),
                    "ok": r.ok,
                    "error": r.error,
                    "frontmatter": r.frontmatter,
                    "decisions": r.decisions.__dict__ if r.decisions else None,
                }
            )
        print(json.dumps(payload, indent=2, ensure_ascii=False))
        return 1 if any(not r.ok for r in results) else 0

    publish_now: List[BulkResult] = []
    scheduled_later: List[BulkResult] = []
    drafts_review: List[BulkResult] = []
    published: List[BulkResult] = []
    archived: List[BulkResult] = []
    problems: List[BulkResult] = []

    for r in results:
        if not r.ok or r.decisions is None:
            problems.append(r)
            continue

        st = r.decisions.status
        if st == "archived":
            archived.append(r)
        elif st == "published":
            published.append(r)
        elif st == "scheduled":
            if r.decisions.should_publish:
                publish_now.append(r)
            else:
                scheduled_later.append(r)
        elif st in {"draft", "review"}:
            drafts_review.append(r)
        else:
            problems.append(r)

    def show_group(title: str, items: List[BulkResult]) -> None:
        print(f"\n== {title} ({len(items)}) ==")
        for it in sorted(items, key=lambda x: x.path):
            fm = it.frontmatter or {}
            tid = fm.get("id", "")
            ttitle = fm.get("title", "")
            print(f"- {relpath(it.path, base)}")
            if tid or ttitle:
                print(f"  id: {tid}")
                print(f"  title: {ttitle}")

    show_group("PUBLISH NOW", publish_now)
    show_group("SCHEDULED LATER", scheduled_later)
    show_group("DRAFT/REVIEW", drafts_review)
    show_group("PUBLISHED", published)
    show_group("ARCHIVED", archived)

    if problems:
        print(f"\n== PROBLEMS ({len(problems)}) ==")
        for it in sorted(problems, key=lambda x: x.path):
            print(f"- {relpath(it.path, base)}")
            if it.error:
                print(f"  error: {it.error}")

    return 1 if problems else 0


def print_single(fm: Dict[str, Any], d: Decisions, now: datetime, as_json: bool = False, path: str = "") -> None:
    if as_json:
        import json

        payload = {
            "path": path,
            "now": now.isoformat(),
            "frontmatter": fm,
            "decisions": d.__dict__,
        }
        print(json.dumps(payload, indent=2, ensure_ascii=False))
        return

    print("== Frontmatter summary ==")
    print(f"id:          {fm.get('id')}")
    print(f"title:       {fm.get('title')}")
    print(f"section:     {fm.get('section')}")
    print(f"authors:     {fm.get('authors')}")
    print(f"publish_at:  {fm.get('publish_at')}")
    print(f"status:      {fm.get('status')}")
    print(f"tags:        {fm.get('tags')}")
    if isinstance(fm.get("image"), dict):
        img = fm["image"]
        print("image:")
        print(f"  src:       {img.get('src')}")
        print(f"  credit:    {img.get('credit')}")
        print(f"  source:    {img.get('source')}")
        print(f"  image_type:{img.get('image_type')}")
    print(f"discord_announce: {fm.get('discord_announce')}")
    print()

    print("== Decisions ==")
    print(f"now:                     {now.isoformat()}")
    print(f"should_build:            {d.should_build}")
    print(f"should_publish:          {d.should_publish}")
    print(f"should_announce_discord: {d.should_announce_discord}")
    print()

    if d.reasons:
        print("== Notes / reasons ==")
        for r in d.reasons:
            print(f"- {r}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("path", help="Path to a markdown file OR a directory to scan recursively")
    ap.add_argument("--tz", default="Europe/Copenhagen", help="Timezone for naive datetimes")
    ap.add_argument(
        "--now",
        default="",
        help='Override "now" (e.g. "2025-12-31 20:00"). If omitted, uses current time in --tz.',
    )
    ap.add_argument("--json", action="store_true", help="Output machine-readable JSON")
    args = ap.parse_args()

    zone = dttz.gettz(args.tz)
    if not zone:
        print(f"ERROR: Unknown timezone: {args.tz}", file=sys.stderr)
        return 2

    if args.now.strip():
        now = parse_dt(args.now, args.tz)
        if now is None:
            print("ERROR: Could not parse --now value.", file=sys.stderr)
            return 2
    else:
        now = datetime.now(tz=zone)

    target = args.path
    if os.path.isdir(target):
        base = target
        files = list(iter_markdown_files(target))
        if not files:
            if args.json:
                import json

                print(json.dumps([], indent=2, ensure_ascii=False))
            else:
                print("No .md files found.")
            return 0

        results = [evaluate_file(p, now=now, tzname=args.tz) for p in files]
        return print_bulk(results, base=base, as_json=args.json)

    # Single file mode
    md = read_text(target)
    fm, _ = split_frontmatter(md)
    if not fm:
        if args.json:
            import json

            print(json.dumps({"path": target, "ok": False, "error": "No valid frontmatter found."}, indent=2))
        else:
            print("No valid frontmatter found.")
        return 1

    d = decide(fm, now=now, tzname=args.tz)
    print_single(fm, d, now=now, as_json=args.json, path=target)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
