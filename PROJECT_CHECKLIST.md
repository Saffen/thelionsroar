# The Lion's Roar Project Checklist

Last updated: 2026-04-01

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
- 2026-03-30: Updated the homepage left-rail heading to use the same widget-title styling as the right rail for consistent headline presentation.
- 2026-03-30: Fixed theme persistence so immersive mode is restored on refresh the same way light and dark modes are.
- 2026-03-30: Enabled markdown rendering for the homepage about_text block so right-rail copy can include links and other simple formatting.
- 2026-03-31: Improved admin article-save diagnostics so the publish endpoint returns step-aware JSON errors and the admin panel shows useful failure details instead of a generic malformed JSON message.
- 2026-03-31: Replaced the article-page Explore rail with a shared Recent Articles rail, matched its feed to the homepage logic, and restyled both rails with thumbnail-based cards inspired by the Live News widget.
- 2026-03-31: Tightened the shared Recent Articles rail styling into a more compact horizontal thumbnail layout after the first pass rendered too large and heavy in the rail.
- 2026-03-31: Adjusted shared Recent Articles thumbnails to preserve a more natural article-image proportion instead of forcing them into square crops.
- 2026-03-31: Made the shared header brand area clickable so the lion logo and site title link back to the homepage.
- 2026-04-01: Fixed deleted-article public-state handling so deleted items are removed from live publish state, excluded from homepage/public rebuild logic, and have stale generated public output cleaned up.
- 2026-04-01: Upgraded the admin workflow so Save Build performs an internal build, Publish Now/Update Live rebuild the live public site, and saved live articles can be announced individually from both the editor and the Library list.
- 2026-04-02: Added Open Graph and Twitter card metadata for article pages, and made article hero images open in a mobile-friendly lightbox when tapped or clicked.
