#!/usr/bin/env python3
"""backpack-kit: turn an adventure's Markdown records into the design board and player pages.

An adventure is a box of marked envelopes. Each puzzle's answer, looked up in the adventure's
cipher, gives the symbols printed on the envelope to open next.

Run from inside an adventure project folder (the one with backpack.json):

  python ../backpack-kit/kit.py build                 write site/ from records/
  python ../backpack-kit/kit.py serve                 build, then preview at http://localhost:8000/site/
  python ../backpack-kit/kit.py check                 validate records, print problems
  python ../backpack-kit/kit.py new puzzle "Star chart"
  python ../backpack-kit/kit.py init ../Celtic --name "Celtic"

Types for `new`: premise, beat, puzzle, prop, question, asset.
No dependencies beyond Python 3.9+ and git. Lock-based backpacks use the kit's v1 tag.
"""
import argparse
import datetime
import functools
import http.server
import json
import os
import random
import time
import re
import shutil
import subprocess
import sys
from checks import readiness

KIT = os.path.dirname(os.path.abspath(__file__))

TYPES = {
    "premise":  {"prefix": "PR", "folder": "premise"},
    "beat":     {"prefix": "ST", "folder": "structure"},
    "puzzle":   {"prefix": "PZ", "folder": "puzzles"},
    "prop":     {"prefix": "PP", "folder": "props"},
    "question": {"prefix": "Q",  "folder": "questions"},
    "asset":    {"prefix": "AS", "folder": "assets"},
}
PREFIX_TYPE = {v["prefix"]: k for k, v in TYPES.items()}
STATUSES = ["idea", "candidate", "decided", "built", "parked"]
QUESTION_STATUSES = ["open", "answered", "parked"]
STALE_STATUSES = {"idea", "candidate"}
# Fields whose values are record IDs. Backlinks are derived from these.
REF_FIELDS = ["links", "superseded_by", "beat", "props", "needs", "about", "for", "envelope"]
INT_FIELDS = ["order", "difficulty"]
# What happens to a prop after the game, on the public reset page (blank = return).
AFTER_GAME = ["return", "keep", "none"]
ID_RE = re.compile(r"^([A-Z]{1,2})-(\d{3,})$")
DEFAULT_CONFIG = {"name": "Untitled adventure", "beatLabel": "Structure beat", "staleDays": 30}
DEFAULT_CIPHER = {"preset": "shapes", "length": [4, 5], "decoys": 0}
# Fields from the lock-based kit (v1). Reported so old records get cleaned up.
LEGACY_FIELDS = {
    "lock": "remove it: answers now give an envelope code",
    "container": "remove it: items go in envelopes",
    "container_in": "remove it: envelopes don't nest",
    "reset_display": "remove it: there are no locks to reset",
    "found_in": "rename it to envelope (start, or the puzzle whose answer opens it)",
}


# ---------- parsing ----------

def parse_scalar(s):
    s = s.strip()
    if len(s) >= 2 and s[0] == s[-1] and s[0] in "\"'":
        return s[1:-1]
    return s


def parse_value(s):
    s = s.strip()
    if s == "":
        return None
    if s.startswith("[") and s.endswith("]"):
        inner = s[1:-1].strip()
        return [parse_scalar(x) for x in inner.split(",") if x.strip()] if inner else []
    return parse_scalar(s)


