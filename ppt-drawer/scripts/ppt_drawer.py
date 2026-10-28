#!/usr/bin/env python3
"""Portable entrypoint for the project-local PPT workflow."""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "runtime" / "python"))
from ppt_drawer.cli import main

if __name__ == "__main__":
    raise SystemExit(main())
