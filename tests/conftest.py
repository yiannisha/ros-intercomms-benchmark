from __future__ import annotations

from pathlib import Path
import sys


SOURCE_DIR = Path(__file__).resolve().parents[1] / "ros2_netbench" / "src"
if str(SOURCE_DIR) not in sys.path:
    sys.path.insert(0, str(SOURCE_DIR))