def parse_record(text):
    """Parse a small YAML subset: `key: value`, `key: [a, b]`, `- item` lists, full-line # comments."""
    lines = text.replace("\r\n", "\n").split("\n")
    if not lines or lines[0].strip() != "---":
        return None, text, ["no frontmatter (file must start with ---)"]
    end = next((i for i in range(1, len(lines)) if lines[i].strip() == "---"), None)
    if end is None:
        return None, text, ["frontmatter is never closed with ---"]
    fields, errors, key = {}, [], None
    for ln in lines[1:end]:
        s = ln.strip()
        if not s or s.startswith("#"):
            continue
        if (s.startswith("- ") or s == "-") and key is not None:
            if not isinstance(fields.get(key), list):
                fields[key] = []
            item = parse_scalar(s[1:])
            if item:
                fields[key].append(item)
            continue
        m = re.match(r"^([A-Za-z_][\w-]*)\s*:(.*)$", ln)
        if not m:
            errors.append(f"can't read frontmatter line: {ln!r}")
            continue
        key = m.group(1)
        fields[key] = parse_value(m.group(2))
    for k in INT_FIELDS:
        v = fields.get(k)
        if isinstance(v, str) and re.fullmatch(r"-?\d+", v):
            fields[k] = int(v)
    body = "\n".join(lines[end + 1:]).strip("\n")
    return fields, body, errors


def as_list(v):
    if v is None or v == "":
        return []
    return v if isinstance(v, list) else [v]


# ---------- git ----------

def git(project, *args):
    try:
        r = subprocess.run(["git", "-C", project, "-c", "core.quotePath=false", *args],
                           capture_output=True, text=True, encoding="utf-8")
    except OSError:
        return None
    return r.stdout if r.returncode == 0 else None


def git_info(project):
    """Return (history per path, commit list, set of uncommitted paths). Paths use forward slashes."""
    per_file, commits = {}, []
    out = git(project, "log", "--relative", "--format=\x1e%cs\x1f%s", "--name-only", "--", "records")
    if out:
        for chunk in out.split("\x1e")[1:]:
            head, _, files = chunk.partition("\n")
            date, _, subject = head.partition("\x1f")
            paths = [f.strip() for f in files.splitlines() if f.strip()]
            commits.append({"date": date, "subject": subject, "paths": paths})
            for p in paths:
                per_file.setdefault(p, []).append({"date": date, "subject": subject})
    dirty = set()
    for args in (("diff", "--relative", "--name-only", "HEAD", "--", "records"),
                 ("diff", "--relative", "--name-only", "--cached", "--", "records"),
                 ("ls-files", "--others", "--exclude-standard", "--", "records")):
        out = git(project, *args)
        if out:
            dirty.update(p.strip() for p in out.splitlines() if p.strip())
    return per_file, commits, dirty


# ---------- loading ----------

def load_config(project):
    cfg = dict(DEFAULT_CONFIG)
    path = os.path.join(project, "backpack.json")
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            cfg.update(json.load(f))
    return cfg


# ---------- cipher and envelopes ----------

def load_cipher(cfg):
    """The adventure's cipher: backpack.json "cipher" on top of its preset (ciphers.json).
    Returns (cipher, problems). cipher["symbols"] maps an answer character to its symbol."""
    with open(os.path.join(KIT, "ciphers.json"), encoding="utf-8") as f:
        presets = json.load(f)
    own = cfg.get("cipher") or {}
    problems = [] if cfg.get("cipher") else ['no "cipher" in backpack.json; using the "shapes" preset']
    c = dict(DEFAULT_CIPHER, **own)
    preset = presets.get(c["preset"]) if isinstance(c.get("preset"), str) and not c["preset"].startswith("_") else None
    if c.get("preset") and preset is None:
        problems.append(f"unknown cipher preset {c['preset']!r}; presets: "
                        + ", ".join(k for k in presets if not k.startswith("_")))
    base = preset or {}
    symbols = {str(k).upper(): v for k, v in (own.get("symbols") or base.get("symbols") or {}).items()}
    labels = {str(k).upper(): v for k, v in (own.get("labels") or base.get("labels") or {}).items()}
    if len(set(symbols.values())) < len(symbols):
        problems.append("cipher symbols must all be different, or two answers could give the same envelope")
    length = c.get("length") or [4, 5]
    if isinstance(length, int):
        length = [length, length]
    return {"name": own.get("name") or base.get("name") or "Cipher", "preset": c.get("preset") or "",
            "symbols": symbols, "labels": labels, "length": [int(length[0]), int(length[-1])],
            "decoys": int(c.get("decoys") or 0)}, problems


