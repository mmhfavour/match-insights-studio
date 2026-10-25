"""Build-up analysis: how a chance was created, not just who made the last pass.

For a shot, walk back through the event stream to where the move started (a regain, a corner, a free
kick, a kick-off, the goalkeeper) and read the patterns of play that produced it: counterattacks,
high regains, short passing sequences, set pieces, entries into the penalty area, attacks through the
half-spaces, third-man runs, one-twos, switches of play, line-breaking passes, second balls and
rebounds, numerical overloads around the ball, and how much time the finisher had.

Everything is deterministic and derived from events. Coordinates in the output are in the attacking
team's frame (attacking towards x=105). Player positions for the freeze frame are estimated with the
same positional model the simulator uses, with the real event locations of the players on the ball.
"""

from __future__ import annotations

import math

from .templates import LANGS, render_buildup

L, W = 105.0, 68.0
BOX_X, BOX_Y0, BOX_Y1 = 88.5, 13.84, 54.16
HALF_SPACES = ((13.84, 24.84), (43.16, 54.16))
FINAL_THIRD_X = 70.0
MOVE_TYPES = ("pass", "carry", "dribble", "shot")
REGAIN_TYPES = ("tackle", "interception", "ball_recovery")
MAX_STEPS = 14
OVERLOAD_RADIUS = 16.0


def in_box(x: float, y: float) -> bool:
    return x >= BOX_X and BOX_Y0 <= y <= BOX_Y1


def lane(y: float) -> str:
    """Vertical lane in the attacking frame. y < 34 is the attacking team's left."""
    side = "left" if y < 34 else "right"
    for lo, hi in HALF_SPACES:
        if lo <= y <= hi:
            return f"{side}_half_space"
    if y < BOX_Y0 or y > BOX_Y1:
        return f"{side}_wing"
    return "centre"


