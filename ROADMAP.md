# 🗺️ Football Analytics — Build Roadmap

Track upcoming features and improvements here.

---

## ✅ Done (Current State)

| Feature | Status |
|---|---|
| YOLOv8 player/ball detection | ✅ |
| K-Means jersey-color team assignment | ✅ |
| Offside line (2nd-to-last defender rule) | ✅ |
| Image upload → annotated result | ✅ |
| Video upload → processed video | ✅ |
| Detection history DB | ✅ |
| JWT auth (admin / manager roles) | ✅ |
| Match management (create, list) | ✅ |
| MJPEG live stream | ✅ |
| WebSocket real-time alerts | ✅ |
| Custom trained model (YOLOv8x on Roboflow dataset) | ✅ |

---

## 🔜 Next Up — Phase 2

### 1. Pitch Homography (Real-World Coordinates)
- Train pitch keypoint detector (notebook: `training/pitch_detection/`)
- Map pixel coordinates → real-world metres (105×68m pitch)
- Display mini-map overlay with player positions

### 2. Player Speed & Distance Tracking
- Use pitch coordinates + frame timestamps to compute metres/second
- Show per-player stats on the manager dashboard
- Heat-map visualization per player

### 3. Match Event Log UI
- Admin dashboard: timeline of offside events with timestamps
- Clickable events jump to video frame
- Export events as CSV/PDF report

### 4. Manager Dashboard
- Per-club stats across multiple matches
- Player-level comparison charts
- Season aggregates

---

## 🔮 Phase 3 — Advanced Features

### 5. Ball Tracking & Pass Detection
- Track ball trajectory across frames
- Detect pass events (ball changes possession)
- Forward pass triggers offside check

### 6. Formation Detection
- Auto-detect team shape (4-4-2, 4-3-3, etc.) per frame
- Formation timeline chart

### 7. Goal Detection
- Track ball crossing goal line
- Auto-clip highlight around goal event

### 8. Model Improvements
- Fine-tune on more diverse datasets (night games, different camera angles)
- Add pitch keypoint model for better homography
- Experiment with YOLOv9 / RT-DETR

### 9. Deployment
- Dockerize backend + frontend
- GitHub Actions CI/CD
- Deploy to cloud (Render / Railway / AWS)

---

## 📝 Known Limitations

| Issue | Notes |
|---|---|
| Large model (130MB) not in git | Download separately or use Git LFS |
| Video processing is synchronous | Should use background task queue (Celery/ARQ) |
| Offside for still images is approximate | Needs pitch homography for accuracy |
| Team assignment can flip between frames | Needs stable ID-to-team mapping across video |

---

## 🛠️ How to Contribute

1. Pick a task from the roadmap above
2. Create a feature branch: `git checkout -b feat/your-feature`
3. Implement, test, commit
4. Open a PR targeting `main`
