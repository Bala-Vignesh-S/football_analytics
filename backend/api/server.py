"""
server.py — Unified Football Analytics FastAPI Server

Endpoints:
  GET  /api/health              Health check (no auth)
  POST /api/process-image       Upload image → annotated base64 + detection info
  POST /api/process-video       Upload video → processed video URL + stats
  GET  /api/video/<filename>    Serve processed video
  GET  /api/history             Detection history
  GET  /api/stats               Aggregate statistics
  GET  /api/detection/<id>      Single detection record

  POST /auth/register           Club manager self-registration
  POST /auth/login              Returns JWT access token
  GET  /matches                 List matches (admin: all, manager: own)
  POST /matches                 Create match (admin only)
  POST /matches/{id}/upload     Upload video for a match
  GET  /matches/{id}/events     Events for a match
  GET  /matches/{id}/stats      Player stats for a match
  WS   /ws/{match_id}          Real-time WebSocket alerts
  GET  /stream/{match_id}       MJPEG stream of processed match video
"""

import os
import uuid
import base64
import asyncio
import json
import time
import traceback
from typing import Optional, List
from datetime import datetime, timedelta

import cv2
import numpy as np

from fastapi import (
    FastAPI, Depends, HTTPException, status,
    WebSocket, WebSocketDisconnect,
    UploadFile, File, Form
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, FileResponse
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from passlib.context import CryptContext
from jose import JWTError, jwt
from pydantic import BaseModel

from api.database import get_db, init_db, User, Match, MatchEvent, PlayerStat
from api.streamer import VideoProcessor, connection_manager
from database import (
    get_db as get_simple_db,
    insert_detection_record,
    get_detection_history,
    get_stats as get_detection_stats,
    Detection,
    SessionLocal as SimpleSession,
)

# ── Config ────────────────────────────────────────────────────────────────────
SECRET_KEY   = os.getenv("SECRET_KEY", "football-analytics-secret-2024")
ALGORITHM    = "HS256"
TOKEN_EXPIRE = 60 * 24   # minutes

UPLOAD_DIR = os.path.join(os.path.dirname(__file__), "uploads")
OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "outputs")
os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(OUTPUT_DIR, exist_ok=True)

ALLOWED_IMAGE = {"png", "jpg", "jpeg", "bmp", "webp"}
ALLOWED_VIDEO = {"mp4", "avi", "mov", "mkv", "webm"}

# ── App ───────────────────────────────────────────────────────────────────────
app = FastAPI(title="Football Analytics API", version="2.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
def on_startup():
    init_db()  # Auth/match DB
    from database import init_db as init_simple_db
    init_simple_db()  # Detection history DB

# ── Lazy detector singleton ───────────────────────────────────────────────────
_detector = None

def get_offside_detector():
    global _detector
    if _detector is None:
        from offside_detector import OffsideDetector
        _detector = OffsideDetector()
    return _detector

def allowed(filename: str, exts: set) -> bool:
    return "." in filename and filename.rsplit(".", 1)[1].lower() in exts

# ── Auth helpers ──────────────────────────────────────────────────────────────
pwd_ctx  = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2   = OAuth2PasswordBearer(tokenUrl="/auth/login")

def _hash(pw: str) -> str:        return pwd_ctx.hash(pw)
def _verify(pw, hashed) -> bool:  return pwd_ctx.verify(pw, hashed)

def _create_token(data: dict) -> str:
    payload = data.copy()
    payload["exp"] = datetime.utcnow() + timedelta(minutes=TOKEN_EXPIRE)
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)

def _current_user(token: str = Depends(oauth2), db: Session = Depends(get_db)) -> User:
    exc = HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid or expired token",
                        headers={"WWW-Authenticate": "Bearer"})
    try:
        payload  = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username = payload.get("sub")
        if not username: raise exc
    except JWTError:
        raise exc
    user = db.query(User).filter_by(username=username).first()
    if not user or not user.is_active:
        raise exc
    return user

def _require_admin(user: User = Depends(_current_user)) -> User:
    if user.role != "admin":
        raise HTTPException(403, "Admin access required")
    return user

# ── Pydantic schemas ──────────────────────────────────────────────────────────
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


# ══════════════════════════════════════════════════════════════════════════════
#  PUBLIC IMAGE / VIDEO PROCESSING ENDPOINTS
# ══════════════════════════════════════════════════════════════════════════════

@app.get("/api/health")
def health():
    return {"status": "ok", "message": "Football Analytics API is running"}


