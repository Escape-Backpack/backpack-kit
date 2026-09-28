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
| puzzle | PZ | `puzzles/` | `beat` (one ID), `props` [IDs], `needs` [IDs], `mechanic`, `difficulty` 1–3, `lock`, `answer` |
| prop | PP | `props/` | `form`: physical / printed / digital, `source`: make / buy / print / 3d-print, `found_in`: `start` or a puzzle ID |
| question | Q | `questions/` | `about` [IDs], `answer` |
| asset | AS | `assets/` | `kind`: image / audio / text / print, `for` (one prop ID), `tool`, `file`. The body holds the generation prompt. |

`lock` must be one of the lock types in `backpack.json` → `locks`. The default is the kit's
standard set (see GUIDE.md): `3-digit`, `4-digit`, `4-letter`, `3-digit-colour`.

"Structure beat" is the generic name. Each backpack sets what the player sees it as
in `backpack.json` → `beatLabel` (the Norse backpack used postcards).

## Status

- Most types: `idea` → `candidate` → `decided` → `built`, or `parked`
- Questions: `open` → `answered`, or `parked`
- Replaced: keep the old record and set `superseded_by: <new ID>`. It moves to the Parked tab.

### Testing and release are separate

Puzzle fields: `test_status: untested | passed | changes-needed`, `test_method:
physical | digital`, `publish_hints: yes | no`, and optional `technique` (library URL).
Old records without these fields remain valid: missing testing means unrecorded;
missing publish_hints means private. No historical puzzle is automatically marked tested.

The puzzle body adds `## Player notices`, `## Player does`, `## Player obtains`,
`## Story reason`, `## Reading order` and `## Playtest evidence`. Evidence records
date, version/files, method, observed actions/stalls, hints used, interpretation,
change and retest. After relevant edits set test_status back to untested.

Props add `container` (physical location) and `## Starting state`, `## Reset`,
`## Replacement`. Use explicit "None needed" where appropriate. `found_in` remains
the single source for availability; it does not mean physical location.

### Checks and generated views

- `check`: record validity, reference existence/types and allowed values.
- `ready`: playtest preparation for decided/built puzzles and props. Flags unreachable
  puzzles/props, missing solving notes, answers, incompatible standard lock formats,
  missing setup/reset and missing player-visible materials.
- `ready --include-candidates`: includes draft candidates without changing status.
- `ready --release`: also requires a recorded passed physical playtest and evidence.
  An empty selected game does not pass. Missing fields are gaps, not auto-filled facts.
- Flow includes active ideas/candidates, showing needs, prop use and prop releases.
  Missing availability and cycles remain marked unresolved. The text list gives the
  same connections without relying on the diagram.
- Setup & reset derives its table from prop records. No separate checklist to maintain.

## One fact, one place

Each relationship is stored on **one** side only. The viewer shows the other side.

| Stored on | Field | Shown on the other record as |
|---|---|---|
| puzzle | `beat` | the beat's puzzle list |
| puzzle | `props` | "used by" on the prop |
| puzzle | `needs` | "needed by" (feeds the v2 flow chart) |
| asset | `for` | the prop's asset list |
| question | `about` | "questions about this" |
| prop | `found_in` | "opens to reveal" on the puzzle |
| any | `links` | "linked from" |

## Play-test page (`play.html`)
Built from the records, never edited by hand. It uses puzzles and props that are
`decided` or `built` (a toggle adds `candidate`), and plays them like this:

1. The player starts with every prop that has `found_in: start`.
2. A lock can be tried once its `needs` are open and its `props` are in hand.
3. The typed code is checked against `answer`. Case, spaces and dashes are ignored.
4. Opening it reveals the props with `found_in: <that puzzle>`.

What a prop shows: its image assets (`kind: image` with a `file`), and/or the
`## Player sees` section of its body. A puzzle's `## Hints` list becomes the hint ladder.
"Designer checks" at the bottom lists locks that can never be opened, props the
player never gets, and props with nothing to show.

## Hint page (`hints/index.html`)
A public, player-facing page built into `site/hints/`, one self-contained file.
It includes only `decided` and `built` puzzles explicitly marked `publish_hints: yes`, in play order, each with:
- its `hint_title`: what players call the lock, with no spoilers (for example "The luggage tag")
- the `## Hints` list, one hint at a time
- the solution: `answer`, plus the `## Solution` section of the puzzle's body

Candidates are excluded from the file itself, including when `?all` is requested.
Published records must have a hint title, hints, solution and an answer if they use
a lock. Existing projects must explicitly opt in when ready; their public hint
page will otherwise be empty after rebuilding. Use private play.html for drafts.
Progress uses stable puzzle IDs, not array positions; this version starts a new
browser progress namespace rather than misreading older position-based progress.

Nothing else from the records is included. Team name, timer and progress stay in the player's browser.

## Syntax rules (small YAML subset)
- `key: value` on one line. Lists are `[A, B]` or `- item` lines underneath.
- Lines starting with `#` are comments.
- Long text goes in the body, not in a field.
- `kit.py check` reports unknown IDs, wrong prefixes, bad statuses and duplicates.
