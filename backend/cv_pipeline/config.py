"""
Central configuration for the CV pipeline.
"""
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# ─── Model Paths ───────────────────────────────────────────────────────────────
MODEL_PATH = os.path.join(BASE_DIR, "models", "football_best.pt")
# Fallback to generic COCO yolov8n if custom model not found yet
FALLBACK_MODEL_PATH = "yolov8n.pt"

# ─── Class Labels (from Roboflow football dataset) ────────────────────────────
CLASS_NAMES = {
    0: "player",
    1: "goalkeeper",
    2: "ball",
    3: "referee",
}

# ─── Detection Settings ────────────────────────────────────────────────────────
DETECTION_CONF = 0.3       # Minimum confidence threshold
DETECTION_IOU  = 0.5       # NMS IoU threshold

# ─── Team Clustering ──────────────────────────────────────────────────────────
N_TEAMS = 2                # Number of teams (excluding goalkeeper)
TEAM_COLORS = {
    1: (255, 80,  80),     # Team 1 – Red/Blue (BGR for OpenCV)
    2: (80,  80, 255),     # Team 2 – Blue/Red
    "goalkeeper": (0, 200, 0),
    "referee":    (0, 200, 200),
    "ball":       (0, 255, 255),
}

# ─── Tracking ─────────────────────────────────────────────────────────────────
TRACK_PERSIST = True       # Keep trackers across frames
TRACK_CONF    = 0.3

# ─── Pitch keypoints ──────────────────────────────────────────────────────────
# 4 reference corners of the pitch in real-world meters (standard pitch ~105x68)
PITCH_REAL_POINTS_M = [
    [0,  0],
    [105, 0],
    [105, 68],
    [0,  68],
]

# ─── Offside Config ───────────────────────────────────────────────────────────
OFFSIDE_LINE_COLOR_BGR = (0, 255, 255)   # Cyan
OFFSIDE_ALERT_FRAMES   = 60             # Show alert for N frames after trigger