class BuildUp:
    def __init__(self, interp):
        self.i = interp

    # ------------------------------------------------------------------ frames
    def _frame(self, team: str, period: int):
        right = (team == self.i.home) == (period == 1)

        def fa(x: float, y: float) -> tuple[float, float]:
            return (x, y) if right else (L - x, W - y)
        return fa

    def _start(self, e: dict, fa) -> tuple[float, float] | None:
        return fa(e["x"], e["y"]) if "x" in e else None

    def _end(self, e: dict, fa) -> tuple[float, float] | None:
        if "end_x" in e:
            return fa(e["end_x"], e["end_y"])
        return self._start(e, fa)

    # ------------------------------------------------------------------ chain
    def _chain(self, shot_idx: int) -> tuple[list[dict], dict | None, int]:
        """Events of the move that ended in the shot, oldest first, plus the restart that began it."""
        evs = self.i.events
        shot = evs[shot_idx]
        team, pid = shot["team"], shot["possession_id"]
        chain: list[dict] = []
        restart = None
        j = shot_idx
        while j >= 0:
            e = evs[j]
            if e["type"] == "physical":
                j -= 1
                continue
            if e.get("possession_id") != pid:
                break
            if j != shot_idx and e["type"] in ("corner", "kickoff"):
                restart = e
                break
            if j != shot_idx and e["type"] == "foul" and e.get("team") != team:
                restart = e
                break
            if j != shot_idx and e["type"] in ("shot", "card", "substitution"):
                break
            chain.append(e)
            j -= 1
        chain.reverse()
        return chain, restart, j

    def _origin(self, team: str, chain: list[dict], restart: dict | None, before_idx: int, fa) -> dict:
        first = next((e for e in chain if e["type"] in MOVE_TYPES and e.get("team") == team), chain[0])
        if restart is not None:
            kind = {"corner": "corner", "kickoff": "kickoff"}.get(restart["type"], "free_kick")
            xy = self._start(restart, fa) if restart["type"] != "foul" else self._start(first, fa)
            return {"type": kind, "player": restart.get("player") if kind != "free_kick" else first.get("player"),
                    "x": xy[0] if xy else None, "y": xy[1] if xy else None, "t": restart["t"]}
        # A regain: the defensive action that handed this team the ball just before the move.
        evs = self.i.events
        j = before_idx
        while j >= 0 and evs[j]["t"] >= first["t"] - 4:
            e = evs[j]
            if e["type"] in REGAIN_TYPES and e.get("team") == team and "x" in e:
                x, y = fa(e["x"], e["y"])
                return {"type": "regain", "how": "counterpress" if (e.get("data") or {}).get("counterpress") else e["type"],
                        "player": e.get("player"), "x": x, "y": y, "t": e["t"]}
            j -= 1
        p = self.i.players.get(first.get("player") or "", {})
        xy = self._start(first, fa)
        kind = "goalkeeper" if p.get("role") == "GK" else "open_play"
        return {"type": kind, "player": first.get("player"), "x": xy[0] if xy else None,
                "y": xy[1] if xy else None, "t": first["t"]}

    # ------------------------------------------------------------------ positions
    def _positions(self, team: str, ball: tuple[float, float], actors: dict[str, tuple[float, float]]) -> list[list]:
        """Estimated positions of every player on the pitch, in the attacking team's frame."""
        opp = self.i.opp(team)
        out = []
        for side, in_poss in ((team, True), (opp, False)):
            bx, by = ball if in_poss else (L - ball[0], W - ball[1])
            for pid in sorted(self.i.on_pitch):
                info = self.i.shape.get(pid)
                if not info or info["team"] != side:
                    continue
                if pid in actors:
                    x, y = actors[pid]
                else:
                    if info["role"] == "GK":
                        px, py = 5 + max(0, bx - 52.5) * 0.12, 34 + (by - 34) * 0.1
                    else:
                        px = info["base_x"] + (6 if in_poss else -4) + (bx - 52.5) * (0.5 if in_poss else 0.45)
                        py = info["base_y"] + (by - 34) * 0.22
                    px, py = min(97, max(2, px)), min(66, max(2, py))
                    x, y = (px, py) if in_poss else (L - px, W - py)
                out.append([pid, round(x, 1), round(y, 1), 1 if side == team else 0])
        return out

    def _count(self, players: list[list], centre: tuple[float, float], radius: float) -> tuple[int, int]:
        att = sum(1 for _, x, y, a in players if a and math.hypot(x - centre[0], y - centre[1]) <= radius)
        dfn = sum(1 for _, x, y, a in players if not a and math.hypot(x - centre[0], y - centre[1]) <= radius)
        return att, dfn

    # ------------------------------------------------------------------ analysis
    def analyze(self, shot_idx: int) -> dict:
        i = self.i
        evs = i.events
        shot = evs[shot_idx]
        team = shot["team"]
        fa = self._frame(team, shot["period"])
        chain, restart, before_idx = self._chain(shot_idx)
        origin = self._origin(team, chain, restart, before_idx, fa)

        moves = [e for e in chain if e["type"] in MOVE_TYPES and e.get("team") == team]
        passes = [e for e in moves if e["type"] == "pass" and (e.get("data") or {}).get("outcome") == "complete"]
        first = moves[0] if moves else shot
        began = min(first["t"], origin["t"]) if origin["type"] == "regain" else first["t"]
        seconds = round(shot["t"] - began, 1)
        sx = fa(shot["x"], shot["y"])
        start_xy = (origin["x"], origin["y"]) if origin.get("x") is not None else self._start(first, fa)
        progress = round(sx[0] - start_xy[0]) if start_xy else 0
        lengths = [e["data"].get("distance_m", 0) for e in passes]
        avg_len = round(sum(lengths) / len(lengths), 1) if lengths else 0.0
        involved = sorted({e["player"] for e in moves if e.get("player")})

        # Steps for the diagram: the last MAX_STEPS ball actions of the move, plus off-ball sprints.
        shown = [e for e in chain if e.get("team") == team and e["type"] in MOVE_TYPES + ("sprint",)][-MAX_STEPS:]
        steps, idx_of = [], {}
        for e in shown:
            s, en = self._start(e, fa), self._end(e, fa)
            d = e.get("data") or {}
            step = {"type": e["type"], "player": e.get("player"), "to": d.get("recipient"),
                    "x": round(s[0], 1), "y": round(s[1], 1), "ex": round(en[0], 1), "ey": round(en[1], 1),
                    "t": round(e["t"] - shot["t"], 1), "flags": []}
            if e["type"] == "pass":
                step["pass_type"] = d.get("pass_type")
            idx_of[e["id"]] = len(steps)
            steps.append(step)

        def flag(e: dict, name: str) -> None:
            k = idx_of.get(e["id"])
            if k is not None and name not in steps[k]["flags"]:
                steps[k]["flags"].append(name)

        patterns: list[dict] = []

        def add(key: str, strength: float, facts: dict, at: list[dict] | None = None) -> None:
            patterns.append({"key": key, "strength": round(min(1.0, strength), 2),
                             "facts": {k: v for k, v in facts.items() if v is not None},
                             "steps": [idx_of[e["id"]] for e in (at or []) if e["id"] in idx_of]})

        # --- how the move began --------------------------------------------------------------
        if origin["type"] == "regain" and origin.get("x") is not None:
            ox = origin["x"]
            if ox >= 60 and seconds <= 12:
                add("high_regain", 0.9 if origin.get("how") == "counterpress" else 0.75, {
                    "player": i.name(origin["player"]), "regain_m_from_goal": round(L - ox),
                    "seconds": round(seconds), "counterpress": origin.get("how") == "counterpress"})
            elif ox < 60 and seconds <= 16 and progress >= 35 and len(passes) <= 5:
                add("counter_attack", 0.6 + min(0.35, progress / 200), {
                    "player": i.name(origin["player"]), "progress_m": progress, "seconds": round(seconds),
                    "speed_ms": round(progress / max(1.0, seconds), 1), "passes": len(passes)})
        if origin["type"] in ("corner", "free_kick"):
            taker = origin.get("player")
            add("set_piece", 0.85, {"kind": origin["type"], "player": i.name(taker), "passes": len(passes)})

        # --- second balls and rebounds --------------------------------------------------------
        if origin["type"] == "regain":
            lo = origin["t"] - 10
            prior = [e for e in i._window(lo, origin["t"] - 0.01)
                     if (e["type"] == "shot" and e.get("team") == team) or
                        (e["type"] == "clearance" and e.get("team") != team)]
            if prior:
                p = prior[-1]
                add("second_ball", 0.8, {"after": "rebound" if p["type"] == "shot" else "clearance",
                                         "player": i.name(origin["player"]),
                                         "seconds_after": round(origin["t"] - p["t"])})

        # --- passing shape ---------------------------------------------------------------------
        if len(passes) >= 6 and avg_len <= 18:
            add("short_passing", 0.5 + min(0.45, (len(passes) - 6) * 0.06), {
                "passes": len(passes), "avg_pass_m": avg_len, "seconds": round(seconds),
                "players": len(involved)}, passes[-6:])

        for a, b in zip(passes, passes[1:]):
            da, db = a["data"], b["data"]
            if da.get("recipient") == b["player"] and db.get("recipient") == a["player"] \
                    and b["t"] - a["t"] <= 4.5:
                gain = round(fa(b["end_x"], b["end_y"])[0] - fa(a["x"], a["y"])[0])
                if gain >= 5:
                    add("one_two", 0.55, {"player": i.name(a["player"]), "partner": i.name(b["player"]),
                                          "gain_m": gain}, [a, b])
                    flag(a, "one_two"); flag(b, "one_two")
        for a, b in zip(passes, passes[1:]):
            da, db = a["data"], b["data"]
            c = db.get("recipient")
            if da.get("recipient") != b["player"] or not c or c == a["player"]:
                continue
            lay = da.get("progressive_m", 0) <= 8 or da.get("distance_m", 99) <= 15
            a_x = fa(a["x"], a["y"])[0]
            c_x = fa(b["end_x"], b["end_y"])[0]
            if lay and b["t"] - a["t"] <= 4.0 and db.get("progressive_m", 0) >= 10 and c_x - a_x >= 10:
                add("third_man", 0.7, {"first": i.name(a["player"]), "wall": i.name(b["player"]),
                                       "runner": i.name(c), "gain_m": round(c_x - a_x)}, [a, b])
                flag(a, "third_man"); flag(b, "third_man")
        for e in passes:
            s, en = self._start(e, fa), self._end(e, fa)
            if abs(en[1] - s[1]) >= 30:
                add("switch_play", 0.45, {"player": i.name(e["player"]), "width_m": round(abs(en[1] - s[1]))}, [e])
                flag(e, "switch")
                break
        breakers = [e for e in passes if e["data"].get("difficulty", 0) >= 0.6 and e["data"].get("progressive_m", 0) >= 15]
        if breakers:
            e = max(breakers, key=lambda x: x["data"]["progressive_m"])
            add("line_break", 0.55, {"player": i.name(e["player"]), "recipient": i.name(e["data"].get("recipient")),
                                     "progress_m": round(e["data"]["progressive_m"]),
                                     "difficulty": e["data"]["difficulty"]}, [e])
            flag(e, "line_break")

        # --- penalty area penetration -------------------------------------------------------------
        entry = None
        entries = 0
        for e in moves:
            if e["type"] == "shot":
                continue
            s, en = self._start(e, fa), self._end(e, fa)
            if s and en and not in_box(*s) and in_box(*en) and (e["type"] != "pass" or e["data"]["outcome"] == "complete"):
                entries += 1
                entry = e
        cutback = next((e for e in passes if self._start(e, fa)[0] >= 99 and e["data"].get("progressive_m", 0) < -2
                        and in_box(*self._end(e, fa))), None)
        if entry is not None or cutback is not None:
            e = cutback or entry
            d = e.get("data") or {}
            method = "cutback" if e is cutback else {"pass": d.get("pass_type", "ground"), "carry": "carry",
                                                      "dribble": "dribble"}[e["type"]]
            method = {"ground": "pass", "long": "pass"}.get(method, method)
            add("box_entry", 0.65, {"method": method, "player": i.name(e["player"]),
                                    "recipient": i.name(d.get("recipient")), "entries": max(1, entries),
                                    "lane": lane(self._start(e, fa)[1])}, [e])
            flag(e, "box_entry")

        # --- half-spaces ------------------------------------------------------------------------------
        hs = []
        for e in moves:
            pt = self._end(e, fa) if e["type"] != "shot" else self._start(e, fa)
            if pt and pt[0] >= FINAL_THIRD_X and lane(pt[1]).endswith("half_space"):
                hs.append(e)
        key_pass = passes[-1] if passes else None
        key_from_hs = key_pass is not None and self._start(key_pass, fa)[0] >= FINAL_THIRD_X - 5 \
            and lane(self._start(key_pass, fa)[1]).endswith("half_space")
        if len(hs) >= 2 or key_from_hs:
            ref = key_pass if key_from_hs else hs[-1]
            pt = self._start(ref, fa) if key_from_hs else self._end(ref, fa)
            add("half_space", 0.5 + 0.1 * min(3, len(hs)), {"side": lane(pt[1]).split("_")[0], "actions": len(hs),
                                                           "player": i.name(ref["player"])}, hs[-3:])
            for e in hs:
                flag(e, "half_space")

        # --- freeze frame and overloads ------------------------------------------------------------
        best = None
        candidates = [e for e in moves if e["type"] != "shot"][-6:] + [shot]
        for e in candidates:
            ball = self._start(e, fa)
            if ball is None:
                continue
            actors = self._actors(e, team, fa)
            players = self._positions(team, ball, actors)
            att, dfn = self._count(players, ball, OVERLOAD_RADIUS)
            score = att - dfn
            if best is None or score > best[0] or (score == best[0] and e is entry):
                best = (score, e, ball, players, att, dfn)
        frame = None
        if best is not None:
            score, e, ball, players, att, dfn = best
            frame = {"t": round(e["t"] - shot["t"], 1), "event": e["type"], "player": e.get("player"),
                     "ball": [round(ball[0], 1), round(ball[1], 1)], "radius": OVERLOAD_RADIUS,
                     "attackers": att, "defenders": dfn, "players": players, "estimated": True}
            if score >= 1 and att >= 3:
                add("overload", 0.5 + 0.12 * score, {"attackers": att, "defenders": dfn,
                                                    "zone": lane(ball[1]), "radius_m": int(OVERLOAD_RADIUS)}, [e])
                flag(e, "overload")

        # --- the finish: time and space -----------------------------------------------------------
        sd = shot["data"]
        recent_pressure = [e for e in i._window(shot["t"] - 5, shot["t"]) if e["type"] == "pressure" and e.get("team") != team]
        shot_players = self._positions(team, sx, self._actors(shot, team, fa))
        defenders = [(x, y) for pid, x, y, a in shot_players if not a and i.shape[pid]["role"] != "GK"]
        nearest = round(min(math.hypot(x - sx[0], y - sx[1]) for x, y in defenders), 1) if defenders else None
        if not sd.get("under_pressure") and not recent_pressure and nearest is not None and nearest >= 5:
            add("time_space", 0.5 + min(0.3, (nearest - 5) * 0.08), {
                "player": i.name(shot["player"]), "nearest_defender_m": nearest,
                "distance_m": round(sd["distance_m"])}, [])
        box_att = sum(1 for _, x, y, a in shot_players if a and in_box(x, y))
        box_def = sum(1 for _, x, y, a in shot_players if not a and in_box(x, y))

        # One entry per pattern: keep the occurrence that gained most ground, and how often it happened.
        merged: dict[str, dict] = {}
        for p in patterns:
            cur = merged.get(p["key"])
            if cur is None:
                merged[p["key"]] = p
                continue
            times = cur["facts"].get("times", 1) + 1
            if p["facts"].get("gain_m", 0) > cur["facts"].get("gain_m", 0):
                p["steps"] = sorted(set(p["steps"]) | set(cur["steps"]))
                merged[p["key"]] = cur = p
            else:
                cur["steps"] = sorted(set(p["steps"]) | set(cur["steps"]))
            cur["facts"]["times"] = times
            cur["strength"] = round(min(1.0, cur["strength"] + 0.05), 2)
        patterns = sorted(merged.values(), key=lambda p: -p["strength"])
        copy = {lang: render_buildup(patterns, lang) for lang in LANGS}
        return {
            "team": team, "team_name": i.team_names[team], "shot_event": shot["id"], "minute": shot["minute"],
            "outcome": sd["outcome"], "origin": {**origin, "player_name": i.name(origin.get("player")),
                                                 "x": round(origin["x"], 1) if origin.get("x") is not None else None,
                                                 "y": round(origin["y"], 1) if origin.get("y") is not None else None},
            "summary": {"passes": len(passes), "seconds": round(seconds), "players_involved": len(involved),
                        "progress_m": progress, "avg_pass_m": avg_len, "box_entries": entries,
                        "box_attackers": box_att, "box_defenders": box_def},
            "finish": {"player": shot["player"], "player_name": i.name(shot["player"]), "x": round(sx[0], 1),
                       "y": round(sx[1], 1), "xg": round(sd["xg"], 2), "speed_kmh": round(sd["speed_kmh"]),
                       "distance_m": round(sd["distance_m"]), "body_part": sd.get("body_part"),
                       "placement": sd.get("placement"), "nearest_defender_m": nearest},
            "patterns": patterns,
            "copy": copy,
            "steps": steps,
            "frame": frame,
        }

    def _actors(self, at: dict, team: str, fa) -> dict[str, tuple[float, float]]:
        """Real locations of players who touched the ball (or pressed it) in the seconds before `at`."""
        actors: dict[str, tuple[float, float]] = {}
        for e in self.i._window(at["t"] - 3, at["t"]):
            if e["type"] not in MOVE_TYPES + ("pressure", "sprint") or not e.get("player") or "x" not in e:
                continue
            if e is at or e["t"] < at["t"]:
                end = self._end(e, fa)
                actors[e["player"]] = self._start(e, fa) if e is at else end
                rec = (e.get("data") or {}).get("recipient")
                if rec and e["type"] == "pass" and e is not at:
                    actors[rec] = end
        if "x" in at and at.get("player"):
            actors[at["player"]] = self._start(at, fa)
        return actors

    def compact(self, a: dict, shot: dict) -> dict:
        """One row for the chance-creation summary."""
        return {"t": shot["t"], "minute": shot["minute"], "team": a["team"], "player": shot["player"],
                "x": a["finish"]["x"], "y": a["finish"]["y"], "xg": a["finish"]["xg"], "outcome": a["outcome"],
                "origin": a["origin"]["type"], "patterns": [p["key"] for p in a["patterns"]]}
