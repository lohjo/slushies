import sys
from pathlib import Path

# Ensure imports like `from app import ...` work no matter where pytest is launched.
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
