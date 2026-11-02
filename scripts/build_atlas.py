#!/usr/bin/env python3
"""Build the atlas and its study-level descriptive statistics without dependencies."""

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from acm_atlas.cli import main

if __name__ == "__main__":
    main(ROOT)
