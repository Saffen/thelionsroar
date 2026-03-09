#!/usr/bin/env python3
"""
publish.py
- If PATH is a file: print frontmatter + decisions (single mode)
- If PATH is a directory: scan all *.md recursively and print grouped decisions (bulk mode)
- Optional: --json for machine-readable output
"""

from __future__ import annotations

import argparse
import os
import sys
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, Iterable, List, Optional, Tuple

try:
    import yaml
except Exception:
    print("ERROR: Missing dependency PyYAML. Install with: pip install pyyaml", file=sys.stderr)
    raise

try:
    from dateutil import parser as dtparser
    from dateutil import tz as dttz
except Exception:
    print("ERROR: Missing dependency python-dateutil. Install with: pip install python-dateutil", file=sys.stderr)
    raise


FRONTMATTER_DELIM = "---"
ALLOWED_STATUS = {"draft", "build", "scheduled", "published", "deleted"}


def read_text(path: str) -> str:
    with open(path, "r", encoding="utf-8") as handle:
        return handle.read()


def split_frontmatter(md: str) -> Tuple[Dict[str, Any], str]:
    lines = md.splitlines()
    if not lines or lines[0].strip() != FRONTMATTER_DELIM:
        return {}, md

    end_idx = None
    for index in range(1, len(lines)):
        if lines[index].strip() == FRONTMATTER_DELIM:
            end_idx = index
            break

    if end_idx is None:
        return {}, md

    fm_text = "\n".join(lines[1:end_idx]).strip() + "\n"
    body = "\n".join(lines[end_idx + 1 :]).lstrip("\n")

    try:
        fm = yaml.safe_load(fm_text) or {}
        if not isinstance(fm, dict):
            fm = {}
    except Exception as exc:
        print(f"ERROR: Failed to parse YAML frontmatter: {exc}", file=sys.stderr)
        fm = {}

    return fm, body


def parse_dt(value: Any, tzname: str) -> Optional[datetime]:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    text = str(value).strip()
    if not text:
        return None

    dt = dtparser.parse(text)
    if dt.tzinfo is None:
        zone = dttz.gettz(tzname)
        dt = dt.replace(tzinfo=zone)
    return dt


def as_list(value: Any) -> list:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def is_truthy(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    return str(value).strip().lower() in {"1", "true", "yes", "y", "on"}


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
    authors = [str(author).strip() for author in as_list(frontmatter.get("authors")) if str(author).strip()]
    tags = [str(tag).strip() for tag in as_list(frontmatter.get("tags")) if str(tag).strip()]

    image = frontmatter.get("image") if isinstance(frontmatter.get("image"), dict) else {}
    image_src = str(image.get("src", "")).strip() if image else ""
    image_type = str(image.get("image_type", "")).strip().lower() if image else ""

    reasons: List[str] = []

    if status not in ALLOWED_STATUS:
        reasons.append(f"Unknown status '{status}' (allowed: {sorted(ALLOWED_STATUS)}).")

    should_build = status in {"build", "scheduled", "published"}
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
    elif status == "build":
        reasons.append("Build status creates internal output only; it is not public.")
    elif status == "draft":
        reasons.append("Draft content is not built or published.")
    elif status == "deleted":
        reasons.append("Deleted content is retained internally but hidden from public output.")

    should_announce_discord = bool(should_publish and discord_announce)

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
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if not (d.startswith("_") or d.startswith("."))]
        for filename in filenames:
            if filename.lower().endswith(".md"):
                yield os.path.join(dirpath, filename)


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
    except Exception as exc:
        return BulkResult(path=path, ok=False, frontmatter={}, decisions=None, error=f"read failed: {exc}")

    fm, _ = split_frontmatter(md)
    if not fm:
        return BulkResult(path=path, ok=False, frontmatter={}, decisions=None, error="missing or invalid frontmatter")

    try:
        decisions = decide(fm, now=now, tzname=tzname)
    except Exception as exc:
        return BulkResult(path=path, ok=False, frontmatter=fm, decisions=None, error=f"decision failed: {exc}")

    return BulkResult(path=path, ok=True, frontmatter=fm, decisions=decisions)


