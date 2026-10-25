"""Glue for the five stages: ingest -> interpret -> explain -> render -> personalize.

`Director` decides which moments are worth proposing and to which audiences.
`overlay_record` is the machine-readable, clock-synced overlay format the renderer consumes.
`build_timeline` runs a whole match offline (template copy for every profile) and is used for the
static demo build, tests and as a deterministic replay for the video.
"""

from __future__ import annotations

from .interpreter import Interpreter
from .simulator import generate_match
from .templates import LANGS, render
from .verifier import verify

DEFAULT_SEED = 21

ALWAYS_CASUAL = {"goal", "half_time", "full_time", "big_chance", "top_speed", "card"}
EVENT_FIELDS = ("id", "t", "clock", "minute", "period", "type", "team", "player", "x", "y", "end_x", "end_y")
EVENT_DATA_FIELDS = ("outcome", "xg", "speed_kmh", "score", "top_speed_kmh", "recipient", "pass_type",
                     "card", "player_off", "player_on")


class Director:
    """Decides what is worth putting to air, and for whom."""

    def __init__(self, min_importance: float = 0.35, casual_min: float = 0.55):
        self.min_importance = min_importance
        self.casual_min = casual_min

    def review(self, moment: dict) -> dict:
        if moment["importance"] < self.min_importance:
            return {"decision": "drop", "reason": "below importance threshold", "audiences": []}
        audiences = ["analyst"]
        if moment["importance"] >= self.casual_min or moment["type"] in ALWAYS_CASUAL:
            audiences.append("casual")
        if moment["players"] or moment["type"] in ("goal", "half_time", "full_time"):
            audiences.append("player")
        return {"decision": "propose", "reason": f"importance {moment['importance']}", "audiences": audiences}


def compact_event(ev: dict) -> dict:
    out = {k: ev[k] for k in EVENT_FIELDS if k in ev and ev[k] is not None}
    d = ev.get("data") or {}
    small = {k: d[k] for k in EVENT_DATA_FIELDS if k in d and d[k] is not None}
    if small:
        out["d"] = small
    return out


def overlay_record(moment: dict, copy: dict, audiences: list[str], profile_key: str) -> dict:
    """The overlay contract a renderer (or a broadcast graphics partner) consumes."""
    e = moment["evidence"]
    graphic = {k: e[k] for k in e if isinstance(e[k], (int, float)) and not isinstance(e[k], bool)}
    return {
        "id": f"{moment['id']}|{profile_key}",
        "moment_id": moment["id"],
        "type": moment["type"],
        "slot": moment["slot"],
        "t_in": moment["t"],
        "duration_s": moment["duration_s"],
        "clock": moment["clock"],
        "minute": moment["minute"],
        "priority": moment["importance"],
        "team": moment["team"],
        "players": moment["players"],
        "audiences": audiences,
        "profile": profile_key,
        "headline": copy["headline"],
        "body": copy["body"],
        "source": copy.get("source", "template"),
        "verifier": copy.get("verifier", []),
        "graphic": graphic,
        "evidence": e,
        "context": moment.get("context", {}),
        "analysis": moment.get("analysis"),
        "why": copy.get("why"),
        "latency_ms": copy.get("latency_ms"),
    }


def static_key(mode: str, lang: str, club: str | None) -> str:
    """Variant key used by the static build: club only changes the casual copy."""
    return f"{mode}|{lang}|{club if (mode == 'casual' and club) else '-'}"


def build_timeline(seed: int = DEFAULT_SEED, script: str = "default", snapshot_every: float = 60.0) -> dict:
    data = generate_match(seed, script)
    match, events = data["match"], data["events"]
    interp = Interpreter(match)
    director = Director()
    roster = interp.players
    clubs = [match["home"]["code"], match["away"]["code"]]
    names = {match["home"]["code"]: match["home"]["name"], match["away"]["code"]: match["away"]["name"]}

    snapshots, moments, overlays, audit = [], [], {}, []
    next_snap = 0.0
    verifier_failures = 0
    for ev in events:
        new = interp.ingest(ev)
        if ev["t"] >= next_snap or ev["type"] in ("goal", "period_end", "match_end"):
            snap = interp.snapshot()
            snap.pop("series", None)
            snap.pop("chances", None)
            snapshots.append(snap)
            next_snap = ev["t"] + snapshot_every
        for m in new:
            review = director.review(m)
            audit.append({"moment_id": m["id"], "clock": m["clock"], "type": m["type"],
                          "action": "auto-approved" if review["decision"] == "propose" else "dropped",
                          "by": "director", "reason": review["reason"]})
            if review["decision"] != "propose":
                continue
            m = {**m, "audiences": review["audiences"]}
            moments.append(m)
            variants = {}
            for lang in LANGS:
                variants[static_key("analyst", lang, None)] = render(m, "analyst", lang)
                for club in [None] + clubs:
                    variants[static_key("casual", lang, club)] = render(m, "casual", lang, club, names.get(club))
            for key, copy in variants.items():
                if verify(copy, m, roster):
                    verifier_failures += 1
            overlays[m["id"]] = variants

    final = interp.snapshot()
    return {
        "match": match,
        "events": [compact_event(e) for e in events if e["type"] != "physical"],
        "snapshots": snapshots,
        "series": interp.series,
        "chances": interp.chances,
        "moments": moments,
        "overlays": overlays,
        "audit": audit,
        "final": final,
        "stats": {"events": len(events), "moments": len(moments), "template_verifier_failures": verifier_failures},
    }
