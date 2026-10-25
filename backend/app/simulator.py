"""Seeded synthetic football match generator.

The simulator plays a possession-by-possession model of a 90-minute match and emits a stream of
football-realistic events: passes, carries, dribbles, pressures, tackles, interceptions, shots,
corners, fouls, cards, substitutions, sprints and per-minute physical load.

Two modes:
  * script="default": a storyline is layered on top of the model (scripted phases change pressing,
    directness and quality over time, and scripted beats force the key goals). This gives a demo
    match with clear narrative arcs that still has realistic totals.
  * script="none": pure model; goals come from xG draws.

All coordinates in emitted events are absolute pitch metres (105 x 68). In period 1 the home team
attacks towards x=105; in period 2 it attacks towards x=0.
"""

from __future__ import annotations

import math
import random
from typing import Callable

from .teams import Player, Team, build_teams

L, W = 105.0, 68.0
HOME, AWAY = "NVR", "PSM"


def xg_model(x: float, y: float, header: bool = False, under_pressure: bool = False) -> float:
    """Simple location model in the attacking frame (goal centre at x=105, y=34)."""
    dx = max(0.5, L - x)
    dy = abs(34 - y)
    dist = math.hypot(dx, dy)
    angle = math.atan2(7.32 * dx, dx * dx + dy * dy - (7.32 / 2) ** 2)
    if angle < 0:
        angle += math.pi
    z = -1.3 + 1.5 * angle - 0.11 * dist
    if header:
        z -= 0.9
    if under_pressure:
        z -= 0.25
    return round(min(0.85, max(0.01, 1 / (1 + math.exp(-z)))), 3)


def pass_difficulty(d: float, dx: float, under_pressure: bool, lofted: bool, end_x: float) -> float:
    diff = 0.08 + 0.55 * (1 - math.exp(-d / 30))
    if under_pressure:
        diff += 0.17
    diff += 0.12 * min(1.0, max(0.0, dx / 25))
    if lofted:
        diff += 0.10
    if end_x > 88:
        diff += 0.12
    if dx < -3:
        diff -= 0.10
    return round(min(0.97, max(0.03, diff)), 2)


def fmt_clock(period: int, clock_s: float) -> str:
    base = 2700 if period == 1 else 5400
    if clock_s >= base:
        extra = clock_s - base
        return f"{base // 60}+{int(extra // 60):02d}:{int(extra % 60):02d}"
    return f"{int(clock_s // 60):02d}:{int(clock_s % 60):02d}"


def minute_label(period: int, clock_s: float) -> str:
    base = 2700 if period == 1 else 5400
    if clock_s >= base:
        return f"{base // 60}+{int((clock_s - base) // 60) + 1}'"
    return f"{int(clock_s // 60) + 1}'"


