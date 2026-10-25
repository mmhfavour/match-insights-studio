"""Interpret: turn the raw event stream into stats, patterns and key moments with evidence.

Everything here is deterministic. The agents downstream are only allowed to talk about the numbers
and names that this module puts into a moment's `evidence`, which is what the Verifier enforces.
"""

from __future__ import annotations

import bisect
from collections import defaultdict

L = 105.0

# Thresholds that trigger player tags and moments.
TOP_SPEED_TAG_KMH = 34.0
ROCKET_SHOT_KMH = 105.0
BIG_CHANCE_XG = 0.35
LINE_BREAKER_DIFFICULTY = 0.84
DISTANCE_MILESTONE_M = 10_000
PASS_MILESTONE = 50

IMPORTANCE = {
    "goal": 1.0, "full_time": 0.95, "half_time": 0.9, "big_chance": 0.75, "press_shift": 0.7,
    "momentum_swing": 0.6, "rhythm_shift": 0.6, "card": 0.55, "top_speed": 0.55, "rocket_shot": 0.5,
    "line_breaker": 0.45, "distance_milestone": 0.4, "substitution": 0.4, "pass_milestone": 0.35,
}
SLOT = {
    "goal": "lower_third", "full_time": "full_card", "half_time": "full_card", "big_chance": "lower_third",
    "press_shift": "stat_card", "momentum_swing": "stat_card", "rhythm_shift": "stat_card",
    "card": "lower_third", "top_speed": "player_tag", "rocket_shot": "player_tag",
    "line_breaker": "player_tag", "distance_milestone": "player_tag", "substitution": "lower_third",
    "pass_milestone": "player_tag",
}
DURATION_S = {"full_card": 14, "lower_third": 9, "stat_card": 10, "player_tag": 7}


def _clamp(v: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, v))


