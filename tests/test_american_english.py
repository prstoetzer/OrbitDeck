"""OrbitDeck uses American English throughout.

A guard rather than a one-off cleanup: spellings drift back in one comment at a
time, and identifiers are the part that actually breaks things later (a public
`analyse_rate` beside an American codebase is a permanent papercut).
"""

import pathlib
import re

BRITISH = [
    "colour", "centre", "behaviour", "normalis", "recognis", "initialis",
    "analyse", "metre", "labelled", "labelling", "cancelled", "modelled",
    "travelled", "neighbour", "grey", "catalogue", "organis", "summaris",
    "optimis", "visualis", "whilst", "judgement", "acknowledgement",
    "kilometre", "manoeuvre", "favourite", "defence", "licence", "fibre",
    "litre", "aluminium", "theatre", "sceptical", "apologis", "utilis",
    "maximis", "minimis", "specialis", "standardis", "prioritis",
]

SUFFIXES = ("*.py", "*.md", "*.toml", "*.yml", "*.xml", "*.bas", "*.desktop")

# Third-party code and build output are not ours to respell. This file is
# skipped too: its own word list would otherwise match itself.
SKIP = ("/.git/", "dist/", "build/", "egg-info", "/_internal/",
        "third_party/", "test_american_english.py",
        # A changelog and a port log have to NAME the old spellings to record
        # what changed; the point is the code, not the history of the code.
        "CHANGELOG.md", "docs/CARDSAT_PORT.md")


def _sources():
    root = pathlib.Path(__file__).resolve().parent.parent
    for pattern in SUFFIXES:
        for path in root.rglob(pattern):
            rel = str(path.relative_to(root))
            if any(s in rel or rel.startswith(s) for s in SKIP):
                continue
            yield rel, path


def test_no_british_spellings_anywhere():
    hits = []
    for rel, path in _sources():
        try:
            text = path.read_text()
        except Exception:
            continue
        for word in BRITISH:
            for m in re.finditer(word, text, re.I):
                line = text.count("\n", 0, m.start()) + 1
                hits.append("%s:%d %s" % (rel, line, m.group(0)))
    assert not hits, hits[:12]


def test_renamed_identifiers_are_american():
    """The rename touched public names, so pin them."""
    from orbitdeck.engine import spacetrack as ST
    assert hasattr(ST, "analyze_rate")
    assert not hasattr(ST, "analyse_rate")
    from orbitdeck.engine import thermal
    assert hasattr(thermal, "CP_ALUMINUM")
    import inspect
    from orbitterm import canvas
    assert "color" in inspect.signature(canvas.Canvas.plot).parameters
