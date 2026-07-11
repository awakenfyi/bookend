#!/usr/bin/env python3
"""bookend — give every AI-generated file a name that sorts and a memory that lasts.

A sortable name at the front, a colophon at the back. Zero dependencies. One file.
"""
import sys, os, re, json, datetime, argparse

CONFIG = ".bookend.json"
FORMATS = {
    "topic-first": "{topic}__{kind}__{date}__{version}{ext}",   # groups by subject (default)
    "date-first":  "{date}__{topic}__{kind}__{version}{ext}",   # sorts newest-by-name
    "flat-slug":   "{topic}-{kind}-{date}-{version}{ext}",       # single-dash, simplest
    "numbered":    "{seq}__{topic}__{kind}{ext}",               # lab-notebook sequential
    "minimal":     "{topic}__{date}{ext}",                       # lightest: subject + date
}
DEFAULTS = {
    "format": "topic-first",
    "scratch_dirs": ["scratch", "tmp", "_wip", ".git", "node_modules", "dist", "build", "vendor"],
    "extensions": [".html", ".md"],
}
KINDS = ["site-page", "chapter", "deck", "spec", "wireframe", "report", "packet",
         "note", "page", "doc"]
COLO_RE = re.compile(r"<!--\s*colophon\b(.*?)-->", re.DOTALL | re.IGNORECASE)

def kebab(s):
    return re.sub(r"-+", "-", re.sub(r"[^a-z0-9]+", "-", s.lower())).strip("-") or "untitled"

def load_config(root):
    p = os.path.join(root, CONFIG)
    if os.path.exists(p):
        return {**DEFAULTS, **json.load(open(p))}
    return dict(DEFAULTS)

def infer_title(text, stem, ext):
    if ext == ".html":
        m = re.search(r"<title>(.*?)</title>", text, re.I | re.S) or re.search(r"<h1[^>]*>(.*?)</h1>", text, re.I | re.S)
        if m: return re.sub(r"<[^>]+>", "", m.group(1)).strip()
    if ext == ".md":
        m = re.search(r"^#\s+(.+)$", text, re.M)
        if m: return m.group(1).strip()
    return stem.replace("_", " ").replace("-", " ").strip()

def infer_kind(name, title, ext):
    hay = (name + " " + title).lower()
    for k in KINDS:
        if k.replace("-", "") in hay.replace("-", "").replace("_", ""):
            return k
    return "page" if ext == ".html" else "doc"

def read_colophon(text):
    m = COLO_RE.search(text)
    if not m: return None
    fields = {}
    for line in m.group(1).splitlines():
        if ":" in line:
            k, v = line.split(":", 1)
            fields[k.strip()] = v.strip()
    return fields

def build_colophon(meta):
    order = ["title", "kind", "version", "date", "supersedes", "related", "source", "status"]
    lines = ["<!-- colophon"]
    for k in order:
        lines.append(f"{k}: {meta.get(k, '')}")
    lines.append("-->")
    return "\n".join(lines)

def strip_colophon(text):
    return COLO_RE.sub("", text).rstrip()

def gather_meta(path, cfg, bump=False):
    text = open(path, encoding="utf-8", errors="ignore").read()
    stem, ext = os.path.splitext(os.path.basename(path))
    existing = read_colophon(text) or {}
    title = existing.get("title") or infer_title(text, stem, ext)
    date = existing.get("date") or datetime.date.fromtimestamp(os.path.getmtime(path)).isoformat()
    kind = existing.get("kind") or infer_kind(stem, title, ext)
    ver = existing.get("version") or "v01"
    if bump:
        n = int("".join(c for c in ver if c.isdigit()) or "1") + 1
        ver = f"v{n:02d}"
    meta = {
        "title": title, "kind": kind, "version": ver, "date": date,
        "supersedes": existing.get("supersedes", ""),
        "related": existing.get("related", ""),
        "source": existing.get("source", ""),
        "status": existing.get("status", "draft"),
    }
    return text, ext, meta

def compliant_name(meta, ext, cfg, seq=1):
    tmpl = FORMATS[cfg["format"]]
    return tmpl.format(topic=kebab(meta["title"]), kind=meta["kind"], date=meta["date"],
                       version=meta["version"], seq=f"{seq:04d}", ext=ext)


def unique_name(meta, ext, cfg, taken, seq=1):
    """Bump the version until the name is free, so same-titled files become a version series."""
    m = dict(meta)
    while True:
        name = compliant_name(m, ext, cfg, seq)
        if name not in taken:
            return name, m["version"]
        n = int("".join(c for c in m["version"] if c.isdigit()) or "1") + 1
        m["version"] = f"v{n:02d}"

def is_scratch(path, cfg):
    parts = set(os.path.normpath(path).split(os.sep))
    return bool(parts & set(cfg["scratch_dirs"]))

def iter_files(root, cfg):
    for dp, dn, fn in os.walk(root):
        dn[:] = [d for d in dn if d not in cfg["scratch_dirs"]]
        for f in fn:
            if os.path.splitext(f)[1].lower() in cfg["extensions"]:
                yield os.path.join(dp, f)

# ---- commands ----
def cmd_formats(a):
    print("Bookend naming formats (set one with `bookend init --format NAME`):\n")
    for name, tmpl in FORMATS.items():
        eg = tmpl.format(topic="awaken-home", kind="site-page", date="2026-07-09",
                         version="v04", seq="0004", ext=".html")
        print(f"  {name:12} {tmpl}")
        print(f"  {'':12} e.g.  {eg}\n")