class Interpreter:
    def __init__(self, match: dict):
        self.match = match
        self.home = match["home"]["code"]
        self.away = match["away"]["code"]
        self.team_names = {self.home: match["home"]["name"], self.away: match["away"]["name"]}
        self.team_short = {self.home: match["home"]["short"], self.away: match["away"]["short"]}
        self.players: dict[str, dict] = {}
        for side in ("home", "away"):
            for p in match[side]["players"] + match[side]["bench"]:
                self.players[p["id"]] = p

        self.events: list[dict] = []
        self.ts: list[float] = []
        self.score = {self.home: 0, self.away: 0}
        self.period = 1
        self.clock = "00:00"
        self.minute = "1'"
        self.t = 0.0
        self.team = {c: defaultdict(float) for c in (self.home, self.away)}
        self.pstats: dict[str, defaultdict] = defaultdict(lambda: defaultdict(float))
        self.on_pitch = {p["id"] for side in ("home", "away") for p in match[side]["players"]}
        self.poss_team: str | None = None
        self.poss_since = 0.0
        self.poss_changes: list[tuple[float, str]] = []
        self.chains: dict[int, dict] = {}
        self.threat: list[tuple[float, str, float]] = []
        self.moments: list[dict] = []
        self.cooldown: dict[str, float] = {}
        self.series: list[dict] = []          # one point per minute for sparklines
        self._crossed_distance: set[str] = set()
        self._pass_milestone_done = False
        self._last_check_t = 0.0
        self._last_goal_chain: dict | None = None

    # ------------------------------------------------------------------ helpers
    def own_x(self, team: str, x: float, period: int | None = None) -> float:
        p = period or self.period
        return x if (team == self.home) == (p == 1) else L - x

    def opp(self, team: str) -> str:
        return self.away if team == self.home else self.home

    def name(self, pid: str | None) -> str | None:
        return self.players[pid]["name"] if pid and pid in self.players else None

    def short(self, pid: str | None) -> str | None:
        return self.players[pid]["short"] if pid and pid in self.players else None

    def _window(self, start_t: float, end_t: float) -> list[dict]:
        i = bisect.bisect_left(self.ts, start_t)
        j = bisect.bisect_right(self.ts, end_t)
        return self.events[i:j]

    def _ready(self, key: str, cooldown_s: float) -> bool:
        return self.t - self.cooldown.get(key, -1e9) >= cooldown_s

    def _moment(self, mtype: str, ev: dict, team: str | None, players: list[str], evidence: dict,
                key: str | None = None) -> dict:
        m = {
            "id": f"m-{len(self.moments) + 1:03d}",
            "type": mtype,
            "t": ev["t"],
            "clock": ev["clock"],
            "minute": ev["minute"],
            "period": ev["period"],
            "team": team,
            "team_name": self.team_names.get(team) if team else None,
            "players": [p for p in players if p],
            "importance": IMPORTANCE[mtype],
            "slot": SLOT[mtype],
            "duration_s": DURATION_S[SLOT[mtype]],
            "evidence": {k: v for k, v in evidence.items() if v is not None},
            "context": self.context(),
        }
        self.moments.append(m)
        if key:
            self.cooldown[key] = self.t
        return m

    # ------------------------------------------------------------------ rolling metrics
    def ppda(self, team: str, start_t: float, end_t: float) -> tuple[float | None, int, int]:
        """Passes allowed per defensive action for `team` (the pressing side) in a window."""
        opp = self.opp(team)
        passes, actions = 0, 0
        for e in self._window(start_t, end_t):
            if "x" not in e:
                continue
            if e["type"] == "pass" and e["team"] == opp and self.own_x(opp, e["x"], e["period"]) < 63:
                passes += 1
            elif e["type"] in ("tackle", "interception", "foul") and e["team"] == team \
                    and self.own_x(team, e["x"], e["period"]) > 42:
                actions += 1
        return (round(passes / actions, 1) if actions else None), passes, actions

    def press_rate(self, team: str, start_t: float, end_t: float) -> tuple[int | None, int]:
        """Pressing actions (pressures, tackles, interceptions, fouls) by `team` in the opponent's own
        60% of the pitch, per 100 opponent passes from that zone. Smoother than PPDA over short windows."""
        opp = self.opp(team)
        passes, actions = 0, 0
        for e in self._window(start_t, end_t):
            if "x" not in e:
                continue
            if e["type"] == "pass" and e["team"] == opp and self.own_x(opp, e["x"], e["period"]) < 63:
                passes += 1
            elif e["type"] in ("pressure", "tackle", "interception", "foul") and e["team"] == team \
                    and self.own_x(team, e["x"], e["period"]) > 42:
                actions += 1
        return (round(100 * actions / passes) if passes else None), passes

    def possession_share(self, start_t: float, end_t: float) -> dict[str, float]:
        secs = {self.home: 0.0, self.away: 0.0}
        changes = self.poss_changes
        for i, (ct, team) in enumerate(changes):
            nt = changes[i + 1][0] if i + 1 < len(changes) else end_t
            a, b = max(ct, start_t), min(nt, end_t)
            if b > a:
                secs[team] += b - a
        tot = sum(secs.values()) or 1
        return {k: round(100 * v / tot) for k, v in secs.items()}

    def momentum(self, end_t: float, window: float = 300) -> float:
        """Home share (0..1) of attacking threat over the last `window` seconds."""
        h = a = 0.0
        for t, team, v in reversed(self.threat):
            if t < end_t - window:
                break
            if t <= end_t:
                if team == self.home:
                    h += v
                else:
                    a += v
        return round((h + 0.15) / (h + a + 0.3), 2)

    def control(self, end_t: float, window: float = 600) -> dict:
        evs = self._window(end_t - window, end_t)
        passes = [e for e in evs if e["type"] == "pass"]
        done = [e for e in passes if e["data"]["outcome"] == "complete"]
        longs = [e for e in passes if e["data"]["pass_type"] in ("long", "cross")]
        switches = sum(1 for t, _ in self.poss_changes if end_t - window <= t <= end_t)
        mins = max(1.0, min(window, end_t) / 60)
        chains = [c["completed"] for pid, c in self.chains.items() if end_t - window <= c["start"] <= end_t]
        avg_chain = sum(chains) / len(chains) if chains else 0.0
        acc = len(done) / len(passes) if passes else 0.0
        spm = switches / mins
        c1 = _clamp((avg_chain - 1.5) / 4)
        c2 = _clamp((acc - 0.65) / 0.25)
        s = _clamp((spm - 2.5) / 3.5)
        lb = _clamp((len(longs) / len(passes) if passes else 0) / 0.3)
        idx = round((c1 + c2) / 2 - (s + lb) / 2, 2)
        label = "control" if idx > 0.2 else "chaos" if idx < -0.2 else "contested"
        return {"index": idx, "label": label, "switches_per_min": round(spm, 1),
                "avg_chain": round(avg_chain, 1), "pass_accuracy": round(100 * acc),
                "long_ball_pct": round(100 * len(longs) / len(passes)) if passes else 0}

    def context(self) -> dict:
        c = self.control(self.t)
        return {"score": dict(self.score), "momentum_home": self.momentum(self.t),
                "control_index": c["index"], "control_label": c["label"]}

    # ------------------------------------------------------------------ ingest
    def ingest(self, ev: dict) -> list[dict]:
        self.events.append(ev)
        self.ts.append(ev["t"])
        self.t = ev["t"]
        self.period = ev["period"]
        self.clock = ev["clock"]
        self.minute = ev["minute"]
        out: list[dict] = []
        et, team, pid, d = ev["type"], ev.get("team"), ev.get("player"), ev.get("data", {})

        if et in ("pass", "carry", "dribble", "shot", "kickoff") and team:
            if team != self.poss_team:
                self.poss_changes.append((ev["t"], team))
                self.poss_team = team
            ch = self.chains.setdefault(ev["possession_id"], {"team": team, "start": ev["t"], "completed": 0,
                                                              "first_event": ev})
            if et == "pass" and d.get("outcome") == "complete":
                ch["completed"] += 1
        if pid and et not in ("physical",):
            self.pstats[pid]["touches"] += 1 if et in ("pass", "carry", "dribble", "shot") else 0

        ts = self.team[team] if team in self.team else None
        if et == "pass" and ts is not None:
            ts["passes"] += 1
            self.pstats[pid]["passes"] += 1
            if d["outcome"] == "complete":
                ts["passes_completed"] += 1
                self.pstats[pid]["passes_completed"] += 1
                sx, ex = self.own_x(team, ev["x"]), self.own_x(team, ev["end_x"])
                if ex >= 70 > sx:
                    ts["final_third_entries"] += 1
                gain = max(0.0, ex - sx)
                self.threat.append((ev["t"], team, gain / L * (ex / L) ** 2 * 2.2))
                out += self._check_pass(ev)
        elif et == "carry" and ts is not None:
            sx, ex = self.own_x(team, ev["x"]), self.own_x(team, ev["end_x"])
            self.threat.append((ev["t"], team, max(0.0, ex - sx) / L * (ex / L) ** 2 * 1.5))
        elif et == "shot" and ts is not None:
            ts["shots"] += 1
            ts["xg"] += d["xg"]
            self.pstats[pid]["shots"] += 1
            self.pstats[pid]["xg"] += d["xg"]
            if d["outcome"] in ("saved", "goal"):
                ts["on_target"] += 1
            self.threat.append((ev["t"], team, d["xg"] * 4))
            out += self._check_shot(ev)
        elif et == "goal" and ts is not None:
            self.score = dict(d["score"])
            self.pstats[pid]["goals"] += 1
            out.append(self._goal_moment(ev))
        elif et == "pressure" and ts is not None:
            ts["pressures"] += 1
            self.pstats[pid]["pressures"] += 1
        elif et == "ball_recovery" and ts is not None:
            ts["recoveries"] += 1
            self.pstats[pid]["recoveries"] += 1
        elif et in ("tackle", "interception") and ts is not None:
            ts[et + "s"] += 1
            self.pstats[pid][et + "s"] += 1
        elif et == "foul" and ts is not None:
            ts["fouls"] += 1
        elif et == "corner" and ts is not None:
            ts["corners"] += 1
            self.threat.append((ev["t"], team, 0.12))
        elif et == "card" and ts is not None:
            ts["cards"] += 1
            out.append(self._card_moment(ev))
        elif et == "sprint" and ts is not None:
            ps = self.pstats[pid]
            ps["sprints"] += 1
            ps["top_speed"] = max(ps["top_speed"], d["top_speed_kmh"])
            ts["sprints"] += 1
            out += self._check_sprint(ev)
        elif et == "substitution" and ts is not None:
            out.append(self._sub_moment(ev))
            self.on_pitch.discard(d["player_off"])
            self.on_pitch.add(d["player_on"])
        elif et == "physical":
            for p, m in d["distance_m"].items():
                self.pstats[p]["distance_m"] += m
                self.team[self.players[p]["team"]]["distance_m"] += m
            out += self._minute_checks(ev)
        elif et == "period_end":
            out.append(self._recap_moment(ev, "half_time" if ev["period"] == 1 else "full_time"))
        return out

    # ------------------------------------------------------------------ moment rules
    def _check_pass(self, ev: dict) -> list[dict]:
        d, out = ev["data"], []
        pid = ev["player"]
        if d["difficulty"] >= LINE_BREAKER_DIFFICULTY and d["progressive_m"] >= 20 and self._ready("line_breaker", 600):
            out.append(self._moment("line_breaker", ev, ev["team"], [pid, d.get("recipient")], {
                "player": self.name(pid), "recipient": self.name(d.get("recipient")),
                "team_name": self.team_names[ev["team"]], "distance_m": round(d["distance_m"]),
                "progressive_m": round(d["progressive_m"]), "difficulty": d["difficulty"],
                "ball_speed_kmh": round(d["ball_speed_kmh"]), "under_pressure": d["under_pressure"],
                "pass_type": d["pass_type"]}, key="line_breaker"))
        if not self._pass_milestone_done and self.pstats[pid]["passes_completed"] >= PASS_MILESTONE:
            self._pass_milestone_done = True
            ps = self.pstats[pid]
            out.append(self._moment("pass_milestone", ev, ev["team"], [pid], {
                "player": self.name(pid), "team_name": self.team_names[ev["team"]],
                "passes_completed": int(ps["passes_completed"]),
                "pass_accuracy_pct": round(100 * ps["passes_completed"] / ps["passes"])}))
        return out

    def _check_shot(self, ev: dict) -> list[dict]:
        d, pid, out = ev["data"], ev["player"], []
        if d["outcome"] == "goal":
            self._last_goal_chain = self._chain_summary(ev)
            return out
        if d["xg"] >= BIG_CHANCE_XG:
            out.append(self._moment("big_chance", ev, ev["team"], [pid], {
                "player": self.name(pid), "team_name": self.team_names[ev["team"]], "xg": round(d["xg"], 2),
                "xg_pct": round(100 * d["xg"]),
                "distance_m": round(d["distance_m"]), "outcome": d["outcome"],
                "shot_speed_kmh": round(d["speed_kmh"]),
                "team_xg": round(self.team[ev["team"]]["xg"], 2),
                "team_goals": self.score[ev["team"]]}))
        elif d["speed_kmh"] >= ROCKET_SHOT_KMH and self._ready("rocket", 300):
            out.append(self._moment("rocket_shot", ev, ev["team"], [pid], {
                "player": self.name(pid), "team_name": self.team_names[ev["team"]],
                "shot_speed_kmh": round(d["speed_kmh"]), "distance_m": round(d["distance_m"]),
                "outcome": d["outcome"], "xg": round(d["xg"], 2)}, key="rocket"))
        return out

    def _chain_summary(self, shot: dict) -> dict:
        pid = shot["possession_id"]
        ch = self.chains.get(pid, {"start": shot["t"], "completed": 0, "first_event": shot})
        first = ch["first_event"]
        # Was the possession won high up the pitch just before (a counter-press regain)?
        regain = None
        for e in reversed(self._window(ch["start"] - 4, ch["start"] + 0.1)):
            if e["type"] == "tackle" and e["team"] == shot["team"] and "x" in e:
                if self.own_x(shot["team"], e["x"]) > 70:
                    regain = e
                break
        return {"passes": ch["completed"], "seconds": round(shot["t"] - ch["start"]),
                "started_own_x": round(self.own_x(shot["team"], first.get("x", 52.5))) if "x" in first else None,
                "regain": regain}

    def _goal_moment(self, ev: dict) -> dict:
        team, pid, d = ev["team"], ev["player"], ev["data"]
        shot = next(e for e in reversed(self.events) if e["type"] == "shot")
        sd = shot["data"]
        chain = self._last_goal_chain or {"passes": 0, "seconds": 0}
        tags = []
        if chain["passes"] >= 8:
            tags.append("patient_buildup")
        if chain.get("regain"):
            tags.append("counterpress_regain")
        if sd["xg"] < 0.05:
            tags.append("low_xg_strike")
        if sd["speed_kmh"] >= ROCKET_SHOT_KMH:
            tags.append("rocket")
        ev_ = {
            "scorer": self.name(pid), "assist": self.name(d.get("assist")),
            "team_name": self.team_names[team], "home_name": self.team_names[self.home],
            "away_name": self.team_names[self.away],
            "score_home": d["score"][self.home], "score_away": d["score"][self.away],
            "xg": round(sd["xg"], 2), "shot_speed_kmh": round(sd["speed_kmh"]),
            "distance_m": round(sd["distance_m"]), "placement": sd.get("placement"),
            "chain_passes": chain["passes"], "chain_seconds": chain["seconds"],
            "why_tags": tags,
        }
        if chain.get("regain"):
            ev_["regain_player"] = self.name(chain["regain"]["player"])
        # Link the goal to a recent tactical shift so the Narrator can explain *why* it happened.
        def favours(m: dict) -> bool:
            e = m["evidence"]
            if m["type"] == "press_shift":
                return (m["team"] != team and e["direction"] == "fading") or (m["team"] == team and e["direction"] == "rising")
            if m["type"] == "momentum_swing":
                return m["team"] == team
            if m["type"] == "rhythm_shift":
                return e["to_label"] == "chaos" and "counterpress_regain" in tags
            return False

        recent = [m for m in self.moments if m["type"] in ("press_shift", "momentum_swing", "rhythm_shift")
                  and ev["t"] - m["t"] <= 900 and favours(m)]
        if recent:
            r = recent[-1]
            ev_["related_moment"] = r["id"]
            ev_["related_type"] = r["type"]
            ev_["related_summary"] = r["evidence"].get("summary")
            for k in ("press_rate_before", "press_rate_now", "pressing_team_name", "direction",
                      "team_name", "threat_share_now", "to_label"):
                if k in r["evidence"]:
                    ev_["related_" + k] = r["evidence"][k]
        players = [pid, d.get("assist")]
        if chain.get("regain"):
            players.append(chain["regain"]["player"])
        return self._moment("goal", ev, team, players, ev_)

    def _card_moment(self, ev: dict) -> dict:
        d = ev["data"]
        return self._moment("card", ev, ev["team"], [ev["player"]], {
            "player": self.name(ev["player"]), "team_name": self.team_names[ev["team"]], "card": d["card"],
            "reason": d.get("reason"), "team_cards": int(self.team[ev["team"]]["cards"])})

    def _check_sprint(self, ev: dict) -> list[dict]:
        d, pid = ev["data"], ev["player"]
        if d["top_speed_kmh"] < TOP_SPEED_TAG_KMH or not self._ready("speed:" + pid, 600):
            return []
        fastest = max((s["top_speed"] for p, s in self.pstats.items()), default=0)
        return [self._moment("top_speed", ev, ev["team"], [pid], {
            "player": self.name(pid), "team_name": self.team_names[ev["team"]],
            "top_speed_kmh": d["top_speed_kmh"], "sprint_distance_m": round(d["distance_m"]),
            "match_fastest": d["top_speed_kmh"] >= fastest,
            "player_sprints": int(self.pstats[pid]["sprints"]),
            "threshold_kmh": TOP_SPEED_TAG_KMH}, key="speed:" + pid)]

    def _sub_moment(self, ev: dict) -> dict:
        d = ev["data"]
        off, on = d["player_off"], d["player_on"]
        ps = self.pstats[off]
        return self._moment("substitution", ev, ev["team"], [on, off], {
            "player_on": self.name(on), "player_off": self.name(off), "team_name": self.team_names[ev["team"]],
            "off_distance_km": round(ps["distance_m"] / 1000, 1), "off_sprints": int(ps["sprints"]),
            "off_pressures": int(ps["pressures"])})

    def _minute_checks(self, ev: dict) -> list[dict]:
        out: list[dict] = []
        t = ev["t"]
        self.series.append({"t": t, "clock": ev["clock"], "minute": ev["minute"],
                            "momentum_home": self.momentum(t), "control_index": self.control(t)["index"]})
        # Distance milestone.
        for pid, s in self.pstats.items():
            if s["distance_m"] >= DISTANCE_MILESTONE_M and pid not in self._crossed_distance:
                self._crossed_distance.add(pid)
                if len(self._crossed_distance) <= 2:
                    team = self.players[pid]["team"]
                    out.append(self._moment("distance_milestone", ev, team, [pid], {
                        "player": self.name(pid), "team_name": self.team_names[team],
                        "distance_km": round(s["distance_m"] / 1000, 1), "milestone_km": DISTANCE_MILESTONE_M // 1000,
                        "rank": len(self._crossed_distance), "sprints": int(s["sprints"]),
                        "pressures": int(s["pressures"])}))
        if t - self._last_check_t < 120 or t < 1200 or ev["clock_s"] >= 5340:
            return out
        self._last_check_t = t
        # Press shift: compare pressing intensity in the last 10 minutes with the match baseline so far.
        for team in (self.home, self.away):
            now, p_now = self.press_rate(team, t - 600, t)
            before, p_bef = self.press_rate(team, 0, t - 600)
            if now is None or before is None or p_now < 20 or p_bef < 40:
                continue
            ratio = now / max(1, before)
            fading = ratio <= 0.62 and before >= 35
            rising = ratio >= 1.45 and now >= 40
            if (fading or rising) and self._ready("press:" + team, 900):
                direction = "fading" if fading else "rising"
                ppda_now, _, _ = self.ppda(team, t - 600, t)
                ppda_before, _, _ = self.ppda(team, 0, t - 600)
                out.append(self._moment("press_shift", ev, team, [], {
                    "pressing_team_name": self.team_names[team], "opponent_name": self.team_names[self.opp(team)],
                    "direction": direction, "press_rate_before": before, "press_rate_now": now,
                    "change_pct": round(100 * (now - before) / before),
                    "ppda_before": ppda_before, "ppda_now": ppda_now, "window_min": 10,
                    "baseline": "match so far",
                    "summary": f"{self.team_short[team]} press {direction}: {now} pressing actions per 100 build-up passes, match baseline {before}"},
                    key="press:" + team))
        # Momentum swing: threat share flips decisively within 10 minutes.
        m_now = self.momentum(t)
        m_then = self.momentum(t - 480)
        for team, share_now, share_then in ((self.home, m_now, m_then), (self.away, 1 - m_now, 1 - m_then)):
            if share_now >= 0.68 and share_then <= 0.5 and self._ready("momentum", 720):
                pos = self.possession_share(t - 600, t)
                out.append(self._moment("momentum_swing", ev, team, [], {
                    "team_name": self.team_names[team], "threat_share_now": round(100 * share_now),
                    "threat_share_before": round(100 * share_then), "possession_10min": pos[team],
                    "threat_window_min": 5, "possession_window_min": 10,
                    "summary": f"momentum swings to {self.team_short[team]}"}, key="momentum"))
        # Rhythm shift: control vs chaos label changes sharply.
        c_now, c_then = self.control(t), self.control(t - 600)
        if c_now["label"] != c_then["label"] and abs(c_now["index"] - c_then["index"]) >= 0.45 \
                and self._ready("rhythm", 900):
            out.append(self._moment("rhythm_shift", ev, None, [], {
                "from_label": c_then["label"], "to_label": c_now["label"],
                "index_before": c_then["index"], "index_now": c_now["index"],
                "switches_per_min_before": c_then["switches_per_min"], "switches_per_min_now": c_now["switches_per_min"],
                "avg_chain_before": c_then["avg_chain"], "avg_chain_now": c_now["avg_chain"],
                "long_ball_pct_now": c_now["long_ball_pct"],
                "summary": f"rhythm shifts from {c_then['label']} to {c_now['label']}"}, key="rhythm"))
        return out

    def _recap_moment(self, ev: dict, mtype: str) -> dict:
        snap = self.snapshot()
        h, a = self.home, self.away
        top_speed = snap["leaders"]["top_speed"]
        top_dist = snap["leaders"]["distance"]
        keys = [m for m in self.moments if m["type"] in ("big_chance", "press_shift", "momentum_swing",
                                                         "rhythm_shift", "card")]
        return self._moment(mtype, ev, None, [top_speed["player"], top_dist["player"]], {
            "home_name": self.team_names[h], "away_name": self.team_names[a],
            "score_home": self.score[h], "score_away": self.score[a],
            "possession_home": snap["possession"][h], "possession_away": snap["possession"][a],
            "shots_home": snap["teams"][h]["shots"], "shots_away": snap["teams"][a]["shots"],
            "xg_home": snap["teams"][h]["xg"], "xg_away": snap["teams"][a]["xg"],
            "pass_acc_home": snap["teams"][h]["pass_accuracy"], "pass_acc_away": snap["teams"][a]["pass_accuracy"],
            "ppda_home": snap["teams"][h]["ppda"], "ppda_away": snap["teams"][a]["ppda"],
            "fastest_player": self.name(top_speed["player"]), "fastest_kmh": top_speed["value"],
            "most_distance_player": self.name(top_dist["player"]), "most_distance_km": round(top_dist["value"], 1),
            "goals": [{"player": m["evidence"]["scorer"], "minute": m["minute"], "team_name": m["team_name"]}
                      for m in self.moments if m["type"] == "goal"],
            "key_moments": [{"id": m["id"], "type": m["type"], "minute": m["minute"],
                             "summary": m["evidence"].get("summary") or m["evidence"].get("scorer")
                             or m["evidence"].get("player")} for m in keys][-8:],
        })

    # ------------------------------------------------------------------ snapshot
    def snapshot(self) -> dict:
        t = self.t
        teams = {}
        for code in (self.home, self.away):
            s = self.team[code]
            ppda_all, _, _ = self.ppda(code, 0, t)
            ppda_10, _, _ = self.ppda(code, t - 600, t)
            teams[code] = {
                "passes": int(s["passes"]),
                "pass_accuracy": round(100 * s["passes_completed"] / s["passes"]) if s["passes"] else 0,
                "shots": int(s["shots"]), "on_target": int(s["on_target"]), "xg": round(s["xg"], 2),
                "ppda": ppda_all, "ppda_10": ppda_10, "pressures": int(s["pressures"]),
                "tackles": int(s["tackles"]), "interceptions": int(s["interceptions"]),
                "recoveries": int(s["recoveries"]), "corners": int(s["corners"]), "fouls": int(s["fouls"]), "cards": int(s["cards"]),
                "final_third_entries": int(s["final_third_entries"]),
                "distance_km": round(s["distance_m"] / 1000, 1), "sprints": int(s["sprints"]),
            }
        players = {}
        for pid, s in self.pstats.items():
            if pid not in self.players:
                continue
            players[pid] = {
                "passes": int(s["passes"]), "passes_completed": int(s["passes_completed"]),
                "touches": int(s["touches"]), "shots": int(s["shots"]), "xg": round(s["xg"], 2),
                "goals": int(s["goals"]), "tackles": int(s["tackles"]), "interceptions": int(s["interceptions"]),
                "pressures": int(s["pressures"]), "sprints": int(s["sprints"]),
                "top_speed": round(s["top_speed"], 1), "distance_km": round(s["distance_m"] / 1000, 2),
                "on_pitch": pid in self.on_pitch,
            }
        top_speed = max(players.items(), key=lambda kv: kv[1]["top_speed"], default=(None, {"top_speed": 0}))
        top_dist = max(players.items(), key=lambda kv: kv[1]["distance_km"], default=(None, {"distance_km": 0}))
        ctl = self.control(t)
        return {
            "t": t, "clock": self.clock, "minute": self.minute, "period": self.period,
            "score": dict(self.score),
            "possession": self.possession_share(0, t),
            "possession_10": self.possession_share(t - 600, t),
            "teams": teams,
            "momentum_home": self.momentum(t),
            "control": ctl,
            "series": self.series[-30:],
            "players": players,
            "leaders": {"top_speed": {"player": top_speed[0], "value": top_speed[1]["top_speed"]},
                        "distance": {"player": top_dist[0], "value": top_dist[1]["distance_km"]}},
        }
