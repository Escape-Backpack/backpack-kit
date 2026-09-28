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
    """Return reachable puzzle IDs and acquired prop IDs; missing inputs block."""
    puzzles = [r for r in records if r["type"] == "puzzle"]
    props = [r for r in records if r["type"] == "prop"]
    done, hand = set(), {r["id"] for r in props if r.get("found_in") == "start"}
    while True:
        ready = {r["id"] for r in puzzles if r["id"] not in done
                 and set(items(r.get("needs"))) <= done and set(items(r.get("props"))) <= hand}
        if not ready:
            return done, hand
        done |= ready
        hand |= {r["id"] for r in props if r.get("found_in") in done}


def readiness(records, candidates=False, release=False):
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
            add(r, "Unreachable: check needs, prop availability and circular dependencies.")
        for title in ("Player notices", "Player does", "Player obtains", "Story reason", "Hints", "Solution"):
            if not section(r, title):
                add(r, f"Missing {title} notes.")
        hints = section(r, "Hints")
        if hints and not re.search(r"^\s*(?:[-*]|\d+\.)\s+\S", hints, re.M):
            add(r, "Hints must be a nonempty numbered or bulleted list for the player pages.")
        answer = str(r.get("answer") or "")
        lock = r.get("lock")
        if lock and not answer:
            add(r, "No lock answer recorded.")
        patterns = {"3-digit": r"\d{3}", "4-digit": r"\d{4}",
                    "4-letter": r"[A-Za-z]{4}", "3-digit-colour": r"\d{3}"}
        if answer and lock in patterns and not re.fullmatch(patterns[lock], answer):
            add(r, f"Answer does not fit {lock}; preserve leading zeroes and check the actual wheels.")
        if lock == "3-digit-colour" and not section(r, "Reading order"):
            add(r, "Record Reading order for the coloured wheels.")
        if release:
            if r.get("test_status") != "passed" or r.get("test_method") != "physical":
                add(r, "Release needs a passed physical playtest; built is not evidence of testing.")
            if not section(r, "Playtest evidence"):
                add(r, "Record dated playtest observations, version tested, hints used and retest result.")
    for r in props:
        if r["id"] not in hand:
            add(r, "Prop is never acquired in the selected game.")
        if not r.get("container"):
            add(r, "Record the physical container/location (including start props).")
        for title in ("Starting state", "Reset", "Replacement"):
            if not section(r, title):
                add(r, f"Missing {title} notes; write 'None needed' when appropriate.")
        images = [a for a in live if a["type"] == "asset" and a.get("for") == r["id"]
                  and a.get("kind") == "image" and a.get("fileExists")]
        if not section(r, "Player sees") and not images:
            add(r, "No Player sees text or available image for the digital walkthrough.")
    for r in live:
        if r["type"] == "asset" and r.get("file") and not r.get("fileExists"):
            add(r, "Referenced asset file is missing.")
    return issues


def flow_model(records):
    """Include unfinished ideas, but label cycles and unresolved inputs as blocked."""
    live = [r for r in records if r["type"] in ("puzzle", "prop")
            and r.get("status") != "parked" and not r.get("superseded_by")]
    nodes = [{"id": "start", "title": "Available at the start", "type": "start", "status": ""}]
    nodes += [{k: r.get(k, "") for k in ("id", "title", "type", "status")} for r in live]
    edges = []
    for r in live:
        if r["type"] == "puzzle":
            edges += [{"from": x, "to": r["id"], "kind": "needs"} for x in items(r.get("needs"))]
            edges += [{"from": x, "to": r["id"], "kind": "uses"} for x in items(r.get("props"))]
        elif r.get("found_in"):
            edges.append({"from": r["found_in"], "to": r["id"], "kind": "reveals"})
    levels = {"start": 0}
    while True:
        new = {}
        for n in nodes:
            if n["id"] in levels:
                continue
            parents = [e["from"] for e in edges if e["to"] == n["id"]]
            if not parents and n["type"] == "prop":
                continue
            if all(p in levels for p in parents):
                new[n["id"]] = max([levels[p] for p in parents] or [0]) + 1
        if not new:
            break
        levels.update(new)
    last = max(levels.values(), default=0) + 1
    for n in nodes:
        n["blocked"] = n["id"] not in levels
        n["level"] = levels.get(n["id"], last)
    return {"nodes": nodes, "edges": edges}