def relpath(path: str, base: str) -> str:
    try:
        return os.path.relpath(path, base)
    except Exception:
        return path


def print_bulk(results: List[BulkResult], base: str, as_json: bool = False) -> int:
    if as_json:
        import json

        payload = []
        for result in results:
            payload.append(
                {
                    "path": relpath(result.path, base),
                    "ok": result.ok,
                    "error": result.error,
                    "frontmatter": result.frontmatter,
                    "decisions": result.decisions.__dict__ if result.decisions else None,
                }
            )
        print(json.dumps(payload, indent=2, ensure_ascii=False))
        return 1 if any(not result.ok for result in results) else 0

    publish_now: List[BulkResult] = []
    scheduled_later: List[BulkResult] = []
    build_only: List[BulkResult] = []
    drafts: List[BulkResult] = []
    published: List[BulkResult] = []
    deleted: List[BulkResult] = []
    problems: List[BulkResult] = []

    for result in results:
        if not result.ok or result.decisions is None:
            problems.append(result)
            continue

        status = result.decisions.status
        if status == "deleted":
            deleted.append(result)
        elif status == "published":
            published.append(result)
        elif status == "scheduled":
            if result.decisions.should_publish:
                publish_now.append(result)
            else:
                scheduled_later.append(result)
        elif status == "build":
            build_only.append(result)
        elif status == "draft":
            drafts.append(result)
        else:
            problems.append(result)

    def show_group(title: str, items: List[BulkResult]) -> None:
        print(f"\n== {title} ({len(items)}) ==")
        for item in sorted(items, key=lambda current: current.path):
            fm = item.frontmatter or {}
            tid = fm.get("id", "")
            ttitle = fm.get("title", "")
            print(f"- {relpath(item.path, base)}")
            if tid or ttitle:
                print(f"  id: {tid}")
                print(f"  title: {ttitle}")

    show_group("PUBLISH NOW", publish_now)
    show_group("SCHEDULED LATER", scheduled_later)
    show_group("BUILD ONLY", build_only)
    show_group("DRAFT", drafts)
    show_group("PUBLISHED", published)
    show_group("DELETED", deleted)

    if problems:
        print(f"\n== PROBLEMS ({len(problems)}) ==")
        for item in sorted(problems, key=lambda current: current.path):
            print(f"- {relpath(item.path, base)}")
            if item.error:
                print(f"  error: {item.error}")

    return 1 if problems else 0


def print_single(fm: Dict[str, Any], decisions: Decisions, now: datetime, as_json: bool = False, path: str = "") -> None:
    if as_json:
        import json

        payload = {
            "path": path,
            "now": now.isoformat(),
            "frontmatter": fm,
            "decisions": decisions.__dict__,
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
    print(f"should_build:            {decisions.should_build}")
    print(f"should_publish:          {decisions.should_publish}")
    print(f"should_announce_discord: {decisions.should_announce_discord}")
    print()

    if decisions.reasons:
        print("== Notes / reasons ==")
        for reason in decisions.reasons:
            print(f"- {reason}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("path", help="Path to a markdown file OR a directory to scan recursively")
    parser.add_argument("--tz", default="Europe/Copenhagen", help="Timezone for naive datetimes")
    parser.add_argument("--now", default="", help='Override "now" (e.g. "2025-12-31 20:00"). If omitted, uses current time in --tz.')
    parser.add_argument("--json", action="store_true", help="Output machine-readable JSON")
    args = parser.parse_args()

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

        results = [evaluate_file(path, now=now, tzname=args.tz) for path in files]
        return print_bulk(results, base=base, as_json=args.json)

    md = read_text(target)
    fm, _ = split_frontmatter(md)
    if not fm:
        if args.json:
            import json
            print(json.dumps({"path": target, "ok": False, "error": "No valid frontmatter found."}, indent=2))
        else:
            print("No valid frontmatter found.")
        return 1

    decisions = decide(fm, now=now, tzname=args.tz)
    print_single(fm, decisions, now=now, as_json=args.json, path=target)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
