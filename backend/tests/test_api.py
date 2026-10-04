from fastapi.testclient import TestClient

from app import scenarios, scoring
from app.main import app

client = TestClient(app)


def test_seed_is_deterministic():
    a, b = scenarios.build(seed=42, level=3), scenarios.build(seed=42, level=3)
    assert a == b
    assert a != scenarios.build(seed=43, level=3)


def test_grade_table():
    assert scoring.grade("fr", None, "int") == -1.0      # fratricide
    assert scoring.grade("bird", None, None) == 1.0      # implicit monitor
    assert scoring.grade("lm", "attack", "jam") == .1    # jam useless on autonomous drone
    assert scoring.optimal("quad", "recon") == "warn"
    assert scoring.optimal("lm", "attack") == "int"


def _play(spawns, perfect=True, breach=False):
    out = []
    for s in spawns:
        opt = scoring.optimal(s["type"], s["intent"])
        hostile_attack = s["intent"] == "attack"
        out.append(dict(id=s["id"], call=s["type"] if perfect else None, act=opt if perfect else None,
                        ts=1.0, td=2.0 if perfect else None,
                        outcome="breach" if breach and hostile_attack else "neut" if hostile_attack else "left"))
    return out


def test_full_flow_perfect_and_adaptive_level():
    r = client.post("/api/scenarios/generate", json=dict(callsign="t-1", unit="TEST", mode="mixed", seed=7))
    assert r.status_code == 200
    d = r.json()
    res = client.post(f"/api/sessions/{d['session_id']}/complete", json=dict(tracks=_play(d["spawns"])))
    assert res.status_code == 200
    m = res.json()["summary"]
    assert m["score"] >= 90 and m["next_level"] == 3 and m["rank"] == "Air-Defence Ace"
    assert client.post(f"/api/sessions/{d['session_id']}/complete", json=dict(tracks=[])).status_code == 409
    assert client.get(f"/api/sessions/{d['session_id']}/aar").json()["leaderboard"][0]["callsign"] == "T-1"


def test_bad_play_scores_low_and_drops_level():
    d = client.post("/api/scenarios/generate", json=dict(callsign="rookie", unit="TEST", mode="swarm", seed=9)).json()
    m = client.post(f"/api/sessions/{d['session_id']}/complete",
                    json=dict(tracks=_play(d["spawns"], perfect=False, breach=True))).json()["summary"]
    assert m["score"] < 45 and m["breaches"] > 0 and m["next_level"] == 1
    assert client.get("/api/trainees/rookie/history").json()["level"] == 1


def test_validation_and_misc():
    assert client.post("/api/scenarios/generate", json=dict(level="9")).status_code == 422
    assert client.post("/api/sessions/99999/complete", json=dict(tracks=[])).status_code == 404
    assert client.get("/api/health").json() == dict(status="ok")
    assert "swarm" in client.get("/api/scenarios/presets").json()
    assert client.get("/api/units/TEST/leaderboard").status_code == 200
