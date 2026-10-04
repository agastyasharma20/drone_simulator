# SKYSHIELD — AI-Enabled Drone & Counter-Drone Threat Simulation Trainer

**Smart India Hackathon 2026 · PS 26247 · Ministry of Defence / Defence Services Staff College · Robotics & Drones**

A software-only trainer that teaches operators to *detect → classify → decide* against single drones and swarms in day/night, degraded-sensor and urban/rural conditions. Runs in a laptop browser with no special hardware. Inspired by the radar / threat-assessment ideas of [theYsnS/drone-defense-simulator](https://github.com/theYsnS/drone-defense-simulator), rebuilt as a full-stack training platform.

## Requirement coverage

| PS outcome | Implementation |
|---|---|
| Scripted + procedurally generated scenarios | `backend/app/scenarios.py`: 4 scripted drills + seeded procedural generator (day/night, urban/rural, nominal/degraded, single/mixed/swarm) |
| Decision-tree scoring (detection time, classification, engagement) | `backend/app/scoring.py`: server-side, against ground truth stored in the DB |
| After-action review, individual + unit, repeated sessions | `/api/sessions/{id}/aar`, trainee history, unit leaderboard; shown in the AAR tab |
| Adjustable difficulty, anti-rote-learning | Per-trainee adaptive level 1-5 (>=75 up, <45 down), new random layout each run, decoys (birds, friendlies, ghost tracks) |
| Desktop / VR-capable | Desktop browser now; WebXR front-end on the roadmap (the API is client-agnostic) |

## Architecture

```
 Browser (frontend/index.html, Canvas 2D radar PPI)
   |  POST /api/scenarios/generate  -> seeded scenario + session row
   |  (real-time simulation runs client-side)
   |  POST /api/sessions/{id}/complete {per-track calls/actions/timings}
   v
 FastAPI (backend/app) -- scoring.py (decision tree, adaptive level)
   |                      scenarios.py (seeded generator)
   v
 SQLAlchemy -- SQLite (default) | PostgreSQL (docker-compose)
   trainees --< sessions --< track_results
```

## Run

```bash
# local (SQLite)
cd backend && pip install -r requirements-dev.txt
uvicorn app.main:app --reload     # UI + API at http://localhost:8000, docs at /docs

# tests
cd backend && pytest -q

# docker (PostgreSQL)
docker compose up --build         # http://localhost:8000
```

Env: `DATABASE_URL` (default `sqlite:///./skyshield.db`), `CORS_ORIGINS`, `FRONTEND_DIR`.

## API

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/health` | liveness |
| GET | `/api/scenarios/presets` | scripted scenario definitions |
| POST | `/api/scenarios/generate` | create session + scenario (`callsign, unit, mode, terrain, time, sensors, level, seed`) |
| POST | `/api/sessions/{id}/complete` | submit tracks, receive scored AAR (409 if already completed) |
| GET | `/api/sessions/{id}/aar` | re-open a past AAR |
| GET/DELETE | `/api/trainees/{callsign}/history` | trainee trend / reset |
| GET | `/api/units/{unit}/leaderboard` | unit performance |

## Controls

Click blip = tag · `1-6` classify · `R` monitor · `Q` warn · `W` jam (inside warning ring, 6 s cooldown) · `E` intercept (6 rounds) · `Space` pause.

## Scoring

Score = 30% detection time + 30% classification + 40% engagement decision, minus 10 per breach, 15 per fratricide, 3 per wasted engagement. Decision tree: benign -> MONITOR; recon -> WARN (jam acceptable); armed with control link -> JAM; autonomous attacker -> INTERCEPT (jam has no effect).

## Limits and roadmap

Speeds, ranges and hit probabilities are illustrative placeholders, not real system data. The simulation runs client-side; the server holds ground truth and rescoring, but it trusts submitted timings and actions. A server-authoritative sim is a next step. Roadmap: WebXR view, YAML scenario authoring for instructors, ML-assisted classifier "wingman", instructor console, auth/roles, full-session replay.

MIT licensed.
