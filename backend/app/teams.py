"""Fictional clubs and squads. Every name here is invented; none refer to real clubs or players."""

from __future__ import annotations

from dataclasses import dataclass, field

# Base positions in the team's own attacking frame: own goal at x=0, opponent goal at x=105.
FORMATIONS: dict[str, list[tuple[str, float, float]]] = {
    "4-3-3": [
        ("GK", 5, 34), ("RB", 30, 9), ("CB", 21, 24), ("CB", 21, 44), ("LB", 30, 59),
        ("DM", 38, 34), ("CM", 50, 22), ("CM", 50, 46),
        ("RW", 73, 10), ("ST", 80, 34), ("LW", 73, 58),
    ],
    "4-2-3-1": [
        ("GK", 5, 34), ("RB", 28, 9), ("CB", 19, 25), ("CB", 19, 43), ("LB", 28, 59),
        ("DM", 37, 26), ("DM", 37, 42),
        ("RW", 62, 11), ("AM", 64, 34), ("LW", 62, 57), ("ST", 78, 34),
    ],
}

# Typical top speeds (km/h) by role, before individual variation.
ROLE_TOP_SPEED = {"GK": 27.5, "CB": 31.5, "RB": 33.5, "LB": 33.5, "DM": 31.0, "CM": 31.5,
                  "AM": 32.0, "RW": 34.5, "LW": 34.5, "ST": 33.5}
# Metres covered per minute of play by role (elite averages sit around 105 to 125).
ROLE_WORK_RATE = {"GK": 58, "CB": 102, "RB": 112, "LB": 112, "DM": 119, "CM": 124,
                  "AM": 118, "RW": 113, "LW": 113, "ST": 107}


@dataclass
class Player:
    id: str
    team: str
    number: int
    name: str
    short: str
    role: str
    base_x: float
    base_y: float
    top_speed: float
    work_rate: float
    on_pitch: bool = True

    def public(self) -> dict:
        return {"id": self.id, "team": self.team, "number": self.number, "name": self.name,
                "short": self.short, "role": self.role, "base_x": self.base_x, "base_y": self.base_y}


@dataclass
class Team:
    code: str
    name: str
    short: str
    color: str
    alt_color: str
    formation: str
    press: float        # 0..1 pressing intensity high up the pitch
    quality: float      # 0..1 technical passing quality
    directness: float   # 0..1 share of long, vertical passes
    shot_bias: float    # multiplier on willingness to shoot
    players: list[Player] = field(default_factory=list)
    bench: list[Player] = field(default_factory=list)

    def on_pitch(self) -> list[Player]:
        return [p for p in self.players if p.on_pitch]

    def by_number(self, number: int) -> Player:
        for p in self.players + self.bench:
            if p.number == number:
                return p
        raise KeyError(f"{self.code} has no #{number}")

    def public(self) -> dict:
        return {"code": self.code, "name": self.name, "short": self.short, "color": self.color,
                "alt_color": self.alt_color, "formation": self.formation,
                "players": [p.public() for p in self.players],
                "bench": [p.public() for p in self.bench]}


_SQUADS = {
    "NVR": {
        "name": "Northvale Rovers", "short": "Northvale", "color": "#E4572E", "alt": "#FFD8C9",
        "formation": "4-3-3", "press": 0.82, "quality": 0.885, "directness": 0.22, "shot_bias": 1.05,
        "xi": [(1, "Tomas Brevik"), (2, "Kofi Mensah-Hale"), (5, "Ruairi Dunne"), (6, "Jonas Ekland"),
               (3, "Sami Haddad"), (4, "Elliot Marsh"), (8, "Davi Okonkwo"), (10, "Luca Ferrante"),
               (7, "Arjun Varma"), (9, "Callum Reyes"), (11, "Theo Lindqvist")],
        "bench": [(14, "Idris Bello", "CM"), (17, "Mateo Quiroga", "RW"), (19, "Finn Albright", "ST")],
    },
    "PSM": {
        "name": "Port Saltmere FC", "short": "Saltmere", "color": "#2E86DE", "alt": "#CFE5FF",
        "formation": "4-2-3-1", "press": 0.48, "quality": 0.855, "directness": 0.38, "shot_bias": 1.0,
        "xi": [(1, "Wiktor Nowak"), (2, "Ade Coleman"), (4, "Henrik Saar"), (5, "Marius Okafor"),
               (3, "Yusuf Demir"), (6, "Pablo Serrano"), (8, "Kenji Arata"),
               (7, "Nico Varela"), (10, "Ravi Chandran"), (11, "Malik Osei"), (9, "Owen Kerrigan")],
        "bench": [(15, "Leon Achterberg", "DM"), (18, "Bruno Tavares", "LW"), (20, "Sean Doyle", "ST")],
    },
}


def _short(name: str) -> str:
    return name.split(" ")[-1]


def build_teams(seed: int = 7) -> dict[str, Team]:
    """Build both squads. Individual speed and work rate vary deterministically by seed."""
    import random

    rng = random.Random(seed * 101 + 3)
    teams: dict[str, Team] = {}
    for code, spec in _SQUADS.items():
        t = Team(code=code, name=spec["name"], short=spec["short"], color=spec["color"],
                 alt_color=spec["alt"], formation=spec["formation"], press=spec["press"],
                 quality=spec["quality"], directness=spec["directness"], shot_bias=spec["shot_bias"])
        for (number, name), (role, bx, by) in zip(spec["xi"], FORMATIONS[spec["formation"]]):
            t.players.append(Player(
                id=f"{code}-{number}", team=code, number=number, name=name, short=_short(name), role=role,
                base_x=bx, base_y=by,
                top_speed=round(ROLE_TOP_SPEED[role] + rng.uniform(-0.8, 1.6), 1),
                work_rate=ROLE_WORK_RATE[role] * rng.uniform(0.95, 1.06)))
        for number, name, role in spec["bench"]:
            t.bench.append(Player(
                id=f"{code}-{number}", team=code, number=number, name=name, short=_short(name), role=role,
                base_x=0, base_y=0, top_speed=round(ROLE_TOP_SPEED[role] + rng.uniform(-0.5, 1.2), 1),
                work_rate=ROLE_WORK_RATE[role] * rng.uniform(0.98, 1.06), on_pitch=False))
        teams[code] = t
    # Story-critical speed: the Saltmere right winger is the quickest player on the pitch.
    teams["PSM"].by_number(7).top_speed = 35.4
    return teams
