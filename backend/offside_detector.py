"""
offside_detector.py — Core Football Offside Detection Engine
Uses YOLOv8 for player/ball detection, K-Means for team assignment,
and geometric analysis for offside line computation.

Model: player_detection/runs/detect/train/weights/best.pt (custom trained)
Fallback: yolov8n.pt (COCO, auto-downloaded)
"""

import os
import cv2
import numpy as np
from ultralytics import YOLO
from sklearn.cluster import KMeans

# ── Model path resolution ──────────────────────────────────────────────────────
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Primary: custom trained model in cv_pipeline/models/
_CV_MODEL = os.path.join(BASE_DIR, "cv_pipeline", "models", "football_best.pt")
# Secondary: training output path (from player_detection runs)
_TRAIN_MODEL = os.path.join(
    os.path.dirname(BASE_DIR),
    "training", "player_detection", "runs", "detect", "train", "weights", "best.pt"
)
# Fallback: COCO YOLOv8n (auto-downloads)
_FALLBACK_MODEL = "yolov8n.pt"

def _resolve_model():
    if os.path.exists(_CV_MODEL):
        print(f"[OffsideDetector] Using model: {_CV_MODEL}")
        return _CV_MODEL
    if os.path.exists(_TRAIN_MODEL):
        print(f"[OffsideDetector] Using model: {_TRAIN_MODEL}")
        return _TRAIN_MODEL
    print(f"[OffsideDetector] Custom model not found — falling back to {_FALLBACK_MODEL}")
    return _FALLBACK_MODEL

# ── Class names from trained dataset ──────────────────────────────────────────
CLASS_NAMES = {0: "ball", 1: "goalkeeper", 2: "player", 3: "referee"}

# ── Visualization colors (BGR) ─────────────────────────────────────────────────
COLORS = {
    "team_a":       (255, 100, 50),
    "team_b":       (50,  100, 255),
    "goalkeeper":   (0,   255, 255),
    "referee":      (0,   255, 0),
    "ball":         (0,   165, 255),
    "offside_line": (0,   0,   255),
    "onside_line":  (0,   255, 0),
}


