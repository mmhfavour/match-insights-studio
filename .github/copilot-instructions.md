# Copilot instructions for Match Insights Studio

- Backend is Python 3.12, FastAPI, Microsoft Agent Framework. Frontend is plain HTML, CSS and JavaScript with no build step.
- The pipeline has five stages: ingest (`simulator.py`), interpret (`interpreter.py`), explain and personalize (`agents.py`, `templates.py`), verify (`verifier.py`), render (`pipeline.overlay_record`, `frontend/viewer.js`).
- Agents may only use numbers and names present in a moment's `evidence`. Any new moment type needs: interpreter rule, evidence fields for every number the copy uses, EN/HI/TA templates, and a test that all variants pass `verify`.
- Keep all data synthetic and all clubs and players fictional. Never add real club, league or player names.
- Run `cd backend && python -m pytest -q` before committing.
