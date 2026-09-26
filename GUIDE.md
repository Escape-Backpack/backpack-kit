# Backpack design guide

Lessons carried over between backpacks. Only add a lesson once it has been
confirmed in a real design session. This guide is not a place for guesses.

## The format
A family member sends the player a backpack about their passion. The player
solves puzzles through the backpack's contents.

## Final prize: a medallion (all backpacks)
Every backpack ends with a medallion as the final prize.

It is 3D printed in two colours: **dark blue body, yellow details.**

The Norse medallion is the reference:
- Files: `EscapeBackpack/NorseBackpack/Props/Medallion/` (STL, build script, README)
- 50 mm diameter, 4.4 mm thick, one solid piece with no assembly
- Front: a crest raised 0.6 mm above a 3.8 mm body. The yellow comes from a colour change at layer 20 (Z = 4.00 mm at 0.20 mm layers).
- Back: "ADVENTURE COMPLETE · ESCAPE BACKPACK" around a compass, recessed 0.4 mm, in the body colour
- Status as of 2026-09-26: not physically test-printed yet (per its README)

Open: which parts stay the same across backpacks (size, the back, the style), and which change per theme.

## Default locks (all backpacks)
- 3-digit lock
- 4-digit lock
- 4-letter lock
- 3-digit lock where each wheel is a different colour

In records these are `lock: 3-digit | 4-digit | 4-letter | 3-digit-colour`.
A backpack can use a different set by adding `"locks": [...]` to its `backpack.json`.

## What we can build with (all backpacks)
- **Home printing:** cardstock, colour.
- **3D printing** at a friend's: Prusa i3 MK3S+, several filament colours (black, white, dark blue, yellow, green...).
- **Small props:** rulers, UV light and UV pen, and so on.
- **Bought items:** the backpack itself, relevant small items.

## Puzzle and clue principles
- Clues are subtle, with no signposting, especially in the final puzzle.

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
_To do: extract these from `EscapeBackpack/NorseBackpack/Norse_Brainstorm.html`
in a dedicated session._