@app.post("/api/process-image")
async def process_image(file: UploadFile = File(...)):
    """
    Upload a football image → returns annotated base64 JPEG + detection info.
    No authentication required — public demo endpoint.
    """
    start = time.time()
    filename = file.filename or "upload"

    if not allowed(filename, ALLOWED_IMAGE):
        raise HTTPException(400, f"Invalid type. Allowed: {', '.join(ALLOWED_IMAGE)}")

    data = await file.read()
    file_size = len(data)

    try:
        detector = get_offside_detector()
        annotated, info = detector.process_image_bytes(data)
        elapsed = time.time() - start

        if annotated is None:
            insert_detection_record(
                file_name=filename, file_type="image",
                status="failed", error_message=info.get("message"),
                processing_time=elapsed, file_size=file_size,
            )
            raise HTTPException(500, info.get("message", "Processing failed"))

        _, buf = cv2.imencode(".jpg", annotated, [cv2.IMWRITE_JPEG_QUALITY, 90])
        img_b64 = base64.b64encode(buf).decode("utf-8")

        insert_detection_record(
            file_name=filename, file_type="image",
            total_players=info.get("players", 0),
            goalkeepers=info.get("goalkeepers", 0),
            referees=info.get("referees", 0),
            balls=info.get("balls", 0),
            offside_count=info.get("offside_players", 0),
            processing_time=elapsed, file_size=file_size,
            status="success", metadata=info,
        )

        return {
            "status": "success",
            "image":  f"data:image/jpeg;base64,{img_b64}",
            "info":   info,
        }

    except HTTPException:
        raise
    except Exception as e:
        traceback.print_exc()
        insert_detection_record(
            file_name=filename, file_type="image",
            status="failed", error_message=str(e),
            processing_time=time.time() - start, file_size=file_size,
        )
        raise HTTPException(500, str(e))


@app.post("/api/process-video")
async def process_video(file: UploadFile = File(...)):
    """
    Upload a football video → returns processed video URL + aggregate stats.
    No authentication required — public demo endpoint.
    """
    start = time.time()
    filename = file.filename or "upload"

    if not allowed(filename, ALLOWED_VIDEO):
        raise HTTPException(400, f"Invalid type. Allowed: {', '.join(ALLOWED_VIDEO)}")

    ext         = filename.rsplit(".", 1)[1].lower()
    in_name     = f"{uuid.uuid4().hex}.{ext}"
    in_path     = os.path.join(UPLOAD_DIR, in_name)
    out_name    = f"{uuid.uuid4().hex}.mp4"
    out_path    = os.path.join(OUTPUT_DIR, out_name)
    file_size   = 0

    try:
        content = await file.read()
        file_size = len(content)
        with open(in_path, "wb") as f:
            f.write(content)

        detector = get_offside_detector()
        result_path, info = detector.process_video(in_path, out_path, max_frames=150)
        elapsed = time.time() - start

        # Cleanup input
        try: os.remove(in_path)
        except: pass

        if result_path is None:
            insert_detection_record(
                file_name=filename, file_type="video",
                status="failed", error_message=info.get("message"),
                processing_time=elapsed, file_size=file_size,
            )
            raise HTTPException(500, info.get("message", "Processing failed"))

        insert_detection_record(
            file_name=filename, file_type="video",
            offside_count=info.get("frames_with_offside", 0),
            processing_time=elapsed, file_size=file_size,
            status="success", output_file=out_name,
            output_path=out_path, metadata=info,
        )

        return {
            "status":    "success",
            "video_url": f"/api/video/{out_name}",
            "info":      info,
        }

    except HTTPException:
        raise
    except Exception as e:
        traceback.print_exc()
        try: os.remove(in_path)
        except: pass
        raise HTTPException(500, str(e))


@app.get("/api/video/{filename}")
def serve_video(filename: str):
    path = os.path.join(OUTPUT_DIR, filename)
    if not os.path.exists(path):
        raise HTTPException(404, "Video not found")
    return FileResponse(path, media_type="video/mp4")


@app.get("/api/history")
def get_history(limit: int = 20):
    records = get_detection_history(limit=limit)
    return {
        "status":  "success",
        "records": [
            {
                "id":              r.id,
                "file_name":       r.file_name,
                "file_type":       r.file_type,
                "timestamp":       r.upload_timestamp.isoformat(),
                "status":          r.status,
                "players":         r.total_players,
                "offside_count":   r.offside_count,
                "processing_time": r.processing_time,
                "file_size":       r.file_size,
            }
            for r in records
        ],
    }


