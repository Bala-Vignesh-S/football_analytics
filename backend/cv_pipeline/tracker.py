"""
tracker.py – YOLOv8 + ByteTrack based detection and tracking.

Returns a list of TrackedObject for each frame:
  - id         : unique track id
  - class_id   : 0=player,1=goalkeeper,2=ball,3=referee
  - confidence : float
  - bbox       : [x1,y1,x2,y2]  (pixel coords)
  - centroid   : (cx, cy)
"""

import os
import cv2
import numpy as np
from dataclasses import dataclass, field
from typing import List, Optional

from ultralytics import YOLO
from cv_pipeline.config import (
    MODEL_PATH, FALLBACK_MODEL_PATH,
    DETECTION_CONF, TRACK_CONF, TRACK_PERSIST, CLASS_NAMES
)


@dataclass
class TrackedObject:
    id: int
    class_id: int
    class_name: str
    confidence: float
    bbox: List[int]          # [x1, y1, x2, y2]
    centroid: tuple          # (cx, cy)
    team_id: Optional[int] = None   # Assigned later by TeamClassifier


class FootballTracker:
    def __init__(self):
        model_path = MODEL_PATH if os.path.exists(MODEL_PATH) else FALLBACK_MODEL_PATH
        print(f"[Tracker] Loading model from: {model_path}")
        self.model = YOLO(model_path)
        self._prev_tracks: dict = {}

    def detect_and_track(self, frame: np.ndarray) -> List[TrackedObject]:
        """
        Run YOLOv8 tracking on a single frame.
        Returns a list of TrackedObject instances.
        """
        results = self.model.track(
            source=frame,
            persist=TRACK_PERSIST,
            conf=TRACK_CONF,
            iou=0.5,
            tracker="bytetrack.yaml",
            verbose=False
        )

        objects: List[TrackedObject] = []
        if results and results[0].boxes is not None:
            boxes = results[0].boxes
            for box in boxes:
                # Skip if no track id yet
                if box.id is None:
                    continue

                track_id  = int(box.id.item())
                class_id  = int(box.cls.item())
                conf      = float(box.conf.item())
                x1, y1, x2, y2 = map(int, box.xyxy[0].tolist())
                cx = (x1 + x2) // 2
                cy = (y1 + y2) // 2

                class_name = CLASS_NAMES.get(class_id, f"cls_{class_id}")

                obj = TrackedObject(
                    id=track_id,
                    class_id=class_id,
                    class_name=class_name,
                    confidence=conf,
                    bbox=[x1, y1, x2, y2],
                    centroid=(cx, cy),
                )
                objects.append(obj)

        return objects

    def get_ball(self, objects: List[TrackedObject]) -> Optional[TrackedObject]:
        """Return the first detected ball object."""
        for obj in objects:
            if obj.class_name == "ball":
                return obj
        return None

    def get_players(self, objects: List[TrackedObject]) -> List[TrackedObject]:
        """Return all player and goalkeeper objects."""
        return [o for o in objects if o.class_name in ("player", "goalkeeper")]

    def get_referees(self, objects: List[TrackedObject]) -> List[TrackedObject]:
        return [o for o in objects if o.class_name == "referee"]
