"""
server.py – Main FastAPI application.

Endpoints:
  POST /auth/register    – Club manager self-registration
  POST /auth/login       – Returns JWT access token
  GET  /matches          – List all matches (admin: all, manager: own club)
  POST /matches          – Create a new match record (admin only)
  POST /matches/{id}/upload – Upload a video for processing
  GET  /matches/{id}/events – List events for a match
  GET  /matches/{id}/stats  – List player stats for a match
  WS   /ws/{match_id}   – WebSocket for real-time alerts during processing
  GET  /stream/{match_id}   – MJPEG stream of processed video
"""

import os
import json
import asyncio
from typing import Optional, List

from fastapi import (
    FastAPI, Depends, HTTPException, status,
    WebSocket, WebSocketDisconnect, UploadFile, File, Form
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from passlib.context import CryptContext
from jose import JWTError, jwt
from datetime import datetime, timedelta
from pydantic import BaseModel

from api.database import get_db, init_db, User, Match, MatchEvent, PlayerStat
from api.streamer import VideoProcessor, connection_manager

# ─── Config ───────────────────────────────────────────────────────────────────
SECRET_KEY   = os.getenv("SECRET_KEY", "football-analytics-secret-2024")
ALGORITHM    = "HS256"
TOKEN_EXPIRE = 60 * 24   # minutes

UPLOAD_DIR   = os.path.join(os.path.dirname(__file__), "..", "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)

# ─── App ──────────────────────────────────────────────────────────────────────
app = FastAPI(title="Football Analytics API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
def on_startup():
    init_db()

# ─── Auth helpers ──────────────────────────────────────────────────────────────
pwd_ctx   = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2    = OAuth2PasswordBearer(tokenUrl="/auth/login")

def _hash(pw: str) -> str:
    return pwd_ctx.hash(pw)

def _verify(pw: str, hashed: str) -> bool:
    return pwd_ctx.verify(pw, hashed)

def _create_token(data: dict, expires_min: int = TOKEN_EXPIRE) -> str:
    payload = data.copy()
    payload["exp"] = datetime.utcnow() + timedelta(minutes=expires_min)
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)

def _get_current_user(token: str = Depends(oauth2), db: Session = Depends(get_db)) -> User:
    creds_exc = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired token",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise creds_exc
    except JWTError:
        raise creds_exc
    user = db.query(User).filter_by(username=username).first()
    if user is None or not user.is_active:
        raise creds_exc
    return user

def _require_admin(current_user: User = Depends(_get_current_user)) -> User:
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    return current_user

# ─── Pydantic schemas ──────────────────────────────────────────────────────────
class RegisterRequest(BaseModel):
    username:  str
    email:     str
    password:  str
    club_name: Optional[str] = None

class MatchCreate(BaseModel):
    title:      str
    home_team:  str
    away_team:  str
    match_date: Optional[str] = None

class TokenResponse(BaseModel):
    access_token: str
    token_type:   str = "bearer"
    role:         str
    username:     str

# ─── Auth Routes ──────────────────────────────────────────────────────────────
@app.post("/auth/register", status_code=201)
def register(req: RegisterRequest, db: Session = Depends(get_db)):
    if db.query(User).filter_by(username=req.username).first():
        raise HTTPException(400, "Username already taken")
    if db.query(User).filter_by(email=req.email).first():
        raise HTTPException(400, "Email already registered")
    user = User(
        username  = req.username,
        email     = req.email,
        hashed_pw = _hash(req.password),
        role      = "manager",
        club_name = req.club_name,
    )
    db.add(user)
    db.commit()
    return {"message": "Account created"}

@app.post("/auth/login", response_model=TokenResponse)
def login(form: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = db.query(User).filter_by(username=form.username).first()
    if not user or not _verify(form.password, user.hashed_pw):
        raise HTTPException(401, "Incorrect username or password")
    token = _create_token({"sub": user.username, "role": user.role})
    return TokenResponse(
        access_token=token, role=user.role, username=user.username
    )

# ─── Match Routes ──────────────────────────────────────────────────────────────
@app.get("/matches")
def list_matches(current_user: User = Depends(_get_current_user), db: Session = Depends(get_db)):
    if current_user.role == "admin":
        return db.query(Match).order_by(Match.created_at.desc()).all()
    # Managers see matches they created
    return db.query(Match).filter_by(created_by=current_user.id).order_by(Match.created_at.desc()).all()

@app.post("/matches", status_code=201)
def create_match(
    req: MatchCreate,
    current_user: User = Depends(_get_current_user),
    db: Session = Depends(get_db)
):
    match = Match(
        title      = req.title,
        home_team  = req.home_team,
        away_team  = req.away_team,
        match_date = datetime.fromisoformat(req.match_date) if req.match_date else datetime.utcnow(),
        created_by = current_user.id,
    )
    db.add(match)
    db.commit()
    db.refresh(match)
    return match

@app.post("/matches/{match_id}/upload")
async def upload_video(
    match_id: int,
    video: UploadFile = File(...),
    current_user: User = Depends(_get_current_user),
    db: Session = Depends(get_db)
):
    match = db.query(Match).filter_by(id=match_id).first()
    if not match:
        raise HTTPException(404, "Match not found")

    ext  = os.path.splitext(video.filename or "video.mp4")[1]
    path = os.path.join(UPLOAD_DIR, f"match_{match_id}{ext}")
    with open(path, "wb") as f:
        f.write(await video.read())

    match.video_path = path
    match.status     = "pending"
    db.commit()
    return {"message": "Video uploaded", "path": path}

@app.get("/matches/{match_id}/events")
def get_events(match_id: int, db: Session = Depends(get_db), _=Depends(_get_current_user)):
    return db.query(MatchEvent).filter_by(match_id=match_id).order_by(MatchEvent.frame_number).all()

@app.get("/matches/{match_id}/stats")
def get_stats(match_id: int, db: Session = Depends(get_db), _=Depends(_get_current_user)):
    return db.query(PlayerStat).filter_by(match_id=match_id).all()

# ─── WebSocket ────────────────────────────────────────────────────────────────
@app.websocket("/ws/{match_id}")
async def ws_endpoint(websocket: WebSocket, match_id: int):
    await connection_manager.connect(match_id, websocket)
    try:
        while True:
            await websocket.receive_text()   # Keep alive
    except WebSocketDisconnect:
        connection_manager.disconnect(match_id, websocket)

# ─── MJPEG Stream ─────────────────────────────────────────────────────────────
@app.get("/stream/{match_id}")
async def video_stream(
    match_id: int,
    attacking_team: int = 1,
    current_user: User = Depends(_get_current_user),
    db: Session = Depends(get_db)
):
    match = db.query(Match).filter_by(id=match_id).first()
    if not match or not match.video_path:
        raise HTTPException(404, "Match video not found")

    processor = VideoProcessor(
        video_path     = match.video_path,
        match_id       = match_id,
        attacking_team = attacking_team,
        db             = db,
    )
    return StreamingResponse(
        processor.generate_frames(),
        media_type="multipart/x-mixed-replace;boundary=frame"
    )
