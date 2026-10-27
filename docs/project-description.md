# Innovation Studio project page text

Project: https://innovationstudio.microsoft.com/hackathons/insidethegamedeveloperhackathon/project/126997

## Fields

- **Title:** Match Insights Studio
- **Tagline:** A multi-agent engine that turns synthetic football events into explained, personalized, producer-approved broadcast overlays for every fan.
- **Keywords:** multi-agent-system, Microsoft Agent Framework, Microsoft Foundry, personalization, broadcast overlays
- **Challenge:** The Synthetic Match Insights Engine for Premier League Studio
- **Open to join:** No (solo)
- **Code repository:** https://gitlab.com/orbilab/match-insights-studio

## Description (paste as is; fill the video URL)

## Problem
Broadcast graphics show numbers, not reasons. A casual fan and a data-hungry analyst get the same overlay, in one language, and no broadcaster can let an AI publish to air unchecked.

## What it does
Match Insights Studio is one pipeline with five stages:
1. **Ingest**: a seeded synthetic match generator streams football-realistic events (passes, carries, pressures, tackles, shots with xG and speed, sprints, physical load) for two invented clubs.
2. **Interpret**: live stats including xG, PPDA, press rate, pass difficulty, momentum, a control vs chaos index, and speed and distance thresholds. Key moments are detected with the evidence behind them.
3. **Explain**: a Narrator agent says why a moment matters. A goal is linked to the tactical shift that caused it, for example a press that faded four minutes earlier. **Goal analysis** rebuilds every shot back to where the move began and names what created it beyond the assist: counterattacks, high regains, short passing sequences, set pieces, box entries, half-space attacks, third-man runs, one-twos, switches, line-breaking passes, second balls, numerical overloads (from an estimated freeze frame of all 22 players) and time and space for the finisher.
4. **Render**: timed, machine-readable overlay JSON (lower thirds, player tags, stat cards, recap cards) synced to the match clock and drawn over a tactical feed.
5. **Personalize**: a Personalizer agent reshapes each overlay for Analyst, Casual fan or Player focus mode, favourite club, and English, Hindi or Tamil.

A code Verifier rejects any draft with numbers or names not in the evidence, sends it back once with the exact problems, then falls back to a deterministic template so the broadcast never stalls. A human producer approves, edits or rejects overlays before they air, with a full audit trail.

## Category
Best Multi-Agent System: Narrator, Personalizer and Recapper agents with distinct roles and JSON contracts, coordinating through a shared moment record, with a verifier handoff that recovers from failures and a human producer in the loop.

## Technologies
Microsoft Agent Framework with FoundryChatClient (Microsoft Foundry), Python (FastAPI, WebSockets), plain JavaScript, Azure Container Apps infrastructure as Bicep with managed identity, GitHub Copilot.

## Status, honestly
The demo runs in template mode: the whole pipeline with deterministic, verifier-checked copy in three languages. The agents are implemented and their repair loop and fallbacks are tested with a stand-in model, but we had no Azure subscription during the hackathon, so they have not run against a live Foundry deployment and the app is not hosted on Azure. Two environment variables switch the agents on.

## Try it
- Replay (single page, no install): https://claude.ai/artifact/KtRhVKYyWpQM9X1HqxLqbL
- Demo video: [YouTube URL]
- Code: https://gitlab.com/orbilab/match-insights-studio
- Run locally: `cd backend && pip install -r requirements.txt && python -m uvicorn app.server:app --port 8000`, then open `/` (viewer), `/producer` (producer desk), `/replay`.

## Data
All data is synthetic. Clubs, players and venues are invented.
