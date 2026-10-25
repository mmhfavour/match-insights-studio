import os

os.environ["AUTOSTART"] = "0"
os.environ["REPLAY_SPEED"] = "240"
os.environ["AUTO_APPROVE_DELAY_S"] = "0.2"

from fastapi.testclient import TestClient  # noqa: E402

from app.server import app  # noqa: E402


def test_health_and_replay_page():
    with TestClient(app) as c:
        assert c.get("/api/health").json()["ok"] is True
        r = c.get("/replay")
        assert r.status_code == 200 and "MIS_TIMELINE" in r.text


def test_viewer_receives_personalized_overlays():
    with TestClient(app) as c:
        with c.websocket_connect("/ws/viewer") as ws:
            hello = ws.receive_json()
            assert hello["type"] == "hello" and hello["match"]["synthetic"] is True
            ws.send_json({"type": "profile", "profile": {"mode": "casual", "lang": "hi", "club": "NVR"}})
            overlay = None
            for _ in range(20000):
                msg = ws.receive_json()
                if msg["type"] == "overlay":
                    overlay = msg["overlay"]
                    break
            assert overlay is not None
            assert overlay["profile"].startswith("casual|hi|NVR")
            for key in ("t_in", "duration_s", "slot", "headline", "body", "evidence"):
                assert key in overlay
