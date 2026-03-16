"""
cv_pipeline – Football Analytics Computer Vision Pipeline.

Public API:
    FootballTracker     – YOLOv8 + ByteTrack detection & tracking
    TeamClassifier      – K-Means jersey-color team assignment
    PitchMapper         – Homography: pixel coords → real-world pitch metres
    OffsideDetector     – Last defender logic + offside line + event trigger
    TrackedObject       – Dataclass returned by the tracker per detection
    OffsideEvent        – Dataclass emitted when an offside is detected
"""

from cv_pipeline.tracker import FootballTracker, TrackedObject
from cv_pipeline.team_classifier import TeamClassifier
from cv_pipeline.pitch_mapper import PitchMapper
from cv_pipeline.offside_logic import OffsideDetector, OffsideEvent

__all__ = [
    "FootballTracker",
    "TrackedObject",
    "TeamClassifier",
    "PitchMapper",
    "OffsideDetector",
    "OffsideEvent",
]
