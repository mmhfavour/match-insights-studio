"""Live server: replays a synthetic match in real time and runs the full pipeline as events arrive.

Viewers (/ws/viewer) receive events, rolling stats and the overlays personalized for their profile.
Producers (/ws/producer) receive proposed overlays and approve, edit or reject them before they air.
"""

from __future__ import annotations

import asyncio
import logging
import os
import time
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from .agents import MatchAgents, profile_key
from .interpreter import Interpreter
from .pipeline import DEFAULT_SEED, Director, build_timeline, compact_event, overlay_record
from .simulator import generate_match
from .static_build import build_static_html

logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))
log = logging.getLogger("server")

ROOT = Path(__file__).resolve().parents[2]
FRONTEND = Path(os.getenv("FRONTEND_DIR", ROOT / "frontend"))


def _now() -> float:
    return time.time()


class MatchSession:
    def __init__(self, seed: int = DEFAULT_SEED, script: str = "default"):
        self.seed, self.script = seed, script
        data = generate_match(seed, script)
        self.match, self.events = data["match"], data["events"]
        roster = {p["id"]: p for side in ("home", "away") for p in self.match[side]["players"] + self.match[side]["bench"]}
        names = {self.match[s]["code"]: self.match[s]["name"] for s in ("home", "away")}
        self.agents = MatchAgents(roster, names)
        self.director = Director()
        self.speed = float(os.getenv("REPLAY_SPEED", "30"))
        self.auto = os.getenv("AUTO_APPROVE", "1") == "1"
        self.auto_delay = float(os.getenv("AUTO_APPROVE_DELAY_S", "5"))
        self.loop_replay = os.getenv("LOOP_REPLAY", "1") == "1"
        self.viewers: dict[WebSocket, dict] = {}
        self.producers: set[WebSocket] = set()
        self.task: asyncio.Task | None = None
        self.resume = asyncio.Event()
        self.resume.set()
        self.reset()

    # ------------------------------------------------------------------ lifecycle
    def reset(self) -> None:
        self.interp = Interpreter(self.match)
        self.idx = 0
        self.state = "ready"
        self.proposals: dict[str, dict] = {}
        self.aired: list[dict] = []
        self.audit: list[dict] = []
        self.counts = {"proposed": 0, "approved": 0, "auto_approved": 0, "rejected": 0, "edited": 0,
                       "aired": 0, "dropped": 0}
        self.draft_latency: list[int] = []
        self.last_snapshot: dict | None = None
        self.recent_events: list[dict] = []

    def start(self) -> None:
        if self.task and not self.task.done():
            self.resume.set()
            return
        self.task = asyncio.create_task(self._run())

    async def restart(self) -> None:
        if self.task and not self.task.done():
            self.task.cancel()
        self.reset()
        await self.broadcast_all({"type": "reset", "match": self.match})
        self.start()

    def set_speed(self, speed: float) -> None:
        self.speed = max(1.0, min(240.0, speed))
        self._rebase = True

    async def _run(self) -> None:
        loop = asyncio.get_running_loop()
        while True:
            self.state = "live"
            await self.broadcast_all({"type": "state", "state": self.state, "speed": self.speed})
            base_real, base_t = loop.time(), self.events[self.idx]["t"] if self.idx < len(self.events) else 0
            self._rebase = False
            next_snap = 0.0
            while self.idx < len(self.events):
                if not self.resume.is_set():
                    self.state = "paused"
                    await self.broadcast_all({"type": "state", "state": self.state, "speed": self.speed})
                    await self.resume.wait()
                    self.state = "live"
                    await self.broadcast_all({"type": "state", "state": self.state, "speed": self.speed})
                    self._rebase = True
                ev = self.events[self.idx]
                if self._rebase:
                    base_real, base_t, self._rebase = loop.time(), ev["t"], False
                delay = base_real + (ev["t"] - base_t) / self.speed - loop.time()
                if delay > 0:
                    await asyncio.sleep(delay)
                new_moments = self.interp.ingest(ev)
                self.idx += 1
                if ev["type"] != "physical":
                    ce = compact_event(ev)
                    self.recent_events = (self.recent_events + [ce])[-40:]
                    await self.broadcast_viewers({"type": "event", "event": ce})
                if ev["t"] >= next_snap or ev["type"] in ("goal", "period_end", "match_end", "substitution"):
                    self.last_snapshot = self.interp.snapshot()
                    next_snap = ev["t"] + 15
                    await self.broadcast_all({"type": "stats", "stats": self.last_snapshot})
                for m in new_moments:
                    await self.propose(m)
            self.state = "finished"
            await self.broadcast_all({"type": "state", "state": self.state, "speed": self.speed})
            if not self.loop_replay:
                return
            await asyncio.sleep(25)
            self.reset()
            await self.broadcast_all({"type": "reset", "match": self.match})

    # ------------------------------------------------------------------ producer workflow
    def _audit(self, moment: dict, action: str, by: str, **extra) -> dict:
        entry = {"at": round(_now(), 3), "clock": moment["clock"], "minute": moment["minute"],
                 "moment_id": moment["id"], "type": moment["type"], "action": action, "by": by, **extra}
        self.audit.append(entry)
        return entry

    async def propose(self, moment: dict) -> None:
        review = self.director.review(moment)
        if review["decision"] != "propose":
            self.counts["dropped"] += 1
            self._audit(moment, "dropped", "director", reason=review["reason"])
            return
        moment = {**moment, "audiences": review["audiences"]}
        draft = await self.agents.overlay(moment, {"mode": "analyst", "lang": "en"})
        self.draft_latency.append(draft.get("latency_ms", 0))
        prop = {"moment": moment, "draft": draft, "status": "pending", "created_at": _now(),
                "auto_at": _now() + self.auto_delay if self.auto else None}
        self.proposals[moment["id"]] = prop
        self.counts["proposed"] += 1
        entry = self._audit(moment, "proposed", "director", headline=draft["headline"], source=draft["source"],
                            verifier=draft.get("verifier", []))
        await self.broadcast_producers({"type": "proposal", "proposal": self._public(prop), "audit": entry,
                                        "metrics": self.metrics()})
        if self.auto:
            asyncio.create_task(self._auto_approve(moment["id"], self.auto_delay))

    async def _auto_approve(self, moment_id: str, delay: float) -> None:
        await asyncio.sleep(delay)
        prop = self.proposals.get(moment_id)
        if prop and prop["status"] == "pending" and self.auto:
            await self.decide(moment_id, "approve", by="auto-approve")

    async def decide(self, moment_id: str, action: str, by: str = "producer", headline: str | None = None,
                     body: str | None = None) -> None:
        prop = self.proposals.get(moment_id)
        if not prop or prop["status"] != "pending":
            return
        moment = prop["moment"]
        if action == "reject":
            prop["status"] = "rejected"
            self.counts["rejected"] += 1
            entry = self._audit(moment, "rejected", by)
        else:
            edit = None
            if action == "edit" and (headline or body):
                edit = {"headline": headline or prop["draft"]["headline"], "body": body or prop["draft"]["body"],
                        "source": "producer", "verifier": []}
                self.counts["edited"] += 1
            prop["status"] = "approved"
            self.counts["auto_approved" if by == "auto-approve" else "approved"] += 1
            entry = self._audit(moment, "edited" if edit else "approved", by,
                                headline=(edit or prop["draft"])["headline"])
            await self.air(moment, edit)
        await self.broadcast_producers({"type": "decision", "moment_id": moment_id, "status": prop["status"],
                                        "audit": entry, "metrics": self.metrics()})

    def _wants(self, profile: dict, moment: dict) -> bool:
        mode = profile.get("mode", "analyst")
        if mode not in moment["audiences"]:
            return False
        if mode == "player":
            focus = profile.get("player")
            return moment["type"] in ("goal", "half_time", "full_time") or (focus in moment["players"])
        return True

    async def air(self, moment: dict, edit: dict | None = None) -> None:
        self.aired.append(moment)
        self.counts["aired"] += 1
        groups: dict[str, list[WebSocket]] = {}
        profiles: dict[str, dict] = {}
        for ws, prof in list(self.viewers.items()):
            if self._wants(prof, moment):
                k = profile_key(prof)
                groups.setdefault(k, []).append(ws)
                profiles[k] = prof

        async def send_group(k: str) -> None:
            prof = profiles[k]
            if edit and prof.get("mode", "analyst") == "analyst" and prof.get("lang", "en") == "en":
                copy = edit
            else:
                copy = await self.agents.overlay(moment, prof)
            rec = overlay_record(moment, copy, moment["audiences"], k)
            await asyncio.gather(*(self._send(ws, {"type": "overlay", "overlay": rec}) for ws in groups[k]))

        await asyncio.gather(*(send_group(k) for k in groups))
        self._audit(moment, "aired", "system", audiences=moment["audiences"], profiles=len(groups))

    def _public(self, prop: dict) -> dict:
        m = prop["moment"]
        return {"moment": {k: m[k] for k in ("id", "type", "clock", "minute", "team", "team_name", "players",
                                             "importance", "slot", "evidence", "context", "audiences")},
                "draft": prop["draft"], "status": prop["status"], "auto_at": prop["auto_at"]}

    def metrics(self) -> dict:
        lat = self.draft_latency
        return {**self.counts, "agents": self.agents.mode, **self.agents.metrics,
                "avg_draft_latency_ms": round(sum(lat) / len(lat)) if lat else 0,
                "auto": self.auto, "auto_delay_s": self.auto_delay, "speed": self.speed, "state": self.state}

    # ------------------------------------------------------------------ sockets
    async def _send(self, ws: WebSocket, msg: dict) -> None:
        try:
            await ws.send_json(msg)
        except Exception:
            self.viewers.pop(ws, None)
            self.producers.discard(ws)

    async def broadcast_viewers(self, msg: dict) -> None:
        await asyncio.gather(*(self._send(ws, msg) for ws in list(self.viewers)))

    async def broadcast_producers(self, msg: dict) -> None:
        await asyncio.gather(*(self._send(ws, msg) for ws in list(self.producers)))

    async def broadcast_all(self, msg: dict) -> None:
        await asyncio.gather(self.broadcast_viewers(msg), self.broadcast_producers(msg))

    async def replay_last(self, ws: WebSocket) -> None:
        """After a profile change, re-render the latest aired moment so the switch is visible at once."""
        prof = self.viewers.get(ws)
        if not prof:
            return
        for m in reversed(self.aired[-6:]):
            if self._wants(prof, m):
                copy = await self.agents.overlay(m, prof)
                rec = overlay_record(m, copy, m["audiences"], profile_key(prof))
                await self._send(ws, {"type": "overlay", "overlay": {**rec, "replay": True}})
                return


