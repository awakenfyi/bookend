#!/usr/bin/env python3
"""End-to-end smoke test. Exits non-zero on any failure. No deps."""
import os, subprocess, tempfile, sys, shutil

B = [sys.executable, os.path.join(os.path.dirname(__file__), "bookend.py")]
def run(*a, **k): return subprocess.run(B + list(a), capture_output=True, text=True, **k)

d = tempfile.mkdtemp()
try:
    os.makedirs(os.path.join(d, "scratch"))
    open(os.path.join(d, "tca-home (3).html"), "w").write("<title>Awaken Homepage</title>")
    open(os.path.join(d, "Untitled-FINAL.html"), "w").write("<title>Awaken Homepage</title>")
    open(os.path.join(d, "notes copy 2.md"), "w").write("# The Imagery System")
    open(os.path.join(d, "scratch", "doodle.html"), "w").write("junk")

    assert "topic-first" in run("formats").stdout, "formats failed"
    assert "DRY RUN" in run("scan", d).stdout, "scan should be a dry run"
    # scan must not move anything
    assert os.path.exists(os.path.join(d, "tca-home (3).html")), "scan moved a file!"
    assert run("apply", d, "--yes").returncode == 0, "apply failed"
    files = sorted(os.listdir(d))
    assert "awaken-homepage__page__2026-" in " ".join(f for f in files if f.endswith(".html")), files
    # collision became a version series
    htmls = [f for f in files if f.endswith(".html")]
    assert any("v01" in f for f in htmls) and any("v02" in f for f in htmls), f"no version series: {htmls}"
    # scratch untouched
    assert os.listdir(os.path.join(d, "scratch")) == ["doodle.html"], "scratch was touched!"
    assert run("index", d).returncode == 0, "index failed on clean lineage"

    # the gate: a fabricated supersedes must make index fail.
    # constructed directly (no round-trip through apply) so the test is deterministic across OSes.
    open(os.path.join(d, "gate__note__2026-01-01__v01.md"), "w").write(
        "# Gate\n\n<!-- colophon\ntitle: Gate\nkind: note\nversion: v01\n"
        "date: 2026-01-01\nsupersedes: ghost__doc__2000-01-01__v01.md\n"
        "related: \nsource: \nstatus: draft\n-->\n")
    r = run("index", d)
    assert r.returncode != 0, f"index should FAIL on fabricated lineage (the gate). got rc=0; stdout={r.stdout!r}"
    print("PASS — formats, dry-run scan, apply, version-series collision, scratch-skip, index, and the lineage gate all hold.")
finally:
    shutil.rmtree(d)
