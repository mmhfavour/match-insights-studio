# CLAUDE.md: Match Insights Studio

Hackathon entry for the Microsoft and Premier League **Inside the Game: Developer Hackathon** (2026).
Owner: Mohammed Hamza (solo). Read `docs/HANDOFF.md` first for full context, status and the remaining plan.

## Hard deadline

- Official rule: 11:59 PM PT, Tue 27 Oct 2026 = **12:29 PM IST, Wed 28 Oct**.
- A reminder email said "11:59 a.m. PT" (= 12:29 AM IST, 28 Oct). Plan to **submit by 6 PM IST on 27 Oct** so both readings are met.
- Judging starts 9:00 AM PT on 27 Oct, before submissions close.

## What this is

One pipeline with five stages (the challenge's own wording): ingest synthetic match events, interpret them into stats and moments, explain why a moment matters, render timed overlays, and personalize them per viewer (Analyst, Casual fan, Player focus; favourite club; English, Hindi, Tamil). A code Verifier gates every agent draft, and a human Producer Desk approves, edits or rejects overlays before they air.

Target category: **Best Multi-Agent System**.

See `docs/` for the hackathon context: `HANDOFF.md` (status, links, plan), `challenge-brief.md`, `research-report.md`, `project-description.md`, `demo-video-script.md`.

## Layout

```
backend/app/
  teams.py         fictional clubs and squads (Northvale Rovers NVR, Port Saltmere FC PSM)
  simulator.py     seeded match generator; scripted story beats; CLI: python -m app.simulator --seed 21
  interpreter.py   stats (xG, PPDA, press rate, momentum, control vs chaos) and moment detection with evidence
  buildup.py       goal/chance build-up analysis: origin of the move, patterns (counterattack, third-man run, half-space, overload...), freeze frame
  templates.py     deterministic EN/HI/TA copy for every moment type and mode; the fallback that always airs
  verifier.py      code gate: every number and player name must trace to evidence; length and banned terms
  agents.py        Narrator, Personalizer, Recapper on Microsoft Agent Framework + FoundryChatClient; repair loop
  pipeline.py      Director (what airs, for whom), overlay record contract, offline timeline builder
  server.py        FastAPI + WebSockets: /ws/viewer, /ws/producer, /api/*, /replay, /producer
  static_build.py  single-file replay page with every overlay variant inlined
backend/tests/     pytest (14 tests)
frontend/          plain HTML/CSS/JS, no build step: index.html + viewer.js + pitch.js, producer.html + producer.js
infra/main.bicep   Container Apps, ACR, managed identity, Log Analytics
scripts/deploy.sh  one-command az containerapp up + identity + Azure AI User role
scripts/build_demo.py  writes dist/replay.html
docs/              handoff, research, challenge brief, project page text, demo script
```

## Commands

```bash
cd backend
pip install -r requirements.txt
python -m pytest -q                                   # must stay green
python -m uvicorn app.server:app --reload --port 8000 # viewer /, producer /producer, replay /replay
python ../scripts/build_demo.py                       # dist/replay.html
```

Env vars (see `.env.example`): `FOUNDRY_PROJECT_ENDPOINT`, `FOUNDRY_MODEL`, `AGENT_TIMEOUT_S`, `MATCH_SEED` (default 21), `REPLAY_SPEED`, `AUTO_APPROVE`, `AUTO_APPROVE_DELAY_S`, `LOOP_REPLAY`, `AUTOSTART`. Without Foundry vars the app runs in template mode. Auth is `DefaultAzureCredential` (az login locally, managed identity on Azure).

## Rules for changes

- **Synthetic only.** Never add real clubs, leagues, players, crests or footage. The verifier bans real club names and "premier league" in overlay copy; the demo video must not show league or club marks or use copyrighted music.
- **Evidence contract.** Agents and templates may only state numbers and names present in a moment's `evidence`. A new moment type needs: an interpreter rule, evidence fields for every number the copy uses, EN/HI/TA templates, and a test that every variant passes `verify`.
- **Never stall the broadcast.** Every model call has a timeout and falls back to templates.
- Keep the seed-21 storyline intact (goals 19', 62', 84'; press fade before 62'; counter-press regain at 84'). Tests assert it.
- Keep the frontend dependency-free (no bundler).
- State is in memory: run one replica.