session: MatchSession | None = None


@asynccontextmanager
async def lifespan(_app: FastAPI):
    global session
    session = MatchSession(int(os.getenv("MATCH_SEED", DEFAULT_SEED)), os.getenv("MATCH_SCRIPT", "default"))
    log.info("Match ready: %s events, agents=%s", len(session.events), session.agents.mode)
    if os.getenv("AUTOSTART", "1") == "1":
        session.start()
    yield
    if session.task:
        session.task.cancel()


app = FastAPI(title="Match Insights Studio", version="0.1.0", lifespan=lifespan)


class Control(BaseModel):
    action: str
    speed: float | None = None


@app.get("/api/health")
async def health() -> dict:
    return {"ok": True, "agents": session.agents.mode, "state": session.state, "speed": session.speed}


@app.get("/api/match")
async def match_info() -> dict:
    return {"match": session.match, "state": session.state, "speed": session.speed,
            "snapshot": session.last_snapshot, "metrics": session.metrics()}


@app.get("/api/overlays")
async def overlays(mode: str = "analyst", lang: str = "en", club: str | None = None, player: str | None = None) -> dict:
    """Machine-readable, clock-synced overlay feed for one profile (everything aired so far)."""
    prof = {"mode": mode, "lang": lang, "club": club, "player": player}
    out = []
    for m in session.aired:
        if session._wants(prof, m):
            copy = await session.agents.overlay(m, prof)
            out.append(overlay_record(m, copy, m["audiences"], profile_key(prof)))
    return {"profile": prof, "overlays": out}


