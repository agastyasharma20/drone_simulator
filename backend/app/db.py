"""SQLAlchemy models. SQLite by default; set DATABASE_URL for PostgreSQL."""
import os
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import JSON, DateTime, Float, ForeignKey, Integer, String, create_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship, sessionmaker

URL = os.getenv("DATABASE_URL", "sqlite:///./skyshield.db")
engine = create_engine(URL, pool_pre_ping=True,
                       connect_args={"check_same_thread": False} if URL.startswith("sqlite") else {})
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)


def now():
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class Trainee(Base):
    __tablename__ = "trainees"
    id: Mapped[int] = mapped_column(primary_key=True)
    callsign: Mapped[str] = mapped_column(String(24), unique=True, index=True)
    unit: Mapped[str] = mapped_column(String(32), index=True)
    level: Mapped[int] = mapped_column(Integer, default=2)          # adaptive difficulty 1-5
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    sessions: Mapped[list["TrainingSession"]] = relationship(back_populates="trainee", cascade="all, delete-orphan")


class TrainingSession(Base):
    __tablename__ = "sessions"
    id: Mapped[int] = mapped_column(primary_key=True)
    trainee_id: Mapped[int] = mapped_column(ForeignKey("trainees.id"), index=True)
    seed: Mapped[int] = mapped_column(Integer)
    config: Mapped[dict] = mapped_column(JSON)
    spawns: Mapped[list] = mapped_column(JSON)                      # ground truth, kept server-side
    status: Mapped[str] = mapped_column(String(12), default="started")
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    det_pct: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    cls_pct: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    dec_pct: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    breaches: Mapped[int] = mapped_column(Integer, default=0)
    fratricide: Mapped[int] = mapped_column(Integer, default=0)
    waste: Mapped[int] = mapped_column(Integer, default=0)
    level: Mapped[int] = mapped_column(Integer, default=2)
    trainee: Mapped[Trainee] = relationship(back_populates="sessions")
    tracks: Mapped[list["TrackResult"]] = relationship(back_populates="session", cascade="all, delete-orphan")


class TrackResult(Base):
    __tablename__ = "track_results"
    id: Mapped[int] = mapped_column(primary_key=True)
    session_id: Mapped[int] = mapped_column(ForeignKey("sessions.id"), index=True)
    track_no: Mapped[int] = mapped_column(Integer)
    truth: Mapped[str] = mapped_column(String(8))
    intent: Mapped[Optional[str]] = mapped_column(String(8), nullable=True)
    call: Mapped[Optional[str]] = mapped_column(String(8), nullable=True)
    action: Mapped[Optional[str]] = mapped_column(String(8), nullable=True)
    optimal: Mapped[str] = mapped_column(String(8))
    t_detect: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    grade: Mapped[float] = mapped_column(Float)
    outcome: Mapped[str] = mapped_column(String(8))
    session: Mapped[TrainingSession] = relationship(back_populates="tracks")
