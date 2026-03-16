"""
team_classifier.py – Assign players to Team A or Team B via K-Means color clustering.

Strategy:
  1. Crop the jersey region of each detected player.
  2. Extract the dominant HSV color from that crop.
  3. Run K-Means with k=2 on all player dominant colors to form two team clusters.
  4. Assign each player the cluster label as their team_id (1 or 2).
"""

import cv2
import numpy as np
from sklearn.cluster import KMeans
from typing import List
from cv_pipeline.tracker import TrackedObject


def _get_jersey_crop(frame: np.ndarray, bbox: List[int]) -> np.ndarray:
    """
    Extract the upper-body (jersey) region of a bounding box.
    We use the top 40% of the box height to capture just the torso.
    """
    x1, y1, x2, y2 = bbox
    h = y2 - y1
    # Use the upper 40% → ~torso / jersey region
    crop_y2 = y1 + int(h * 0.4)
    crop = frame[y1:crop_y2, x1:x2]
    if crop.size == 0:
        return None
    return crop


def _dominant_color_hsv(crop: np.ndarray) -> np.ndarray:
    """
    Get the dominant color of an image crop using a 2-bin K-Means on HSV space.
    Returns the dominant hue+sat+val as a 1D array [H, S, V].
    """
    hsv = cv2.cvtColor(crop, cv2.COLOR_BGR2HSV)
    pixels = hsv.reshape(-1, 3).astype(np.float32)
    # Quick dominant color via mini-batch kmeans
    km = KMeans(n_clusters=2, n_init=3, max_iter=50, random_state=0)
    km.fit(pixels)
    # Pick the cluster with the most pixels
    labels, counts = np.unique(km.labels_, return_counts=True)
    dominant_label = labels[np.argmax(counts)]
    return km.cluster_centers_[dominant_label]


class TeamClassifier:
    def __init__(self):
        self._fitted = False
        self._km = KMeans(n_clusters=2, n_init=5, random_state=0)
        self._team_map: dict = {}   # track_id → team_id (1 or 2)

    def fit(self, frame: np.ndarray, players: List[TrackedObject]):
        """
        Cluster all current players into two teams using their jersey colors.
        Call this every N frames (e.g. every 30 frames) to re-cluster.
        """
        if len(players) < 2:
            return

        colors = []
        valid_players = []

        for p in players:
            crop = _get_jersey_crop(frame, p.bbox)
            if crop is None:
                continue
            dom_color = _dominant_color_hsv(crop)
            colors.append(dom_color)
            valid_players.append(p)

        if len(colors) < 2:
            return

        color_matrix = np.array(colors)
        self._km.fit(color_matrix)
        self._fitted = True

        for i, player in enumerate(valid_players):
            team_id = int(self._km.labels_[i]) + 1   # 1-indexed
            self._team_map[player.id] = team_id

    def assign_teams(self, players: List[TrackedObject]):
        """
        Assign cached team IDs to player objects.
        For new players, try to predict which team they belong to.
        """
        if not self._fitted:
            # Default assignment before first fit
            for p in players:
                p.team_id = self._team_map.get(p.id, 0)
            return

        for player in players:
            if player.id in self._team_map:
                player.team_id = self._team_map[player.id]
            else:
                # New player – assign 0 (unknown) until next fit
                player.team_id = 0
