"""
main.py – Entry point. Run with:
    uvicorn main:app --reload --host 0.0.0.0 --port 8000
"""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))

from api.server import app  # noqa: F401