def norm_answer(answer):
    """Answers ignore case, spaces and dashes."""
    return re.sub(r"[\s\-_.,:;/|]+", "", str(answer or "")).upper()


def encode(answer, cipher):
    """The symbols for an answer, or None if a character isn't in the cipher."""
    chars = norm_answer(answer)
    if not chars or any(ch not in cipher["symbols"] for ch in chars):
        return None
    return [cipher["symbols"][ch] for ch in chars]


def answer_problems(answer, cipher):
    chars = norm_answer(answer)
    out = []
    bad = sorted({ch for ch in chars if ch not in cipher["symbols"]})
    if bad:
        out.append(f"answer {answer!r} uses {', '.join(bad)}, which the {cipher['name']} cipher can't encode")
    lo, hi = cipher["length"]
    if chars and not lo <= len(chars) <= hi:
        out.append(f"answer {answer!r} has {len(chars)} characters; envelope codes are {lo}"
                   + (f" to {hi}" if hi != lo else "") + " long")
    return out


def decoy_codes(cipher, taken, seed):
    """Codes for decoy envelopes: stable for an adventure, never equal to a real code."""
    rng = random.Random(seed)
    keys = sorted(cipher["symbols"])
    lo, hi = cipher["length"]
    out, seen = [], {"".join(c) for c in taken}
    for _ in range(cipher["decoys"] * 50):
        if len(out) >= cipher["decoys"] or not keys:
            break
        code = [cipher["symbols"][rng.choice(keys)] for _ in range(rng.randint(lo, hi))]
        if "".join(code) not in seen:
            seen.add("".join(code))
            out.append(code)
    return out


def live(r):
    return r.get("status") != "parked" and not r.get("superseded_by")


def envelope_model(records, cfg, cipher):
    """Every envelope in play order: the puzzle whose answer opens it, its code and what's inside.
    Includes ideas and candidates (each envelope carries its puzzle's status); parked ones are left out."""
    puzzles = [r for r in records if r["type"] == "puzzle" and live(r)]
    props = [r for r in records if r["type"] == "prop" and live(r)]
    envelopes = []
    for p in play_order(puzzles, props):
        envelopes.append({
            "puzzle": p["id"], "title": p.get("title") or "", "status": p.get("status") or "",
            "answer": p.get("answer") or "", "code": encode(p.get("answer"), cipher),
            "contents": [x["id"] for x in props if x.get("envelope") == p["id"]],
        })
    real = [e["code"] for e in envelopes if e["code"]]
    return {"start": [x["id"] for x in props if x.get("envelope") == "start"],
            "envelopes": envelopes,
            "decoys": decoy_codes(cipher, real, cfg.get("name", ""))}


def record_files(project):
    root = os.path.join(project, "records")
    for type_, info in TYPES.items():
        folder = os.path.join(root, info["folder"])
        if not os.path.isdir(folder):
            continue
        for name in sorted(os.listdir(folder)):
            if name.endswith(".md"):
                yield type_, os.path.join(folder, name)


def id_sort_key(rid):
    m = ID_RE.match(rid or "")
    return (m.group(1), int(m.group(2))) if m else ("~", 0)


