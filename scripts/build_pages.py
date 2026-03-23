#!/usr/bin/env python3

import argparse
import sys
from pathlib import Path

from build import REPO_ROOT, build, ensure_public_assets


PAGES_DIR = REPO_ROOT / 'content' / 'pages'


def iter_page_files(root: Path) -> list[Path]:
    if not root.exists():
        return []
    return sorted(
        path for path in root.rglob('*.md')
        if all(not part.startswith('_') and not part.startswith('.') for part in path.parts)
    )


def main() -> int:
    parser = argparse.ArgumentParser(description='Build only source-driven static pages from content/pages.')
    parser.add_argument('--mode', choices=['public', 'internal'], default='public')
    parser.add_argument('--sync-assets', action='store_true', help='Refresh build/public/assets and build/internal/assets first')
    parser.add_argument('--pages-dir', default=str(PAGES_DIR), help='Override the pages source directory')
    args = parser.parse_args()

    pages_dir = Path(args.pages_dir)
    page_files = iter_page_files(pages_dir)
    if not page_files:
        print(f'No page markdown files found in {pages_dir}')
        return 0

    if args.sync_assets:
        ensure_public_assets()

    for page_file in page_files:
        build(page_file, mode=args.mode)

    print(f'Built {len(page_files)} page(s) from {pages_dir}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
