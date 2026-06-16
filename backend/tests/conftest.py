"""Pytest fixtures shared across all tests."""
import os
import sys
from pathlib import Path

# Ensure backend/ is in PYTHONPATH
backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))
