#!/usr/bin/env python3
"""
SimpleERP - Backend Launcher
"""
import sys
import os

backend_dir = os.path.dirname(os.path.abspath(__file__))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from server import main

if __name__ == "__main__":
    main()
