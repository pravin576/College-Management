#!/usr/bin/env python3
"""
SimpleERP - Top-Level Launcher
Allows running `python app.py` directly from the College Management root folder.
"""
import sys
import os

backend_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "backend")
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from server import main

if __name__ == "__main__":
    main()
