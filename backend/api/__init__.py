"""
api – FastAPI application package.
"""
from api.database import init_db, get_db
from api.streamer import VideoProcessor, connection_manager