@app.get("/api/stats")
def statistics():
    return {"status": "success", **get_detection_stats()}


@app.get("/api/detection/{detection_id}")
def detection_detail(detection_id: int):
    db = SimpleSession()
    try:
        r = db.query(Detection).filter_by(id=detection_id).first()
        if not r:
            raise HTTPException(404, "Detection not found")
        return {
            "status":          "success",
            "id":              r.id,
            "file_name":       r.file_name,
            "file_type":       r.file_type,
            "timestamp":       r.upload_timestamp.isoformat(),
            "total_players":   r.total_players,
            "goalkeepers":     r.goalkeepers,
            "referees":        r.referees,
            "balls":           r.balls,
            "offside_count":   r.offside_count,
            "processing_time": r.processing_time,
            "file_size":       r.file_size,
            "error_message":   r.error_message,
            "detection_data":  r.detection_data,
        }
    finally:
        db.close()


# ══════════════════════════════════════════════════════════════════════════════
#  AUTH ROUTES
# ══════════════════════════════════════════════════════════════════════════════

@app.post("/auth/register", status_code=201)
def register(req: RegisterRequest, db: Session = Depends(get_db)):
    if db.query(User).filter_by(username=req.username).first():
        raise HTTPException(400, "Username already taken")
    if db.query(User).filter_by(email=req.email).first():
        raise HTTPException(400, "Email already registered")
    db.add(User(
        username=req.username, email=req.email,
        hashed_pw=_hash(req.password), role="manager",
        club_name=req.club_name,
    ))
    db.commit()
    return {"message": "Account created"}


@app.post("/auth/login", response_model=TokenResponse)
def login(form: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = db.query(User).filter_by(username=form.username).first()
    if not user or not _verify(form.password, user.hashed_pw):
        raise HTTPException(401, "Incorrect username or password")
    token = _create_token({"sub": user.username, "role": user.role})
    return TokenResponse(access_token=token, role=user.role, username=user.username)


# ══════════════════════════════════════════════════════════════════════════════
#  MATCH MANAGEMENT ROUTES
# ══════════════════════════════════════════════════════════════════════════════

@app.get("/matches")
def list_matches(user: User = Depends(_current_user), db: Session = Depends(get_db)):
    q = db.query(Match)
    if user.role != "admin":
        q = q.filter_by(created_by=user.id)
    return q.order_by(Match.created_at.desc()).all()


@app.post("/matches", status_code=201)
def create_match(req: MatchCreate, user: User = Depends(_current_user),
                 db: Session = Depends(get_db)):
    match = Match(
        title=req.title, home_team=req.home_team, away_team=req.away_team,
        match_date=(datetime.fromisoformat(req.match_date)
                    if req.match_date else datetime.utcnow()),
        created_by=user.id,
    )
    db.add(match)
    db.commit()
    db.refresh(match)
    return match


@app.post("/matches/{match_id}/upload")
async def upload_match_video(match_id: int, video: UploadFile = File(...),
                             user: User = Depends(_current_user),
                             db: Session = Depends(get_db)):
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
def get_events(match_id: int, db: Session = Depends(get_db),
               _=Depends(_current_user)):
    return db.query(MatchEvent).filter_by(match_id=match_id)\
             .order_by(MatchEvent.frame_number).all()


@app.get("/matches/{match_id}/stats")
def get_player_stats(match_id: int, db: Session = Depends(get_db),
                     _=Depends(_current_user)):
    return db.query(PlayerStat).filter_by(match_id=match_id).all()


# ── WebSocket ─────────────────────────────────────────────────────────────────
@app.websocket("/ws/{match_id}")
async def ws_endpoint(websocket: WebSocket, match_id: int):
    await connection_manager.connect(match_id, websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        connection_manager.disconnect(match_id, websocket)


# ── MJPEG stream ──────────────────────────────────────────────────────────────
@app.get("/stream/{match_id}")
async def video_stream(match_id: int, attacking_team: int = 1,
                       user: User = Depends(_current_user),
                       db: Session = Depends(get_db)):
    match = db.query(Match).filter_by(id=match_id).first()
    if not match or not match.video_path:
        raise HTTPException(404, "Match video not found")
    processor = VideoProcessor(
        video_path=match.video_path, match_id=match_id,
        attacking_team=attacking_team, db=db,
    )
    return StreamingResponse(
        processor.generate_frames(),
        media_type="multipart/x-mixed-replace;boundary=frame"
    )
