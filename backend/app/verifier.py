"""Verifier: a deterministic gate between the agents and the air.

An overlay passes only if every number it states and every player it names can be traced to the
moment's evidence (or the live match context), it stays within on-screen length limits, and it avoids
banned framing (betting language, real competition or club marks). Failures come back as specific,
machine-readable reasons so the Personalizer can repair its draft.
"""

from __future__ import annotations

import re

NUM_RE = re.compile(r"(?<![\w.])-?\d+(?:[.,]\d+)?")
HEADLINE_MAX = 72
BODY_MAX = 260

BANNED = [
    r"\bbet(s|ting)?\b", r"\bodds\b", r"\bwager", r"\bgambl", r"\bguarantee", r"\bpremier league\b",
    r"\barsenal\b", r"\bchelsea\b", r"\bliverpool\b", r"\bmanchester\b", r"\bman (utd|united|city)\b",
    r"\btottenham\b", r"\bnewcastle\b", r"\baston villa\b", r"\bwest ham\b", r"\beverton\b",
    r"\bbrighton\b", r"\bwolves\b", r"\bfulham\b", r"\bbrentford\b", r"\bcrystal palace\b",
    r"\bnottingham forest\b", r"\bbournemouth\b",
]


def _numbers_in(value, out: set[float]) -> None:
    if isinstance(value, bool) or value is None:
        return
    if isinstance(value, (int, float)):
        out.add(float(value))
    elif isinstance(value, str):
        for m in NUM_RE.findall(value):
            try:
                out.add(float(m.replace(",", ".")))
            except ValueError:
                pass
    elif isinstance(value, dict):
        for v in value.values():
            _numbers_in(v, out)
    elif isinstance(value, (list, tuple)):
        for v in value:
            _numbers_in(v, out)


def _strings_in(value, out: list[str]) -> None:
    if isinstance(value, str):
        out.append(value)
    elif isinstance(value, dict):
        for v in value.values():
            _strings_in(v, out)
    elif isinstance(value, (list, tuple)):
        for v in value:
            _strings_in(v, out)


def allowed_numbers(moment: dict) -> set[float]:
    nums: set[float] = set()
    _numbers_in(moment.get("evidence", {}), nums)
    _numbers_in(moment.get("context", {}).get("score", {}), nums)
    _numbers_in(moment.get("minute", ""), nums)
    _numbers_in(moment.get("clock", ""), nums)
    # Derived forms a writer may legitimately use: rounded values and ratios as percentages.
    derived = set()
    for v in nums:
        derived.add(round(v))
        derived.add(round(v, 1))
        derived.add(abs(v))
        if 0 < abs(v) <= 1:
            derived.add(round(v * 100))
    return nums | derived


def _number_ok(n: float, allowed: set[float]) -> bool:
    return any(abs(n - a) <= 0.051 for a in allowed)


def verify(overlay: dict, moment: dict, roster: dict[str, dict]) -> list[str]:
    """Return a list of problems. An empty list means the overlay may air."""
    errors: list[str] = []
    headline = (overlay.get("headline") or "").strip()
    body = (overlay.get("body") or "").strip()
    if not headline:
        errors.append("headline is empty")
    if not body:
        errors.append("body is empty")
    if len(headline) > HEADLINE_MAX:
        errors.append(f"headline too long ({len(headline)} > {HEADLINE_MAX} chars)")
    if len(body) > BODY_MAX:
        errors.append(f"body too long ({len(body)} > {BODY_MAX} chars)")
    text = f"{headline}\n{body}"

    allowed = allowed_numbers(moment)
    # "km/h", "xG" and similar units carry no digits; ordinals like 2nd are checked by their number.
    for raw in NUM_RE.findall(text):
        n = float(raw.replace(",", "."))
        if not _number_ok(n, allowed):
            errors.append(f"number {raw} is not supported by the evidence")

    evidence_text = []
    _strings_in(moment.get("evidence", {}), evidence_text)
    ev_blob = " ".join(evidence_text).lower()
    for p in roster.values():
        name, short = p["name"], p["short"]
        mentioned = name.lower() in text.lower() or re.search(rf"\b{re.escape(short)}\b", text, re.I)
        if mentioned and name.lower() not in ev_blob:
            errors.append(f"player {name} is not part of this moment")

    for pat in BANNED:
        if re.search(pat, text, re.I):
            errors.append(f"banned or out-of-scope term matched /{pat}/")
    return errors
