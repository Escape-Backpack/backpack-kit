# {{name}}: working rules for AI agents

This is an adventure backpack design project. The design lives in `records/`,
one Markdown file per record, rendered by the shared viewer from
[backpack-kit](https://github.com/Escape-Backpack/backpack-kit).

## How sessions work
- Sessions are brainstorming. Propose options and ask questions **before**
  writing a design decision into a record.
- One piece of the game per session (one puzzle, one beat, one prop...).
- Unfinished work and open questions are normal. Record them as `question` records.
- **Never invent** rules, answers or status. If something isn't decided, it stays
  `idea` or `candidate`, or becomes an open question.
- Prefer subtle clues, but every necessary connection must be inferable from the game.
  Theme-specific preferences belong in premise records, not universal rules.
- Built does not mean tested. Record playtest evidence separately; never invent a
  pass. After changes to a tested mechanism or clue, mark test_status untested.
- Keep publish_hints: no until the designer explicitly chooses to release the
  puzzle's hints. Candidate answers must not enter the public hint build.
- Don't commit or push unless the designer says so.
- At the end of a session, update `HANDOFF.md`.

## Records
- Format reference: `../backpack-kit/docs/RECORDS.md`.
- Create records with `python ../backpack-kit/kit.py new <type> "Title"`. Never pick IDs by hand.
- One fact in one place. Refer to other records by ID and never copy their content.
- Relationships are stored on one side only (a puzzle stores its `beat` and `props`;
  an asset stores `for`). The viewer shows the reverse side.
- Replacing an idea: create the new record and set `superseded_by: <new ID>` on the old one.
  Don't delete it.
- Run `python ../backpack-kit/kit.py check` after editing. It must report no problems.
- Before a playtest run `python ../backpack-kit/kit.py ready --include-candidates`.
  It reports gaps without forcing unfinished ideas into decisions. Before release,
  run `ready --release` for the decided/built game and check the actual lock wheels.

## Kit location
The kit is expected next to this repo, at `../backpack-kit`. If it's missing
(for example in a Claude cloud session), fetch it first:
`git clone https://github.com/Escape-Backpack/backpack-kit ../backpack-kit`

## Preview
- Online: escapepack.ca rebuilds a few minutes after every push to main
  (`.github/workflows/rebuild-site.yml`). The design board is at `https://escapepack.ca/design/<slug>/`
  (no login, `noindex`) and the public hint page at `https://escapepack.ca/help/<slug>/`.
  The slug is this repo's line in `escapepack-site/backpacks.txt`.
- Local: `python ../backpack-kit/kit.py serve`, then open http://localhost:8000/site/