class MatchSimulator:
    def __init__(self, seed: int = 7, script: str = "default"):
        self.seed = seed
        self.rng = random.Random(seed)
        self.teams: dict[str, Team] = build_teams(seed)
        self.script = script
        self.goal_mode = "scripted" if script == "default" else "xg"
        self.events: list[dict] = []
        self.score = {HOME: 0, AWAY: 0}
        self.period = 1
        self.elapsed = 0.0
        self.period_start = 0.0
        self.poss = HOME
        self.ball = (52.5, 34.0)
        self.carrier: Player | None = None
        self.possession_id = 0
        self.cards: dict[str, int] = {}
        self._last_phys_minute = 0
        self._beats: list[tuple[float, Callable[[], None]]] = []
        if script == "default":
            self._beats = [
                (17.4, self._beat_patient_goal),
                (40.6, self._beat_big_chance),
                (57.6, self._beat_wing_sprint),
                (61.7, self._beat_long_range_goal),
                (65.6, lambda: self._substitute(HOME, 4, 14)),
                (70.2, lambda: self._substitute(AWAY, 9, 20)),
                (75.4, lambda: self._substitute(AWAY, 11, 18)),
                (78.8, self._beat_tactical_foul),
                (80.3, lambda: self._substitute(HOME, 11, 17)),
                (83.5, self._beat_counterpress_goal),
            ]
        else:
            self._beats = [(64.0, lambda: self._substitute(HOME, 4, 14)),
                           (71.0, lambda: self._substitute(AWAY, 9, 20)),
                           (79.0, lambda: self._substitute(HOME, 11, 17))]

    # ------------------------------------------------------------------ time and frames
    @property
    def clock_s(self) -> float:
        off = self.elapsed - self.period_start
        return off if self.period == 1 else 2700 + off

    @property
    def minute(self) -> float:
        return self.clock_s / 60

    def opp(self, code: str) -> str:
        return AWAY if code == HOME else HOME

    def to_abs(self, team: str, x: float, y: float) -> tuple[float, float]:
        attacks_right = (team == HOME) == (self.period == 1)
        if attacks_right:
            return round(x, 1), round(y, 1)
        return round(L - x, 1), round(W - y, 1)

    # ------------------------------------------------------------------ storyline phases
    def _phase(self, team: str, param: str) -> float:
        """Scripted multipliers that bend the model into a storyline. 1.0 means no change."""
        if self.script != "default":
            return 1.0
        m = self.minute
        if team == HOME and param == "press":
            if m < 46:
                return 1.0
            if m < 56:
                return 1.0 - 0.7 * (m - 46) / 10     # the press fades: 1.0 -> 0.3
            if m < 66:
                return 0.3
            return 0.82                                # fresh legs from the bench
        if team == AWAY and param == "press":
            return 0.9 if m < 30 else 1.1 if m < 45 else 1.3 if m < 70 else 1.0
        if param == "directness" and 70 <= m < 83:
            return 1.9                                 # the chaos phase: long balls both ways
        if team == HOME and param == "quality" and 50 <= m < 66:
            return 0.965
        if team == AWAY and param == "shot_bias" and 50 <= m < 66:
            return 1.4
        return 1.0

    def press_eff(self, code: str) -> float:
        t = self.teams[code]
        return t.press * self._phase(code, "press") * (1 - 0.12 * self.minute / 95)

    def quality_eff(self, code: str) -> float:
        t = self.teams[code]
        return t.quality * self._phase(code, "quality") * (1 - 0.03 * self.minute / 95)

    def directness_eff(self, code: str) -> float:
        return min(0.9, self.teams[code].directness * self._phase(code, "directness"))

    # ------------------------------------------------------------------ positions
    def player_pos(self, p: Player, ball_x_own_frame: float, ball_y: float, in_poss: bool) -> tuple[float, float]:
        """Approximate position of a player in their own attacking frame."""
        if p.role == "GK":
            return (5 + max(0, ball_x_own_frame - 52.5) * 0.12, 34 + (ball_y - 34) * 0.1)
        if in_poss:
            px = p.base_x + 6 + (ball_x_own_frame - 52.5) * 0.5
        else:
            px = p.base_x - 4 + (ball_x_own_frame - 52.5) * 0.45
        py = p.base_y + (ball_y - 34) * 0.22
        return (min(97, max(2, px)), min(66, max(2, py)))

    def nearest(self, team: str, x: float, y: float, in_poss: bool, ball_xy: tuple[float, float],
                exclude: Player | None = None, allow_gk: bool = False) -> tuple[Player, tuple[float, float]]:
        best, best_d, best_pos = None, 1e9, (x, y)
        for p in self.teams[team].on_pitch():
            if p is exclude or (p.role == "GK" and not allow_gk):
                continue
            pos = self.player_pos(p, ball_xy[0], ball_xy[1], in_poss)
            d = math.hypot(pos[0] - x, pos[1] - y)
            if d < best_d:
                best, best_d, best_pos = p, d, pos
        assert best is not None
        return best, best_pos

    def defender_near(self, x: float, y: float) -> Player:
        """Nearest defending player to a point given in the attacking team's frame."""
        dx, dy = L - x, W - y
        p, _ = self.nearest(self.opp(self.poss), dx, dy, False, (dx, dy), allow_gk=x > 96)
        return p

    # ------------------------------------------------------------------ emission
    def emit(self, etype: str, team: str | None = None, player: Player | None = None,
             xy: tuple[float, float] | None = None, end: tuple[float, float] | None = None,
             frame_team: str | None = None, **data) -> dict:
        ft = frame_team or team
        ev: dict = {
            "id": len(self.events) + 1,
            "t": round(self.elapsed, 2),
            "clock_s": round(self.clock_s, 1),
            "clock": fmt_clock(self.period, self.clock_s),
            "minute": minute_label(self.period, self.clock_s),
            "period": self.period,
            "type": etype,
            "team": team,
            "player": player.id if player else None,
            "possession_id": self.possession_id,
        }
        if xy is not None and ft:
            ev["x"], ev["y"] = self.to_abs(ft, *xy)
        if end is not None and ft:
            ev["end_x"], ev["end_y"] = self.to_abs(ft, *end)
        if data:
            ev["data"] = data
        self.events.append(ev)
        return ev

    def advance(self, seconds: float) -> None:
        self.elapsed += max(0.2, seconds)
        self._physical_ticks()

    def _physical_ticks(self) -> None:
        while self._last_phys_minute < int(self.clock_s // 60):
            self._last_phys_minute += 1
            m = self._last_phys_minute
            dist: dict[str, int] = {}
            for code, team in self.teams.items():
                boost = 1 + 0.06 * self.press_eff(code)
                for p in team.on_pitch():
                    fatigue = 1 - 0.13 * (m / 95) * (1.0 if getattr(p, "_fresh_from", 0) == 0 else 0.3)
                    dist[p.id] = int(p.work_rate * fatigue * boost * self.rng.uniform(0.9, 1.1))
            self.emit("physical", window_s=60, distance_m=dist)

    def change_possession(self, new_team: str, x_own: float, y_own: float, carrier: Player | None) -> None:
        self.poss = new_team
        self.ball = (min(104, max(1, x_own)), min(67, max(1, y_own)))
        self.carrier = carrier
        self.possession_id += 1

    def flip_to_defenders(self, x_att: float, y_att: float, winner: Player) -> None:
        self.change_possession(self.opp(self.poss), L - x_att, W - y_att, winner)

    # ------------------------------------------------------------------ match loop
    def run(self) -> dict:
        start_meta = self.meta()  # line-ups as they kick off, before any substitutions
        stoppage = {1: 2, 2: 4} if self.script == "default" else {1: self.rng.randint(1, 3), 2: self.rng.randint(3, 6)}
        for period in (1, 2):
            self.period = period
            self.period_start = self.elapsed
            end_clock = (2700 if period == 1 else 5400) + stoppage[period] * 60 + self.rng.uniform(5, 40)
            self._kickoff(HOME if period == 1 else AWAY)
            while self.clock_s < end_clock:
                while self._beats and self.minute >= self._beats[0][0] and self.period == (1 if self._beats[0][0] < 45 else 2):
                    _, beat = self._beats.pop(0)
                    beat()
                self._step()
            self.emit("period_end", score=dict(self.score), stoppage_min=stoppage[period])
            self.elapsed += 1
        self.emit("match_end", score=dict(self.score))
        return {"match": start_meta, "events": self.events}

    def meta(self) -> dict:
        return {
            "id": f"syn-{self.seed}-{self.script}",
            "seed": self.seed,
            "script": self.script,
            "home": self.teams[HOME].public(),
            "away": self.teams[AWAY].public(),
            "venue": "Saltmere Road (fictional)",
            "competition": "Synthetic League",
            "pitch": {"length": L, "width": W},
            "synthetic": True,
        }

    def _kickoff(self, team: str) -> None:
        st = next(p for p in self.teams[team].on_pitch() if p.role in ("ST",))
        self.change_possession(team, 52.5, 34, st)
        self.emit("kickoff", team, st, (52.5, 34), score=dict(self.score))
        self.advance(1.0)

    # ------------------------------------------------------------------ one action
    def _step(self) -> None:
        att = self.teams[self.poss]
        bx, by = self.ball
        if self.carrier is None or not self.carrier.on_pitch:
            self.carrier, _ = self.nearest(self.poss, bx, by, True, self.ball, allow_gk=bx < 15)

        dpress = self.press_eff(self.opp(self.poss))
        if bx < 52.5:
            p_press = 0.10 + 0.55 * dpress * (1 - bx / 52.5)
        else:
            p_press = 0.16 + 0.14 * (bx / L)
        under = self.rng.random() < p_press
        if under:
            d = self.defender_near(bx, by)
            self.emit("pressure", d.team, d, (L - bx, W - by), frame_team=d.team)
            self.advance(0.5)

        central = abs(by - 34) < 20
        shot_bias = att.shot_bias * self._phase(self.poss, "shot_bias")
        if bx > 86 and central:
            weights = {"shot": 0.075 * shot_bias, "pass": 0.58, "dribble": 0.15, "carry": 0.10}
        elif bx > 72:
            weights = {"shot": (0.022 * shot_bias if central else 0.0),
                       "cross": (0.0 if central else 0.17), "pass": 0.58, "dribble": 0.11, "carry": 0.12}
        else:
            weights = {"pass": 0.80, "carry": 0.16, "dribble": 0.04}
        if under:
            weights["carry"] = weights.get("carry", 0) * 0.4
        action = self.rng.choices(list(weights), list(weights.values()))[0]

        if action == "pass":
            self._pass(under)
        elif action == "cross":
            self._pass(under, kind="cross")
        elif action == "carry":
            self._carry()
        elif action == "dribble":
            self._dribble(under)
        else:
            self._shot(under)

    def _carry(self) -> None:
        bx, by = self.ball
        dist = self.rng.uniform(4, 14)
        ang = self.rng.gauss(0, 0.5)
        ex = min(96, max(2, bx + dist * math.cos(ang)))
        ey = min(66, max(2, by + dist * math.sin(ang)))
        self.emit("carry", self.poss, self.carrier, (bx, by), (ex, ey), distance_m=round(math.hypot(ex - bx, ey - by), 1))
        self.ball = (ex, ey)
        self.advance(dist / self.rng.uniform(4.5, 6.5))

    def _dribble(self, under: bool) -> None:
        bx, by = self.ball
        d = self.defender_near(bx, by)
        p_win = 0.5 + (0.1 if self.carrier and self.carrier.role in ("RW", "LW", "AM") else 0) - (0.12 if under else 0)
        if self.rng.random() < p_win:
            ex, ey = min(96, bx + self.rng.uniform(3, 8)), min(66, max(2, by + self.rng.uniform(-4, 4)))
            self.emit("dribble", self.poss, self.carrier, (bx, by), (ex, ey), outcome="complete", opponent=d.id)
            self.ball = (ex, ey)
            self.advance(2.0)
        else:
            if self.rng.random() < 0.15:
                self._foul(d, bx, by)
                return
            self.emit("dribble", self.poss, self.carrier, (bx, by), outcome="lost", opponent=d.id)
            self.emit("tackle", d.team, d, (L - bx, W - by), frame_team=d.team, outcome="won")
            self.flip_to_defenders(bx, by, d)
            self.advance(1.5)

    def _foul(self, fouler: Player, bx: float, by: float, force_card: str | None = None) -> None:
        fouled = self.carrier
        self.emit("foul", fouler.team, fouler, (L - bx, W - by), frame_team=fouler.team,
                  on=fouled.id if fouled else None)
        n = self.cards.get(fouler.id, 0)
        card = force_card or ("yellow" if self.rng.random() < 0.09 and n == 0 else None)
        if card:
            self.cards[fouler.id] = n + 1
            self.advance(20)
            self.emit("card", fouler.team, fouler, (L - bx, W - by), frame_team=fouler.team, card=card,
                      reason="tactical foul" if force_card else "foul")
        self.advance(self.rng.uniform(12, 25))

    def _pass(self, under: bool, kind: str | None = None, target: tuple[float, float] | None = None,
              receiver: Player | None = None, force: bool | None = None, lofted: bool | None = None) -> bool:
        bx, by = self.ball
        passer = self.carrier
        long_ball = False
        if target is None:
            if kind == "cross":
                target = (self.rng.uniform(92, 100), self.rng.uniform(26, 42))
                lofted = True
            else:
                long_ball = self.rng.random() < (self.directness_eff(self.poss) * 0.35 + (0.2 if under and bx < 35 else 0))
                dist = self.rng.lognormvariate(math.log(30 if long_ball else 13), 0.3 if long_ball else 0.45)
                dist = min(60, max(4, dist))
                fwd = 0.0 if bx < 80 else (0.9 if by > 34 else -0.9)
                ang = self.rng.gauss(fwd, 0.95 if not long_ball else 0.5)
                target = (min(103, max(2, bx + dist * math.cos(ang))), min(66, max(2, by + dist * math.sin(ang))))
        if receiver is None:
            receiver, rpos = self.nearest(self.poss, target[0], target[1], True, target, exclude=passer,
                                          allow_gk=target[0] < 25)
            ex = 0.6 * rpos[0] + 0.4 * target[0] + self.rng.gauss(0, 1.5)
            ey = 0.6 * rpos[1] + 0.4 * target[1] + self.rng.gauss(0, 1.5)
        else:
            ex, ey = target
        ex, ey = min(104, max(1, ex)), min(67, max(1, ey))
        d = math.hypot(ex - bx, ey - by)
        dx = ex - bx
        lofted = bool(lofted) if lofted is not None else (long_ball or d > 35)
        diff = pass_difficulty(d, dx, under, lofted, ex)
        if force is None:
            p_ok = self.quality_eff(self.poss) * (1 - 0.55 * diff) + 0.17
            if kind == "cross":
                p_ok *= 0.62
            ok = self.rng.random() < p_ok
        else:
            ok = force
        speed = (42 + 0.75 * d + self.rng.gauss(0, 5)) if lofted else (28 + 1.05 * d + self.rng.gauss(0, 4))
        speed = round(min(105, max(15, speed)), 1)
        ptype = "cross" if kind == "cross" else ("through" if dx > 18 and not lofted else ("long" if lofted else "ground"))
        ev = self.emit("pass", self.poss, passer, (bx, by), (ex, ey), outcome="complete" if ok else "incomplete",
                       recipient=receiver.id if ok else None, under_pressure=under, distance_m=round(d, 1),
                       ball_speed_kmh=speed, difficulty=diff, pass_type=ptype, progressive_m=round(dx, 1))
        self.advance(d / (speed / 3.6) + self.rng.uniform(0.8, 2.0))

        if ok:
            # A long run onto a forward ball produces a tracked sprint.
            start_pos = self.player_pos(receiver, bx, by, True)
            run = math.hypot(ex - start_pos[0], ey - start_pos[1])
            if run > 13 and dx > 12 and receiver.role != "GK":
                self._sprint(receiver, start_pos, (ex, ey), run + self.rng.uniform(4, 16))
            self.carrier = receiver
            self.ball = (ex, ey)
            return True

        r = self.rng.random()
        mid = ((bx + ex) / 2, (by + ey) / 2) if r < 0.35 else (ex, ey)
        if r < 0.72:
            # Most misplaced passes are picked up loose; only some are true interceptions.
            d_pl = self.defender_near(*mid)
            etype = "interception" if r < 0.24 else "ball_recovery"
            self.emit(etype, d_pl.team, d_pl, (L - mid[0], W - mid[1]), frame_team=d_pl.team)
            self.flip_to_defenders(mid[0], mid[1], d_pl)
        elif r < 0.86 or ev["data"]["pass_type"] == "cross":
            # out of play or cleared: restart for the defending side
            d_pl = self.defender_near(ex, ey)
            if ev["data"]["pass_type"] == "cross" and self.rng.random() < 0.5:
                self.emit("clearance", d_pl.team, d_pl, (L - ex, W - ey), frame_team=d_pl.team)
                if self.rng.random() < 0.3:
                    self._corner()
                    return False
            self.flip_to_defenders(ex, 1.0 if ey < 34 else 67.0, d_pl)
            self.advance(self.rng.uniform(6, 14))
        else:
            d_pl = self.defender_near(ex, ey)
            self.emit("tackle", d_pl.team, d_pl, (L - ex, W - ey), frame_team=d_pl.team, outcome="won", on=receiver.id)
            self.flip_to_defenders(ex, ey, d_pl)
        return False

    def _sprint(self, p: Player, start: tuple[float, float], end: tuple[float, float], distance: float,
                top_speed: float | None = None) -> None:
        fatigue = 1 - 0.035 * self.minute / 95
        ts = top_speed or round(p.top_speed * fatigue * self.rng.uniform(0.88, 0.99), 1)
        self.emit("sprint", p.team, p, start, end, top_speed_kmh=ts, distance_m=round(distance, 1))

    def _shot(self, under: bool, header: bool = False, spec: dict | None = None) -> None:
        bx, by = self.ball
        shooter = self.carrier
        spec = spec or {}
        xg = spec.get("xg") or xg_model(bx, by, header, under)
        dist = math.hypot(L - bx, 34 - by)
        if header:
            speed = self.rng.uniform(45, 68)
        else:
            speed = 58 + self.rng.random() * 38 + (8 if dist > 20 else 0)
        speed = round(spec.get("speed_kmh", speed), 1)
        if "outcome" in spec:
            outcome = spec["outcome"]
        else:
            r = self.rng.random()
            blocked = 0.24 + (0.1 if under else 0)
            if r < blocked:
                outcome = "blocked"
            elif r < blocked + 0.37:
                outcome = "off_target"
            else:
                outcome = "saved"
                if self.goal_mode == "xg" and self.rng.random() < min(0.9, xg / 0.36):
                    outcome = "goal"
                elif self.rng.random() < 0.04:
                    outcome = "woodwork"
        gx, gy = 105.0, 34 + self.rng.uniform(-3.2, 3.2)
        self.emit("shot", self.poss, shooter, (bx, by), (gx, gy), outcome=outcome, xg=xg, speed_kmh=speed,
                  distance_m=round(dist, 1), body_part="head" if header else spec.get("body_part", "right_foot"),
                  under_pressure=under, placement=spec.get("placement"))
        self.advance(1.5)
        if outcome == "goal":
            self.score[self.poss] += 1
            self.emit("goal", self.poss, shooter, (bx, by), score=dict(self.score),
                      assist=spec.get("assist"))
            self.advance(self.rng.uniform(55, 75))
            self._kickoff(self.opp(self.poss))
            return
        gk = next(p for p in self.teams[self.opp(self.poss)].on_pitch() if p.role == "GK")
        if outcome == "saved":
            self.emit("save", gk.team, gk, (L - gx, W - gy), frame_team=gk.team, shot_xg=xg)
            if spec.get("then") == "corner" or self.rng.random() < 0.3:
                self.advance(3)
                self._corner()
            else:
                self.change_possession(gk.team, 6, 34, gk)
                self.advance(self.rng.uniform(5, 12))
        elif outcome == "blocked":
            d = self.defender_near(bx, by)
            if self.rng.random() < 0.45:
                self.advance(3)
                self._corner()
            else:
                self.flip_to_defenders(bx, by, d)
        else:
            self.change_possession(gk.team, 6, 34, gk)
            self.advance(self.rng.uniform(15, 30))

    def _corner(self) -> None:
        side_y = 1.0 if self.rng.random() < 0.5 else 67.0
        taker = max(self.teams[self.poss].on_pitch(), key=lambda p: p.base_x if p.role in ("RW", "LW", "AM", "CM") else 0)
        self.carrier = taker
        self.ball = (104.0, side_y)
        self.emit("corner", self.poss, taker, (104.0, side_y))
        self.advance(self.rng.uniform(18, 30))
        if self._pass(False, kind="cross"):
            if self.rng.random() < 0.5:
                self._shot(True, header=True)

    def _substitute(self, team: str, off_no: int, on_no: int) -> None:
        t = self.teams[team]
        off = t.by_number(off_no)
        on = t.by_number(on_no)
        on.base_x, on.base_y, on.role = off.base_x, off.base_y, off.role if on.role != off.role else on.role
        off.on_pitch = False
        on.on_pitch = True
        setattr(on, "_fresh_from", self.minute)
        t.players.append(on)
        t.bench = [p for p in t.bench if p is not on]
        if self.carrier is off:
            self.carrier = None
        self.emit("substitution", team, on, player_off=off.id, player_on=on.id)
        self.advance(25)

    # ------------------------------------------------------------------ scripted beats
    def _move(self, team: str, start: tuple[float, float], start_no: int, passes: list[tuple[int, float, float]]) -> None:
        """Play a scripted, always-successful passing move for `team` in its attacking frame."""
        if self.poss != team:
            self.change_possession(team, *start, self.teams[team].by_number(start_no))
        else:
            self.ball, self.carrier = start, self.teams[team].by_number(start_no)
        for number, tx, ty in passes:
            rec = self.teams[team].by_number(number)
            self._pass(False, target=(tx, ty), receiver=rec, force=True, lofted=False)

    def _beat_patient_goal(self) -> None:
        # 18': Northvale's 13-pass move, finished by the No. 9 from a through ball.
        moves = [(6, 30, 40), (4, 38, 34), (8, 47, 22), (2, 56, 9), (8, 58, 23), (4, 47, 36), (5, 36, 45),
                 (3, 53, 58), (10, 61, 46), (11, 72, 56), (10, 71, 40), (7, 83, 15)]
        self._move(HOME, (22, 26), 5, moves)
        self._pass(False, target=(95.5, 31), receiver=self.teams[HOME].by_number(9), force=True, lofted=False)
        self._shot(False, spec={"outcome": "goal", "speed_kmh": 88.4, "assist": f"{HOME}-7", "placement": "low far corner"})

    def _beat_big_chance(self) -> None:
        # 41': Saltmere break, Osei has a clear sight of goal and is denied by Brevik.
        self._move(AWAY, (38, 30), 6, [(10, 58, 34), (7, 80, 14)])
        self._pass(False, target=(98.5, 34.5), receiver=self.teams[AWAY].by_number(11), force=True, lofted=False)
        self._shot(False, spec={"outcome": "saved", "speed_kmh": 74.2, "then": "corner"})

    def _beat_wing_sprint(self) -> None:
        # 58': Varela burns down the right at 35.2 km/h; the cross is blocked behind.
        self._move(AWAY, (46, 22), 8, [(7, 55, 11)])
        varela = self.teams[AWAY].by_number(7)
        self._sprint(varela, (55, 11), (91, 7), 49.6, top_speed=35.2)
        self.emit("carry", AWAY, varela, (55, 11), (91, 7), distance_m=36.3)
        self.ball = (91, 7)
        self.advance(5.5)
        d = self.teams[HOME].by_number(5)
        self.emit("clearance", HOME, d, (L - 93, W - 12), frame_team=HOME)
        self.advance(3)
        self._corner()

    def _beat_long_range_goal(self) -> None:
        # 62': with the press gone, Arata has time to strike from 31 metres. Low xG, unstoppable shot.
        self._move(AWAY, (44, 40), 4, [(6, 48, 38), (10, 60, 33), (8, 67, 29)])
        arata = self.teams[AWAY].by_number(8)
        self.emit("carry", AWAY, arata, (67, 29), (74.5, 31), distance_m=7.8)
        self.ball = (74.5, 31)
        self.advance(2.2)
        self._shot(False, spec={"outcome": "goal", "speed_kmh": 118.3, "assist": f"{AWAY}-10",
                                "placement": "top corner", "body_part": "right_foot"})

    def _beat_tactical_foul(self) -> None:
        # 79': Saar stops a Northvale counter and takes a yellow card for it.
        self._move(HOME, (40, 20), 8, [(7, 58, 12)])
        varma = self.teams[HOME].by_number(7)
        self.emit("carry", HOME, varma, (58, 12), (63, 14), distance_m=5.4)
        self.ball = (63, 14)
        self.advance(1.8)
        self._foul(self.teams[AWAY].by_number(4), 63, 14, force_card="yellow")

    def _beat_counterpress_goal(self) -> None:
        # 84': Northvale win it back high (counter-press) and score within 8 seconds.
        self.change_possession(AWAY, 21, 40, self.teams[AWAY].by_number(4))
        okonkwo = self.teams[HOME].by_number(8)
        self.emit("pressure", HOME, okonkwo, (L - 21, W - 40), frame_team=HOME)
        self.advance(0.6)
        self.emit("tackle", HOME, okonkwo, (L - 23, W - 39), frame_team=HOME, outcome="won", counterpress=True)
        self.change_possession(HOME, L - 23, W - 39, okonkwo)
        self.advance(0.8)
        self._pass(False, target=(88, 32), receiver=self.teams[HOME].by_number(10), force=True, lofted=False)
        self._pass(False, target=(94.5, 35), receiver=self.teams[HOME].by_number(9), force=True, lofted=False)
        self._shot(False, spec={"outcome": "goal", "speed_kmh": 96.1, "assist": f"{HOME}-10", "placement": "near post"})


def generate_match(seed: int = 7, script: str = "default") -> dict:
    return MatchSimulator(seed=seed, script=script).run()


if __name__ == "__main__":
    import argparse
    import json

    ap = argparse.ArgumentParser(description="Generate a synthetic football match as JSON Lines events.")
    ap.add_argument("--seed", type=int, default=21)
    ap.add_argument("--script", choices=["default", "none"], default="default")
    ap.add_argument("--out", default="-", help="output file, or - for stdout")
    args = ap.parse_args()
    data = generate_match(args.seed, args.script)
    lines = [json.dumps({"type": "match_meta", **data["match"]})] + [json.dumps(e) for e in data["events"]]
    if args.out == "-":
        print("\n".join(lines))
    else:
        with open(args.out, "w", encoding="utf-8") as f:
            f.write("\n".join(lines) + "\n")
