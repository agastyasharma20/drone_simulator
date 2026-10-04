"""SKYSHIELD API: scenario generation, authoritative scoring, AAR, unit analytics."""
import os
from pathlib import Path
from typing import Literal, Optional

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from . import scenarios, scoring
from .db import Base, SessionLocal, TrackResult, Trainee, TrainingSession, engine, now

Base.metadata.create_all(engine)
app = FastAPI(title="SKYSHIELD C-UAS Threat Simulation Trainer API", version="1.0.0")
app.add_middleware(CORSMiddleware, allow_origins=os.getenv("CORS_ORIGINS", "*").split(","),
                   allow_methods=["*"], allow_headers=["*"])


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


class GenReq(BaseModel):
    callsign: str = Field("TRAINEE", min_length=1, max_length=24, pattern=r"^[\w\- ]+$")
    unit: str = Field("UNIT-1", min_length=1, max_length=32)
    mode: Literal["single", "mixed", "swarm", "rand"] = "mixed"
    terrain: Literal["rural", "urban", "rand"] = "rural"
    time: Literal["day", "night", "rand"] = "day"
    sensors: Literal["nom", "deg", "rand"] = "nom"
    level: str = Field("auto", pattern=r"^(auto|[1-5])$")
    seed: Optional[int] = Field(None, ge=1, le=2_000_000_000)


class TrackIn(BaseModel):
    id: int
    call: Optional[Literal["quad", "fw", "lm", "bird", "fr", "cl"]] = None
    act: Optional[Literal["mon", "warn", "jam", "int"]] = None
    ts: Optional[float] = Field(None, ge=0, le=600)
    td: Optional[float] = Field(None, ge=0, le=600)
    outcome: Literal["act", "neut", "breach", "left", "gone"]


class CompleteReq(BaseModel):
    tracks: list[TrackIn] = Field(max_length=300)


def _board(db: Session, unit: str):
    q = (select(Trainee.callsign, func.count(TrainingSession.id), func.avg(TrainingSession.score))
         .select_from(Trainee).join(TrainingSession, TrainingSession.trainee_id == Trainee.id)
         .where(Trainee.unit == unit, TrainingSession.status == "completed")
         .group_by(Trainee.callsign).order_by(func.avg(TrainingSession.score).desc()))
    return [dict(callsign=c, sessions=n, avg=round(a or 0)) for c, n, a in db.execute(q)]


def _history(db: Session, trainee_id: int, limit=12):
    q = (select(TrainingSession).where(TrainingSession.trainee_id == trainee_id, TrainingSession.status == "completed")
         .order_by(TrainingSession.id.desc()).limit(limit))
    return [dict(session_id=s.id, score=s.score, level=s.level, det_pct=s.det_pct, cls_pct=s.cls_pct,
                 dec_pct=s.dec_pct, seed=s.seed, mode=s.config.get("mode"),
                 when=s.completed_at.isoformat() if s.completed_at else None) for s in db.scalars(q)][::-1]


def _aar(db: Session, s: TrainingSession):
    rows = db.scalars(select(TrackResult).where(TrackResult.session_id == s.id).order_by(TrackResult.track_no)).all()
    n = s.trainee
    avg_dt = [r.t_detect for r in rows if r.t_detect is not None]
    return dict(
        summary=dict(session_id=s.id, score=s.score, rank=scoring.rank(s.score or 0), det_pct=s.det_pct,
                     cls_pct=s.cls_pct, dec_pct=s.dec_pct, breaches=s.breaches, fratricide=s.fratricide,
                     waste=s.waste, det_avg_s=round(sum(avg_dt) / len(avg_dt), 2) if avg_dt else None,
                     level=s.level, next_level=n.level, seed=s.seed, config=s.config),
        tracks=[dict(id=r.track_no, truth=r.truth, intent=r.intent, call=r.call, action=r.action,
                     optimal=r.optimal, t_detect=r.t_detect, grade=r.grade, outcome=r.outcome) for r in rows],
        history=_history(db, n.id), leaderboard=_board(db, n.unit), trainee=dict(callsign=n.callsign, unit=n.unit))


@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.get("/api/scenarios/presets")
def presets():
    return scenarios.PRESETS


@app.post("/api/scenarios/generate")
def generate(req: GenReq, db: Session = Depends(get_db)):
    cs = req.callsign.strip().upper()
    tr = db.scalar(select(Trainee).where(Trainee.callsign == cs))
    if tr is None:
        tr = Trainee(callsign=cs, unit=req.unit.strip(), level=2)
        db.add(tr)
    tr.unit = req.unit.strip()
    level = tr.level if req.level == "auto" else int(req.level)
    sc = scenarios.build(req.mode, req.terrain, req.time, req.sensors, level, req.seed)
    s = TrainingSession(trainee=tr, seed=sc["config"]["seed"], config=sc["config"], spawns=sc["spawns"], level=level)
    db.add(s)
    db.commit()
    return dict(session_id=s.id, trainee=dict(callsign=cs, unit=tr.unit, level=tr.level), **sc)


@app.post("/api/sessions/{sid}/complete")
def complete(sid: int, body: CompleteReq, db: Session = Depends(get_db)):
    s = db.get(TrainingSession, sid)
    if s is None:
        raise HTTPException(404, "session not found")
    if s.status == "completed":
        raise HTTPException(409, "session already completed")
    ev = scoring.evaluate(s.spawns, [t.model_dump() for t in body.tracks], s.level)
    s.status, s.completed_at, s.score = "completed", now(), ev["score"]
    s.det_pct, s.cls_pct, s.dec_pct = ev["det_pct"], ev["cls_pct"], ev["dec_pct"]
    s.breaches, s.fratricide, s.waste = ev["breaches"], ev["fratricide"], ev["waste"]
    s.trainee.level = ev["next_level"]
    for r in ev["rows"]:
        db.add(TrackResult(session_id=s.id, track_no=r["id"], truth=r["truth"], intent=r["intent"], call=r["call"],
                           action=r["action"], optimal=r["optimal"], t_detect=r["t_detect"], grade=r["grade"],
                           outcome=r["outcome"]))
    db.commit()
    return _aar(db, s)


@app.get("/api/sessions/{sid}/aar")
def aar(sid: int, db: Session = Depends(get_db)):
    s = db.get(TrainingSession, sid)
    if s is None or s.status != "completed":
        raise HTTPException(404, "no completed session")
    return _aar(db, s)


@app.get("/api/trainees/{callsign}/history")
def history(callsign: str, db: Session = Depends(get_db)):
    tr = db.scalar(select(Trainee).where(Trainee.callsign == callsign.upper()))
    if tr is None:
        raise HTTPException(404, "unknown trainee")
    return dict(callsign=tr.callsign, unit=tr.unit, level=tr.level, sessions=_history(db, tr.id, 60))


@app.delete("/api/trainees/{callsign}/history", status_code=204)
def clear_history(callsign: str, db: Session = Depends(get_db)):
    tr = db.scalar(select(Trainee).where(Trainee.callsign == callsign.upper()))
    if tr:
        for s in list(tr.sessions):
            db.delete(s)
        tr.level = 2
        db.commit()


@app.get("/api/units/{unit}/leaderboard")
def leaderboard(unit: str, db: Session = Depends(get_db)):
    return _board(db, unit)


FRONTEND = Path(os.getenv("FRONTEND_DIR", Path(__file__).resolve().parents[2] / "frontend"))
if FRONTEND.is_dir():
    app.mount("/", StaticFiles(directory=FRONTEND, html=True), name="ui")
