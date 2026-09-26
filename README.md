# backpack-kit

Shared tooling for Escape-Backpack design projects: a viewer, a build script,
record templates and a design guide.

Each backpack stores its design as **records**, one Markdown file per fact.
`kit.py` bundles them into a local viewer with fixed tabs: Overview, Premise,
Structure, Puzzles, Props, Questions, Decisions, Parked and Assets.

## Setup
Clone the kit next to the backpack repos:

```
EscapeBackpack/
  backpack-kit/        <- this repo
  Space-Exploration/   <- a backpack project
```

Requires Python 3.9+ and git. There are no other dependencies.

## Daily use (run inside a backpack folder)

| Do this | Command |
|---|---|
| Preview | `python ../backpack-kit/kit.py serve` → http://localhost:8000/site/ |
| Rebuild after edits | `python ../backpack-kit/kit.py build`, then refresh the page |
| Add a record | `python ../backpack-kit/kit.py new puzzle "Star chart"` |
| Check for broken IDs etc. | `python ../backpack-kit/kit.py check` |

`site/` is generated and git-ignored. You can also open `site/index.html`
directly, without the server.

## Online page and remote editing
Each backpack repo has `.github/workflows/pages.yml`. On every push to main (and
daily) it builds the viewer and publishes it to
`https://escape-backpack.github.io/<repo>/`. The repos are public, so the page
and the records (answers included) are visible to anyone with the link.

To edit from anywhere, open a Claude session on the backpack repo at
claude.ai/code. `AGENTS.md` tells it to clone the kit if it's missing.
A change to the kit itself shows up online at the next push to a backpack, or
after the daily rebuild.

Record types for `new`: `premise`, `beat`, `puzzle`, `prop`, `question`, `asset`.

## Start a new backpack
```
python backpack-kit/kit.py init Celtic --name "Celtic"
```
This creates `backpack.json`, `AGENTS.md`, `CLAUDE.md`, `HANDOFF.md`,
`.gitignore`, `.gitattributes`, the Pages workflow and the empty `records/` folders.
Existing files are kept. Then move the seed notes from `seeds/` into records.
After the first push, turn on Pages:
`gh api -X POST repos/Escape-Backpack/<repo>/pages -f build_type=workflow`

## What's in here
| Path | What it is |
|---|---|
| `kit.py` | Build, serve, check, new, init |
| `viewer/index.html` | The shared viewer (copied into each project's `site/` on build) |
| `templates/records/` | One template per record type |
| `templates/project/` | Files `init` copies into a new backpack |
| `docs/RECORDS.md` | Record format reference |
| `GUIDE.md` | Backpack design guide (lessons carried between backpacks) |
| `seeds/` | Notes for backpacks that don't have a repo yet |

## Planned
- v2: a puzzle flow chart generated from the puzzles' `needs:` fields.
