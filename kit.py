#!/usr/bin/env python3
"""backpack-kit: turn a backpack's Markdown records into the design viewer.

Run from inside a backpack project folder (the one with backpack.json):

  python ../backpack-kit/kit.py build                 write site/ from records/
  python ../backpack-kit/kit.py serve                 build, then preview at http://localhost:8000/site/
  python ../backpack-kit/kit.py check                 validate records, print problems
  python ../backpack-kit/kit.py new puzzle "Star chart"
  python ../backpack-kit/kit.py init ../Celtic --name "Celtic"

Types for `new`: premise, beat, puzzle, prop, question, asset.
No dependencies beyond Python 3.9+ and git.
"""
import argparse
import datetime
import functools
import http.server
import json
import os
import time
import re
import shutil
import subprocess
import sys
from checks import readiness, flow_model

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
REF_FIELDS = ["links", "superseded_by", "beat", "props", "needs", "about", "for", "found_in"]
INT_FIELDS = ["order", "difficulty"]
ID_RE = re.compile(r"^([A-Z]{1,2})-(\d{3,})$")
# Default lock kit for every backpack (GUIDE.md). A backpack can override "locks" in backpack.json.
DEFAULT_LOCKS = ["3-digit", "4-digit", "4-letter", "3-digit-colour"]
DEFAULT_CONFIG = {"name": "Untitled backpack", "beatLabel": "Structure beat", "staleDays": 30,
                  "locks": DEFAULT_LOCKS}


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
        if rtype == "puzzle" and fields.get("lock") and fields["lock"] not in cfg["locks"]:
            warn(rel, rid, f"lock {fields['lock']!r} is not one of: {', '.join(cfg['locks'])}")
        if rtype == "puzzle":
            for key, allowed_values in (("test_status", ("untested", "passed", "changes-needed")),
                                        ("test_method", ("physical", "digital")),
                                        ("publish_hints", ("yes", "no"))):
                if fields.get(key) and fields[key] not in allowed_values:
                    warn(rel, rid, f"{key} must be one of: {', '.join(allowed_values)}")

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
                if field == "found_in" and target == "start":
                    continue
                if field == "found_in" and target in by_id and by_id[target]["type"] != "puzzle":
                    warn(r["path"], r["id"], f"found_in must be start or a puzzle ID, not {target}")
                if target not in by_id:
                    warn(r["path"], r["id"], f"{field} points to unknown id {target}")
                expected = {"beat": "beat", "props": "prop", "needs": "puzzle", "for": "prop"}.get(field)
                if expected and target in by_id and by_id[target]["type"] != expected:
                    warn(r["path"], r["id"], f"{field} requires a {expected} ID, not {target}")
        if r.get("superseded_by") == r["id"]:
            warn(r["path"], r["id"], "superseded_by points to itself")
        if (r["type"] == "puzzle" and r.get("publish_hints") == "yes" and not r.get("superseded_by")
                and r.get("status") in ("decided", "built") and hint_gaps(r)):
            warn(r["path"], r["id"], f"publish_hints: yes but missing {', '.join(hint_gaps(r))}; "
                                     "left off the public hint page")

    records.sort(key=lambda r: id_sort_key(r["id"]))
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
        "flow": flow_model(records),
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
    """Puzzles in the order a player can open them (found_in / needs / props); unreachable ones last."""
    ids = {p["id"] for p in puzzles}
    prop_ids = {x["id"] for x in props}
    done, hand = [], {x["id"] for x in props if x.get("found_in") == "start"}
    grew = True
    while grew:
        grew = False
        for p in sorted(puzzles, key=lambda p: id_sort_key(p["id"])):
            if p["id"] in done:
                continue
            if (all(n in done for n in as_list(p.get("needs")))
                    and all(x in hand for x in as_list(p.get("props")))):
                done.append(p["id"])
                hand |= {x["id"] for x in props if x.get("found_in") == p["id"]}
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
        ("answer", not p.get("lock") or p.get("answer"))) if not ok]
    return gaps


def build_hints(data, site, viewer):
    """Write site/hints/index.html: a self-contained, public, player-facing hint page.
    It carries only each lock's hint_title, lock type, hints and solution: no design notes."""
    playable = ("decided", "built")
    live = [r for r in data["records"] if not r.get("superseded_by") and r.get("status") in playable]
    # Incomplete puzzles are left off the page; load() reports them as warnings.
    puzzles = [r for r in live if r["type"] == "puzzle" and r.get("publish_hints") == "yes"
               and not hint_gaps(r)]
    props = [r for r in live if r["type"] == "prop"]
    ordered = play_order([r for r in live if r["type"] == "puzzle"], props)
    public_ids = {p["id"] for p in puzzles}
    locks = [{
        "id": p["id"],
        "title": p.get("hint_title") or "",
        "lock": p.get("lock") or "",
        "status": p["status"],
        "hints": list_items(md_section(p["body"], "Hints")),
        "answer": p.get("answer") or "",
        "solution": md_section(p["body"], "Solution"),
    } for p in ordered if p["id"] in public_ids]
    payload = {"name": data["config"]["name"], "builtAt": data["builtAt"], "locks": locks}

    def read(name):
        with open(os.path.join(viewer, name), encoding="utf-8") as f:
            return f.read()
    html = read(os.path.join("hints", "index.html"))
    html = html.replace('<link rel="stylesheet" href="../style.css">', "<style>\n" + read("style.css") + "</style>")
    html = html.replace('<script src="../common.js"></script>', "<script>\n" + read("common.js") + "</script>")
    data_js = "window.HINTS = " + json.dumps(payload, ensure_ascii=False).replace("</", "<\\/") + ";"
    html = html.replace('<script src="hints-data.js"></script>', "<script>" + data_js + "</script>")
    os.makedirs(os.path.join(site, "hints"), exist_ok=True)
    with open(os.path.join(site, "hints", "index.html"), "w", encoding="utf-8") as f:
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
    for page in ("index.html", "play.html"):
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
