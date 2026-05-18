"""
Enhanced Database Models for Football Analytics
SQLAlchemy ORM with SQLite backend
Tracks users, matches, events, and player statistics
"""

import os
from datetime import datetime
from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, Boolean, JSON, Text, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship

# Database setup
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATABASE_PATH = os.path.join(BASE_DIR, "football_offside.db")
DATABASE_URL = f"sqlite:///{DATABASE_PATH}"

engine = create_engine(DATABASE_URL, echo=False, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


class User(Base):
    """User accounts (admin and club managers)"""
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, nullable=False, index=True)
    email = Column(String, unique=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    full_name = Column(String, nullable=True)
    role = Column(String, default="manager")  # "admin" or "manager"
    club_name = Column(String, nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    matches = relationship("Match", back_populates="created_by_user")


class Match(Base):
    """Match/game records"""
    __tablename__ = "matches"
    
    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, nullable=False)
    home_team = Column(String, nullable=False)
    away_team = Column(String, nullable=False)
    date = Column(DateTime, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    created_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    
    # Video & processing
    video_path = Column(String, nullable=True)
    processed_video_path = Column(String, nullable=True)
    status = Column(String, default="pending")  # pending, processing, completed, failed
    
    # Metadata
    total_duration_sec = Column(Float, nullable=True)
    fps = Column(Integer, nullable=True)
    resolution = Column(String, nullable=True)
    
    # Relationships
    created_by_user = relationship("User", back_populates="matches")
    events = relationship("MatchEvent", back_populates="match", cascade="all, delete-orphan")
    player_stats = relationship("PlayerStat", back_populates="match", cascade="all, delete-orphan")


class MatchEvent(Base):
    """Event log (offside detections, fouls, etc.)"""
    __tablename__ = "match_events"
    
    id = Column(Integer, primary_key=True, index=True)
    match_id = Column(Integer, ForeignKey("matches.id"), nullable=False)
    event_type = Column(String, nullable=False)  # "offside", "foul", "goal", etc.
    frame_number = Column(Integer, nullable=False)
    timestamp_sec = Column(Float, nullable=True)
    team = Column(String, nullable=True)  # "team_a" or "team_b"
    player_id = Column(String, nullable=True)  # Track ID from detector
    coordinates = Column(JSON, nullable=True)  # {"x": float, "y": float}
    confidence = Column(Float, nullable=True)
    description = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    match = relationship("Match", back_populates="events")


class PlayerStat(Base):
    """Aggregated player statistics per match"""
    __tablename__ = "player_stats"
    
    id = Column(Integer, primary_key=True, index=True)
    match_id = Column(Integer, ForeignKey("matches.id"), nullable=False)
    player_id = Column(String, nullable=False)  # Track ID from detector
    team = Column(String, nullable=False)  # "team_a" or "team_b"
    player_number = Column(Integer, nullable=True)
    jersey_color = Column(String, nullable=True)
    
    # Statistics
    distance_m = Column(Float, default=0)  # Total distance covered in metres
    avg_speed_mps = Column(Float, default=0)  # Average speed m/s
    max_speed_mps = Column(Float, default=0)  # Max speed m/s
    offside_count = Column(Integer, default=0)  # Times in offside position
    offside_frames = Column(Integer, default=0)  # Frames in offside
    passes = Column(Integer, default=0)
    passes_received = Column(Integer, default=0)
    
    # Relationships
    match = relationship("Match", back_populates="player_stats")


class Detection(Base):
    """Frame-level detection results"""
    __tablename__ = "detections"
    
    id = Column(Integer, primary_key=True, index=True)
    match_id = Column(Integer, nullable=True)
    file_name = Column(String, nullable=False)
    file_type = Column(String, nullable=False)  # "image" or "video"
    upload_timestamp = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    # Detection results
    total_players = Column(Integer, nullable=True)
    goalkeepers = Column(Integer, nullable=True)
    referees = Column(Integer, nullable=True)
    balls = Column(Integer, nullable=True)
    offside_count = Column(Integer, nullable=True)
    offside_frames = Column(Integer, nullable=True)
    
    # Metadata
    processing_time = Column(Float, nullable=True)
    file_size = Column(Integer, nullable=True)
    status = Column(String, default="success")
    error_message = Column(Text, nullable=True)
    output_file = Column(String, nullable=True)
    output_path = Column(String, nullable=True)
    detection_data = Column(JSON, nullable=True)


class Model(Base):
    """Tracks available ML models"""
    __tablename__ = "models"
    
    id = Column(Integer, primary_key=True, index=True)
    model_name = Column(String, unique=True, nullable=False)
    model_type = Column(String, nullable=False)  # "player_detection", "pitch_detection", "offside"
    version = Column(String, nullable=False)
    weight_path = Column(String, nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    last_used = Column(DateTime, nullable=True)


def init_db():
    """Initialize database and create all tables"""
    Base.metadata.create_all(bind=engine)
    print(f"[Database] Initialized at {DATABASE_PATH}")
    _seed_default_data()


def _seed_default_data():
    """Seed database with default data (admin user, etc.)"""
    db = SessionLocal()
    try:
        # Check if admin exists
        admin = db.query(User).filter(User.username == "admin").first()
        if not admin:
            from passlib.context import CryptContext
            pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
            
            admin_user = User(
                username="admin",
                email="admin@football.local",
                hashed_password=pwd_context.hash("admin1234"),
                full_name="Admin User",
                role="admin",
                club_name="System"
            )
            db.add(admin_user)
            db.commit()
            print("[Database] Created default admin user (admin/admin1234)")
    except Exception as e:
        print(f"[Database] Warning during seeding: {e}")
    finally:
        db.close()


def get_db():
    """Dependency for getting database session"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# Helper functions
def insert_detection_record(
    file_name: str,
    file_type: str,
    match_id: int = None,
    total_players: int = None,
    goalkeepers: int = None,
    referees: int = None,
    balls: int = None,
    offside_count: int = None,
    processing_time: float = None,
    file_size: int = None,
    status: str = "success",
    error_message: str = None,
    output_file: str = None,
    output_path: str = None,
    metadata: dict = None,
):
    """Insert detection record"""
    db = SessionLocal()
    try:
        detection = Detection(
            match_id=match_id,
            file_name=file_name,
            file_type=file_type,
            total_players=total_players,
            goalkeepers=goalkeepers,
            referees=referees,
            balls=balls,
            offside_count=offside_count,
            processing_time=processing_time,
            file_size=file_size,
            status=status,
            error_message=error_message,
            output_file=output_file,
            output_path=output_path,
            detection_data=metadata or {},
        )
        db.add(detection)
        db.commit()
        db.refresh(detection)
        return detection
    except Exception as e:
        db.rollback()
        print(f"[Database Error] {e}")
        return None
    finally:
        db.close()


def get_detection_history(limit: int = 20):
    """Get recent detections"""
    db = SessionLocal()
    try:
        records = db.query(Detection).order_by(Detection.upload_timestamp.desc()).limit(limit).all()
        return records
    finally:
        db.close()


def get_stats():
    """Get database statistics"""
    db = SessionLocal()
    try:
        return {
            "total_detections": db.query(Detection).count(),
            "image_detections": db.query(Detection).filter(Detection.file_type == "image").count(),
            "video_detections": db.query(Detection).filter(Detection.file_type == "video").count(),
            "offside_detections": db.query(Detection).filter(Detection.offside_count > 0).count(),
            "total_matches": db.query(Match).count(),
            "total_users": db.query(User).count(),
        }
    finally:
        db.close()

