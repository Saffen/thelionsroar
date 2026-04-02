# Crossword Puzzle Config Guide

Add a new YAML file in `content/puzzles/` and rebuild with `scripts/build_pages.py`.

## Minimal schema

```yaml
id: my-puzzle
title: My Puzzle Title
teaser: Short card copy for the landing page.
intro: Optional intro at the top of the puzzle page.
difficulty: Easy
published: true
entries:
  - direction: across
    row: 0
    col: 0
    answer: ROAR
    clue: The paper's namesake sound.
  - direction: down
    row: 0
    col: 0
    answer: RUNE
    clue: Ancient carved letter.
```

## Supported fields

- `id`: Optional slug. Defaults to the filename.
- `title`: Required display title.
- `kicker`: Optional small label above the title.
- `teaser`: Optional short summary used on the `/puzzles/` landing page.
- `intro`: Optional intro paragraph on the puzzle page.
- `difficulty`: Optional label shown above the grid.
- `published`: Optional boolean. Set `false` to keep a config out of the generated landing page.
- `output_path`: Optional custom output path. Defaults to `puzzles/<id>/`.
- `details`: Optional markdown block rendered below the puzzle.
- `listing`: Optional card settings.
- `entries`: Required list of crossword answers and clues.

## Entry fields

- `direction`: Required. Use `across` or `down`.
- `row`: Required zero-based row index.
- `col`: Required zero-based column index.
- `answer`: Required. Letters and digits are used to build the grid.
- `clue`: Required clue text.

## Notes

- Black squares are inferred automatically from unused coordinates.
- Puzzle numbering is generated from the start position of each entry.
- If two answers cross, the shared letter must match or the build will fail.
- The visitor's progress is saved locally in their browser.
