#!/usr/bin/env python3
"""bookend — give every file a name that sorts and a memory that lasts.

A sortable name at the front, a colophon at the back (for files that can hold one).
Zero dependencies. One file.
"""
import sys, os, re, json, datetime, argparse

CONFIG = ".bookend.json"
FORMATS = {
    "topic-first": "{topic}__{kind}__{date}__{version}{ext}",
    "date-first":  "{date}__{topic}__{kind}__{version}{ext}",
    "flat-slug":   "{topic}-{kind}-{date}-{version}{ext}",
    "numbered":    "{seq}__{topic}__{kind}{ext}",
    "minimal":     "{topic}__{date}{ext}",
}
# text files → renamed AND stamped with a colophon (Bookend can read them)
STAMP_EXT = [".html", ".md", ".txt"]
# binaries with real names → renamed only; the INDEX is their memory (can't embed a comment)
RENAME_EXT = [".pdf", ".pptx", ".docx", ".xlsx", ".csv", ".zip", ".png", ".jpg",
              ".jpeg", ".heic", ".dng", ".gif", ".svg", ".mp4", ".mov", ".key", ".numbers"]
KIND_BY_EXT = {
    ".pdf": "pdf", ".pptx": "deck", ".key": "deck", ".docx": "doc", ".xlsx": "sheet",
    ".numbers": "sheet", ".csv": "data", ".zip": "archive", ".png": "image", ".jpg": "image",
    ".jpeg": "image", ".heic": "photo", ".dng": "photo", ".gif": "image", ".svg": "image",
    ".mp4": "video", ".mov": "video",
}
KINDS = ["site-page", "chapter", "deck", "spec", "wireframe", "report", "packet", "note", "page", "doc"]
# names that carry no meaning — Bookend refuses to invent a topic for these
OPAQUE = re.compile(r"^(img|dsc|dscn|pxl|photo|screenshot|screen shot|scan|untitled|image|"
                    r"download|file|document|copy of|new|whatsapp|signal|fullsizerender|"
                    r"video|movie|clip|vid|export|render|final|draft|temp|tmp)\b|^[\d\W_]+$",
                    re.IGNORECASE)
COLO_RE = re.compile(r"<!--\s*colophon\b(.*?)-->", re.DOTALL | re.IGNORECASE)
DEFAULTS = {"format": "topic-first",
            "scratch_dirs": ["scratch", "tmp", "_wip", ".git", "node_modules", "dist", "build", "vendor"],
            "stamp_ext": STAMP_EXT, "rename_ext": RENAME_EXT}

def kebab(s):
    return re.sub(r"-+", "-", re.sub(r"[^a-z0-9]+", "-", s.lower())).strip("-") or "untitled"

def bump(ver):
    return f"v{int(''.join(c for c in ver if c.isdigit()) or '1') + 1:02d}"

def load_config(root):
    p = os.path.join(root, CONFIG)
    return {**DEFAULTS, **json.load(open(p))} if os.path.exists(p) else dict(DEFAULTS)

def is_opaque(stem):
    return bool(OPAQUE.match(stem.strip()))

def infer_title(text, stem, ext):
    if ext == ".html":
        m = re.search(r"<title>(.*?)</title>", text, re.I | re.S) or re.search(r"<h1[^>]*>(.*?)</h1>", text, re.I | re.S)
        if m: return re.sub(r"<[^>]+>", "", m.group(1)).strip()
    if ext in (".md", ".txt"):
        m = re.search(r"^#\s+(.+)$", text, re.M)
        if m: return m.group(1).strip()
    return stem.replace("_", " ").replace("-", " ").strip()

def infer_kind(name, title, ext):
    if ext in KIND_BY_EXT: return KIND_BY_EXT[ext]
    hay = (name + " " + title).lower().replace("-", "").replace("_", "")
    for k in KINDS:
        if k.replace("-", "") in hay: return k
    return "page" if ext == ".html" else "doc"

def read_colophon(text):
    m = COLO_RE.search(text)
    if not m: return None
    return {k.strip(): v.strip() for k, v in (l.split(":", 1) for l in m.group(1).splitlines() if ":" in l)}

def build_colophon(meta):
    order = ["title", "kind", "version", "date", "supersedes", "related", "source", "status"]
    return "\n".join(["<!-- colophon"] + [f"{k}: {meta.get(k, '')}" for k in order] + ["-->"])

def strip_colophon(text):
    return COLO_RE.sub("", text).rstrip()

