"""Explain and Personalize: the agent layer, built on Microsoft Agent Framework and Microsoft Foundry.

Three model-backed agents, each with one job and a narrow contract:

  Narrator     moment evidence  -> neutral "why it matters" explanation (JSON)
  Personalizer narration + profile -> on-screen headline and body for one viewer profile (JSON)
  Recapper     half-time / full-time evidence -> short match story (JSON)

They hand off through a shared moment record (the evidence produced by the Interpreter). Every
Personalizer draft goes through the code Verifier; a failed draft is sent back once with the exact
problems, and if it fails again the deterministic template airs instead. If Foundry is not configured
or a call times out, the templates air directly, so the broadcast never stalls.

Configuration (environment):
  FOUNDRY_PROJECT_ENDPOINT   https://<resource>.services.ai.azure.com/api/projects/<project>
  FOUNDRY_MODEL              model deployment name, for example gpt-5-mini
  AGENT_TIMEOUT_S            per-call timeout, default 12
Authentication uses DefaultAzureCredential (az login locally, managed identity on Azure).
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import time

from .templates import render
from .verifier import verify

log = logging.getLogger("agents")

LANG_NAMES = {"en": "English", "hi": "Hindi (Devanagari script)", "ta": "Tamil (Tamil script)"}

NARRATOR_INSTRUCTIONS = """You are the Narrator on a live football broadcast analytics desk.
You receive one match moment as JSON evidence produced by a stats engine. Explain WHY the moment
matters, not just what happened: link it to pressing, momentum, control vs chaos, chance quality,
speed or workload when the evidence supports it.
Rules:
- Use only facts, numbers and names present in the evidence. Never invent a statistic.
- Neutral tone, no betting language, no real clubs or competitions.
- Reply with JSON only: {"why": "<max 2 sentences>", "key_numbers": ["<number with unit>", ...]}"""

PERSONALIZER_INSTRUCTIONS = """You are the Personalizer. You write the on-screen overlay a single viewer sees.
Input: the moment evidence, the Narrator's explanation, and the viewer profile.
Profiles:
- analyst: dense, numeric, tactical vocabulary (xG, PPDA, press rate, progressive metres).
- casual: warm, plain words, at most one number, explain the stakes.
- player: frame everything around the focus player when they are involved.
If the viewer supports a club, acknowledge what the moment means for that club in a few words.
Write in the requested language. Keep player and club names in Latin script exactly as given.
Rules:
- Every number you write must appear in the evidence. Do not compute new numbers.
- Only name players that appear in the evidence.
- headline: max 60 characters. body: max 200 characters.
- No betting language, no real clubs or competitions.
Reply with JSON only: {"headline": "...", "body": "..."}"""

RECAPPER_INSTRUCTIONS = """You are the Recapper. Turn half-time or full-time evidence into a short match story
for a studio graphic: the result, the turning point, and one standout performer.
Use only the numbers and names in the evidence. Write in the requested language and register.
Reply with JSON only: {"headline": "<max 60 chars>", "body": "<max 220 chars>"}"""


def _extract_json(text: str) -> dict:
    m = re.search(r"\{.*\}", text or "", re.S)
    if not m:
        raise ValueError("no JSON object in model reply")
    return json.loads(m.group(0))


def profile_key(profile: dict) -> str:
    mode = profile.get("mode", "analyst")
    lang = profile.get("lang", "en")
    club = profile.get("club") or "-"
    player = profile.get("player") or "-"
    return f"{mode}|{lang}|{club}|{player if mode == 'player' else '-'}"


class MatchAgents:
    def __init__(self, roster: dict[str, dict], team_names: dict[str, str]):
        self.roster = roster
        self.team_names = team_names
        self.timeout = float(os.getenv("AGENT_TIMEOUT_S", "12"))
        self.enabled = False
        self.model = os.getenv("FOUNDRY_MODEL") or os.getenv("FOUNDRY_MODEL_DEPLOYMENT")
        self._narration_cache: dict[str, dict] = {}
        self._overlay_cache: dict[tuple[str, str], dict] = {}
        self.metrics = {"llm_calls": 0, "llm_failures": 0, "verifier_rejections": 0, "repaired": 0,
                        "template_fallbacks": 0}
        endpoint = os.getenv("FOUNDRY_PROJECT_ENDPOINT")
        if endpoint and self.model and os.getenv("AGENTS_DISABLED") != "1":
            try:
                from agent_framework import Agent
                from agent_framework.foundry import FoundryChatClient
                from azure.identity.aio import DefaultAzureCredential

                client = FoundryChatClient(project_endpoint=endpoint, model=self.model,
                                           credential=DefaultAzureCredential())
                self.narrator = Agent(client, NARRATOR_INSTRUCTIONS, name="Narrator")
                self.personalizer = Agent(client, PERSONALIZER_INSTRUCTIONS, name="Personalizer")
                self.recapper = Agent(client, RECAPPER_INSTRUCTIONS, name="Recapper")
                self.enabled = True
                log.info("Foundry agents enabled with model %s", self.model)
            except Exception as exc:  # pragma: no cover - depends on Azure setup
                log.warning("Foundry agents unavailable, using templates: %s", exc)

    @property
    def mode(self) -> str:
        return f"foundry:{self.model}" if self.enabled else "templates"

    # ------------------------------------------------------------------ model calls
    async def _ask(self, agent_name: str, prompt: str) -> str:
        """Run one agent turn. Tests replace this method to exercise the repair loop offline."""
        agent = getattr(self, agent_name)
        self.metrics["llm_calls"] += 1
        resp = await asyncio.wait_for(agent.run(prompt), timeout=self.timeout)
        return resp.text

    async def narrate(self, moment: dict) -> dict | None:
        if moment["id"] in self._narration_cache:
            return self._narration_cache[moment["id"]]
        prompt = json.dumps({"moment_type": moment["type"], "minute": moment["minute"],
                             "team": moment.get("team_name"), "evidence": moment["evidence"],
                             "context": moment["context"]}, ensure_ascii=False)
        try:
            out = _extract_json(await self._ask("narrator", prompt))
            self._narration_cache[moment["id"]] = out
            return out
        except Exception as exc:
            self.metrics["llm_failures"] += 1
            log.warning("Narrator failed on %s: %s", moment["id"], exc)
            return None

    # ------------------------------------------------------------------ public API
    async def overlay(self, moment: dict, profile: dict) -> dict:
        """Produce the verified overlay copy for one moment and one viewer profile."""
        key = (moment["id"], profile_key(profile))
        if key in self._overlay_cache:
            return self._overlay_cache[key]
        started = time.perf_counter()
        mode, lang, club = profile.get("mode", "analyst"), profile.get("lang", "en"), profile.get("club")
        template = render(moment, mode, lang, club, self.team_names.get(club) if club else None)
        result = {**template, "source": "template", "attempts": 0, "verifier": []}

        if self.enabled:
            result = await self._agent_overlay(moment, profile, template)
        if result["source"] == "template" and self.enabled:
            self.metrics["template_fallbacks"] += 1
        result["latency_ms"] = round((time.perf_counter() - started) * 1000)
        self._overlay_cache[key] = result
        return result

    async def _agent_overlay(self, moment: dict, profile: dict, template: dict) -> dict:
        is_recap = moment["type"] in ("half_time", "full_time")
        narration = None if is_recap else await self.narrate(moment)
        if narration is None and not is_recap:
            return {**template, "source": "template", "attempts": 0, "verifier": ["narrator unavailable"]}
        focus = profile.get("player")
        request = {
            "viewer_profile": {
                "mode": profile.get("mode", "analyst"),
                "language": LANG_NAMES.get(profile.get("lang", "en"), "English"),
                "supports_club": self.team_names.get(profile.get("club")) if profile.get("club") else None,
                "focus_player": self.roster[focus]["name"] if focus in self.roster else None,
            },
            "moment_type": moment["type"], "minute": moment["minute"], "evidence": moment["evidence"],
            "narration": narration,
        }
        agent = "recapper" if is_recap else "personalizer"
        problems: list[str] = []
        for attempt in (1, 2):
            prompt = json.dumps(request, ensure_ascii=False)
            if problems:
                prompt += "\nYour previous draft was rejected by the verifier: " + "; ".join(problems) + \
                          ". Fix exactly these problems and reply with JSON only."
            try:
                draft = _extract_json(await self._ask(agent, prompt))
            except Exception as exc:
                self.metrics["llm_failures"] += 1
                log.warning("%s failed on %s: %s", agent, moment["id"], exc)
                return {**template, "source": "template", "attempts": attempt, "verifier": [f"model error: {exc}"]}
            draft = {"headline": str(draft.get("headline", "")).strip(), "body": str(draft.get("body", "")).strip()}
            problems = verify(draft, moment, self.roster)
            if not problems:
                if attempt == 2:
                    self.metrics["repaired"] += 1
                return {**draft, "source": "foundry", "attempts": attempt, "verifier": [],
                        "why": (narration or {}).get("why")}
            self.metrics["verifier_rejections"] += 1
        return {**template, "source": "template", "attempts": 2, "verifier": problems}