def load(project):
    cfg = load_config(project)
    per_file, commits, dirty = git_info(project)
    today = datetime.date.today()
    records, warnings = [], []

    def warn(rel, rid, msg):
        warnings.append({"file": rel, "id": rid, "msg": msg})

    cipher, problems = load_cipher(cfg)
    for msg in problems:
        warn("backpack.json", None, msg)

    for folder_type, path in record_files(project):
        rel = os.path.relpath(path, project).replace(os.sep, "/")
        with open(path, encoding="utf-8") as f:
            fields, body, errors = parse_record(f.read())
        for e in errors:
            warn(rel, None, e)
        if fields is None:
            continue
        rid = fields.get("id")
        rtype = fields.get("type") or folder_type
        if not rid or not ID_RE.match(str(rid)):
            warn(rel, rid, f"missing or malformed id: {rid!r} (expected like PZ-004)")
            continue
        prefix = ID_RE.match(rid).group(1)
        if rtype not in TYPES:
            warn(rel, rid, f"unknown type {rtype!r}")
        elif TYPES[rtype]["prefix"] != prefix:
            warn(rel, rid, f"id prefix {prefix} doesn't match type {rtype} ({TYPES[rtype]['prefix']})")
        if rtype != folder_type:
            warn(rel, rid, f"type {rtype!r} is in the {TYPES[folder_type]['folder']}/ folder")
        if not os.path.basename(path).startswith(rid):
            warn(rel, rid, "file name should start with the id")
        if not fields.get("title"):
            warn(rel, rid, "missing title")
        allowed = QUESTION_STATUSES if rtype == "question" else STATUSES
        if fields.get("status") not in allowed:
            warn(rel, rid, f"status {fields.get('status')!r} is not one of: {', '.join(allowed)}")
        for key, fix in LEGACY_FIELDS.items():
            if key in fields:
                warn(rel, rid, f"{key} is from the lock-based kit; {fix}")
        if rtype == "puzzle" and fields.get("answer") and fields.get("status") != "parked" and not fields.get("superseded_by"):
            for msg in answer_problems(fields["answer"], cipher):
                warn(rel, rid, msg)
        if rtype == "puzzle":
            for key, allowed_values in (("test_status", ("untested", "passed", "changes-needed")),
                                        ("test_method", ("physical", "digital")),
                                        ("publish_hints", ("yes", "no"))):
                if fields.get(key) and fields[key] not in allowed_values:
                    warn(rel, rid, f"{key} must be one of: {', '.join(allowed_values)}")
        if rtype == "prop" and fields.get("after_game") and fields["after_game"] not in AFTER_GAME:
            warn(rel, rid, f"after_game must be one of: {', '.join(AFTER_GAME)}")

        history = per_file.get(rel, [])
        is_dirty = rel in dirty or not history
        if is_dirty:
            touched = datetime.date.fromtimestamp(os.path.getmtime(path)).isoformat()
        else:
            touched = history[0]["date"]
        age = (today - datetime.date.fromisoformat(touched)).days
        stale = (fields.get("status") in STALE_STATUSES and not fields.get("superseded_by")
                 and age > cfg["staleDays"])

        rec = dict(fields)
        rec.update({"id": rid, "type": rtype, "body": body, "path": rel,
                    "touched": touched, "ageDays": age, "dirty": is_dirty, "stale": stale,
                    "history": history[:8]})
        if rtype == "asset" and fields.get("file"):
            rec["fileExists"] = os.path.exists(os.path.join(project, fields["file"]))
        records.append(rec)

    by_id = {}
    for r in records:
        if r["id"] in by_id:
            warn(r["path"], r["id"], f"duplicate id (also in {by_id[r['id']]['path']})")
        else:
            by_id[r["id"]] = r
    for r in records:
        for field in REF_FIELDS:
            for target in as_list(r.get(field)):
                if field == "envelope" and target == "start":
                    continue
                if target not in by_id:
                    warn(r["path"], r["id"], f"{field} points to unknown id {target}")
                expected = {"beat": "beat", "props": "prop", "needs": "puzzle", "for": "prop", "envelope": "puzzle"}.get(field)
                if expected and target in by_id and by_id[target]["type"] != expected:
                    warn(r["path"], r["id"], f"{field} requires a {expected} ID, not {target}")
        if r.get("superseded_by") == r["id"]:
            warn(r["path"], r["id"], "superseded_by points to itself")
        if (r["type"] == "puzzle" and r.get("publish_hints") == "yes" and not r.get("superseded_by")
                and r.get("status") in ("decided", "built") and hint_gaps(r)):
            warn(r["path"], r["id"], f"publish_hints: yes but missing {', '.join(hint_gaps(r))}; "
                                     "left off the public hint page")

    records.sort(key=lambda r: id_sort_key(r["id"]))
    envelopes = envelope_model(records, cfg, cipher)
    codes = {}
    for e in envelopes["envelopes"]:
        if e["code"]:
            codes.setdefault("".join(e["code"]), []).append(e["puzzle"])
    for code, ids in codes.items():
        if len(ids) > 1:
            warn(by_id[ids[1]]["path"], ids[1], f"same envelope code {code} as {', '.join(ids[:1] + ids[2:])}: "
                                                "change one answer so each envelope is unique")
    rel_to_id = {r["path"]: r["id"] for r in records}
    changes = []
    dirty_ids = sorted({rel_to_id[p] for p in dirty if p in rel_to_id}, key=id_sort_key)
    if dirty_ids:
        changes.append({"date": today.isoformat(), "subject": "Uncommitted edits", "ids": dirty_ids,
                        "uncommitted": True})
    for c in commits[:40]:
        ids = sorted({rel_to_id[p] for p in c["paths"] if p in rel_to_id}, key=id_sort_key)
        if ids:
            changes.append({"date": c["date"], "subject": c["subject"], "ids": ids})

    return {
        "config": cfg,
        "builtAt": datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),
        "today": today.isoformat(),
        "types": TYPES,
        "refFields": REF_FIELDS,
        "records": records,
        "changes": changes,
        "warnings": warnings,
        "readiness": readiness(records),
        "releaseReadiness": readiness(records, release=True),
        "cipher": cipher,
        "envelopes": envelopes,
        "playOrder": [e["puzzle"] for e in envelopes["envelopes"]],
    }


