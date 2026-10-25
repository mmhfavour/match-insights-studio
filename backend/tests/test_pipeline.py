import asyncio
import json

import pytest

from app.agents import MatchAgents
from app.interpreter import Interpreter
from app.pipeline import DEFAULT_SEED, build_timeline
from app.simulator import generate_match, xg_model
from app.templates import LANGS, render
from app.verifier import verify


@pytest.fixture(scope="module")
def timeline():
    return build_timeline(DEFAULT_SEED)


@pytest.fixture(scope="module")
def roster(timeline):
    return Interpreter(timeline["match"]).players


def test_generator_is_deterministic():
    a = generate_match(DEFAULT_SEED)["events"]
    b = generate_match(DEFAULT_SEED)["events"]
    assert a == b


def test_match_totals_are_football_realistic(timeline):
    final = timeline["final"]
    for code, t in final["teams"].items():
        assert 450 <= t["passes"] <= 850, (code, t["passes"])
        assert 70 <= t["pass_accuracy"] <= 90
        assert 5 <= t["shots"] <= 28
        assert 0.4 <= t["xg"] <= 3.5
        assert 6 <= t["ppda"] <= 20
        assert 95 <= t["distance_km"] <= 125
    assert sum(final["possession"].values()) == 100
    assert final["score"] == {"NVR": 2, "PSM": 1}


def test_xg_model_is_monotonic_with_distance():
    assert xg_model(99, 34) > xg_model(94, 34) > xg_model(84, 34) > xg_model(75, 34)
    assert xg_model(94, 34, header=True) < xg_model(94, 34)


def test_story_moments_are_detected(timeline):
    types = [m["type"] for m in timeline["moments"]]
    assert types.count("goal") == 3
    assert "half_time" in types and "full_time" in types
    goal_62 = next(m for m in timeline["moments"] if m["type"] == "goal" and m["minute"] == "62'")
    assert "low_xg_strike" in goal_62["evidence"]["why_tags"]
    # The equaliser is explained by the press fading just before it.
    assert goal_62["evidence"].get("related_type") == "press_shift"
    assert goal_62["evidence"].get("related_direction") == "fading"
    goal_84 = next(m for m in timeline["moments"] if m["type"] == "goal" and m["minute"] == "84'")
    assert "counterpress_regain" in goal_84["evidence"]["why_tags"]


def test_every_template_variant_passes_the_verifier(timeline, roster):
    assert timeline["stats"]["template_verifier_failures"] == 0
    for m in timeline["moments"]:
        for lang in LANGS:
            for mode in ("analyst", "casual"):
                copy = render(m, mode, lang, "NVR", "Northvale Rovers")
                assert verify(copy, m, roster) == [], (m["type"], mode, lang, copy)


def test_verifier_catches_invented_numbers_names_and_banned_terms(timeline, roster):
    goal = next(m for m in timeline["moments"] if m["type"] == "goal")
    assert any("number 0.93" in e for e in verify({"headline": "Goal", "body": "xG 0.93 strike"}, goal, roster))
    other = next(p for p in roster.values() if p["name"] not in json.dumps(goal["evidence"]))
    assert any("not part of this moment" in e
               for e in verify({"headline": "Goal", "body": f"{other['name']} watched on"}, goal, roster))
    assert any("banned" in e for e in verify({"headline": "Goal", "body": "Great for your bets"}, goal, roster))
    assert any("too long" in e for e in verify({"headline": "x" * 90, "body": "ok"}, goal, roster))


def test_overlay_record_is_timed_and_machine_readable(timeline):
    from app.pipeline import overlay_record

    m = timeline["moments"][0]
    rec = overlay_record(m, render(m), m["audiences"], "analyst|en|-|-")
    for key in ("id", "moment_id", "slot", "t_in", "duration_s", "clock", "headline", "body", "graphic"):
        assert key in rec
    json.dumps(rec)


def _agents(timeline):
    roster = Interpreter(timeline["match"]).players
    names = {"NVR": "Northvale Rovers", "PSM": "Port Saltmere FC"}
    a = MatchAgents(roster, names)
    a.enabled = True  # exercise the agent path with a scripted fake model
    return a


def test_agent_draft_is_repaired_after_verifier_rejection(timeline):
    agents = _agents(timeline)
    goal = next(m for m in timeline["moments"] if m["type"] == "goal")
    replies = iter([
        '{"why": "Patient build-up", "key_numbers": []}',
        '{"headline": "Reyes scores", "body": "A 99 km/h finish"}',            # 99 is invented
        '{"headline": "Reyes scores", "body": "A 13-pass move, finished at 88 km/h."}',
    ])

    async def fake_ask(agent_name, prompt):
        return next(replies)

    agents._ask = fake_ask
    out = asyncio.run(agents.overlay(goal, {"mode": "analyst", "lang": "en"}))
    assert out["source"] == "foundry"
    assert out["attempts"] == 2
    assert agents.metrics["verifier_rejections"] == 1 and agents.metrics["repaired"] == 1


def test_agent_falls_back_to_template_after_two_failures(timeline):
    agents = _agents(timeline)
    goal = next(m for m in timeline["moments"] if m["type"] == "goal")
    replies = iter(['{"why": "x"}', '{"headline": "Bet now", "body": "odds"}', '{"headline": "", "body": ""}'])

    async def fake_ask(agent_name, prompt):
        return next(replies)

    agents._ask = fake_ask
    out = asyncio.run(agents.overlay(goal, {"mode": "casual", "lang": "hi"}))
    assert out["source"] == "template"
    assert out["headline"] == render(goal, "casual", "hi")["headline"]


def test_agent_timeout_falls_back_to_template(timeline):
    agents = _agents(timeline)
    m = timeline["moments"][1]

    async def boom(agent_name, prompt):
        raise asyncio.TimeoutError()

    agents._ask = boom
    out = asyncio.run(agents.overlay(m, {"mode": "analyst", "lang": "ta"}))
    assert out["source"] == "template"
