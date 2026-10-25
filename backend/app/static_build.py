"""Build a single self-contained HTML replay of a match: the viewer, its scripts and the full timeline
(events, stats snapshots, moments and every overlay variant) inlined into one file.

Used for the hosted fallback page (/replay), for judges who want to test without a live server,
and for sharing a demo as one file.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from .pipeline import DEFAULT_SEED, build_timeline

ROOT = Path(__file__).resolve().parents[2]
FRONTEND = ROOT / "frontend"


def _between(text: str, start: str, end: str) -> str:
    return text.split(start, 1)[1].split(end, 1)[0]


def build_static_html(seed: int = DEFAULT_SEED, fragment: bool = False) -> str:
    """Return the replay page. `fragment=True` omits the doctype/html/head/body wrapper."""
    index = (FRONTEND / "index.html").read_text(encoding="utf-8")
    head = _between(index, "<!--HEAD-START-->", "<!--HEAD-END-->").strip()
    body = _between(index, "<!--BODY-START-->", "<!--BODY-END-->").strip()
    css = (FRONTEND / "styles.css").read_text(encoding="utf-8")
    pitch = (FRONTEND / "pitch.js").read_text(encoding="utf-8")
    viewer = (FRONTEND / "viewer.js").read_text(encoding="utf-8")
    tl = build_timeline(seed)
    tl.pop("audit", None)
    data = json.dumps(tl, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    body = re.sub(r'<a href="/producer"[^>]*>.*?</a>', "", body, flags=re.S)
    page = (f"{head}\n<style>\n{css}\n</style>\n{body}\n"
            f"<script>window.MIS_TIMELINE={data};</script>\n<script>\n{pitch}\n</script>\n<script>\n{viewer}\n</script>\n")
    if fragment:
        return page
    return ('<!doctype html>\n<html lang="en">\n<head>\n<meta charset="utf-8">\n'
            '<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">\n'
            f"{page.replace(body, '</head><body>' + body, 1)}</body>\n</html>\n")
