# Record format

Each record is one Markdown file in `records/<folder>/`, named `<ID>-<slug>.md`.
Create records with `kit.py new <type> "Title"`, which picks the next free ID.

```yaml
---
id: PZ-004
title: Star chart alignment
type: puzzle
status: candidate
links: [PP-002, Q-007]
superseded_by:
tags: []
---
Free notes in Markdown. Mentioning an ID like PZ-002 turns it into a link.
```

The build computes these, so you never type them:
- **Last touched**: from git (or the file date for uncommitted edits)
- **Backlinks**: "Referenced by" in the viewer
- **Stale flag**: `idea` or `candidate`, untouched for more than `staleDays` (in `backpack.json`, default 30)

## Types

| Type | Prefix | Folder | Extra fields |
|---|---|---|---|
| premise | PR | `premise/` | `aspect`: sender / player goal / story / tone / ending / other |
| beat | ST | `structure/` | `order` (number), `label`, `reveals` |
| puzzle | PZ | `puzzles/` | `beat` (one ID), `props` [IDs], `needs` [IDs], `mechanic`, `difficulty` 1–3, `answer` |
| prop | PP | `props/` | `form`: physical / printed / digital, `source`: make / buy / print |
| question | Q | `questions/` | `about` [IDs], `answer` |
| asset | AS | `assets/` | `kind`: image / audio / text / print, `for` (one prop ID), `tool`, `file`. The body holds the generation prompt. |

"Structure beat" is the generic name. Each backpack sets what the player sees it as
in `backpack.json` → `beatLabel` (the Norse backpack used postcards).

## Status

- Most types: `idea` → `candidate` → `decided` → `built`, or `parked`
- Questions: `open` → `answered`, or `parked`
- Replaced: keep the old record and set `superseded_by: <new ID>`. It moves to the Parked tab.

## One fact, one place

Each relationship is stored on **one** side only. The viewer shows the other side.

| Stored on | Field | Shown on the other record as |
|---|---|---|
| puzzle | `beat` | the beat's puzzle list |
| puzzle | `props` | "used by" on the prop |
| puzzle | `needs` | "needed by" (feeds the v2 flow chart) |
| asset | `for` | the prop's asset list |
| question | `about` | "questions about this" |
| any | `links` | "linked from" |

## Syntax rules (small YAML subset)
- `key: value` on one line. Lists are `[A, B]` or `- item` lines underneath.
- Lines starting with `#` are comments.
- Long text goes in the body, not in a field.
- `kit.py check` reports unknown IDs, wrong prefixes, bad statuses and duplicates.