# ---------- commands ----------

def find_project(start):
    p = os.path.abspath(start)
    while True:
        if os.path.exists(os.path.join(p, "backpack.json")):
            return p
        parent = os.path.dirname(p)
        if parent == p:
            sys.exit("No backpack.json found here or above. Run inside a backpack project, "
                     "or pass --project.")
        p = parent


def print_warnings(warnings):
    for w in warnings:
        print(f"  ! {w['file']}: {w['msg']}")


def md_section(body, heading):
    """Text of a '## Heading' section of a record body, up to the next ## heading."""
    out = None
    for ln in (body or "").split("\n"):
        m = re.match(r"^##\s+(.*)", ln)
        if m:
            if out is not None:
                break
            if m.group(1).strip().lower() == heading.lower():
                out = []
            continue
        if out is not None:
            out.append(ln)
    return "\n".join(out).strip() if out else ""


def list_items(text):
    items = []
    for ln in text.split("\n"):
        m = re.match(r"^\s*(?:[-*]|\d+\.)\s*(.*)$", ln)
        if m:
            if m.group(1).strip():
                items.append(m.group(1).strip())
        elif ln.strip() and items:
            items[-1] += " " + ln.strip()
    return items


def play_order(puzzles, props):
    """Puzzles in the order a player can solve them (envelope / needs / props); unreachable ones last."""
    done, hand = [], {x["id"] for x in props if x.get("envelope") == "start"}
    grew = True
    while grew:
        grew = False
        for p in sorted(puzzles, key=lambda p: id_sort_key(p["id"])):
            if p["id"] in done:
                continue
            if (all(n in done for n in as_list(p.get("needs")))
                    and all(x in hand for x in as_list(p.get("props")))):
                done.append(p["id"])
                hand |= {x["id"] for x in props if x.get("envelope") == p["id"]}
                grew = True
                break
    order = {pid: i for i, pid in enumerate(done)}
    return sorted(puzzles, key=lambda p: (order.get(p["id"], 10_000), id_sort_key(p["id"])))


def hint_gaps(p):
    """What a puzzle marked publish_hints: yes still lacks for the public hint page."""
    gaps = [label for label, ok in (
        ("hint_title", p.get("hint_title")),
        ("## Hints list", list_items(md_section(p.get("body", ""), "Hints"))),
        ("## Solution", md_section(p.get("body", ""), "Solution")),
        ("answer", p.get("answer"))) if not ok]
    return gaps