def classify(path, cfg):
    ext = os.path.splitext(path)[1].lower()
    if ext in cfg["stamp_ext"]: return "stamp"
    if ext in cfg["rename_ext"]: return "rename"
    return None

def gather_meta(path, cfg, cls, do_bump=False):
    stem, ext = os.path.splitext(os.path.basename(path))
    date = datetime.date.fromtimestamp(os.path.getmtime(path)).isoformat()
    if cls == "stamp":
        text = open(path, encoding="utf-8", errors="ignore").read()
        ex = read_colophon(text) or {}
        title = ex.get("title") or infer_title(text, stem, ext)
        meta = {"title": title, "kind": ex.get("kind") or infer_kind(stem, title, ext),
                "version": ex.get("version") or "v01", "date": ex.get("date") or date,
                "supersedes": ex.get("supersedes", ""), "related": ex.get("related", ""),
                "source": ex.get("source", ""), "status": ex.get("status", "draft")}
        if do_bump: meta["version"] = bump(meta["version"])
        return text, ext, meta
    # rename-only (binary): filename is the only signal
    meta = {"title": stem.replace("_", " ").replace("-", " ").strip(), "kind": infer_kind(stem, "", ext),
            "version": "v01", "date": date, "status": "kept"}
    return None, ext, meta

def compliant_name(meta, ext, cfg, seq=1):
    return FORMATS[cfg["format"]].format(topic=kebab(meta["title"]), kind=meta["kind"],
        date=meta["date"], version=meta["version"], seq=f"{seq:04d}", ext=ext)

def unique(meta, ext, cfg, taken, seq):
    m = dict(meta)
    while True:
        n = compliant_name(m, ext, cfg, seq)
        if n not in taken: return n, m["version"]
        m["version"] = bump(m["version"])

def iter_files(root, cfg):
    for dp, dn, fn in os.walk(root):
        dn[:] = [d for d in dn if d not in cfg["scratch_dirs"]]
        for f in fn:
            path = os.path.join(dp, f)
            cls = classify(path, cfg)
            if cls: yield path, cls

def plan_dir(root, cfg):
    """Return (renames, opaque). Each rename: (path, cls, cur, want, meta)."""
    renames, opaque, taken = [], [], set()
    for i, (path, cls) in enumerate(sorted(iter_files(root, cfg)), 1):
        stem = os.path.splitext(os.path.basename(path))[0]
        if cls == "rename" and is_opaque(stem):
            opaque.append(path); continue
        _, ext, meta = gather_meta(path, cfg, cls)
        want, ver = unique(meta, ext, cfg, taken, i); meta["version"] = ver
        taken.add(want)
        renames.append((path, cls, os.path.basename(path), want, meta))
    return renames, opaque

# ---- commands ----
def cmd_formats(a):
    print("Bookend naming formats (set with `bookend init --format NAME`):\n")
    for name, tmpl in FORMATS.items():
        eg = tmpl.format(topic="awaken-home", kind="deck", date="2026-07-09", version="v04", seq="0004", ext=".pptx")
        print(f"  {name:12} {tmpl}\n  {'':12} e.g.  {eg}\n")

def cmd_init(a):
    if a.format not in FORMATS: sys.exit(f"unknown format '{a.format}'. run `bookend formats`.")
    cfg = dict(DEFAULTS); cfg["format"] = a.format
    json.dump(cfg, open(CONFIG, "w"), indent=2)
    print(f"wrote {CONFIG} (format: {a.format}). run `bookend scan .`")

def cmd_scan(a):
    cfg = load_config(a.dir)
    renames, opaque = plan_dir(a.dir, cfg)
    need = [r for r in renames if r[2] != r[3]]
    print(f"BOOKEND SCAN · {a.dir} · format={cfg['format']}")
    print(f"{len(renames)} nameable files · {len(need)} would be renamed · {len(opaque)} skipped (no readable title)\n")
    for path, cls, cur, want, meta in need[:a.limit]:
        tag = "✎" if cls == "stamp" else "→"
        print(f"  {tag} {cur}\n      becomes: {want}")
    if len(need) > a.limit: print(f"  … +{len(need) - a.limit} more (use --limit 0 for all)")
    if opaque:
        print(f"\n  {len(opaque)} files have names Bookend can't turn into a title (IMG_4823, Screenshot…).")
        print(f"  It won't invent meaning it can't read. Examples:")
        for p in opaque[:5]: print(f"    · {os.path.basename(p)}")
    print(f"\nDRY RUN. nothing moved. to execute:  bookend apply {a.dir} --yes")

