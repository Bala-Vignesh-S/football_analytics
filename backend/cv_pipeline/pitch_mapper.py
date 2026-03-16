"""
pitch_mapper.py – Pitch keypoint detection and homography transform.

Converts pixel coordinates on the camera image into 2D real-world pitch
coordinates (in metres on a standard 105 × 68 m pitch).

Workflow:
  1. Detect the 4 pitch corner keypoints from a frame (user-supplied or auto).
  2. Compute a Homography matrix (H) using cv2.getPerspectiveTransform.
  3. Transform any pixel point (cx, cy) → real-world (rx, ry) via H.
"""

import cv2
import numpy as np
from typing import List, Optional, Tuple

from cv_pipeline.config import PITCH_REAL_POINTS_M


# ─── Standard pitch corners in real-world space (metres) ──────────────────────
# Order: top-left, top-right, bottom-right, bottom-left (matches mouse click order)
REAL_CORNERS = np.float32(PITCH_REAL_POINTS_M)   # shape (4, 2)


class PitchMapper:
    """
    Manages the homography between camera-space pixels and 2D pitch coordinates.

    Usage:
        mapper = PitchMapper()
        mapper.set_from_clicks(pixel_corners)   # called once via UI or auto-detect
        rx, ry = mapper.pixel_to_pitch(cx, cy)
    """

    def __init__(self):
        self._H: Optional[np.ndarray] = None          # 3×3 homography matrix
        self._H_inv: Optional[np.ndarray] = None      # inverse (pitch → pixel)
        self._pixel_corners: Optional[np.ndarray] = None
        self._calibrated = False

    # ── Calibration ───────────────────────────────────────────────────────────

    def set_from_clicks(self, pixel_corners: List[Tuple[int, int]]):
        """
        Set homography from 4 manually clicked pixel corners.
        Click order: top-left, top-right, bottom-right, bottom-left.
        """
        if len(pixel_corners) != 4:
            raise ValueError("Exactly 4 corner points required.")

        src = np.float32(pixel_corners)                # camera pixels
        dst = REAL_CORNERS * 10                        # scale to cm for stability

        self._H = cv2.getPerspectiveTransform(src, dst)
        self._H_inv = cv2.getPerspectiveTransform(dst, src)
        self._pixel_corners = src
        self._calibrated = True
        print("[PitchMapper] Homography calibrated from clicked corners.")

    def auto_calibrate(self, frame: np.ndarray) -> bool:
        """
        Attempt automatic pitch boundary detection using green-field masking
        and finding the outermost white-line corners.
        Returns True if successful, False if manual calibration is needed.
        """
        corners = _detect_pitch_corners(frame)
        if corners is None:
            return False
        self.set_from_clicks(corners)
        return True

    # ── Transform helpers ──────────────────────────────────────────────────────

    def pixel_to_pitch(self, cx: int, cy: int) -> Optional[Tuple[float, float]]:
        """Map a pixel centroid to real-world pitch coordinates (metres)."""
        if not self._calibrated:
            return None
        pt = np.float32([[[cx, cy]]])
        mapped = cv2.perspectiveTransform(pt, self._H)[0][0]
        rx, ry = float(mapped[0]) / 10, float(mapped[1]) / 10  # back to metres
        return rx, ry

    def pitch_to_pixel(self, rx: float, ry: float) -> Optional[Tuple[int, int]]:
        """Map a real-world pitch coordinate back to pixel space."""
        if not self._calibrated or self._H_inv is None:
            return None
        pt = np.float32([[[rx * 10, ry * 10]]])
        mapped = cv2.perspectiveTransform(pt, self._H_inv)[0][0]
        return int(mapped[0]), int(mapped[1])

    def transform_centroid(self, centroid: Tuple[int, int]) -> Optional[Tuple[float, float]]:
        return self.pixel_to_pitch(centroid[0], centroid[1])

    @property
    def is_calibrated(self) -> bool:
        return self._calibrated

    # ── Drawing helpers ────────────────────────────────────────────────────────

    def draw_calibration(self, frame: np.ndarray) -> np.ndarray:
        """Draw the calibration corner markers on the frame (for debug view)."""
        if not self._calibrated:
            return frame
        vis = frame.copy()
        labels = ["TL", "TR", "BR", "BL"]
        for i, pt in enumerate(self._pixel_corners):
            cx, cy = int(pt[0]), int(pt[1])
            cv2.circle(vis, (cx, cy), 8, (0, 255, 0), -1)
            cv2.putText(vis, labels[i], (cx + 10, cy - 10),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
        return vis


# ─── Auto-detection helpers ───────────────────────────────────────────────────

def _detect_pitch_corners(frame: np.ndarray) -> Optional[List[Tuple[int, int]]]:
    """
    Try to detect the 4 pitch corners automatically using:
    1. HSV green masking to isolate the pitch area.
    2. Canny edge detection on the green mask.
    3. Probabilistic Hough lines to find the pitch boundary lines.
    4. Line intersection to estimate corners.

    Returns 4 corners [TL, TR, BR, BL] or None if detection fails.
    """
    h, w = frame.shape[:2]
    hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)

    # Green pitch mask
    lower_green = np.array([35, 40, 40])
    upper_green = np.array([85, 255, 255])
    mask = cv2.inRange(hsv, lower_green, upper_green)

    # Morphological clean-up
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (15, 15))
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)

    # Contour of the largest green region
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        return None

    largest = max(contours, key=cv2.contourArea)
    if cv2.contourArea(largest) < (h * w * 0.2):
        # Pitch occupies <20% of frame — not reliable
        return None

    rect = cv2.minAreaRect(largest)
    box = cv2.boxPoints(rect)
    box = np.int0(box)

    # Sort corners: top-left, top-right, bottom-right, bottom-left
    corners = _sort_corners(box)
    return [(int(c[0]), int(c[1])) for c in corners]


def _sort_corners(pts: np.ndarray) -> np.ndarray:
    """Sort 4 points into [TL, TR, BR, BL] order."""
    pts = pts[np.argsort(pts[:, 1])]   # sort by y
    top    = pts[:2][np.argsort(pts[:2, 0])]    # sort top two by x → [TL, TR]
    bottom = pts[2:][np.argsort(pts[2:, 0])]    # sort bottom two by x → [BL, BR]
    return np.array([top[0], top[1], bottom[1], bottom[0]])  # TL, TR, BR, BL