def build_hints(data, site, viewer):
    """Write site/hints/index.html: a self-contained, public, player-facing hint page.
    It carries only each puzzle's hint_title, hints, answer, envelope code and solution: no design notes.
    (The payload keeps the name "locks" because the stats API and sync.js count steps as locks.)"""
    playable = ("decided", "built")
    selected = [r for r in data["records"] if not r.get("superseded_by") and r.get("status") in playable]
    # Incomplete puzzles are left off the page; load() reports them as warnings.
    puzzles = [r for r in selected if r["type"] == "puzzle" and r.get("publish_hints") == "yes"
               and not hint_gaps(r)]
    props = [r for r in selected if r["type"] == "prop"]
    ordered = play_order([r for r in selected if r["type"] == "puzzle"], props)
    public_ids = {p["id"] for p in puzzles}
    cipher = data.get("cipher") or load_cipher(data["config"])[0]
    locks = [{
        "id": p["id"],
        "title": p.get("hint_title") or "",
        "status": p["status"],
        "hints": list_items(md_section(p["body"], "Hints")),
        "answer": p.get("answer") or "",
        "code": "".join(encode(p.get("answer"), cipher) or []),
        "solution": md_section(p["body"], "Solution"),
    } for p in ordered if p["id"] in public_ids]
    payload = {"name": data["config"]["name"], "builtAt": data["builtAt"], "locks": locks}
    # Optional run logging, game codes and team comparison (viewer/sync.js); see docs/RECORDS.md.
    if data["config"].get("stats"):
        payload["stats"] = data["config"]["stats"]

    def read(name):
        with open(os.path.join(viewer, name), encoding="utf-8") as f:
            return f.read()
    html = read(os.path.join("hints", "index.html"))
    html = html.replace('<link rel="stylesheet" href="../style.css">', "<style>\n" + read("style.css") + "</style>")
    html = html.replace('<script src="../common.js"></script>', "<script>\n" + read("common.js") + "</script>")
    html = html.replace('<script src="../sync.js"></script>', "<script>\n" + read("sync.js") + "</script>")
    data_js = "window.HINTS = " + json.dumps(payload, ensure_ascii=False).replace("</", "<\\/") + ";"
    html = html.replace('<script src="hints-data.js"></script>', "<script>" + data_js + "</script>")
    os.makedirs(os.path.join(site, "hints"), exist_ok=True)
    with open(os.path.join(site, "hints", "index.html"), "w", encoding="utf-8") as f:
        f.write(html)


NO_NOTE = re.compile(r"^(none needed|not recorded yet)\b", re.I)


def reset_model(data):
    """The public reset checklist: one step per envelope (its code and what goes back in it),
    then what goes loose in the box. Built from the decided/built game: puzzles (answer) and
    props (envelope, after_game, reset_name, ## Reset)."""
    playable = ("decided", "built")
    selected = [r for r in data["records"] if not r.get("superseded_by") and r.get("status") in playable]
    props = [r for r in selected if r["type"] == "prop"]
    cipher = data.get("cipher") or load_cipher(data["config"])[0]
    ordered = play_order([r for r in selected if r["type"] == "puzzle"], props)
    name = lambda p: p.get("reset_name") or p.get("title") or p["id"]
    fate = lambda p: p.get("after_game") or "return"
    note = lambda p: " ".join(md_section(p.get("body", ""), "Reset").split())

    # A note many props share (e.g. "fold the map along its creases") is said once, at the top.
    counts = {}
    for p in props:
        if note(p) and not NO_NOTE.match(note(p)):
            counts[note(p)] = counts.get(note(p), 0) + 1
    general = [n for n, c in counts.items() if c >= 3]

    def notes(ps):
        seen = []
        for p in ps:
            n = note(p)
            if n and not NO_NOTE.match(n) and n not in general and n not in seen:
                seen.append(n)
        return seen

    steps = []
    for n, puzzle in enumerate(ordered, 1):
        inside = [p for p in props if p.get("envelope") == puzzle["id"]]
        steps.append({
            "id": puzzle["id"], "n": n, "code": "".join(encode(puzzle.get("answer"), cipher) or []),
            "put": [name(p) for p in inside if fate(p) == "return"],
            "keep": [name(p) for p in inside if fate(p) == "keep"],
            "notes": notes(inside),
        })
    start = [p for p in props if p.get("envelope") == "start"]
    return {
        "name": data["config"]["name"], "builtAt": data["builtAt"], "general": general, "steps": steps,
        "decoys": cipher["decoys"],
        "start": [name(p) for p in start if fate(p) == "return"],
        "startNotes": notes(start),
    }


