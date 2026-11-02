import os
import sys
from pathlib import Path

# Resolve root and backend paths so that 'app.*' modules are cleanly imported
root_dir = Path(__file__).resolve().parent.parent
backend_dir = root_dir / "backend"

if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

# Import the ASGI FastAPI application instance
from app.main import app
