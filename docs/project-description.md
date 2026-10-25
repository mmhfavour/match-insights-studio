# Innovation Studio project page text

Project: https://innovationstudio.microsoft.com/hackathons/insidethegamedeveloperhackathon/project/126997

## Currently saved (23 Oct)

- **Title:** Match Insights Studio
- **Tagline:** A multi-agent AI engine on Azure that turns synthetic football events into explained, personalized, producer-approved broadcast overlays for every fan.
- **Keywords:** multi-agent-system, Microsoft Foundry, Agent Framework, personalizations
- **Challenge:** The Synthetic Match Insights Engine for Premier League Studio
- **Writing code:** Yes
- **Open to join:** Yes (change to No if solo)

## Description to paste at submission (replace the saved one; fill the [brackets])

## Problem
Broadcast graphics show numbers, not reasons. A casual fan and a data-hungry analyst get the same overlay, in one language, and no broadcaster can let an AI publish to air unchecked.

## What it does
Match Insights Studio is one pipeline with five stages, running live:
1. **Ingest**: a seeded synthetic match generator streams football-realistic events (passes, carries, pressures, tackles, shots with xG and speed, sprints, physical load) for fictional clubs.
2. **Interpret**: live stats including xG, PPDA, press rate, pass difficulty, momentum, a control vs chaos index, speed and distance thresholds. Key moments are detected with the evidence behind them.
3. **Explain**: a Narrator agent on Microsoft Foundry says why a moment matters. A goal is linked to the tactical shift that caused it, for example a press that faded four minutes earlier.
4. **Render**: timed, machine-readable overlay JSON (lower thirds, player tags, stat cards, recap cards) synced to the match clock and drawn over a live tactical feed.
5. **Personalize**: a Personalizer agent reshapes each overlay for Analyst, Casual fan or Player focus mode, favourite club, and English, Hindi or Tamil.

A code Verifier rejects any draft with numbers or names not in the evidence, sends it back once with the exact problems, then falls back to a deterministic template so the broadcast never stalls. A human producer approves, edits or rejects overlays before they air, with a full audit trail.

## Category
Best Multi-Agent System: Narrator, Personalizer and Recapper agents with distinct roles, coordinating through a shared moment record, with a verifier handoff that recovers from failures and a human in the loop.

## Technologies
Microsoft Foundry, Microsoft Agent Framework, Azure Container Apps with managed identity, GitHub Copilot, GitHub Actions, Python (FastAPI, WebSockets), JavaScript.

## Try it
- Live: [https://<app>.azurecontainerapps.io/] (viewer), [/producer] (producer desk), [/replay] (self-contained replay)
- Demo video: [YouTube URL]
- Code: [GitHub URL]

## Data
All data is synthetic. Clubs, players and venues are invented.
