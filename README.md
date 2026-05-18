# ⚽ Football Analytics System

AI-powered real-time football analytics with player tracking, team classification, pitch homography, offside detection, and a web UI.

---

## 📂 Project Structure

```
football_analytics/
├── backend/
│   ├── api/                   # API routes and WebSocket management
│   ├── cv_pipeline/           # Computer Vision modules
│   │   ├── models/            # ← Place football_best.pt here
│   │   └── ...
│   ├── database.py            # SQLite schema (SQLAlchemy)
│   ├── offside_detector.py    # Core detection engine (YOLOv8 + K-Means + Offside logic)
│   ├── server.py              # FastAPI app (auth, routes, WebSocket, stream, image processing)
│   └── main.py                # Uvicorn entry point
│
├── colab/                     # Training notebooks
│   └── football_ai.ipynb      # Main YOLOv8 training notebook
│
├── frontend/                  # React + Vite web UI (Drag-and-drop Image/Video upload)
│
├── training/                  # Additional training resources
│   ├── pitch_detection/
│   └── player_detection/
```

---

## 🚀 Getting Started

### Step 1 — Train the Model (Google Colab)

1. Open `colab/football_ai.ipynb` in Google Colab.
2. Train the model using the provided steps.
3. Download `best.pt` and place it at:
   ```
   backend/cv_pipeline/models/football_best.pt
   ```

### Step 2 — Backend Setup

```powershell
cd football_analytics/backend
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
uvicorn api.server:app --reload --host 0.0.0.0 --port 8000
```
Interactive docs: **http://localhost:8000/docs**

### Step 3 — Frontend Setup

```powershell
cd football_analytics/frontend
npm install
npm run dev
```
Open **http://localhost:5173** in your browser.

---

## 🔌 API Reference

### Public Processing Endpoints
| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/process-image` | Upload an image for offside detection |
| `POST` | `/api/process-video` | Upload a video for offside detection |
| `GET`  | `/api/history` | List detection history |

### Auth & Match Endpoints
| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/auth/login` | JWT login |
| `GET`  | `/matches` | List matches |
| `POST` | `/matches/{id}/upload` | Upload video for match processing |

## 🧠 Features

1. **Player & Ball Detection**: YOLOv8 detects players, goalkeepers, referees, and the ball.
2. **Team Classification**: K-Means clusters jersey colors to group players into teams.
3. **Offside Detection**: Computes the 2nd-to-last defender line and checks attacker positions.
4. **Interactive UI**: Drag-and-drop images or videos for instant analysis.
