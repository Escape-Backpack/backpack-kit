# Backpack design guide

Shared working method and lessons carried between backpacks. Mark new principles
as design guidance; call something a confirmed lesson only when the source session
supports it. Defaults are choices, not proof that a mechanism will work.

## The format
Someone the player knows sends them a box about their passion: a family member,
a friend, or another acquaintance (a co-worker, a pen pal...). The player solves
puzzles through the box's contents, opening marked envelopes as they go (see below).

## Final prize: a medallion (all backpacks)
Every backpack ends with a medallion as the final prize.

It is 3D printed in two colours: **dark blue body, yellow details.**

The Norse medallion is the reference:
- Files: `EscapeBackpack/NorseBackpack/Props/Medallion/` (STL, build script, README)
- 50 mm diameter, 4.4 mm thick, one solid piece with no assembly
- Front: a crest raised 0.6 mm above a 3.8 mm body. The yellow comes from a colour change at layer 20 (Z = 4.00 mm at 0.20 mm layers).
- Back: "ADVENTURE COMPLETE · ESCAPE BACKPACK" around a compass, recessed 0.4 mm, in the body colour
- Current Norse revision: v3, updated 2026-10-05; no physical print of v3 recorded.

On 2026-10-05 the designer approved the Space digital medallion and asked to
reuse its back on Norse and Hiking. These three models share the 50 mm body,
4.4 mm total thickness and 0.4 mm engraved back; the front motif changes by theme.
The approved back uses 4.6 mm Arial Bold capitals for ADVENTURE / COMPLETE and
4.0 mm Arial Regular capitals for ESCAPE BACKPACK. Minimum adjacent brand-letter
clearance is 0.831 mm in the curved layout. Exact profiles and print notes live
with each model; the reusable builder is `EscapeBackpack/Tools/medallion_cad.py`.

Later on 2026-10-05 the designer requested the same family for Space Station
Aurora, Hockey Road Trip and Canada Exploration, selecting station symbol,
puck/road and maple leaf/train fronts respectively. Their v1 digital models
reuse the same back and dimensions; print files and validation live in each
project's `assets/medallion/` directory. These versions are physically untested.

Correction later that day: Aurora v2 replaces the station silhouette with the
designer-supplied maple-leaf-and-orbit STATION / AURORA patch, also selected for
public branding. Canada v2 replaces the first stylised leaf with the existing
maple-leaf SVG outline; train and tracks are retained. v1 files remain as history.

The designer reported poor S, B and K on an earlier print; its exact version
and printer settings are unknown. Larger, more open lettering is approved
geometry guidance, not a confirmed printing fix. Each new package includes a
1.2 mm thick full-size back trial. Physical results remain to be recorded.

## Envelopes and the cipher (all adventures, from October 2026)
Adventures moved from locks, pouches and pockets in a backpack to **marked envelopes in a
board-game box**: cheaper, lighter and simpler to reset. Lock-based backpacks (Norse, Hiking...)
keep the kit's `v1` tag.

- Each puzzle's **answer** is 4 or 5 characters (digits, or letters if the cipher has them).
- Each adventure has its own **cipher**: a lookup card that turns each character into a symbol.
  It is a tool, not a puzzle. Give each adventure its own look (planet symbols for Space,
  runes for Norse...). Presets live in `ciphers.json`; an adventure can define its own symbols.
- The envelope the answer opens is marked with those symbols. Symbols instead of numbers mean
  players can't tell which envelope comes next without the answer.
- **Decoy envelopes** (`"decoys": 2` in the cipher settings) make guessing pointless.
- Props say which envelope they're in (`envelope: PZ-004`), or `start` for loose in the box.
  There are no containers, nesting or packing order to work out.
- The board's **Print envelopes** page makes the cipher card, the labels (shuffled, decoys mixed
  in) and a packing list.

In `backpack.json`:

```json
"cipher": { "preset": "planets", "length": [4, 5], "decoys": 2 }
```

## What we can build with (all backpacks)
- **Home printing:** cardstock, colour.
- **3D printing** at a friend's: Prusa i3 MK3S+, several filament colours (black, white, dark blue, yellow, green...).
- **Small props:** rulers, UV light and UV pen, and so on.
- **Bought items:** a board-game box, envelopes, relevant small items.

## Puzzle and clue principles
- Prefer subtle clues, but make every necessary connection inferable from the game.
  A player should be able to explain why they selected, ordered and read the inputs.
- Supply required knowledge and keys in the box. Separate finding the method
  from repetitive execution; a long transcription is not automatically a better puzzle.
- Vary actions and give each puzzle a story reason. Reuse props when the connection
  is understandable, not simply to increase the number of steps.
- Theme-specific preferences belong in premise records. They are not universal rules.

## Working method
- Sessions are brainstorming. Propose options and ask questions before writing a decision down.
- One piece of the game per session.
- Unfinished work and open questions are normal. Record them as `question` records.
- Never invent rules, answers or status.

## Lessons from the Norse backpack (the tooling)
The Norse brainstorm page was a single 870 KB HTML file that mixed content, layout and scripts. It led to:

| Problem | What the kit does instead |
|---|---|
| Stale content: the same fact copied across tabs | One record per fact. Tabs are generated from records. |
| Decisions not tracked reliably (hand-written status prose and pills) | A `status` field with a fixed set of values, and a Decisions tab built from it |
| Poor organization: tabs added ad hoc | A fixed set of tabs, the same for every backpack |

What worked and is kept: a visual page that shows ideas, decisions, and work done vs. to do.

## Lessons from the Norse backpack (the design)

Confirmed session evidence in `../EscapeBackpack/HANDOFF.md`:
- 2026-09-27, Leif playtest: feedback changed clue wording and the release order;
  it also prompted larger joined sky digits. Record the exact version played and
  retest the modified print. The enlargement itself is not a confirmed physical pass.
- 2026-09-27, ticket cleanup: decorative serial numbers were removed because they
  could be mistaken for puzzle inputs. Audit incidental numbers and marks.
- 2026-09-26, Fun Fact edits: Aud's message was tied to the comb grille geometry,
  so only its independent fact text could be rewritten freely. Record dependencies
  and test the whole linked mechanism after changing a clue, layout or scale.
- 2026-09-27, duplex tests: the user confirmed the mirrored back placement and
  bleed worked after printing. Screen alignment was not enough to settle the settings.

Hiking's existing illustrated reset page (`../escapepack-site/hiking-reset.html`)
is a reference for documenting the starting state and reset sequence. This is a
documented practice, not evidence of a measured reset time or error rate.

## A light workflow

1. **Explore:** collect a technique and story connection. Keep status idea/candidate;
   unknowns remain open. Do not require a complete form to capture an idea.
2. **Shape:** describe what players notice → do → obtain, and why the object belongs.
   Link required props and prerequisite puzzles once known. Write reading order.
3. **Prepare:** add solution and hint ladder; record prop location, starting state,
   reset and consumables. Run `kit.py ready --include-candidates` on the prototype.
4. **Observe:** test the actual materials with a fresh reader where possible.
   Record version, observed behaviour, hint use, interpretation and change separately.
5. **Retest:** mark relevant changed puzzles untested; keep earlier evidence with its
   date/version. A built artifact is not a passed playtest.
6. **Release deliberately:** run `kit.py ready --release` on the decided/built game.
   Set `publish_hints: yes` only for hints chosen for public release. The automated
   check cannot establish answer uniqueness, fairness or physical reliability.

The viewer derives Flow and Setup & reset from the same records. Do not maintain
duplicate release lists in the handoff. Handoff entries link IDs and the next action.
