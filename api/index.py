import sys
from pathlib import Path

# Discover backend directory across both local workspace and Vercel Lambda container:
# 1. current_dir: /var/task (when app/ is inside api/)
# 2. current_dir / "backend": container fallback
# 3. current_dir.parent / "backend": <repo_root>/backend (local workspace fallback)
# 4. Path.cwd(): process working directory
# 5. Path.cwd() / "backend": CWD backend fallback
current_dir = Path(__file__).resolve().parent
candidates = [
    current_dir,
    current_dir / "backend",
    current_dir.parent / "backend",
    Path.cwd(),
    Path.cwd() / "backend",
]

selected_backend_dir = None
for candidate in candidates:
    if (candidate / "app" / "__init__.py").is_file() and (candidate / "app" / "main.py").is_file():
        selected_backend_dir = candidate
        break

if selected_backend_dir is None:
    raise RuntimeError(
        "CRITICAL SERVERLESS BOOTSTRAP ERROR: Could not locate valid backend directory "
        "containing 'app/__init__.py' and 'app/main.py' among candidates: "
        f"{[str(c) for c in candidates]}"
    )

if str(selected_backend_dir) not in sys.path:
    sys.path.insert(0, str(selected_backend_dir))

# Import the ASGI FastAPI application instance
from app.main import app
