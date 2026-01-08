"""Vercel serverless function handler for FastAPI backend."""

# Add the backend directory to the path
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Import the FastAPI app
from backend.main import app

# Vercel expects the handler to be named 'handler' or 'app'
# For ASGI apps like FastAPI, export the app directly
handler = app
