#!/usr/bin/env python3
import json
import subprocess
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
PUBLISH_SCRIPT = PROJECT_ROOT / "scripts" / "publish.py"
CONTENT_DIR = PROJECT_ROOT / "content"


def main() -> int:
    # Run publish.py in bulk JSON mode
    result = subprocess.run(
        [sys.executable, str(PUBLISH_SCRIPT), str(CONTENT_DIR), "--json"],
        capture_output=True,
        text=True,
        check=False,
    )

    # publish.py returns:
    # 0 = ok, no problems
    # 1 = ok, but problems found
    # other = hard failure
    if result.returncode not in (0, 1):
        print("ERROR: publish.py failed to run", file=sys.stderr)
        if result.stderr.strip():
            print(result.stderr, file=sys.stderr)
        return 2

    # Parse JSON output
    try:
        data = json.loads(result.stdout)
        if not isinstance(data, list):
            raise ValueError("Expected JSON list from publish.py")
    except Exception as e:
        print("ERROR: Could not parse JSON output from publish.py", file=sys.stderr)
        print(str(e), file=sys.stderr)
        if result.stderr.strip():
            print(result.stderr, file=sys.stderr)
        return 2

    # Separate problem files
    problems = [
        item for item in data
        if not item.get("ok", False)
    ]

    # Separate publishable items
    publish_now = [
        item for item in data
        if item.get("ok", False)
        and isinstance(item.get("decisions"), dict)
        and item["decisions"].get("should_publish") is True
    ]

    # Report problems first
    if problems:
        print("Problems detected:")
        for item in problems:
            path = item.get("path", "(unknown path)")
            error = item.get("error", "Unknown error")
            print(f"- {path}")
            print(f"  error: {error}")
        print()

    # Report publishable items
    if publish_now:
        print("Publish now:")
        for item in publish_now:
            path = item.get("path", "(unknown path)")
            fm = item.get("frontmatter", {}) if isinstance(item.get("frontmatter"), dict) else {}
            title = fm.get("title", "")

            print(f"- {path}")
            if title:
                print(f"  title: {title}")
    else:
        print("Nothing to publish.")

    # Exit codes:
    # 0  = nothing to do, no problems
    # 10 = publishable items exist
    # 20 = problems exist (but script still ran correctly)
    if publish_now:
        return 10
    if problems:
        return 20
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