@app.get("/api/audit")
async def audit() -> dict:
    return {"audit": session.audit[-500:], "metrics": session.metrics()}


@app.get("/api/timeline")
async def timeline(seed: int = DEFAULT_SEED) -> JSONResponse:
    return JSONResponse(build_timeline(seed))


@app.post("/api/control")
async def control(c: Control) -> dict:
    await _control(c.action, c.speed)
    return {"state": session.state, "speed": session.speed}


async def _control(action: str, speed: float | None = None) -> None:
    if action == "start":
        session.start()
    elif action == "pause":
        session.resume.clear()
    elif action == "resume":
        session.resume.set()
    elif action == "restart":
        await session.restart()
    elif action == "speed" and speed:
        session.set_speed(speed)
        await session.broadcast_all({"type": "state", "state": session.state, "speed": session.speed})


@app.websocket("/ws/viewer")
async def ws_viewer(ws: WebSocket) -> None:
    await ws.accept()
    session.viewers[ws] = {"mode": "analyst", "lang": "en", "club": None, "player": None}
    await ws.send_json({"type": "hello", "match": session.match, "state": session.state, "speed": session.speed,
                        "snapshot": session.last_snapshot, "recent_events": session.recent_events,
                        "agents": session.agents.mode})
    if session.state == "ready":
        session.start()
    try:
        while True:
            msg = await ws.receive_json()
            if msg.get("type") == "profile":
                p = msg.get("profile", {})
                session.viewers[ws] = {"mode": p.get("mode", "analyst"), "lang": p.get("lang", "en"),
                                       "club": p.get("club") or None, "player": p.get("player") or None}
                await session.replay_last(ws)
    except WebSocketDisconnect:
        pass
    finally:
        session.viewers.pop(ws, None)