def build_reset(data, site, viewer):
    """Write site/reset/index.html, a public, self-contained reset checklist (publish_reset: true)."""
    def read(name):
        with open(os.path.join(viewer, name), encoding="utf-8") as f:
            return f.read()
    html = read(os.path.join("reset", "index.html"))
    html = html.replace('<link rel="stylesheet" href="../style.css">', "<style>\n" + read("style.css") + "</style>")
    html = html.replace('<script src="../common.js"></script>', "<script>\n" + read("common.js") + "</script>")
    data_js = "window.RESET = " + json.dumps(reset_model(data), ensure_ascii=False).replace("</", "<\\/") + ";"
    html = html.replace('<script src="reset-data.js"></script>', "<script>" + data_js + "</script>")
    os.makedirs(os.path.join(site, "reset"), exist_ok=True)
    with open(os.path.join(site, "reset", "index.html"), "w", encoding="utf-8") as f:
        f.write(html)


def cmd_build(project, quiet=False):
    data = load(project)
    site = os.path.join(project, "site")
    os.makedirs(site, exist_ok=True)
    viewer = os.path.join(KIT, "viewer")
    for name in os.listdir(viewer):
        if name.endswith((".html", ".js", ".css")):
            shutil.copyfile(os.path.join(viewer, name), os.path.join(site, name))
    # Static hosts cache .js/.css for hours; a new ?v= on each build makes a normal refresh
    # pick up the latest data.js. The HTML pages themselves are always revalidated.
    version = str(int(time.time()))
    for page in ("index.html", "play.html", "print.html"):
        path = os.path.join(site, page)
        with open(path, encoding="utf-8") as f:
            html = f.read()
        for asset in ("data.js", "common.js", "style.css"):
            html = html.replace('"' + asset + '"', '"' + asset + "?v=" + version + '"')
        with open(path, "w", encoding="utf-8", newline="") as f:
            f.write(html)
    # Copy made asset files into site/files/ so the page works when only site/ is published.
    files_dir = os.path.join(site, "files")
    shutil.rmtree(files_dir, ignore_errors=True)
    for r in data["records"]:
        if r.get("fileExists"):
            dest = os.path.join(files_dir, r["file"])
            os.makedirs(os.path.dirname(dest), exist_ok=True)
            shutil.copyfile(os.path.join(project, r["file"]), dest)
    payload = json.dumps(data, ensure_ascii=False, indent=1).replace("</", "<\\/")
    with open(os.path.join(site, "data.js"), "w", encoding="utf-8") as f:
        f.write("window.BACKPACK = " + payload + ";\n")
    build_hints(data, site, viewer)
    if data["config"].get("publish_reset"):
        build_reset(data, site, viewer)
    if not quiet:
        print(f"Built {len(data['records'])} records -> {os.path.relpath(site)}{os.sep}index.html")
        if data["warnings"]:
            print(f"{len(data['warnings'])} warning(s):")
            print_warnings(data["warnings"])
    return data


def cmd_check(project):
    data = load(project)
    if data["warnings"]:
        print(f"{len(data['warnings'])} problem(s):")
        print_warnings(data["warnings"])
        return 1
    print(f"OK: {len(data['records'])} records, no problems.")
    return 0


def cmd_ready(project, candidates=False, release=False):
    data = load(project)
    problems = data["warnings"] + readiness(data["records"], candidates, release)
    if problems:
        print(f"{len(problems)} readiness gap(s); unfinished ideas are allowed:")
        print_warnings(problems)
        return 1
    print("Recorded release checks complete." if release else "Ready for a playtest on the recorded information.")
    print("This does not prove puzzle fairness, uniqueness or physical reliability.")
    return 0


