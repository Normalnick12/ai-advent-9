"""Optional adapter; the existing local assistant remains the only core."""
from pathlib import Path
import sys

CORE = Path(__file__).resolve().parents[2] / "day-27-local-architecture-assistant"
if str(CORE) not in sys.path:
    sys.path.insert(0, str(CORE))
