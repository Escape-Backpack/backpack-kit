"""Pure record checks shared by the CLI and generated design board."""
import re


def items(value):
    return value if isinstance(value, list) else [value] if value else []


def section(record, title):
    match = re.search(r"^##\s+" + re.escape(title) + r"\s*\n(.*?)(?=^##\s|\Z)",
                      record.get("body", ""), re.M | re.S | re.I)
    text = match.group(1).strip() if match else ""
    text = re.sub(r"<!--.*?-->", "", text, flags=re.S).strip()
    if re.fullmatch(r"\[[^\]]*\]", text):
        return ""
    return text if text.lower() not in ("", "tbd", "todo", "open", "[open]", "1.") else ""


def selected(records, candidates=False):
    statuses = {"decided", "built"} | ({"candidate"} if candidates else set())
    return [r for r in records if not r.get("superseded_by") and r.get("status") in statuses]


def reachable(records):
    """Return solvable puzzle IDs and acquired prop IDs; missing inputs block.
    A prop is in hand once its envelope is open (envelope: start, or the puzzle whose answer opens it)."""
    puzzles = [r for r in records if r["type"] == "puzzle"]
    props = [r for r in records if r["type"] == "prop"]
    done, hand = set(), {r["id"] for r in props if r.get("envelope") == "start"}
    while True:
        ready = {r["id"] for r in puzzles if r["id"] not in done
                 and set(items(r.get("needs"))) <= done and set(items(r.get("props"))) <= hand}
        if not ready:
            return done, hand
        done |= ready
        hand |= {r["id"] for r in props if r.get("envelope") in done}


def readiness(records, candidates=False, release=False):
    """Gaps before a playtest (or a release) of the decided/built game. Answer format and
    envelope-code clashes are checked when records load (kit.py), so they show up in both."""
    live = selected(records, candidates)
    puzzles = [r for r in live if r["type"] == "puzzle"]
    props = [r for r in live if r["type"] == "prop"]
    done, hand = reachable(live)
    issues = []
    def add(r, message):
        issues.append({"id": r.get("id", ""), "file": r.get("path", ""), "msg": message})
    if not puzzles:
        add({}, "No puzzles selected. Decide a puzzle or use --include-candidates for a draft audit.")
    for r in puzzles:
        if r["id"] not in done:
            add(r, "Unreachable: check needs, which envelope its props are in, and circular dependencies.")
        if not r.get("answer"):
            add(r, "No answer recorded, so no envelope code.")
        for title in ("Hints", "Solution"):
            if not section(r, title):
                add(r, f"Missing {title} notes.")
        hints = section(r, "Hints")
        if hints and not re.search(r"^\s*(?:[-*]|\d+\.)\s+\S", hints, re.M):
            add(r, "Hints must be a nonempty numbered or bulleted list for the player pages.")
        if release:
            if r.get("test_status") != "passed" or r.get("test_method") != "physical":
                add(r, "Release needs a passed physical playtest; built is not evidence of testing.")
            if not section(r, "Playtest evidence"):
                add(r, "Record dated playtest observations, version tested, hints used and retest result.")
    for r in props:
        if r["id"] not in hand:
            add(r, "Prop is never found: set envelope to start or to the puzzle whose answer opens it.")
        images = [a for a in live if a["type"] == "asset" and a.get("for") == r["id"]
                  and a.get("kind") == "image" and a.get("fileExists")]
        if not section(r, "Player sees") and not images:
            add(r, "No Player sees text or available image for the digital walkthrough.")
    for r in live:
        if r["type"] == "asset" and r.get("file") and not r.get("fileExists"):
            add(r, "Referenced asset file is missing.")
    return issues
