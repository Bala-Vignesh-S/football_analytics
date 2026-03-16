"""
database.py – SQLite database setup and models using SQLAlchemy.

Tables:
  - users       : Admin and Club Manager accounts (JWT auth)
  - matches     : Match records
  - match_events: Frame-level events (offside, goal, etc.)
  - player_stats: Per-player per-match statistics
"""

from datetime import datetime
from sqlalchemy import (
    create_engine, Column, Integer, String,
    Float, DateTime, ForeignKey, Boolean, Text
)
from sqlalchemy.orm import declarative_base, sessionmaker, relationship

DATABASE_URL = "sqlite:///./football_analytics.db"

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False}
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


# ─── Models ───────────────────────────────────────────────────────────────────

class User(Base):
    __tablename__ = "users"

    id         = Column(Integer, primary_key=True, index=True)
    username   = Column(String, unique=True, nullable=False)
    email      = Column(String, unique=True, nullable=False)
    hashed_pw  = Column(String, nullable=False)
    role       = Column(String, default="manager")   # "admin" | "manager"
    club_name  = Column(String, nullable=True)        # for manager accounts
    created_at = Column(DateTime, default=datetime.utcnow)
    is_active  = Column(Boolean, default=True)

    matches = relationship("Match", back_populates="created_by_user")


class Match(Base):
    __tablename__ = "matches"

    id           = Column(Integer, primary_key=True, index=True)
    title        = Column(String, nullable=False)
    home_team    = Column(String, nullable=False)
    away_team    = Column(String, nullable=False)
    match_date   = Column(DateTime, default=datetime.utcnow)
    video_path   = Column(String, nullable=True)   # Uploaded video file path
    status       = Column(String, default="pending")  # pending|processing|done
    created_by   = Column(Integer, ForeignKey("users.id"))
    created_at   = Column(DateTime, default=datetime.utcnow)

    created_by_user = relationship("User", back_populates="matches")
    events          = relationship("MatchEvent", back_populates="match")
    player_stats    = relationship("PlayerStat", back_populates="match")


class MatchEvent(Base):
    __tablename__ = "match_events"

    id           = Column(Integer, primary_key=True, index=True)
    match_id     = Column(Integer, ForeignKey("matches.id"), nullable=False)
    event_type   = Column(String, nullable=False)   # "offside" | "goal" | "foul"
    frame_number = Column(Integer, nullable=False)
    timestamp_s  = Column(Float, nullable=True)     # seconds into the video
    player_id    = Column(Integer, nullable=True)   # track id of offending player
    team_id      = Column(Integer, nullable=True)
    detail       = Column(Text, nullable=True)       # JSON string for extra info
    created_at   = Column(DateTime, default=datetime.utcnow)

    match = relationship("Match", back_populates="events")


class PlayerStat(Base):
    __tablename__ = "player_stats"

    id              = Column(Integer, primary_key=True, index=True)
    match_id        = Column(Integer, ForeignKey("matches.id"), nullable=False)
    player_track_id = Column(Integer, nullable=False)   # ByteTrack track id
    team_id         = Column(Integer, nullable=True)
    distance_m      = Column(Float, default=0.0)        # Total distance moved (metres)
    avg_speed_ms    = Column(Float, default=0.0)        # Average speed (m/s)
    max_speed_ms    = Column(Float, default=0.0)
    offside_count   = Column(Integer, default=0)
    frames_detected = Column(Integer, default=0)

    match = relationship("Match", back_populates="player_stats")


# ─── Helpers ──────────────────────────────────────────────────────────────────

def init_db():
    """Create all tables and seed an admin user if none exists."""
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        if not db.query(User).filter_by(role="admin").first():
            from passlib.context import CryptContext
            pwd_ctx = CryptContext(schemes=["bcrypt"], deprecated="auto")
            admin = User(
                username  = "admin",
                email     = "admin@football.ai",
                hashed_pw = pwd_ctx.hash("admin1234"),
                role      = "admin",
            )
            db.add(admin)
            db.commit()
            print("[DB] Seeded default admin user: admin / admin1234")
    finally:
        db.close()


def get_db():
    """FastAPI dependency for DB session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
