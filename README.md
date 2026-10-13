# backpack-kit

Shared tooling for Escape Backpack adventures: a design board, a build script,
record templates and a design guide. See GUIDE.md for the working method and
docs/RECORDS.md for the record format.

An adventure is a box of **marked envelopes**. Each puzzle's answer, looked up in the
adventure's cipher, gives the symbols on the envelope to open next. Each adventure stores its
design as **records**, one Markdown file per fact. `kit.py` bundles them into a board with three
tabs (Story, Puzzles, Props), a play-test, a print page for the envelope labels and cipher card,
and the public hint and reset pages.

**Lock-based backpacks** (Norse, Hiking, and anything built for padlocks and pouches) use the
`v1` tag of this kit: `git clone --branch v1 https://github.com/Escape-Backpack/backpack-kit`.

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
| Prepare a prototype test | `python ../backpack-kit/kit.py ready --include-candidates` |
| Audit release evidence | `python ../backpack-kit/kit.py ready --release` |
| Play-test the decided game | the **▶ Play-test** button, or `site/play.html` |
| Print labels and the cipher card | the **Print envelopes** button, or `site/print.html` |

`site/` is generated and git-ignored. You can also open `site/index.html`
directly, without the server.

## Working together: the Studio
escapepack.ca/studio/ is a live, shared board for an adventure's story, puzzles and props
(code and setup: `escapepack-site/workers/studio/`). It saves to the adventure's GitHub repo every
10 minutes. Claude sessions sync with `kit.py studio pull` and `kit.py studio push`.

## Online pages and remote editing
Everything is served from escapepack.ca by one Cloudflare Pages project, `escapepack-site`.
Its `build.sh` downloads this kit (which must stay public) and builds every adventure
listed in `escapepack-site/backpacks.txt`. A third column there picks the kit version
(`v1` for lock-based backpacks; blank = the latest, envelope-based kit):

| Address | What | Who sees it |
|---|---|---|
| `escapepack.ca/design/<slug>/` | the design board, play-test and print page | anyone with the link (`noindex`, no login) |
| `escapepack.ca/help/<slug>/` | the public hint page: this is the printed QR link | everyone |

Each backpack's `.github/workflows/rebuild-site.yml` calls the site's deploy hook on every
push to main (org secret `SITE_DEPLOY_HOOK`), so the pages update a few minutes after a push.

To edit from anywhere, open a Claude session on the backpack repo at
claude.ai/code. `AGENTS.md` tells it to clone the kit if it's missing.

Record types for `new`: `premise`, `beat`, `puzzle`, `prop`, `question`, `asset`.

## Start a new adventure
```
python backpack-kit/kit.py init Celtic --name "Celtic"
```
This creates `backpack.json`, `AGENTS.md`, `CLAUDE.md`, `HANDOFF.md`,
`.gitignore`, `.gitattributes`, the site rebuild workflow and the empty `records/` folders.
Existing files are kept. Then move the seed notes from `seeds/` into records.
To publish it, add `<slug>  Escape-Backpack/<repo>` to `escapepack-site/backpacks.txt`.

## What's in here
| Path | What it is |
|---|---|
| `kit.py` | Build, serve, check, ready, new, init |
| `checks.py` | Readiness and dependency checks used by CLI and viewer |
| `viewer/` | The shared pages, copied into each project's `site/` on build: `index.html` (design board), `play.html` (play-test), `hints/` (public hint page), plus `style.css` and `common.js` |
| `templates/records/` | One template per record type |
| `templates/project/` | Files `init` copies into a new backpack |
| `docs/RECORDS.md` | Record format reference |
| `GUIDE.md` | Backpack design guide (lessons carried between backpacks) |
| `seeds/` | Notes for backpacks that don't have a repo yet |

## Added in the process review
- Flow and Setup & reset are generated from records. Overview shows readiness gaps.
- Public hints now require `publish_hints: yes` on decided/built puzzles. Existing
  projects need explicit opt-in; candidate content is no longer embedded publicly.
  See `docs/RECORDS.md` for migration and the independent test evidence fields.

Existing record files remain valid. Add the new notes when you next work on each
puzzle/prop; don't fabricate historical evidence. Existing AGENTS.md files are
kept by init, so align their clue/testing guidance with templates/project/AGENTS.md.

## Planned
- Play-test: a feedback box for testers.
- Rebuild backpacks automatically when the kit changes.
