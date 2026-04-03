# Brand Logo Spacing: Previous Values

Rollback reference for the masthead logo spacing change.

## Previous SVG/CSS values

- `templates/base.html`
  - `.brand-text svg` used `viewBox="0 0 500 140"`

- `assets/css/newbase.css`
  - `.brand-text svg` used `margin-bottom: -48px;`
  - `:root[data-theme="immersive"] .brand-text svg` used `margin-bottom: -48px;`
  - In `@media (max-width: 900px)`, `.tagline` and `:root[data-theme="immersive"] .tagline` used `margin-top: -48px;`

## Current intent

The SVG `viewBox` now trims the unused lower whitespace so `.brand-text svg` and `.tagline` can stack normally without fixed negative margins. If the desktop spacing feels off, restore the values above first.