def cmd_serve(project, port):
    cmd_build(project)
    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=project)
    handler.log_message = lambda *a, **k: None
    with http.server.ThreadingHTTPServer(("127.0.0.1", port), handler) as httpd:
        print(f"Preview: http://localhost:{port}/site/   (Ctrl+C to stop; re-run build after edits)")
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            pass


def slugify(title):
    s = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")
    return s[:40].rstrip("-") or "untitled"


def cmd_new(project, type_, title):
    info = TYPES[type_]
    folder = os.path.join(project, "records", info["folder"])
    os.makedirs(folder, exist_ok=True)
    used = 0
    for _, path in record_files(project):
        m = re.match(rf"^{info['prefix']}-(\d+)", os.path.basename(path))
        if m:
            used = max(used, int(m.group(1)))
    rid = f"{info['prefix']}-{used + 1:03d}"
    with open(os.path.join(KIT, "templates", "records", f"{type_}.md"), encoding="utf-8") as f:
        text = f.read().replace("{{id}}", rid).replace("{{title}}", title)
    path = os.path.join(folder, f"{rid}-{slugify(title)}.md")
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)
    print(f"Created {os.path.relpath(path, project)}")


def cmd_init(target, name):
    target = os.path.abspath(target)
    os.makedirs(target, exist_ok=True)
    src = os.path.join(KIT, "templates", "project")
    for dirpath, _, files in os.walk(src):
        for fn in files:
            s = os.path.join(dirpath, fn)
            rel = os.path.relpath(s, src)
            d = os.path.join(target, rel)
            if os.path.exists(d):
                print(f"  kept existing {rel}")
                continue
            os.makedirs(os.path.dirname(d), exist_ok=True)
            with open(s, encoding="utf-8") as f:
                text = f.read().replace("{{name}}", name).replace("{{repo}}", os.path.basename(target))
            with open(d, "w", encoding="utf-8", newline="\n") as f:
                f.write(text)
            print(f"  created {rel}")
    for info in TYPES.values():
        folder = os.path.join(target, "records", info["folder"])
        os.makedirs(folder, exist_ok=True)
        keep = os.path.join(folder, ".gitkeep")
        if not os.listdir(folder):
            open(keep, "w").close()
    print(f"Initialised {name} in {target}")


def main():
    ap = argparse.ArgumentParser(description="Backpack design kit", formatter_class=argparse.RawDescriptionHelpFormatter,
                                 epilog=__doc__)
    ap.add_argument("--project", default=".", help="backpack project folder (default: search upward from here)")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("build", help="write site/ from records/")
    sub.add_parser("check", help="validate records")
    rp = sub.add_parser("ready", help="audit playtest preparation without changing records")
    rp.add_argument("--include-candidates", action="store_true", help="also audit draft candidates")
    rp.add_argument("--release", action="store_true", help="also require recorded physical playtest evidence")
    sp = sub.add_parser("serve", help="build and preview")
    sp.add_argument("--port", type=int, default=8000)
    np_ = sub.add_parser("new", help="create a record from a template")
    np_.add_argument("type", choices=list(TYPES))
    np_.add_argument("title")
    ip = sub.add_parser("init", help="set up a new backpack project folder")
    ip.add_argument("target")
    ip.add_argument("--name", required=True)
    a = ap.parse_args()

    if a.cmd == "init":
        return cmd_init(a.target, a.name)
    project = find_project(a.project)
    if a.cmd == "build":
        cmd_build(project)
    elif a.cmd == "check":
        return cmd_check(project)
    elif a.cmd == "ready":
        return cmd_ready(project, a.include_candidates, a.release)
    elif a.cmd == "serve":
        cmd_serve(project, a.port)
    elif a.cmd == "new":
        cmd_new(project, a.type, a.title)


if __name__ == "__main__":
    sys.exit(main() or 0)
