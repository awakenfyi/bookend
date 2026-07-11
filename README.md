# Bookend

**A sortable name at the front. A colophon at the back. Zero dependencies. One file.**

Your AI generates a beautiful HTML page. You save it. Two minutes later it generates a better
one. You save that too. Now you have `index.html`, `index (1).html`, `Untitled-final.html`,
`Untitled-final-FINAL.html`, `Untitled-final-FINAL-actually.html`, and `tca-home (3) copy 2.html`.

You have no idea which is newest. You have no idea what any of them came from. You open three of
them to find out. Two are identical. One is from a different project. It is 11pm.

**Bookend fixes this.** It gives every file a name that sorts itself and a memory that survives
you closing the tab.

```
before:  Untitled-final-FINAL.html          tca-home (3).html          notes copy 2.md
after:   awaken-home__page__2026-07-09__v01.html                       the-imagery-system__note__2026-07-09__v01.md
                └topic┘ └kind┘  └─date─┘ └ver┘
```

Now `ls` alone sorts your files by topic, then date, then version. And every file ends with a
**colophon** — the little note at the back of a book that says what it is, when, and what it came
from:

```html
<!-- colophon
title: awaken.fyi homepage
kind: site-page
version: v04
date: 2026-07-09
supersedes: awaken-home__site-page__2026-07-08__v03.html
related: imagery-system__spec__2026-07-07__v01.md
source: session 0e9c5a1a
status: ship-ready
-->
```

Every file points home. Your folder quietly becomes a second brain.

## Try it in 60 seconds

```bash
git clone https://github.com/awakenfyi/bookend && cd bookend
python3 bookend.py formats                    # pick how you want files named
python3 bookend.py init --format topic-first  # writes .bookend.json
python3 bookend.py scan ~/Downloads           # DRY RUN — see the plan, move nothing
```

`scan` never touches a file. It shows you exactly what *would* happen. When you're ready:

```bash
python3 bookend.py apply ~/Downloads --yes     # renames + stamps + rewrites internal links
python3 bookend.py index ~/Downloads           # builds a searchable INDEX.md
```

## The five formats (you choose)

| format | example | good for |
|---|---|---|
| `topic-first` | `awaken-home__page__2026-07-09__v04.html` | grouping everything about one thing |
| `date-first`  | `2026-07-09__awaken-home__page__v04.html` | "what did I make recently" |
| `flat-slug`   | `awaken-home-page-2026-07-09-v04.html`    | people who hate double underscores |
| `numbered`    | `0004__awaken-home__page.html`            | lab-notebook / sequential brains |
| `minimal`     | `awaken-home__2026-07-09.html`            | just the subject and the day |

Don't like any of them? `.bookend.json` is three lines; change the template.

## The three promises

1. **`scan` is always a dry run.** Bookend never moves a file you didn't see coming.
2. **It never overwrites.** Two files with the same name become a version series (`v01`, `v02`),
   not a casualty.
3. **It never lies about lineage.** If a file's colophon says it `supersedes` another file, and
   that file doesn't exist, `index` fails loudly. An empty lineage is honest. A fake one is the
   one thing Bookend won't tolerate.

## What it won't touch

Anything in a `scratch/`, `tmp/`, or `_wip/` folder. The path is the disclaimer — doodles get to
stay doodles. (Edit the list in `.bookend.json`.)

## Works on

`.html` and `.md`. Both accept the same HTML-comment colophon, so one tool covers your pages and
your notes. Add extensions in the config.

---

*Bookend is an [xOP](https://github.com/awakenfyi/xop) — a small rule an AI (or a human) can be
held to. The rule: every durable file carries its name and its memory. The gate: never fake the
memory. Built by [awaken.fyi](https://awaken.fyi). No tracking, no dependencies, no telemetry —
it's one Python file, go read it.*
