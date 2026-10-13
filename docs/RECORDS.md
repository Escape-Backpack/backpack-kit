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
- **Last touched** and **history**: from git (or the file date for uncommitted edits)
- **Backlinks**: "used by", "puzzles" and so on in the viewer
- **Envelope codes**: from each puzzle's `answer` and the cipher in `backpack.json`

## The board
Three tabs: **Story** (premise and beats), **Puzzles** and **Props**. Questions and files
show inside the record they're about, not on tabs of their own. A status filter on each tab
shows ideas, candidates, decided, built or parked records.

## Types

| Type | Prefix | Folder | Extra fields |
|---|---|---|---|
| premise | PR | `premise/` | `aspect`: sender / player goal / story / tone / ending / other |
| beat | ST | `structure/` | `order` (number) |
| puzzle | PZ | `puzzles/` | `beat` (one ID), `props` [IDs], `needs` [IDs], `mechanic`, `difficulty` 1–3, `answer` |
| prop | PP | `props/` | `form`: physical / printed / digital, `source`: make / buy / print / 3d-print, `envelope`: `start` or a puzzle ID |
| question | Q | `questions/` | `about` [IDs], `answer`. Shown on the records in `about`. |
| asset | AS | `assets/` | `kind`: image / audio / text / print, `for` (one prop ID), `file`. Shown on its prop (or its first `links` record). The body holds the generation prompt. |

"Structure beat" is the generic name. Each adventure sets what it's called in
`backpack.json` → `beatLabel` (Space Exploration uses "Era").

## Envelopes and the cipher

```json
"cipher": { "preset": "planets", "length": [4, 5], "decoys": 2 }
```

- `preset`: a cipher from the kit's `ciphers.json` (`planets`, `runes`, `shapes`), or leave it
  out and give your own `"name"`, `"symbols": {"0": "☉", ...}` and optional `"labels"`.
  Keys are answer characters (digits and/or letters); symbols must all be different.
- `length`: allowed answer lengths. `decoys`: extra envelopes that are never opened.
- A puzzle's `answer` (case, spaces and dashes ignored) is encoded one character at a time.
  The envelope it opens is marked with that code. Props with `envelope: <that puzzle>` go inside.
- `kit.py check` reports answers the cipher can't encode, answers of the wrong length and
  two puzzles with the same envelope code.

## Status

- Most types: `idea` → `candidate` → `decided` → `built`, or `parked`
- Questions: `open` → `answered`, or `parked`
- Replaced: keep the old record and set `superseded_by: <new ID>`. It's hidden unless the
  "parked" filter is on.

### Testing and release are separate

Puzzle fields: `test_status: untested | passed | changes-needed`, `test_method:
physical | digital`, `publish_hints: yes | no`, `hint_title`.
Missing testing means unrecorded; missing publish_hints means private.

The puzzle body has `## How it works`, `## Clue wording`, `## Hints`, `## Solution` and
`## Playtest evidence`. Evidence records date, version/files, method, observed actions/stalls,
hints used, interpretation, change and retest. After relevant edits set test_status back to untested.

Props add `after_game` (`return`, `keep`, `none`), `reset_name`, `## Player sees` and `## Reset`.

### Checks

- `check`: record validity, references, allowed values, the cipher and envelope codes. Fields from
  the lock-based kit (`lock`, `container`, `container_in`, `reset_display`, `found_in`) are reported
  so old records get cleaned up.
- `ready`: playtest preparation for decided/built puzzles and props: unreachable puzzles, props
  never found, missing answers, hints, solutions and player-visible material.
- `ready --include-candidates`: includes draft candidates without changing status.
- `ready --release`: also requires a recorded passed physical playtest and evidence.

## One fact, one place

Each relationship is stored on **one** side only. The viewer shows the other side.

| Stored on | Field | Shown on the other record as |
|---|---|---|
| puzzle | `beat` | the beat's puzzle list |
| puzzle | `props` | "used by" on the prop |
| puzzle | `needs` | (play order) |
| prop | `envelope` | "inside" on the puzzle |
| asset | `for` | files on the prop |
| question | `about` | questions on the record |
| any | `links` | (search) |

## Pages `build` writes

| Page | Who | What |
|---|---|---|
| `site/index.html` | designers | the board |
| `site/play.html` | designers | play-test: start with the `envelope: start` props, type each answer, get the envelope's props. Hints come from `## Hints`. |
| `site/print.html` | designers | cipher card, envelope labels (shuffled, decoys mixed in), packing list |
| `site/hints/index.html` | public | hint page (below) |
| `site/reset/index.html` | public | reset checklist, with `"publish_reset": true` |

### Hint page
One self-contained file. It includes only `decided` and `built` puzzles marked
`publish_hints: yes`, in play order, each with its `hint_title`, the `## Hints` list one hint
at a time, then the answer, the envelope it opens and the `## Solution` section.
Records missing any of these are left off and reported by `check`. Nothing else is included.

### Reset checklist
One step per envelope in play order: its code, the props that go back in (`after_game: return`),
the ones the team keeps, and each prop's `## Reset` note (a note shared by 3+ props is shown once
at the top). Then what goes loose in the box, and a count of envelopes including decoys.

### Run logging and team comparison (optional)
Add to `backpack.json`:

```json
"stats": { "api": "https://escapepack.ca/api", "backpack": "space", "version": "2026-10-12", "linear": true }
```

The hint page then (`viewer/sync.js`) logs each run (team name, timer, when each envelope was marked
opened, hints read), shows a game code so teammates can join on another phone, and compares the
finished run with earlier teams of the same `version`. The stats API counts steps as "locks";
each puzzle is one step. Change `version` whenever the puzzle order or a puzzle changes enough that
older times no longer compare.

## Syntax rules (small YAML subset)
- `key: value` on one line. Lists are `[A, B]` or `- item` lines underneath.
- Lines starting with `#` are comments.
- Long text goes in the body, not in a field.
