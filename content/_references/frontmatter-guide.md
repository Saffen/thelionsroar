# Lion’s Roar – Article Frontmatter Reference

This document explains each frontmatter field used in Lion’s Roar articles, what it controls, and how it should be used.

Frontmatter is the **contract** between the writer, the publisher system, the website, and Discord automation.  
Only put structured data here. No prose explanations inside the frontmatter itself.

---

## `id`

**Type:** string  
**Required:** yes  
**Example:**

```
id: 20260105-admiralty-patrols
```

**Purpose:**  
Permanent internal identifier for the article.

**Rules:**

- Must be unique
- Must never change after publication
- Not shown to readers


**Used for:**

- Tracking whether an article has already been published
- Preventing duplicate Discord announcements
- Stable internal references even if title or filename changes

**Convention:**  
Date-based prefix + short slug is recommended.

---

## `title`

**Type:** string  
**Required:** yes  
**Example:**

```
title: "Admiralty Announces New Patrols Across the Great Sea"
```

**Purpose:**  
The article headline.

**Used for:**

- Article page heading
- Frontpage and section teasers
- Discord announcement title
- Browser `<title>` and social previews

**Notes:**

- Can be edited after publication
- Changes do not affect internal identity

---

## `section`

**Type:** string (single value)  
**Required:** yes  
**Example:**

```
section: news
```

**Purpose:**  
Defines which part of the newspaper the article belongs to.

**Used for:**

- URL structure (`/news/...`)
- Section frontpages
- Navigation highlighting

**Allowed values (example set):**

- `news`
- `events`
- `opinion`
- `magazines`
- `community`

This is **not** a tag.

---

## `authors`

**Type:** list of strings  
**Required:** yes  
**Example:**

```
authors:
  - Hardhy Lester
  - Rosie Geargrind
```

**Purpose:**  
Article byline.

**Used for:**

- Displayed byline
- Discord announcements
- Author archives later

**Rules:**

- Always use a list, even for one author
- Order matters (first author is primary)

---

## `teaser`

**Type:** string  
**Required:** yes  
**Example:**

```
teaser: "The Admiralty confirms expanded patrols as piracy rises across key trade routes."
```

**Purpose:**  
Short editorial summary written by the author.

**Used for:**

- Frontpage cards
- Section listings
- Discord announcement body
- Social previews

**Notes:**

- Should be 1–2 sentences
- Written intentionally, not auto-generated

---

## `publish_at`

**Type:** datetime string  
**Required:** yes  
**Example:**

```
publish_at: 2026-01-05 20:00
```

**Purpose:**  
Controls when the article becomes publicly visible.

**Used for:**

- Scheduled publishing
- Triggering Discord announcements

**Rules:**

- Server local time
- Can be in the past for immediate publication
- Must be machine-readable

---

## `status`

**Type:** string  
**Required:** yes  
**Example:**

```
status: draft
```

**Purpose:**  
Editorial state of the article.

**Supported values:**

- `draft`  
    Article is ignored entirely.
- `scheduled`  
    Article publishes when `publish_at` is reached.
- `published`  
    Article is always visible regardless of date.
- `hidden`  
    Article is removed from the site but kept on disk.

**Used for:**

- Safe drafting
- Retractions
- Manual overrides

---

## `discord_announce`

**Type:** boolean  
**Required:** yes  
**Example:**

```
discord_announce: true
```

**Purpose:**  
Controls whether a Discord post is sent when the article is published.

**Notes:**

- Set to `false` for quiet publications
- Prevents spam for corrections or backfilled articles

---

## `tags`

**Type:** list of strings  
**Required:** no  
**Example:**

```
tags:
  - Stormwind
  - Proudmoore Admiralty
  - Piracy
```

**Purpose:**  
Cross-cutting classification for themes, locations, institutions, and storylines.

**Used for:**

- Related articles
- Tag archive pages
- Storyline tracking

**Notes:**

- Tags are case-sensitive and should be consistent
- Avoid duplicates and near-synonyms

---

## `image`

**Type:** object  
**Required:** no

### `image.src`

```
src: /assets/images/admiralty.jpg
```

Path to the lead image.

### `image.credit`

```
credit: "M. Ironquill"
```

Who created the image.

### `image.source`

```
source: "Lion's Roar archives"
```

Optional provenance or courtesy line.

### `image.type`

```
type: illustration
```

Optional classification.

**Suggested values (convention only):**

- `illustration`
- `screenshot`
- `submission`

---

## `kicker`

**Type:** string  
**Required:** no  
**Example:**

```
kicker: "Exclusive · Alliance"
```

**Purpose:**  
Short label displayed above the headline.

**Used for:**

- Visual hierarchy
- Editorial emphasis
- Frontpage styling

---

## Fields intentionally not included (yet)

These are derived or editorial decisions and should not be in frontmatter at this stage:

- Read time
- Word count
- Slug or URL
- Layout flags
- View counts
- Editorial notes

---

## Summary

Frontmatter exists to:

- control publication
- describe content
- enable automation

If a field does not do one of those, it does not belong here.

---
