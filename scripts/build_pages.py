#!/usr/bin/env python3

import argparse
from pathlib import Path

from build import PUZZLE_CONFIG_DIR, REPO_ROOT, build, build_puzzles_landing, ensure_public_assets


PAGES_DIR = REPO_ROOT / 'content' / 'pages'


def iter_page_files(root: Path) -> list[Path]:
    if not root.exists():
        return []
    return sorted(
        path for path in root.rglob('*.md')
        if all(not part.startswith('_') and not part.startswith('.') for part in path.relative_to(root).parts)
    )


def iter_puzzle_files(root: Path) -> list[Path]:
    if not root.exists():
        return []
    return sorted(
        path for path in root.rglob('*')
        if path.is_file()
        and path.suffix.lower() in {'.yaml', '.yml'}
        and all(not part.startswith('_') and not part.startswith('.') for part in path.relative_to(root).parts)
    )


def main() -> int:
    parser = argparse.ArgumentParser(description='Build static pages from content/pages plus puzzle configs from content/puzzles.')
    parser.add_argument('--mode', choices=['public', 'internal'], default='public')
    parser.add_argument('--sync-assets', action='store_true', help='Refresh build/public/assets and build/internal/assets first')
    parser.add_argument('--pages-dir', default=str(PAGES_DIR), help='Override the pages source directory')
    parser.add_argument('--puzzles-dir', default=str(PUZZLE_CONFIG_DIR), help='Override the puzzle config directory')
    args = parser.parse_args()

    pages_dir = Path(args.pages_dir)
    puzzles_dir = Path(args.puzzles_dir)
    page_files = iter_page_files(pages_dir)
    puzzle_files = iter_puzzle_files(puzzles_dir)

    if not page_files and not puzzle_files:
        print(f'No page markdown files found in {pages_dir} and no puzzle configs found in {puzzles_dir}')
        return 0

    if args.sync_assets:
        ensure_public_assets()

    for page_file in page_files:
        build(page_file, mode=args.mode)

    for puzzle_file in puzzle_files:
        build(puzzle_file, mode=args.mode)

    build_puzzles_landing(mode=args.mode)

    print(f'Built {len(page_files)} page(s), {len(puzzle_files)} puzzle(s), and the puzzles landing page')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
