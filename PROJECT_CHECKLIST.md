# The Lion's Roar Project Checklist

Last updated: 2026-03-23

This is the working status file for the project. It should be updated as we make progress so the current state stays visible in-repo.

## Confirmed Working / Accepted As Done

- [x] Source content structure exists for static pages and news articles.
- [x] Static site generation exists through `scripts/build.py` and `scripts/build_pages.py`.
- [x] CMS/editor exists through `api/main.py` and `templates/admin_editor.html`.
- [x] Article workflow exists for draft, build, scheduled, published, and deleted states.
- [x] Article version snapshots and restore flow exist.
- [x] Discord publish/announce workflow exists in scripts.
- [x] Games are considered functional as-is.
- [x] Event signup flow is considered functional as-is.
- [x] Routing between nginx, admin, and API is handled outside the repo and should be treated as working.
- [x] Admin protection is handled outside the repo via `.htaccess` and should be treated as working.
- [x] Public templates now hide section-driven navigation and tag UI for the simplified article-first structure.
- [x] Homepage scaffolding now supports optional modules such as games, comics, or crosswords without making them mandatory.
- [x] Shared nav, footer, and explore links now live in content/config.yaml.
- [x] Article-page Explore links now render at build time from the shared config, instead of relying on runtime widget data.

## In Progress / Partially Complete

- [ ] Public-facing homepage is fully restored and serving real site content.
- [ ] Source-driven homepage generation is wired up and actively used.
- [ ] Article archive or recent-articles browsing experience is complete.
- [ ] Homepage content blocks are populated from real content instead of placeholders.
- [ ] Local development setup is documented and reproducible on the current machine.
- [ ] Build/publish workflow can be run cleanly from the current environment without setup issues.
- [ ] Deployment/runtime expectations are documented clearly enough for recovery or handoff.

## Current Known Gaps

- [ ] Replace the placeholder root page in `build/public/index.php` with the real homepage.
- [ ] Build and verify the new source-driven homepage output from `content/pages/home.md`.
- [ ] Confirm the homepage lead now only uses truly public content.
- [ ] Confirm the recent-articles and earlier-editions blocks render cleanly with a small article inventory.
- [ ] Decide whether there should also be a dedicated archive or all-articles page.
- [ ] Decide whether tag pages are needed later, even if hidden for now.
- [ ] Verify the Docker/deploy packaging includes all files the API expects at runtime.
- [ ] Document the production stack clearly.
- [ ] Document static output responsibilities.
- [ ] Document FastAPI admin/API responsibilities.
- [ ] Document PHP-backed legacy or standalone feature responsibilities.
- [ ] Clean up or document legacy folders so it is clear what is active vs archival.

## Infrastructure Assumptions

These are currently treated as solved outside the repo unless proven otherwise.

- [x] nginx handles the route mapping between public paths and API/admin paths.
- [x] `.htaccess` protects the admin area appropriately.
- [x] Games can remain as standalone working features.
- [x] Event signup pages can remain as standalone working features.

## Notes

- The repo currently contains authored source content, generated `build/` output, API code, and some legacy material.
- The current direction is an article-first public site with optional add-on modules such as comics, crosswords, events, or games when content exists.
- The main remaining work appears to be homepage/article-feed completeness and project operability/documentation, not the games or signup flow.

## Update Log

- 2026-03-23: Created initial checklist from repo review and deployment context provided in chat.
- 2026-03-23: Simplified public templates to hide section-driven navigation and public tag display.
- 2026-03-23: Reframed the checklist around an article-first homepage with optional modules instead of required public sections.
- 2026-03-23: Added a source-driven homepage scaffold that promotes the latest public article automatically.
- 2026-03-23: Tightened homepage selection to true public content and moved shared link sets into content/config.yaml.
- 2026-03-23: Moved article-page Explore links to build-time rendering from the shared config.
- 2026-03-23: Implemented the immersive nav toggle and replaced the placeholder header social dots with a real Discord invite link.