def cmd_init(a):
    if a.format not in FORMATS:
        sys.exit(f"unknown format '{a.format}'. run `bookend formats`.")
    cfg = dict(DEFAULTS); cfg["format"] = a.format
    json.dump(cfg, open(CONFIG, "w"), indent=2)
    print(f"wrote {CONFIG} (format: {a.format}). run `bookend scan .` to see the plan.")

def cmd_stamp(a):
    cfg = load_config(".")
    text, ext, meta = gather_meta(a.file, cfg, bump=a.bump)
    body = strip_colophon(text)
    out = body + "\n\n" + build_colophon(meta) + "\n"
    if a.write:
        open(a.file, "w", encoding="utf-8").write(out)
        print(f"stamped {a.file}")
    else:
        print(build_colophon(meta))
    print(f"compliant name → {compliant_name(meta, ext, cfg)}")

def cmd_scan(a):
    cfg = load_config(a.dir)
    rows, renames, taken = [], 0, set()
    for i, path in enumerate(sorted(iter_files(a.dir, cfg)), 1):
        _, ext, meta = gather_meta(path, cfg)
        cur = os.path.basename(path)
        want, _ = unique_name(meta, ext, cfg, taken, seq=i)
        taken.add(want)
        ok = cur == want
        renames += 0 if ok else 1
        rows.append((ok, cur, want))
    print(f"BOOKEND SCAN · {a.dir} · format={cfg['format']} · {len(rows)} files · {renames} need renaming\n")
    for ok, cur, want in rows:
        print(f"  {'OK ' if ok else '→  '} {cur}")
        if not ok: print(f"       becomes: {want}")
    if renames:
        print(f"\nDRY RUN. nothing moved. to execute: bookend apply {a.dir} --yes")

def cmd_apply(a):
    cfg = load_config(a.dir)
    plan, taken = [], set()
    for i, path in enumerate(sorted(iter_files(a.dir, cfg)), 1):
        text, ext, meta = gather_meta(path, cfg)
        want, ver = unique_name(meta, ext, cfg, taken, seq=i)
        meta["version"] = ver
        taken.add(want)
        newp = os.path.join(os.path.dirname(path), want)
        stamped = strip_colophon(text) + "\n\n" + build_colophon(meta) + "\n"
        plan.append((path, newp, os.path.basename(path), want, stamped, path != newp))
    print(f"BOOKEND APPLY · {sum(1 for p in plan if p[5])} renames + colophon on {len(plan)} files")
    if not a.yes:
        print("refusing to move files without --yes. this rewrites names AND injects colophons.")
        return
    name_map = {p[2]: p[3] for p in plan if p[5]}
    for old, new, ocur, ncur, stamped, moved in plan:
        # rewrite internal links to any renamed sibling before writing
        for o, n in name_map.items():
            stamped = stamped.replace(o, n)
        open(old, "w", encoding="utf-8").write(stamped)
        if moved:
            if os.path.exists(new):
                print(f"SKIP (target exists): {ncur}"); continue
            os.rename(old, new)
            print(f"moved: {ocur} → {ncur}")
        else:
            print(f"stamped: {ocur}")
    print("done. run `bookend index` to build the searchable INDEX.")

def cmd_index(a):
    cfg = load_config(a.dir)
    rows = []
    for path in iter_files(a.dir, cfg):
        m = read_colophon(open(path, encoding="utf-8", errors="ignore").read())
        if m:
            rows.append((m.get("date", ""), m.get("title", ""), m.get("kind", ""),
                         m.get("version", ""), m.get("status", ""),
                         os.path.relpath(path, a.dir), m.get("supersedes", ""), m.get("related", "")))
    rows.sort(reverse=True)
    dead = []
    known = {os.path.basename(r[5]) for r in rows}
    out = ["# INDEX", "", f"*{len(rows)} bookended files · compiled by Bookend · newest first*", "",
           "| date | title | kind | ver | status | file |", "|---|---|---|---|---|---|"]
    for d, t, k, v, s, f, sup, rel in rows:
        out.append(f"| {d} | {t} | {k} | {v} | {s} | `{f}` |")
        for link in [x.strip() for x in (sup + "," + rel).split(",") if x.strip()]:
            if link.endswith((".html", ".md")) and os.path.basename(link) not in known:
                dead.append((f, link))
    if dead:
        out += ["", "## ⚠ broken lineage (the gate — fix these)", ""]
        for f, link in dead:
            out.append(f"- `{f}` points to missing `{link}`")
    dst = os.path.join(a.dir, "INDEX.md")
    open(dst, "w").write("\n".join(out) + "\n")
    print(f"wrote {dst} · {len(rows)} files · {len(dead)} broken lineage links")
    if dead: sys.exit(1)

def main():
    p = argparse.ArgumentParser(prog="bookend", description="a sortable name at the front, a colophon at the back")
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("formats").set_defaults(fn=cmd_formats)
    i = sub.add_parser("init"); i.add_argument("--format", default="topic-first"); i.set_defaults(fn=cmd_init)
    s = sub.add_parser("stamp"); s.add_argument("file"); s.add_argument("--write", action="store_true"); s.add_argument("--bump", action="store_true"); s.set_defaults(fn=cmd_stamp)
    sc = sub.add_parser("scan"); sc.add_argument("dir", nargs="?", default="."); sc.set_defaults(fn=cmd_scan)
    ap = sub.add_parser("apply"); ap.add_argument("dir", nargs="?", default="."); ap.add_argument("--yes", action="store_true"); ap.set_defaults(fn=cmd_apply)
    ix = sub.add_parser("index"); ix.add_argument("dir", nargs="?", default="."); ix.set_defaults(fn=cmd_index)
    a = p.parse_args(); a.fn(a)

if __name__ == "__main__":
    main()
