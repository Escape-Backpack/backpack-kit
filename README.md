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
| Play-test the decided game | the **▶ Play-test** button, or `site/play.html` |

`site/` is generated and git-ignored. You can also open `site/index.html`
directly, without the server.

## Online pages and remote editing
Hosting is moving to Cloudflare Pages on escapepack.ca. The files stay on GitHub.

| Address | Built from | Who sees it |
|---|---|---|
| `escapepack.ca` | `escapepack-site` (public site, no build step) | everyone |
| `<backpack>-design.escapepack.ca` | the backpack repo, via `cloudflare-build.sh` | only people allowed by Cloudflare Access |
| `<backpack>-design.escapepack.ca/hints/` | the same build | everyone (Access skips this path) |
| `escapepack.ca/<backpack>/hints` | a redirect in `escapepack-site/_redirects` | everyone: this is the printed QR link |

Cloudflare Pages settings for a backpack: build command `bash cloudflare-build.sh`,
output directory `site`. The script downloads this kit (which must stay public).

Until the migration is done, `.github/workflows/pages.yml` still publishes each
backpack to `https://escape-backpack.github.io/<repo>/`.

To edit from anywhere, open a Claude session on the backpack repo at
claude.ai/code. `AGENTS.md` tells it to clone the kit if it's missing.

Record types for `new`: `premise`, `beat`, `puzzle`, `prop`, `question`, `asset`.

## Start a new backpack
```
python backpack-kit/kit.py init Celtic --name "Celtic"
```
This creates `backpack.json`, `AGENTS.md`, `CLAUDE.md`, `HANDOFF.md`,
`.gitignore`, `.gitattributes`, `cloudflare-build.sh`, the Pages workflow and the empty `records/` folders.
Existing files are kept. Then move the seed notes from `seeds/` into records.
After the first push, turn on Pages:
`gh api -X POST repos/Escape-Backpack/<repo>/pages -f build_type=workflow`

## What's in here
| Path | What it is |
|---|---|
| `kit.py` | Build, serve, check, new, init |
| `viewer/` | The shared pages, copied into each project's `site/` on build: `index.html` (design board), `play.html` (play-test), `hints/` (public hint page), plus `style.css` and `common.js` |
| `templates/records/` | One template per record type |
| `templates/project/` | Files `init` copies into a new backpack |
| `docs/RECORDS.md` | Record format reference |
| `GUIDE.md` | Backpack design guide (lessons carried between backpacks) |
| `seeds/` | Notes for backpacks that don't have a repo yet |

## Planned
- v2: a puzzle flow chart generated from the puzzles' `needs:` fields.
- Play-test: a feedback box for testers.
- Rebuild backpacks automatically when the kit changes.
