"""
offside_logic.py – Last defender detection and offside line drawing.

Algorithm:
  1. Separate players by team and identify the attacking/defending team
     based on ball position (ball is in the half closest to the attacking team).
  2. Sort the defending team's players by their real-world X coordinate
     (along the pitch length axis).
  3. The second-furthest defender from goal = the "last outfield defender".
     (The furthest is usually the goalkeeper.)
  4. Draw a vertical offside line at that X position in pixel space.
  5. Check each attacking player: if any attacker's foot is ahead of the
     offside line AND the ball is played forward → trigger an OFFSIDE event.

Offside line is drawn in pixel space using the inverse homography from PitchMapper.
"""

import cv2
import numpy as np
from dataclasses import dataclass
from typing import List, Optional, Tuple

from cv_pipeline.tracker import TrackedObject
from cv_pipeline.pitch_mapper import PitchMapper
from cv_pipeline.config import (
    OFFSIDE_LINE_COLOR_BGR, OFFSIDE_ALERT_FRAMES, TEAM_COLORS
)


@dataclass
class OffsideEvent:
    frame_number: int
    offending_player_id: int
    offending_team: int
    last_defender_id: int
    last_defender_x_m: float      # real-world pitch X in metres
    attacker_x_m: float


class OffsideDetector:
    """
    Stateful offside detector.

    Must be updated every frame with the current tracked objects.
    Maintains alert state so the UI can show a banner for N frames.
    """

    def __init__(self, mapper: PitchMapper, attacking_team: int = 1):
        self._mapper = mapper
        self.attacking_team: int = attacking_team   # 1 or 2
        self.defending_team: int = 3 - attacking_team

        self._alert_frames_remaining: int = 0
        self._last_event: Optional[OffsideEvent] = None
        self._frame_count: int = 0

        # Previous ball position to detect forward passes
        self._prev_ball_x: Optional[float] = None

    # ── Per-frame update ───────────────────────────────────────────────────────

    def update(
        self,
        frame: np.ndarray,
        players: List[TrackedObject],
        ball: Optional[TrackedObject],
        frame_number: int,
    ) -> Tuple[np.ndarray, Optional[OffsideEvent]]:
        """
        Process one frame. Returns:
          - annotated frame (with offside line + alert banner drawn)
          - OffsideEvent if offside was detected this frame, else None
        """
        self._frame_count = frame_number
        event: Optional[OffsideEvent] = None

        if not self._mapper.is_calibrated:
            self._draw_uncalibrated_warning(frame)
            return frame, None

        # ── Real-world positions ───────────────────────────────────────────────
        defenders  = [p for p in players if p.team_id == self.defending_team]
        attackers  = [p for p in players if p.team_id == self.attacking_team]

        # Auto swap attack/defense direction based on ball position
        if ball is not None:
            ball_pitch = self._mapper.transform_centroid(ball.centroid)
            if ball_pitch:
                bx, _ = ball_pitch
                self._infer_direction(attackers, defenders, bx)

        # ── Last defender ──────────────────────────────────────────────────────
        last_def = self._get_last_defender(defenders)
        if last_def is None:
            return frame, None

        last_def_pitch = self._mapper.transform_centroid(last_def.centroid)
        if last_def_pitch is None:
            return frame, None

        last_def_x, _ = last_def_pitch

        # ── Draw offside line ──────────────────────────────────────────────────
        frame = self._draw_offside_line(frame, last_def_x)

        # ── Check attackers ────────────────────────────────────────────────────
        ball_played_forward = self._is_ball_played_forward(ball)

        if ball_played_forward:
            for attacker in attackers:
                att_pitch = self._mapper.transform_centroid(attacker.centroid)
                if att_pitch is None:
                    continue
                att_x, _ = att_pitch
                if self._is_offside(att_x, last_def_x):
                    event = OffsideEvent(
                        frame_number=frame_number,
                        offending_player_id=attacker.id,
                        offending_team=self.attacking_team,
                        last_defender_id=last_def.id,
                        last_defender_x_m=last_def_x,
                        attacker_x_m=att_x,
                    )
                    self._last_event = event
                    self._alert_frames_remaining = OFFSIDE_ALERT_FRAMES
                    break   # one event per frame is enough

        # ── Draw alert banner ──────────────────────────────────────────────────
        if self._alert_frames_remaining > 0:
            frame = self._draw_alert_banner(frame)
            self._alert_frames_remaining -= 1

        # ── Update ball position ───────────────────────────────────────────────
        if ball is not None and self._mapper.is_calibrated:
            bp = self._mapper.transform_centroid(ball.centroid)
            if bp:
                self._prev_ball_x = bp[0]

        return frame, event

    # ── Team direction inference ───────────────────────────────────────────────

    def _infer_direction(
        self,
        attackers: List[TrackedObject],
        defenders: List[TrackedObject],
        ball_x: float,
    ):
        """
        Heuristic: if the ball is on the right half of the pitch (x > 52.5m),
        the attacking team is pressing toward the right goal, so their
        offside line should be at a HIGH x value.
        Swap attacking/defending team if needed.
        """
        if not attackers or not defenders:
            return

        atk_xs = [
            self._mapper.transform_centroid(p.centroid)[0]
            for p in attackers
            if self._mapper.transform_centroid(p.centroid)
        ]
        def_xs = [
            self._mapper.transform_centroid(p.centroid)[0]
            for p in defenders
            if self._mapper.transform_centroid(p.centroid)
        ]
        if not atk_xs or not def_xs:
            return

        if np.mean(atk_xs) < np.mean(def_xs):
            # Attackers are toward the low-x goal → swap
            self.attacking_team, self.defending_team = (
                self.defending_team, self.attacking_team
            )

    # ── Core logic helpers ─────────────────────────────────────────────────────

    def _get_last_defender(self, defenders: List[TrackedObject]) -> Optional[TrackedObject]:
        """
        Return the last outfield defender (second-deepest in defense).
        Assumes attackers attack in the +X direction.
        """
        if len(defenders) < 2:
            return defenders[0] if defenders else None

        # Get real-world x positions for all defenders
        defs_with_x = []
        for d in defenders:
            pitch_pos = self._mapper.transform_centroid(d.centroid)
            if pitch_pos:
                defs_with_x.append((d, pitch_pos[0]))

        if not defs_with_x:
            return None

        # Sort by X ascending (defenders deepest in their half have LOWEST or HIGHEST x)
        # We sort descending (highest x = furthest into the attacking direction)
        defs_with_x.sort(key=lambda t: t[1], reverse=True)

        # [0] is the goalkeeper (furthest back), [1] is the last outfield defender
        return defs_with_x[1][0] if len(defs_with_x) >= 2 else defs_with_x[0][0]

    def _is_offside(self, attacker_x: float, last_defender_x: float) -> bool:
        """
        An attacker is offside if they are further forward (higher X) than
        the last defender (excluding goalkeeper).
        Add a small tolerance (0.3 m) to avoid false positives.
        """
        TOLERANCE_M = 0.3
        return attacker_x > last_defender_x + TOLERANCE_M

    def _is_ball_played_forward(self, ball: Optional[TrackedObject]) -> bool:
        """
        Detect a forward pass: ball moves in the positive X direction
        (relative to the attacking team's goal direction).
        """
        if ball is None or self._prev_ball_x is None or not self._mapper.is_calibrated:
            return False
        bp = self._mapper.transform_centroid(ball.centroid)
        if bp is None:
            return False
        curr_ball_x = bp[0]
        return (curr_ball_x - self._prev_ball_x) > 1.5   # moved >1.5 m forward

    # ── Drawing helpers ────────────────────────────────────────────────────────

    def _draw_offside_line(self, frame: np.ndarray, last_def_x: float) -> np.ndarray:
        """Draw a vertical offside line at the last defender's X coordinate."""
        h, w = frame.shape[:2]

        # Find pixel X by converting pitch (last_def_x, 34) → pixel (use mid-pitch Y)
        pixel_top    = self._mapper.pitch_to_pixel(last_def_x, 0)
        pixel_bottom = self._mapper.pitch_to_pixel(last_def_x, 68)

        if pixel_top is None or pixel_bottom is None:
            return frame

        # Clamp to frame bounds
        def clamp(pt):
            return (max(0, min(w - 1, pt[0])), max(0, min(h - 1, pt[1])))

        pt1 = clamp(pixel_top)
        pt2 = clamp(pixel_bottom)

        cv2.line(frame, pt1, pt2, OFFSIDE_LINE_COLOR_BGR, 3)
        cv2.putText(
            frame, "Offside Line",
            (pt1[0] + 5, pt1[1] + 30),
            cv2.FONT_HERSHEY_SIMPLEX, 0.7, OFFSIDE_LINE_COLOR_BGR, 2
        )
        return frame

    def _draw_alert_banner(self, frame: np.ndarray) -> np.ndarray:
        """Draw a prominent OFFSIDE red banner at the top of the frame."""
        h, w = frame.shape[:2]
        banner_h = 70

        overlay = frame.copy()
        cv2.rectangle(overlay, (0, 0), (w, banner_h), (0, 0, 200), -1)
        alpha = 0.75
        frame = cv2.addWeighted(overlay, alpha, frame, 1 - alpha, 0)

        text = "⚑  OFFSIDE!"
        font_scale = 1.8
        thickness = 3
        (tw, th), _ = cv2.getTextSize(text, cv2.FONT_HERSHEY_DUPLEX, font_scale, thickness)
        tx = (w - tw) // 2
        ty = (banner_h + th) // 2

        cv2.putText(frame, text, (tx, ty),
                    cv2.FONT_HERSHEY_DUPLEX, font_scale, (255, 255, 255), thickness)

        if self._last_event:
            detail = (
                f"Player #{self._last_event.offending_player_id} | "
                f"Team {self._last_event.offending_team} | "
                f"Frame {self._last_event.frame_number}"
            )
            cv2.putText(frame, detail, (10, banner_h + 25),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.55, (200, 200, 200), 1)

        return frame

    def _draw_uncalibrated_warning(self, frame: np.ndarray):
        """Warn that pitch calibration is needed."""
        cv2.putText(
            frame,
            "⚠ Pitch not calibrated — click corners to enable offside detection",
            (30, 40), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 100, 255), 2
        )

    # ── Properties ────────────────────────────────────────────────────────────

    @property
    def alert_active(self) -> bool:
        return self._alert_frames_remaining > 0

    @property
    def last_event(self) -> Optional[OffsideEvent]:
        return self._last_event
