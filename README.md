# ⚽ Football Analytics System

AI-powered real-time football analytics with player tracking, team classification, pitch homography, offside detection, and a dual-portal web UI.

---

## 📂 Project Structure

```
football_analytics/
├── backend/
│   ├── cv_pipeline/           # Computer Vision modules
│   │   ├── config.py          # Central config (model path, colors, thresholds)
│   │   ├── tracker.py         # YOLOv8 + ByteTrack detection & tracking
│   │   ├── team_classifier.py # K-Means jersey-color team assignment
│   │   ├── pitch_mapper.py    # Homography: pixel coords → real-world metres
│   │   ├── offside_logic.py   # Last defender + offside line + alert
│   │   └── models/            # ← Place football_best.pt here after Colab training
│   ├── api/
│   │   ├── database.py        # SQLite schema (SQLAlchemy)
│   │   ├── server.py          # FastAPI app (auth, routes, WebSocket, stream)
│   │   └── streamer.py        # Video processor + MJPEG generator
│   ├── main.py                # Uvicorn entry point
│   ├── requirements.txt
│   ├── uploads/               # Uploaded match videos
│   └── processed/             # (future) processed video output
│
├── colab/
│   └── train_yolov8_football.ipynb  # Run in Google Colab to train the model
│
└── frontend/                  # Next.js web UI
    ├── app/
    │   ├── page.tsx           # Login / Register portal
    │   ├── admin/page.tsx     # Admin dashboard (live feed, offside alerts)
    │   ├── admin/matches/new/ # Create match form
    │   └── manager/page.tsx   # Club manager (player stats)
    └── .env.local             # API URL config
```

---

## 🚀 Getting Started

### Step 1 — Train the Model (Google Colab)

1. Open `colab/train_yolov8_football.ipynb` in [Google Colab](https://colab.research.google.com)
2. Set runtime to **GPU** (Runtime → Change runtime type → T4 GPU)
3. Add your **Roboflow API key** in Step 2
4. Run all cells (~20-30 min)
5. Download `football_best.pt` and place it at:
   ```
   backend/cv_pipeline/models/football_best.pt
   ```

> ✅ **You can do this simultaneously** while the backend and frontend are being set up!

---

### Step 2 — Backend Setup

```powershell
cd football_analytics/backend

# Create virtual environment
python -m venv venv
venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Start the server
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

The API will be live at **http://localhost:8000**  
Interactive docs: **http://localhost:8000/docs**

---

### Step 3 — Frontend Setup

```powershell
cd football_analytics/frontend

npm install
npm run dev
```

Open **http://localhost:3000** in your browser.

---

## 🔐 Default Login

| Role  | Username | Password   |
|-------|----------|------------|
| Admin | `admin`  | `admin1234` |

Club managers can self-register from the login page.

---

## 🧠 How It Works

| Step | Module | What happens |
|------|--------|-------------|
| 1 | `tracker.py` | YOLOv8 detects players, ball, goalkeepers, referees. ByteTrack assigns stable IDs across frames. |
| 2 | `team_classifier.py` | K-Means clusters players into Team A / Team B by jersey colour (HSV dominant colour). |
| 3 | `pitch_mapper.py` | Auto-detects pitch corners via green-mask contour. Computes homography to map pixel → metres on a 105×68m pitch. |
| 4 | `offside_logic.py` | Finds the 2nd-deepest defender (last outfield defender). Draws the offside line. If a forward pass is detected and an attacker is ahead of the line → **OFFSIDE event**. |
| 5 | `streamer.py` | Runs all of the above per frame, encodes to MJPEG for live streaming, persists events to SQLite, broadcasts via WebSocket. |
| 6 | Frontend | Admin sees the live feed + real-time offside alerts. Managers see per-player stats (distance, speed, offside count). |

---

## 🔌 API Reference

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/auth/login` | JWT login |
| `POST` | `/auth/register` | Club manager registration |
| `GET`  | `/matches` | List matches |
| `POST` | `/matches` | Create match (admin) |
| `POST` | `/matches/{id}/upload` | Upload video |
| `GET`  | `/matches/{id}/events` | Offside event log |
| `GET`  | `/matches/{id}/stats` | Player stats |
| `GET`  | `/stream/{id}` | MJPEG video stream |
| `WS`   | `/ws/{id}` | Real-time WebSocket alerts |

---

## ⚙️ Configuration

Edit `backend/cv_pipeline/config.py` to tune:
- `DETECTION_CONF` — detection confidence threshold
- `CLASS_NAMES` — if your dataset uses different class indices
- `OFFSIDE_ALERT_FRAMES` — how long the red banner stays on screen
- `PITCH_REAL_POINTS_M` — real-world pitch dimensions
