"""
streamer.py – Video frame processor and WebSocket connection manager.

VideoProcessor:
  - Opens a video file with OpenCV.
  - Runs each frame through the full CV pipeline:
      FootballTracker → TeamClassifier → PitchMapper → OffsideDetector
  - Auto-calibrates pitch on the first frame (falls back to full-frame if auto fails).
  - Yields MJPEG frames for the StreamingResponse endpoint.
  - Broadcasts offside events to WebSocket clients.
  - Persists events and player stats to the database.

ConnectionManager:
  - Manages WebSocket connections grouped by match_id.
  - Broadcasts JSON messages to all connected clients for a match.
"""

import cv2
import json
import asyncio
import numpy as np
from typing import Dict, List, AsyncGenerator
from fastapi import WebSocket

from cv_pipeline import (
    FootballTracker, TeamClassifier, PitchMapper,
    OffsideDetector, TrackedObject
)
from api.database import SessionLocal, MatchEvent, PlayerStat, Match


# ─── WebSocket Connection Manager ─────────────────────────────────────────────

class ConnectionManager:
    def __init__(self):
        self._connections: Dict[int, List[WebSocket]] = {}

    async def connect(self, match_id: int, ws: WebSocket):
        await ws.accept()
        self._connections.setdefault(match_id, []).append(ws)

    def disconnect(self, match_id: int, ws: WebSocket):
        if match_id in self._connections:
            self._connections[match_id].remove(ws)

    async def broadcast(self, match_id: int, payload: dict):
        msg = json.dumps(payload)
        dead = []
        for ws in self._connections.get(match_id, []):
            try:
                await ws.send_text(msg)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.disconnect(match_id, ws)


connection_manager = ConnectionManager()


# ─── Player Stats Accumulator ─────────────────────────────────────────────────

class PlayerStatsAccumulator:
    """Tracks distance, speed and offside count per player across frames."""

    def __init__(self):
        self._prev_positions: Dict[int, tuple] = {}   # track_id → (x, y) in metres
        self._distance: Dict[int, float] = {}
        self._speeds:   Dict[int, List[float]] = {}
        self._max_speed: Dict[int, float] = {}
        self._frames:   Dict[int, int] = {}
        self._team:     Dict[int, int] = {}
        self._offside:  Dict[int, int] = {}

    def update(self, players: List[TrackedObject], pitch_positions: Dict[int, tuple], fps: float):
        for p in players:
            tid = p.id
            self._frames[tid]  = self._frames.get(tid, 0) + 1
            self._team[tid]    = p.team_id or 0

            if tid in pitch_positions:
                rx, ry = pitch_positions[tid]
                if tid in self._prev_positions:
                    px, py = self._prev_positions[tid]
                    dist = np.sqrt((rx - px) ** 2 + (ry - py) ** 2)
                    self._distance[tid] = self._distance.get(tid, 0.0) + dist
                    speed = dist * fps   # m/s
                    self._speeds.setdefault(tid, []).append(speed)
                    self._max_speed[tid] = max(self._max_speed.get(tid, 0.0), speed)
                self._prev_positions[tid] = (rx, ry)

    def record_offside(self, player_id: int):
        self._offside[player_id] = self._offside.get(player_id, 0) + 1

    def flush_to_db(self, db, match_id: int):
        """Write accumulated stats to PlayerStat rows."""
        for tid in self._frames:
            speeds = self._speeds.get(tid, [])
            avg_sp = float(np.mean(speeds)) if speeds else 0.0
            row = db.query(PlayerStat).filter_by(
                match_id=match_id, player_track_id=tid
            ).first()
            if row is None:
                row = PlayerStat(match_id=match_id, player_track_id=tid)
                db.add(row)
            row.team_id         = self._team.get(tid, 0)
            row.distance_m      = round(self._distance.get(tid, 0.0), 2)
            row.avg_speed_ms    = round(avg_sp, 3)
            row.max_speed_ms    = round(self._max_speed.get(tid, 0.0), 3)
            row.offside_count   = self._offside.get(tid, 0)
            row.frames_detected = self._frames.get(tid, 0)
        db.commit()


# ─── Video Processor ──────────────────────────────────────────────────────────

RECLUSTER_EVERY = 30   # Re-run K-Means team clustering every N frames