@app.websocket("/ws/producer")
async def ws_producer(ws: WebSocket) -> None:
    await ws.accept()
    session.producers.add(ws)
    await ws.send_json({"type": "hello", "match": session.match, "state": session.state, "speed": session.speed,
                        "proposals": [session._public(p) for p in list(session.proposals.values())[-30:]],
                        "audit": session.audit[-80:], "metrics": session.metrics(), "snapshot": session.last_snapshot})
    try:
        while True:
            msg = await ws.receive_json()
            t = msg.get("type")
            if t == "decision":
                await session.decide(msg["moment_id"], msg.get("action", "approve"), "producer",
                                     msg.get("headline"), msg.get("body"))
            elif t == "control":
                await _control(msg.get("action", ""), msg.get("speed"))
            elif t == "auto":
                session.auto = bool(msg.get("enabled", True))
                if msg.get("delay"):
                    session.auto_delay = float(msg["delay"])
                if session.auto:
                    for mid, p in session.proposals.items():
                        if p["status"] == "pending":
                            asyncio.create_task(session._auto_approve(mid, session.auto_delay))
                await session.broadcast_producers({"type": "metrics", "metrics": session.metrics()})
    except WebSocketDisconnect:
        pass
    finally:
        session.producers.discard(ws)


@app.get("/")
async def index() -> FileResponse:
    return FileResponse(FRONTEND / "index.html")


_replay_cache: dict[int, str] = {}


@app.get("/replay", response_class=HTMLResponse)
async def replay(seed: int = DEFAULT_SEED) -> HTMLResponse:
    """Self-contained replay with every overlay variant pre-rendered. Works without the live socket."""
    if seed not in _replay_cache:
        _replay_cache[seed] = build_static_html(seed)
    return HTMLResponse(_replay_cache[seed])


@app.get("/producer")
async def producer() -> FileResponse:
    return FileResponse(FRONTEND / "producer.html")


if FRONTEND.exists():
    app.mount("/static", StaticFiles(directory=FRONTEND), name="static")