class OffsideDetector:
    """Detects players, assigns teams, and draws offside lines on frames."""

    def __init__(self):
        model_path = _resolve_model()
        self.model = YOLO(model_path)
        print("[OffsideDetector] Model loaded.")

    # ── Internal helpers ───────────────────────────────────────────────────────

    def _extract_jersey_crops(self, frame, boxes):
        """Crop the upper-body (jersey) region of each detection."""
        crops = []
        h, w = frame.shape[:2]
        for box in boxes:
            x1, y1, x2, y2 = map(int, box[:4])
            x1, y1 = max(0, x1), max(0, y1)
            x2, y2 = min(w, x2), min(h, y2)
            crop = frame[y1:y2, x1:x2]
            if crop.size > 0:
                mid = crop.shape[0] // 2
                jersey = crop[:mid, :]
                crops.append(jersey if jersey.size > 0 else crop)
            else:
                crops.append(np.zeros((10, 10, 3), dtype=np.uint8))
        return crops

    def _dominant_color(self, crop):
        """Get the dominant BGR color of a crop via K-Means."""
        if crop.size == 0:
            return np.array([0.0, 0.0, 0.0])
        pixels = crop.reshape(-1, 3).astype(np.float32)
        k = min(3, len(pixels))
        km = KMeans(n_clusters=k, n_init=5, max_iter=50, random_state=42)
        km.fit(pixels)
        labels, counts = np.unique(km.labels_, return_counts=True)
        return km.cluster_centers_[labels[np.argmax(counts)]]

    def _assign_teams(self, frame, player_boxes):
        """Cluster players into 2 teams by jersey color."""
        if len(player_boxes) < 2:
            return [0] * len(player_boxes)
        crops  = self._extract_jersey_crops(frame, player_boxes)
        colors = np.array([self._dominant_color(c) for c in crops])
        if len(colors) < 2:
            return [0] * len(player_boxes)
        km = KMeans(n_clusters=2, n_init=10, max_iter=100, random_state=42)
        return km.fit_predict(colors).tolist()

    # ── Core frame processing ──────────────────────────────────────────────────

    def process_frame(self, frame: np.ndarray):
        """
        Process one frame:
          - Run YOLOv8 detection
          - Assign teams via jersey-color clustering
          - Compute offside line (2nd-to-last defender rule)
          - Draw all annotations

        Returns:
            annotated (np.ndarray), info (dict)
        """
        results = self.model(frame, conf=0.3, imgsz=1280, verbose=False)

        if not results or results[0].boxes is None or len(results[0].boxes) == 0:
            return frame, {"status": "no_detections", "players": 0, "goalkeepers": 0,
                           "referees": 0, "balls": 0, "offside_players": 0}

        boxes_raw = results[0].boxes
        annotated = frame.copy()
        h, w = frame.shape[:2]

        player_boxes, gk_boxes, ref_boxes, ball_boxes = [], [], [], []

        for box in boxes_raw:
            cls_id = int(box.cls[0])
            xyxy   = box.xyxy[0].cpu().numpy()
            if cls_id == 2:   player_boxes.append(xyxy)
            elif cls_id == 1: gk_boxes.append(xyxy)
            elif cls_id == 3: ref_boxes.append(xyxy)
            elif cls_id == 0: ball_boxes.append(xyxy)

        # Team assignment
        team_labels = (self._assign_teams(frame, player_boxes)
                       if len(player_boxes) >= 2 else [0] * len(player_boxes))

        # Build team position lists: (x_center, y_bottom, box)
        team_a, team_b = [], []
        for box, team in zip(player_boxes, team_labels):
            cx = (box[0] + box[2]) / 2
            yb = box[3]
            (team_a if team == 0 else team_b).append((cx, yb, box))

        # Assign goalkeepers to nearest team by average x
        for gk in gk_boxes:
            gk_cx = (gk[0] + gk[2]) / 2
            avg_a = np.mean([p[0] for p in team_a]) if team_a else w
            avg_b = np.mean([p[0] for p in team_b]) if team_b else 0
            (team_a if abs(gk_cx - avg_a) < abs(gk_cx - avg_b) else team_b).append(
                (gk_cx, gk[3], gk))

        # Determine defending/attacking teams by average x
        avg_a = np.mean([p[0] for p in team_a]) if team_a else 0
        avg_b = np.mean([p[0] for p in team_b]) if team_b else 0

        if avg_a > avg_b:
            defending, attacking = team_a, team_b
            def_col, att_col = COLORS["team_a"], COLORS["team_b"]
            defending_right = True
        else:
            defending, attacking = team_b, team_a
            def_col, att_col = COLORS["team_b"], COLORS["team_a"]
            defending_right = False

        # Compute offside line (second-to-last defender)
        offside_x      = None
        offside_players = []

        if len(defending) >= 2:
            sorted_def = sorted(defending, key=lambda p: p[0],
                                reverse=not defending_right)
            offside_x = sorted_def[1][0]

            for pos in attacking:
                is_offside = (pos[0] > offside_x if defending_right
                              else pos[0] < offside_x)
                if is_offside:
                    offside_players.append(pos)

        # ── Draw annotations ───────────────────────────────────────────────────

        # Offside line
        if offside_x is not None:
            lc = COLORS["offside_line"] if offside_players else COLORS["onside_line"]
            cv2.line(annotated, (int(offside_x), 0), (int(offside_x), h), lc, 3)
            cv2.putText(annotated, "OFFSIDE LINE", (int(offside_x) + 10, 40),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.9, lc, 2)

        # Players
        for box, team in zip(player_boxes, team_labels):
            col  = COLORS["team_a"] if team == 0 else COLORS["team_b"]
            x1, y1, x2, y2 = map(int, box[:4])
            cx = (box[0] + box[2]) / 2
            label = f"Team {'A' if team == 0 else 'B'}"
            is_off = offside_x is not None and any(abs(p[0] - cx) < 5 for p in offside_players)
            if is_off:
                label += " OFFSIDE!"
                cv2.rectangle(annotated, (x1, y1), (x2, y2), (0, 0, 255), 4)
            else:
                cv2.rectangle(annotated, (x1, y1), (x2, y2), col, 2)
            cv2.putText(annotated, label, (x1, y1 - 10),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, col, 2)

        # Goalkeepers
        for gk in gk_boxes:
            x1, y1, x2, y2 = map(int, gk[:4])
            cv2.rectangle(annotated, (x1, y1), (x2, y2), COLORS["goalkeeper"], 2)
            cv2.putText(annotated, "GK", (x1, y1 - 10),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, COLORS["goalkeeper"], 2)

        # Referees
        for ref in ref_boxes:
            x1, y1, x2, y2 = map(int, ref[:4])
            cv2.rectangle(annotated, (x1, y1), (x2, y2), COLORS["referee"], 2)
            cv2.putText(annotated, "Referee", (x1, y1 - 10),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, COLORS["referee"], 2)

        # Ball
        for ball in ball_boxes:
            x1, y1, x2, y2 = map(int, ball[:4])
            cx, cy = (x1 + x2) // 2, (y1 + y2) // 2
            r = max(x2 - x1, y2 - y1) // 2
            cv2.circle(annotated, (cx, cy), r + 5, COLORS["ball"], 3)
            cv2.putText(annotated, "Ball", (x1, y1 - 10),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, COLORS["ball"], 2)

        # Bottom summary bar
        summary = (f"Players: {len(player_boxes)} | GK: {len(gk_boxes)} "
                   f"| Ref: {len(ref_boxes)} | Ball: {len(ball_boxes)}")
        cv2.rectangle(annotated, (0, h - 50), (w, h), (0, 0, 0), -1)
        cv2.putText(annotated, summary, (10, h - 20),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)

        if offside_x is not None:
            ot = "OFFSIDE DETECTED!" if offside_players else "No offside"
            oc = (0, 0, 255) if offside_players else (0, 255, 0)
            cv2.putText(annotated, ot, (w - 420, h - 20),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, oc, 2)

        info = {
            "status":          "success",
            "players":         len(player_boxes),
            "goalkeepers":     len(gk_boxes),
            "referees":        len(ref_boxes),
            "balls":           len(ball_boxes),
            "offside_players": len(offside_players),
            "offside_info":    (f"Line at x={int(offside_x)}, "
                                f"{len(offside_players)} offside"
                                if offside_x else "No line computed"),
        }
        return annotated, info

    # ── Public API ─────────────────────────────────────────────────────────────

    def process_image(self, image_path: str):
        """Process a single image file. Returns (annotated_frame, info_dict)."""
        frame = cv2.imread(image_path)
        if frame is None:
            return None, {"status": "error", "message": "Could not read image"}
        return self.process_frame(frame)

    def process_image_bytes(self, data: bytes):
        """Process raw image bytes (e.g. from UploadFile). Returns (annotated, info)."""
        arr   = np.frombuffer(data, np.uint8)
        frame = cv2.imdecode(arr, cv2.IMREAD_COLOR)
        if frame is None:
            return None, {"status": "error", "message": "Could not decode image"}
        return self.process_frame(frame)

    def process_video(self, video_path: str, output_path: str, max_frames: int = 150):
        """
        Process a video file and write annotated output.
        Returns (output_path, summary_dict) or (None, error_dict).
        """
        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            return None, {"status": "error", "message": "Could not open video"}

        fps    = int(cap.get(cv2.CAP_PROP_FPS)) or 25
        w      = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        h_     = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        total  = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        limit  = min(total, max_frames)

        fourcc = cv2.VideoWriter_fourcc(*"mp4v")
        out    = cv2.VideoWriter(output_path, fourcc, fps, (w, h_))

        processed, offside_frames_count = 0, 0
        while cap.isOpened() and processed < limit:
            ret, frame = cap.read()
            if not ret:
                break
            annotated, info = self.process_frame(frame)
            out.write(annotated)
            if info.get("offside_players", 0) > 0:
                offside_frames_count += 1
            processed += 1

        cap.release()
        out.release()

        return output_path, {
            "status":              "success",
            "total_frames":        processed,
            "frames_with_offside": offside_frames_count,
            "fps":                 fps,
        }