def cmd_apply(a):
    cfg = load_config(a.dir)
    renames, opaque = plan_dir(a.dir, cfg)
    moves = [r for r in renames if r[2] != r[3]]
    print(f"BOOKEND APPLY · {len(moves)} renames · {sum(1 for r in renames if r[1]=='stamp')} get a colophon · {len(opaque)} skipped")
    if not a.yes:
        print("refusing to move files without --yes. this renames files and stamps text ones.")
        return
    name_map = {cur: want for _, cls, cur, want, _ in moves}
    for path, cls, cur, want, meta in renames:
        newp = os.path.join(os.path.dirname(path), want)
        if cls == "stamp":
            text = strip_colophon(open(path, encoding="utf-8", errors="ignore").read())
            for o, n in name_map.items(): text = text.replace(o, n)
            text += "\n\n" + build_colophon(meta) + "\n"
            open(path, "w", encoding="utf-8").write(text)
        if cur != want:
            if os.path.exists(newp): print(f"  SKIP (exists): {want}"); continue
            os.rename(path, newp); print(f"  {'✎' if cls=='stamp' else '→'} {cur} → {want}")
    print("done. run `bookend index` to build the searchable INDEX.")

def parse_name(fname):
    """Best-effort metadata from a compliant filename when there's no colophon (binaries)."""
    stem = os.path.splitext(fname)[0]
    date = (re.search(r"\d{4}-\d{2}-\d{2}", stem) or [None])
    date = re.search(r"\d{4}-\d{2}-\d{2}", stem)
    ver = re.search(r"v\d{2,}", stem)
    parts = re.split(r"__|-", stem)
    topic = parts[0] if parts else stem
    return {"title": topic.replace("-", " "), "kind": "", "version": ver.group(0) if ver else "",
            "date": date.group(0) if date else "", "status": "kept", "supersedes": "", "related": ""}

def cmd_index(a):
    cfg = load_config(a.dir)
    rows, known = [], set()
    for path, cls in iter_files(a.dir, cfg):
        fname = os.path.basename(path); known.add(fname)
        if cls == "stamp":
            m = read_colophon(open(path, encoding="utf-8", errors="ignore").read()) or parse_name(fname)
        else:
            m = parse_name(fname)
        rows.append((m.get("date", ""), m.get("title", ""), m.get("kind", ""), m.get("version", ""),
                     m.get("status", ""), os.path.relpath(path, a.dir), m.get("supersedes", ""), m.get("related", "")))
    rows.sort(reverse=True)
    dead = []
    out = ["# INDEX", "", f"*{len(rows)} files · compiled by Bookend · newest first*", "",
           "| date | title | kind | ver | status | file |", "|---|---|---|---|---|---|"]
    for d, t, k, v, s, f, sup, rel in rows:
        out.append(f"| {d} | {t} | {k} | {v} | {s} | `{f}` |")
        for link in [x.strip() for x in (sup + "," + rel).split(",") if x.strip()]:
            if link.endswith((".html", ".md")) and os.path.basename(link) not in known:
                dead.append((f, link))
    if dead:
        out += ["", "## ⚠ broken lineage (the gate — fix these)", ""] + [f"- `{f}` → missing `{l}`" for f, l in dead]
    open(os.path.join(a.dir, "INDEX.md"), "w").write("\n".join(out) + "\n")
    print(f"wrote {os.path.join(a.dir, 'INDEX.md')} · {len(rows)} files · {len(dead)} broken lineage links")
    if dead: sys.exit(1)

def main():
    p = argparse.ArgumentParser(prog="bookend", description="a sortable name at the front, a colophon at the back")
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("formats").set_defaults(fn=cmd_formats)
    i = sub.add_parser("init"); i.add_argument("--format", default="topic-first"); i.set_defaults(fn=cmd_init)
    sc = sub.add_parser("scan"); sc.add_argument("dir", nargs="?", default="."); sc.add_argument("--limit", type=int, default=20); sc.set_defaults(fn=cmd_scan)
    ap = sub.add_parser("apply"); ap.add_argument("dir", nargs="?", default="."); ap.add_argument("--yes", action="store_true"); ap.set_defaults(fn=cmd_apply)
    ix = sub.add_parser("index"); ix.add_argument("dir", nargs="?", default="."); ix.set_defaults(fn=cmd_index)
    a = p.parse_args()
    if getattr(a, "limit", 1) == 0: a.limit = 10**9
    a.fn(a)

if __name__ == "__main__":
    main()
