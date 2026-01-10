"""Vercel serverless function entry point.

This file simply imports and re-exports the FastAPI app from backend/main.py,
ensuring a single source of truth for the API implementation.
"""

import sys
from pathlib import Path

# Add project root to path so backend module can be imported
sys.path.insert(0, str(Path(__file__).parent.parent))

# Import the FastAPI app - Vercel will detect this as an ASGI app
from backend.main import app

# Vercel expects 'app' to be the ASGI application
# This is all that's needed - Vercel's Python runtime handles the rest