class VideoProcessor:
    """
    Runs the full CV pipeline on a video file and yields MJPEG frames.
    Persists events to the database and broadcasts via WebSocket.
    """

    def __init__(self, video_path: str, match_id: int, attacking_team: int = 1, db=None):
        self.video_path     = video_path
        self.match_id       = match_id
        self.attacking_team = attacking_team
        self._db            = db or SessionLocal()

        # CV pipeline components
        self.tracker    = FootballTracker()
        self.classifier = TeamClassifier()
        self.mapper     = PitchMapper()
        self.offside    = OffsideDetector(self.mapper, attacking_team=attacking_team)
        self.stats_acc  = PlayerStatsAccumulator()

    async def generate_frames(self) -> AsyncGenerator[bytes, None]:
        cap = cv2.VideoCapture(self.video_path)
        if not cap.isOpened():
            return

        fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
        frame_num = 0
        flush_every = int(fps * 10)  # flush stats to DB every 10 seconds of video

        while True:
            ret, frame = cap.read()
            if not ret:
                break

            frame_num += 1

            # ── Auto-calibrate pitch on frame 1 ───────────────────────────────
            if frame_num == 1 and not self.mapper.is_calibrated:
                if not self.mapper.auto_calibrate(frame):
                    # Fallback: use full frame corners
                    h, w = frame.shape[:2]
                    self.mapper.set_from_clicks([
                        (0, 0), (w, 0), (w, h), (0, h)
                    ])

            # ── Detection & tracking ───────────────────────────────────────────
            objects = self.tracker.detect_and_track(frame)
            players = self.tracker.get_players(objects)
            ball    = self.tracker.get_ball(objects)

            # ── Team classification ────────────────────────────────────────────
            if frame_num % RECLUSTER_EVERY == 1:
                self.classifier.fit(frame, players)
            self.classifier.assign_teams(players)

            # ── Pitch positions ────────────────────────────────────────────────
            pitch_pos = {}
            for p in players:
                pos = self.mapper.transform_centroid(p.centroid)
                if pos:
                    pitch_pos[p.id] = pos

            self.stats_acc.update(players, pitch_pos, fps)

            # ── Offside detection ──────────────────────────────────────────────
            frame, event = self.offside.update(frame, players + ([] if not ball else [ball]), ball, frame_num)

            if event:
                # Persist event to DB
                db_event = MatchEvent(
                    match_id     = self.match_id,
                    event_type   = "offside",
                    frame_number = event.frame_number,
                    timestamp_s  = round(event.frame_number / fps, 2),
                    player_id    = event.offending_player_id,
                    team_id      = event.offending_team,
                    detail       = json.dumps({
                        "last_defender_x_m": round(event.last_defender_x_m, 2),
                        "attacker_x_m":      round(event.attacker_x_m, 2),
                    }),
                )
                self._db.add(db_event)
                self._db.commit()
                self.stats_acc.record_offside(event.offending_player_id)

                # Broadcast to WebSocket clients
                asyncio.create_task(connection_manager.broadcast(self.match_id, {
                    "type":      "offside",
                    "frame":     event.frame_number,
                    "timestamp": round(event.frame_number / fps, 2),
                    "player_id": event.offending_player_id,
                    "team":      event.offending_team,
                }))

            # ── Annotate bounding boxes on frame ──────────────────────────────
            frame = _annotate_frame(frame, objects, pitch_pos, frame_num)

            # ── Encode to JPEG for MJPEG stream ───────────────────────────────
            _, buf = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
            yield (
                b"--frame\r\n"
                b"Content-Type: image/jpeg\r\n\r\n"
                + buf.tobytes()
                + b"\r\n"
            )

            # ── Periodic DB flush ──────────────────────────────────────────────
            if frame_num % flush_every == 0:
                self.stats_acc.flush_to_db(self._db, self.match_id)

        # Final stats flush
        self.stats_acc.flush_to_db(self._db, self.match_id)

        # Mark match as done
        match = self._db.query(Match).filter_by(id=self.match_id).first()
        if match:
            match.status = "done"
            self._db.commit()

        cap.release()


# ─── Frame annotation helper ──────────────────────────────────────────────────

TEAM_COLORS = {
    1: (80,  80,  255),   # Team 1 — blue
    2: (255, 80,  80),    # Team 2 — red
    0: (180, 180, 180),   # Unknown
}

def _annotate_frame(frame, objects, pitch_pos: dict, frame_num: int) -> np.ndarray:
    for obj in objects:
        x1, y1, x2, y2 = obj.bbox
        color = TEAM_COLORS.get(getattr(obj, "team_id", 0) or 0, (180, 180, 180))

        if obj.class_name == "ball":
            color = (0, 255, 255)
        elif obj.class_name == "referee":
            color = (0, 200, 200)

        cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)

        label = f"#{obj.id} {obj.class_name}"
        if obj.id in pitch_pos:
            rx, ry = pitch_pos[obj.id]
            label += f" ({rx:.1f},{ry:.1f})"

        cv2.putText(frame, label, (x1, y1 - 8),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 1)

    # Frame counter
    cv2.putText(frame, f"Frame: {frame_num}", (10, frame.shape[0] - 15),
                cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
    return frame
