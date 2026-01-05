#!/usr/bin/env python3
import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Tuple


PROJECT_ROOT = Path(__file__).resolve().parents[1]
PUBLISH_SCRIPT = PROJECT_ROOT / "scripts" / "publish.py"
DEFAULT_CONTENT_DIR = PROJECT_ROOT / "content"
DEFAULT_STATE_FILE = PROJECT_ROOT / "state" / "published.json"


def load_state(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            return data
        return {}
    except Exception:
        return {}


def save_state(path: Path, state: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def iso_now_utc() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def run_publish_json(content_dir: Path) -> Tuple[int, str, str]:
    result = subprocess.run(
        [sys.executable, str(PUBLISH_SCRIPT), str(content_dir), "--json"],
        capture_output=True,
        text=True,
        check=False,
    )
    return result.returncode, result.stdout, result.stderr


def main() -> int:
    ap = argparse.ArgumentParser(description="Orchestrate publish decisions and track state.")
    ap.add_argument("--content", default=str(DEFAULT_CONTENT_DIR), help="Content root to scan (default: ./content)")
    ap.add_argument("--state", default=str(DEFAULT_STATE_FILE), help="State file path (default: ./state/published.json)")
    ap.add_argument(
        "--apply",
        action="store_true",
        help="Write new publish entries to the state file. Default is dry-run.",
    )
    args = ap.parse_args()

    content_dir = Path(args.content).resolve()
    state_path = Path(args.state).resolve()

    rc, out, err = run_publish_json(content_dir)

    # publish.py returns:
    # 0 = ok, no problems
    # 1 = ok, but problems exist (still prints valid JSON)
    # other = hard failure
    if rc not in (0, 1):
        print("ERROR: publish.py failed to run", file=sys.stderr)
        if err.strip():
            print(err, file=sys.stderr)
        return 2

    try:
        data = json.loads(out)
        if not isinstance(data, list):
            raise ValueError("Expected JSON list from publish.py bulk mode.")
    except Exception as e:
        print("ERROR: Could not parse JSON output from publish.py", file=sys.stderr)
        print(str(e), file=sys.stderr)
        if err.strip():
            print(err, file=sys.stderr)
        return 2

    state = load_state(state_path)

    problems: List[Dict[str, Any]] = []
    publish_now_new: List[Dict[str, Any]] = []
    publish_now_existing: List[Dict[str, Any]] = []

    for item in data:
        if not item.get("ok", False):
            problems.append(item)
            continue

        decisions = item.get("decisions")
        if not isinstance(decisions, dict):
            item2 = dict(item)
            item2["error"] = "missing decisions block"
            problems.append(item2)
            continue

        if decisions.get("should_publish") is not True:
            continue

        fm = item.get("frontmatter")
        if not isinstance(fm, dict):
            item2 = dict(item)
            item2["error"] = "missing frontmatter block"
            problems.append(item2)
            continue

        article_id = fm.get("id")
        if not isinstance(article_id, str) or not article_id.strip():
            item2 = dict(item)
            item2["error"] = "missing frontmatter.id"
            problems.append(item2)
            continue

        article_id = article_id.strip()

        if article_id in state:
            publish_now_existing.append(item)
        else:
            publish_now_new.append(item)

    # Output problems
    if problems:
        print("Problems detected:")
        for p in problems:
            p_path = p.get("path", "(unknown path)")
            p_err = p.get("error", "Unknown error")
            print(f"- {p_path}")
            print(f"  error: {p_err}")
        print()

    # Output publishable
    if publish_now_new:
        print("To publish (not yet in state):")
        for it in publish_now_new:
            p = it.get("path", "(unknown path)")
            fm = it.get("frontmatter", {}) if isinstance(it.get("frontmatter"), dict) else {}
            title = fm.get("title", "")
            aid = fm.get("id", "")
            print(f"- {p}")
            print(f"  id: {aid}")
            if title:
                print(f"  title: {title}")
        print()
    else:
        print("To publish (not yet in state): none\n")

    if publish_now_existing:
        print("Already in state (would publish, but recorded):")
        for it in publish_now_existing:
            p = it.get("path", "(unknown path)")
            fm = it.get("frontmatter", {}) if isinstance(it.get("frontmatter"), dict) else {}
            title = fm.get("title", "")
            aid = fm.get("id", "")
            print(f"- {p}")
            print(f"  id: {aid}")
            if title:
                print(f"  title: {title}")
        print()
    else:
        print("Already in state (would publish, but recorded): none\n")

    # Apply state updates (only for items newly publishable)
    if args.apply and publish_now_new:
        now_utc = iso_now_utc()
        for it in publish_now_new:
            fm = it["frontmatter"]
            aid = fm["id"].strip()
            state[aid] = {
                "path": it.get("path"),
                "title": fm.get("title"),
                "section": fm.get("section"),
                "publish_at": fm.get("publish_at"),
                "recorded_at": now_utc,
                # Placeholder for later:
                # When we post to Discord, we will store:
                # { "channel_id": "...", "message_id": "...", "posted_at": "..." }
                "discord": None,
            }

        save_state(state_path, state)
        print(f"Wrote {len(publish_now_new)} new entrie(s) to state: {state_path}\n")

    # Exit codes:
    # 10 = work to do (new items to publish)
    # 20 = problems exist but no new publish items
    # 0  = nothing to do, no problems
    if publish_now_new:
        return 10
    if problems:
        return 20
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
